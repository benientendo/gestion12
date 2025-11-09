"""
Script de diagnostic pour verifier les ventes dans Django
A executer depuis: C:/Users/PC/Documents/GestionMagazin/
Commande: python verifier_ventes_backend.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Vente, Boutique, Client
from django.utils import timezone
from datetime import timedelta

print("=" * 60)
print("🔍 DIAGNOSTIC - VENTES REÇUES PAR DJANGO")
print("=" * 60)

# Compter toutes les ventes
total_ventes = Vente.objects.all().count()
print(f"\n📊 Total ventes en base: {total_ventes}")

# Ventes récentes (dernières 24h)
depuis_24h = timezone.now() - timedelta(hours=24)
ventes_recentes = Vente.objects.filter(date_vente__gte=depuis_24h)
print(f"📅 Ventes dernières 24h: {ventes_recentes.count()}")

# Afficher les dernières ventes
print("\n" + "=" * 60)
print("🔴 DERNIÈRES 10 VENTES")
print("=" * 60)

for vente in Vente.objects.all().order_by('-date_vente')[:10]:
    print(f"\n📝 Vente #{vente.id}")
    print(f"   📅 Date: {vente.date_vente}")
    print(f"   💰 Total: {vente.montant_total} CDF")
    print(f"   📦 Facture: {vente.numero_facture}")
    
    # Vérifier l'association boutique
    if vente.boutique:
        print(f"   🏪 Boutique: {vente.boutique.nom} (ID: {vente.boutique.id})")
    else:
        print(f"   🏪 Boutique: ❌ AUCUNE - PROBLÈME TROUVÉ!")
    
    # Vérifier l'association terminal
    if vente.client_maui:
        print(f"   📱 Terminal: {vente.client_maui.nom_terminal} ({vente.client_maui.numero_serie})")
    else:
        print(f"   📱 Terminal: ❌ AUCUN - PROBLÈME TROUVÉ!")
    
    # Articles
    lignes = vente.lignes.all()
    print(f"   📦 Articles: {lignes.count()}")
    for ligne in lignes:
        print(f"      └─ {ligne.article.nom}: {ligne.quantite} x {ligne.prix_unitaire} CDF")

# Vérifier les boutiques
print("\n" + "=" * 60)
print("🏪 BOUTIQUES ENREGISTRÉES")
print("=" * 60)

for boutique in Boutique.objects.all():
    ventes_boutique = Vente.objects.filter(boutique=boutique).count()
    print(f"\n🏪 {boutique.nom} (ID: {boutique.id})")
    print(f"   📊 Ventes associées: {ventes_boutique}")
    if hasattr(boutique, 'commercant'):
        print(f"   👤 Commerçant: {boutique.commercant.user.username}")
    print(f"   📍 Adresse: {boutique.adresse if hasattr(boutique, 'adresse') else 'N/A'}")

# Vérifier les terminaux
print("\n" + "=" * 60)
print("📱 TERMINAUX ENREGISTRÉS")
print("=" * 60)

for terminal in Client.objects.all():
    ventes_terminal = Vente.objects.filter(client_maui=terminal).count()
    print(f"\n📱 {terminal.nom_terminal}")
    print(f"   🔢 Numéro série: {terminal.numero_serie}")
    print(f"   🏪 Boutique: {terminal.boutique.nom if terminal.boutique else '❌ AUCUNE'}")
    print(f"   📊 Ventes associées: {ventes_terminal}")
    print(f"   ✅ Actif: {terminal.est_actif}")

# Ventes orphelines (sans boutique)
ventes_orphelines = Vente.objects.filter(boutique__isnull=True).count()
print(f"\n" + "=" * 60)
print(f"⚠️ VENTES ORPHELINES (sans boutique): {ventes_orphelines}")
print("=" * 60)

if ventes_orphelines > 0:
    print("\n🔴 DÉTAILS DES VENTES ORPHELINES:")
    for vente in Vente.objects.filter(boutique__isnull=True)[:5]:
        print(f"\n   - Vente #{vente.id}")
        print(f"     Date: {vente.date_vente}")
        print(f"     Total: {vente.montant_total} CDF")
        print(f"     Facture: {vente.numero_facture}")
        print(f"     Terminal: {vente.client_maui.numero_serie if vente.client_maui else 'AUCUN'}")

# Ventes sans terminal
ventes_sans_terminal = Vente.objects.filter(client_maui__isnull=True).count()
print(f"\n⚠️ VENTES SANS TERMINAL: {ventes_sans_terminal}")

if ventes_sans_terminal > 0:
    print("\n🔴 DÉTAILS DES VENTES SANS TERMINAL:")
    for vente in Vente.objects.filter(client_maui__isnull=True)[:5]:
        print(f"\n   - Vente #{vente.id}")
        print(f"     Date: {vente.date_vente}")
        print(f"     Total: {vente.montant_total} CDF")
        print(f"     Facture: {vente.numero_facture}")
        print(f"     Boutique: {vente.boutique.nom if vente.boutique else 'AUCUNE'}")

print("\n" + "=" * 60)
print("✅ DIAGNOSTIC TERMINÉ")
print("=" * 60)
print("\n💡 INTERPRÉTATION DES RÉSULTATS:")
print("   1. Si 'Ventes orphelines' > 0 → Problème d'association boutique")
print("   2. Si 'Ventes sans terminal' > 0 → Problème d'association terminal")
print("   3. Si total ventes = 0 → Les ventes n'arrivent pas à Django")
print("   4. Si ventes dans mauvaise boutique → Problème de terminal")
print("\n📄 Consultez DIAGNOSTIC_BACKEND_VENTES.md pour les solutions")
