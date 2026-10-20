import importlib
from decimal import Decimal

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from inventory.models import Article, Boutique, Commercant, Conditionnement


class ReparerAttributsRecusTest(TestCase):

    def setUp(self):
        user = get_user_model().objects.create_user(username='repair_0082', password='x')
        self.commercant = Commercant.objects.create(
            nom_entreprise='REPAIR 0082',
            nom_responsable='Test',
            email='repair0082@example.com',
            user=user,
        )
        self.source = Boutique.objects.create(
            nom='SOURCE 0082',
            commercant=self.commercant,
            type_commerce='BOUCHERIE',
            code_boutique='REPAIR0082-SRC',
            cle_api_boutique='repair0082-src',
        )
        self.destination = Boutique.objects.create(
            nom='DESTINATION 0082',
            commercant=self.commercant,
            type_commerce='BOUCHERIE',
            code_boutique='REPAIR0082-DST',
            cle_api_boutique='repair0082-dst',
        )
        self.article_source = Article.objects.create(
            code='REPAIR0082-SRC-1',
            nom='cuisse',
            boutique=self.source,
            prix_vente=Decimal('0'),
            unite_base='kg',
            est_valide_client=True,
        )
        Conditionnement.objects.create(
            article=self.article_source, libelle='kg', coefficient=1, prix_vente=Decimal('5000'),
        )
        Conditionnement.objects.create(
            article=self.article_source, libelle='demi', coefficient=5, prix_vente=Decimal('25000'),
        )
        self.article_destination = Article.objects.create(
            code='REPAIR0082-DST-1',
            nom='cuisse',
            boutique=self.destination,
            prix_vente=Decimal('3500'),
            unite_base='',
            est_valide_client=True,
        )

    def test_tous_les_articles_recus_heritent_des_unites(self):
        migration = importlib.import_module('inventory.migrations.0082_reparer_attributs_articles_recus')
        migration.reparer_attributs(apps, None)

        self.article_destination.refresh_from_db()

        self.assertEqual(self.article_destination.unite_base, 'kg')
        self.assertEqual(self.article_destination.prix_vente, Decimal('3500.00'))
        libelles = list(
            self.article_destination.conditionnements
            .order_by('coefficient')
            .values_list('libelle', flat=True)
        )
        self.assertEqual(libelles, ['kg', 'demi'])
