# api_urls_multi_boutiques.py
# URLs pour l'API multi-boutiques

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views_multi_boutiques_new import (
    ArticleMultiBoutiquesViewSet,
    CategorieMultiBoutiquesViewSet, 
    VenteMultiBoutiquesViewSet,
    authentifier_client_maui_multi_boutiques,
    get_boutique_info,
    update_stock_multi_boutiques
)

# Création du router pour les ViewSets multi-boutiques
router = DefaultRouter()
router.register(r'articles', ArticleMultiBoutiquesViewSet, basename='articles-multi-boutiques')
router.register(r'categories', CategorieMultiBoutiquesViewSet, basename='categories-multi-boutiques')
router.register(r'ventes', VenteMultiBoutiquesViewSet, basename='ventes-multi-boutiques')

urlpatterns = [
    # ViewSets avec filtrage par boutique
    path('', include(router.urls)),
    
    # Authentification MAUI multi-boutiques
    path('auth/maui/', authentifier_client_maui_multi_boutiques, name='auth_maui_multi_boutiques'),
    
    # Informations boutique
    path('boutique/<int:boutique_id>/info/', get_boutique_info, name='boutique_info'),
    
    # Gestion stock multi-boutiques
    path('stock/update/', update_stock_multi_boutiques, name='update_stock_multi_boutiques'),
]
