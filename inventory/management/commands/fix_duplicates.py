from django.core.management.base import BaseCommand
from django.db import transaction
from inventory.models import Article, MouvementStock
from django.db.models import Count, Sum, Min
from django.utils import timezone


class Command(BaseCommand):
    help = 'Corrige les articles avec validations multiples en gardant seulement la premiere'

    def add_arguments(self, parser):
        parser.add_argument('--boutique', type=int, default=44, help='ID de la boutique')
        parser.add_argument('--dry-run', action='store_true', help='Afficher sans modifier')
        parser.add_argument('--fix', action='store_true', help='Appliquer les corrections')

    def handle(self, *args, **options):
        boutique_id = options['boutique']
        dry_run = not options['fix']
        
        if dry_run:
            self.stdout.write(self.style.WARNING("=== MODE SIMULATION (ajouter --fix pour appliquer) ===\n"))
        else:
            self.stdout.write(self.style.SUCCESS("=== MODE CORRECTION ===\n"))

        # Trouver les articles avec plusieurs validations
        articles_multi = MouvementStock.objects.filter(
            article__boutique_id=boutique_id,
            reference_document__startswith="VALIDATION-"
        ).values("article__id").annotate(
            nb=Count("id"),
            total_ajoute=Sum("quantite"),
            premiere_date=Min("date_mouvement")
        ).filter(nb__gt=1).order_by("-nb")

        if not articles_multi.exists():
            self.stdout.write("Aucun article avec validations multiples trouve.")
            return

        self.stdout.write(f"Articles avec validations multiples: {articles_multi.count()}\n")
        
        total_corrige = 0
        total_stock_reduit = 0

        for item in articles_multi:
            article_id = item['article__id']
            
            try:
                article = Article.objects.get(id=article_id)
            except Article.DoesNotExist:
                continue

            # Recuperer tous les mouvements de validation pour cet article
            mouvements = MouvementStock.objects.filter(
                article_id=article_id,
                reference_document__startswith="VALIDATION-"
            ).order_by("date_mouvement")

            mouvements_list = list(mouvements)
            if len(mouvements_list) <= 1:
                continue

            # Garder le premier mouvement, supprimer les autres
            premier_mouvement = mouvements_list[0]
            doublons = mouvements_list[1:]
            
            # Calculer la quantite en trop
            quantite_doublon = sum(m.quantite for m in doublons)
            
            self.stdout.write(f"\n{article.nom[:40]}")
            self.stdout.write(f"  Code: {article.code}")
            self.stdout.write(f"  Validations: {len(mouvements_list)} (garder 1, supprimer {len(doublons)})")
            self.stdout.write(f"  Stock actuel: {article.quantite_stock}")
            self.stdout.write(f"  Quantite en trop: {quantite_doublon}")
            self.stdout.write(f"  Stock corrige: {article.quantite_stock - quantite_doublon}")
            
            for i, mv in enumerate(mouvements_list):
                status = "GARDER" if i == 0 else "SUPPRIMER"
                self.stdout.write(f"    [{status}] {mv.date_mouvement.strftime('%m-%d %H:%M')} +{mv.quantite}")

            if not dry_run:
                with transaction.atomic():
                    # Reduire le stock
                    nouveau_stock = article.quantite_stock - quantite_doublon
                    if nouveau_stock < 0:
                        nouveau_stock = premier_mouvement.quantite  # Au minimum la premiere validation
                    
                    article.quantite_stock = nouveau_stock
                    article.save(update_fields=['quantite_stock'])
                    
                    # Supprimer les mouvements en double
                    for mv in doublons:
                        mv.delete()
                    
                    # Creer un mouvement de correction
                    MouvementStock.objects.create(
                        article=article,
                        type_mouvement='CORRECTION',
                        quantite=-quantite_doublon,
                        reference_document=f'FIX-DOUBLON-{timezone.now().strftime("%Y%m%d")}',
                        commentaire=f'Correction auto: suppression de {len(doublons)} validation(s) en double'
                    )
                    
                    total_corrige += 1
                    total_stock_reduit += quantite_doublon
                    self.stdout.write(self.style.SUCCESS(f"  -> CORRIGE"))

        self.stdout.write(f"\n{'='*50}")
        if dry_run:
            self.stdout.write(self.style.WARNING(f"SIMULATION: {articles_multi.count()} articles a corriger"))
            self.stdout.write("Executez avec --fix pour appliquer les corrections")
        else:
            self.stdout.write(self.style.SUCCESS(f"TERMINE: {total_corrige} articles corriges"))
            self.stdout.write(self.style.SUCCESS(f"Stock total reduit de: {total_stock_reduit} unites"))
