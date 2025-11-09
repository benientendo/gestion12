#!/usr/bin/env python3
"""
Test d'authentification avec le bon numéro de série
"""

import requests
import json

def test_correct_auth():
    """Test avec le numéro de série correct"""
    print("🧪 TEST AUTHENTIFICATION AVEC BON NUMÉRO DE SÉRIE")
    print("=" * 60)
    
    # Données d'authentification correctes
    auth_data = {
        "numero_serie": "1327637493002135",  # ✅ Numéro de série valide
        "version_app": "2.0.0"
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/api/v2/auth/maui/",
            json=auth_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"📡 Requête envoyée vers: /api/v2/auth/maui/")
        print(f"📤 Données: {json.dumps(auth_data, indent=2)}")
        print(f"📥 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ AUTHENTIFICATION RÉUSSIE!")
            print(f"🎫 Token: {result.get('token', '')[:50]}...")
            print(f"🏪 Boutique ID: {result.get('boutique_id')}")
            print(f"🏪 Boutique Nom: {result.get('boutique', {}).get('nom')}")
            
            # Test récupération articles avec ce token
            test_articles_with_token(result.get('token'), result.get('boutique_id'))
            
        else:
            print(f"❌ ERREUR D'AUTHENTIFICATION")
            print(f"📄 Réponse: {response.text}")
            
    except Exception as e:
        print(f"❌ ERREUR DE CONNEXION: {e}")

def test_articles_with_token(token, boutique_id):
    """Test récupération articles avec token"""
    print(f"\n📦 TEST RÉCUPÉRATION ARTICLES")
    print("-" * 40)
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            f"http://localhost:8000/api/v2/articles/?boutique_id={boutique_id}",
            headers=headers
        )
        
        print(f"📡 URL: /api/v2/articles/?boutique_id={boutique_id}")
        print(f"📥 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ ARTICLES RÉCUPÉRÉS AVEC SUCCÈS!")
            print(f"📊 Nombre d'articles: {result.get('count', 0)}")
            
            articles = result.get('articles', [])
            for article in articles[:3]:  # Afficher les 3 premiers
                print(f"  📦 {article.get('nom')} (Code: {article.get('code')})")
        else:
            print(f"❌ ERREUR RÉCUPÉRATION ARTICLES: {response.text}")
            
    except Exception as e:
        print(f"❌ ERREUR: {e}")

def test_wrong_serial():
    """Test avec le mauvais numéro de série (pour comparaison)"""
    print(f"\n🚫 TEST AVEC MAUVAIS NUMÉRO DE SÉRIE")
    print("-" * 40)
    
    auth_data = {
        "numero_serie": "localhost",  # ❌ Mauvais numéro
        "version_app": "2.0.0"
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/api/v2/auth/maui/",
            json=auth_data
        )
        
        print(f"📤 Données: {json.dumps(auth_data)}")
        print(f"📥 Status Code: {response.status_code}")
        
        if response.status_code == 403:
            print("✅ SÉCURITÉ OK - Accès refusé pour mauvais numéro de série")
        else:
            print(f"⚠️ Réponse inattendue: {response.text}")
            
    except Exception as e:
        print(f"❌ ERREUR: {e}")

if __name__ == "__main__":
    test_correct_auth()
    test_wrong_serial()
    
    print(f"\n💡 SOLUTION POUR MAUI:")
    print("1. Remplacez 'localhost' par '1327637493002135' dans votre code")
    print("2. Vérifiez la méthode GetDeviceSerial() ou équivalent")
    print("3. Testez l'authentification avec le bon numéro de série")
    print("4. Les erreurs 401/403 disparaîtront automatiquement")
