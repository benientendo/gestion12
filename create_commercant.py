#!/usr/bin/env python
"""
Script pour créer un commerçant par défaut
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from django.contrib.auth.models import User
from inventory.models_multi_commercants import Commercant, Boutique

def create_default_commercant():
    """Créer un commerçant par défaut pour l'utilisateur admin"""
    
    try:
        # Récupérer l'utilisateur admin (ou le premier utilisateur)
        user = User.objects.first()
        if not user:
            print("❌ Aucun utilisateur trouvé!")
            return False
        
        print(f"👤 Utilisateur trouvé: {user.username}")
        
        # Vérifier si un commerçant existe déjà
        commercant, created = Commercant.objects.get_or_create(
            utilisateur=user,
            defaults={
                'nom_entreprise': 'Entreprise par défaut',
                'nom_responsable': f'{user.first_name} {user.last_name}' or user.username,
                'email': user.email or 'admin@example.com',
                'telephone': '',
                'adresse': '',
                'est_actif': True,
                'limite_boutiques': 10,
            }
        )
        
        if created:
            print(f"✅ Commerçant créé: {commercant.nom_entreprise}")
        else:
            print(f"ℹ️  Commerçant existe déjà: {commercant.nom_entreprise}")
        
        # Vérifier si une boutique par défaut existe
        try:
            boutique = Boutique.objects.get(commercant=commercant, nom='Boutique par défaut')
            created = False
            print(f"ℹ️  Boutique existe déjà: {boutique.nom}")
        except Boutique.DoesNotExist:
            # Créer directement avec SQL pour éviter les problèmes de modèle
            from django.db import connection
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO inventory_boutique 
                (nom, description, type_commerce, adresse, ville, quartier, telephone, 
                 code_boutique, cle_api_boutique, est_active, devise, date_creation, 
                 date_mise_a_jour, commercant_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), ?)
            """, [
                'Boutique par défaut',
                'Boutique créée automatiquement', 
                'BOUTIQUE',
                '',
                '',
                '',
                '',
                'BOUT_001',
                'default-api-key',
                True,
                'CDF',
                commercant.id
            ])
            created = True
            print("✅ Boutique créée via SQL")
        
        print(f"📊 Total commerçants: {Commercant.objects.count()}")
        print(f"📊 Total boutiques: {Boutique.objects.count()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

if __name__ == "__main__":
    success = create_default_commercant()
    sys.exit(0 if success else 1)
