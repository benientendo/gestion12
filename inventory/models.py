from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
import re
import qrcode
from io import BytesIO
from django.core.files import File
import json
import logging
import uuid
import random
import string

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
    
    code = models.CharField(max_length=50, unique=True)
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    prix_vente = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    prix_achat = models.DecimalField(max_digits=10, decimal_places=2)
    categorie = models.ForeignKey(Categorie, on_delete=models.SET_NULL, null=True, related_name='articles')
    boutique = models.ForeignKey('Boutique', on_delete=models.CASCADE, related_name='articles', null=True, blank=True)
    quantite_stock = models.IntegerField(default=0)
    est_actif = models.BooleanField(default=True, help_text="L'article est-il actif?")
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True)
    image = models.ImageField(upload_to='articles/', blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nom} ({self.code})"

    def save(self, *args, **kwargs):
        logger = logging.getLogger(__name__)
        
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
    
    class Meta:
        verbose_name = "Article"
        verbose_name_plural = "Articles"
        ordering = ['nom']


class Vente(models.Model):
    """Ventes."""
    
    numero_facture = models.CharField(max_length=50, unique=True)
    date_vente = models.DateTimeField(auto_now_add=True)
    montant_total = models.DecimalField(max_digits=12, decimal_places=2)
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
    
    def __str__(self):
        return f"Vente {self.numero_facture} - {self.date_vente.strftime('%d/%m/%Y')}"
    
    class Meta:
        verbose_name = "Vente"
        verbose_name_plural = "Ventes"
        ordering = ['-date_vente']


class LigneVente(models.Model):
    vente = models.ForeignKey(Vente, related_name='lignes', on_delete=models.CASCADE)
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField()
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    
    @property
    def total_ligne(self):
        return self.quantite * self.prix_unitaire
    
    def __str__(self):
        return f"{self.article.nom} x{self.quantite}"
    
    class Meta:
        verbose_name = "Ligne de vente"
        verbose_name_plural = "Lignes de vente"


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
        """Retourne le nombre de boutiques de ce commerçant"""
        return self.boutiques.count()
    
    def peut_creer_boutique(self):
        """Vérifie si le commerçant peut créer une nouvelle boutique"""
        return self.nombre_boutiques() < self.max_boutiques
    
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
    type_commerce = models.CharField(max_length=50, choices=[
        ('PHARMACIE', 'Pharmacie'),
        ('BAR', 'Bar/Café'),
        ('ALIMENTATION', 'Alimentation générale'),
        ('SUPERMARCHE', 'Supermarché'),
        ('BOUTIQUE', 'Boutique générale'),
        ('KIOSQUE', 'Kiosque'),
        ('HABILLEMENT', 'Habillement'),
        ('ELECTRONIQUE', 'Électronique'),
        ('AUTRE', 'Autre')
    ], default='BOUTIQUE')
    
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
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    
    # Paramètres de fonctionnement
    devise = models.CharField(max_length=10, default='CDF')
    alerte_stock_bas = models.IntegerField(default=5, help_text="Seuil d'alerte pour stock bas")
    
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
