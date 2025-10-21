#!/usr/bin/env python
"""
Script pour remplacer urls.py avec les vues qui existent réellement
"""

WORKING_URLS_CONTENT = '''from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Pages principales
    path('', views.home, name='home'),
    path('ajouter/', views.ajouter_article, name='ajouter_article'),
    
    # Gestion des catégories
    path('categories/', views.liste_categories, name='categories'),
    path('categories/editer/<int:categorie_id>/', views.editer_categorie, name='editer_categorie'),
    path('categories/supprimer/<int:categorie_id>/', views.supprimer_categorie, name='supprimer_categorie'),
    
    # Gestion des articles
    path('articles/', views.liste_articles, name='articles'),
    path('articles/supprimer/<int:article_id>/', views.supprimer_article, name='supprimer_article'),
    path('articles/qr-codes/pdf/', views.generate_qr_pdf, name='generer_qr_codes_pdf'),
    
    # Gestion des ventes
    path('ventes/', views.liste_ventes, name='ventes'),
    path('ventes/historique/', views.historique_ventes, name='historique_ventes'),
    
    # Authentification
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('change-password/', views.change_password, name='change_password'),
    
    # Gestion des utilisateurs (super admin)
    path('utilisateurs/', views.gestion_utilisateurs, name='gestion_utilisateurs'),
    path('utilisateurs/creer/', views.creer_utilisateur, name='creer_utilisateur'),
    path('utilisateurs/<int:user_id>/editer/', views.editer_utilisateur, name='editer_utilisateur'),
    path('utilisateurs/<int:user_id>/supprimer/', views.supprimer_utilisateur, name='supprimer_utilisateur'),
    
    # Gestion des clients MAUI
    path('clients-maui/', views.gestion_clients_maui, name='gestion_clients_maui'),
    path('clients-maui/dashboard/', views.dashboard_clients_maui, name='dashboard_clients_maui'),
    path('clients-maui/ajouter/', views.ajouter_client_maui, name='ajouter_client_maui'),
    path('clients-maui/<int:client_id>/', views.details_client_maui, name='details_client_maui'),
]
'''

def replace_urls():
    """Remplacer le fichier urls.py"""
    
    try:
        with open('inventory/urls.py', 'w', encoding='utf-8') as f:
            f.write(WORKING_URLS_CONTENT)
        
        print("✅ Fichier urls.py remplacé avec les vues existantes!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

if __name__ == "__main__":
    success = replace_urls()
    exit(0 if success else 1)
