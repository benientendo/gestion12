"""
URLs API v2 Multi-Boutiques SIMPLIFIÉE (Sans Authentification)
==============================================================
"""

from django.urls import path
from . import api_views_v2_simple
from .api_views_v2 import RapportCaisseListCreateView

app_name = 'api_v2_simple'

urlpatterns = [
    # ===== DIAGNOSTIC =====
    path('status/', api_views_v2_simple.api_status_v2_simple, name='api_status'),
    path('pos/status/', api_views_v2_simple.pos_status_simple, name='pos_status'),
    
    # ===== BOUTIQUES =====
    path('boutiques/', api_views_v2_simple.boutiques_list_simple, name='boutiques_list'),
    
    # ===== TERMINAUX =====
    path('terminal/<str:numero_serie>/', api_views_v2_simple.terminal_info_simple, name='terminal_info'),
    
    # ===== ARTICLES =====
    path('articles/', api_views_v2_simple.articles_list_simple, name='articles_list'),
    path('articles/terminal/<str:numero_serie>/', api_views_v2_simple.articles_by_serial_simple, name='articles_by_serial'),
    path('articles/<int:article_id>/stock/', api_views_v2_simple.update_stock_simple, name='update_stock'),
    
    # ===== CATÉGORIES =====
    path('categories/', api_views_v2_simple.categories_list_simple, name='categories_list'),
    
    # ===== VENTES =====
    path('ventes/', api_views_v2_simple.create_vente_simple, name='create_vente'),
    path('ventes/sync', api_views_v2_simple.sync_ventes_simple, name='sync_ventes_no_slash'),  # Sans slash pour MAUI
    path('ventes/sync/', api_views_v2_simple.sync_ventes_simple, name='sync_ventes'),
    path('ventes/historique/', api_views_v2_simple.historique_ventes_simple, name='historique_ventes'),
    
    # ===== RAPPORTS DE CAISSE =====
    path('rapports-caisse/', RapportCaisseListCreateView.as_view(), name='rapports_caisse_simple'),
    
    # ===== STATISTIQUES =====
    path('statistiques/', api_views_v2_simple.statistiques_boutique_simple, name='statistiques_boutique'),
    
    path('articles-negocies', api_views_v2_simple.creer_article_negocie_simple, name='articles_negocies_create_no_slash'),
    path('articles-negocies/', api_views_v2_simple.creer_article_negocie_simple, name='articles_negocies_create'),
    path('retours-articles', api_views_v2_simple.creer_retour_article_simple, name='retours_articles_create_no_slash'),
    path('retours-articles/', api_views_v2_simple.creer_retour_article_simple, name='retours_articles_create'),
    path('articles-negocies/historique/', api_views_v2_simple.historique_articles_negocies_simple, name='articles_negocies_history'),
    path('retours-articles/historique/', api_views_v2_simple.historique_retours_articles_simple, name='retours_articles_history'),
]
