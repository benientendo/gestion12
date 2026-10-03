"""
Tests de la clôture de journée (terminal MAUI <-> back-office) :
- API /api/v2/simple/cloture/enregistrer/ et /etat/
- Annulation back-office (déblocage du terminal)
- Blocage des mutations (entrées, prix, suppressions) pendant la clôture
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, Client as TestClient
from django.urls import reverse
from django.utils import timezone

from inventory.models import Article, Boutique, ClotureJournee, Client, Commercant

User = get_user_model()


class ClotureJourneeApiTestCase(TestCase):
    """Endpoints API de la clôture (terminal MAUI)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_cj', password='pass1234', email='comm_cj@test.cd'
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='CJ SARL',
            nom_responsable='CJ',
            email='comm_cj@test.cd',
            user=self.user,
        )
        self.boutique = Boutique.objects.create(
            nom='Boutique CJ',
            commercant=self.commercant,
            code_boutique='BT-CJ-001',
        )
        self.terminal = Client.objects.create(
            compte_proprietaire=self.user,
            boutique=self.boutique,
            nom_terminal='T1',
            numero_serie='SERIAL-CJ-001',
            est_actif=True,
        )
        self.api = TestClient(SERVER_NAME='127.0.0.1')
        self.entete = {'HTTP_X_DEVICE_SERIAL': 'SERIAL-CJ-001'}
        self.url_enregistrer = reverse('api_v2_simple:enregistrer_cloture')
        self.url_etat = reverse('api_v2_simple:etat_cloture')

    def _enregistrer(self, nombre=3, total=150000):
        return self.api.post(
            self.url_enregistrer,
            data={
                'boutique_id': self.boutique.id,
                'nombre_ventes': nombre,
                'total_ventes': total,
            },
            content_type='application/json',
            **self.entete,
        )

    def _etat(self, boutique=None):
        return self.api.post(
            self.url_etat,
            data={'boutique_id': (boutique or self.boutique).id},
            content_type='application/json',
            **self.entete,
        )

    def test_enregistrer_cloture(self):
        r = self._enregistrer()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['cloturee'])
        self.assertEqual(r.json()['code'], 'CLOTURE_OK')

        cloture = ClotureJournee.objects.get(boutique=self.boutique)
        self.assertEqual(cloture.statut, ClotureJournee.STATUT_VALIDEE)
        self.assertEqual(cloture.date_jour, timezone.localdate())
        self.assertEqual(cloture.nombre_ventes, 3)
        self.assertEqual(cloture.total_ventes, Decimal('150000'))
        self.assertEqual(cloture.terminal_serial, 'SERIAL-CJ-001')
        self.assertIsNotNone(cloture.date_cloture)

    def test_enregistrer_idempotent(self):
        self._enregistrer()
        r = self._enregistrer()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['code'], 'DEJA_CLOTUREE')
        self.assertEqual(
            ClotureJournee.objects.filter(boutique=self.boutique).count(), 1
        )

    def test_enregistrer_sans_serial_rejete(self):
        r = self.api.post(self.url_enregistrer, data={}, content_type='application/json')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()['code'], 'MISSING_SERIAL')

    def test_serial_inconnu(self):
        r = self.api.post(
            self.url_enregistrer,
            data={'nombre_ventes': 1, 'total_ventes': 1000},
            content_type='application/json',
            HTTP_X_DEVICE_SERIAL='SERIAL-INCONNU-999',
        )
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()['code'], 'TERMINAL_UNAUTHORIZED')

    def test_enregistrer_uniquement_par_serial(self):
        r = self.api.post(
            self.url_enregistrer,
            data={'nombre_ventes': 1, 'total_ventes': 5000},
            content_type='application/json',
            **self.entete,
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(
            ClotureJournee.objects.filter(boutique=self.boutique).exists()
        )

    def test_etat_sans_cloture(self):
        r = self._etat()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['success'])
        self.assertFalse(r.json()['cloturee'])
        self.assertFalse(r.json()['annulee'])

    def test_etat_apres_enregistrement(self):
        self._enregistrer()
        r = self._etat()
        self.assertTrue(r.json()['success'])
        self.assertTrue(r.json()['cloturee'])
        self.assertFalse(r.json()['annulee'])

    def test_etat_apres_annulation(self):
        self._enregistrer()
        ClotureJournee.objects.filter(boutique=self.boutique).update(
            statut=ClotureJournee.STATUT_ANNULEE
        )
        r = self._etat()
        self.assertFalse(r.json()['cloturee'])
        self.assertTrue(r.json()['annulee'])

    def test_cloture_propre_a_la_boutique(self):
        autre = Boutique.objects.create(
            nom='Autre boutique', commercant=self.commercant, code_boutique='BT-CJ-002'
        )
        self._enregistrer()
        r = self._etat(autre)
        self.assertFalse(r.json()['cloturee'])
        self.assertFalse(r.json()['annulee'])


