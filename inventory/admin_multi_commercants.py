# admin_multi_commercants.py
# Interface d'administration pour l'architecture multi-commerçants

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum
from .models_multi_commercants import Commercant, Boutique, TerminalMaui, SessionTerminalMaui

# ===== ADMINISTRATION COMMERÇANTS =====

class BoutiqueInline(admin.TabularInline):
    """Inline pour afficher les boutiques d'un commerçant"""
    model = Boutique
    extra = 0
    readonly_fields = ['code_boutique', 'cle_api', 'date_creation']
    fields = ['nom', 'type_commerce', 'adresse', 'est_active', 'code_boutique', 'date_creation']

@admin.register(Commercant)
class CommercantAdmin(admin.ModelAdmin):
    list_display = ['nom_entreprise', 'nom_responsable', 'email', 'type_abonnement', 
                   'nombre_boutiques_display', 'est_actif', 'date_creation']
    list_filter = ['type_abonnement', 'est_actif', 'date_creation']
    search_fields = ['nom_entreprise', 'nom_responsable', 'email']
    readonly_fields = ['date_creation', 'date_mise_a_jour']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('nom_entreprise', 'nom_responsable', 'email', 'telephone', 'adresse')
        }),
        ('Compte utilisateur', {
            'fields': ('utilisateur',)
        }),
        ('Abonnement et limites', {
            'fields': ('type_abonnement', 'limite_boutiques', 'limite_articles_par_boutique')
        }),
        ('Statut', {
            'fields': ('est_actif',)
        }),
        ('Métadonnées', {
            'fields': ('date_creation', 'date_mise_a_jour', 'notes_admin'),
            'classes': ('collapse',)
        })
    )
    
    inlines = [BoutiqueInline]
    
    def nombre_boutiques_display(self, obj):
        count = obj.boutiques.count()
        if count > 0:
            url = reverse('admin:inventory_boutique_changelist') + f'?commercant__id={obj.id}'
            return format_html('<a href="{}">{} boutique(s)</a>', url, count)
        return '0 boutique'
    nombre_boutiques_display.short_description = 'Boutiques'
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('boutiques')


# ===== ADMINISTRATION BOUTIQUES =====

class TerminalMauiInline(admin.TabularInline):
    """Inline pour afficher les terminaux d'une boutique"""
    model = TerminalMaui
    extra = 0
    readonly_fields = ['cle_api', 'derniere_connexion', 'date_creation']
    fields = ['nom_terminal', 'numero_serie', 'nom_utilisateur', 'est_actif', 'derniere_connexion']

@admin.register(Boutique)
class BoutiqueAdmin(admin.ModelAdmin):
    list_display = ['nom', 'commercant', 'type_commerce', 'code_boutique', 
                   'nombre_articles_display', 'nombre_terminaux_display', 'est_active', 'date_creation']
    list_filter = ['type_commerce', 'est_active', 'commercant', 'date_creation']
    search_fields = ['nom', 'code_boutique', 'commercant__nom_entreprise']
    readonly_fields = ['code_boutique', 'cle_api', 'date_creation', 'date_mise_a_jour']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('nom', 'description', 'commercant', 'type_commerce')
        }),
        ('Localisation', {
            'fields': ('adresse', 'ville', 'quartier', 'telephone')
        }),
        ('Configuration technique', {
            'fields': ('code_boutique', 'cle_api', 'devise', 'fuseau_horaire')
        }),
        ('Paramètres', {
            'fields': ('alerte_stock_bas', 'est_active')
        }),
        ('Métadonnées', {
            'fields': ('date_creation', 'date_mise_a_jour'),
            'classes': ('collapse',)
        })
    )
    
    inlines = [TerminalMauiInline]
    
    def nombre_articles_display(self, obj):
        count = obj.articles.count()
        if count > 0:
            url = reverse('admin:inventory_article_changelist') + f'?boutique__id={obj.id}'
            return format_html('<a href="{}">{} article(s)</a>', url, count)
        return '0 article'
    nombre_articles_display.short_description = 'Articles'
    
    def nombre_terminaux_display(self, obj):
        count = obj.terminaux.count()
        if count > 0:
            url = reverse('admin:inventory_terminalmui_changelist') + f'?boutique__id={obj.id}'
            return format_html('<a href="{}">{} terminal(aux)</a>', url, count)
        return '0 terminal'
    nombre_terminaux_display.short_description = 'Terminaux'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('commercant').prefetch_related('articles', 'terminaux')


