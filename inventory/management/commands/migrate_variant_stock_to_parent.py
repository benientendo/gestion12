"""
Migration: stock des variantes → article parent
================================================
Pour chaque article ayant des variantes actives :
  - Calcule la somme des stocks de toutes les variantes actives
  - Met à jour article.quantite_stock avec cette somme

Usage:
  python manage.py migrate_variant_stock_to_parent           # dry-run (aperçu sans modifier)
  python manage.py migrate_variant_stock_to_parent --execute  # applique la migration
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from inventory.models import Article, VarianteArticle, MouvementStock


class Command(BaseCommand):
    help = "Transfère le stock réparti dans les variantes vers l'article parent"

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
        nb_ignores = 0

        self.stdout.write(f"Articles concernés : {total_articles}\n")
        self.stdout.write("-" * 70)

        with transaction.atomic():
            for article in articles_avec_variantes:
                variantes_actives = article.variantes.filter(est_actif=True)
                somme_variantes = sum(v.quantite_stock for v in variantes_actives)
                stock_parent_actuel = article.quantite_stock

                # Si le parent a déjà un stock non nul et différent de la somme,
                # on prend la SOMME des variantes (source de vérité avant la migration)
                if somme_variantes == 0 and stock_parent_actuel > 0:
                    # Parent a du stock, variantes vides → déjà géré au parent, on laisse
                    statut = "IGNORÉ (parent déjà à jour)"
                    nb_ignores += 1
                elif somme_variantes == stock_parent_actuel:
                    statut = "DÉJÀ OK"
                    nb_deja_ok += 1
                else:
                    statut = f"MIGRATION : variantes={somme_variantes} → parent {stock_parent_actuel} → {somme_variantes}"
                    nb_migres += 1

                    if execute:
                        article.quantite_stock = somme_variantes
                        article.save(update_fields=['quantite_stock'])

                        # Mouvement de stock pour traçabilité
                        if somme_variantes != stock_parent_actuel:
                            MouvementStock.objects.create(
                                article=article,
                                type_mouvement='CORRECTION',
                                quantite=abs(somme_variantes - stock_parent_actuel),
                                stock_avant=stock_parent_actuel,
                                stock_apres=somme_variantes,
                                reference_document='MIGRATION-VAR-PARENT',
                                commentaire=(
                                    f"Migration stock variantes → parent. "
                                    f"Variantes: {', '.join(f'{v.nom_variante}={v.quantite_stock}' for v in variantes_actives)}"
                                )
                            )

                detail_variantes = ", ".join(
                    f"{v.nom_variante}={v.quantite_stock}" for v in variantes_actives
                )
                self.stdout.write(
                    f"  [{article.boutique_id}] {article.nom:<30} | {detail_variantes:<40} | {statut}"
                )

            if not execute:
                # Annuler toutes les modifications en dry-run
                transaction.set_rollback(True)

        self.stdout.write("-" * 70)
        self.stdout.write(self.style.SUCCESS(
            f"\nRésumé ({'DRY-RUN' if not execute else 'EXÉCUTÉ'}):"
        ))
        self.stdout.write(f"  Total articles avec variantes : {total_articles}")
        self.stdout.write(self.style.SUCCESS(f"  À migrer / migrés             : {nb_migres}"))
        self.stdout.write(f"  Déjà corrects                 : {nb_deja_ok}")
        self.stdout.write(self.style.WARNING(f"  Ignorés (parent déjà à jour)  : {nb_ignores}"))

        if not execute:
            self.stdout.write(self.style.WARNING(
                "\n→ Relancez avec --execute pour appliquer les changements.\n"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\n✓ Migration terminée. Mouvements de stock créés pour traçabilité.\n"
            ))
