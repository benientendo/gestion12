"""
Script de correction pour associer les ventes orphelines à leur boutique
À exécuter depuis: C:\Users\PC\Documents\GestionMagazin\
Commande: python corriger_ventes_orphelines.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Vente, Client

print("=" * 60)
print("🔧 CORRECTION - VENTES ORPHELINES")
print("=" * 60)

# Trouver les ventes orphelines
ventes_orphelines = Vente.objects.filter(boutique__isnull=True)
total_orphelines = ventes_orphelines.count()

print(f"\n📊 Ventes orphelines trouvées: {total_orphelines}")

if total_orphelines == 0:
    print("✅ Aucune vente orpheline à corriger!")
    exit(0)

print("\n🔄 Tentative de correction automatique...")

corrigees = 0
non_corrigees = 0

for vente in ventes_orphelines:
    print(f"\n📝 Vente #{vente.id} - {vente.numero_facture}")
    
    # Si la vente a un terminal associé, utiliser sa boutique
    if vente.client_maui and vente.client_maui.boutique:
        vente.boutique = vente.client_maui.boutique
        vente.save(update_fields=['boutique'])
        print(f"   ✅ Corrigée → Boutique: {vente.boutique.nom}")
        corrigees += 1
    else:
        print(f"   ❌ Impossible de corriger (pas de terminal ou terminal sans boutique)")
        non_corrigees += 1

print("\n" + "=" * 60)
print("📊 RÉSULTAT DE LA CORRECTION")
print("=" * 60)
print(f"✅ Ventes corrigées: {corrigees}")
print(f"❌ Ventes non corrigées: {non_corrigees}")

if non_corrigees > 0:
    print("\n⚠️ VENTES NON CORRIGÉES:")
    for vente in Vente.objects.filter(boutique__isnull=True):
        print(f"   - Vente #{vente.id} - {vente.numero_facture}")
        print(f"     Raison: Terminal = {vente.client_maui.numero_serie if vente.client_maui else 'AUCUN'}")
        if vente.client_maui:
            print(f"     Boutique terminal = {vente.client_maui.boutique.nom if vente.client_maui.boutique else 'AUCUNE'}")

print("\n💡 PROCHAINES ÉTAPES:")
if corrigees > 0:
    print("   1. Relancer: python verifier_ventes_backend.py")
    print("   2. Vérifier que les ventes apparaissent dans l'interface")
if non_corrigees > 0:
    print("   3. Associer manuellement les terminaux à des boutiques")
    print("   4. Relancer ce script")
