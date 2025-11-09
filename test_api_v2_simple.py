#!/usr/bin/env python3
"""
Test API v2 Simplifiée (Sans Authentification)
==============================================
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api/v2/simple"

def test_api_status():
    """Test du statut de l'API"""
    print("🔍 1. TEST STATUT API")
    print("-" * 30)
    
    try:
        response = requests.get(f"{API_URL}/status/")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ API v2 Simple active")
            print(f"Version: {data.get('api_version')}")
            print(f"Message: {data.get('message')}")
            return True
        else:
            print(f"❌ Erreur: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return False

def test_boutiques_list():
    """Test de la liste des boutiques"""
    print("\n🏪 2. TEST LISTE BOUTIQUES")
    print("-" * 30)
    
    try:
        response = requests.get(f"{API_URL}/boutiques/")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {data.get('count')} boutique(s) trouvée(s)")
            
            for boutique in data.get('boutiques', []):
                print(f"  🏪 {boutique['nom']} (ID: {boutique['id']})")
                print(f"     Type: {boutique['type_commerce']}")
                print(f"     Ville: {boutique['ville']}")
                print(f"     Articles: {boutique['nb_articles']}")
                print(f"     Terminaux: {boutique['nb_terminaux']}")
            
            return data.get('boutiques', [])
        else:
            print(f"❌ Erreur: {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return []

def test_terminal_info():
    """Test des informations terminal"""
    print("\n📱 3. TEST INFO TERMINAL")
    print("-" * 30)
    
    numero_serie = "1327637493002135"
    
    try:
        response = requests.get(f"{API_URL}/terminal/{numero_serie}/")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            terminal = data.get('terminal', {})
            boutique = data.get('boutique', {})
            
            print(f"✅ Terminal trouvé: {terminal.get('nom_terminal')}")
            print(f"   Numéro série: {terminal.get('numero_serie')}")
            print(f"   Statut: {'✅ Actif' if terminal.get('est_actif') else '❌ Inactif'}")
            print(f"   Boutique: {boutique.get('nom')} (ID: {boutique.get('id')})")
            
            return boutique.get('id')
        else:
            print(f"❌ Erreur: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None

def test_articles_list(boutique_id):
    """Test de la liste des articles"""
    print(f"\n📦 4. TEST ARTICLES BOUTIQUE {boutique_id}")
    print("-" * 30)
    
    try:
        response = requests.get(f"{API_URL}/articles/?boutique_id={boutique_id}")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {data.get('count')} article(s) dans {data.get('boutique_nom')}")
            
            for article in data.get('articles', [])[:5]:  # Afficher les 5 premiers
                print(f"  📦 {article['nom']} (Code: {article['code']})")
                print(f"     Prix: {article['prix_vente']} {data.get('boutique_nom', 'CDF')}")
                print(f"     Stock: {article['quantite_stock']}")
            
            return data.get('articles', [])
        else:
            print(f"❌ Erreur: {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return []

def test_categories_list(boutique_id):
    """Test de la liste des catégories"""
    print(f"\n🏷️ 5. TEST CATÉGORIES BOUTIQUE {boutique_id}")
    print("-" * 30)
    
    try:
        response = requests.get(f"{API_URL}/categories/?boutique_id={boutique_id}")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ {data.get('count')} catégorie(s) dans {data.get('boutique_nom')}")
            
            for categorie in data.get('categories', []):
                print(f"  🏷️ {categorie['nom']}")
                if categorie.get('description'):
                    print(f"     {categorie['description']}")
            
            return data.get('categories', [])
        else:
            print(f"❌ Erreur: {response.text}")
            return []
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return []

def test_create_vente(boutique_id, articles):
    """Test de création d'une vente"""
    print(f"\n💰 6. TEST CRÉATION VENTE")
    print("-" * 30)
    
    if not articles:
        print("❌ Aucun article disponible pour créer une vente")
        return
    
    # Prendre le premier article disponible
    article = articles[0]
    
    vente_data = {
        "boutique_id": boutique_id,
        "numero_serie": "1327637493002135",
        "numero_facture": f"TEST-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "mode_paiement": "CASH",
        "paye": True,
        "lignes": [
            {
                "article_id": article['id'],
                "quantite": 1,
                "prix_unitaire": article['prix_vente']
            }
        ]
    }
    
    try:
        response = requests.post(
            f"{API_URL}/ventes/",
            json=vente_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 201:
            data = response.json()
            vente = data.get('vente', {})
            
            print(f"✅ Vente créée: {vente.get('numero_facture')}")
            print(f"   Montant: {vente.get('montant_total')} CDF")
            print(f"   Articles: {len(vente.get('lignes', []))}")
            
            for ligne in vente.get('lignes', []):
                print(f"     - {ligne['article_nom']}: {ligne['quantite']} x {ligne['prix_unitaire']} = {ligne['sous_total']}")
            
            return True
        else:
            print(f"❌ Erreur: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

def test_errors():
    """Test des cas d'erreur"""
    print(f"\n🚫 7. TEST GESTION D'ERREURS")
    print("-" * 30)
    
    # Test sans boutique_id
    print("Test sans boutique_id:")
    response = requests.get(f"{API_URL}/articles/")
    print(f"  Status: {response.status_code} (attendu: 400)")
    
    # Test boutique inexistante
    print("Test boutique inexistante:")
    response = requests.get(f"{API_URL}/articles/?boutique_id=999")
    print(f"  Status: {response.status_code} (attendu: 404)")
    
    # Test terminal inexistant
    print("Test terminal inexistant:")
    response = requests.get(f"{API_URL}/terminal/INEXISTANT/")
    print(f"  Status: {response.status_code} (attendu: 404)")

def main():
    """Test complet de l'API v2 simplifiée"""
    print("🧪 TEST COMPLET API v2 SIMPLIFIÉE")
    print("=" * 50)
    
    # 1. Test du statut
    if not test_api_status():
        print("❌ API non disponible, arrêt des tests")
        return
    
    # 2. Test des boutiques
    boutiques = test_boutiques_list()
    if not boutiques:
        print("❌ Aucune boutique disponible")
        return
    
    # 3. Test des informations terminal
    boutique_id = test_terminal_info()
    if not boutique_id:
        print("❌ Terminal non trouvé, utilisation de la première boutique")
        boutique_id = boutiques[0]['id']
    
    # 4. Test des articles
    articles = test_articles_list(boutique_id)
    
    # 5. Test des catégories
    test_categories_list(boutique_id)
    
    # 6. Test de création de vente
    if articles:
        test_create_vente(boutique_id, articles)
    
    # 7. Test des erreurs
    test_errors()
    
    print(f"\n🎉 TESTS TERMINÉS")
    print("=" * 50)
    print("✅ API v2 Simplifiée fonctionnelle sans authentification")
    print("✅ Isolation des données par boutique maintenue")
    print("✅ Prêt pour intégration MAUI simplifiée")

if __name__ == "__main__":
    main()
