from django.contrib import admin
from .models import Categorie, Article, Vente, LigneVente, MouvementStock

@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description')
    search_fields = ('nom',)

class LigneVenteInline(admin.TabularInline):
    model = LigneVente
    extra = 1
    readonly_fields = ('total_ligne',)

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('code', 'nom', 'prix_vente', 'prix_achat', 'categorie', 'quantite_stock', 'date_mise_a_jour')
    list_filter = ('categorie', 'date_creation')
    search_fields = ('code', 'nom')
    readonly_fields = ('date_creation', 'date_mise_a_jour', 'qr_code')
    fieldsets = (
        ('Informations de base', {
            'fields': ('code', 'nom', 'description', 'categorie')
        }),
        ('Prix', {
            'fields': ('prix_achat', 'prix_vente')
        }),
        ('Stock', {
            'fields': ('quantite_stock',)
        }),
        ('QR Code', {
            'fields': ('qr_code',)
        }),
        ('Dates', {
            'fields': ('date_creation', 'date_mise_a_jour')
        }),
    )

@admin.register(Vente)
class VenteAdmin(admin.ModelAdmin):
    list_display = ('numero_facture', 'date_vente', 'montant_total', 'paye', 'mode_paiement')
    list_filter = ('date_vente', 'paye', 'mode_paiement')
    search_fields = ('numero_facture',)
    inlines = [LigneVenteInline]

@admin.register(LigneVente)
class LigneVenteAdmin(admin.ModelAdmin):
    list_display = ('vente', 'article', 'quantite', 'prix_unitaire', 'total_ligne')
    list_filter = ('vente', 'article')
    search_fields = ('vente__numero_facture', 'article__nom')
    readonly_fields = ('total_ligne',)

@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = ('article', 'type_mouvement', 'quantite', 'date_mouvement')
    list_filter = ('type_mouvement', 'date_mouvement')
    search_fields = ('article__nom', 'article__code', 'commentaire')
    date_hierarchy = 'date_mouvement'
    readonly_fields = ('date_mouvement',)
    fieldsets = (
        ('Informations de base', {
            'fields': ('article', 'type_mouvement', 'quantite')
        }),
        ('Commentaire', {
            'fields': ('commentaire',)
        }),
        ('Date', {
            'fields': ('date_mouvement',)
        }),
    )
