"""
Tests du code de clôture de journée :
- Endpoint API /api/v2/simple/cloture/verifier-code/ (terminal MAUI)
- Vue back-office de génération du code (commerçant)
"""
from datetime import timedelta

from django.test import TestCase, Client as TestClient
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from inventory.models import Boutique, Client, CodeCloture, Commercant

User = get_user_model()


class CodeClotureApiTestCase(TestCase):
    """Tests de l'endpoint de vérification du code de clôture."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_cloture', password='pass1234', email='comm_cloture@test.cd'
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='Test SARL',
            nom_responsable='Test',
            email='comm_cloture@test.cd',
            user=self.user,
        )
        self.boutique = Boutique.objects.create(
            nom='Boutique Test',
            commercant=self.commercant,
            code_boutique='BT-CLT-001',
        )
        self.terminal = Client.objects.create(
            compte_proprietaire=self.user,
            boutique=self.boutique,
            nom_terminal='Terminal Caisse',
            numero_serie='SERIAL-CLT-001',
            est_actif=True,
        )
        self.api = TestClient(SERVER_NAME='127.0.0.1')
        self.url = reverse('api_v2_simple:verifier_code_cloture')
        self.entete = {'HTTP_X_DEVICE_SERIAL': 'SERIAL-CLT-001'}

    def _creer_code(self, code='123456', date_jour=None, actif=True):
        return CodeCloture.objects.create(
            boutique=self.boutique,
            code=code,
            date_jour=date_jour or timezone.localdate(),
            actif=actif,
            genere_par=self.user,
        )

    def test_code_valide(self):
        self._creer_code('123456')
        r = self.api.post(self.url, data={'boutique_id': self.boutique.id, 'code': '123456'},
                          content_type='application/json', **self.entete)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['valide'])
        self.assertEqual(r.json()['code'], 'CODE_OK')

    def test_code_valide_insensible_casse(self):
        self._creer_code('Ab12Cd')
        r = self.api.post(self.url, data={'boutique_id': self.boutique.id, 'code': 'AB12CD'},
                          content_type='application/json', **self.entete)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['valide'])

    def test_code_invalide(self):
        self._creer_code('123456')
        r = self.api.post(self.url, data={'boutique_id': self.boutique.id, 'code': '999999'},
                          content_type='application/json', **self.entete)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['valide'])
        self.assertEqual(r.json()['code'], 'CODE_INVALID')

    def test_aucun_code_du_jour(self):
        r = self.api.post(self.url, data={'boutique_id': self.boutique.id, 'code': '123456'},
                          content_type='application/json', **self.entete)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['valide'])
        self.assertEqual(r.json()['code'], 'NO_CODE')

    def test_code_jour_precedent_rejete(self):
        hier = timezone.localdate() - timedelta(days=1)
        self._creer_code('123456', date_jour=hier)
        r = self.api.post(self.url, data={'boutique_id': self.boutique.id, 'code': '123456'},
                          content_type='application/json', **self.entete)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['valide'])
        self.assertEqual(r.json()['code'], 'NO_CODE')

    def test_code_inactif_rejete(self):
        self._creer_code('123456', actif=False)
        r = self.api.post(self.url, data={'boutique_id': self.boutique.id, 'code': '123456'},
                          content_type='application/json', **self.entete)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['valide'])
        self.assertEqual(r.json()['code'], 'NO_CODE')

    def test_boutique_du_terminal_sans_boutique_id(self):
        self._creer_code('123456')
        r = self.api.post(self.url, data={'code': '123456'},
                          content_type='application/json', **self.entete)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['valide'])

    def test_serial_requis(self):
        self._creer_code('123456')
        r = self.api.post(self.url, data={'boutique_id': self.boutique.id, 'code': '123456'},
                          content_type='application/json')
        self.assertEqual(r.status_code, 401)

    def test_code_requis(self):
        r = self.api.post(self.url, data={'boutique_id': self.boutique.id},
                          content_type='application/json', **self.entete)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'MISSING_CODE')


class GenerationCodeClotureBackofficeTestCase(TestCase):
    """Tests de la vue back-office de génération du code."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_gen', password='pass1234', email='comm_gen@test.cd'
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='Gen SARL',
            nom_responsable='Gen',
            email='comm_gen@test.cd',
            user=self.user,
        )
        self.boutique = Boutique.objects.create(
            nom='Boutique Gen',
            commercant=self.commercant,
            code_boutique='BT-GEN-001',
        )
        self.client_web = TestClient()
        self.url = reverse('inventory:generer_code_cloture', args=[self.boutique.id])

    def test_generation_cree_code_actif(self):
        self.client_web.force_login(self.user)
        r = self.client_web.post(self.url)
        self.assertEqual(r.status_code, 302)

        code = CodeCloture.objects.get(boutique=self.boutique)
        self.assertTrue(code.actif)
        self.assertEqual(code.date_jour, timezone.localdate())
        self.assertEqual(code.genere_par, self.user)
        self.assertEqual(len(code.code), 6)
        self.assertTrue(code.code.isdigit())

    def test_regeneration_invalide_ancien_code(self):
        self.client_web.force_login(self.user)
        ancien = CodeCloture.objects.create(
            boutique=self.boutique, code='111111',
            date_jour=timezone.localdate(), actif=True, genere_par=self.user,
        )
        self.client_web.post(self.url)

        ancien.refresh_from_db()
        self.assertFalse(ancien.actif)
        nouveaux = CodeCloture.objects.filter(boutique=self.boutique, actif=True)
        self.assertEqual(nouveaux.count(), 1)
        self.assertNotEqual(nouveaux.first().code, '111111')

    def test_code_affiche_sur_page_boutique(self):
        self.client_web.force_login(self.user)
        CodeCloture.objects.create(
            boutique=self.boutique, code='654321',
            date_jour=timezone.localdate(), actif=True, genere_par=self.user,
        )
        url_detail = reverse('inventory:commercant_detail_boutique', args=[self.boutique.id])
        r = self.client_web.get(url_detail)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '654321')
        self.assertIsNotNone(r.context.get('code_cloture_dujour'))

    def test_acces_non_authentifie_redirige(self):
        r = self.client_web.post(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(CodeCloture.objects.count(), 0)
