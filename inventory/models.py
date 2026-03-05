from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone
import re
import qrcode
from io import BytesIO
from django.core.files import File
import json
import logging
import uuid
import random
import string

# Importer les modèles de bilan
from .models_bilan import BilanGeneral, IndicateurPerformance

# Create your models here.

class Client(models.Model):
    """Modèle représentant un client MAUI (terminal de vente)."""
    
    # Lien avec le compte propriétaire
    compte_proprietaire = models.ForeignKey(User, on_delete=models.CASCADE, related_name='clients_maui',
                                           help_text="Compte utilisateur propriétaire de ce client MAUI")
    
    # Lien avec la boutique spécifique
    boutique = models.ForeignKey('Boutique', on_delete=models.CASCADE, related_name='clients', 
                                null=True, blank=True, help_text="Boutique à laquelle ce terminal est associé")
    
    # Informations du terminal/responsable
    nom_terminal = models.CharField(max_length=100, help_text="Nom du terminal ou responsable MAUI")
    description = models.TextField(blank=True, help_text="Description du terminal ou notes")
    
    # Système d'authentification par numéro de série
    numero_serie = models.CharField(max_length=50, unique=True, help_text="Numéro de série unique pour l'authentification MAUI")
    cle_api = models.CharField(max_length=100, unique=True, default=uuid.uuid4, help_text="Clé API générée automatiquement")
    
    # Statut et informations de connexion
    est_actif = models.BooleanField(default=True, help_text="Le client peut-il se connecter?")
    derniere_connexion = models.DateTimeField(null=True, blank=True)
    derniere_activite = models.DateTimeField(null=True, blank=True)
    version_app_maui = models.CharField(max_length=20, blank=True, help_text="Version de l'application MAUI")
    derniere_adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, help_text="Notes internes")
    
    def __str__(self):
        return f"{self.nom_terminal} ({self.numero_serie})"
    
    class Meta:
        verbose_name = "Client MAUI"
        verbose_name_plural = "Clients MAUI"
        ordering = ['-derniere_connexion', 'nom_terminal']


class SessionClientMaui(models.Model):
    """Modèle pour suivre les sessions actives des clients MAUI."""
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='sessions')
    token_session = models.CharField(max_length=100, unique=True)
    adresse_ip = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    version_app = models.CharField(max_length=50, blank=True)
    date_debut = models.DateTimeField(auto_now_add=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    est_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Session {self.client.nom_terminal} - {self.date_debut}"
    
    class Meta:
        verbose_name = "Session Client MAUI"
        verbose_name_plural = "Sessions Clients MAUI"
        ordering = ['-date_debut']


class Categorie(models.Model):
    """Catégories d'articles."""
    
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    boutique = models.ForeignKey('Boutique', on_delete=models.CASCADE, related_name='categories', null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nom
    
    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ['nom']


class Article(models.Model):
    """Articles de vente."""
    
    DEVISE_CHOICES = [
        ('CDF', 'Franc Congolais'),
        ('USD', 'Dollar US'),
    ]
    
    code = models.CharField(max_length=50)
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    # Devise principale de l'article (détermine la devise des prix)
    devise = models.CharField(max_length=3, choices=DEVISE_CHOICES, default='CDF', help_text="Devise des prix de cet article")
    # Les prix sont dans la devise sélectionnée
    prix_vente = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0)], help_text="Prix de vente dans la devise de l'article")
    prix_achat = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Prix d'achat dans la devise de l'article")
    # Champs de conversion (optionnels, pour affichage dans l'autre devise)
    prix_vente_usd = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)], help_text="Prix de vente converti en USD (si devise=CDF)")
    prix_achat_usd = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, help_text="Prix d'achat converti en USD (si devise=CDF)")
    categorie = models.ForeignKey(Categorie, on_delete=models.SET_NULL, null=True, related_name='articles')
    boutique = models.ForeignKey('Boutique', on_delete=models.CASCADE, related_name='articles', null=True, blank=True)
    quantite_stock = models.IntegerField(default=0)
    date_expiration = models.DateField(null=True, blank=True, help_text="Date d'expiration du produit")
    est_actif = models.BooleanField(default=True, help_text="L'article est-il actif?")
    est_valide_client = models.BooleanField(default=False, help_text="L'article a été validé par le client MAUI (quantité vérifiée)")
    quantite_envoyee = models.IntegerField(default=0, help_text="Quantité envoyée depuis Django en attente de validation")
    date_envoi = models.DateTimeField(null=True, blank=True, help_text="Date d'envoi pour validation client")
    date_validation = models.DateTimeField(null=True, blank=True, help_text="Date de validation par le client MAUI")
    date_suppression = models.DateTimeField(null=True, blank=True, help_text="Date de désactivation/suppression pour sync MAUI")
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True)
    image = models.ImageField(upload_to='articles/', blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nom} ({self.code})"

    def save(self, *args, **kwargs):
        logger = logging.getLogger(__name__)
        
        # Tracer la date de suppression quand un article est désactivé
        if self.pk:
            try:
                old_instance = Article.objects.get(pk=self.pk)
                if old_instance.est_actif and not self.est_actif:
                    self.date_suppression = timezone.now()
                    logger.info(f"📍 Article {self.code} désactivé - date_suppression mise à jour")
                elif not old_instance.est_actif and self.est_actif:
                    self.date_suppression = None
                    logger.info(f"📍 Article {self.code} réactivé - date_suppression effacée")
            except Article.DoesNotExist:
                pass
        
        # Determine if this save call is specifically for updating the qr_code field
        updating_qr_code_field_only = False
        update_fields = kwargs.get('update_fields')
        if update_fields and isinstance(update_fields, (list, tuple)) and 'qr_code' in update_fields and len(update_fields) == 1:
            updating_qr_code_field_only = True

        # Call the original save method
        super(Article, self).save(*args, **kwargs)

        # Generate and save QR code only if needed
        if self.pk and not self.qr_code and not updating_qr_code_field_only:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr_data = {
                'id': self.id,
                'code': self.code,
                'nom': self.nom,
                'prix': str(self.prix_vente),
                'categorie': self.categorie.nom if self.categorie else ''
            }
            qr.add_data(json.dumps(qr_data))
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            filename = f'qr_code_{self.code}.png'
            self.qr_code.save(filename, File(buffer), save=False)
            super(Article, self).save(update_fields=['qr_code'])
    
    @property
    def a_variantes(self):
        """Retourne True si l'article a des variantes ACTIVES"""
        return self.variantes.filter(est_actif=True).exists()
    
    @property
    def stock_total(self):
        """
        Retourne le stock total:
        - Si variantes: somme des stocks des variantes
        - Sinon: quantite_stock de l'article
        """
        if self.a_variantes:
            return self.variantes.filter(est_actif=True).aggregate(
                total=models.Sum('quantite_stock')
            )['total'] or 0
        return self.quantite_stock
    
    @property
    def nb_variantes(self):
        """Retourne le nombre de variantes actives"""
        return self.variantes.filter(est_actif=True).count()
    
    @property
    def est_expire(self):
        """Retourne True si l'article est expiré"""
        if self.date_expiration:
            from datetime import date
            return self.date_expiration < date.today()
        return False
    
    @property
    def expire_bientot(self):
        """Retourne True si l'article expire dans les 30 prochains jours"""
        if self.date_expiration and not self.est_expire:
            from datetime import date, timedelta
            return self.date_expiration <= date.today() + timedelta(days=30)
        return False
    
    class Meta:
        verbose_name = "Article"
        verbose_name_plural = "Articles"
        ordering = ['nom']
        unique_together = [['code', 'boutique']]
        indexes = [
            models.Index(fields=['boutique', 'est_actif'], name='idx_article_boutique_actif'),
            models.Index(fields=['boutique', 'est_actif', 'nom'], name='idx_article_boutique_nom'),
            models.Index(fields=['quantite_stock'], name='idx_article_stock'),
            models.Index(fields=['date_expiration'], name='idx_article_expiration'),
        ]


