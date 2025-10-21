import os
import django
import sys

# Configuration de Django
sys.path.append('/Users/PC/Documents/GestionMagazin')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GestionMagazin.settings')
django.setup()

from inventory.models import Article

def test_prix_conversion():
    # Cas de test pour différents formats de prix
    test_cases = [
        ('10.50', True),     # Prix standard
        ('0', True),         # Prix zéro
        ('100', True),       # Prix entier
        ('15.999', False),   # Trop de décimales
        ('-5.00', False),    # Prix négatif
        ('abc', False),      # Invalide
        ('10,50', False),    # Virgule au lieu de point
    ]
    
    print("Test de conversion des prix :")
    for prix_str, expected_valid in test_cases:
        try:
            article = Article(
                code=f'test_{prix_str}', 
                nom=f'Article Test {prix_str}', 
                prix_vente=prix_str,
                prix_achat='0',
                categorie=None,
                quantite_stock=0
            )
            article.full_clean()  # Validation Django
            print(f"Prix '{prix_str}' : ✅ Valide (Converti en {article.prix_vente})")
        except Exception as e:
            if expected_valid:
                print(f"Prix '{prix_str}' : ❌ Invalide - {e}")
            else:
                print(f"Prix '{prix_str}' : ✅ Rejeté comme prévu - {e}")

def test_mobile_conversion():
    # Simulation de la conversion côté mobile (C#)
    print("\nTest de conversion côté mobile (C#) :")
    prix_tests = [
        '10.50',   # Prix standard
        '0',       # Zéro
        '100',     # Entier
        '15.999',  # Trop de décimales
        '-5.00',   # Négatif
        'abc'      # Invalide
    ]
    
    for prix_str in prix_tests:
        try:
            # Simulation de decimal.TryParse en Python
            prix = float(prix_str)
            print(f"Prix '{prix_str}' : ✅ Converti en {prix}")
        except ValueError:
            print(f"Prix '{prix_str}' : ❌ Impossible à convertir")

if __name__ == '__main__':
    test_prix_conversion()
    test_mobile_conversion()
