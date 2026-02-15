from django.core.management.base import BaseCommand
from inventory.models import Article, MouvementStock
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Analyse les articles avec quantites doublees apres validation'

    def add_arguments(self, parser):
        parser.add_argument('--boutique', type=int, default=44, help='ID de la boutique')

    def handle(self, *args, **options):
        boutique_id = options['boutique']
        self.stdout.write(f"=== ANALYSE BOUTIQUE ID {boutique_id} ===\n")

        # 1. Articles avec plusieurs validations
        self.stdout.write("1. ARTICLES AVEC PLUSIEURS VALIDATIONS:")
        multi = MouvementStock.objects.filter(
            article__boutique_id=boutique_id,
            reference_document__startswith="VALIDATION-"
        ).values(
            "article__id", "article__nom", "article__code", "article__quantite_stock"
        ).annotate(
            nb=Count("id"), total=Sum("quantite")
        ).filter(nb__gt=1).order_by("-nb")

        for a in multi[:15]:
            self.stdout.write(f"  {a['article__nom'][:40]} | {a['nb']} valid. | +{a['total']} | stock={a['article__quantite_stock']}")
            
            # Details des mouvements
            mouvements = MouvementStock.objects.filter(
                article_id=a['article__id'],
                reference_document__startswith='VALIDATION-'
            ).order_by('date_mouvement')
            for mv in mouvements:
                self.stdout.write(f"    -> {mv.date_mouvement} | +{mv.quantite} | {mv.reference_document}")

        if not multi.exists():
            self.stdout.write("  Aucun article avec plusieurs validations.")

        # 2. Validations recentes
        self.stdout.write("\n2. VALIDATIONS RECENTES (7 jours):")
        recent = MouvementStock.objects.filter(
            article__boutique_id=boutique_id,
            reference_document__startswith="VALIDATION-",
            date_mouvement__gte=timezone.now() - timedelta(days=7)
        ).select_related("article").order_by("-date_mouvement")[:20]

        for mv in recent:
            self.stdout.write(
                f"  {mv.date_mouvement.strftime('%m-%d %H:%M')} | {mv.article.nom[:30]} | +{mv.quantite} | stock={mv.article.quantite_stock}"
            )

        # 3. Stock potentiellement double
        self.stdout.write("\n3. STOCK POSSIBLEMENT DOUBLE (stock = 2x validation):")
        found_double = False
        for mv in recent:
            if mv.quantite > 0 and mv.article.quantite_stock == mv.quantite * 2:
                found_double = True
                self.stdout.write(f"  !! {mv.article.nom}")
                self.stdout.write(f"     Code: {mv.article.code}")
                self.stdout.write(f"     Validation: +{mv.quantite} | Stock actuel: {mv.article.quantite_stock}")
        
        if not found_double:
            self.stdout.write("  Aucun cas detecte.")

        # 4. Articles en attente de validation
        self.stdout.write("\n4. ARTICLES EN ATTENTE DE VALIDATION:")
        pending = Article.objects.filter(
            boutique_id=boutique_id, 
            est_valide_client=False, 
            est_actif=True
        )
        for a in pending[:10]:
            self.stdout.write(f"  {a.nom[:35]} | envoyee={a.quantite_envoyee} | stock={a.quantite_stock}")
        
        if not pending.exists():
            self.stdout.write("  Aucun article en attente.")

        self.stdout.write("\n=== FIN ===")