class VarianteArticle(models.Model):
    """
    Variantes d'un article avec code-barres unique.
    Exemple: Déodorant avec variantes Rouge, Bleu, Vert - même prix, différents codes-barres.
    """
    
    article_parent = models.ForeignKey(
        Article, 
        on_delete=models.CASCADE, 
        related_name='variantes',
        help_text="Article parent dont cette variante hérite le prix"
    )
    
    # Code-barres unique pour cette variante
    code_barre = models.CharField(
        max_length=100, 
        help_text="Code-barres unique de cette variante"
    )
    
    # Nom de la variante (ex: "Rouge", "500ml", "Vanille")
    nom_variante = models.CharField(
        max_length=100,
        help_text="Nom de la variante (couleur, taille, parfum, etc.)"
    )
    
    # Type d'attribut pour faciliter le regroupement
    TYPE_ATTRIBUT_CHOICES = [
        ('COULEUR', 'Couleur'),
        ('TAILLE', 'Taille'),
        ('PARFUM', 'Parfum'),
        ('POIDS', 'Poids'),
        ('VOLUME', 'Volume'),
        ('MODELE', 'Modèle'),
        ('AUTRE', 'Autre'),
    ]
    type_attribut = models.CharField(
        max_length=20, 
        choices=TYPE_ATTRIBUT_CHOICES, 
        default='AUTRE',
        help_text="Type d'attribut de cette variante"
    )
    
    # Stock spécifique à cette variante
    quantite_stock = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Stock disponible pour cette variante"
    )
    
    # Statut
    est_actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    
    # Image spécifique à la variante (optionnel)
    image = models.ImageField(upload_to='variantes/', blank=True, null=True)
    
    @property
    def prix_vente(self):
        """Le prix est hérité de l'article parent."""
        return self.article_parent.prix_vente
    
    @property
    def prix_achat(self):
        """Le prix d'achat est hérité de l'article parent."""
        return self.article_parent.prix_achat
    
    @property
    def devise(self):
        """La devise est héritée de l'article parent."""
        return self.article_parent.devise
    
    @property
    def boutique(self):
        """La boutique est héritée de l'article parent."""
        return self.article_parent.boutique
    
    @property
    def categorie(self):
        """La catégorie est héritée de l'article parent."""
        return self.article_parent.categorie
    
    @property
    def nom_complet(self):
        """Retourne le nom complet: Article - Variante"""
        return f"{self.article_parent.nom} - {self.nom_variante}"
    
    def __str__(self):
        return f"{self.article_parent.nom} - {self.nom_variante} ({self.code_barre})"
    
    class Meta:
        verbose_name = "Variante d'article"
        verbose_name_plural = "Variantes d'articles"
        ordering = ['article_parent__nom', 'nom_variante']
        # Code-barres unique par article parent seulement (pas globalement)
        # L'unicité par boutique est gérée dans les vues
        unique_together = [['code_barre', 'article_parent']]


class Vente(models.Model):
    """Ventes."""
    
    numero_facture = models.CharField(max_length=100, unique=True)
    date_vente = models.DateTimeField(default=timezone.now)
    montant_total = models.DecimalField(max_digits=12, decimal_places=2)
    # Montant en dollars USD
    montant_total_usd = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Montant total en USD")
    devise = models.CharField(max_length=3, choices=[('CDF', 'Franc Congolais'), ('USD', 'Dollar US')], default='CDF', help_text="Devise utilisée pour cette vente")
    paye = models.BooleanField(default=False)
    mode_paiement = models.CharField(max_length=50, choices=[
        ('CASH', 'Espèces'),
        ('CARD', 'Carte bancaire'),
        ('MOBILE', 'Paiement mobile')
    ])
    
    # ⭐ ISOLATION: Lien direct avec la boutique
    boutique = models.ForeignKey('Boutique', on_delete=models.CASCADE, related_name='ventes',
                                null=True, blank=True, help_text="Boutique à laquelle cette vente appartient")
    
    # Association avec le client MAUI qui a effectué la vente
    client_maui = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventes')
    adresse_ip_client = models.GenericIPAddressField(null=True, blank=True, help_text="Adresse IP du client MAUI")
    version_app_maui = models.CharField(max_length=50, blank=True, help_text="Version de l'app MAUI utilisée")
    
    # ⭐ ANNULATION DE VENTE
    est_annulee = models.BooleanField(default=False, help_text="La vente a-t-elle été annulée?")
    date_annulation = models.DateTimeField(null=True, blank=True, help_text="Date et heure de l'annulation")
    motif_annulation = models.TextField(blank=True, help_text="Raison de l'annulation")
    annulee_par = models.CharField(max_length=100, blank=True, help_text="Terminal ou utilisateur ayant annulé")
    
    def __str__(self):
        return f"Vente {self.numero_facture} - {self.date_vente.strftime('%d/%m/%Y')}"
    
    class Meta:
        verbose_name = "Vente"
        verbose_name_plural = "Ventes"
        ordering = ['-date_vente']
        # 🚀 Index pour optimiser les requêtes fréquentes
        indexes = [
            models.Index(fields=['date_vente'], name='idx_vente_date'),
            models.Index(fields=['client_maui', 'date_vente'], name='idx_vente_client_date'),
            models.Index(fields=['paye', 'est_annulee'], name='idx_vente_statut'),
            models.Index(fields=['boutique', 'date_vente'], name='idx_vente_boutique_date'),
            models.Index(fields=['devise'], name='idx_vente_devise'),
        ]


class LigneVente(models.Model):
    vente = models.ForeignKey(Vente, related_name='lignes', on_delete=models.CASCADE)
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    # Optionnel: variante spécifique vendue (si l'article a des variantes)
    variante = models.ForeignKey(
        VarianteArticle, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='lignes_vente',
        help_text="Variante spécifique vendue (optionnel)"
    )
    quantite = models.PositiveIntegerField()
    prix_unitaire = models.DecimalField(max_digits=15, decimal_places=2)
    # Prix original avant négociation (pour traçabilité)
    prix_original = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, 
                                         help_text="Prix original avant négociation")
    # Indique si le prix a été négocié
    est_negocie = models.BooleanField(default=False, help_text="Prix négocié avec le client")
    # Motif de la réduction pour justification
    motif_reduction = models.CharField(max_length=255, blank=True, default='', 
                                        help_text="Motif/justification de la réduction accordée")
    # Prix en dollars USD
    prix_unitaire_usd = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, help_text="Prix unitaire en USD")
    devise = models.CharField(max_length=3, choices=[('CDF', 'Franc Congolais'), ('USD', 'Dollar US')], default='CDF')
    
    @property
    def total_ligne(self):
        return self.quantite * self.prix_unitaire
    
    @property
    def total_ligne_usd(self):
        if self.prix_unitaire_usd:
            return self.quantite * self.prix_unitaire_usd
        return None
    
    @property
    def reduction_pourcentage(self):
        """Pourcentage de réduction si prix négocié"""
        if self.prix_original and self.prix_original > 0:
            return round((1 - float(self.prix_unitaire) / float(self.prix_original)) * 100, 1)
        return 0
    
    @property
    def montant_reduction(self):
        """Montant de la réduction par unité"""
        if self.prix_original:
            return (self.prix_original - self.prix_unitaire) * self.quantite
        return 0
    
    def __str__(self):
        return f"{self.article.nom} x{self.quantite}"
    
    class Meta:
        verbose_name = "Ligne de vente"
        verbose_name_plural = "Lignes de vente"
        # 🚀 Index pour optimiser les requêtes de négociation
        indexes = [
            models.Index(fields=['est_negocie'], name='idx_ligne_negocie'),
            models.Index(fields=['vente', 'est_negocie'], name='idx_ligne_vente_nego'),
        ]


