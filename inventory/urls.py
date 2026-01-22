from django.urls import path
from . import views
from . import admin_views
from . import views_commercant

app_name = 'inventory'

urlpatterns = [
    # Pages principales
    path('', views.home, name='home'),
    path('ajouter/', views.ajouter_article, name='ajouter_article'),
    
    # Gestion des catégories
    path('categories/', views.liste_categories, name='categories'),
    path('categories/ajouter/', views.ajouter_categorie, name='ajouter_categorie'),
    path('categories/editer/<int:categorie_id>/', views.editer_categorie, name='editer_categorie'),
    path('categories/modifier/<int:categorie_id>/', views.modifier_categorie, name='modifier_categorie'),
    path('categories/supprimer/<int:categorie_id>/', views.supprimer_categorie, name='supprimer_categorie'),
    
    # Gestion des articles
    path('articles/', views.liste_articles, name='articles'),
    path('articles/supprimer/<int:article_id>/', views.supprimer_article, name='supprimer_article'),
    path('articles/qr-codes/pdf/', views.generate_qr_pdf, name='generer_qr_codes_pdf'),
    
    # Gestion des ventes
    path('ventes/', views.liste_ventes, name='ventes'),
    path('ventes/historique/', views.historique_ventes, name='historique_ventes'),
    path('ventes/historique/supprimer-selection/', views.supprimer_ventes_selectionnees, name='supprimer_ventes_selectionnees'),
    
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
    
    # ===== VUES SUPER ADMINISTRATEUR =====
    path('superadmin/dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('superadmin/commercants/', admin_views.gestion_commercants, name='admin_gestion_commercants'),
    path('superadmin/commercants/ajouter/', admin_views.ajouter_commercant, name='admin_ajouter_commercant'),
    path('superadmin/commercants/<int:commercant_id>/', admin_views.details_commercant, name='admin_details_commercant'),
    path('superadmin/commercants/<int:commercant_id>/modifier/', admin_views.modifier_commercant, name='admin_modifier_commercant'),
    path('superadmin/commercants/<int:commercant_id>/supprimer/', admin_views.supprimer_commercant, name='admin_supprimer_commercant'),
    path('superadmin/commercants/<int:commercant_id>/reset-password/', admin_views.reset_commercant_password, name='admin_reset_commercant_password'),
    path('superadmin/commercants/<int:commercant_id>/toggle-status/', admin_views.toggle_commercant_status, name='admin_toggle_commercant_status'),
    path('superadmin/boutiques/', admin_views.gestion_boutiques_admin, name='admin_gestion_boutiques'),
    path('superadmin/boutiques/<int:boutique_id>/toggle-pos/', admin_views.toggle_boutique_pos_admin, name='admin_toggle_boutique_pos'),
    path('superadmin/diagnostic-api/', admin_views.diagnostic_api, name='admin_diagnostic_api'),
    
    # ===== INTERFACE COMMERÇANT =====
    path('commercant/login/', views_commercant.login_commercant, name='login_commercant'),
    path('commercant/logout/', views_commercant.logout_commercant, name='logout_commercant'),
    path('commercant/dashboard/', views_commercant.dashboard_commercant, name='commercant_dashboard'),
    path('commercant/taux-dollar/', views_commercant.modifier_taux_dollar, name='modifier_taux_dollar'),
    path('commercant/boutiques/', views_commercant.liste_boutiques, name='commercant_boutiques'),
    path('commercant/boutiques/creer/', views_commercant.creer_boutique, name='commercant_creer_boutique'),
    path('commercant/boutiques/<int:boutique_id>/', views_commercant.detail_boutique, name='commercant_detail_boutique'),
    path('commercant/boutiques/<int:boutique_id>/modifier/', views_commercant.modifier_boutique, name='modifier_boutique'),
    path('commercant/boutiques/<int:boutique_id>/supprimer/', views_commercant.supprimer_boutique, name='supprimer_boutique'),
    path('commercant/boutiques/<int:boutique_id>/toggle-pos/', views_commercant.toggle_boutique_pos, name='toggle_boutique_pos'),
    path('commercant/boutiques/<int:boutique_id>/entrer/', views_commercant.entrer_boutique, name='entrer_boutique'),
    path('commercant/boutiques/<int:boutique_id>/articles/', views_commercant.articles_boutique, name='commercant_articles_boutique'),
    path('commercant/boutiques/<int:boutique_id>/terminaux/', views_commercant.terminaux_boutique, name='commercant_terminaux_boutique'),
    path('commercant/boutiques/<int:boutique_id>/terminaux/creer/', views_commercant.creer_terminal, name='commercant_creer_terminal'),
    path('commercant/boutiques/<int:boutique_id>/terminaux/<int:terminal_id>/modifier/', views_commercant.modifier_terminal, name='modifier_terminal'),
    path('commercant/boutiques/<int:boutique_id>/terminaux/<int:terminal_id>/toggle/', views_commercant.toggle_terminal, name='toggle_terminal'),
    path('commercant/boutiques/<int:boutique_id>/terminaux/<int:terminal_id>/supprimer/', views_commercant.supprimer_terminal, name='supprimer_terminal'),
    path('commercant/boutiques/<int:boutique_id>/client-maui/ajouter/', views_commercant.ajouter_client_maui_boutique, name='ajouter_client_maui_boutique'),
    path('commercant/boutiques/<int:boutique_id>/articles/ajouter/', views_commercant.ajouter_article_boutique, name='ajouter_article_boutique'),
    path('commercant/boutiques/<int:boutique_id>/articles/<int:article_id>/modifier/', views_commercant.modifier_article_boutique, name='modifier_article_boutique'),
    path('commercant/boutiques/<int:boutique_id>/articles/<int:article_id>/supprimer/', views_commercant.supprimer_article_boutique, name='supprimer_article_boutique'),
    path('commercant/boutiques/<int:boutique_id>/articles/<int:article_id>/ajuster-stock/', views_commercant.ajuster_stock_article, name='ajuster_stock_article'),
    path('commercant/boutiques/<int:boutique_id>/articles/<int:article_id>/modifier-prix/', views_commercant.modifier_prix_article, name='modifier_prix_article'),
    path('commercant/boutiques/<int:boutique_id>/categories/', views_commercant.categories_boutique, name='commercant_categories_boutique'),
    path('commercant/boutiques/<int:boutique_id>/ventes/', views_commercant.ventes_boutique, name='commercant_ventes_boutique'),
    path('commercant/boutiques/<int:boutique_id>/mouvements-stock/', views_commercant.historique_mouvements_stock, name='historique_mouvements_stock'),
    path('commercant/boutiques/<int:boutique_id>/ventes-refusees/', views_commercant.ventes_refusees_boutique, name='commercant_ventes_refusees_boutique'),
    path('commercant/boutiques/<int:boutique_id>/rapports-caisse/', views_commercant.rapports_caisse_boutique, name='commercant_rapports_caisse_boutique'),
    path('commercant/boutiques/<int:boutique_id>/rapports-caisse/articles-negocies/', views_commercant.articles_negocies_boutique, name='commercant_articles_negocies_boutique'),
    path('commercant/boutiques/<int:boutique_id>/rapports-caisse/retours-articles/', views_commercant.retours_articles_boutique, name='commercant_retours_articles_boutique'),
    path('commercant/boutiques/<int:boutique_id>/rapports-caisse/articles-negocies/<int:negociation_id>/appliquer/', views_commercant.appliquer_article_negocie, name='appliquer_article_negocie'),
    path('commercant/boutiques/<int:boutique_id>/rapports-caisse/<int:rapport_id>/appliquer-depense/', views_commercant.appliquer_depense_rapport_caisse, name='appliquer_depense_rapport_caisse'),
    path('commercant/boutiques/<int:boutique_id>/qr-codes-pdf/', views_commercant.generer_pdf_qr_codes, name='generer_pdf_qr_codes'),
    path('commercant/boutiques/<int:boutique_id>/rapport-ca-quotidien/', views_commercant.rapport_ca_quotidien, name='rapport_ca_quotidien'),
    path('commercant/boutiques/<int:boutique_id>/rapport-ca-mensuel/', views_commercant.rapport_ca_mensuel, name='rapport_ca_mensuel'),
    path('commercant/boutiques/<int:boutique_id>/export-ca-pdf/', views_commercant.exporter_ca_quotidien_pdf, name='exporter_ca_quotidien_pdf'),
    path('commercant/boutiques/<int:boutique_id>/export-ca-mensuel-pdf/', views_commercant.exporter_ca_mensuel_pdf, name='exporter_ca_mensuel_pdf'),
    path('commercant/api/boutique/<int:boutique_id>/stats/', views_commercant.api_stats_boutique, name='commercant_api_stats_boutique'),
    path('commercant/api/vente/<int:vente_id>/details/', views_commercant.api_vente_details, name='api_vente_details'),
    
    # Gestion des dépôts
    path('commercant/depots/', views_commercant.liste_depots, name='commercant_liste_depots'),
    path('commercant/depots/<int:depot_id>/', views_commercant.detail_depot, name='detail_depot'),
    path('commercant/depots/<int:depot_id>/transfert/creer/', views_commercant.creer_transfert_stock, name='creer_transfert_stock'),
    path('commercant/depots/<int:depot_id>/approvisionner/', views_commercant.approvisionner_depot, name='approvisionner_depot'),
    path('commercant/depots/<int:depot_id>/importer-articles/', views_commercant.importer_articles_vers_depot, name='importer_articles_vers_depot'),
    path('commercant/depots/<int:depot_id>/importer-excel/', views_commercant.importer_excel_depot, name='importer_excel_depot'),
    path('commercant/depots/<int:depot_id>/articles/<int:article_id>/', views_commercant.detail_article_depot, name='detail_article_depot'),
    path('commercant/depots/<int:depot_id>/articles/<int:article_id>/modifier/', views_commercant.modifier_article_depot, name='modifier_article_depot'),
    path('commercant/depots/<int:depot_id>/articles/<int:article_id>/supprimer/', views_commercant.supprimer_article_depot, name='supprimer_article_depot'),
    path('commercant/depots/<int:depot_id>/transferts/historique/', views_commercant.historique_transferts, name='historique_transferts'),
    path('commercant/depots/<int:depot_id>/transfert-multiple/', views_commercant.transfert_multiple, name='transfert_multiple'),
    path('commercant/depots/<int:depot_id>/valider-transferts-multiples/', views_commercant.valider_transferts_multiples, name='valider_transferts_multiples'),
    path('commercant/transferts/<int:transfert_id>/', views_commercant.detail_transfert, name='detail_transfert'),
    path('commercant/transferts/<int:transfert_id>/valider/', views_commercant.valider_transfert, name='valider_transfert'),
    path('commercant/transferts/<int:transfert_id>/annuler/', views_commercant.annuler_transfert, name='annuler_transfert'),
]
