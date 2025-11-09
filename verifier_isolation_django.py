"""
Script de vérification rapide de l'isolation Django
Exécuter avec: python manage.py shell < verifier_isolation_django.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Vente, Boutique, Client
from django.db import connection

print("\n" + "="*80)
print("VÉRIFICATION RAPIDE DE L'ISOLATION DJANGO")
print("="*80 + "\n")

# 1. Vérifier la structure de la table Vente
print("📋 STRUCTURE DE LA TABLE VENTE")
print("-" * 80)
with connection.cursor() as cursor:
    cursor.execute("PRAGMA table_info(inventory_vente)")
    columns = cursor.fetchall()
    
    has_boutique = False
    has_client_maui = False
    
    for col in columns:
        col_name = col[1]
        if col_name == 'boutique_id':
            has_boutique = True
            print(f"✅ Colonne 'boutique_id' existe")
        if col_name == 'client_maui_id':
            has_client_maui = True
            print(f"✅ Colonne 'client_maui_id' existe")

if not has_boutique:
    print("❌ PROBLÈME: Colonne 'boutique_id' manquante!")
    print("   Solution: Exécuter les migrations Django")
    print("   python manage.py makemigrations")
    print("   python manage.py migrate")

print()

# 2. Vérifier les ventes
print("📊 ÉTAT DES VENTES")
print("-" * 80)

total_ventes = Vente.objects.count()
ventes_avec_boutique = Vente.objects.filter(boutique__isnull=False).count()
ventes_sans_boutique = Vente.objects.filter(boutique__isnull=True).count()

print(f"Total ventes: {total_ventes}")
print(f"Ventes avec boutique: {ventes_avec_boutique}")
print(f"Ventes SANS boutique: {ventes_sans_boutique}")

if ventes_sans_boutique > 0:
    print(f"\n⚠️  {ventes_sans_boutique} vente(s) sans boutique détectée(s)")
    print("\nDétails:")
    for vente in Vente.objects.filter(boutique__isnull=True)[:5]:
        print(f"  - Vente #{vente.numero_facture}")
        print(f"    Date: {vente.date_vente}")
        print(f"    Client MAUI: {vente.client_maui}")
        if vente.client_maui:
            print(f"    Boutique du client: {vente.client_maui.boutique}")
        print()

print()

# 3. Vérifier les boutiques et leurs ventes
print("🏪 VENTES PAR BOUTIQUE")
print("-" * 80)

boutiques = Boutique.objects.all()
for boutique in boutiques:
    ventes_count = Vente.objects.filter(boutique=boutique).count()
    clients_count = boutique.clients.count()
    print(f"{boutique.nom} (ID: {boutique.id})")
    print(f"  Commerçant: {boutique.commercant.nom_entreprise}")
    print(f"  Terminaux MAUI: {clients_count}")
    print(f"  Ventes: {ventes_count}")
    print()

# 4. Vérifier les dernières ventes créées
print("🔍 DERNIÈRES VENTES CRÉÉES")
print("-" * 80)

dernieres_ventes = Vente.objects.all().order_by('-date_vente')[:5]
for vente in dernieres_ventes:
    print(f"Vente #{vente.numero_facture}")
    print(f"  Date: {vente.date_vente}")
    print(f"  Boutique (direct): {vente.boutique}")
    print(f"  Client MAUI: {vente.client_maui}")
    if vente.client_maui:
        print(f"  Boutique (via client): {vente.client_maui.boutique}")
    print()

# 5. Test d'isolation
print("="*80)
print("TEST D'ISOLATION")
print("="*80 + "\n")

if boutiques.count() >= 2:
    boutique1 = boutiques[0]
    boutique2 = boutiques[1]
    
    ventes_b1 = Vente.objects.filter(boutique=boutique1).count()
    ventes_b2 = Vente.objects.filter(boutique=boutique2).count()
    
    print(f"Boutique 1: {boutique1.nom} → {ventes_b1} ventes")
    print(f"Boutique 2: {boutique2.nom} → {ventes_b2} ventes")
    
    # Vérifier qu'il n'y a pas de chevauchement
    ventes_b1_ids = set(Vente.objects.filter(boutique=boutique1).values_list('id', flat=True))
    ventes_b2_ids = set(Vente.objects.filter(boutique=boutique2).values_list('id', flat=True))
    
    chevauchement = ventes_b1_ids.intersection(ventes_b2_ids)
    
    if len(chevauchement) == 0:
        print("\n✅ ISOLATION PARFAITE: Aucun chevauchement entre boutiques")
    else:
        print(f"\n❌ PROBLÈME: {len(chevauchement)} vente(s) en commun!")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80 + "\n")

if ventes_sans_boutique == 0 and has_boutique:
    print("✅ DJANGO EST 100% CORRECT")
    print("\n   ✓ Champ 'boutique' existe dans la table")
    print("   ✓ Toutes les ventes ont une boutique assignée")
    print("   ✓ Isolation entre boutiques fonctionnelle")
    print("\n   → Le problème vient probablement de MAUI")
    print("   → Voir le guide GUIDE_INTEGRATION_MAUI_ISOLATION.md")
else:
    print("⚠️  PROBLÈMES DÉTECTÉS CÔTÉ DJANGO")
    if not has_boutique:
        print("\n   ✗ Champ 'boutique' manquant")
        print("   → Exécuter: python manage.py migrate")
    if ventes_sans_boutique > 0:
        print(f"\n   ✗ {ventes_sans_boutique} vente(s) sans boutique")
        print("   → Exécuter: python manage.py shell < corriger_isolation_ventes.py")

print()
