from django.core.management.base import BaseCommand
from inventory.models import Article, MouvementStock
from django.db.models import Sum


class Command(BaseCommand):
    help = 'Analyse les corrections effectuees et identifie les cas problematiques'

    def add_arguments(self, parser):
        parser.add_argument('--boutique', type=int, default=44, help='ID de la boutique')
        parser.add_argument('--restore', action='store_true', help='Restaurer le stock pour les cas problematiques')

    def handle(self, *args, **options):
        boutique_id = options['boutique']
        do_restore = options['restore']
        
        self.stdout.write(f"=== ANALYSE DES CORRECTIONS BOUTIQUE {boutique_id} ===\n")

        # Recuperer les mouvements de correction
        corrections = MouvementStock.objects.filter(
            article__boutique_id=boutique_id,
            reference_document__startswith="FIX-DOUBLON"
        ).select_related("article").order_by("quantite")  # Du plus negatif au moins negatif

        if not corrections.exists():
            self.stdout.write("Aucune correction trouvee.")
            return

        self.stdout.write(f"Total corrections: {corrections.count()}\n")
        
        # Analyser chaque correction
        cas_problematiques = []
        
        for c in corrections:
            article = c.article
            qte_retiree = abs(c.quantite)
            stock_actuel = article.quantite_stock
            
            # Cas problematique: si on a retire plus que le stock actuel
            # ou si le stock est tres bas apres correction
            ratio = qte_retiree / (stock_actuel + qte_retiree) if (stock_actuel + qte_retiree) > 0 else 1
            
            if ratio > 0.6:  # Plus de 60% du stock a ete retire
                cas_problematiques.append({
                    'article': article,
                    'correction': c,
                    'qte_retiree': qte_retiree,
                    'stock_actuel': stock_actuel,
                    'stock_avant': stock_actuel + qte_retiree,
                    'ratio': ratio
                })

        self.stdout.write(f"\n--- CAS POTENTIELLEMENT PROBLEMATIQUES ({len(cas_problematiques)}) ---")
        self.stdout.write("(plus de 60% du stock retire)\n")
        
        for cas in cas_problematiques[:30]:
            art = cas['article']
            self.stdout.write(f"\n{art.nom[:40]}")
            self.stdout.write(f"  Code: {art.code}")
            self.stdout.write(f"  Stock avant: {cas['stock_avant']} -> apres: {cas['stock_actuel']}")
            self.stdout.write(f"  Retire: {cas['qte_retiree']} ({cas['ratio']*100:.0f}% du total)")
            self.stdout.write(f"  Commentaire: {cas['correction'].commentaire}")

        # Stats globales
        total_retire = sum(abs(c.quantite) for c in corrections)
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"TOTAL retire: {total_retire} unites")
        self.stdout.write(f"Cas problematiques: {len(cas_problematiques)} articles")
        
        if cas_problematiques and not do_restore:
            self.stdout.write(self.style.WARNING("\nPour restaurer le stock des cas problematiques, executez avec --restore"))
        
        if do_restore and cas_problematiques:
            from django.db import transaction
            from django.utils import timezone
            
            self.stdout.write(self.style.SUCCESS("\n=== RESTAURATION DU STOCK ===\n"))
            
            total_restaure = 0
            articles_restaures = 0
            
            for cas in cas_problematiques:
                art = cas['article']
                qte_a_restaurer = cas['qte_retiree']
                correction_mv = cas['correction']
                
                with transaction.atomic():
                    # Restaurer le stock
                    art.quantite_stock += qte_a_restaurer
                    art.save(update_fields=['quantite_stock'])
                    
                    # Creer un mouvement de restauration
                    MouvementStock.objects.create(
                        article=art,
                        type_mouvement='CORRECTION',
                        quantite=qte_a_restaurer,
                        reference_document=f'RESTORE-{timezone.now().strftime("%Y%m%d")}',
                        commentaire=f'Restauration: correction excessive annulee ({cas["ratio"]*100:.0f}% retire)'
                    )
                    
                    # Supprimer l'ancien mouvement de correction
                    correction_mv.delete()
                    
                    total_restaure += qte_a_restaurer
                    articles_restaures += 1
                    
                    self.stdout.write(f"  {art.nom[:35]} | +{qte_a_restaurer} restaure | nouveau stock: {art.quantite_stock}")
            
            self.stdout.write(self.style.SUCCESS(f"\n=== TERMINE ==="))
            self.stdout.write(self.style.SUCCESS(f"Articles restaures: {articles_restaures}"))
            self.stdout.write(self.style.SUCCESS(f"Stock total restaure: {total_restaure} unites"))
