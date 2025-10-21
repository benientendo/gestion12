#!/usr/bin/env python
"""
Script pour nettoyer le fichier models.py et le restaurer à l'état original
"""

# Contenu original du fichier models.py
ORIGINAL_MODELS_CONTENT = '''from django.db import models
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
    quantite_stock = models.IntegerField(default=0)
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
    """Mouvements de stock."""
    
    TYPES = [
        ('ENTREE', 'Entrée de stock'),
        ('SORTIE', 'Sortie de stock'),
        ('AJUSTEMENT', 'Ajustement'),
        ('VENTE', 'Vente')
    ]
    
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='mouvements')
    type_mouvement = models.CharField(max_length=20, choices=TYPES)
    quantite = models.IntegerField()
    date_mouvement = models.DateTimeField(auto_now_add=True)
    commentaire = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.type_mouvement} - {self.article.nom} ({self.quantite})"
    
    class Meta:
        ordering = ['-date_mouvement']
'''

def clean_models_file():
    """Nettoyer le fichier models.py"""
    
    try:
        # Écrire le contenu original
        with open('inventory/models.py', 'w', encoding='utf-8') as f:
            f.write(ORIGINAL_MODELS_CONTENT)
        
        print("✅ Fichier models.py restauré à l'état original!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la restauration: {e}")
        return False

if __name__ == "__main__":
    success = clean_models_file()
    exit(0 if success else 1)
'''
