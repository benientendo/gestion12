from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from inventory.models import (
    Article,
    Boutique,
    Client,
    Commercant,
    Conditionnement,
    TransfertStock,
)


class TransfertAttributsTestCase(TestCase):
    """Un transfert ne doit pas écraser les prix/unités du destinataire
    sauf demande explicite du terminal source.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_transfert', password='pass1234',
            email='comm_transfert@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='TRANSFERT', nom_responsable='TRANS',
            email='comm_transfert@test.cd', user=self.user,
        )
        self.source = Boutique.objects.create(
            nom='Boucherie Source', commercant=self.commercant,
            code_boutique='BT-SRC-001', type_commerce='BOUCHERIE',
        )
        self.dest = Boutique.objects.create(
            nom='Boucherie Destination', commercant=self.commercant,
            code_boutique='BT-DST-001', type_commerce='BOUCHERIE',
        )
        self.terminal = Client.objects.create(
            compte_proprietaire=self.user, boutique=self.source,
            nom_terminal='Terminal source', numero_serie='SER-SRC-001',
        )

        self.article_source = Article.objects.create(
            boutique=self.source, nom='Poisson', code='POISSON-1',
            prix_vente=Decimal('100'), prix_achat=Decimal('10'),
            devise='CDF', quantite_stock=100, est_actif=True,
            est_valide_client=True, unite_base='kg',
        )
        Conditionnement.objects.create(
            article=self.article_source, libelle='kg', coefficient=1,
            prix_vente=Decimal('100'), ordre=0,
        )
        Conditionnement.objects.create(
            article=self.article_source, libelle='demi', coefficient=5,
            prix_vente=Decimal('500'), ordre=1,
        )
        Conditionnement.objects.create(
            article=self.article_source, libelle='carton', coefficient=30,
            prix_vente=Decimal('3000'), ordre=2,
        )

        self.article_dest = Article.objects.create(
            boutique=self.dest, nom='Poisson', code='POISSON-1',
            prix_vente=Decimal('200'), prix_achat=Decimal('20'),
            devise='CDF', quantite_stock=5, est_actif=True,
            est_valide_client=True, unite_base='kg',
        )
        Conditionnement.objects.create(
            article=self.article_dest, libelle='kg', coefficient=1,
            prix_vente=Decimal('250'), ordre=0,
        )
        Conditionnement.objects.create(
            article=self.article_dest, libelle='carton', coefficient=30,
            prix_vente=Decimal('9000'), ordre=1,
        )
        Conditionnement.objects.create(
            article=self.article_dest, libelle='sac', coefficient=25,
            prix_vente=Decimal('5000'), ordre=2,
        )

    def _creer_transfert(self, quantite=10):
        return TransfertStock.objects.create(
            article=self.article_source,
            depot_source=self.source,
            boutique_destination=self.dest,
            quantite=quantite,
            effectue_par='Terminal test',
        )

    def test_par_defaut_le_destinataire_garde_ses_prix_et_unites(self):
        transfert = self._creer_transfert()
        article_dest = transfert.valider_transfert('test')

        self.assertEqual(article_dest.prix_vente, Decimal('200'))
        self.assertEqual(article_dest.prix_achat, Decimal('20'))
        self.assertEqual(
            article_dest.conditionnements.get(libelle='kg').prix_vente,
            Decimal('250'),
        )
        self.assertEqual(
            article_dest.conditionnements.get(libelle='carton').prix_vente,
            Decimal('9000'),
        )
        self.assertFalse(article_dest.conditionnements.filter(libelle='demi').exists())
        self.assertEqual(article_dest.quantite_stock, 5)
        self.assertEqual(article_dest.quantite_envoyee, 10)
        self.assertFalse(article_dest.est_valide_client)

    def test_ecrasement_selectif_dune_unite(self):
        transfert = self._creer_transfert()
        article_dest = transfert.valider_transfert(
            'test', ecraser_attributs=True, unites_a_ecraser=['carton'],
        )

        self.assertEqual(article_dest.prix_vente, Decimal('100'))
        self.assertEqual(article_dest.prix_achat, Decimal('10'))
        self.assertEqual(
            article_dest.conditionnements.get(libelle='carton').prix_vente,
            Decimal('3000'),
        )
        self.assertEqual(
            article_dest.conditionnements.get(libelle='kg').prix_vente,
            Decimal('250'),
        )
        self.assertFalse(article_dest.conditionnements.filter(libelle='demi').exists())
        self.assertTrue(article_dest.conditionnements.filter(libelle='sac').exists())

    def test_ecrasement_total_prix_et_unites(self):
        transfert = self._creer_transfert()
        article_dest = transfert.valider_transfert('test', ecraser_attributs=True)

        self.assertEqual(article_dest.prix_vente, Decimal('100'))
        self.assertEqual(
            article_dest.conditionnements.get(libelle='kg').prix_vente,
            Decimal('100'),
        )
        self.assertEqual(
            article_dest.conditionnements.get(libelle='demi').prix_vente,
            Decimal('500'),
        )
        self.assertEqual(
            article_dest.conditionnements.get(libelle='carton').prix_vente,
            Decimal('3000'),
        )
        self.assertTrue(article_dest.conditionnements.filter(libelle='sac').exists())

    def test_nouvel_article_destination_recoit_les_attributs_source(self):
        article_dest = Article.objects.get(id=self.article_dest.id)
        article_dest.delete()

        transfert = self._creer_transfert()
        article_dest = transfert.valider_transfert('test')

        self.assertEqual(article_dest.prix_vente, Decimal('100'))
        self.assertEqual(article_dest.unite_base, 'kg')
        self.assertEqual(
            set(article_dest.conditionnements.values_list('libelle', flat=True)),
            {'kg', 'demi', 'carton'},
        )
        self.assertEqual(article_dest.conditionnements.get(libelle='demi').prix_vente,
                         Decimal('500'))

    def test_api_sans_option_conserve_les_prix_destination(self):
        api = APIClient()
        response = api.post(
            reverse('api_maui_desktop:transfert_entre_boutiques'),
            {
                'boutique_destination_id': self.dest.id,
                'lignes': [{'article_id': self.article_source.id, 'quantite': 3}],
            },
            format='json',
            HTTP_X_DEVICE_SERIAL=self.terminal.numero_serie,
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['success'])
        self.article_dest.refresh_from_db()
        self.assertEqual(self.article_dest.prix_vente, Decimal('200'))
        self.assertEqual(
            self.article_dest.conditionnements.get(libelle='carton').prix_vente,
            Decimal('9000'),
        )

    def test_api_avec_option_ecrase_les_unites_choisies(self):
        api = APIClient()
        response = api.post(
            reverse('api_maui_desktop:transfert_entre_boutiques'),
            {
                'boutique_destination_id': self.dest.id,
                'lignes': [{
                    'article_id': self.article_source.id,
                    'quantite': 3,
                    'ecraser_prix_unites': True,
                    'unites_a_ecraser': ['carton'],
                }],
            },
            format='json',
            HTTP_X_DEVICE_SERIAL=self.terminal.numero_serie,
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['transferts'][0]['attributs_ecrases'])
        self.article_dest.refresh_from_db()
        self.assertEqual(self.article_dest.prix_vente, Decimal('100'))
        self.assertEqual(
            self.article_dest.conditionnements.get(libelle='carton').prix_vente,
            Decimal('3000'),
        )
        self.assertEqual(
            self.article_dest.conditionnements.get(libelle='kg').prix_vente,
            Decimal('250'),
        )
