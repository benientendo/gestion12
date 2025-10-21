from django.urls import path
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
    path('articles/editer/<int:article_id>/', views.editer_article, name='editer_article'),
    path('articles/rechercher/', views.rechercher_article, name='rechercher_article'),
    path('articles/qr-codes/pdf/', views.generer_qr_codes_pdf, name='generer_qr_codes_pdf'),
    
    # Gestion des ventes
    path('ventes/', views.liste_ventes, name='ventes'),
    path('ventes/nouvelle/', views.nouvelle_vente, name='nouvelle_vente'),
    path('ventes/<int:vente_id>/', views.details_vente, name='details_vente'),
    
    # Authentification
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('change-password/', views.change_password, name='change_password'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Gestion des clients MAUI (simplifié)
    path('clients-maui/', views.gestion_clients_maui, name='gestion_clients_maui'),
    path('clients-maui/ajouter/', views.ajouter_client_maui, name='ajouter_client_maui'),
]
