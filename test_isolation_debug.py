#!/usr/bin/env python3
"""
Script de diagnostic pour tester l'isolation des données entre boutiques.
Reproduit le problème signalé par l'utilisateur.
"""

import os
import django
import requests
import json

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Commercant, Boutique, Client, Article, Categorie

def test_isolation_problem():
    """
    Test spécifique pour reproduire le problème d'isolation.
    """
    print("=== DIAGNOSTIC ISOLATION MULTI-BOUTIQUES ===\n")
    
    # 1. Vérifier la configuration actuelle
    print("1. 📊 ÉTAT ACTUEL DE LA BASE DE DONNÉES")
    
    commercant_messie = Commercant.objects.get(nom_entreprise="messie")
    print(f"   Commerçant: {commercant_messie.nom_entreprise}")
    
    boutiques = commercant_messie.boutiques.all()
    print(f"   Boutiques du commerçant: {boutiques.count()}")
    
    for boutique in boutiques:
        articles_count = boutique.articles.count()
        print(f"   - {boutique.nom}: {articles_count} articles")
        for article in boutique.articles.all():
            print(f"     * {article.nom} (ID: {article.id}, Code: {article.code})")
    
    # 2. Identifier le terminal MAUI
    print("\n2. 📱 TERMINAL MAUI")
    terminal = Client.objects.get(numero_serie="1327637493002135")
    print(f"   Terminal: {terminal.nom_terminal}")
    print(f"   Boutique liée: {terminal.boutique.nom} (ID: {terminal.boutique.id})")
    
    # 3. Tester l'API v1 (ancienne) - PROBLÈME POTENTIEL
    print("\n3. 🔍 TEST API v1 (ANCIENNE)")
    try:
        response = requests.get('http://127.0.0.1:8000/api/articles/')
        if response.status_code == 200:
            articles_v1 = response.json()
            print(f"   Status: {response.status_code}")
            print(f"   Articles retournés par API v1: {len(articles_v1)}")
            for article in articles_v1:
                print(f"   - {article.get('nom', 'N/A')} (ID: {article.get('id', 'N/A')})")
        else:
            print(f"   Erreur API v1: {response.status_code}")
    except Exception as e:
        print(f"   Erreur connexion API v1: {e}")
    
    # 4. Tester l'API v2 (nouvelle) avec boutique_id
    print("\n4. ✅ TEST API v2 (NOUVELLE) - AVEC BOUTIQUE_ID")
    try:
        boutique_id = terminal.boutique.id
        response = requests.get(f'http://127.0.0.1:8000/api/v2/articles/?boutique_id={boutique_id}')
        if response.status_code == 200:
            articles_v2 = response.json()
            print(f"   Status: {response.status_code}")
            print(f"   Articles retournés par API v2: {len(articles_v2)}")
            for article in articles_v2:
                print(f"   - {article.get('nom', 'N/A')} (ID: {article.get('id', 'N/A')})")
        else:
            print(f"   Erreur API v2: {response.status_code}")
    except Exception as e:
        print(f"   Erreur connexion API v2: {e}")
    
    # 5. Tester l'API v2 sans boutique_id
    print("\n5. 🔒 TEST API v2 (NOUVELLE) - SANS BOUTIQUE_ID")
    try:
        response = requests.get('http://127.0.0.1:8000/api/v2/articles/')
        if response.status_code == 200:
            articles_v2_no_id = response.json()
            print(f"   Status: {response.status_code}")
            print(f"   Articles retournés sans boutique_id: {len(articles_v2_no_id)}")
        else:
            print(f"   Erreur API v2 sans boutique_id: {response.status_code}")
    except Exception as e:
        print(f"   Erreur connexion API v2: {e}")
    
    # 6. Diagnostic du problème
    print("\n6. 🎯 DIAGNOSTIC")
    
    # Vérifier quelle API MAUI utilise
    print("   QUESTIONS CLÉS:")
    print("   - Quelle API votre application MAUI utilise-t-elle ?")
    print("     * API v1: http://serveur/api/articles/ (❌ PAS d'isolation)")
    print("     * API v2: http://serveur/api/v2/articles/?boutique_id=X (✅ Isolation)")
    
    print("\n   URLS DISPONIBLES:")
    print("   - API v1 (ancienne): /api/articles/ - RETOURNE TOUS LES ARTICLES")
    print("   - API v2 (nouvelle): /api/v2/articles/?boutique_id=X - FILTRE PAR BOUTIQUE")
    
    # 7. Recommandations
    print("\n7. 💡 RECOMMANDATIONS")
    print("   Si MAUI voit tous les articles:")
    print("   ✅ SOLUTION: Modifier MAUI pour utiliser l'API v2")
    print("   ✅ CHANGEMENT: /api/articles/ → /api/v2/articles/?boutique_id=X")
    print("   ✅ AUTHENTIFICATION: Utiliser /api/v2/auth/maui/ pour récupérer boutique_id")
    
    return {
        'terminal_boutique_id': terminal.boutique.id,
        'total_boutiques': boutiques.count(),
        'articles_par_boutique': {b.nom: b.articles.count() for b in boutiques}
    }

if __name__ == "__main__":
    try:
        result = test_isolation_problem()
        print(f"\n=== RÉSULTAT ===")
        print(f"Terminal lié à boutique ID: {result['terminal_boutique_id']}")
        print(f"Total boutiques du commerçant: {result['total_boutiques']}")
        print(f"Articles par boutique: {result['articles_par_boutique']}")
        
    except Exception as e:
        print(f"Erreur lors du diagnostic: {e}")
        import traceback
        traceback.print_exc()