class ScanRecent(models.Model):
    """Scans récents d'articles."""
    
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    date_scan = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date_scan']


class MouvementStock(models.Model):
    """Mouvements de stock avec traçabilité complète."""
    
    TYPES = [
        ('ENTREE', 'Entrée de stock'),
        ('SORTIE', 'Sortie de stock'),
        ('AJUSTEMENT', 'Ajustement'),
        ('VENTE', 'Vente'),
        ('RETOUR', 'Retour client')
    ]
    
    # Champs existants
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='mouvements')
    type_mouvement = models.CharField(max_length=20, choices=TYPES)
    quantite = models.IntegerField(help_text="Négatif pour sortie, positif pour entrée")
    date_mouvement = models.DateTimeField(auto_now_add=True)
    commentaire = models.TextField(blank=True)
    
    # ⭐ NOUVEAUX CHAMPS pour meilleure traçabilité
    stock_avant = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Stock avant le mouvement"
    )
    stock_apres = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Stock après le mouvement"
    )
    reference_document = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="Numéro de facture, bon de livraison, etc."
    )
    utilisateur = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="Nom d'utilisateur ou device_serial"
    )
    
    def __str__(self):
        return f"{self.type_mouvement} - {self.article.nom} ({self.quantite})"
    
    class Meta:
        ordering = ['-date_mouvement']
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        indexes = [
            models.Index(fields=['article', 'date_mouvement'], name='mouvement_article_date_idx'),
            models.Index(fields=['type_mouvement'], name='mouvement_type_idx'),
            models.Index(fields=['reference_document'], name='mouvement_ref_idx'),
        ]


# ===== MODÈLES MULTI-COMMERÇANTS =====

class Commercant(models.Model):
    """
    Modèle représentant un commerçant (entreprise ou personne) 
    qui peut posséder plusieurs boutiques.
    """
    
    # Informations de base
    nom_entreprise = models.CharField(max_length=200, help_text="Nom de l'entreprise ou du commerçant")
    nom_responsable = models.CharField(max_length=100, help_text="Nom du responsable principal")
    email = models.EmailField(unique=True, help_text="Email de contact principal")
    telephone = models.CharField(max_length=20, blank=True)
    adresse = models.TextField(blank=True, help_text="Adresse principale de l'entreprise")
    
    # Informations légales
    numero_registre_commerce = models.CharField(max_length=50, blank=True, help_text="Numéro de registre de commerce")
    numero_fiscal = models.CharField(max_length=50, blank=True, help_text="Numéro d'identification fiscale")
    
    # Association avec le compte utilisateur Django
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profil_commercant',
                                help_text="Compte utilisateur Django associé")
    
    # Paramètres et statut
    est_actif = models.BooleanField(default=True, help_text="Le commerçant peut-il accéder au système?")
    taux_dollar = models.DecimalField(max_digits=10, decimal_places=2, default=2800, 
                                      help_text="Taux de change: 1 USD = X CDF (appliqué à tous les points de vente)")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    
    # Paramètres de l'abonnement (pour futur système de facturation)
    type_abonnement = models.CharField(max_length=50, choices=[
        ('GRATUIT', 'Gratuit (limité)'),
        ('STANDARD', 'Standard'),
        ('PREMIUM', 'Premium'),
        ('ENTREPRISE', 'Entreprise')
    ], default='GRATUIT')
    
    max_boutiques = models.IntegerField(default=1, help_text="Nombre maximum de boutiques autorisées")
    limite_articles_par_boutique = models.IntegerField(default=100, help_text="Nombre maximum d'articles par boutique")
    
    # Métadonnées
    notes_admin = models.TextField(blank=True, help_text="Notes internes pour l'administration")
    
    def __str__(self):
        return f"{self.nom_entreprise} ({self.nom_responsable})"
    
    def nombre_boutiques(self):
        """Retourne le nombre de boutiques de ce commerçant (hors dépôts)"""
        return self.boutiques.filter(est_depot=False).count()
    
    def peut_creer_boutique(self):
        """Vérifie si le commerçant peut créer une nouvelle boutique (hors dépôts)"""
        return self.nombre_boutiques() < self.max_boutiques
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Créer un dépôt par défaut pour les nouveaux commerçants
        if is_new:
            Boutique.objects.create(
                nom=f"Dépôt Central - {self.nom_entreprise}",
                description=f"Dépôt central de stockage pour {self.nom_entreprise}",
                commercant=self,
                type_commerce='DEPOT',
                est_depot=True,
                est_active=True,
                ville=self.adresse.split(',')[0] if self.adresse else '',
            )
    
    class Meta:
        verbose_name = "Commerçant"
        verbose_name_plural = "Commerçants"
        ordering = ['nom_entreprise']


