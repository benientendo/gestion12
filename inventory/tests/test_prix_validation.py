from django.test import TestCase
from django.core.exceptions import ValidationError
from inventory.models import Article, Categorie

class PrixValidationTestCase(TestCase):
    def setUp(self):
        # Créer une catégorie de test
        self.categorie = Categorie.objects.create(nom='Catégorie Test')

    def test_prix_valides(self):
        """
        Tester les prix valides
        """
        prix_valides = [
            '10.50',   # Prix standard
            '0',       # Prix zéro
            '100',     # Prix entier
            '15.75'    # Prix avec deux décimales
        ]
        
        for prix in prix_valides:
            article = Article(
                code=f'test_code_{prix}',
                nom=f'Article Test {prix}',
                prix_vente=prix,
                prix_achat='0',
                categorie=self.categorie,
                quantite_stock=10
            )
            
            try:
                article.full_clean()  # Validation Django
                article.save()
                print(f"Prix {prix} validé avec succès")
            except ValidationError as e:
                self.fail(f"Prix {prix} invalide : {e}")

    def test_prix_invalides(self):
        """
        Tester les prix invalides
        """
        prix_invalides = [
            '-5.00',   # Prix négatif
            '15.999',  # Trop de décimales
            'abc',     # Invalide
            '10,50',   # Virgule au lieu de point
            ''         # Vide
        ]
        
        for prix in prix_invalides:
            article = Article(
                code=f'test_code_{prix}',
                nom=f'Article Test {prix}',
                prix_vente=prix,
                prix_achat='0',
                categorie=self.categorie,
                quantite_stock=10
            )
            
            with self.assertRaises(
                ValidationError, 
                msg=f"Prix {prix} aurait dû être invalide"
            ):
                article.full_clean()  # Validation Django

    def test_conversion_prix(self):
        """
        Tester la conversion et l'arrondi des prix
        """
        test_cases = [
            ('10.555', '10.56'),  # Arrondi à 2 décimales
            ('10.50', '10.50'),   # Pas de changement
            ('10', '10.00')       # Ajout de décimales
        ]
        
        for input_prix, expected_prix in test_cases:
            article = Article(
                code=f'test_code_{input_prix}',
                nom=f'Article Test {input_prix}',
                prix_vente=input_prix,
                prix_achat='0',
                categorie=self.categorie,
                quantite_stock=10
            )
            
            try:
                article.full_clean()
                # Vérifier que le prix est bien converti
                self.assertEqual(
                    str(article.prix_vente), 
                    expected_prix, 
                    f"Conversion incorrecte pour {input_prix}"
                )
            except ValidationError as e:
                self.fail(f"Erreur de conversion pour {input_prix} : {e}")

    def test_limite_decimales(self):
        """
        Tester la limitation des décimales
        """
        prix_trop_precis = '10.555'
        
        article = Article(
            code='test_code_precis',
            nom='Article Test Précision',
            prix_vente=prix_trop_precis,
            prix_achat='0',
            categorie=self.categorie,
            quantite_stock=10
        )
        
        with self.assertRaises(
            ValidationError, 
            msg="Prix avec trop de décimales aurait dû être rejeté"
        ):
            article.full_clean()
