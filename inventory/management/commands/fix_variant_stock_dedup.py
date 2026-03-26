"""
Management command: Corrige le stock pour les ventes ayant 2+ variantes du même parent.

Bug corrigé: Le dedup MouvementStock filtrait par (vente, article, VENTE) sans distinguer
les variantes. Quand 2 variantes du même parent étaient vendues dans la même vente,
seule la 1ère décrémentait le stock. Les suivantes étaient skippées.

Ce script:
1. Trouve toutes les LigneVente des N derniers jours avec une variante
2. Vérifie si un MouvementStock correspondant existe (via commentaire contenant le nom variante)
3. Crée les MouvementStock manquants et corrige le stock du parent

Usage:
    python manage.py fix_variant_stock_dedup --dry-run     # Aperçu sans modifier
    python manage.py fix_variant_stock_dedup                # Appliquer les corrections
    python manage.py fix_variant_stock_dedup --days 7       # Sur 7 jours au lieu de 3
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from inventory.models import Vente, LigneVente, MouvementStock, Article


class Command(BaseCommand):
    help = 'Corrige le stock pour les ventes avec 2+ variantes du même parent (bug dedup)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Aperçu sans appliquer les corrections',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=3,
            help='Nombre de jours à corriger (défaut: 3)',
        )
        parser.add_argument(
            '--boutique',
            type=int,
            default=None,
            help='ID boutique spécifique (défaut: toutes)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        days = options['days']
        boutique_id = options['boutique']

        date_debut = timezone.now() - timedelta(days=days)
        mode = "🔍 DRY-RUN" if dry_run else "🔧 CORRECTION"
        self.stdout.write(f"\n{'='*70}")
        self.stdout.write(f"{mode} — Stock variantes (derniers {days} jours)")
        self.stdout.write(f"{'='*70}\n")

        # 1. Trouver les LigneVente avec variante dans la période
        lignes_qs = LigneVente.objects.filter(
            vente__date_vente__gte=date_debut,
            variante__isnull=False,
            vente__est_annulee=False,
        ).select_related('vente', 'article', 'variante')

        if boutique_id:
            lignes_qs = lignes_qs.filter(vente__boutique_id=boutique_id)
            self.stdout.write(f"📍 Filtré sur boutique ID={boutique_id}")

        lignes_avec_variante = list(lignes_qs.order_by('vente__date_vente'))
        self.stdout.write(f"📊 {len(lignes_avec_variante)} lignes avec variante trouvées\n")

        if not lignes_avec_variante:
            self.stdout.write(self.style.SUCCESS("✅ Aucune ligne avec variante — rien à corriger"))
            return

        # 2. Pour chaque ligne, vérifier si MouvementStock existe
        lignes_manquantes = []
        lignes_ok = 0

        for ligne in lignes_avec_variante:
            nom_variante = ligne.variante.nom_variante
            # Chercher un MouvementStock qui correspond à cette variante spécifique
            mouvement_existe = MouvementStock.objects.filter(
                reference_document=ligne.vente.numero_facture,
                article=ligne.article,
                type_mouvement='VENTE',
                commentaire__contains=f"Variante: {nom_variante}"
            ).exists()

            if mouvement_existe:
                lignes_ok += 1
            else:
                # Vérifier aussi s'il existe un MouvementStock générique (sans variante dans commentaire)
                # pour ce même article+vente — c'est le cas du bug (la 1ère variante a été enregistrée)
                lignes_manquantes.append(ligne)

        self.stdout.write(f"✅ {lignes_ok} lignes déjà correctes (MouvementStock trouvé)")
        self.stdout.write(f"❌ {len(lignes_manquantes)} lignes SANS MouvementStock correspondant\n")

        if not lignes_manquantes:
            self.stdout.write(self.style.SUCCESS("✅ Tout est cohérent — rien à corriger"))
            return

        # 3. Afficher et corriger les lignes manquantes
        self.stdout.write(f"{'─'*70}")
        self.stdout.write(f"DÉTAILS DES LIGNES À CORRIGER:")
        self.stdout.write(f"{'─'*70}")

        corrections = 0
        articles_corriges = {}  # article_id → total quantité manquante

        for ligne in lignes_manquantes:
            vente = ligne.vente
            article = ligne.article
            variante = ligne.variante
            quantite = ligne.quantite

            self.stdout.write(
                f"  📦 Vente {vente.numero_facture[:20]}... | "
                f"{article.nom} → Variante: {variante.nom_variante} | "
                f"Qté: {quantite} | "
                f"Date: {vente.date_vente.strftime('%d/%m/%Y %H:%M')} | "
                f"Boutique: {vente.boutique.nom if vente.boutique else 'N/A'}"
            )

            # Accumuler par article
            if article.id not in articles_corriges:
                articles_corriges[article.id] = {
                    'article': article,
                    'quantite_manquante': 0,
                    'lignes': []
                }
            articles_corriges[article.id]['quantite_manquante'] += quantite
            articles_corriges[article.id]['lignes'].append(ligne)

        self.stdout.write(f"\n{'─'*70}")
        self.stdout.write(f"RÉSUMÉ PAR ARTICLE PARENT:")
        self.stdout.write(f"{'─'*70}")

        for art_id, info in articles_corriges.items():
            article = info['article']
            qte_manquante = info['quantite_manquante']
            stock_actuel = article.quantite_stock
            stock_corrige = stock_actuel - qte_manquante
            self.stdout.write(
                f"  🏷️ {article.nom} (ID:{art_id}) | "
                f"Stock actuel: {stock_actuel} → Corrigé: {stock_corrige} | "
                f"Manque: -{qte_manquante} ({len(info['lignes'])} lignes)"
            )

        if dry_run:
            self.stdout.write(f"\n{'='*70}")
            self.stdout.write(self.style.WARNING(
                f"🔍 DRY-RUN: {len(lignes_manquantes)} corrections à appliquer. "
                f"Relancez SANS --dry-run pour corriger."
            ))
            return

        # 4. Appliquer les corrections
        self.stdout.write(f"\n⚙️ Application des corrections...")

        with transaction.atomic():
            for ligne in lignes_manquantes:
                article = Article.objects.select_for_update().get(id=ligne.article_id)
                variante = ligne.variante
                vente = ligne.vente
                quantite = ligne.quantite

                stock_avant = article.quantite_stock
                article.quantite_stock -= quantite
                article.save(update_fields=['quantite_stock'])

                MouvementStock.objects.create(
                    article=article,
                    type_mouvement='VENTE',
                    quantite=-quantite,
                    stock_avant=stock_avant,
                    stock_apres=article.quantite_stock,
                    reference_document=vente.numero_facture,
                    utilisateur='FIX_DEDUP_VARIANT',
                    commentaire=(
                        f"Vente #{vente.numero_facture} - Variante: {variante.nom_variante} "
                        f"- Prix: {ligne.prix_unitaire} - CORRECTION bug dedup"
                    )
                )
                corrections += 1
                self.stdout.write(
                    f"  ✅ {article.nom} → {variante.nom_variante}: "
                    f"stock {stock_avant} → {article.quantite_stock}"
                )

        self.stdout.write(f"\n{'='*70}")
        self.stdout.write(self.style.SUCCESS(
            f"✅ {corrections} corrections appliquées avec succès!"
        ))
        self.stdout.write(f"{'='*70}\n")