class Boutique(models.Model):
    """
    Modèle représentant une boutique/établissement appartenant à un commerçant.
    Chaque boutique a ses propres articles, ventes et terminaux MAUI.
    """
    
    # Informations de base
    nom = models.CharField(max_length=200, help_text="Nom de la boutique")
    description = models.TextField(blank=True, help_text="Description de la boutique")
    
    # Association avec le commerçant propriétaire
    commercant = models.ForeignKey(Commercant, on_delete=models.CASCADE, related_name='boutiques',
                                 help_text="Commerçant propriétaire de cette boutique")
    
    # Type et catégorie de commerce
    TYPE_COMMERCE_CHOICES = [
        ('GENERAL', 'Commerce Général'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('DEPOT', 'Dépôt central'),
        ('PHARMACIE', 'Pharmacie'),
        ('ALIMENTATION', 'Alimentation générale'),
        ('SUPERMARCHE', 'Supermarché'),
        ('BOUTIQUE', 'Boutique générale'),
        ('KIOSQUE', 'Kiosque'),
        ('BAR', 'Bar/Café'),
        ('RESTAURANT', 'Restaurant / Fast-food'),
        ('HABILLEMENT', 'Habillement / Friperie'),
        ('COIFFURE_BEAUTE', 'Salon de coiffure / Beauté'),
        ('ELECTRONIQUE', 'Appareils électroniques / Accessoires'),
        ('TELEPHONIE_MOBILE', 'Téléphonie / Mobile Money'),
        ('QUINCAILLERIE', 'Quincaillerie'),
        ('SERVICES_BUREAU', 'Services bureautiques / Cybercafé'),
        ('AUTRE', 'Autre')
    ]
    type_commerce = models.CharField(max_length=50, choices=TYPE_COMMERCE_CHOICES, default='GENERAL')
    
    # Informations de localisation
    adresse = models.TextField(blank=True, help_text="Adresse de la boutique")
    ville = models.CharField(max_length=100, blank=True)
    code_postal = models.CharField(max_length=10, blank=True)
    quartier = models.CharField(max_length=100, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True, help_text="Email de contact de la boutique")
    
    # Identifiants uniques pour l'API
    code_boutique = models.CharField(max_length=50, unique=True, 
                                   help_text="Code unique pour identifier la boutique dans l'API")
    cle_api_boutique = models.CharField(max_length=100, unique=True, default=uuid.uuid4,
                                      help_text="Clé API unique pour cette boutique")
    
    # Statut et paramètres
    est_active = models.BooleanField(default=True, help_text="La boutique est-elle active?")
    est_depot = models.BooleanField(default=False, help_text="Est-ce un dépôt central de stockage?")
    pos_autorise = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    
    # Paramètres de fonctionnement
    devise = models.CharField(max_length=10, default='CDF')
    alerte_stock_bas = models.IntegerField(default=5, help_text="Seuil d'alerte pour stock bas")
    taux_dollar = models.DecimalField(max_digits=10, decimal_places=2, default=2800, 
                                      help_text="Taux de change USD vers CDF pour conversion des factures")
    derniere_lecture_rapports_caisse = models.DateTimeField(null=True, blank=True)
    derniere_lecture_articles_negocies = models.DateTimeField(null=True, blank=True)
    derniere_lecture_retours_articles = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # Générer un code boutique unique si pas défini
        if not self.code_boutique:
            # Format: COMM_BOUTIQUE_001
            commercant_prefix = self.commercant.nom_entreprise[:4].upper().replace(' ', '')
            numero = self.commercant.boutiques.count() + 1
            self.code_boutique = f"{commercant_prefix}_BOUT_{numero:03d}"
        
        # Générer une clé API si pas définie
        if not self.cle_api_boutique:
            self.cle_api_boutique = str(uuid.uuid4())
            
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.nom} ({self.commercant.nom_entreprise})"
    
    def nombre_articles(self):
        """Retourne le nombre d'articles de cette boutique"""
        return self.articles.count()
    
    def nombre_ventes_aujourd_hui(self):
        """Retourne le nombre de ventes d'aujourd'hui"""
        from django.utils import timezone
        aujourd_hui = timezone.now().date()
        return Vente.objects.filter(
            client_maui__boutique=self,
            date_vente__date=aujourd_hui
        ).count()
    
    def chiffre_affaires_aujourd_hui(self):
        """Retourne le chiffre d'affaires d'aujourd'hui"""
        from django.utils import timezone
        from django.db.models import Sum
        aujourd_hui = timezone.now().date()
        result = Vente.objects.filter(
            client_maui__boutique=self,
            date_vente__date=aujourd_hui,
            paye=True
        ).aggregate(total=Sum('montant_total'))
        return result['total'] or 0
    
    class Meta:
        verbose_name = "Boutique"
        verbose_name_plural = "Boutiques"
        ordering = ['commercant__nom_entreprise', 'nom']
        unique_together = ['commercant', 'nom']  # Nom unique par commerçant


class RapportCaisse(models.Model):
    """Rapport de caisse quotidien lié à une boutique et un terminal MAUI (Client)."""

    boutique = models.ForeignKey('Boutique', on_delete=models.CASCADE, related_name='rapports_caisse')
    terminal = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='rapports_caisse')

    date_rapport = models.DateTimeField(default=timezone.now)
    detail = models.TextField(max_length=500)
    depense = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    devise = models.CharField(max_length=10, default='CDF')

    depense_appliquee = models.BooleanField(default=False)
    date_application_depense = models.DateTimeField(null=True, blank=True)

    est_synchronise = models.BooleanField(default=True)
    id_backend = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Rapport {self.date_rapport} - {self.boutique} - {self.terminal}"

    class Meta:
        verbose_name = "Rapport de caisse"
        verbose_name_plural = "Rapports de caisse"
        ordering = ['-date_rapport', '-created_at']


class ArticleNegocie(models.Model):
    boutique = models.ForeignKey('Boutique', on_delete=models.CASCADE, related_name='articles_negocies')
    terminal = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='articles_negocies')
    article = models.ForeignKey(Article, on_delete=models.SET_NULL, null=True, blank=True, related_name='negociations')

    code_article = models.CharField(max_length=100)
    quantite = models.PositiveIntegerField(default=1)
    montant_negocie = models.DecimalField(max_digits=12, decimal_places=2)
    devise = models.CharField(max_length=10, default='CDF')
    date_operation = models.DateTimeField()
    motif = models.CharField(max_length=255, blank=True)
    reference_vente = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_operation', '-created_at']


class RetourArticle(models.Model):
    boutique = models.ForeignKey('Boutique', on_delete=models.CASCADE, related_name='retours_articles')
    terminal = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='retours_articles')
    article = models.ForeignKey(Article, on_delete=models.SET_NULL, null=True, blank=True, related_name='retours')

    code_article = models.CharField(max_length=100)
    quantite = models.PositiveIntegerField(default=1)
    montant_retourne = models.DecimalField(max_digits=12, decimal_places=2)
    devise = models.CharField(max_length=10, default='CDF')
    date_operation = models.DateTimeField()
    motif = models.CharField(max_length=255, blank=True)
    reference_vente = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_operation', '-created_at']


class VenteRejetee(models.Model):
    """
    Ventes rejetées lors de la synchronisation pour traçabilité et conformité.
    Permet de suivre les ventes offline qui n'ont pas pu être validées par le serveur.
    """
    
    RAISONS_REJET = [
        ('INSUFFICIENT_STOCK', 'Stock insuffisant'),
        ('ARTICLE_NOT_FOUND', 'Article non trouvé'),
        ('PRIX_MODIFIE', 'Prix modifié'),
        ('TOTAL_INCOHERENT', 'Total incohérent'),
        ('BOUTIQUE_MISMATCH', 'Boutique non autorisée'),
        ('DUPLICATE', 'Vente déjà existante'),
        ('INVALID_FORMAT', 'Format invalide'),
        ('OTHER', 'Autre erreur'),
    ]
    
    ACTIONS_REQUISES = [
        ('NOTIFY_USER', 'Notifier l\'utilisateur'),
        ('NOTIFY_MANAGER', 'Notifier le gérant'),
        ('ANNULATION', 'Annulation requise'),
        ('REGULARISATION', 'Régularisation requise'),
        ('AUCUNE', 'Aucune action requise'),
    ]
    
    # Identifiant unique de la vente rejetée
    vente_uid = models.CharField(max_length=100, db_index=True, 
                                 help_text="Numéro de facture/UID de la vente rejetée")
    
    # Liens avec terminal et boutique
    terminal = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='ventes_rejetees')
    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name='ventes_rejetees')
    
    # Date et données de la tentative
    date_tentative = models.DateTimeField(default=timezone.now, 
                                          help_text="Date de la tentative de synchronisation")
    date_vente_originale = models.DateTimeField(null=True, blank=True,
                                                help_text="Date originale de la vente côté client")
    donnees_vente = models.JSONField(help_text="Snapshot complet des données de vente envoyées")
    
    # Informations sur le rejet
    raison_rejet = models.CharField(max_length=50, choices=RAISONS_REJET, default='OTHER')
    message_erreur = models.TextField(help_text="Message d'erreur détaillé")
    
    # Détails pour faciliter le diagnostic
    article_concerne_id = models.IntegerField(null=True, blank=True,
                                              help_text="ID de l'article concerné si applicable")
    article_concerne_nom = models.CharField(max_length=100, blank=True)
    stock_demande = models.IntegerField(null=True, blank=True)
    stock_disponible = models.IntegerField(null=True, blank=True)
    
    # Gestion du traitement
    action_requise = models.CharField(max_length=20, choices=ACTIONS_REQUISES, default='NOTIFY_USER')
    traitee = models.BooleanField(default=False, help_text="Le rejet a-t-il été traité/résolu?")
    date_traitement = models.DateTimeField(null=True, blank=True)
    traite_par = models.CharField(max_length=100, blank=True, help_text="Utilisateur ayant traité le rejet")
    notes_traitement = models.TextField(blank=True, help_text="Notes sur le traitement effectué")
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Rejet {self.vente_uid} - {self.get_raison_rejet_display()} ({self.boutique.nom})"
    
    class Meta:
        verbose_name = "Vente rejetée"
        verbose_name_plural = "Ventes rejetées"
        ordering = ['-date_tentative']
        indexes = [
            models.Index(fields=['boutique', 'date_tentative'], name='rejet_boutique_date_idx'),
            models.Index(fields=['raison_rejet'], name='rejet_raison_idx'),
            models.Index(fields=['traitee'], name='rejet_traitee_idx'),
        ]


