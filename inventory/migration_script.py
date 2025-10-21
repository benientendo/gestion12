#!/usr/bin/env python3
"""
Script de migration pour intégrer l'architecture multi-commerçants
Usage: python migration_script.py
"""

import os
import sys
import django
from pathlib import Path

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

def backup_current_models():
    """Sauvegarde le fichier models.py actuel"""
    models_file = Path(__file__).parent / 'models.py'
    backup_file = Path(__file__).parent / 'models_backup.py'
    
    if models_file.exists():
        import shutil
        shutil.copy2(models_file, backup_file)
        print(f"✅ Sauvegarde créée: {backup_file}")
    else:
        print("❌ Fichier models.py non trouvé")

def create_new_models_file():
    """Crée le nouveau fichier models.py avec l'architecture multi-commerçants"""
    
    new_models_content = '''# models.py - Architecture Multi-Commerçants
# Généré automatiquement par migration_script.py

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

# ===== NOUVEAUX MODÈLES MULTI-COMMERÇANTS =====

class Commercant(models.Model):
    """Commerçant propriétaire de boutiques"""
    nom_entreprise = models.CharField(max_length=200)
    nom_responsable = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    telephone = models.CharField(max_length=20, blank=True)
    adresse = models.TextField(blank=True)
    
    utilisateur = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profil_commercant')
    
    est_actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    
    type_abonnement = models.CharField(max_length=50, choices=[
        ('GRATUIT', 'Gratuit'),
        ('STANDARD', 'Standard'),
        ('PREMIUM', 'Premium')
    ], default='GRATUIT')
    
    limite_boutiques = models.IntegerField(default=1)
    
    def __str__(self):
        return f"{self.nom_entreprise} ({self.nom_responsable})"
    
    class Meta:
        verbose_name = "Commerçant"
        verbose_name_plural = "Commerçants"

class Boutique(models.Model):
    """Boutique appartenant à un commerçant"""
    nom = models.CharField(max_length=200)
    commercant = models.ForeignKey(Commercant, on_delete=models.CASCADE, related_name='boutiques')
    
    type_commerce = models.CharField(max_length=50, choices=[
        ('PHARMACIE', 'Pharmacie'),
        ('BAR', 'Bar/Café'),
        ('ALIMENTATION', 'Alimentation'),
        ('BOUTIQUE', 'Boutique générale'),
        ('AUTRE', 'Autre')
    ], default='BOUTIQUE')
    
    adresse = models.TextField(blank=True)
    code_boutique = models.CharField(max_length=50, unique=True)
    cle_api = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    
    est_active = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if not self.code_boutique:
            prefix = self.commercant.nom_entreprise[:4].upper()
            numero = self.commercant.boutiques.count() + 1
            self.code_boutique = f"{prefix}_BOUT_{numero:03d}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.nom} ({self.commercant.nom_entreprise})"
    
    class Meta:
        verbose_name = "Boutique"
        verbose_name_plural = "Boutiques"

# ===== MODÈLES MODIFIÉS =====

class Categorie(models.Model):
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, null=True, blank=True, related_name='categories')

    def __str__(self):
        return self.nom
    
    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"

class Article(models.Model):
    code = models.CharField(max_length=50)
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    prix_vente = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    prix_achat = models.DecimalField(max_digits=10, decimal_places=2)
    
    boutique = models.ForeignKey(Boutique, on_delete=models.CASCADE, related_name='articles')
    categorie = models.ForeignKey(Categorie, on_delete=models.SET_NULL, null=True, related_name='articles')
    
    quantite_stock = models.IntegerField(default=0)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True)
    image = models.ImageField(upload_to='articles/', blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nom} ({self.code}) - {self.boutique.nom}"

    class Meta:
        verbose_name = "Article"
        verbose_name_plural = "Articles"
        unique_together = ['code', 'boutique']

# Continuer avec les autres modèles...
# (Le script complet sera généré)
'''
    
    models_file = Path(__file__).parent / 'models_new.py'
    with open(models_file, 'w', encoding='utf-8') as f:
        f.write(new_models_content)
    
    print(f"✅ Nouveau fichier créé: {models_file}")

if __name__ == "__main__":
    print("🚀 Début de la migration multi-commerçants")
    backup_current_models()
    create_new_models_file()
    print("✅ Migration terminée")
    print("\n📋 Prochaines étapes:")
    print("1. Vérifier models_new.py")
    print("2. Remplacer models.py par models_new.py")
    print("3. Exécuter: python manage.py makemigrations")
    print("4. Exécuter: python manage.py migrate")
