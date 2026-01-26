from django.urls import path
from . import api_bilan

app_name = 'api_bilan'

urlpatterns = [
    # Bilans API
    path('bilans/', api_bilan.bilans_api, name='bilans'),
    path('bilans/<int:bilan_id>/', api_bilan.bilan_detail_api, name='bilan_detail'),
    path('bilans/<int:bilan_id>/valider/', api_bilan.valider_bilan_api, name='valider_bilan'),
    
    # Indicateurs API
    path('indicateurs/', api_bilan.indicateurs_api, name='indicateurs'),
    path('indicateurs/rafraichir/', api_bilan.rafraichir_indicateurs_api, name='rafraichir_indicateurs'),
    
    # Statistiques temps réel
    path('statistiques-temps-reel/', api_bilan.statistiques_temps_reel_api, name='statistiques_temps_reel'),
    path('ventes-par-jour/', api_bilan.ventes_par_jour_api, name='ventes_par_jour'),
    path('top-articles/', api_bilan.top_articles_api, name='top_articles'),
    path('performance-categories/', api_bilan.performance_categories_api, name='performance_categories'),
]
