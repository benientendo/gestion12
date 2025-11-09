"""
Script de Test Complet - Système de Vente MAUI
==============================================

Ce script teste tous les endpoints de l'API v2 simple pour vérifier
que le système de vente fonctionne correctement.
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://192.168.52.224:8000"
NUMERO_SERIE = "0a1badae951f8473"  # Terminal de test

# Headers avec numéro de série
HEADERS = {
    "Content-Type": "application/json",
    "X-Device-Serial": NUMERO_SERIE
}

def print_section(title):
    """Affiche un titre de section"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_status():
    """Test 1: Vérifier le statut de l'API"""
    print_section("TEST 1: Statut de l'API")
    
    try:
        response = requests.get(f"{BASE_URL}/api/v2/simple/status/")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API Opérationnelle")
            print(f"   Version: {data.get('version')}")
            print(f"   Endpoints: {len(data.get('endpoints', []))}")
            return True
        else:
            print(f"❌ Erreur: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def test_terminal_info():
    """Test 2: Récupérer les infos du terminal"""
    print_section("TEST 2: Informations Terminal")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v2/simple/terminal/{NUMERO_SERIE}/",
            headers=HEADERS
        )
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Terminal trouvé")
            print(f"   Nom: {data.get('nom_terminal')}")
            print(f"   Boutique ID: {data.get('boutique_id')}")
            print(f"   Boutique: {data.get('boutique_nom')}")
            return data.get('boutique_id')
        else:
            print(f"❌ Erreur: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return None

def test_articles():
    """Test 3: Récupérer les articles"""
    print_section("TEST 3: Liste des Articles")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v2/simple/articles/",
            headers=HEADERS
        )
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            articles = data.get('articles', [])
            print(f"✅ Articles récupérés: {len(articles)}")
            
            if articles:
                print("\n   Articles disponibles:")
                for article in articles[:3]:  # Afficher les 3 premiers
                    print(f"   - ID: {article['id']}, Nom: {article['nom']}, Prix: {article['prix_vente']} CDF, Stock: {article['quantite_stock']}")
                
                return articles
            else:
                print("⚠️  Aucun article disponible")
                return []
        else:
            print(f"❌ Erreur: {response.text}")
            return []
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return []

