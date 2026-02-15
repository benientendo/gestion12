from django.core.management.base import BaseCommand
from inventory.models import Article, MouvementStock
import base64


class Command(BaseCommand):
    help = 'Exporte les cas critiques en HTML (affichable/imprimable)'

    def add_arguments(self, parser):
        parser.add_argument('--boutique', type=int, default=44, help='ID de la boutique')

    def handle(self, *args, **options):
        boutique_id = options['boutique']
        
        # Recuperer les articles restaures
        mouvements_restore = MouvementStock.objects.filter(
            article__boutique_id=boutique_id,
            reference_document__startswith="RESTORE-"
        ).select_related('article').order_by('-quantite')
        
        if not mouvements_restore.exists():
            self.stdout.write("Aucun article restaure trouve.")
            return
        
        # Generer HTML
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Rapport Cas Critiques - KMC LUKALA</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; font-size: 12px; }
        h1 { color: #1a365d; text-align: center; }
        h2 { color: #2c5282; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th { background: #1a365d; color: white; padding: 10px; text-align: left; }
        td { padding: 8px; border-bottom: 1px solid #ddd; }
        tr:nth-child(even) { background: #f7fafc; }
        .high { background: #fed7d7 !important; }
        .summary { background: #e2e8f0; padding: 15px; margin: 20px 0; border-radius: 5px; }
        .legend { background: #edf2f7; padding: 10px; margin-top: 20px; font-size: 11px; }
        @media print { body { margin: 0; } }
    </style>
</head>
<body>
    <h1>RAPPORT DES CAS CRITIQUES - KMC LUKALA</h1>
    <p style="text-align:center;">Articles dont plus de 60% du stock a ete restaure</p>
    
    <table>
        <tr>
            <th>#</th>
            <th>Article</th>
            <th>Code</th>
            <th>Stock Actuel</th>
            <th>Restaure</th>
            <th>Validation Init.</th>
            <th>Ecart</th>
        </tr>
"""
        
        total_restaure = 0
        
        for i, mv_restore in enumerate(mouvements_restore, 1):
            article = mv_restore.article
            qte_restauree = mv_restore.quantite
            stock_actuel = article.quantite_stock
            total_restaure += qte_restauree
            
            # Trouver la validation initiale
            validation = MouvementStock.objects.filter(
                article=article,
                reference_document__startswith="VALIDATION-"
            ).first()
            
            qte_validation = validation.quantite if validation else 0
            
            # Calcul de l'ecart
            if stock_actuel > 0:
                ecart_pct = (qte_restauree / stock_actuel) * 100
            else:
                ecart_pct = 100
            
            row_class = "high" if ecart_pct > 80 else ""
            
            html += f"""        <tr class="{row_class}">
            <td>{i}</td>
            <td>{article.nom}</td>
            <td>{article.code or '-'}</td>
            <td>{stock_actuel}</td>
            <td>+{qte_restauree}</td>
            <td>{qte_validation}</td>
            <td>{ecart_pct:.0f}%</td>
        </tr>
"""
        
        html += f"""    </table>
    
    <div class="summary">
        <strong>RESUME:</strong> {mouvements_restore.count()} articles | Stock total restaure: +{total_restaure} unites
    </div>
    
    <div class="legend">
        <strong>LEGENDE:</strong><br>
        - <strong>Stock Actuel</strong>: Quantite en stock apres correction<br>
        - <strong>Restaure</strong>: Quantite ajoutee (etait supprimee par erreur)<br>
        - <strong>Validation Init.</strong>: Premiere validation enregistree<br>
        - <strong>Ecart</strong>: % du stock restaure (rouge si > 80%)<br>
        - Les lignes en rouge indiquent les cas les plus critiques
    </div>
</body>
</html>"""
        
        # Encoder en base64 pour affichage
        html_b64 = base64.b64encode(html.encode('utf-8')).decode('utf-8')
        
        self.stdout.write("=== HTML BASE64 (copier et decoder) ===")
        self.stdout.write(html_b64)
        self.stdout.write("=== FIN ===")