# ===== ADMINISTRATION TERMINAUX MAUI =====

class SessionTerminalMauiInline(admin.TabularInline):
    """Inline pour afficher les sessions d'un terminal"""
    model = SessionTerminalMaui
    extra = 0
    readonly_fields = ['token_session', 'date_debut', 'date_fin', 'adresse_ip']
    fields = ['token_session', 'date_debut', 'date_fin', 'est_active', 'adresse_ip', 'version_app']
    ordering = ['-date_debut']

@admin.register(TerminalMaui)
class TerminalMauiAdmin(admin.ModelAdmin):
    list_display = ['nom_terminal', 'boutique', 'numero_serie', 'nom_utilisateur', 
                   'est_actif', 'derniere_connexion', 'date_creation']
    list_filter = ['est_actif', 'boutique__commercant', 'boutique', 'date_creation']
    search_fields = ['nom_terminal', 'numero_serie', 'nom_utilisateur', 'boutique__nom']
    readonly_fields = ['cle_api', 'derniere_connexion', 'derniere_activite', 'date_creation', 'date_mise_a_jour']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('nom_terminal', 'description', 'boutique', 'nom_utilisateur')
        }),
        ('Authentification', {
            'fields': ('numero_serie', 'cle_api')
        }),
        ('Statut et connexion', {
            'fields': ('est_actif', 'derniere_connexion', 'derniere_activite', 'derniere_adresse_ip')
        }),
        ('Informations techniques', {
            'fields': ('version_app_maui',)
        }),
        ('Métadonnées', {
            'fields': ('date_creation', 'date_mise_a_jour'),
            'classes': ('collapse',)
        })
    )
    
    inlines = [SessionTerminalMauiInline]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('boutique__commercant')


# ===== ADMINISTRATION SESSIONS =====

@admin.register(SessionTerminalMaui)
class SessionTerminalMauiAdmin(admin.ModelAdmin):
    list_display = ['terminal', 'boutique_display', 'date_debut', 'date_fin', 
                   'est_active', 'adresse_ip', 'version_app']
    list_filter = ['est_active', 'terminal__boutique__commercant', 'terminal__boutique', 'date_debut']
    search_fields = ['terminal__nom_terminal', 'terminal__boutique__nom', 'adresse_ip', 'token_session']
    readonly_fields = ['token_session', 'date_debut', 'date_fin']
    
    fieldsets = (
        ('Session', {
            'fields': ('terminal', 'token_session', 'date_debut', 'date_fin', 'est_active')
        }),
        ('Informations de connexion', {
            'fields': ('adresse_ip', 'user_agent', 'version_app')
        })
    )
    
    def boutique_display(self, obj):
        return obj.terminal.boutique.nom
    boutique_display.short_description = 'Boutique'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('terminal__boutique__commercant')


# ===== PERSONNALISATION DE L'ADMIN UTILISATEUR =====

class CommercantInline(admin.StackedInline):
    """Inline pour afficher le profil commerçant d'un utilisateur"""
    model = Commercant
    can_delete = False
    verbose_name_plural = 'Profil Commerçant'
    fields = ['nom_entreprise', 'nom_responsable', 'email', 'telephone', 'type_abonnement', 'est_actif']

# Désenregistrer l'admin User par défaut et le réenregistrer avec notre inline
admin.site.unregister(User)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = (CommercantInline,)
    
    def get_inline_instances(self, request, obj=None):
        # Afficher l'inline seulement si l'utilisateur a un profil commerçant
        if obj and hasattr(obj, 'profil_commercant'):
            return super().get_inline_instances(request, obj)
        return []


# ===== CONFIGURATION DE L'ADMIN SITE =====

admin.site.site_header = "Administration Multi-Commerçants"
admin.site.site_title = "Gestion Magazin"
admin.site.index_title = "Tableau de bord administrateur"
