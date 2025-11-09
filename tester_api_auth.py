"""
Script pour tester l'API d'authentification MAUI
Commande: python tester_api_auth.py
"""
import requests
import json

# Configuration
BASE_URL = "http://192.168.142.224:8000"
NUMERO_SERIE = "575c50cf32d00948"

print("=" * 60)
print("TEST API AUTHENTIFICATION MAUI")
print("=" * 60)

# Test 1: API v1 (ancienne) - /api/maui/auth/
print("\n1. Test API v1: /api/maui/auth/")
print("-" * 60)

url_v1 = f"{BASE_URL}/api/maui/auth/"
data_v1 = {
    "numero_serie": NUMERO_SERIE,
    "version_app": "2.0.0"
}

try:
    response = requests.post(url_v1, json=data_v1, timeout=5)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ REPONSE:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Verifier client_maui
        if 'client_maui' in result:
            if result['client_maui'] is not None:
                print(f"\n✅ client_maui present avec boutique!")
                print(f"   Boutique ID: {result['client_maui'].get('boutique_id')}")
                print(f"   Boutique Nom: {result['client_maui'].get('boutique', {}).get('nom')}")
            else:
                print(f"\n❌ client_maui est null - Terminal sans boutique")
        else:
            print(f"\n⚠️ client_maui absent de la reponse")
    else:
        print(f"❌ Erreur: {response.text}")
        
except Exception as e:
    print(f"❌ Erreur de connexion: {e}")

# Test 2: API v2 - /api/v2/auth/maui/
print("\n\n2. Test API v2: /api/v2/auth/maui/")
print("-" * 60)

url_v2 = f"{BASE_URL}/api/v2/auth/maui/"
data_v2 = {
    "numero_serie": NUMERO_SERIE,
    "version_app": "2.0.0"
}

try:
    response = requests.post(url_v2, json=data_v2, timeout=5)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ REPONSE:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Verifier boutique_id
        if 'boutique_id' in result:
            print(f"\n✅ boutique_id present: {result['boutique_id']}")
            print(f"   Boutique Nom: {result.get('boutique', {}).get('nom')}")
        else:
            print(f"\n❌ boutique_id absent de la reponse")
    else:
        print(f"❌ Erreur: {response.text}")
        
except Exception as e:
    print(f"❌ Erreur de connexion: {e}")

print("\n" + "=" * 60)
print("TESTS TERMINES")
print("=" * 60)

print("\n💡 INTERPRETATION:")
print("   - API v1 doit retourner 'client_maui' avec 'boutique'")
print("   - API v2 doit retourner 'boutique_id' et 'boutique'")
print("   - Si client_maui est null, le terminal n'a pas de boutique associee")
