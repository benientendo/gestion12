"""
Context processors pour injecter des données globales dans tous les templates.
"""
from django.db.models import F
from .models import Article, Boutique


def alertes_stock(request):
    """
    Injecte les alertes de stock bas dans le contexte de tous les templates.
    Fonctionne pour les commerçants connectés.
    """
    alertes = {
        'alertes_stock_count': 0,
        'alertes_stock_articles': [],
        'alertes_stock_rupture': 0,
    }
    
    if not request.user.is_authenticated:
        return alertes
    
    # Vérifier si c'est un commerçant
    try:
        commercant = request.user.profil_commercant
        
        # Récupérer toutes les boutiques du commerçant (hors dépôts)
        boutiques = Boutique.objects.filter(
            commercant=commercant, 
            est_active=True,
            est_depot=False
        )
        
        # Articles en stock bas (quantite_stock <= alerte_stock_bas de la boutique)
        articles_stock_bas = Article.objects.filter(
            boutique__in=boutiques,
            est_actif=True,
            quantite_stock__lte=F('boutique__alerte_stock_bas')
        ).select_related('boutique', 'categorie').order_by('quantite_stock')[:10]
        
        # Compter les ruptures (stock = 0)
        ruptures = Article.objects.filter(
            boutique__in=boutiques,
            est_actif=True,
            quantite_stock__lte=0
        ).count()
        
        # Total alertes
        total_alertes = Article.objects.filter(
            boutique__in=boutiques,
            est_actif=True,
            quantite_stock__lte=F('boutique__alerte_stock_bas')
        ).count()
        
        alertes['alertes_stock_count'] = total_alertes
        alertes['alertes_stock_articles'] = articles_stock_bas
        alertes['alertes_stock_rupture'] = ruptures
        
    except Exception:
        # Pas un commerçant ou erreur - retourner les valeurs par défaut
        pass
    
    return alertes
