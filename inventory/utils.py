from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import cm, inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from django.conf import settings
import os
from io import BytesIO
from PIL import Image as PILImage
import tempfile
from django.db import transaction
import logging
from decimal import Decimal
import time

logger = logging.getLogger(__name__)

# Classe personnalisée pour créer un PDF sans horodatage
class NoTimestampDocTemplate(SimpleDocTemplate):
    """Version personnalisée de SimpleDocTemplate qui supprime les métadonnées temporelles"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def handle_documentBegin(self):
        super().handle_documentBegin()
        # Supprimer les métadonnées temporelles du document PDF
        self.canv._doc.info.producer = ''
        self.canv._doc.info.creator = ''
        self.canv._doc.info.creationDate = ''

def generate_qr_codes_pdf(articles):
    """
    Génère un PDF contenant tous les codes QR des articles avec leur nom
    Utilise une approche directe avec Canvas pour éviter tout horodatage
    """
    # Dimensions et marges
    page_width, page_height = A4
    margin = 1.5*cm
    
    # Espacement
    title_height = 2*cm
    subtitle_height = 1*cm
    row_height = 6*cm  # Hauteur de chaque ligne de codes QR
    column_width = (page_width - 2*margin) / 2  # Largeur de chaque colonne
    qr_size = 4*cm  # Taille des codes QR
    
    # Compter le nombre d'articles avec des codes QR
    articles_with_qr = [article for article in articles if article.qr_code and hasattr(article.qr_code, 'path')]
    
    # Calculer le nombre de pages nécessaires
    qr_per_page = 8  # 4 rangées de 2 colonnes
    total_pages = (len(articles_with_qr) + qr_per_page - 1) // qr_per_page if articles_with_qr else 1
    
    # Créer un buffer pour le PDF
    buffer = BytesIO()
    
    # Créer le canvas sans aucune métadonnée temporelle
    c = canvas.Canvas(buffer, pagesize=A4)
    
    # Supprimer explicitement toutes les métadonnées liées au temps
    c._doc.info.producer = ''
    c._doc.info.creator = ''
    c._doc.info.creationDate = ''
    c._doc.info.title = 'Catalogue des Codes QR'
    c._doc.info.author = ''
    c._doc.info.subject = ''
    c._doc.info.keywords = ''
    
    page_num = 1
    qr_index = 0
    
    while page_num <= total_pages:
        # Titre de la page
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(page_width/2, page_height - title_height, "Catalogue des Codes QR")
        
        # Sous-titre
        c.setFont("Helvetica", 12)
        c.drawCentredString(page_width/2, page_height - title_height - subtitle_height, 
                           "Liste de tous les articles avec leurs codes QR")
        
        if not articles_with_qr:
            # Message si aucun article avec code QR
            c.setFont("Helvetica", 12)
            c.drawCentredString(page_width/2, page_height/2, "Aucun article avec code QR trouvé.")
        else:
            # Dessiner les codes QR sur cette page
            for row in range(4):  # 4 rangées par page
                y_pos = page_height - title_height - subtitle_height - (row * row_height) - margin
                
                for col in range(2):  # 2 colonnes par rangée
                    if qr_index >= len(articles_with_qr):
                        break
                        
                    article = articles_with_qr[qr_index]
                    qr_path = article.qr_code.path
                    
                    # Position pour ce code QR
                    x_pos = margin + (col * column_width) + (column_width/2 - qr_size/2)
                    
                    # Dessiner le cadre
                    c.setStrokeColorRGB(0.7, 0.7, 0.7)  # Gris clair
                    c.rect(margin + (col * column_width), y_pos - row_height + margin,
                           column_width, row_height - margin, stroke=1, fill=0)
                    
                    # Dessiner le code QR
                    try:
                        c.drawImage(qr_path, x_pos, y_pos - qr_size - 0.5*cm, width=qr_size, height=qr_size)
                    except Exception as e:
                        # En cas d'erreur avec l'image
                        logger.error(f"Erreur avec l'image QR {qr_path}: {str(e)}")
                        c.setFont("Helvetica", 8)
                        c.drawCentredString(x_pos + qr_size/2, y_pos - qr_size/2, "Image non disponible")
                    
                    # Dessiner le nom de l'article
                    c.setFont("Helvetica-Bold", 10)
                    text_width = c.stringWidth(article.nom, "Helvetica-Bold", 10)
                    if text_width > column_width - 20:  # 10px de marge de chaque côté
                        # Tronquer le texte si trop long
                        ratio = (column_width - 20) / text_width
                        max_chars = int(len(article.nom) * ratio) - 3  # -3 pour les points de suspension
                        text = article.nom[:max_chars] + "..."
                    else:
                        text = article.nom
                    c.drawCentredString(margin + (col * column_width) + column_width/2, 
                                       y_pos - qr_size - 1.0*cm, text)
                    
                    # Dessiner le code de l'article
                    c.setFont("Helvetica-Oblique", 8)
                    c.drawCentredString(margin + (col * column_width) + column_width/2, 
                                       y_pos - qr_size - 1.5*cm, f"Code: {article.code}")
                    
                    qr_index += 1
                    
                    if qr_index >= len(articles_with_qr):
                        break
                
                if qr_index >= len(articles_with_qr):
                    break
        
        # Numéro de page en bas
        c.setFont("Helvetica", 8)
        c.drawRightString(page_width - margin, margin/2, f"Page {page_num} / {total_pages}")
        
        # Passer à la page suivante si nécessaire
        if page_num < total_pages:
            c.showPage()
            # Réappliquer les paramètres pour supprimer les métadonnées sur chaque page
            c._doc.info.producer = ''
            c._doc.info.creator = ''
            c._doc.info.creationDate = ''
        
        page_num += 1
    
    # Finaliser le document
    c.save()
    
    # Récupérer le contenu du PDF
    pdf = buffer.getvalue()
    buffer.close()
    
    return pdf

def update_stock_by_article_id(article_id, quantite, type_mouvement="VENTE", reference=None, utilisateur=None, details=None, is_sale=True):
    """
    Méthode efficace pour mettre à jour le stock d'un article par son ID
    
    Args:
        article_id (int): ID de l'article à mettre à jour
        quantite (int): Quantité à ajouter (positive) ou retirer (négative)
        type_mouvement (str): Type de mouvement (VENTE, ACHAT, AJUSTEMENT, etc.)
        reference (str): Numéro de référence (facture, commande, etc.)
        utilisateur (str): Nom de l'utilisateur effectuant l'opération
        details (dict): Détails supplémentaires pour l'historique
        is_sale (bool): Si True, la quantité sera soustraite du stock (vente), sinon ajoutée
    
    Returns:
        tuple: (success, message, mouvement) - succès de l'opération, message d'information, objet MouvementStock
    """
    from .models import Article, MouvementStock
    
    if not article_id or not isinstance(article_id, int) or article_id <= 0:
        return False, "ID d'article invalide", None
    
    try:
        # Conversion en entier pour être sûr
        quantite = int(quantite)
        if quantite <= 0:
            return False, "La quantité doit être positive", None
            
        # Ajuster le signe selon l'opération
        quantite_signed = -quantite if is_sale else quantite
        
        # Récupérer les détails de l'article pour l'historique
        try:
            article = Article.objects.select_for_update().get(id=article_id)
        except Article.DoesNotExist:
            return False, f"Article avec ID {article_id} non trouvé", None
        
        # Effectuer la mise à jour du stock dans une transaction atomique
        with transaction.atomic():
            # Enregistrer le stock avant modification
            stock_avant = article.quantite_stock
            
            # Calculer le nouveau stock (ne pas permettre un stock négatif)
            if is_sale:  # Vente = diminution du stock
                nouveau_stock = max(0, stock_avant - quantite)
                # Si le stock est insuffisant, annuler l'opération
                if nouveau_stock != stock_avant - quantite:  # Stock insuffisant
                    return False, f"Stock insuffisant pour l'article {article.nom} (ID:{article_id}). Stock disponible: {stock_avant}", None
            else:  # Achat ou ajout = augmentation du stock
                nouveau_stock = stock_avant + quantite
            
            # Mettre à jour le stock
            article.quantite_stock = nouveau_stock
            # Utiliser update_fields pour optimiser la requête SQL
            article.save(update_fields=['quantite_stock'])
            
            # Préparer les informations pour le mouvement de stock
            note_details = ""
            mouvement = MouvementStock.objects.create(
                article=article,
                type_mouvement=type_mouvement,
                quantite=quantite if not is_sale else -quantite,
                stock_avant=stock_avant,
                stock_apres=nouveau_stock,
                reference=reference or "",
                utilisateur=utilisateur or "API",
                note=f"{type_mouvement} - Article: {article.nom} ({article.code})"
            )
            
            # Journal pour le débogage
            action = "retirées de" if is_sale else "ajoutées au"
            logger.info(f"{quantite} unités {action} stock pour l'article {article.nom} (ID:{article_id}). Stock: {stock_avant} → {nouveau_stock}")
            
            return True, f"Stock mis à jour avec succès pour {article.nom} (ID:{article_id}). Nouveau stock: {nouveau_stock}", mouvement
            
    except Article.DoesNotExist:
        return False, f"Article non trouvé (ID:{article_id})", None
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du stock: {str(e)}")
        return False, f"Erreur lors de la mise à jour du stock: {str(e)}", None
