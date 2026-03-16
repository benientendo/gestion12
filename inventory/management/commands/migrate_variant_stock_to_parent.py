"""
Migration: stock des variantes → article parent
================================================
Logique :
  - Le stock du PARENT est conservé tel quel (source fiable = achats/approvisionnements)
  - Tous les stocks des variantes sont remis à 0 (les variantes ne gèrent plus le stock)
  - Les ventes futures décrémentent uniquement le parent

Usage:
  python manage.py migrate_variant_stock_to_parent           # dry-run (aperçu sans modifier)
  python manage.py migrate_variant_stock_to_parent --execute  # applique la migration
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from inventory.models import Article, VarianteArticle, MouvementStock


class Command(BaseCommand):
    help = "Remet les stocks variants à 0 — le parent devient la seule source de stock"

    def add_arguments(self, parser):
        parser.add_argument(
            '--execute',
            action='store_true',
            help='Appliquer la migration (sans ce flag : affichage seulement)',
        )

    def handle(self, *args, **options):
        execute = options['execute']

        if not execute:
            self.stdout.write(self.style.WARNING(
                "\n[DRY-RUN] Aperçu sans modification. Ajoutez --execute pour appliquer.\n"
            ))
        else:
            self.stdout.write(self.style.SUCCESS("\n[EXECUTE] Migration en cours...\n"))

        # Articles ayant au moins une variante active
        articles_avec_variantes = Article.objects.filter(
            variantes__est_actif=True
        ).distinct().order_by('boutique_id', 'nom')

        total_articles = articles_avec_variantes.count()
        nb_migres = 0
        nb_deja_ok = 0

        self.stdout.write(f"Articles concernés : {total_articles}\n")
        self.stdout.write("-" * 70)

        with transaction.atomic():
            for article in articles_avec_variantes:
                variantes_actives = article.variantes.filter(est_actif=True)
                somme_variantes = sum(v.quantite_stock for v in variantes_actives)
                stock_parent_actuel = article.quantite_stock

                # Vérifier si des variantes ont encore du stock non nul
                variantes_non_nulles = [v for v in variantes_actives if v.quantite_stock != 0]

                if not variantes_non_nulles:
                    statut = "DÉJÀ OK (variants=0)"
                    nb_deja_ok += 1
                else:
                    statut = (
                        f"MIGRATION : variants=[{', '.join(f'{v.nom_variante}={v.quantite_stock}' for v in variantes_non_nulles)}]"
                        f" → remis à 0 | parent conservé={stock_parent_actuel}"
                    )
                    nb_migres += 1

                    if execute:
                        # Remettre tous les stocks des variantes à 0
                        for v in variantes_non_nulles:
                            v.quantite_stock = 0
                            v.save(update_fields=['quantite_stock'])

                        # Mouvement de stock pour traçabilité
                        MouvementStock.objects.create(
                            article=article,
                            type_mouvement='CORRECTION',
                            quantite=0,
                            stock_avant=stock_parent_actuel,
                            stock_apres=stock_parent_actuel,
                            reference_document='MIGRATION-VAR-PARENT',
                            commentaire=(
                                f"Migration variants→parent: stocks variants remis à 0. "
                                f"Parent conservé={stock_parent_actuel}. "
                                f"Variants zeroed: {', '.join(f'{v.nom_variante}={v.quantite_stock}' for v in variantes_actives)}"
                            )
                        )

                self.stdout.write(
                    f"  [{article.boutique_id}] {article.nom:<35} | {statut}"
                )

            if not execute:
                transaction.set_rollback(True)

        self.stdout.write("-" * 70)
        self.stdout.write(self.style.SUCCESS(
            f"\nRésumé ({'DRY-RUN' if not execute else 'EXÉCUTÉ'}):"
        ))
        self.stdout.write(f"  Total articles avec variantes : {total_articles}")
        self.stdout.write(self.style.SUCCESS(f"  Variants remis à 0            : {nb_migres}"))
        self.stdout.write(f"  Déjà corrects (variants=0)    : {nb_deja_ok}")

        if not execute:
            self.stdout.write(self.style.WARNING(
                "\n→ Relancez avec --execute pour appliquer les changements.\n"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\n✓ Migration terminée. Stocks variants remis à 0. Parent inchangé.\n"
            ))
