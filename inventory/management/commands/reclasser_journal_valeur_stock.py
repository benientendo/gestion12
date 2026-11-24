"""
Commande de gestion : reclasser_journal_valeur_stock
=====================================================
Réécrit les colonnes de flux du journal de valeur (Inventaire, Stock ajouté,
Transfert IN, Transfert OUT, Stock sorti) directement depuis les MouvementStock,
avec les règles de classification de ``inventory.journal_valeur_stock``, puis
recalcule la chaîne valeur_stock_precedent → valeur_stock_restant.

« Ventes », « Modif. prix » et « Réduction » ont des sources propres et ne sont
jamais touchées.

À utiliser après un changement de règles de classification. La migration
0089_reclasser_journal_valeur_stock appelle exactement la même fonction au
déploiement ; cette commande permet de la relancer (une boutique, une période).

Usage :
    python manage.py reclasser_journal_valeur_stock
    python manage.py reclasser_journal_valeur_stock --boutique-id 97
    python manage.py reclasser_journal_valeur_stock --date-debut 2026-11-01
    python manage.py reclasser_journal_valeur_stock --date-fin 2026-11-24
"""

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from inventory.journal_valeur_stock import reclasser_colonnes_depuis_mouvements
from inventory.models import Boutique


class Command(BaseCommand):
    help = (
        "Réécrit les colonnes de flux du journal de valeur depuis les "
        "MouvementStock (Inventaire, Stock ajouté, Transfert IN/OUT, Stock sorti)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--boutique-id', type=int, default=None,
            help="Traiter uniquement cette boutique (ID). Sans cette option : toutes.",
        )
        parser.add_argument(
            '--date-debut', default=None,
            help="Date de début (AAAA-MM-JJ). Défaut : depuis le début.",
        )
        parser.add_argument(
            '--date-fin', default=None,
            help="Date de fin (AAAA-MM-JJ). Défaut : jusqu'à aujourd'hui.",
        )

    def handle(self, *args, **options):
        date_debut = self._date(options['date_debut'], 'date-debut')
        date_fin = self._date(options['date_fin'], 'date-fin')

        if options['boutique_id']:
            boutiques = Boutique.objects.filter(pk=options['boutique_id'])
            if not boutiques.exists():
                raise CommandError(f"Boutique ID={options['boutique_id']} introuvable.")
        else:
            boutiques = Boutique.objects.all()

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Reclassification du journal de valeur — {boutiques.count()} boutique(s)"
        ))

        total = 0
        for boutique in boutiques:
            reecrites = reclasser_colonnes_depuis_mouvements(
                boutique, date_debut=date_debut, date_fin=date_fin,
            )
            total += reecrites
            self.stdout.write(
                f"  → {boutique.nom} (ID={boutique.id}) : {reecrites} ligne(s) réécrite(s)"
            )

        self.stdout.write(self.style.SUCCESS(f"Terminé : {total} ligne(s)."))

    @staticmethod
    def _date(valeur, nom):
        if not valeur:
            return None
        try:
            return datetime.strptime(valeur, '%Y-%m-%d').date()
        except ValueError:
            raise CommandError(f"{nom} invalide : {valeur} (format AAAA-MM-JJ attendu)")
