"""
Commande de gestion : initialiser_journal_valeur_stock
=======================================================
Reconstruit le JournalValeurStock depuis les données existantes
(MouvementStock + Article). À lancer une seule fois après la migration,
ou à nouveau si vous suspectez une incohérence.

Usage :
    python manage.py initialiser_journal_valeur_stock
    python manage.py initialiser_journal_valeur_stock --boutique-id 3
    python manage.py initialiser_journal_valeur_stock --reset
"""

from decimal import Decimal
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import Boutique, MouvementStock, JournalValeurStock
from inventory.journal_valeur_stock import recalculer_tout_depuis_debut


class Command(BaseCommand):
    help = "Initialise ou reconstruit le JournalValeurStock depuis les MouvementStock existants."

    def add_arguments(self, parser):
        parser.add_argument(
            '--boutique-id',
            type=int,
            default=None,
            help="Traiter uniquement cette boutique (ID). Sans cette option : toutes les boutiques."
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            default=False,
            help="Supprime d'abord toutes les lignes existantes avant de reconstruire."
        )

    def handle(self, *args, **options):
        boutique_id = options['boutique_id']
        reset = options['reset']

        if boutique_id:
            boutiques = Boutique.objects.filter(pk=boutique_id)
            if not boutiques.exists():
                self.stderr.write(self.style.ERROR(f"Boutique ID={boutique_id} introuvable."))
                return
        else:
            boutiques = Boutique.objects.all()

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Initialisation JournalValeurStock — {boutiques.count()} boutique(s)"
        ))

        for boutique in boutiques:
            self._traiter_boutique(boutique, reset)

        self.stdout.write(self.style.SUCCESS("Terminé."))

    def _traiter_boutique(self, boutique, reset):
        self.stdout.write(f"\n  Boutique : {boutique.nom} (ID={boutique.id})")

        if reset:
            deleted, _ = JournalValeurStock.objects.filter(boutique=boutique).delete()
            self.stdout.write(f"    → {deleted} ligne(s) supprimée(s)")

        # Récupère tous les mouvements des articles de cette boutique, triés par date
        mouvements = (
            MouvementStock.objects
            .filter(article__boutique=boutique)
            .select_related('article')
            .order_by('date_mouvement')
        )

        total = mouvements.count()
        if total == 0:
            self.stdout.write("    → Aucun mouvement trouvé, rien à faire.")
            return

        self.stdout.write(f"    → {total} mouvement(s) à traiter…")

        # Accumulation par date
        # Structure : {date: {champ: valeur_cumulée}}
        cumuls = defaultdict(lambda: defaultdict(Decimal))

        for mouv in mouvements:
            article = mouv.article
            prix_vente = Decimal(str(article.prix_vente or 0))
            quantite = abs(mouv.quantite)
            valeur = prix_vente * quantite
            ref = mouv.reference_document or ''
            type_mouv = mouv.type_mouvement
            date_j = mouv.date_mouvement.date()

            if type_mouv == 'VENTE':
                cumuls[date_j]['valeur_ventes'] += valeur

            elif type_mouv == 'ENTREE':
                if ref.startswith('TRANSFERT-'):
                    cumuls[date_j]['valeur_transfert_entrant'] += valeur
                else:
                    cumuls[date_j]['valeur_stock_ajoute'] += valeur

            elif type_mouv == 'SORTIE':
                if ref.startswith('TRANSFERT-'):
                    cumuls[date_j]['valeur_transfert_sortant'] += valeur
                else:
                    cumuls[date_j]['valeur_stock_sorti'] += valeur

            elif type_mouv == 'AJUSTEMENT':
                impact = prix_vente * Decimal(str(mouv.quantite))
                cumuls[date_j]['montant_inventaire'] += impact

            elif type_mouv == 'RETOUR':
                cumuls[date_j]['valeur_stock_ajoute'] += valeur

        # Écriture en base dans l'ordre chronologique
        dates_triees = sorted(cumuls.keys())
        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for date_j in dates_triees:
                data = cumuls[date_j]
                ligne, created = JournalValeurStock.objects.get_or_create(
                    boutique=boutique,
                    date=date_j,
                    defaults={'valeur_stock_precedent': Decimal('0')}
                )
                # Additionner (ne pas écraser, au cas où des données existent déjà)
                ligne.valeur_ventes += data.get('valeur_ventes', Decimal('0'))
                ligne.valeur_stock_ajoute += data.get('valeur_stock_ajoute', Decimal('0'))
                ligne.valeur_transfert_entrant += data.get('valeur_transfert_entrant', Decimal('0'))
                ligne.valeur_transfert_sortant += data.get('valeur_transfert_sortant', Decimal('0'))
                ligne.valeur_stock_sorti += data.get('valeur_stock_sorti', Decimal('0'))
                ligne.montant_inventaire += data.get('montant_inventaire', Decimal('0'))
                ligne.save()

                if created:
                    created_count += 1
                else:
                    updated_count += 1

        self.stdout.write(f"    → {created_count} ligne(s) créée(s), {updated_count} mise(s) à jour")

        # Recalculer les valeurs_stock_precedent dans l'ordre chronologique
        recalculer_tout_depuis_debut(boutique)
        self.stdout.write(f"    → Chaîne valeur_stock_precedent recalculée")
