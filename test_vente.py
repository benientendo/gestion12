#!/usr/bin/env python3
"""
Script de test pour vérifier que Django peut recevoir et traiter une vente
"""
import requests
import json

# Configuration
DJANGO_URL = "http://192.168.1.111:8000/api/ventes/"

# Données de test (format MAUI)
test_payload = {
    "reference": "TEST-MAUI-001",
    "total": 100000,
    "mode_paiement": "Espèces",
    "paye": True,
    "lignes": [
        {
            "article_id": 1,  # ID Django de tecno_kc2
            "quantite": 1,
            "prix_unitaire": 50000,
            "montant_ligne": 50000
        },
        {
            "article_id": 11,  # ID Django de pneu
            "quantite": 1,
            "prix_unitaire": 50000,
            "montant_ligne": 50000
        }
    ]
}

def test_django_vente():
    """Test direct de l'API Django"""
    print("🧪 === TEST DIRECT DJANGO ===")
    print(f"URL: {DJANGO_URL}")
    print(f"Payload: {json.dumps(test_payload, indent=2)}")
    
    try:
        response = requests.post(
            DJANGO_URL,
            json=test_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"\n📡 Status Code: {response.status_code}")
        print(f"📄 Réponse: {response.text}")
        
        if response.status_code == 201:
            print("✅ SUCCÈS: Django a accepté la vente")
            return True
        else:
            print("❌ ÉCHEC: Django a rejeté la vente")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ ERREUR RÉSEAU: {e}")
        return False

if __name__ == "__main__":
    success = test_django_vente()
    if success:
        print("\n🎉 Django fonctionne parfaitement !")
        print("Le problème vient donc de l'envoi MAUI.")
    else:
        print("\n⚠️ Django a des problèmes.")
        print("Vérifiez que le serveur Django est démarré.")