class TransfertStock(models.Model):
    """Transfert de stock du dépôt vers une boutique."""
    
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('VALIDE', 'Validé'),
        ('ANNULE', 'Annulé')
    ]
    
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='transferts')
    depot_source = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name='transferts_sortants',
                                    help_text="Dépôt d'origine")
    boutique_destination = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name='transferts_entrants',
                                            help_text="Boutique de destination")
    
    quantite = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    date_transfert = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(null=True, blank=True)
    
    effectue_par = models.CharField(max_length=100, help_text="Utilisateur ayant effectué le transfert")
    valide_par = models.CharField(max_length=100, blank=True, help_text="Utilisateur ayant validé le transfert")
    
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    reference_lot = models.CharField(max_length=50, blank=True, db_index=True, help_text="Référence de lot pour regrouper les transferts multiples")
    commentaire = models.TextField(blank=True)
    
    stock_depot_avant = models.IntegerField(null=True, blank=True, help_text="Stock du dépôt avant transfert")
    stock_depot_apres = models.IntegerField(null=True, blank=True, help_text="Stock du dépôt après transfert")
    stock_boutique_avant = models.IntegerField(null=True, blank=True, help_text="Stock de la boutique avant transfert")
    stock_boutique_apres = models.IntegerField(null=True, blank=True, help_text="Stock de la boutique après transfert")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Transfert {self.article.nom} - {self.depot_source.nom} → {self.boutique_destination.nom} ({self.quantite})"
    
    def valider_transfert(self, valide_par_user):
        """Valide le transfert et met à jour les stocks"""
        if self.statut != 'EN_ATTENTE':
            raise ValidationError("Ce transfert a déjà été traité")
        
        article_depot = self.article
        
        if article_depot.quantite_stock < self.quantite:
            raise ValidationError(f"Stock insuffisant au dépôt. Disponible: {article_depot.quantite_stock}, Demandé: {self.quantite}")
        
        self.stock_depot_avant = article_depot.quantite_stock
        article_depot.quantite_stock -= self.quantite
        article_depot.save()
        self.stock_depot_apres = article_depot.quantite_stock
        
        MouvementStock.objects.create(
            article=article_depot,
            type_mouvement='SORTIE',
            quantite=-self.quantite,
            stock_avant=self.stock_depot_avant,
            stock_apres=self.stock_depot_apres,
            commentaire=f"Transfert vers {self.boutique_destination.nom}",
            reference_document=f"TRANSFERT-{self.id}",
            utilisateur=valide_par_user
        )
        
        try:
            article_boutique = Article.objects.get(code=article_depot.code, boutique=self.boutique_destination)
            self.stock_boutique_avant = article_boutique.quantite_stock
            article_boutique.quantite_stock += self.quantite
            article_boutique.save()
            self.stock_boutique_apres = article_boutique.quantite_stock
        except Article.DoesNotExist:
            article_boutique = Article.objects.create(
                code=article_depot.code,
                nom=article_depot.nom,
                description=article_depot.description,
                prix_vente=article_depot.prix_vente,
                prix_achat=article_depot.prix_achat,
                categorie=article_depot.categorie,
                boutique=self.boutique_destination,
                quantite_stock=self.quantite,
                est_actif=True
            )
            self.stock_boutique_avant = 0
            self.stock_boutique_apres = self.quantite
        
        MouvementStock.objects.create(
            article=article_boutique,
            type_mouvement='ENTREE',
            quantite=self.quantite,
            stock_avant=self.stock_boutique_avant,
            stock_apres=self.stock_boutique_apres,
            commentaire=f"Transfert depuis {self.depot_source.nom}",
            reference_document=f"TRANSFERT-{self.id}",
            utilisateur=valide_par_user
        )
        
        self.statut = 'VALIDE'
        self.date_validation = timezone.now()
        self.valide_par = valide_par_user
        self.save()
    
    class Meta:
        verbose_name = "Transfert de stock"
        verbose_name_plural = "Transferts de stock"
        ordering = ['-date_transfert']
        indexes = [
            models.Index(fields=['depot_source', 'date_transfert'], name='transfert_depot_date_idx'),
            models.Index(fields=['boutique_destination', 'date_transfert'], name='transfert_boutique_date_idx'),
            models.Index(fields=['statut'], name='transfert_statut_idx'),
        ]


class NotificationStock(models.Model):
    """
    Notifications pour informer les clients MAUI des ajouts de stock.
    Créées automatiquement lorsque du stock est ajouté à leur boutique.
    """
    
    TYPE_NOTIFICATION_CHOICES = [
        ('STOCK_AJOUT', 'Ajout de stock'),
        ('STOCK_RETRAIT', 'Retrait de stock'),
        ('STOCK_TRANSFERT', 'Transfert de stock'),
        ('STOCK_AJUSTEMENT', 'Ajustement de stock'),
        ('AJUSTEMENT_PRIX', 'Ajustement de prix'),
    ]
    
    client = models.ForeignKey(
        Client, 
        on_delete=models.CASCADE, 
        related_name='notifications',
        help_text="Client MAUI destinataire de la notification"
    )
    boutique = models.ForeignKey(
        Boutique, 
        on_delete=models.CASCADE, 
        related_name='notifications',
        help_text="Boutique concernée par la notification"
    )
    
    type_notification = models.CharField(
        max_length=20, 
        choices=TYPE_NOTIFICATION_CHOICES,
        default='STOCK_AJOUT'
    )
    
    titre = models.CharField(
        max_length=200,
        help_text="Titre court de la notification"
    )
    message = models.TextField(
        help_text="Message détaillé de la notification"
    )
    
    mouvement_stock = models.ForeignKey(
        MouvementStock,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        help_text="Mouvement de stock associé"
    )
    
    article = models.ForeignKey(
        Article,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
        help_text="Article concerné"
    )
    
    quantite_mouvement = models.IntegerField(
        default=0,
        help_text="Quantité du mouvement (positif pour ajout, négatif pour retrait)"
    )
    
    stock_avant = models.IntegerField(
        default=0,
        help_text="Stock avant le mouvement"
    )
    
    stock_actuel = models.IntegerField(
        default=0,
        help_text="Stock actuel après le mouvement"
    )
    
    quantite_ajoutee = models.IntegerField(
        default=0,
        help_text="[DEPRECATED] Utiliser quantite_mouvement"
    )
    
    lue = models.BooleanField(
        default=False,
        help_text="La notification a-t-elle été lue?"
    )
    date_lecture = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date et heure de lecture"
    )
    
    date_creation = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de création de la notification"
    )
    
    donnees_supplementaires = models.JSONField(
        null=True,
        blank=True,
        help_text="Données supplémentaires (prix, catégorie, etc.)"
    )
    
    def marquer_comme_lue(self):
        """Marque la notification comme lue"""
        if not self.lue:
            self.lue = True
            self.date_lecture = timezone.now()
            self.save(update_fields=['lue', 'date_lecture'])
    
    def __str__(self):
        statut = "✓ Lue" if self.lue else "● Non lue"
        return f"{statut} - {self.titre} ({self.client.nom_terminal})"
    
    class Meta:
        verbose_name = "Notification de stock"
        verbose_name_plural = "Notifications de stock"
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['client', 'lue', '-date_creation'], name='notif_client_lue_date_idx'),
            models.Index(fields=['boutique', '-date_creation'], name='notif_boutique_date_idx'),
            models.Index(fields=['lue', '-date_creation'], name='notif_lue_date_idx'),
        ]


