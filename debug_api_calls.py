#!/usr/bin/env python3
"""
Script pour identifier qui fait des appels à l'API v2
"""

import time
import requests
from datetime import datetime

def monitor_api_calls():
    """Surveiller les appels API et identifier les patterns"""
    print("🔍 SURVEILLANCE DES APPELS API v2")
    print("=" * 50)
    
    # Tester si quelqu'un fait des appels répétés
    base_url = "http://localhost:8000"
    
    print(f"⏰ {datetime.now().strftime('%H:%M:%S')} - Début surveillance...")
    
    # Vérifier les endpoints problématiques
    endpoints_to_check = [
        "/api/v2/articles/",
        "/api/v2/categories/",
        "/api/v2/status/"
    ]
    
    for i in range(10):  # Surveiller pendant 10 cycles
        print(f"\n📊 Cycle {i+1}/10 - {datetime.now().strftime('%H:%M:%S')}")
        
        for endpoint in endpoints_to_check:
            try:
                start_time = time.time()
                response = requests.get(f"{base_url}{endpoint}", timeout=2)
                response_time = time.time() - start_time
                
                print(f"  {endpoint}: {response.status_code} ({response_time:.2f}s)")
                
                if endpoint == "/api/v2/status/":
                    # Cet endpoint devrait fonctionner
                    if response.status_code != 200:
                        print(f"    ⚠️ Problème avec endpoint status")
                
            except requests.exceptions.RequestException as e:
                print(f"  {endpoint}: ERREUR - {e}")
        
        time.sleep(5)  # Attendre 5 secondes entre les cycles
    
    print(f"\n✅ Surveillance terminée - {datetime.now().strftime('%H:%M:%S')}")
    
    # Recommandations
    print("\n💡 RECOMMANDATIONS:")
    print("1. Vérifiez si une application MAUI est en cours de test")
    print("2. Cherchez des scripts Python qui tournent en arrière-plan")
    print("3. Vérifiez les onglets de navigateur ouverts")
    print("4. Regardez les processus actifs avec 'tasklist | findstr python'")

if __name__ == "__main__":
    monitor_api_calls()
