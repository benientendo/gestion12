"""Cohérence de la recette : service unique, API de clôture et stock précédent."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, Client as TestClient
from django.urls import reverse
from django.utils import timezone

from inventory.api_views_v2_simple import _compute_dashboard_stats
from inventory.cloture_service import resume_journee, resume_periode
from inventory.journal_valeur_stock import (
    enregistrer_vente,
    recalculer_tout_depuis_debut,
)
from inventory.models import (
    Article,
    Boutique,
    Client,
    ClotureJournee,
    Commercant,
    JournalValeurStock,
    LigneVente,
    RapportCaisse,
    Vente,
)

User = get_user_model()


class ClotureServiceBase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_cs', password='pass1234', email='comm_cs@test.cd'
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='CS SARL',
            nom_responsable='CS',
            email='comm_cs@test.cd',
            user=self.user,
        )
        self.boutique = Boutique.objects.create(
            nom='Boutique CS',
            commercant=self.commercant,
            code_boutique='BT-CS-001',
        )
        self.terminal = Client.objects.create(
            compte_proprietaire=self.user,
            boutique=self.boutique,
            nom_terminal='T1',
            numero_serie='SERIAL-CS-001',
            est_actif=True,
        )
        self.article = Article.objects.create(
            code='ART-CS-1',
            nom='Article CS',
            prix_vente=Decimal('100'),
            prix_achat=Decimal('50'),
            boutique=self.boutique,
            quantite_stock=10,
            devise='CDF',
        )
        self._numero = 1

    def _creer_vente(self, montant, devise='CDF', date=None, prix_unitaire=None):
        date = date or timezone.now()
        prix = Decimal(str(prix_unitaire if prix_unitaire is not None else montant))
        vente = Vente.objects.create(
            numero_facture=f'VENT-CS-{self._numero}',
            montant_total=Decimal('0') if devise == 'USD' else Decimal(str(montant)),
            montant_total_usd=Decimal(str(montant)) if devise == 'USD' else None,
            mode_paiement='CASH',
            boutique=self.boutique,
            client_maui=self.terminal,
            devise=devise,
            paye=True,
            date_vente=date,
        )
        self._numero += 1
        LigneVente.objects.create(
            vente=vente,
            article=self.article,
            quantite=1,
            prix_unitaire=Decimal('0') if devise == 'USD' else prix,
            prix_unitaire_usd=prix if devise == 'USD' else None,
            devise=devise,
        )
        return vente

    def _depense(self, montant, devise='CDF'):
        return RapportCaisse.objects.create(
            boutique=self.boutique,
            terminal=self.terminal,
            date_rapport=timezone.now(),
            detail='Dépense test',
            depense=Decimal(str(montant)),
            devise=devise,
            depense_appliquee=True,
        )


class RecetteServiceTestCase(ClotureServiceBase):

    def test_cdf_et_usd_avec_depenses(self):
        self._creer_vente(2000, 'CDF')
        self._creer_vente(5, 'USD')
        self._depense(500, 'CDF')
        self._depense(2, 'USD')

        recette = resume_journee(self.boutique)

        self.assertEqual(recette['recette']['cdf']['ventes_brutes'], 2000.0)
        self.assertEqual(recette['recette']['cdf']['depenses'], 500.0)
        self.assertEqual(recette['recette']['cdf']['recette_nette'], 1500.0)
        self.assertEqual(recette['recette']['usd']['ventes_brutes'], 5.0)
        self.assertEqual(recette['recette']['usd']['depenses'], 2.0)
        self.assertEqual(recette['recette']['usd']['recette_nette'], 3.0)
        self.assertEqual(
            recette['recette']['cdf']['nb_ventes']
            + recette['recette']['usd']['nb_ventes'],
            2,
        )

    def test_remboursement_impute_au_jour_annulation(self):
        hier = timezone.localdate() - timedelta(days=1)
        vente = self._creer_vente(
            2000, 'CDF', date=timezone.now() - timedelta(days=1)
        )
        annulation = timezone.now()
        ligne = vente.lignes.get()
        ligne.est_annulee = True
        ligne.date_annulation = annulation
        ligne.save(update_fields=['est_annulee', 'date_annulation'])
        vente.est_annulee = True
        vente.date_annulation = annulation
        vente.save(update_fields=['est_annulee', 'date_annulation'])

        recette_hier = resume_periode(self.boutique, hier, hier)['cdf']
        recette_jour = resume_periode(
            self.boutique, timezone.localdate(), timezone.localdate()
        )['cdf']

        self.assertEqual(recette_hier['ventes_brutes'], Decimal('2000'))
        self.assertEqual(recette_hier['remboursements'], Decimal('0'))
        self.assertEqual(recette_hier['recette_nette'], Decimal('2000'))
        self.assertEqual(recette_jour['remboursements'], Decimal('2000'))
        self.assertEqual(recette_jour['recette_nette'], Decimal('-2000'))

    def test_dashboard_utilise_la_meme_recette(self):
        self._creer_vente(2000, 'CDF')
        self._creer_vente(5, 'USD')
        self._depense(500, 'CDF')

        stats = _compute_dashboard_stats(self.boutique)
        recette = resume_journee(self.boutique)

        self.assertEqual(stats['ca_jour'], recette['recette']['cdf']['recette_nette'])
        self.assertEqual(
            stats['ca_jour_usd'], recette['recette']['usd']['recette_nette']
        )
        self.assertEqual(stats['nb_ventes_jour'], 2)

    def test_dashboard_et_rapport_affichent_la_meme_recette(self):
        self._creer_vente(2000, 'CDF')
        self._depense(500, 'CDF')
        self.client = TestClient()
        self.client.force_login(self.user)

        dashboard = self.client.get(reverse('inventory:commercant_dashboard'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.context['recette_jour'], Decimal('1500'))

        rapport = self.client.get(
            reverse('inventory:rapport_ca_quotidien', args=[self.boutique.id])
        )
        self.assertEqual(rapport.status_code, 200)
        self.assertEqual(rapport.context['total_ca'], Decimal('1500'))
        self.assertEqual(rapport.context['total_ca_brut'], Decimal('2000'))


class ResumeClotureApiTestCase(ClotureServiceBase):

    def setUp(self):
        super().setUp()
        self.api = TestClient(SERVER_NAME='127.0.0.1')
        self.entete = {'HTTP_X_DEVICE_SERIAL': 'SERIAL-CS-001'}
        self.url = reverse('api_v2_simple:resume_cloture')

    def test_resume_renvoie_les_memes_montants_que_le_dashboard(self):
        self._creer_vente(2000, 'CDF')
        self._creer_vente(5, 'USD')
        self._depense(500, 'CDF')

        r = self.api.get(
            self.url, {'boutique_id': self.boutique.id}, **self.entete
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body['success'])

        stats = _compute_dashboard_stats(self.boutique)
        self.assertEqual(body['resume']['recette']['cdf']['recette_nette'], stats['ca_jour'])
        self.assertEqual(
            body['resume']['recette']['usd']['recette_nette'], stats['ca_jour_usd']
        )
        self.assertFalse(body['cloture']['cloturee'])

    def test_enregistrer_utilise_les_valeurs_serveur(self):
        self._creer_vente(2000, 'CDF')
        url = reverse('api_v2_simple:enregistrer_cloture')

        r = self.api.post(
            url,
            data={
                'boutique_id': self.boutique.id,
                'nombre_ventes': 99,
                'total_ventes': 999999,
            },
            content_type='application/json',
            **self.entete,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['source'], 'serveur')
        self.assertFalse(r.json()['ecart_terminal'] is None)

        cloture = ClotureJournee.objects.get(boutique=self.boutique)
        self.assertEqual(cloture.nombre_ventes, 1)
        self.assertEqual(cloture.total_ventes, Decimal('2000'))

    def test_enregistrer_sans_vente_synchronisee_garde_le_terminal(self):
        url = reverse('api_v2_simple:enregistrer_cloture')
        r = self.api.post(
            url,
            data={
                'boutique_id': self.boutique.id,
                'nombre_ventes': 3,
                'total_ventes': 150000,
            },
            content_type='application/json',
            **self.entete,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['source'], 'terminal')

        cloture = ClotureJournee.objects.get(boutique=self.boutique)
        self.assertEqual(cloture.nombre_ventes, 3)
        self.assertEqual(cloture.total_ventes, Decimal('150000'))


class StockPrecedentTestCase(ClotureServiceBase):

    def test_sync_antidatee_propage_le_stock_restant(self):
        hier = timezone.localdate() - timedelta(days=1)
        # Le stock initial de l'article a créé une ligne d'ouverture
        # aujourd'hui ; on l'isole pour tester la chaîne hier -> aujourd'hui.
        JournalValeurStock.objects.filter(
            boutique=self.boutique, date=timezone.localdate()
        ).delete()
        JournalValeurStock.objects.create(
            boutique=self.boutique,
            date=hier,
            valeur_stock_precedent=Decimal('10000'),
            valeur_stock_ajoute=Decimal('5000'),
            valeur_ventes=Decimal('2000'),
            valeur_stock_reel=Decimal('13000'),
        )

        enregistrer_vente(self.boutique, Decimal('1000'))
        ligne_jour = JournalValeurStock.objects.get(
            boutique=self.boutique, date=timezone.localdate()
        )
        self.assertEqual(ligne_jour.valeur_stock_precedent, Decimal('13000'))
        self.assertEqual(ligne_jour.valeur_stock_restant, Decimal('12000'))

        # Synchronisation retardée d'une vente de la veille.
        enregistrer_vente(self.boutique, Decimal('500'), date=hier)

        ligne_hier = JournalValeurStock.objects.get(
            boutique=self.boutique, date=hier
        )
        ligne_jour.refresh_from_db()

        self.assertEqual(ligne_hier.valeur_ventes, Decimal('2500'))
        self.assertEqual(ligne_hier.valeur_stock_restant, Decimal('12500'))
        self.assertEqual(ligne_jour.valeur_stock_precedent, Decimal('12500'))
        self.assertEqual(ligne_jour.valeur_stock_restant, Decimal('11500'))
        # Le stock réel d'hier n'est pas écrasé par le stock live.
        self.assertEqual(ligne_hier.valeur_stock_reel, Decimal('13000'))

        recalculer_tout_depuis_debut(self.boutique)
        ligne_jour.refresh_from_db()
        self.assertEqual(ligne_jour.valeur_stock_precedent, Decimal('12500'))
        self.assertEqual(ligne_jour.valeur_stock_restant, Decimal('11500'))