class Fournisseur(models.Model):
    """Fournisseurs pour les approvisionnements."""
    
    nom = models.CharField(max_length=200, help_text="Nom du fournisseur")
    contact = models.CharField(max_length=100, blank=True, help_text="Téléphone ou email")
    adresse = models.TextField(blank=True, help_text="Adresse du fournisseur")
    commercant = models.ForeignKey('Commercant', on_delete=models.CASCADE, related_name='fournisseurs')
    est_actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.nom
    
    class Meta:
        verbose_name = "Fournisseur"
        verbose_name_plural = "Fournisseurs"
        ordering = ['nom']
        unique_together = ['nom', 'commercant']


class FactureApprovisionnement(models.Model):
    """Facture d'approvisionnement regroupant plusieurs articles."""
    
    numero_facture = models.CharField(max_length=100, help_text="Numéro de facture fournisseur")
    fournisseur = models.ForeignKey(Fournisseur, on_delete=models.SET_NULL, null=True, blank=True, related_name='factures')
    fournisseur_nom = models.CharField(max_length=200, blank=True, help_text="Nom du fournisseur (si pas dans la liste)")
    depot = models.ForeignKey('Boutique', on_delete=models.CASCADE, related_name='factures_approvisionnement')
    date_facture = models.DateField(help_text="Date de la facture")
    montant_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Montant total de la facture")
    devise = models.CharField(max_length=3, choices=[('CDF', 'Franc Congolais'), ('USD', 'Dollar US')], default='CDF')
    notes = models.TextField(blank=True, help_text="Notes ou commentaires")
    created_by = models.CharField(max_length=150, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        fournisseur_display = self.fournisseur.nom if self.fournisseur else self.fournisseur_nom
        return f"Facture {self.numero_facture} - {fournisseur_display}"
    
    def calculer_montant_total(self):
        """Recalcule le montant total à partir des lignes."""
        total = self.lignes.aggregate(
            total=models.Sum(models.F('prix_achat_total'))
        )['total'] or 0
        self.montant_total = total
        self.save(update_fields=['montant_total'])
        return total
    
    class Meta:
        verbose_name = "Facture d'approvisionnement"
        verbose_name_plural = "Factures d'approvisionnement"
        ordering = ['-date_facture', '-date_creation']
        unique_together = [['numero_facture', 'depot']]
        indexes = [
            models.Index(fields=['depot', '-date_facture'], name='facture_depot_date_idx'),
            models.Index(fields=['numero_facture'], name='facture_numero_idx'),
        ]


class LigneApprovisionnement(models.Model):
    """Ligne d'une facture d'approvisionnement (un article)."""
    
    TYPE_QUANTITE_CHOICES = [
        ('UNITE', 'Unités'),
        ('CARTON', 'Cartons'),
    ]
    
    facture = models.ForeignKey(FactureApprovisionnement, on_delete=models.CASCADE, related_name='lignes')
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='lignes_approvisionnement')
    categorie = models.ForeignKey(Categorie, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Type de quantité (unité ou carton)
    type_quantite = models.CharField(max_length=10, choices=TYPE_QUANTITE_CHOICES, default='UNITE')
    
    # Pour les cartons
    nombre_cartons = models.IntegerField(default=0, help_text="Nombre de cartons")
    pieces_par_carton = models.IntegerField(default=1, help_text="Nombre de pièces par carton")
    
    # Quantité finale en unités
    quantite_unites = models.IntegerField(help_text="Quantité totale en unités")
    
    # Prix
    prix_achat_carton = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Prix d'achat par carton")
    prix_achat_unitaire = models.DecimalField(max_digits=12, decimal_places=2, help_text="Prix d'achat unitaire calculé")
    prix_achat_total = models.DecimalField(max_digits=15, decimal_places=2, help_text="Prix total de la ligne")
    
    # Prix de vente suggéré
    prix_vente_unitaire = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Prix de vente unitaire")
    
    date_creation = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        # Calcul automatique des quantités et prix
        if self.type_quantite == 'CARTON' and self.nombre_cartons > 0 and self.pieces_par_carton > 0:
            self.quantite_unites = self.nombre_cartons * self.pieces_par_carton
            if self.prix_achat_carton > 0:
                self.prix_achat_unitaire = self.prix_achat_carton / self.pieces_par_carton
        
        # Calcul du prix total
        self.prix_achat_total = self.quantite_unites * self.prix_achat_unitaire
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.article.nom} x {self.quantite_unites} ({self.facture.numero_facture})"
    
    class Meta:
        verbose_name = "Ligne d'approvisionnement"
        verbose_name_plural = "Lignes d'approvisionnement"
        ordering = ['date_creation']


class Inventaire(models.Model):
    """Modèle représentant un inventaire physique du stock."""
    
    STATUT_CHOICES = [
        ('EN_COURS', 'En cours'),
        ('TERMINE', 'Terminé'),
        ('REGULARISE', 'Régularisé'),
        ('ANNULE', 'Annulé'),
    ]
    
    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name='inventaires')
    reference = models.CharField(max_length=50, unique=True, help_text="Référence unique de l'inventaire")
    date_inventaire = models.DateField(help_text="Date de l'inventaire")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_COURS')
    
    # Statistiques
    nb_articles = models.IntegerField(default=0)
    nb_ecarts = models.IntegerField(default=0)
    valeur_ecart_positif = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    valeur_ecart_negatif = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    notes = models.TextField(blank=True)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='inventaires_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_cloture = models.DateTimeField(null=True, blank=True)
    date_regularisation = models.DateTimeField(null=True, blank=True)
    
    def generer_reference(self):
        """Génère une référence unique pour l'inventaire."""
        date_str = timezone.now().strftime('%Y%m%d')
        count = Inventaire.objects.filter(reference__startswith=f'INV-{date_str}').count() + 1
        return f'INV-{date_str}-{count:03d}'
    
    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generer_reference()
        super().save(*args, **kwargs)
    
    def calculer_statistiques(self):
        """Calcule les statistiques de l'inventaire."""
        lignes = self.lignes.all()
        self.nb_articles = lignes.count()
        self.nb_ecarts = lignes.exclude(ecart=0).count()
        self.valeur_ecart_positif = sum(l.valeur_ecart for l in lignes if l.ecart > 0)
        self.valeur_ecart_negatif = abs(sum(l.valeur_ecart for l in lignes if l.ecart < 0))
        self.save()
    
    def __str__(self):
        return f"{self.reference} - {self.boutique.nom} ({self.get_statut_display()})"
    
    class Meta:
        verbose_name = "Inventaire"
        verbose_name_plural = "Inventaires"
        ordering = ['-date_creation']


