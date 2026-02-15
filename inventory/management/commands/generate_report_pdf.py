from django.core.management.base import BaseCommand
from inventory.models import Article, MouvementStock
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
import os


class Command(BaseCommand):
    help = 'Genere un PDF des cas critiques (articles restaures)'

    def add_arguments(self, parser):
        parser.add_argument('--boutique', type=int, default=44, help='ID de la boutique')
        parser.add_argument('--output', type=str, default='/tmp/rapport_cas_critiques.pdf', help='Chemin du fichier PDF')

    def handle(self, *args, **options):
        boutique_id = options['boutique']
        output_path = options['output']
        
        self.stdout.write(f"Generation du rapport PDF...")
        
        # Recuperer les articles restaures
        mouvements_restore = MouvementStock.objects.filter(
            article__boutique_id=boutique_id,
            reference_document__startswith="RESTORE-"
        ).select_related('article').order_by('-quantite')
        
        if not mouvements_restore.exists():
            self.stdout.write("Aucun article restaure trouve.")
            return
        
        # Creer le PDF
        doc = SimpleDocTemplate(
            output_path,
            pagesize=landscape(A4),
            rightMargin=1*cm,
            leftMargin=1*cm,
            topMargin=1*cm,
            bottomMargin=1*cm
        )
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        elements = []
        
        # Titre
        title = Paragraph(f"RAPPORT DES CAS CRITIQUES - KMC LUKALA", title_style)
        elements.append(title)
        
        subtitle = Paragraph(f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Total: {mouvements_restore.count()} articles", styles['Normal'])
        elements.append(subtitle)
        elements.append(Spacer(1, 0.5*cm))
        
        # Tableau principal
        data = [['#', 'Article', 'Code', 'Stock Actuel', 'Restaure', 'Validation Initiale', 'Ecart (%)']]
        
        for i, mv_restore in enumerate(mouvements_restore, 1):
            article = mv_restore.article
            qte_restauree = mv_restore.quantite
            stock_actuel = article.quantite_stock
            
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
            
            data.append([
                str(i),
                article.nom[:35],
                article.code[:15] if article.code else '-',
                str(stock_actuel),
                f"+{qte_restauree}",
                str(qte_validation),
                f"{ecart_pct:.0f}%"
            ])
        
        # Style du tableau
        table = Table(data, colWidths=[1*cm, 8*cm, 4*cm, 2.5*cm, 2.5*cm, 3*cm, 2*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 1*cm))
        
        # Resume
        total_restaure = sum(mv.quantite for mv in mouvements_restore)
        resume = Paragraph(f"<b>RESUME:</b> {mouvements_restore.count()} articles | Stock total restaure: +{total_restaure} unites", styles['Normal'])
        elements.append(resume)
        
        # Explication
        elements.append(Spacer(1, 0.5*cm))
        explication = Paragraph(
            "<b>LEGENDE:</b><br/>"
            "- <b>Stock Actuel</b>: Quantite en stock apres correction<br/>"
            "- <b>Restaure</b>: Quantite ajoutee lors de la restauration (etait supprimee par erreur)<br/>"
            "- <b>Validation Initiale</b>: Premiere validation enregistree<br/>"
            "- <b>Ecart</b>: Pourcentage du stock qui a ete restaure (cas critique si > 60%)",
            styles['Normal']
        )
        elements.append(explication)
        
        # Generer le PDF
        doc.build(elements)
        
        self.stdout.write(self.style.SUCCESS(f"PDF genere: {output_path}"))
        self.stdout.write(f"Taille: {os.path.getsize(output_path)} bytes")
