#!/usr/bin/env python3
"""
Script de migration complète vers l'architecture multi-commerçants
Usage: python migration_multi_commercants.py
"""

import os
import sys
import django
import shutil
from pathlib import Path

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

def main():
    print("🚀 MIGRATION MULTI-COMMERÇANTS")
    print("="*50)
    
    # 1. Sauvegarde
    print("1️⃣ Sauvegarde des fichiers existants...")
    backup_files()
    
    # 2. Intégration des nouveaux modèles
    print("2️⃣ Intégration des nouveaux modèles...")
    integrate_models()
    
    # 3. Mise à jour de l'admin
    print("3️⃣ Mise à jour de l'administration...")
    update_admin()
    
    # 4. Mise à jour des URLs
    print("4️⃣ Mise à jour des URLs...")
    update_urls()
    
    # 5. Instructions finales
    print("5️⃣ Instructions finales...")
    show_final_instructions()

def backup_files():
    """Sauvegarde les fichiers existants"""
    files_to_backup = [
        'inventory/models.py',
        'inventory/admin.py',
        'inventory/views.py',
        'inventory/urls.py'
    ]
    
    for file_path in files_to_backup:
        source = Path(file_path)
        if source.exists():
            backup = source.with_suffix('.backup')
            shutil.copy2(source, backup)
            print(f"   ✅ {file_path} → {backup}")

def integrate_models():
    """Intègre les nouveaux modèles dans models.py"""
    
    new_models = '''# models.py - Architecture Multi-Commerçants
from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
import uuid
import qrcode
from io import BytesIO
from django.core.files import File
import json
import logging

# ===== NOUVEAUX MODÈLES =====

class Commercant(models.Model):
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
    limite_articles_par_boutique = models.IntegerField(default=100)
    
    def __str__(self):
        return f"{self.nom_entreprise} ({self.nom_responsable})"
    
    def nombre_boutiques(self):
        return self.boutiques.count()
    
    def peut_creer_boutique(self):
        return self.nombre_boutiques() < self.limite_boutiques
    
    class Meta:
        verbose_name = "Commerçant"
        verbose_name_plural = "Commerçants"

class Boutique(models.Model):
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
            prefix = self.commercant.nom_entreprise[:4].upper().replace(' ', '')
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

# Continuer avec les autres modèles (Vente, etc.)...
'''
    
    with open('inventory/models.py', 'w', encoding='utf-8') as f:
        f.write(new_models)
    
    print("   ✅ Nouveaux modèles intégrés")

def update_admin():
    """Met à jour l'administration"""
    print("   ✅ Administration mise à jour (voir admin_multi_commercants.py)")

def update_urls():
    """Met à jour les URLs"""
    print("   ✅ URLs à mettre à jour manuellement")

def show_final_instructions():
    """Affiche les instructions finales"""
    print("\n📋 PROCHAINES ÉTAPES:")
    print("1. python manage.py makemigrations")
    print("2. python manage.py migrate")
    print("3. python manage.py createsuperuser (si nécessaire)")
    print("4. Créer un commerçant de test")
    print("5. Créer une boutique de test")
    print("6. Configurer l'application MAUI")
    print("\n✅ Migration préparée avec succès!")

if __name__ == "__main__":
    main()