class LigneInventaire(models.Model):
    """Ligne d'inventaire pour un article."""
    
    inventaire = models.ForeignKey(Inventaire, on_delete=models.CASCADE, related_name='lignes')
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='lignes_inventaire')
    
    # Quantités
    stock_theorique = models.IntegerField(help_text="Stock système au moment de l'inventaire")
    stock_physique = models.IntegerField(null=True, blank=True, help_text="Stock compté physiquement")
    ecart = models.IntegerField(default=0, help_text="Écart (physique - théorique)")
    
    # Valeurs
    prix_unitaire = models.DecimalField(max_digits=12, decimal_places=2, help_text="Prix d'achat unitaire")
    valeur_ecart = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Régularisation
    est_regularise = models.BooleanField(default=False)
    commentaire = models.TextField(blank=True, help_text="Commentaire ou justification de l'écart")
    
    date_saisie = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        # Calculer l'écart si stock physique renseigné
        if self.stock_physique is not None:
            self.ecart = self.stock_physique - self.stock_theorique
            self.valeur_ecart = self.ecart * self.prix_unitaire
            if not self.date_saisie:
                self.date_saisie = timezone.now()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.article.nom} - Écart: {self.ecart}"
    
    class Meta:
        verbose_name = "Ligne d'inventaire"
        verbose_name_plural = "Lignes d'inventaire"
        unique_together = ['inventaire', 'article']
        ordering = ['article__nom']


class ErreurTransaction(models.Model):
    """Capture et suivi des erreurs de transaction pour le débogage."""
    
    TYPE_ERREUR_CHOICES = [
        ('VENTE', 'Erreur de vente'),
        ('PAIEMENT', 'Erreur de paiement'),
        ('STOCK', 'Erreur de stock'),
        ('SYNC', 'Erreur de synchronisation'),
        ('API', 'Erreur API'),
        ('AUTRE', 'Autre erreur'),
    ]
    
    GRAVITE_CHOICES = [
        ('INFO', 'Information'),
        ('WARNING', 'Avertissement'),
        ('ERROR', 'Erreur'),
        ('CRITICAL', 'Critique'),
    ]
    
    # Informations de contexte
    boutique = models.ForeignKey('Boutique', on_delete=models.SET_NULL, null=True, blank=True, related_name='erreurs_transactions')
    commercant = models.ForeignKey('Commercant', on_delete=models.SET_NULL, null=True, blank=True, related_name='erreurs_transactions')
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='erreurs_transactions')
    client_maui = models.ForeignKey('Client', on_delete=models.SET_NULL, null=True, blank=True, related_name='erreurs_transactions')
    
    # Type et gravité
    type_erreur = models.CharField(max_length=20, choices=TYPE_ERREUR_CHOICES, default='VENTE')
    gravite = models.CharField(max_length=20, choices=GRAVITE_CHOICES, default='ERROR')
    
    # Détails de l'erreur
    message = models.TextField(help_text="Message d'erreur principal")
    details = models.TextField(blank=True, help_text="Détails techniques (traceback, etc.)")
    donnees_contexte = models.JSONField(default=dict, blank=True, help_text="Données de contexte JSON (panier, articles, etc.)")
    
    # Informations de requête
    url_requete = models.CharField(max_length=500, blank=True)
    methode_requete = models.CharField(max_length=10, blank=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    
    # Suivi
    est_resolu = models.BooleanField(default=False)
    note_resolution = models.TextField(blank=True, help_text="Notes de résolution")
    resolu_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='erreurs_resolues')
    date_resolution = models.DateTimeField(null=True, blank=True)
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        boutique_nom = self.boutique.nom if self.boutique else 'N/A'
        return f"[{self.gravite}] {self.type_erreur} - {boutique_nom} - {self.date_creation.strftime('%d/%m/%Y %H:%M')}"
    
    class Meta:
        verbose_name = "Erreur de transaction"
        verbose_name_plural = "Erreurs de transactions"
        ordering = ['-date_creation']


class TransactionMobileMoney(models.Model):
    """
    Modèle pour les transactions Mobile Money (Dépôt, Retrait, Transfert)
    """
    
    TYPE_OPERATION_CHOICES = [
        ('DEPOT', 'Dépôt'),
        ('RETRAIT', 'Retrait'),
        ('TRANSFERT', 'Transfert'),
        ('PAIEMENT', 'Paiement facture'),
    ]
    
    OPERATEUR_CHOICES = [
        ('AIRTEL', 'Airtel Money'),
        ('VODACOM', 'M-Pesa (Vodacom)'),
        ('ORANGE', 'Orange Money'),
        ('AFRICELL', 'Africell Money'),
        ('AFRIMONEY', 'Afrimoney'),
    ]
    
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('CONFIRME', 'Confirmé'),
        ('ANNULE', 'Annulé'),
        ('ECHOUE', 'Échoué'),
    ]
    
    # Relation avec la boutique Mobile Money
    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name='transactions_mobile_money')
    
    # Type d'opération
    type_operation = models.CharField(max_length=20, choices=TYPE_OPERATION_CHOICES)
    operateur = models.CharField(max_length=20, choices=OPERATEUR_CHOICES)
    
    # Informations client
    numero_telephone_client = models.CharField(max_length=20, help_text="Numéro de téléphone du client")
    nom_client = models.CharField(max_length=100, blank=True, help_text="Nom du client (optionnel)")
    
    # Pour les transferts
    numero_destinataire = models.CharField(max_length=20, blank=True, help_text="Numéro du destinataire (pour transferts)")
    
    # Montants
    montant = models.DecimalField(max_digits=15, decimal_places=2, help_text="Montant de la transaction")
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Commission perçue")
    montant_net = models.DecimalField(max_digits=15, decimal_places=2, help_text="Montant net (après commission)")
    
    # Référence et statut
    reference_operateur = models.CharField(max_length=100, blank=True, help_text="Code de confirmation de l'opérateur")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    
    # Métadonnées
    date_transaction = models.DateTimeField(auto_now_add=True)
    date_confirmation = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    # Utilisateur qui a effectué la transaction
    effectue_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def save(self, *args, **kwargs):
        # Calculer le montant net si non défini
        if not self.montant_net:
            self.montant_net = self.montant - self.commission
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.get_type_operation_display()} - {self.numero_telephone_client} - {self.montant} FC"
    
    class Meta:
        verbose_name = "Transaction Mobile Money"
        verbose_name_plural = "Transactions Mobile Money"
        ordering = ['-date_transaction']


class VenteCredit(models.Model):
    """
    Modèle pour la vente de crédit téléphonique (gros et détail)
    """
    
    TYPE_VENTE_CHOICES = [
        ('DETAIL', 'Détail'),
        ('GROS', 'Gros'),
    ]
    
    OPERATEUR_CHOICES = [
        ('AIRTEL', 'Airtel'),
        ('VODACOM', 'Vodacom'),
        ('ORANGE', 'Orange'),
        ('AFRICELL', 'Africell'),
        ('AFRIMONEY', 'Afrimoney'),
    ]
    
    # Relation avec la boutique
    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name='ventes_credit')
    
    # Type de vente
    type_vente = models.CharField(max_length=10, choices=TYPE_VENTE_CHOICES, default='DETAIL')
    operateur = models.CharField(max_length=20, choices=OPERATEUR_CHOICES)
    
    # Informations client (pour gros)
    numero_telephone_client = models.CharField(max_length=20, blank=True, help_text="Numéro du client (pour gros)")
    nom_client = models.CharField(max_length=100, blank=True, help_text="Nom du client (pour gros)")
    
    # Unités vendues (montant en FC)
    unites_vendues = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Unités de crédit vendues (en FC)")
    montant_recu = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Montant reçu du client")
    benefice = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Bénéfice réalisé")
    
    # Métadonnées
    date_vente = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    effectue_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        # Calculer le bénéfice
        self.benefice = self.montant_recu - self.unites_vendues
        super().save(*args, **kwargs)
        # Déduire du stock seulement pour une nouvelle vente
        if is_new:
            try:
                stock = StockCredit.objects.get(boutique=self.boutique, operateur=self.operateur)
                stock.unites_disponibles -= self.unites_vendues
                stock.save()
            except StockCredit.DoesNotExist:
                pass
    
    def __str__(self):
        return f"Crédit {self.get_operateur_display()} - {self.unites_vendues} FC ({self.get_type_vente_display()})"
    
    class Meta:
        verbose_name = "Vente de crédit"
        verbose_name_plural = "Ventes de crédit"
        ordering = ['-date_vente']


