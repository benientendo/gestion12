# models_modifications.py
# Modifications des modèles existants pour supporter l'architecture multi-boutiques

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

# Import des nouveaux modèles
from .models_multi_commercants import Boutique, TerminalMaui

class Categorie(models.Model):
    """
    Modèle Catégorie modifié pour supporter les boutiques.
    Une catégorie peut être globale (partagée) ou spécifique à une boutique.
    """
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Nouvelle liaison optionnelle vers boutique
    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, null=True, blank=True,
                               related_name='categories',
                               help_text="Si défini, cette catégorie n'est visible que dans cette boutique. "
                                        "Si vide, la catégorie est globale.")
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        if self.boutique:
            return f"{self.nom} ({self.boutique.nom})"
        return f"{self.nom} (Global)"
    
    def est_globale(self):
        """Retourne True si la catégorie est globale (non liée à une boutique)"""
        return self.boutique is None
    
    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        # Une catégorie ne peut avoir le même nom qu'une seule fois par boutique
        unique_together = ['nom', 'boutique']
        ordering = ['boutique__nom', 'nom']


class Article(models.Model):
    """
    Modèle Article modifié pour être lié à une boutique spécifique.
    Chaque article appartient maintenant à une boutique.
    """
    code = models.CharField(max_length=50, help_text="Code unique de l'article dans la boutique")
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    prix_vente = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    prix_achat = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Nouvelle liaison obligatoire vers boutique
    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name='articles',
                               help_text="Boutique à laquelle appartient cet article")
    
    # Catégorie (peut être globale ou spécifique à la boutique)
    categorie = models.ForeignKey(Categorie, on_delete=models.SET_NULL, null=True, related_name='articles')
    
    quantite_stock = models.IntegerField(default=0)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True)
    image = models.ImageField(upload_to='articles/', blank=True, null=True)
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    
    # Paramètres spécifiques à l'article
    est_actif = models.BooleanField(default=True, help_text="L'article est-il disponible à la vente?")
    stock_minimum = models.IntegerField(default=0, help_text="Stock minimum avant alerte")
    
    def clean(self):
        """Validation personnalisée"""
        super().clean()
        
        # Vérifier que la catégorie est compatible avec la boutique
        if self.categorie and self.categorie.boutique:
            if self.categorie.boutique != self.boutique:
                raise ValidationError(
                    "La catégorie sélectionnée n'appartient pas à la même boutique que l'article."
                )
    
    def __str__(self):
        return f"{self.nom} ({self.code}) - {self.boutique.nom}"

    def save(self, *args, **kwargs):
        logger = logging.getLogger(__name__)
        action = 'Mise à jour' if self.pk else 'Création'
        logger.info(f"[Article.save - {action}] Article ID: {self.pk}, Code: {self.code}, Nom: {self.nom}, Boutique: {self.boutique}")
        
        # Determine if this save call is specifically for updating the qr_code field
        updating_qr_code_field_only = False
        update_fields = kwargs.get('update_fields')
        if update_fields and isinstance(update_fields, (list, tuple)) and 'qr_code' in update_fields and len(update_fields) == 1:
            updating_qr_code_field_only = True

        # Call the original save method
        super(Article, self).save(*args, **kwargs)

        # Generate and save QR code only if needed
        if self.pk and not self.qr_code and not updating_qr_code_field_only:
            logger.info(f"[Article.save] Génération du QR code pour l'article ID: {self.pk}")
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
                'boutique_id': self.boutique.id,
                'boutique_nom': self.boutique.nom,
                'categorie': self.categorie.nom if self.categorie else ''
            }
            qr.add_data(json.dumps(qr_data))
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            filename = f'qr_code_{self.boutique.code_boutique}_{self.code}.png'
            self.qr_code.save(filename, File(buffer), save=False)
            super(Article, self).save(update_fields=['qr_code'])
    
    def est_en_stock(self):
        """Vérifie si l'article est en stock"""
        return self.quantite_stock > 0 and self.est_actif
    
    def stock_bas(self):
        """Vérifie si le stock est en dessous du minimum"""
        return self.quantite_stock <= self.stock_minimum
    
    class Meta:
        verbose_name = "Article"
        verbose_name_plural = "Articles"
        # Le code doit être unique par boutique
        unique_together = ['code', 'boutique']
        ordering = ['boutique__nom', 'nom']


