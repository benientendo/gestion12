# models_multi_commercants.py
# Nouveaux modèles pour l'architecture multi-commerçants

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
import uuid
from django.utils import timezone

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
    utilisateur = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profil_commercant',
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
    
    limite_boutiques = models.IntegerField(default=1, help_text="Nombre maximum de boutiques autorisées")
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
        return self.nombre_boutiques() < self.limite_boutiques
    
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
    quartier = models.CharField(max_length=100, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    
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
    
    def save(self, *args, **kwargs):
        # Générer un code boutique unique si pas défini
        if not self.code_boutique:
            # Format: COMM_BOUTIQUE_001
            commercant_prefix = self.commercant.nom_entreprise[:4].upper().replace(' ', '')
            numero = self.commercant.boutiques.count() + 1
            self.code_boutique = f"{commercant_prefix}_BOUT_{numero:03d}"
        
        # Générer une clé API si pas définie
        if not self.cle_api:
            self.cle_api = str(uuid.uuid4())
            
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
        return self.ventes.filter(date_vente__date=aujourd_hui).count()
    
    def chiffre_affaires_aujourd_hui(self):
        """Retourne le chiffre d'affaires d'aujourd'hui"""
        from django.utils import timezone
        from django.db.models import Sum
        aujourd_hui = timezone.now().date()
        result = self.ventes.filter(
            date_vente__date=aujourd_hui,
            paye=True
        ).aggregate(total=Sum('montant_total'))
        return result['total'] or 0
    
    class Meta:
        verbose_name = "Boutique"
        verbose_name_plural = "Boutiques"
        ordering = ['commercant__nom_entreprise', 'nom']
        unique_together = ['commercant', 'nom']  # Nom unique par commerçant


class TerminalMaui(models.Model):
    """
    Modèle représentant un terminal MAUI connecté à une boutique.
    Remplace l'ancien modèle Client avec une liaison vers Boutique.
    """
    
    # Informations de base
    nom_terminal = models.CharField(max_length=200, help_text="Nom du terminal (ex: Caisse 1, Terminal Principal)")
    description = models.TextField(blank=True, help_text="Description du terminal")
    
    # Association avec la boutique
    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name='terminaux',
                               help_text="Boutique à laquelle ce terminal est associé")
    
    # Système d'authentification
    numero_serie = models.CharField(max_length=50, unique=True, 
                                  help_text="Numéro de série unique pour l'authentification MAUI")
    cle_api = models.CharField(max_length=100, unique=True, default=uuid.uuid4,
                             help_text="Clé API générée automatiquement")
    
    # Informations de l'utilisateur du terminal
    nom_utilisateur = models.CharField(max_length=100, blank=True, 
                                     help_text="Nom de la personne utilisant ce terminal")
    
    # Statut et informations de connexion
    est_actif = models.BooleanField(default=True, help_text="Le terminal peut-il se connecter?")
    derniere_connexion = models.DateTimeField(null=True, blank=True)
    derniere_activite = models.DateTimeField(null=True, blank=True)
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    
    # Paramètres du terminal
    version_app_maui = models.CharField(max_length=20, blank=True)
    derniere_adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        # Générer automatiquement une clé API si elle n'existe pas
        if not self.cle_api:
            self.cle_api = str(uuid.uuid4())
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.nom_terminal} - {self.boutique.nom} ({self.numero_serie})"
    
    class Meta:
        verbose_name = "Terminal MAUI"
        verbose_name_plural = "Terminaux MAUI"
        ordering = ['boutique__nom', 'nom_terminal']


class SessionTerminalMaui(models.Model):
    """
    Modèle pour suivre les sessions actives des terminaux MAUI.
    Remplace SessionClientMaui avec liaison vers TerminalMaui.
    """
    
    terminal = models.ForeignKey(TerminalMaui, on_delete=models.CASCADE, related_name='sessions')
    token_session = models.CharField(max_length=100, unique=True)
    date_debut = models.DateTimeField(auto_now_add=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    est_active = models.BooleanField(default=True)
    
    # Informations de connexion
    adresse_ip = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    version_app = models.CharField(max_length=20, blank=True)
    
    def __str__(self):
        return f"Session {self.terminal.nom_terminal} - {self.date_debut}"
    
    class Meta:
        verbose_name = "Session Terminal MAUI"
        verbose_name_plural = "Sessions Terminaux MAUI"
        ordering = ['-date_debut']


    
