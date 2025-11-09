"""
Script de diagnostic pour identifier le problème d'isolation des ventes
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Boutique, Vente, Client, Commercant
from django.contrib.auth.models import User

print("\n" + "="*80)
print("DIAGNOSTIC - ISOLATION DES VENTES PAR BOUTIQUE")
print("="*80 + "\n")

# Trouver le commerçant
try:
    commercant = Commercant.objects.first()
    print(f"✅ Commerçant trouvé: {commercant.nom_entreprise}")
    print(f"   Nombre de boutiques: {commercant.boutiques.count()}\n")
except:
    print("❌ Aucun commerçant trouvé\n")
    exit()

# Analyser chaque boutique
print("="*80)
print("ANALYSE PAR BOUTIQUE")
print("="*80 + "\n")

boutiques = commercant.boutiques.all()
for boutique in boutiques:
    print(f"🏪 Boutique: {boutique.nom} (ID: {boutique.id})")
    print("-" * 60)
    
    # Terminaux MAUI
    terminaux = boutique.clients.all()
    print(f"   📱 Terminaux MAUI: {terminaux.count()}")
    for terminal in terminaux:
        print(f"      - {terminal.nom_terminal}")
        print(f"        Numéro série: {terminal.numero_serie}")
        print(f"        Actif: {terminal.est_actif}")
    
    if terminaux.count() == 0:
        print("      ⚠️  Aucun terminal MAUI lié")
    
    # Ventes via champ boutique
    ventes_directes = Vente.objects.filter(boutique=boutique)
    print(f"\n   💰 Ventes (via champ boutique): {ventes_directes.count()}")
    
    # Ventes via client_maui
    ventes_via_client = Vente.objects.filter(client_maui__boutique=boutique)
    print(f"   💰 Ventes (via client_maui.boutique): {ventes_via_client.count()}")
    
    # Afficher les détails des ventes
    if ventes_directes.count() > 0:
        print(f"\n   Détails des ventes:")
        for vente in ventes_directes[:5]:
            print(f"      - Vente #{vente.numero_facture}")
            print(f"        Date: {vente.date_vente}")
            print(f"        Montant: {vente.montant_total} CDF")
            print(f"        Boutique (champ): {vente.boutique.nom if vente.boutique else 'AUCUNE'}")
            print(f"        Client MAUI: {vente.client_maui.nom_terminal if vente.client_maui else 'AUCUN'}")
            if vente.client_maui and vente.client_maui.boutique:
                print(f"        Boutique (via client): {vente.client_maui.boutique.nom}")
            print()
    
    print()

# Vérifier les ventes sans boutique
print("="*80)
print("VENTES SANS BOUTIQUE ASSIGNÉE")
print("="*80 + "\n")

ventes_sans_boutique = Vente.objects.filter(boutique__isnull=True)
print(f"Total: {ventes_sans_boutique.count()}")

if ventes_sans_boutique.count() > 0:
    print("\n⚠️  PROBLÈME DÉTECTÉ: Ventes sans boutique\n")
    for vente in ventes_sans_boutique:
        print(f"   - Vente #{vente.numero_facture}")
        print(f"     Date: {vente.date_vente}")
        print(f"     Client MAUI: {vente.client_maui.nom_terminal if vente.client_maui else 'AUCUN'}")
        if vente.client_maui and vente.client_maui.boutique:
            print(f"     Boutique du client: {vente.client_maui.boutique.nom}")
        print()

# Test d'isolation
print("="*80)
print("TEST D'ISOLATION")
print("="*80 + "\n")

if boutiques.count() >= 2:
    boutique1 = boutiques[0]
    boutique2 = boutiques[1]
    
    ventes_b1 = Vente.objects.filter(boutique=boutique1)
    ventes_b2 = Vente.objects.filter(boutique=boutique2)
    
    print(f"Boutique 1: {boutique1.nom}")
    print(f"  Ventes: {ventes_b1.count()}")
    
    print(f"\nBoutique 2: {boutique2.nom}")
    print(f"  Ventes: {ventes_b2.count()}")
    
    # Vérifier chevauchement
    ids_b1 = set(ventes_b1.values_list('id', flat=True))
    ids_b2 = set(ventes_b2.values_list('id', flat=True))
    
    chevauchement = ids_b1.intersection(ids_b2)
    
    if len(chevauchement) == 0:
        print(f"\n✅ ISOLATION OK: Aucune vente en commun")
    else:
        print(f"\n❌ PROBLÈME: {len(chevauchement)} vente(s) en commun!")
        for vente_id in chevauchement:
            vente = Vente.objects.get(id=vente_id)
            print(f"   - Vente #{vente.numero_facture}")

# Vérifier les vues backend
print("\n" + "="*80)
print("TEST DES VUES BACKEND")
print("="*80 + "\n")

user = commercant.user
print(f"Utilisateur: {user.username}")

# Simuler la requête de liste_ventes
if user.is_superuser:
    ventes_visibles = Vente.objects.all()
    print("Type: Super Admin")
    print(f"Ventes visibles: {ventes_visibles.count()} (TOUTES)")
else:
    try:
        ventes_visibles = Vente.objects.filter(boutique__commercant=commercant)
        print("Type: Commerçant")
        print(f"Ventes visibles: {ventes_visibles.count()}")
        
        # Grouper par boutique
        for boutique in boutiques:
            ventes_boutique = ventes_visibles.filter(boutique=boutique)
            print(f"  - {boutique.nom}: {ventes_boutique.count()} ventes")
    except:
        ventes_visibles = Vente.objects.none()
        print("Type: Utilisateur legacy")
        print(f"Ventes visibles: 0")

print("\n" + "="*80)
print("RECOMMANDATIONS")
print("="*80 + "\n")

if ventes_sans_boutique.count() > 0:
    print("⚠️  PROBLÈME DÉTECTÉ:")
    print(f"   {ventes_sans_boutique.count()} vente(s) n'ont pas de boutique assignée.")
    print("\n   SOLUTION:")
    print("   Exécuter: python manage.py shell < corriger_isolation_ventes.py")
else:
    print("✅ Toutes les ventes ont une boutique assignée")
    print("\n   Si le problème persiste dans l'interface:")
    print("   1. Vérifier le code de la vue qui affiche les ventes")
    print("   2. Vérifier que la vue filtre bien par boutique__commercant")
    print("   3. Vider le cache du navigateur")

print()
