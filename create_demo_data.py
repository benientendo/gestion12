#!/usr/bin/env python
"""
Script de démonstration pour créer des données de test
pour l'architecture multi-commerçants.
"""

import os
import sys
import django
from django.contrib.auth.models import User

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Commercant, Boutique, Client, Article, Categorie, Vente, LigneVente
from django.db import transaction
from decimal import Decimal
import random

def create_demo_data():
    """Créer des données de démonstration."""
    
    print("🚀 Création des données de démonstration...")
    
    try:
        with transaction.atomic():
            # 1. Créer un super administrateur
            admin_user, created = User.objects.get_or_create(
                username='admin',
                defaults={
                    'email': 'admin@example.com',
                    'first_name': 'Super',
                    'last_name': 'Admin',
                    'is_staff': True,
                    'is_superuser': True
                }
            )
            if created:
                admin_user.set_password('admin123')
                admin_user.save()
                print(f"✅ Super administrateur créé: {admin_user.username}")
            else:
                print(f"ℹ️  Super administrateur existe déjà: {admin_user.username}")
            
            # 2. Créer des commerçants
            commercants_data = [
                {
                    'username': 'pharmacien1',
                    'password': 'pharma123',
                    'first_name': 'Jean',
                    'last_name': 'Dupont',
                    'email': 'jean.dupont@pharma.com',
                    'nom_entreprise': 'Pharmacies Dupont',
                    'siret': '12345678901234',
                    'adresse_siege': '123 Rue de la Santé, 75001 Paris',
                    'telephone': '01.23.45.67.89',
                    'email_contact': 'contact@pharmacies-dupont.fr',
                    'max_boutiques': 3
                },
                {
                    'username': 'commercant2',
                    'password': 'commerce123',
                    'first_name': 'Marie',
                    'last_name': 'Martin',
                    'email': 'marie.martin@commerce.com',
                    'nom_entreprise': 'Commerces Martin',
                    'siret': '98765432109876',
                    'adresse_siege': '456 Avenue du Commerce, 69000 Lyon',
                    'telephone': '04.56.78.90.12',
                    'email_contact': 'contact@commerces-martin.fr',
                    'max_boutiques': 5
                }
            ]
            
            for data in commercants_data:
                # Créer l'utilisateur
                user, created = User.objects.get_or_create(
                    username=data['username'],
                    defaults={
                        'email': data['email'],
                        'first_name': data['first_name'],
                        'last_name': data['last_name']
                    }
                )
                if created:
                    user.set_password(data['password'])
                    user.save()
                
                # Créer le commerçant
                commercant, created = Commercant.objects.get_or_create(
                    user=user,
                    defaults={
                        'nom_entreprise': data['nom_entreprise'],
                        'siret': data['siret'],
                        'adresse_siege': data['adresse_siege'],
                        'telephone': data['telephone'],
                        'email_contact': data['email_contact'],
                        'max_boutiques': data['max_boutiques']
                    }
                )
                if created:
                    print(f"✅ Commerçant créé: {commercant.nom_entreprise}")
                else:
                    print(f"ℹ️  Commerçant existe déjà: {commercant.nom_entreprise}")
            
            # 3. Créer des boutiques
            commercant1 = Commercant.objects.get(nom_entreprise='Pharmacies Dupont')
            commercant2 = Commercant.objects.get(nom_entreprise='Commerces Martin')
            
            boutiques_data = [
                # Boutiques du pharmacien
                {
                    'commercant': commercant1,
                    'nom': 'Pharmacie Centrale',
                    'type_commerce': 'PHARMACIE',
                    'adresse': '10 Place de la République',
                    'ville': 'Paris',
                    'code_postal': '75011',
                    'telephone': '01.23.45.67.90'
                },
                {
                    'commercant': commercant1,
                    'nom': 'Pharmacie des Halles',
                    'type_commerce': 'PHARMACIE',
                    'adresse': '25 Rue des Halles',
                    'ville': 'Paris',
                    'code_postal': '75001',
                    'telephone': '01.23.45.67.91'
                },
                # Boutiques du commerçant
                {
                    'commercant': commercant2,
                    'nom': 'Alimentation du Coin',
                    'type_commerce': 'ALIMENTATION',
                    'adresse': '15 Rue de la Paix',
                    'ville': 'Lyon',
                    'code_postal': '69001',
                    'telephone': '04.56.78.90.13'
                },
                {
                    'commercant': commercant2,
                    'nom': 'Bar Le Central',
                    'type_commerce': 'BAR',
                    'adresse': '8 Place Bellecour',
                    'ville': 'Lyon',
                    'code_postal': '69002',
                    'telephone': '04.56.78.90.14'
                },
                {
                    'commercant': commercant2,
                    'nom': 'Boulangerie Martin',
                    'type_commerce': 'BOULANGERIE',
                    'adresse': '32 Avenue de la Liberté',
                    'ville': 'Lyon',
                    'code_postal': '69003',
                    'telephone': '04.56.78.90.15'
                }
            ]
            
            boutiques_creees = []
            for data in boutiques_data:
                boutique, created = Boutique.objects.get_or_create(
                    commercant=data['commercant'],
                    nom=data['nom'],
                    defaults=data
                )
                if created:
                    print(f"✅ Boutique créée: {boutique.nom}")
                    boutiques_creees.append(boutique)
                else:
                    print(f"ℹ️  Boutique existe déjà: {boutique.nom}")
                    boutiques_creees.append(boutique)
            
            # 4. Créer des clients MAUI pour certaines boutiques
            for i, boutique in enumerate(boutiques_creees[:3]):  # Seulement les 3 premières
                client, created = Client.objects.get_or_create(
                    boutique=boutique,
                    defaults={
                        'nom_terminal': f'Terminal {boutique.nom}',
                        'description': f'Terminal MAUI pour {boutique.nom}',
                        'numero_serie': f'MAUI{1000 + i}',
                        'version_app_minimale': '1.0.0',
                        'notes': f'Client MAUI configuré pour {boutique.nom}'
                    }
                )
                if created:
                    print(f"✅ Client MAUI créé: {client.nom_terminal}")
            
            # 5. Créer des catégories pour chaque boutique
            categories_par_type = {
                'PHARMACIE': ['Médicaments', 'Parapharmacie', 'Hygiène', 'Cosmétiques'],
                'ALIMENTATION': ['Fruits & Légumes', 'Épicerie', 'Boissons', 'Surgelés'],
                'BAR': ['Boissons chaudes', 'Boissons froides', 'Snacks', 'Alcools'],
                'BOULANGERIE': ['Pains', 'Viennoiseries', 'Pâtisseries', 'Sandwichs']
            }
            
            for boutique in boutiques_creees:
                categories_noms = categories_par_type.get(boutique.type_commerce, ['Général'])
                for nom_cat in categories_noms:
                    categorie, created = Categorie.objects.get_or_create(
                        boutique=boutique,
                        nom=nom_cat,
                        defaults={
                            'description': f'Catégorie {nom_cat} pour {boutique.nom}'
                        }
                    )
                    if created:
                        print(f"✅ Catégorie créée: {nom_cat} ({boutique.nom})")
            
            # 6. Créer des articles pour chaque boutique
            articles_par_type = {
                'PHARMACIE': [
                    ('DOLIPRANE500', 'Doliprane 500mg', 8.50, 6.20),
                    ('ASPIR100', 'Aspirine 100mg', 3.20, 2.10),
                    ('VITC1000', 'Vitamine C 1000mg', 12.90, 8.50),
                    ('SERUM250', 'Sérum physiologique', 4.50, 2.80)
                ],
                'ALIMENTATION': [
                    ('POMME1KG', 'Pommes 1kg', 2.50, 1.20),
                    ('PAIN500G', 'Pain de mie 500g', 1.80, 0.90),
                    ('LAIT1L', 'Lait entier 1L', 1.20, 0.80),
                    ('YAOURT8', 'Yaourts nature x8', 3.20, 2.10)
                ],
                'BAR': [
                    ('CAFE', 'Café expresso', 1.50, 0.30),
                    ('COCA33', 'Coca-Cola 33cl', 2.50, 1.20),
                    ('BIERE25', 'Bière pression 25cl', 3.50, 1.80),
                    ('SANDWICH', 'Sandwich jambon-beurre', 4.50, 2.20)
                ],
                'BOULANGERIE': [
                    ('BAGUETTE', 'Baguette tradition', 1.20, 0.60),
                    ('CROISSANT', 'Croissant au beurre', 1.10, 0.55),
                    ('ECLAIR', 'Éclair au chocolat', 2.80, 1.40),
                    ('TARTE6P', 'Tarte aux pommes 6 parts', 18.50, 12.00)
                ]
            }
            
            for boutique in boutiques_creees:
                articles_data = articles_par_type.get(boutique.type_commerce, [])
                categories_boutique = list(boutique.categories.all())
                
                for code, nom, prix_vente, prix_achat in articles_data:
                    categorie = random.choice(categories_boutique) if categories_boutique else None
                    article, created = Article.objects.get_or_create(
                        boutique=boutique,
                        code=code,
                        defaults={
                            'nom': nom,
                            'prix_vente': Decimal(str(prix_vente)),
                            'prix_achat': Decimal(str(prix_achat)),
                            'categorie': categorie,
                            'quantite_stock': random.randint(10, 100),
                            'description': f'{nom} - {boutique.nom}'
                        }
                    )
                    if created:
                        print(f"✅ Article créé: {nom} ({boutique.nom})")
            
            print("\n🎉 Données de démonstration créées avec succès!")
            print("\n📋 Comptes créés:")
            print("   👑 Super Admin: admin / admin123")
            print("   💊 Pharmacien: pharmacien1 / pharma123")
            print("   🏪 Commerçant: commercant2 / commerce123")
            print("\n🏪 Boutiques créées:")
            for boutique in boutiques_creees:
                print(f"   • {boutique.nom} ({boutique.get_type_commerce_display()}) - {boutique.commercant.nom_entreprise}")
            
            print(f"\n📊 Statistiques:")
            print(f"   • {User.objects.count()} utilisateurs")
            print(f"   • {Commercant.objects.count()} commerçants")
            print(f"   • {Boutique.objects.count()} boutiques")
            print(f"   • {Client.objects.count()} clients MAUI")
            print(f"   • {Categorie.objects.count()} catégories")
            print(f"   • {Article.objects.count()} articles")
            
    except Exception as e:
        print(f"❌ Erreur lors de la création des données: {e}")
        raise

if __name__ == '__main__':
    create_demo_data()
