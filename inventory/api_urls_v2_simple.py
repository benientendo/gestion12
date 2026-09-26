"""
URLs API v2 Multi-Boutiques SIMPLIFIÉE (Sans Authentification)
==============================================================
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views_v2_simple
from .api_views_v2 import RapportCaisseListCreateView
from .api_views_notifications import NotificationStockViewSet

app_name = 'api_v2_simple'

router = DefaultRouter()
router.register(r'notifications', NotificationStockViewSet, basename='notification')

urlpatterns = [
    # ===== DIAGNOSTIC =====
    path('status/', api_views_v2_simple.api_status_v2_simple, name='api_status'),
    path('pos/status/', api_views_v2_simple.pos_status_simple, name='pos_status'),
    
    # ===== BOUTIQUES =====
    path('boutiques/', api_views_v2_simple.boutiques_list_simple, name='boutiques_list'),
    
    # ===== TERMINAUX =====
    path('terminal/token/', api_views_v2_simple.enregistrer_token_fcm, name='terminal_token'),
    path('terminal/debug/', api_views_v2_simple.debug_terminals, name='terminal_debug'),
    path('terminal/test-push/', api_views_v2_simple.test_push_fcm, name='terminal_test_push'),
    path('terminal/<str:numero_serie>/', api_views_v2_simple.terminal_info_simple, name='terminal_info'),
    
    # ===== ARTICLES =====
    path('articles/', api_views_v2_simple.articles_list_simple, name='articles_list'),
    path('articles/deleted/', api_views_v2_simple.articles_deleted_simple, name='articles_deleted'),
    path('articles/pending/', api_views_v2_simple.articles_pending_validation, name='articles_pending'),
    path('articles/valider/', api_views_v2_simple.valider_article, name='valider_article'),
    path('articles/refuser/', api_views_v2_simple.refuser_article, name='refuser_article'),
    path('articles/terminal/<str:numero_serie>/', api_views_v2_simple.articles_by_serial_simple, name='articles_by_serial'),
    path('articles/<int:article_id>/stock/', api_views_v2_simple.update_stock_simple, name='update_stock'),
    
    # ===== VARIANTES =====
    path('variantes/', api_views_v2_simple.variantes_list_simple, name='variantes_list'),
    
    # ===== CATÉGORIES =====
    path('categories/', api_views_v2_simple.categories_list_simple, name='categories_list'),
    
    # ===== VENTES =====
    path('ventes/', api_views_v2_simple.create_vente_simple, name='create_vente'),
    path('ventes/sync', api_views_v2_simple.sync_ventes_simple, name='sync_ventes_no_slash'),  # Sans slash pour MAUI
    path('ventes/sync/', api_views_v2_simple.sync_ventes_simple, name='sync_ventes'),
    path('ventes/historique/', api_views_v2_simple.historique_ventes_simple, name='historique_ventes'),
    path('ventes/reconciliation/', api_views_v2_simple.reconcilier_ventes, name='reconcilier_ventes'),
    path('ventes/annuler', api_views_v2_simple.annuler_vente_simple, name='annuler_vente_no_slash'),  # Sans slash pour MAUI
    path('ventes/annuler/', api_views_v2_simple.annuler_vente_simple, name='annuler_vente'),
    path('ventes/notifier-rejet', api_views_v2_simple.notifier_rejet_vente_simple, name='notifier_rejet_no_slash'),
    path('ventes/notifier-rejet/', api_views_v2_simple.notifier_rejet_vente_simple, name='notifier_rejet'),
    
    # ===== ANALYSE IA MOUVEMENTS =====
    path('analyse/mouvements', api_views_v2_simple.analyse_mouvements_simple, name='analyse_mouvements_no_slash'),
    path('analyse/mouvements/', api_views_v2_simple.analyse_mouvements_simple, name='analyse_mouvements'),
    path('analyse/regulariser', api_views_v2_simple.regulariser_alerte_stock_simple, name='regulariser_alerte_no_slash'),
    path('analyse/regulariser/', api_views_v2_simple.regulariser_alerte_stock_simple, name='regulariser_alerte'),

    # ===== RAPPORTS DE CAISSE =====
    path('rapports-caisse/', RapportCaisseListCreateView.as_view(), name='rapports_caisse_simple'),
    
    # ===== STATISTIQUES =====
    path('statistiques/', api_views_v2_simple.statistiques_boutique_simple, name='statistiques_boutique'),
    
    # ===== 💰 NÉGOCIATIONS =====
    path('negociations/', api_views_v2_simple.rapport_negociations_simple, name='rapport_negociations'),
    
    path('articles-negocies', api_views_v2_simple.creer_article_negocie_simple, name='articles_negocies_create_no_slash'),
    path('articles-negocies/', api_views_v2_simple.creer_article_negocie_simple, name='articles_negocies_create'),
    path('articles-negocies/<int:trace_id>', api_views_v2_simple.modifier_article_negocie_simple, name='articles_negocies_update_no_slash'),
    path('articles-negocies/<int:trace_id>/', api_views_v2_simple.modifier_article_negocie_simple, name='articles_negocies_update'),
    path('retours-articles', api_views_v2_simple.creer_retour_article_simple, name='retours_articles_create_no_slash'),
    path('retours-articles/', api_views_v2_simple.creer_retour_article_simple, name='retours_articles_create'),
    path('articles-negocies/historique/', api_views_v2_simple.historique_articles_negocies_simple, name='articles_negocies_history'),
    path('retours-articles/historique/', api_views_v2_simple.historique_retours_articles_simple, name='retours_articles_history'),
    
    # ===== NOTIFICATIONS =====
    path('', include(router.urls)),

    # ===== JOURNAL VALEUR STOCK =====
    path('journal-valeur-stock/', api_views_v2_simple.journal_valeur_stock_simple, name='journal_valeur_stock'),
    path('journal-valeur-stock', api_views_v2_simple.journal_valeur_stock_simple, name='journal_valeur_stock_no_slash'),
    
    # ===== RÉCONCILIATION STOCKS CLIENT =====
    path('reconciliation/stocks/', api_views_v2_simple.reconcilier_stocks_client, name='reconcilier_stocks_client'),
    path('reconciliation/stocks', api_views_v2_simple.reconcilier_stocks_client, name='reconcilier_stocks_client_no_slash'),
    path('reconciliation/stocks/check/', api_views_v2_simple.verifier_divergences_stocks, name='verifier_divergences_stocks'),
    path('reconciliation/stocks/check', api_views_v2_simple.verifier_divergences_stocks, name='verifier_divergences_stocks_no_slash'),

    # ===== BANNIÈRES PUBLICITAIRES =====
    path('banners/', api_views_v2_simple.banners_list_simple, name='banners_list'),
    path('banners', api_views_v2_simple.banners_list_simple, name='banners_list_no_slash'),

    # ===== MESSAGES COMMERCANT =====
    path('merchant-messages/', api_views_v2_simple.merchant_messages_list, name='merchant_messages_list'),
    path('merchant-messages/<int:message_id>/read/', api_views_v2_simple.merchant_messages_mark_read, name='merchant_messages_mark_read'),
]
