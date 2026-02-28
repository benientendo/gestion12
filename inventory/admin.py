from django.contrib import admin
from .models import Categorie, Article, Vente, LigneVente, MouvementStock, ArticleNegocie, RetourArticle, VenteRejetee, NotificationStock, VarianteArticle, TransactionMobileMoney, VenteCredit, StockCredit, ApprovisionnementCredit

@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description')
    search_fields = ('nom',)

class LigneVenteInline(admin.TabularInline):
    model = LigneVente
    extra = 1
    readonly_fields = ('total_ligne',)

class VarianteArticleInline(admin.TabularInline):
    """Inline pour gérer les variantes directement depuis l'article."""
    model = VarianteArticle
    extra = 1
    fields = ('code_barre', 'nom_variante', 'type_attribut', 'quantite_stock', 'est_actif')
    readonly_fields = ('date_creation',)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('code', 'nom', 'prix_vente', 'prix_achat', 'categorie', 'quantite_stock', 'nb_variantes', 'date_mise_a_jour')
    list_filter = ('categorie', 'date_creation')
    search_fields = ('code', 'nom')
    readonly_fields = ('date_creation', 'date_mise_a_jour', 'qr_code')
    inlines = [VarianteArticleInline]
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
    
    def nb_variantes(self, obj):
        return obj.variantes.filter(est_actif=True).count()
    nb_variantes.short_description = 'Variantes'


