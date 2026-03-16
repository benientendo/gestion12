"""
Commande Django pour migrer les stocks des variants vers les parents.

Cette commande :
1. Pour chaque article ayant des variants
2. Calcule la SOMME des stocks de tous ses variants
3. Ajoute cette somme au stock du parent
4. Met les stocks des variants à 0 (obsolètes)

Usage:
    python manage.py migrer_stocks_variants
    python manage.py migrer_stocks_variants --dry-run  # Simulation sans modification
    python manage.py migrer_stocks_variants --boutique-id 44  # Pour une boutique spécifique
"""

from django.core.management.base import BaseCommand
from django.db.models import Sum
from inventory.models import Article, VarianteArticle, Boutique, MouvementStock
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migre les stocks des variants vers les articles parents'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulation sans modification de la base de données',
        )
        parser.add_argument(
            '--boutique-id',
            type=int,
            help='ID de la boutique à migrer (optionnel, toutes par défaut)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        boutique_id = options.get('boutique_id')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 MODE SIMULATION - Aucune modification ne sera effectuée'))
        
        # Filtrer par boutique si spécifié
        if boutique_id:
            try:
                boutique = Boutique.objects.get(id=boutique_id)
                self.stdout.write(f'📍 Migration pour la boutique : {boutique.nom} (ID: {boutique_id})')
                articles = Article.objects.filter(boutique_id=boutique_id)
            except Boutique.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'❌ Boutique {boutique_id} introuvable'))
                return
        else:
            self.stdout.write('📍 Migration pour TOUTES les boutiques')
            articles = Article.objects.all()
        
        # Récupérer tous les articles ayant des variants
        articles_avec_variants = articles.filter(variantes__isnull=False).distinct()
        
        self.stdout.write(f'\n📦 {articles_avec_variants.count()} articles avec variants trouvés\n')
        
        total_articles_migres = 0
        total_stock_transfere = 0
        
        for article in articles_avec_variants:
            # Récupérer tous les variants actifs de cet article
            variants = article.variantes.filter(est_actif=True)
            
            if not variants.exists():
                continue
            
            # Calculer la somme des stocks des variants
            somme_stocks_variants = variants.aggregate(total=Sum('quantite_stock'))['total'] or 0
            
            if somme_stocks_variants == 0:
                continue
            
            stock_parent_avant = article.quantite_stock
            stock_parent_apres = stock_parent_avant + somme_stocks_variants
            
            self.stdout.write(f'\n📦 Article: {article.nom} (ID: {article.id})')
            self.stdout.write(f'   └─ Stock parent avant : {stock_parent_avant}')
            self.stdout.write(f'   └─ Variants ({variants.count()}) :')
            
            for variant in variants:
                if variant.quantite_stock > 0:
                    self.stdout.write(f'      ├─ {variant.nom_variante}: {variant.quantite_stock} unités')
            
            self.stdout.write(f'   └─ Somme stocks variants : {somme_stocks_variants}')
            self.stdout.write(self.style.SUCCESS(f'   └─ Stock parent après : {stock_parent_apres}'))
            
            if not dry_run:
                # Mettre à jour le stock du parent
                article.quantite_stock = stock_parent_apres
                article.save(update_fields=['quantite_stock'])
                
                # Créer un mouvement de stock pour traçabilité
                MouvementStock.objects.create(
                    article=article,
                    type_mouvement='AJUSTEMENT',
                    quantite=somme_stocks_variants,
                    stock_avant=stock_parent_avant,
                    stock_apres=stock_parent_apres,
                    reference_document='MIGRATION-VARIANTS',
                    utilisateur='SYSTEM',
                    commentaire=f'Migration stocks variants vers parent ({variants.count()} variants)'
                )
                
                # Mettre les stocks des variants à 0 (obsolètes)
                for variant in variants:
                    if variant.quantite_stock > 0:
                        variant.quantite_stock = 0
                        variant.save(update_fields=['quantite_stock'])
                
                self.stdout.write(self.style.SUCCESS(f'   ✅ Migration effectuée'))
            else:
                self.stdout.write(self.style.WARNING(f'   🔍 Simulation - Aucune modification'))
            
            total_articles_migres += 1
            total_stock_transfere += somme_stocks_variants
        
        # Résumé
        self.stdout.write('\n' + '='*60)
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 SIMULATION TERMINÉE'))
        else:
            self.stdout.write(self.style.SUCCESS('✅ MIGRATION TERMINÉE'))
        
        self.stdout.write(f'\n📊 Résumé :')
        self.stdout.write(f'   ├─ Articles migrés : {total_articles_migres}')
        self.stdout.write(f'   └─ Stock total transféré : {total_stock_transfere} unités')
        
        if dry_run:
            self.stdout.write('\n💡 Pour effectuer la migration, relancez sans --dry-run')
        else:
            self.stdout.write('\n✅ Les stocks des variants ont été transférés aux parents')
            self.stdout.write('✅ Les mouvements de stock ont été enregistrés pour traçabilité')
