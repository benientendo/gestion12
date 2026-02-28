from django.core.management.base import BaseCommand
from inventory.models import Boutique, Article, VarianteArticle
from django.utils import timezone


class Command(BaseCommand):
    help = 'Verifier et reinitialiser les stocks d une boutique'

    def add_arguments(self, parser):
        parser.add_argument('boutique_id', type=int)
        parser.add_argument('--reset', action='store_true', help='Reinitialiser les stocks')

    def handle(self, *args, **options):
        boutique_id = options['boutique_id']
        
        try:
            b = Boutique.objects.get(id=boutique_id)
            self.stdout.write(f"Boutique: {b.nom}")
            self.stdout.write(f"Commercant: {b.commercant.nom_entreprise}")
            articles = Article.objects.filter(boutique_id=boutique_id, est_actif=True)
            variantes = VarianteArticle.objects.filter(
                article_parent__boutique_id=boutique_id, est_actif=True
            )
            self.stdout.write(f"Nombre d articles: {articles.count()}")
            self.stdout.write(f"Nombre de variantes: {variantes.count()}")
            
            if options['reset']:
                nb_articles = articles.update(
                    quantite_stock=0,
                    prix_vente=0,
                    date_mise_a_jour=timezone.now()
                )
                nb_variantes = variantes.update(
                    quantite_stock=0,
                    date_mise_a_jour=timezone.now()
                )
                self.stdout.write(self.style.SUCCESS(
                    f"{nb_articles} articles + {nb_variantes} variantes reinitialises"
                ))
            else:
                self.stdout.write(self.style.WARNING("Ajoutez --reset pour reinitialiser"))
                
        except Boutique.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Boutique ID {boutique_id} introuvable"))
