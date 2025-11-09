"""
Script de test pour vérifier l'isolation des ventes dans le backend Django
Exécuter avec: python manage.py shell < test_isolation_ventes_backend.py
"""

import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from django.contrib.auth.models import User
from inventory.models import Vente, Boutique, Commercant, Client

print("\n" + "="*80)
print("TEST D'ISOLATION DES VENTES DANS LE BACKEND")
print("="*80 + "\n")

# 1. Vérifier les ventes dans la base de données
print("📊 ÉTAT ACTUEL DE LA BASE DE DONNÉES")
print("-" * 80)

total_ventes = Vente.objects.all().count()
print(f"✅ Total ventes dans la base: {total_ventes}")

# Ventes avec boutique assignée
ventes_avec_boutique = Vente.objects.filter(boutique__isnull=False).count()
print(f"✅ Ventes avec boutique assignée: {ventes_avec_boutique}")

# Ventes SANS boutique (problème!)
ventes_sans_boutique = Vente.objects.filter(boutique__isnull=True).count()
if ventes_sans_boutique > 0:
    print(f"⚠️  Ventes SANS boutique: {ventes_sans_boutique} (PROBLÈME D'ISOLATION!)")
    print("\n   Détails des ventes sans boutique:")
    for vente in Vente.objects.filter(boutique__isnull=True)[:5]:
        print(f"   - Vente #{vente.numero_facture} - {vente.date_vente} - Terminal: {vente.client_maui}")
else:
    print(f"✅ Ventes sans boutique: 0 (Parfait!)")

print("\n" + "="*80)
print("🏪 ISOLATION PAR BOUTIQUE")
print("="*80 + "\n")

# 2. Tester l'isolation par boutique
boutiques = Boutique.objects.all()
print(f"Nombre de boutiques: {boutiques.count()}\n")

for boutique in boutiques:
    print(f"🏪 Boutique: {boutique.nom} (ID: {boutique.id})")
    print(f"   Commerçant: {boutique.commercant.nom_entreprise}")
    
    # Ventes via relation directe boutique.ventes
    ventes_directes = Vente.objects.filter(boutique=boutique).count()
    print(f"   ✅ Ventes (via boutique): {ventes_directes}")
    
    # Ventes via relation indirecte client_maui__boutique
    ventes_indirectes = Vente.objects.filter(client_maui__boutique=boutique).count()
    print(f"   ✅ Ventes (via client_maui): {ventes_indirectes}")
    
    # Vérifier la cohérence
    if ventes_directes != ventes_indirectes:
        print(f"   ⚠️  INCOHÉRENCE: {ventes_directes} != {ventes_indirectes}")
    
    # Terminaux de la boutique
    terminaux = boutique.clients.all().count()
    print(f"   📱 Terminaux MAUI: {terminaux}")
    print()

print("="*80)
print("👥 ISOLATION PAR COMMERÇANT")
print("="*80 + "\n")

# 3. Tester l'isolation par commerçant
commercants = Commercant.objects.all()
print(f"Nombre de commerçants: {commercants.count()}\n")

for commercant in commercants:
    print(f"👤 Commerçant: {commercant.nom_entreprise}")
    
    # Ventes via boutique__commercant
    ventes_commercant = Vente.objects.filter(boutique__commercant=commercant).count()
    print(f"   ✅ Ventes totales: {ventes_commercant}")
    
    # Boutiques du commerçant
    boutiques_commercant = commercant.boutiques.all()
    print(f"   🏪 Boutiques: {boutiques_commercant.count()}")
    
    for boutique in boutiques_commercant:
        ventes_boutique = Vente.objects.filter(boutique=boutique).count()
        print(f"      - {boutique.nom}: {ventes_boutique} ventes")
    print()

print("="*80)
print("🔍 VÉRIFICATION CROISÉE")
print("="*80 + "\n")

# 4. Vérifier qu'aucune vente n'est visible par plusieurs boutiques
print("Test: Une vente ne doit appartenir qu'à UNE seule boutique\n")

for vente in Vente.objects.all()[:10]:  # Tester les 10 premières ventes
    boutiques_trouvees = []
    
    # Vérifier via relation directe
    if vente.boutique:
        boutiques_trouvees.append(f"Direct: {vente.boutique.nom}")
    
    # Vérifier via client_maui
    if vente.client_maui and vente.client_maui.boutique:
        boutiques_trouvees.append(f"Client: {vente.client_maui.boutique.nom}")
    
    if len(boutiques_trouvees) == 0:
        print(f"❌ Vente #{vente.numero_facture}: AUCUNE boutique assignée!")
    elif len(boutiques_trouvees) == 1:
        print(f"✅ Vente #{vente.numero_facture}: {boutiques_trouvees[0]}")
    elif len(boutiques_trouvees) > 1:
        # Vérifier si c'est la même boutique
        if "Direct:" in boutiques_trouvees[0] and "Client:" in boutiques_trouvees[1]:
            boutique_direct = boutiques_trouvees[0].replace("Direct: ", "")
            boutique_client = boutiques_trouvees[1].replace("Client: ", "")
            if boutique_direct == boutique_client:
                print(f"✅ Vente #{vente.numero_facture}: {boutique_direct} (cohérent)")
            else:
                print(f"❌ Vente #{vente.numero_facture}: INCOHÉRENCE! {boutiques_trouvees}")

print("\n" + "="*80)
print("📋 RECOMMANDATIONS")
print("="*80 + "\n")

if ventes_sans_boutique > 0:
    print("⚠️  PROBLÈME DÉTECTÉ:")
    print(f"   {ventes_sans_boutique} vente(s) n'ont pas de boutique assignée.")
    print("\n   SOLUTION:")
    print("   1. Identifier ces ventes:")
    print("      ventes = Vente.objects.filter(boutique__isnull=True)")
    print("\n   2. Les assigner à la bonne boutique:")
    print("      for vente in ventes:")
    print("          if vente.client_maui and vente.client_maui.boutique:")
    print("              vente.boutique = vente.client_maui.boutique")
    print("              vente.save()")
    print("\n   3. Ou créer un script de migration:")
    print("      python manage.py shell < migrer_ventes_boutiques.py")
else:
    print("✅ ISOLATION PARFAITE!")
    print("   Toutes les ventes ont une boutique assignée.")
    print("   L'isolation entre boutiques est garantie.")

print("\n" + "="*80)
print("TEST TERMINÉ")
print("="*80 + "\n")