class StockCredit(models.Model):
    """
    Modèle pour gérer le stock d'unités de crédit par opérateur (envoyé par flash)
    """
    
    OPERATEUR_CHOICES = VenteCredit.OPERATEUR_CHOICES
    
    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name='stocks_credit')
    operateur = models.CharField(max_length=20, choices=OPERATEUR_CHOICES)
    
    # Stock en unités (montant total disponible en FC)
    unites_disponibles = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Unités de crédit disponibles (en FC)")
    seuil_alerte = models.DecimalField(max_digits=15, decimal_places=2, default=50000, help_text="Seuil d'alerte stock bas")
    
    # Suivi des coûts
    cout_total_achats = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Coût total des achats")
    
    # Dernière mise à jour
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    
    @property
    def est_bas(self):
        return self.unites_disponibles <= self.seuil_alerte
    
    def __str__(self):
        return f"Stock {self.get_operateur_display()} - {self.boutique.nom}: {self.unites_disponibles} unités"
    
    class Meta:
        verbose_name = "Stock de crédit"
        verbose_name_plural = "Stocks de crédit"
        unique_together = ['boutique', 'operateur']


class ApprovisionnementCredit(models.Model):
    """
    Modèle pour l'approvisionnement en unités de crédit (flash)
    """
    
    OPERATEUR_CHOICES = VenteCredit.OPERATEUR_CHOICES
    
    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name='approvisionnements_credit')
    operateur = models.CharField(max_length=20, choices=OPERATEUR_CHOICES)
    
    # Unités approvisionnées (montant en FC)
    unites = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Unités envoyées par flash (en FC)")
    cout_achat = models.DecimalField(max_digits=15, decimal_places=2, help_text="Coût d'achat des unités")
    
    # Fournisseur/Source
    fournisseur = models.CharField(max_length=100, blank=True, help_text="Source du flash")
    reference = models.CharField(max_length=100, blank=True, help_text="Référence de la transaction")
    
    # Métadonnées
    date_approvisionnement = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    effectue_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    @property
    def marge(self):
        """Marge potentielle sur cet approvisionnement"""
        return self.unites - self.cout_achat
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # Mettre à jour le stock seulement pour un nouvel approvisionnement
        if is_new:
            stock, created = StockCredit.objects.get_or_create(
                boutique=self.boutique,
                operateur=self.operateur,
                defaults={'unites_disponibles': 0, 'cout_total_achats': 0}
            )
            stock.unites_disponibles += self.unites
            stock.cout_total_achats += self.cout_achat
            stock.save()
    
    def __str__(self):
        return f"Flash {self.get_operateur_display()} - {self.unites} unités"
    
    class Meta:
        verbose_name = "Approvisionnement crédit"
        verbose_name_plural = "Approvisionnements crédit"
        ordering = ['-date_approvisionnement']


class AlerteStock(models.Model):
    """
    Modèle pour enregistrer les alertes de stock lors des ventes.
    Créé quand une vente est acceptée malgré un écart de stock entre client et serveur.
    Permet au commerçant de régulariser les écarts en fin de journée.
    """
    
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente de régularisation'),
        ('REGULARISE', 'Régularisé'),
        ('IGNORE', 'Ignoré'),
    ]
    
    TYPE_ALERTE_CHOICES = [
        ('STOCK_INSUFFISANT', 'Stock insuffisant'),
        ('STOCK_NEGATIF', 'Stock devenu négatif'),
        ('ECART_STOCK', 'Écart de stock détecté'),
    ]
    
    # Lien avec la vente et la boutique
    vente = models.ForeignKey('Vente', on_delete=models.CASCADE, related_name='alertes_stock')
    boutique = models.ForeignKey('Boutique', on_delete=models.CASCADE, related_name='alertes_stock')
    terminal = models.ForeignKey('Client', on_delete=models.SET_NULL, null=True, blank=True, related_name='alertes_stock')
    
    # Article concerné
    article = models.ForeignKey('Article', on_delete=models.CASCADE, related_name='alertes_stock')
    variante = models.ForeignKey('VarianteArticle', on_delete=models.SET_NULL, null=True, blank=True, related_name='alertes_stock')
    
    # Détails de l'écart
    type_alerte = models.CharField(max_length=30, choices=TYPE_ALERTE_CHOICES, default='STOCK_INSUFFISANT')
    quantite_vendue = models.PositiveIntegerField(help_text="Quantité vendue par le client")
    stock_serveur_avant = models.IntegerField(help_text="Stock serveur avant la vente")
    stock_serveur_apres = models.IntegerField(help_text="Stock serveur après la vente (peut être négatif)")
    ecart = models.IntegerField(help_text="Écart de stock (négatif = manque)")
    
    # Statut de régularisation
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    date_regularisation = models.DateTimeField(null=True, blank=True)
    regularise_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='alertes_regularisees')
    notes_regularisation = models.TextField(blank=True, help_text="Notes sur la régularisation effectuée")
    
    # Action suggérée
    action_suggeree = models.TextField(blank=True, help_text="Action suggérée pour régulariser")
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    numero_facture = models.CharField(max_length=100, blank=True)
    
    def save(self, *args, **kwargs):
        # Calculer l'écart automatiquement
        if not self.ecart:
            self.ecart = self.stock_serveur_avant - self.quantite_vendue
        
        # Définir le type d'alerte automatiquement
        if self.stock_serveur_apres < 0:
            self.type_alerte = 'STOCK_NEGATIF'
        elif self.stock_serveur_avant < self.quantite_vendue:
            self.type_alerte = 'STOCK_INSUFFISANT'
        
        # Générer l'action suggérée
        if not self.action_suggeree:
            nom_article = self.variante.nom_complet if self.variante else self.article.nom
            if self.stock_serveur_apres < 0:
                self.action_suggeree = f"Vérifier l'inventaire physique de '{nom_article}'. Stock serveur négatif ({self.stock_serveur_apres}). Ajuster le stock ou récupérer {abs(self.stock_serveur_apres)} article(s)."
            else:
                self.action_suggeree = f"Vérifier le stock de '{nom_article}'. Écart détecté lors de la vente."
        
        super().save(*args, **kwargs)
    
    def regulariser(self, user, notes=""):
        """Marquer l'alerte comme régularisée"""
        self.statut = 'REGULARISE'
        self.date_regularisation = timezone.now()
        self.regularise_par = user
        self.notes_regularisation = notes
        self.save()
    
    def ignorer(self, user, notes=""):
        """Marquer l'alerte comme ignorée"""
        self.statut = 'IGNORE'
        self.date_regularisation = timezone.now()
        self.regularise_par = user
        self.notes_regularisation = notes
        self.save()
    
    @property
    def nom_article_complet(self):
        if self.variante:
            return self.variante.nom_complet
        return self.article.nom
    
    def __str__(self):
        return f"Alerte {self.get_type_alerte_display()} - {self.nom_article_complet} ({self.ecart})"
    
    class Meta:
        verbose_name = "Alerte stock"
        verbose_name_plural = "Alertes stock"
        ordering = ['-date_creation']