@admin.register(VarianteArticle)
class VarianteArticleAdmin(admin.ModelAdmin):
    """Admin standalone pour les variantes d'articles."""
    list_display = ('code_barre', 'nom_variante', 'article_parent', 'type_attribut', 'quantite_stock', 'prix_vente', 'est_actif')
    list_filter = ('type_attribut', 'est_actif', 'article_parent__categorie')
    search_fields = ('code_barre', 'nom_variante', 'article_parent__nom', 'article_parent__code')
    readonly_fields = ('date_creation', 'date_mise_a_jour', 'prix_vente', 'prix_achat', 'devise')
    autocomplete_fields = ['article_parent']
    
    fieldsets = (
        ('Article parent', {
            'fields': ('article_parent',)
        }),
        ('Identification variante', {
            'fields': ('code_barre', 'nom_variante', 'type_attribut')
        }),
        ('Prix (hérité de l\'article parent)', {
            'fields': ('prix_vente', 'prix_achat', 'devise'),
            'classes': ('collapse',)
        }),
        ('Stock', {
            'fields': ('quantite_stock', 'est_actif')
        }),
        ('Image', {
            'fields': ('image',),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('date_creation', 'date_mise_a_jour'),
            'classes': ('collapse',)
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

@admin.register(ArticleNegocie)
class ArticleNegocieAdmin(admin.ModelAdmin):
    list_display = ('boutique', 'terminal', 'code_article', 'montant_negocie', 'devise', 'date_operation', 'reference_vente')
    list_filter = ('boutique', 'devise', 'date_operation')
    search_fields = ('code_article', 'reference_vente', 'motif')

@admin.register(RetourArticle)
class RetourArticleAdmin(admin.ModelAdmin):
    list_display = ('boutique', 'terminal', 'code_article', 'montant_retourne', 'devise', 'date_operation', 'reference_vente')
    list_filter = ('boutique', 'devise', 'date_operation')
    search_fields = ('code_article', 'reference_vente', 'motif')


@admin.register(VenteRejetee)
class VenteRejeteeAdmin(admin.ModelAdmin):
    list_display = ('vente_uid', 'boutique', 'terminal', 'raison_rejet', 'date_tentative', 'traitee', 'action_requise')
    list_filter = ('raison_rejet', 'traitee', 'action_requise', 'boutique', 'date_tentative')
    search_fields = ('vente_uid', 'message_erreur', 'article_concerne_nom')
    readonly_fields = ('vente_uid', 'terminal', 'boutique', 'date_tentative', 'date_vente_originale', 
                       'donnees_vente', 'raison_rejet', 'message_erreur', 'article_concerne_id',
                       'article_concerne_nom', 'stock_demande', 'stock_disponible', 'created_at', 'updated_at')
    date_hierarchy = 'date_tentative'
    
    fieldsets = (
        ('Identification', {
            'fields': ('vente_uid', 'terminal', 'boutique')
        }),
        ('Dates', {
            'fields': ('date_tentative', 'date_vente_originale')
        }),
        ('Raison du rejet', {
            'fields': ('raison_rejet', 'message_erreur')
        }),
        ('Article concerné', {
            'fields': ('article_concerne_id', 'article_concerne_nom', 'stock_demande', 'stock_disponible'),
            'classes': ('collapse',)
        }),
        ('Données originales', {
            'fields': ('donnees_vente',),
            'classes': ('collapse',)
        }),
        ('Traitement', {
            'fields': ('action_requise', 'traitee', 'date_traitement', 'traite_par', 'notes_traitement')
        }),
    )
    
    actions = ['marquer_comme_traitee']
    
    @admin.action(description="Marquer les ventes sélectionnées comme traitées")
    def marquer_comme_traitee(self, request, queryset):
        from django.utils import timezone
        queryset.update(
            traitee=True, 
            date_traitement=timezone.now(),
            traite_par=request.user.username
        )
        self.message_user(request, f"{queryset.count()} vente(s) rejetée(s) marquée(s) comme traitée(s).")


@admin.register(NotificationStock)
class NotificationStockAdmin(admin.ModelAdmin):
    list_display = ('titre', 'client', 'boutique', 'type_notification', 'lue', 'date_creation', 'article')
    list_filter = ('type_notification', 'lue', 'date_creation', 'boutique')
    search_fields = ('titre', 'message', 'client__nom_terminal', 'article__nom', 'article__code')
    readonly_fields = ('date_creation', 'date_lecture', 'mouvement_stock', 'donnees_supplementaires')
    date_hierarchy = 'date_creation'
    
    fieldsets = (
        ('Destinataire', {
            'fields': ('client', 'boutique')
        }),
        ('Type et contenu', {
            'fields': ('type_notification', 'titre', 'message')
        }),
        ('Article concerné', {
            'fields': ('article', 'quantite_ajoutee', 'stock_actuel')
        }),
        ('Statut de lecture', {
            'fields': ('lue', 'date_lecture')
        }),
        ('Références', {
            'fields': ('mouvement_stock', 'donnees_supplementaires'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('date_creation',)
        }),
    )
    
    actions = ['marquer_comme_lue', 'marquer_comme_non_lue']
    
    @admin.action(description="Marquer les notifications sélectionnées comme lues")
    def marquer_comme_lue(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(lue=False).update(
            lue=True, 
            date_lecture=timezone.now()
        )
        self.message_user(request, f"{count} notification(s) marquée(s) comme lue(s).")
    
    @admin.action(description="Marquer les notifications sélectionnées comme non lues")
    def marquer_comme_non_lue(self, request, queryset):
        count = queryset.filter(lue=True).update(
            lue=False, 
            date_lecture=None
        )
        self.message_user(request, f"{count} notification(s) marquée(s) comme non lue(s).")


@admin.register(TransactionMobileMoney)
class TransactionMobileMoneyAdmin(admin.ModelAdmin):
    list_display = ('type_operation', 'operateur', 'numero_telephone_client', 'montant', 'commission', 'statut', 'date_transaction', 'boutique')
    list_filter = ('type_operation', 'operateur', 'statut', 'boutique', 'date_transaction')
    search_fields = ('numero_telephone_client', 'nom_client', 'reference_operateur', 'numero_destinataire')
    readonly_fields = ('date_transaction', 'montant_net')
    date_hierarchy = 'date_transaction'
    
    fieldsets = (
        ('Boutique', {
            'fields': ('boutique',)
        }),
        ('Opération', {
            'fields': ('type_operation', 'operateur')
        }),
        ('Client', {
            'fields': ('numero_telephone_client', 'nom_client', 'numero_destinataire')
        }),
        ('Montants', {
            'fields': ('montant', 'commission', 'montant_net')
        }),
        ('Statut', {
            'fields': ('statut', 'reference_operateur')
        }),
        ('Métadonnées', {
            'fields': ('effectue_par', 'notes', 'date_transaction', 'date_confirmation'),
            'classes': ('collapse',)
        }),
    )


@admin.register(VenteCredit)
class VenteCreditAdmin(admin.ModelAdmin):
    list_display = ('type_vente', 'operateur', 'unites_vendues', 'montant_recu', 'benefice', 'date_vente', 'boutique')
    list_filter = ('type_vente', 'operateur', 'boutique', 'date_vente')
    search_fields = ('numero_telephone_client', 'nom_client')
    readonly_fields = ('benefice', 'date_vente')
    date_hierarchy = 'date_vente'


@admin.register(StockCredit)
class StockCreditAdmin(admin.ModelAdmin):
    list_display = ('boutique', 'operateur', 'unites_disponibles', 'seuil_alerte', 'date_mise_a_jour')
    list_filter = ('operateur', 'boutique')
    readonly_fields = ('date_mise_a_jour',)


@admin.register(ApprovisionnementCredit)
class ApprovisionnementCreditAdmin(admin.ModelAdmin):
    list_display = ('operateur', 'unites', 'cout_achat', 'fournisseur', 'date_approvisionnement', 'boutique')
    list_filter = ('operateur', 'boutique', 'date_approvisionnement')
    search_fields = ('fournisseur', 'reference')
    readonly_fields = ('date_approvisionnement',)
    date_hierarchy = 'date_approvisionnement'

