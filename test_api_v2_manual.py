#!/usr/bin/env python3
"""
Test Manuel API v2 - Authentification et Requêtes
================================================
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"
NUMERO_SERIE = "1327637493002135"  # Terminal de test

def test_authentication():
    """Test d'authentification API v2"""
    print("🔐 Test d'authentification API v2...")
    
    auth_data = {
        "numero_serie": NUMERO_SERIE,
        "version_app": "2.0.0"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v2/auth/maui/",
            json=auth_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Authentification réussie!")
            print(f"Token: {data.get('token', '')[:50]}...")
            print(f"Boutique ID: {data.get('boutique_id')}")
            print(f"Boutique: {data.get('boutique', {}).get('nom')}")
            return data.get('token'), data.get('boutique_id')
        else:
            print(f"❌ Erreur d'authentification: {response.text}")
            return None, None
            
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return None, None

def test_articles_with_auth(token, boutique_id):
    """Test récupération articles avec authentification"""
    print(f"\n📦 Test récupération articles (boutique_id={boutique_id})...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v2/articles/?boutique_id={boutique_id}",
            headers=headers
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Articles récupérés avec succès!")
            print(f"Nombre d'articles: {data.get('count', 0)}")
            
            articles = data.get('articles', [])
            for article in articles[:3]:  # Afficher les 3 premiers
                print(f"  - {article.get('nom')} (Code: {article.get('code')})")
                
        else:
            print(f"❌ Erreur récupération articles: {response.text}")
            
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")

def test_articles_without_auth():
    """Test sans authentification (doit échouer)"""
    print(f"\n🚫 Test sans authentification (doit échouer)...")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v2/articles/")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 401:
            print("✅ Sécurité OK - Accès refusé sans authentification")
        else:
            print(f"⚠️ Problème de sécurité - Accès autorisé: {response.text}")
            
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")

def main():
    """Test complet de l'API v2"""
    print("🧪 TEST MANUEL API v2 MULTI-BOUTIQUES")
    print("=" * 50)
    
    # Test sans authentification
    test_articles_without_auth()
    
    # Test avec authentification
    token, boutique_id = test_authentication()
    
    if token and boutique_id:
        test_articles_with_auth(token, boutique_id)
    else:
        print("❌ Impossible de continuer sans authentification")
    
    print("\n" + "=" * 50)
    print("🏁 Tests terminés")

if __name__ == "__main__":
    main()
