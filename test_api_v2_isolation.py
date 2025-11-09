#!/usr/bin/env python3
"""
Script de Test - API v2 Multi-Boutiques
=======================================

Ce script teste l'isolation des données par boutique et la sécurité de l'API v2.
Il valide que chaque terminal ne peut accéder qu'aux données de sa boutique.
"""

import os
import sys
import django
import requests
import json
from datetime import datetime

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Client, Boutique, Article, Commercant
from django.contrib.auth.models import User

# Configuration du serveur de test
BASE_URL = "http://127.0.0.1:8000"
API_V2_URL = f"{BASE_URL}/api/v2"

class Colors:
    """Couleurs pour l'affichage console"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_header(title):
    """Affiche un en-tête coloré"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{title.center(60)}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.END}")

def print_success(message):
    """Affiche un message de succès"""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_error(message):
    """Affiche un message d'erreur"""
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_warning(message):
    """Affiche un avertissement"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def print_info(message):
    """Affiche une information"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")

def analyze_database():
    """Analyse la base de données pour comprendre la structure"""
    print_header("ANALYSE DE LA BASE DE DONNÉES")
    
    # Compter les éléments
    commercants = Commercant.objects.all()
    boutiques = Boutique.objects.all()
    terminaux = Client.objects.all()
    articles = Article.objects.all()
    
    print_info(f"Commerçants: {commercants.count()}")
    print_info(f"Boutiques: {boutiques.count()}")
    print_info(f"Terminaux MAUI: {terminaux.count()}")
    print_info(f"Articles: {articles.count()}")
    
    # Détails par commerçant
    for commercant in commercants:
        print(f"\n{Colors.MAGENTA}📊 Commerçant: {commercant.nom_entreprise}{Colors.END}")
        
        for boutique in commercant.boutiques.all():
            nb_terminaux = boutique.clients.count()
            nb_articles = boutique.articles.count()
            nb_categories = boutique.categories.count()
            
            print(f"  🏪 {boutique.nom} (ID: {boutique.id})")
            print(f"     - Terminaux: {nb_terminaux}")
            print(f"     - Articles: {nb_articles}")
            print(f"     - Catégories: {nb_categories}")
            
            # Lister les terminaux
            for terminal in boutique.clients.all():
                print(f"     📱 Terminal: {terminal.nom_terminal} ({terminal.numero_serie})")
    
    return {
        'commercants': list(commercants),
        'boutiques': list(boutiques),
        'terminaux': list(terminaux),
        'articles': list(articles)
    }

