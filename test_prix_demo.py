import sys
import os

# Configuration de Django
sys.path.append('/Users/PC/Documents/GestionMagazin')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GestionMagazin.settings')

import django
django.setup()

from inventory.models import Article, Categorie
from django.core.exceptions import ValidationError

def demonstrer_validation_prix():
    print("🔍 Démonstration de Validation des Prix 🔍")
    
    # Créer une catégorie de test
    categorie, _ = Categorie.objects.get_or_create(nom='Catégorie Démonstration')

    # Scénarios de test
    scenarios = [
        ('Prix Valide', '10.50', True),
        ('Prix Négatif', '-5.00', False),
        ('Prix Invalide', 'abc', False),
        ('Prix Trop Précis', '10.555', False),
        ('Prix Zéro', '0', True)
    ]

    for description, prix, attendu_valide in scenarios:
        print(f"\n📌 Scénario : {description}")
        print(f"   Prix testé : {prix}")
        
        article = Article(
            code=f'test_{prix}',
            nom=f'Article Test {prix}',
            prix_vente=prix,
            prix_achat='0',
            categorie=categorie,
            quantite_stock=10
        )

        try:
            article.full_clean()  # Validation Django
            
            if not attendu_valide:
                print("❌ ERREUR : Prix aurait dû être invalide")
            else:
                print(f"✅ Prix {prix} validé avec succès")
                article.save()
        
        except ValidationError as e:
            if attendu_valide:
                print("❌ ERREUR : Prix valide rejeté")
                print(f"   Détails de l'erreur : {e}")
            else:
                print("✅ Prix invalide correctement rejeté")
                print(f"   Détails de l'erreur : {e}")

if __name__ == '__main__':
    demonstrer_validation_prix()