def test_categories():
    """Test 4: Récupérer les catégories"""
    print_section("TEST 4: Liste des Catégories")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v2/simple/categories/",
            headers=HEADERS
        )
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            categories = data.get('categories', [])
            print(f"✅ Catégories récupérées: {len(categories)}")
            
            if categories:
                print("\n   Catégories disponibles:")
                for cat in categories:
                    print(f"   - ID: {cat['id']}, Nom: {cat['nom']}")
            
            return True
        else:
            print(f"❌ Erreur: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def test_create_vente(articles):
    """Test 5: Créer une vente"""
    print_section("TEST 5: Création de Vente")
    
    if not articles:
        print("⚠️  Impossible de tester: Aucun article disponible")
        return False
    
    # Prendre le premier article avec stock suffisant
    article = None
    for a in articles:
        if a['quantite_stock'] > 0:
            article = a
            break
    
    if not article:
        print("⚠️  Impossible de tester: Aucun article avec stock disponible")
        return False
    
    print(f"\n📦 Article sélectionné:")
    print(f"   ID: {article['id']}")
    print(f"   Nom: {article['nom']}")
    print(f"   Prix: {article['prix_vente']} CDF")
    print(f"   Stock avant: {article['quantite_stock']}")
    
    # Créer la vente (format MINIMAL)
    vente_data = {
        "lignes": [
            {
                "article_id": article['id'],
                "quantite": 1,
                "prix_unitaire": float(article['prix_vente'])
            }
        ]
    }
    
    print(f"\n📤 Envoi de la vente:")
    print(f"   Body: {json.dumps(vente_data, indent=2)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v2/simple/ventes/",
            headers=HEADERS,
            json=vente_data
        )
        print(f"\n📥 Réponse:")
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code in [200, 201]:
            data = response.json()
            print(f"✅ Vente créée avec succès!")
            print(f"   Numéro facture: {data['vente']['numero_facture']}")
            print(f"   Montant total: {data['vente']['montant_total']} CDF")
            print(f"   Mode paiement: {data['vente']['mode_paiement']}")
            print(f"   Boutique ID: {data['boutique_id']}")
            
            # Vérifier le stock après
            response_check = requests.get(
                f"{BASE_URL}/api/v2/simple/articles/",
                headers=HEADERS
            )
            if response_check.status_code == 200:
                articles_after = response_check.json().get('articles', [])
                article_after = next((a for a in articles_after if a['id'] == article['id']), None)
                if article_after:
                    print(f"   Stock après: {article_after['quantite_stock']}")
                    if article_after['quantite_stock'] == article['quantite_stock'] - 1:
                        print(f"   ✅ Stock mis à jour correctement!")
                    else:
                        print(f"   ⚠️  Stock non mis à jour")
            
            return True
        else:
            print(f"❌ Erreur lors de la création:")
            print(f"   {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def test_historique():
    """Test 6: Récupérer l'historique des ventes"""
    print_section("TEST 6: Historique des Ventes")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v2/simple/ventes/historique/?limit=5",
            headers=HEADERS
        )
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            ventes = data.get('ventes', [])
            stats = data.get('statistiques', {})
            
            print(f"✅ Historique récupéré")
            print(f"   Total ventes: {stats.get('total_ventes', 0)}")
            print(f"   CA total: {stats.get('chiffre_affaires', 0)} CDF")
            
            if ventes:
                print(f"\n   Dernières ventes:")
                for vente in ventes[:3]:
                    print(f"   - {vente['numero_facture']}: {vente['montant_total']} CDF")
            
            return True
        else:
            print(f"❌ Erreur: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def test_statistiques():
    """Test 7: Récupérer les statistiques"""
    print_section("TEST 7: Statistiques Boutique")
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v2/simple/statistiques/",
            headers=HEADERS
        )
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            stats = data.get('statistiques', {})
            
            print(f"✅ Statistiques récupérées")
            print(f"\n   📊 Articles:")
            print(f"      Total: {stats.get('articles', {}).get('total', 0)}")
            print(f"      Stock bas: {stats.get('articles', {}).get('stock_bas', 0)}")
            
            print(f"\n   💰 Ventes du jour:")
            print(f"      Nombre: {stats.get('ventes_jour', {}).get('nombre', 0)}")
            print(f"      CA: {stats.get('ventes_jour', {}).get('chiffre_affaires', 0)} CDF")
            
            print(f"\n   📅 Ventes du mois:")
            print(f"      Nombre: {stats.get('ventes_mois', {}).get('nombre', 0)}")
            print(f"      CA: {stats.get('ventes_mois', {}).get('chiffre_affaires', 0)} CDF")
            
            return True
        else:
            print(f"❌ Erreur: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def main():
    """Exécuter tous les tests"""
    print("\n" + "="*60)
    print("  TEST COMPLET - SYSTÈME DE VENTE MAUI")
    print("="*60)
    print(f"\n🔧 Configuration:")
    print(f"   Base URL: {BASE_URL}")
    print(f"   Numéro série: {NUMERO_SERIE}")
    print(f"   Date: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    results = {
        "API Status": test_status(),
        "Terminal Info": test_terminal_info() is not None,
        "Articles": len(test_articles()) > 0,
        "Catégories": test_categories(),
    }
    
    # Test de vente seulement si les articles sont disponibles
    articles = test_articles()
    if articles:
        results["Création Vente"] = test_create_vente(articles)
        results["Historique"] = test_historique()
        results["Statistiques"] = test_statistiques()
    
    # Résumé
    print_section("RÉSUMÉ DES TESTS")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} - {test_name}")
    
    print(f"\n📊 Résultat: {passed}/{total} tests réussis")
    
    if passed == total:
        print("\n🎉 TOUS LES TESTS SONT PASSÉS!")
        print("   Le système de vente MAUI est 100% fonctionnel!")
    else:
        print(f"\n⚠️  {total - passed} test(s) ont échoué")
        print("   Vérifiez les logs Django pour plus de détails")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
