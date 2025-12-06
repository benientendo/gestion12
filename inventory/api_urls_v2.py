"""
URLs API v2 Multi-Boutiques
===========================

Routes pour l'API v2 avec isolation des données par boutique.
Toutes les routes nécessitent une authentification et un boutique_id valide.
"""

from django.urls import path
from . import api_views_v2

app_name = 'api_v2'

urlpatterns = [
    # ===== AUTHENTIFICATION =====
    path('auth/maui/', api_views_v2.maui_auth_v2, name='maui_auth'),
    path('auth/validate/', api_views_v2.validate_session_v2, name='validate_session'),
    
    # ===== ARTICLES =====
    path('articles/', api_views_v2.articles_list_v2, name='articles_list'),
    path('articles/<int:article_id>/stock/', api_views_v2.update_stock_v2, name='update_stock'),
    
    # ===== CATÉGORIES =====
    path('categories/', api_views_v2.categories_list_v2, name='categories_list'),
    
    # ===== VENTES =====
    path('ventes/', api_views_v2.create_vente_v2, name='create_vente'),
    path('rapports-caisse/', api_views_v2.RapportCaisseListCreateView.as_view(), name='rapports_caisse'),
    
    # ===== BOUTIQUE =====
    path('boutique/<int:boutique_id>/info/', api_views_v2.boutique_info_v2, name='boutique_info'),
    
    # ===== DIAGNOSTIC =====
    path('status/', api_views_v2.api_status_v2, name='api_status'),
]
