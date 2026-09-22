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
]