class Vente(models.Model):
    """
    Modèle Vente modifié pour être lié à une boutique et un terminal.
    """
    numero_facture = models.CharField(max_length=50, help_text="Numéro unique de facture dans la boutique")
    date_vente = models.DateTimeField(auto_now_add=True)
    montant_total = models.DecimalField(max_digits=12, decimal_places=2)
    paye = models.BooleanField(default=False)
    mode_paiement = models.CharField(max_length=50, choices=[
        ('CASH', 'Espèces'),
        ('CARD', 'Carte bancaire'),
        ('MOBILE', 'Paiement mobile')
    ])
    
    # Nouvelles liaisons obligatoires
    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name='ventes',
                               help_text="Boutique où la vente a été effectuée")
    
    terminal_maui = models.ForeignKey(TerminalMaui, on_delete=models.CASCADE, related_name='ventes',
                                    help_text="Terminal MAUI qui a effectué cette vente")
    
    # Informations supplémentaires pour le suivi
    adresse_ip_client = models.GenericIPAddressField(null=True, blank=True)
    version_app_maui = models.CharField(max_length=20, blank=True)
    
    # Informations client (optionnelles)
    nom_client = models.CharField(max_length=100, blank=True, help_text="Nom du client (optionnel)")
    telephone_client = models.CharField(max_length=20, blank=True)
    
    def clean(self):
        """Validation personnalisée"""
        super().clean()
        
        # Vérifier que le terminal appartient à la même boutique
        if self.terminal_maui and self.terminal_maui.boutique != self.boutique:
            raise ValidationError(
                "Le terminal MAUI doit appartenir à la même boutique que la vente."
            )

    def __str__(self):
        return f"Facture {self.numero_facture} - {self.boutique.nom}"
    
    def save(self, *args, **kwargs):
        # Auto-assigner la boutique si pas définie mais terminal défini
        if not self.boutique and self.terminal_maui:
            self.boutique = self.terminal_maui.boutique
        
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Vente"
        verbose_name_plural = "Ventes"
        # Le numéro de facture doit être unique par boutique
        unique_together = ['numero_facture', 'boutique']
        ordering = ['-date_vente']


class LigneVente(models.Model):
    """
    Modèle LigneVente - pas de modification majeure nécessaire
    car il hérite de la boutique via la vente.
    """
    vente = models.ForeignKey(Vente, related_name='lignes', on_delete=models.CASCADE)
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField()
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    montant_ligne = models.DecimalField(max_digits=10, decimal_places=2)

    def clean(self):
        """Validation personnalisée"""
        super().clean()
        
        # Vérifier que l'article appartient à la même boutique que la vente
        if self.article and self.vente and self.article.boutique != self.vente.boutique:
            raise ValidationError(
                "L'article doit appartenir à la même boutique que la vente."
            )

    def save(self, *args, **kwargs):
        self.montant_ligne = self.quantite * self.prix_unitaire
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.article.nom} - {self.quantite} x {self.prix_unitaire}"

    class Meta:
        verbose_name = "Ligne de vente"
        verbose_name_plural = "Lignes de vente"


class MouvementStock(models.Model):
    """
    Modèle MouvementStock modifié pour inclure la boutique.
    """
    TYPES = [
        ('VENTE', 'Vente'),
        ('ACHAT', 'Achat'),
        ('AJUSTEMENT', 'Ajustement'),
        ('RETOUR', 'Retour client'),
        ('PERTE', 'Perte/Casse'),
        ('TRANSFERT', 'Transfert')
    ]
    
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='mouvements')
    
    # Nouvelle liaison vers boutique (déduite de l'article mais utile pour les requêtes)
    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name='mouvements_stock',
                               help_text="Boutique concernée par ce mouvement")
    
    type_mouvement = models.CharField(max_length=20, choices=TYPES)
    quantite = models.IntegerField()  # Peut être négatif pour les sorties
    stock_avant = models.IntegerField()
    stock_apres = models.IntegerField()
    date_mouvement = models.DateTimeField(auto_now_add=True)
    reference = models.CharField(max_length=50, blank=True)  # Numéro de facture, bon de commande, etc.
    note = models.TextField(blank=True)
    utilisateur = models.CharField(max_length=100, blank=True)
    
    # Liaison optionnelle vers la vente (si le mouvement est lié à une vente)
    vente = models.ForeignKey(Vente, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='mouvements_stock')
    
    def clean(self):
        """Validation personnalisée"""
        super().clean()
        
        # Vérifier que la boutique correspond à celle de l'article
        if self.article and self.article.boutique != self.boutique:
            raise ValidationError(
                "La boutique du mouvement doit correspondre à celle de l'article."
            )
    
    def save(self, *args, **kwargs):
        # Auto-assigner la boutique si pas définie
        if not self.boutique and self.article:
            self.boutique = self.article.boutique
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.get_type_mouvement_display()} de {abs(self.quantite)} {self.article.nom} - {self.boutique.nom}"
    
    class Meta:
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        ordering = ['-date_mouvement']
        indexes = [
            models.Index(fields=['boutique']),
            models.Index(fields=['article']),
            models.Index(fields=['date_mouvement']),
            models.Index(fields=['type_mouvement']),
        ]


class ScanRecent(models.Model):
    """
    Modèle ScanRecent modifié pour inclure la boutique.
    """
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    
    # Nouvelle liaison vers boutique
    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name='scans_recents',
                               help_text="Boutique où le scan a été effectué")
    
    # Liaison optionnelle vers le terminal
    terminal_maui = models.ForeignKey(TerminalMaui, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='scans_recents')
    
    date_scan = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        # Auto-assigner la boutique si pas définie
        if not self.boutique and self.article:
            self.boutique = self.article.boutique
        
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = 'Scan récent'
        verbose_name_plural = 'Scans récents'
        ordering = ['-date_scan']
        indexes = [
            models.Index(fields=['boutique']),
            models.Index(fields=['date_scan']),
        ]
