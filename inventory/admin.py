from django.contrib import admin
from django import forms
from django.utils import timezone
from .models import Categorie, Article, Vente, LigneVente, MouvementStock, ArticleNegocie, RetourArticle, VenteRejetee, NotificationStock, VarianteArticle, TransactionMobileMoney, VenteCredit, StockCredit, ApprovisionnementCredit, DemandeResetPdv, Client


class ArticleAdminForm(forms.ModelForm):
    """Formulaire admin avec traçabilité du stock.

    ⚠️ Toute modification de quantite_stock crée un MouvementStock 'AJUSTEMENT'
    qui alimente automatiquement le JournalValeurStock (via signals).
    """

    class Meta:
        model = Article
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if instance and instance.pk:
            self._ancienne_quantite = instance.quantite_stock
            self.fields['quantite_stock'].help_text = (
                f"⚠️ Stock actuel : {instance.quantite_stock}. Toute modification sera "
                f"tracée dans le journal de valeur de stock (MouvementStock AJUSTEMENT)."
            )
        else:
            self._ancienne_quantite = 0
            self.fields['quantite_stock'].help_text = (
                "⚠️ Toute modification sera tracée dans le journal de valeur de stock."
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.pk:
            try:
                ancien = Article.objects.get(pk=instance.pk)
                ancienne_qte = ancien.quantite_stock
            except Article.DoesNotExist:
                ancienne_qte = 0
        else:
            ancienne_qte = 0

        nouveau = instance.quantite_stock or 0
        difference = nouveau - ancienne_qte

        if commit:
            instance.save()

        # 🔍 Traçabilité : créer le mouvement si le stock a changé
        if difference != 0:
            try:
                MouvementStock.objects.create(
                    article=instance,
                    type_mouvement='AJUSTEMENT',
                    quantite=difference,
                    stock_avant=ancienne_qte,
                    stock_apres=nouveau,
                    reference_document=f"ADMIN-{instance.code or instance.pk}",
                    utilisateur="Admin Django",
                    commentaire=f"Ajustement manuel admin: {ancienne_qte} → {nouveau} ({difference:+d})"
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"[Admin] Erreur traçabilité stock {instance.pk}: {e}")
        return instance

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
    # ⚠️ Conformité stock: les variantes sont des identifiants (code-barres) uniquement.
    # Le stock vit sur le PARENT (Article.quantite_stock). 'quantite_stock' est donc
    # affiché en lecture seule pour éviter toute divergence avec MAUI et les ventes.
    fields = ('code_barre', 'nom_variante', 'type_attribut', 'est_actif')
    readonly_fields = ('date_creation', 'quantite_stock')


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    form = ArticleAdminForm  # 🔍 Traçabilité du stock dans le journal
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

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change:
            try:
                from inventory.websocket_utils import notify_article_updated, notify_sync_required
                if obj.boutique:
                    notify_article_updated(obj.boutique.id, obj)
                    notify_sync_required(obj.boutique.id, "Article modifié depuis l'admin")
            except Exception:
                pass


@admin.register(VarianteArticle)
class VarianteArticleAdmin(admin.ModelAdmin):
    """Admin standalone pour les variantes d'articles."""
    list_display = ('code_barre', 'nom_variante', 'article_parent', 'type_attribut', 'quantite_stock', 'prix_vente', 'est_actif')
    list_filter = ('type_attribut', 'est_actif', 'article_parent__categorie')
    search_fields = ('code_barre', 'nom_variante', 'article_parent__nom', 'article_parent__code')
    readonly_fields = ('date_creation', 'date_mise_a_jour', 'prix_vente', 'prix_achat', 'devise', 'quantite_stock')
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
        ('Stock (lecture seule — le stock est géré sur l\'article parent)', {
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


@admin.register(DemandeResetPdv)
class DemandeResetPdvAdmin(admin.ModelAdmin):
    """Admin de suivi des demandes de réinitialisation PDV (validation via page dédiée)."""
    list_display = ('id', 'terminal', 'boutique', 'demandeur', 'statut', 'date_demande', 'traite_par', 'date_traitement')
    list_filter = ('statut', 'boutique')
    search_fields = ('terminal__nom_terminal', 'terminal__numero_serie', 'boutique__nom')
    readonly_fields = ('date_demande',)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Admin des terminaux MAUI avec réinitialisation directe du PDV."""
    list_display = ('nom_terminal', 'numero_serie', 'boutique', 'est_actif', 'derniere_connexion', 'reset_bouton')
    search_fields = ('nom_terminal', 'numero_serie', 'boutique__nom')
    list_filter = ('est_actif', 'boutique')
    actions = ['reinitialiser_pdv', 'reinitialiser_pdv_serveur']

    @admin.action(description="🔄 Réinitialiser les PDV sélectionnés (exécution immédiate admin)")
    def reinitialiser_pdv(self, request, queryset):
        """Réinitialise directement les terminaux cochés (admin = autorité de validation)."""
        from .views_reset_pdv import executer_reset_boutique

        total_articles = 0
        nb_terminal = 0
        for terminal in queryset:
            nb, nb_tot, resultat = executer_reset_boutique(terminal, request.user)
            total_articles += nb
            nb_terminal += 1
            # Historique dans la même table que les demandes (traçabilité)
            DemandeResetPdv.objects.create(
                terminal=terminal,
                boutique=terminal.boutique,
                demandeur=request.user,
                motif="Réinitialisation directe (admin Django)",
                statut='VALIDEE',
                traite_par=request.user,
                date_traitement=timezone.now(),
                resultat=resultat,
            )
        self.message_user(
            request,
            f"✔ {nb_terminal} point(s) de vente réinitialisé(s) : {total_articles} "
            "article(s) remis en attente de re-validation par les terminaux MAUI.",
        )

    @admin.action(description="⚠️ Réinitialisation SERVEUR COMPLÈTE des PDV sélectionnés (supprime articles, ventes…)")
    def reinitialiser_pdv_serveur(self, request, queryset):
        """Attention : supprime TOUTES les données serveur des boutiques des terminaux sélectionnés."""
        from .views_reset_pdv import executer_reset_serveur_boutique

        nb_terminal = 0
        for terminal in queryset:
            if not terminal.boutique:
                continue
            compte_rendu, resultat = executer_reset_serveur_boutique(terminal.boutique, request.user)
            nb_terminal += 1
            DemandeResetPdv.objects.create(
                terminal=terminal,
                boutique=terminal.boutique,
                demandeur=request.user,
                motif="Réinitialisation serveur complète (admin Django)",
                type_reset='SERVEUR',
                statut='VALIDEE',
                traite_par=request.user,
                date_traitement=timezone.now(),
                resultat=resultat,
            )
        self.message_user(
            request,
            f"⚠️ {nb_terminal} point(s) de vente remis à zéro (articles, ventes, mouvements supprimés).",
            level='warning',
        )

    # 🔍 Boutons visibles par ligne : réinitialisation MAUI ou SERVEUR COMPLÈTE
    @admin.display(description='Reset PDV')
    def reset_bouton(self, obj):
        from django.utils.html import format_html
        url_maui = f"/admin-demandes-reset/terminal/{obj.id}/direct/"
        url_serveur = f"/admin-demandes-reset/terminal/{obj.id}/direct-serveur/"
        return format_html(
            '<a class="button" style="background:#b02b2b; color:#fff; padding:3px 8px; '
            'border-radius:3px; text-decoration:none; white-space:nowrap; margin-right:4px" '
            'href="{url_maui}">↺ MAUI</a>'
            '<a class="button" style="background:#7a0000; color:#fff; padding:3px 8px; '
            'border-radius:3px; text-decoration:none; white-space:nowrap" '
            'href="{url_serveur}">⚠️ Serveur</a>',
            url_maui=url_maui,
            url_serveur=url_serveur,
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