def test_authentication_v2():
    """Test de l'authentification API v2"""
    print_header("TEST AUTHENTIFICATION API v2")
    
    # Récupérer un terminal de test
    terminal = Client.objects.filter(est_actif=True).first()
    if not terminal:
        print_error("Aucun terminal actif trouvé dans la base de données")
        return None
    
    print_info(f"Test avec terminal: {terminal.nom_terminal} ({terminal.numero_serie})")
    print_info(f"Boutique associée: {terminal.boutique.nom if terminal.boutique else 'Aucune'}")
    
    # Test d'authentification
    auth_data = {
        "numero_serie": terminal.numero_serie,
        "version_app": "2.0.0"
    }
    
    try:
        response = requests.post(f"{API_V2_URL}/auth/maui/", json=auth_data, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print_success("Authentification réussie")
            print_info(f"Token reçu: {data.get('token', 'N/A')[:50]}...")
            print_info(f"Boutique ID: {data.get('boutique_id')}")
            print_info(f"Boutique nom: {data.get('boutique', {}).get('nom')}")
            
            return {
                'token': data.get('token'),
                'boutique_id': data.get('boutique_id'),
                'boutique_info': data.get('boutique', {}),
                'terminal_info': data.get('terminal', {})
            }
        else:
            print_error(f"Échec authentification: {response.status_code}")
            print_error(f"Réponse: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print_error(f"Erreur de connexion: {e}")
        return None

def test_articles_isolation(auth_info):
    """Test de l'isolation des articles par boutique"""
    print_header("TEST ISOLATION ARTICLES")
    
    if not auth_info:
        print_error("Pas d'informations d'authentification")
        return False
    
    token = auth_info['token']
    boutique_id = auth_info['boutique_id']
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Test 1: Récupération des articles de la boutique
    print_info(f"Test 1: Récupération articles boutique {boutique_id}")
    
    try:
        response = requests.get(
            f"{API_V2_URL}/articles/",
            params={'boutique_id': boutique_id},
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            articles_count = data.get('count', 0)
            print_success(f"Articles récupérés: {articles_count}")
            
            # Afficher quelques articles
            for article in data.get('articles', [])[:3]:
                print(f"  📦 {article.get('nom')} (Code: {article.get('code')})")
        else:
            print_error(f"Échec récupération articles: {response.status_code}")
            print_error(f"Réponse: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_error(f"Erreur de connexion: {e}")
        return False
    
    # Test 2: Tentative d'accès à une autre boutique
    print_info("Test 2: Tentative d'accès à une autre boutique")
    
    other_boutique = Boutique.objects.exclude(id=boutique_id).first()
    if other_boutique:
        try:
            response = requests.get(
                f"{API_V2_URL}/articles/",
                params={'boutique_id': other_boutique.id},
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 403:
                print_success("Accès refusé à une autre boutique (sécurité OK)")
            elif response.status_code == 200:
                data = response.json()
                articles_count = data.get('count', 0)
                print_error(f"SÉCURITÉ COMPROMISE: Accès autorisé à {articles_count} articles d'une autre boutique")
                return False
            else:
                print_warning(f"Réponse inattendue: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print_error(f"Erreur de connexion: {e}")
    else:
        print_warning("Pas d'autre boutique pour tester l'isolation")
    
    # Test 3: Requête sans boutique_id
    print_info("Test 3: Requête sans boutique_id")
    
    try:
        response = requests.get(
            f"{API_V2_URL}/articles/",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 400:
            print_success("Requête sans boutique_id rejetée (sécurité OK)")
        else:
            print_error(f"SÉCURITÉ COMPROMISE: Requête sans boutique_id acceptée ({response.status_code})")
            return False
            
    except requests.exceptions.RequestException as e:
        print_error(f"Erreur de connexion: {e}")
        return False
    
    return True

def test_categories_isolation(auth_info):
    """Test de l'isolation des catégories par boutique"""
    print_header("TEST ISOLATION CATÉGORIES")
    
    if not auth_info:
        print_error("Pas d'informations d'authentification")
        return False
    
    token = auth_info['token']
    boutique_id = auth_info['boutique_id']
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(
            f"{API_V2_URL}/categories/",
            params={'boutique_id': boutique_id},
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            categories_count = data.get('count', 0)
            print_success(f"Catégories récupérées: {categories_count}")
            
            # Afficher quelques catégories
            for categorie in data.get('categories', [])[:3]:
                print(f"  🏷️  {categorie.get('nom')}")
            
            return True
        else:
            print_error(f"Échec récupération catégories: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_error(f"Erreur de connexion: {e}")
        return False

def test_boutique_info(auth_info):
    """Test des informations boutique"""
    print_header("TEST INFORMATIONS BOUTIQUE")
    
    if not auth_info:
        print_error("Pas d'informations d'authentification")
        return False
    
    token = auth_info['token']
    boutique_id = auth_info['boutique_id']
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(
            f"{API_V2_URL}/boutique/{boutique_id}/info/",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            boutique_info = data.get('boutique', {})
            stats = data.get('statistiques', {})
            
            print_success("Informations boutique récupérées")
            print_info(f"Nom: {boutique_info.get('nom')}")
            print_info(f"Type: {boutique_info.get('type_commerce')}")
            print_info(f"Articles: {stats.get('nb_articles')}")
            print_info(f"Catégories: {stats.get('nb_categories')}")
            print_info(f"Ventes aujourd'hui: {stats.get('nb_ventes_aujourd_hui')}")
            print_info(f"CA aujourd'hui: {stats.get('ca_aujourd_hui')} {boutique_info.get('devise', 'CDF')}")
            
            return True
        else:
            print_error(f"Échec récupération infos boutique: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_error(f"Erreur de connexion: {e}")
        return False

def test_session_validation(auth_info):
    """Test de validation de session"""
    print_header("TEST VALIDATION SESSION")
    
    if not auth_info:
        print_error("Pas d'informations d'authentification")
        return False
    
    token = auth_info['token']
    terminal_info = auth_info['terminal_info']
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    validation_data = {
        'numero_serie': terminal_info.get('numero_serie')
    }
    
    try:
        response = requests.post(
            f"{API_V2_URL}/auth/validate/",
            json=validation_data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print_success("Session validée")
            print_info(f"Boutique ID: {data.get('boutique_id')}")
            print_info(f"Terminal ID: {data.get('terminal_id')}")
            print_info(f"Dernière activité: {data.get('derniere_activite')}")
            
            return True
        else:
            print_error(f"Échec validation session: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_error(f"Erreur de connexion: {e}")
        return False

def generate_report(results):
    """Génère un rapport de test"""
    print_header("RAPPORT DE TEST")
    
    total_tests = len(results)
    passed_tests = sum(1 for result in results.values() if result)
    failed_tests = total_tests - passed_tests
    
    print_info(f"Tests exécutés: {total_tests}")
    print_success(f"Tests réussis: {passed_tests}")
    
    if failed_tests > 0:
        print_error(f"Tests échoués: {failed_tests}")
    
    print(f"\n{Colors.BOLD}Détails des tests:{Colors.END}")
    for test_name, result in results.items():
        status = "✅ RÉUSSI" if result else "❌ ÉCHOUÉ"
        color = Colors.GREEN if result else Colors.RED
        print(f"  {color}{status}{Colors.END} - {test_name}")
    
    # Calcul du score
    score = (passed_tests / total_tests) * 100
    
    if score == 100:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 TOUS LES TESTS RÉUSSIS - ISOLATION PARFAITE !{Colors.END}")
    elif score >= 80:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  ISOLATION PARTIELLE - Score: {score:.1f}%{Colors.END}")
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}🚨 PROBLÈMES DE SÉCURITÉ DÉTECTÉS - Score: {score:.1f}%{Colors.END}")
    
    return score

def main():
    """Fonction principale"""
    print_header("TEST API v2 MULTI-BOUTIQUES - ISOLATION DES DONNÉES")
    print_info(f"Début des tests: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_info(f"URL de base: {BASE_URL}")
    
    # Analyse de la base de données
    db_info = analyze_database()
    
    # Vérification des prérequis
    if not db_info['terminaux']:
        print_error("Aucun terminal MAUI trouvé dans la base de données")
        print_error("Veuillez créer au moins un terminal pour les tests")
        return
    
    # Tests
    results = {}
    
    # Test d'authentification
    auth_info = test_authentication_v2()
    results['Authentification v2'] = auth_info is not None
    
    if auth_info:
        # Tests d'isolation
        results['Isolation Articles'] = test_articles_isolation(auth_info)
        results['Isolation Catégories'] = test_categories_isolation(auth_info)
        results['Informations Boutique'] = test_boutique_info(auth_info)
        results['Validation Session'] = test_session_validation(auth_info)
    else:
        print_error("Impossible de continuer les tests sans authentification")
        results.update({
            'Isolation Articles': False,
            'Isolation Catégories': False,
            'Informations Boutique': False,
            'Validation Session': False
        })
    
    # Génération du rapport
    score = generate_report(results)
    
    print_info(f"Fin des tests: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Code de sortie
    sys.exit(0 if score == 100 else 1)

if __name__ == "__main__":
    main()
