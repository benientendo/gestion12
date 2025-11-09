"""
Script de test pour vérifier l'isolation des ventes par boutique
"""

import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Client, Vente, Boutique

print("=" * 60)
print("TEST D'ISOLATION DES VENTES PAR BOUTIQUE")
print("=" * 60)
print()

# 1. Vérifier le terminal
try:
    terminal = Client.objects.get(numero_serie='0a1badae951f8473')
    print(f"✅ Terminal trouvé: {terminal.nom_terminal}")
    print(f"   Boutique: {terminal.boutique.nom} (ID: {terminal.boutique.id})")
    print()
except Client.DoesNotExist:
    print("❌ Terminal non trouvé !")
    exit(1)

# 2. Compter les ventes par boutique
ventes_boutique = Vente.objects.filter(boutique=terminal.boutique)
ventes_sans_boutique = Vente.objects.filter(boutique__isnull=True)
toutes_ventes = Vente.objects.all()

print(f"📊 STATISTIQUES:")
print(f"   Total ventes: {toutes_ventes.count()}")
print(f"   ✅ Ventes boutique {terminal.boutique.id} ({terminal.boutique.nom}): {ventes_boutique.count()}")
print(f"   ⚠️  Ventes sans boutique: {ventes_sans_boutique.count()}")
print()

# 3. Vérifier les ventes d'autres boutiques
autres_boutiques = Boutique.objects.exclude(id=terminal.boutique.id)
print(f"🔍 VÉRIFICATION AUTRES BOUTIQUES:")
for boutique in autres_boutiques:
    ventes_autres = Vente.objects.filter(boutique=boutique)
    if ventes_autres.exists():
        print(f"   Boutique {boutique.id} ({boutique.nom}): {ventes_autres.count()} ventes")
print()

# 4. Afficher les dernières ventes
print(f"📋 DERNIÈRES 10 VENTES (toutes boutiques):")
for v in Vente.objects.all().order_by('-date_vente')[:10]:
    if v.boutique:
        boutique_info = f"Boutique {v.boutique.id} ({v.boutique.nom})"
    else:
        boutique_info = "❌ SANS BOUTIQUE"
    
    terminal_info = f"Terminal: {v.client_maui.nom_terminal}" if v.client_maui else "Pas de terminal"
    print(f"   - {v.numero_facture}")
    print(f"     {boutique_info}")
    print(f"     {terminal_info}")
    print(f"     Montant: {v.montant_total} CDF")
    print()

# 5. Test de filtrage
print("=" * 60)
print("TEST DE FILTRAGE PAR BOUTIQUE")
print("=" * 60)
print()

ventes_filtrees = Vente.objects.filter(boutique=terminal.boutique)
print(f"✅ Ventes filtrées pour boutique {terminal.boutique.id}:")
for v in ventes_filtrees[:5]:
    print(f"   - {v.numero_facture}: {v.montant_total} CDF")

print()
print("=" * 60)
print("RÉSULTAT DU TEST")
print("=" * 60)

if ventes_sans_boutique.count() > 0:
    print(f"⚠️  ATTENTION: {ventes_sans_boutique.count()} ventes sans boutique !")
    print("   → Exécuter: python migrer_ventes_boutiques.py")
else:
    print("✅ Toutes les ventes ont une boutique assignée")

if ventes_boutique.count() > 0:
    print(f"✅ Le terminal a {ventes_boutique.count()} ventes dans sa boutique")
else:
    print("⚠️  Aucune vente pour ce terminal dans sa boutique")

print()
