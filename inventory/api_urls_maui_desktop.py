"""
URLs API pour le client MAUI Windows (Desktop)
================================================
"""

from django.urls import path
from . import api_views_maui_desktop

app_name = 'api_maui_desktop'

urlpatterns = [
    # Authentification
    path('auth/', api_views_maui_desktop.auth_commercant, name='auth_commercant'),

    # Boutiques
    path('boutiques/', api_views_maui_desktop.boutiques_commercant, name='boutiques_commercant'),

    # Catégories
    path('categories/', api_views_maui_desktop.categories_boutique, name='categories_boutique'),

    # Articles (sans facture)
    path('articles/', api_views_maui_desktop.recevoir_articles, name='recevoir_articles'),

    # Facture approvisionnement
    path('approvisionnement/', api_views_maui_desktop.recevoir_facture, name='recevoir_facture'),

    # Transfert entre boutiques (même commerçant)
    path('transferts/', api_views_maui_desktop.transfert_entre_boutiques, name='transfert_entre_boutiques'),
    path('transferts/historique/', api_views_maui_desktop.historique_transferts_maui,
         name='historique_transferts_maui'),
    path('transferts/<str:reference_lot>/bon/', api_views_maui_desktop.bon_transfert_maui,
         name='bon_transfert_maui'),
]
