from django.core.management.base import BaseCommand
from inventory.models import Article, MouvementStock


class Command(BaseCommand):
    help = 'Verifie l historique des mouvements pour quelques articles'

    def add_arguments(self, parser):
        parser.add_argument('--boutique', type=int, default=44, help='ID de la boutique')

    def handle(self, *args, **options):
        boutique_id = options['boutique']
        
        self.stdout.write("=== VERIFICATION DES ARTICLES RESTAURES ===\n")
        
        # Trouver les articles qui ont un mouvement RESTORE
        articles_restaures = MouvementStock.objects.filter(
            article__boutique_id=boutique_id,
            reference_document__startswith="RESTORE-"
        ).select_related('article').order_by('-quantite')[:5]
        
        for mv_restore in articles_restaures:
            article = mv_restore.article
            try:
                self.stdout.write(f"\n{'='*60}")
                self.stdout.write(f"ARTICLE: {article.nom}")
                self.stdout.write(f"Code: {article.code}")
                self.stdout.write(f"Stock actuel: {article.quantite_stock}")
                self.stdout.write(f"{'='*60}")
                
                # Recuperer tous les mouvements
                mouvements = MouvementStock.objects.filter(
                    article=article
                ).order_by('date_mouvement')
                
                if not mouvements.exists():
                    self.stdout.write("  Aucun mouvement")
                    continue
                
                # Calculer le stock theorique
                stock_theorique = 0
                
                self.stdout.write("\nHistorique des mouvements:")
                for mv in mouvements:
                    stock_theorique += mv.quantite
                    self.stdout.write(
                        f"  {mv.date_mouvement.strftime('%Y-%m-%d %H:%M')} | "
                        f"{mv.type_mouvement:12} | "
                        f"{mv.quantite:+6} | "
                        f"= {stock_theorique:6} | "
                        f"{mv.reference_document[:30] if mv.reference_document else '-'}"
                    )
                
                # Comparer
                self.stdout.write(f"\nStock theorique (somme mouvements): {stock_theorique}")
                self.stdout.write(f"Stock en base: {article.quantite_stock}")
                
                if stock_theorique == article.quantite_stock:
                    self.stdout.write(self.style.SUCCESS("OK - Les stocks correspondent"))
                else:
                    diff = article.quantite_stock - stock_theorique
                    self.stdout.write(self.style.ERROR(f"ECART de {diff} unites!"))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erreur pour {article.nom}: {e}"))
        
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write("Verification terminee")
