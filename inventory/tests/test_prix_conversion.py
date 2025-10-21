from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from inventory.models import Article, Categorie

class PrixConversionTestCase(TestCase):
    def setUp(self):
        # Créer une catégorie de test
        self.categorie = Categorie.objects.create(nom='Catégorie Test')

    def test_prix_conversion_valide(self):
        """
        Tester les conversions de prix valides
        """
        test_cases = [
            '10.50',   # Prix standard
            '0',       # Prix zéro
            '100',     # Prix entier
            '15.50'    # Prix avec deux décimales
        ]
        
        for prix_str in test_cases:
            article = Article(
                code=f'test_code_{prix_str}',
                nom=f'Article Test {prix_str}',
                prix_vente=prix_str,
                prix_achat='0',
                categorie=self.categorie,
                quantite_stock=10
            )
            
            try:
                article.full_clean()  # Validation Django
                article.save()
                self.assertTrue(True, f"Prix {prix_str} converti et sauvegardé avec succès")
            except ValidationError as e:
                self.fail(f"Prix {prix_str} invalide : {e}")

    def test_prix_conversion_invalide(self):
        """
        Tester les conversions de prix invalides
        """
        test_cases = [
            '15.999',  # Trop de décimales
            '-5.00',   # Prix négatif
            'abc',     # Invalide
            '10,50'    # Virgule au lieu de point
        ]
        
        for prix_str in test_cases:
            article = Article(
                code=f'test_code_{prix_str}',
                nom=f'Article Test {prix_str}',
                prix_vente=prix_str,
                prix_achat='0',
                categorie=self.categorie,
                quantite_stock=10
            )
            
            with self.assertRaises(
                ValidationError, 
                msg=f"Prix {prix_str} aurait dû être invalide"
            ):
                article.full_clean()  # Validation Django

    def test_conversion_mobile(self):
        """
        Simuler la conversion côté mobile (C#)
        """
        test_cases = [
            ('10.50', True),   # Prix standard
            ('0', True),       # Prix zéro
            ('100', True),     # Prix entier
            ('15.999', False), # Trop de décimales
            ('-5.00', False), # Prix négatif
            ('abc', False)     # Invalide
        ]
        
        for prix_str, expected_valid in test_cases:
            try:
                # Simulation de decimal.TryParse
                prix = float(prix_str)
                
                # Vérifications supplémentaires
                if prix < 0:
                    self.assertFalse(expected_valid, f"Prix {prix_str} aurait dû être invalide")
                elif len(prix_str.split('.')[-1]) > 2:
                    self.assertFalse(expected_valid, f"Prix {prix_str} aurait dû être invalide")
                else:
                    self.assertTrue(expected_valid, f"Prix {prix_str} devrait être valide")
            
            except ValueError:
                self.assertFalse(expected_valid, f"Prix {prix_str} aurait dû être valide")