class AnnulationBackofficeTestCase(TestCase):
    """Annulation de la clôture par le commerçant (déblocage du terminal)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_annul', password='pass1234', email='comm_annul@test.cd'
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='Annul SARL',
            nom_responsable='Annul',
            email='comm_annul@test.cd',
            user=self.user,
        )
        self.boutique = Boutique.objects.create(
            nom='Boutique Annul',
            commercant=self.commercant,
            code_boutique='BT-ANN-001',
        )
        self.client_web = TestClient()
        self.url_annuler = reverse(
            'inventory:annuler_cloture_journee', args=[self.boutique.id]
        )
        self.url_detail = reverse(
            'inventory:commercant_detail_boutique', args=[self.boutique.id]
        )
        self.cloture = ClotureJournee.objects.create(
            boutique=self.boutique,
            date_jour=timezone.localdate(),
            statut=ClotureJournee.STATUT_VALIDEE,
            nombre_ventes=2,
            total_ventes=Decimal('90000'),
            date_cloture=timezone.now(),
            terminal_serial='SERIAL-ANN-001',
        )

    def test_annulation_change_statut(self):
        self.client_web.force_login(self.user)
        r = self.client_web.post(self.url_annuler)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, self.url_detail)

        self.cloture.refresh_from_db()
        self.assertEqual(self.cloture.statut, ClotureJournee.STATUT_ANNULEE)
        self.assertIsNotNone(self.cloture.date_annulation)
        self.assertEqual(self.cloture.annulee_par, self.user)

    def test_annulation_debloque_prix(self):
        self.client_web.force_login(self.user)
        self.client_web.post(self.url_annuler)

        r = self.client_web.post(
            reverse(
                'inventory:modifier_prix_article',
                args=[self.boutique.id, 999999],
            ),
            {'prix_vente': '2500'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn('introuvable', r.json()['message'])

    def test_annulation_sans_cloture_active(self):
        self.cloture.delete()
        self.client_web.force_login(self.user)
        r = self.client_web.post(self.url_annuler)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, self.url_detail)
        self.assertFalse(
            ClotureJournee.objects.filter(boutique=self.boutique).exists()
        )

    def test_annulation_get_interdit(self):
        self.client_web.force_login(self.user)
        r = self.client_web.get(self.url_annuler)
        self.assertEqual(r.status_code, 405)
        self.cloture.refresh_from_db()
        self.assertEqual(self.cloture.statut, ClotureJournee.STATUT_VALIDEE)

    def test_annulation_deconnecte_redirige_login(self):
        r = self.client_web.post(self.url_annuler)
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r.url)
        self.cloture.refresh_from_db()
        self.assertEqual(self.cloture.statut, ClotureJournee.STATUT_VALIDEE)


class BlocageMutationsClotureTestCase(TestCase):
    """Pendant la clôture active, entrées et prix sont bloqués côté back-office."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_bloc', password='pass1234', email='comm_bloc@test.cd'
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='Bloc SARL',
            nom_responsable='Bloc',
            email='comm_bloc@test.cd',
            user=self.user,
        )
        self.boutique = Boutique.objects.create(
            nom='Boutique Bloc',
            commercant=self.commercant,
            code_boutique='BT-BLC-001',
        )
        self.article = Article.objects.create(
            code='ART-BLC-1',
            nom='Savon',
            prix_vente=Decimal('1000'),
            boutique=self.boutique,
            quantite_stock=10,
        )
        self.client_web = TestClient()
        self.url_prix = reverse(
            'inventory:modifier_prix_article', args=[self.boutique.id, self.article.id]
        )
        self.url_delete = reverse(
            'inventory:bulk_delete_articles', args=[self.boutique.id]
        )

    def _cloturer(self):
        ClotureJournee.objects.create(
            boutique=self.boutique,
            date_jour=timezone.localdate(),
            statut=ClotureJournee.STATUT_VALIDEE,
            date_cloture=timezone.now(),
        )

    def test_prix_bloque_journee_cloturee(self):
        self._cloturer()
        self.client_web.force_login(self.user)
        r = self.client_web.post(
            self.url_prix,
            {'prix_vente': '2500'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r.status_code, 403)
        data = r.json()
        self.assertFalse(data['success'])
        self.assertIn('cl', data['error'])
        self.article.refresh_from_db()
        self.assertEqual(self.article.prix_vente, Decimal('1000'))

    def test_prix_autorise_journee_ouverte(self):
        self.client_web.force_login(self.user)
        r = self.client_web.post(
            reverse(
                'inventory:modifier_prix_article',
                args=[self.boutique.id, 999999],
            ),
            {'prix_vente': '2500'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['success'])
        self.assertIn('introuvable', r.json()['message'])

    def test_suppression_bloquee_journee_cloturee(self):
        self._cloturer()
        self.client_web.force_login(self.user)
        r = self.client_web.post(
            self.url_delete,
            data='{"article_ids": [%d]}' % self.article.id,
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r.status_code, 403)
        self.assertFalse(r.json()['success'])
        self.assertTrue(
            Article.objects.filter(id=self.article.id).exists()
        )

    def test_cloture_hier_ne_bloque_pas(self):
        ClotureJournee.objects.create(
            boutique=self.boutique,
            date_jour=timezone.localdate() - timezone.timedelta(days=1),
            statut=ClotureJournee.STATUT_VALIDEE,
            date_cloture=timezone.now(),
        )
        self.client_web.force_login(self.user)
        r = self.client_web.post(
            reverse(
                'inventory:modifier_prix_article',
                args=[self.boutique.id, 999999],
            ),
            {'prix_vente': '2500'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn('introuvable', r.json()['message'])

    def test_cloture_annulee_ne_bloque_pas(self):
        ClotureJournee.objects.create(
            boutique=self.boutique,
            date_jour=timezone.localdate(),
            statut=ClotureJournee.STATUT_ANNULEE,
            date_cloture=timezone.now(),
            date_annulation=timezone.now(),
        )
        self.client_web.force_login(self.user)
        r = self.client_web.post(
            reverse(
                'inventory:modifier_prix_article',
                args=[self.boutique.id, 999999],
            ),
            {'prix_vente': '2500'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn('introuvable', r.json()['message'])
