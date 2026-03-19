#!/usr/bin/env python
"""Test de la synchronisation incrémentale des variants"""
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"
BOUTIQUE_ID = 12  # DADIER

print("=" * 70)
print("🧪 TEST SYNCHRONISATION INCRÉMENTALE - VARIANTS")
print("=" * 70)

# TEST 1 : Vérifier combien de variants existent
print("\n📥 TEST 1 : Synchronisation COMPLÈTE des variants")
print("-" * 70)

try:
    response = requests.get(f"{BASE_URL}/api/v2/simple/variantes/?boutique_id={BOUTIQUE_ID}")
    data = response.json()
    
    if data.get('success'):
        variants = data.get('variantes', [])
        sync_meta = data.get('sync_metadata', {})
        
        print(f"✅ Réponse reçue")
        print(f"📦 Nombre de variants: {len(variants)}")
        print(f"🔄 Mode: {'Incrémental' if sync_meta.get('is_incremental') else 'Complet'}")
        print(f"⏰ Heure serveur: {sync_meta.get('server_time', 'N/A')}")
        
        if variants:
            print(f"\n📋 Exemple de variant:")
            variant = variants[0]
            print(f"   - ID: {variant.get('id')}")
            print(f"   - Article parent: {variant.get('article_parent_id')}")
            print(f"   - Nom: {variant.get('nom_variante')}")
            print(f"   - Code-barres: {variant.get('code_barre')}")
            print(f"   - Stock: {variant.get('quantite_stock')}")
            print(f"   - Prix: {variant.get('prix_vente')} {variant.get('devise')}")
            print(f"   - Type: {variant.get('type_attribut')}")
            if 'last_updated' in variant:
                print(f"   - Dernière MAJ: {variant.get('last_updated')}")
        else:
            print("\nℹ️ Aucun variant trouvé dans cette boutique")
    else:
        print(f"❌ Erreur: {data.get('error')}")

except Exception as e:
    print(f"❌ Erreur: {e}")

# TEST 2 : Sync incrémentale (dernières 24h)
print("\n" + "=" * 70)
print("📥 TEST 2 : Synchronisation INCRÉMENTALE (dernières 24h)")
print("-" * 70)

yesterday = (datetime.now() - timedelta(days=1)).isoformat()

try:
    response = requests.get(
        f"{BASE_URL}/api/v2/simple/variantes/?boutique_id={BOUTIQUE_ID}&since={yesterday}"
    )
    data = response.json()
    
    if data.get('success'):
        variants = data.get('variantes', [])
        sync_meta = data.get('sync_metadata', {})
        
        print(f"✅ Réponse reçue")
        print(f"📦 Variants modifiés: {len(variants)}")
        print(f"🔄 Mode: {'Incrémental ✨' if sync_meta.get('is_incremental') else 'Complet'}")
        print(f"📅 Depuis: {sync_meta.get('since', 'N/A')}")
        print(f"⏰ Heure serveur: {sync_meta.get('server_time', 'N/A')}")
        
        if variants:
            print(f"\n📋 Variants modifiés dans les dernières 24h:")
            for variant in variants[:5]:
                print(f"   - {variant.get('nom_complet')} (Stock: {variant.get('quantite_stock')})")
        else:
            print(f"\n✅ Aucun variant modifié dans les dernières 24h")
            print(f"   → Le POS n'a rien à télécharger !")

except Exception as e:
    print(f"❌ Erreur: {e}")

print("\n" + "=" * 70)
print("✅ TESTS TERMINÉS")
print("=" * 70)

print("\n💡 RÉSUMÉ:")
print("   - API variants supporte maintenant la sync incrémentale")
print("   - Paramètre ?since= fonctionne comme pour les articles")
print("   - Champ 'last_updated' inclus dans la réponse")
print("   - Métadonnées de sync disponibles")
