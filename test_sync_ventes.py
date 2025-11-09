"""
Script de Test - Synchronisation de Ventes MAUI
===============================================

Ce script teste l'endpoint de synchronisation de ventes.
"""

import requests
import json

# Configuration
BASE_URL = "http://10.28.176.224:8000"
NUMERO_SERIE = "0a1badae951f8473"

def test_sync_ventes(with_slash=True):
    """Tester la synchronisation de ventes"""
    
    print("="*70)
    print(f"  TEST SYNCHRONISATION VENTES MAUI {'(AVEC slash)' if with_slash else '(SANS slash)'}")
    print("="*70)
    
    # URL de l'endpoint - Supporte les deux formats
    url = f"{BASE_URL}/api/v2/simple/ventes/sync{'/' if with_slash else ''}"
    
    # Headers avec numéro de série
    headers = {
        "Content-Type": "application/json",
        "X-Device-Serial": NUMERO_SERIE
    }
    
    # Données de test - Tableau de ventes
    ventes_data = [
        {
            "numero_facture": "TEST-SYNC-001",
            "mode_paiement": "CASH",
            "paye": True,
            "lignes": [
                {
                    "article_id": 6,
                    "quantite": 1,
                    "prix_unitaire": 40000
                }
            ]
        },
        {
            "numero_facture": "TEST-SYNC-002",
            "mode_paiement": "MOBILE_MONEY",
            "paye": True,
            "lignes": [
                {
                    "article_id": 6,
                    "quantite": 2,
                    "prix_unitaire": 40000
                }
            ]
        }
    ]
    
    print(f"\n📡 URL: {url}")
    print(f"🔑 Numéro de série: {NUMERO_SERIE}")
    print(f"📦 Nombre de ventes: {len(ventes_data)}")
    print(f"\n📤 Envoi des données...")
    
    try:
        # Envoyer la requête
        response = requests.post(url, headers=headers, json=ventes_data, timeout=10)
        
        print(f"\n📥 Statut HTTP: {response.status_code}")
        
        # Afficher la réponse
        if response.status_code in [200, 201]:
            data = response.json()
            print(f"\n✅ SUCCÈS!")
            print(f"\n📊 Statistiques:")
            print(f"   Total envoyées: {data.get('statistiques', {}).get('total_envoyees', 0)}")
            print(f"   Réussies: {data.get('statistiques', {}).get('reussies', 0)}")
            print(f"   Erreurs: {data.get('statistiques', {}).get('erreurs', 0)}")
            
            print(f"\n🏪 Boutique: {data.get('boutique_nom')}")
            print(f"📱 Terminal: {data.get('terminal')}")
            
            if data.get('ventes_creees'):
                print(f"\n✅ Ventes créées:")
                for vente in data['ventes_creees']:
                    print(f"   - {vente['numero_facture']}: {vente['montant_total']} CDF")
            
            if data.get('ventes_erreurs'):
                print(f"\n❌ Ventes en erreur:")
                for erreur in data['ventes_erreurs']:
                    print(f"   - {erreur.get('numero_facture', 'N/A')}: {erreur.get('erreur')}")
            
            print(f"\n📄 Réponse complète:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"\n❌ ERREUR!")
            try:
                error_data = response.json()
                print(f"\n📄 Détails de l'erreur:")
                print(json.dumps(error_data, indent=2, ensure_ascii=False))
            except:
                print(f"\n📄 Réponse brute:")
                print(response.text)
        
    except requests.exceptions.ConnectionError:
        print(f"\n❌ ERREUR: Impossible de se connecter au serveur")
        print(f"   Vérifiez que Django est démarré sur {BASE_URL}")
    except requests.exceptions.Timeout:
        print(f"\n❌ ERREUR: Timeout de la requête")
    except Exception as e:
        print(f"\n❌ ERREUR: {str(e)}")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    # Tester les deux formats d'URL
    print("\n🔹 Test 1 : URL SANS slash (format MAUI)")
    test_sync_ventes(with_slash=False)
    
    print("\n\n🔹 Test 2 : URL AVEC slash (format Django standard)")
    test_sync_ventes(with_slash=True)
