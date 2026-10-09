"""
Vente à crédit (API Android) :
- article_id + quantite : lien vers le catalogue, prix toujours = prix_vente × quantité
- quantite stockée sur VenteAcompte, article FK renseigné, réponses JSON complètes
- compatibilité : ancien payload (article_nom + prix_total libre) toujours accepté
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, Client as TestClient
from django.urls import reverse

from inventory.models import Article, Boutique, Client, Commercant, VenteAcompte

User = get_user_model()


class CreditCreerVenteCatalogueTestCase(TestCase):
    """Fixtures : boutique, terminal, article du catalogue."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_credit', password='pass1234', email='comm_credit@test.cd'
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='CRED SARL',
            nom_responsable='CRED',
            email='comm_credit@test.cd',
            user=self.user,
        )
        self.boutique = Boutique.objects.create(
            nom='Boutique CRED',
            commercant=self.commercant,
            code_boutique='BT-CRED-001',
        )
        self.terminal = Client.objects.create(
            compte_proprietaire=self.user,
            boutique=self.boutique,
            nom_terminal='T1',
            numero_serie='SERIAL-CRED-001',
            est_actif=True,
        )
        self.article = Article.objects.create(
            code='CRED-1', nom='Televiseur Samsung',
            prix_vente=Decimal('30000'),
            boutique=self.boutique,
            quantite_stock=10,
            est_actif=True, est_valide_client=True,
        )

        self.api = TestClient(SERVER_NAME='127.0.0.1')
        self.entete = {'HTTP_X_DEVICE_SERIAL': 'SERIAL-CRED-001'}
        self.url_creer = reverse('inventory:api_credit_creer_vente', args=[self.boutique.id])

    def _payload(self, **kwargs):
        base = {
            'client_id':    None,
            'nom':          'KABILA',
            'prenom':       'Jean',
            'telephone':    '0810000000',
            'adresse':      'Kinshasa',
            'article_nom':  'Televiseur Samsung',
            'prix_total':   float(Decimal('30000') * 2),
            'seuil_retrait': float(Decimal('30000')),
            'acompte_initial': 0,
            'commentaire':  '',
        }
        base.update(kwargs)
        return base

    # ── Création avec article du catalogue ───────────────────────────────

    def test_creation_avec_article_catalogue(self):
        """article_id + quantite : prix catalogue appliqué, FK article renseigné."""
        resp = self.api.post(
            self.url_creer,
            data=self._payload(article_id=self.article.id, quantite=2),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        vente = VenteAcompte.objects.get()
        self.assertEqual(vente.article, self.article)
        self.assertEqual(vente.quantite, 2)
        self.assertEqual(vente.article_nom, 'Televiseur Samsung')
        self.assertEqual(vente.prix_total, Decimal('60000.00'))
        self.assertEqual(vente.seuil_retrait, Decimal('30000.00'))
        self.assertEqual(vente.statut, 'EN_COURS')
        self.assertEqual(resp.json()['quantite'], 2)

    def test_prix_total_faux_rejete(self):
        """Un prix total qui ne correspond pas au catalogue est refusé."""
        resp = self.api.post(
            self.url_creer,
            data=self._payload(
                article_id=self.article.id, quantite=2,
                prix_total=10000, seuil_retrait=5000,
            ),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('prix catalogue', resp.json()['error'].lower())
        self.assertFalse(VenteAcompte.objects.exists())

    def test_quantite_invalide_rejete(self):
        resp = self.api.post(
            self.url_creer,
            data=self._payload(article_id=self.article.id, quantite=0),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(VenteAcompte.objects.exists())

    def test_article_autre_boutique_rejete(self):
        autre_boutique = Boutique.objects.create(
            nom='Boutique AUTRE', commercant=self.commercant, code_boutique='BT-AUTRE',
        )
        article_autre = Article.objects.create(
            code='AUTRE-1', nom='Article autre boutique',
            prix_vente=Decimal('5000'), boutique=autre_boutique,
            quantite_stock=5, est_actif=True, est_valide_client=True,
        )
        resp = self.api.post(
            self.url_creer,
            data=self._payload(article_id=article_autre.id, quantite=1,
                               prix_total=5000, seuil_retrait=2500),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(VenteAcompte.objects.exists())

    # ── Compatibilité ancien payload ─────────────────────────────────────

    def test_ancien_payload_sans_article_id(self):
        """Sans article_id : article_nom libre, quantite=1, pas de FK article."""
        resp = self.api.post(
            self.url_creer,
            data=self._payload(quantite=None, article_id=None),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        vente = VenteAcompte.objects.get()
        self.assertIsNone(vente.article)
        self.assertEqual(vente.quantite, 1)
        self.assertEqual(vente.prix_total, Decimal('60000.00'))

    # ── Listes / détails ─────────────────────────────────────────────────

    def test_liste_et_detail_incluent_quantite(self):
        self.api.post(
            self.url_creer,
            data=self._payload(article_id=self.article.id, quantite=3,
                               prix_total=float(Decimal('30000') * 3)),
            content_type='application/json', **self.entete,
        )
        vente = VenteAcompte.objects.get()

        liste = self.api.get(f'/api/credit/boutique/{self.boutique.id}/ventes/',
                             **self.entete)
        self.assertEqual(liste.status_code, 200)
        self.assertEqual(liste.json()['ventes'][0]['quantite'], 3)

        detail = self.api.get(f'/api/credit/vente/{vente.id}/', **self.entete)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['quantite'], 3)
        self.assertEqual(detail.json()['prix_total'], 90000.0)
