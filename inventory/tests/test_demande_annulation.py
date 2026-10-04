"""
Demande d'annulation (délai de 1 h dépassé) :
- API terminal MAUI : /annulation/demander/, /annulation/etat/,
  /ventes/annuler-ligne/ et prolongation acceptée par /ventes/annuler/
- Back-office : accord (+1 h fixe) / refus, alerte clignotante du dashboard
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, Client as TestClient, RequestFactory
from django.urls import reverse
from django.utils import timezone

from inventory.context_processors import demandes_annulation
from inventory.models import (
    Article, Boutique, Client, Commercant, DemandeAnnulationVente,
    LigneVente, MouvementStock, Vente,
)

User = get_user_model()


class DemandeAnnulationBase(TestCase):
    """Fixtures communes : boutique, terminal, articles, ventes."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_ann', password='pass1234', email='comm_ann@test.cd'
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='ANN SARL',
            nom_responsable='ANN',
            email='comm_ann@test.cd',
            user=self.user,
        )
        self.boutique = Boutique.objects.create(
            nom='Boutique ANN',
            commercant=self.commercant,
            code_boutique='BT-ANN-001',
        )
        self.terminal = Client.objects.create(
            compte_proprietaire=self.user,
            boutique=self.boutique,
            nom_terminal='T1',
            numero_serie='SERIAL-ANN-001',
            est_actif=True,
        )
        self.article = Article.objects.create(
            code='ART-ANN-1',
            nom='Savon',
            prix_vente=Decimal('1000'),
            boutique=self.boutique,
            quantite_stock=10,
        )
        self.article2 = Article.objects.create(
            code='ART-ANN-2',
            nom='Huile',
            prix_vente=Decimal('2000'),
            boutique=self.boutique,
            quantite_stock=5,
        )

        self.api = TestClient(SERVER_NAME='127.0.0.1')
        self.entete = {'HTTP_X_DEVICE_SERIAL': 'SERIAL-ANN-001'}
        self.web = TestClient()
        self._numero = 1

        self.url_demander = reverse('api_v2_simple:demander_annulation')
        self.url_etat = reverse('api_v2_simple:etat_annulation')
        self.url_annuler = reverse('api_v2_simple:annuler_vente')
        self.url_annuler_ligne = reverse('api_v2_simple:annuler_ligne_vente')

    def _creer_vente(self, heures_ecoulees=0, articles=None):
        articles = articles or [(self.article, 2, Decimal('1000'))]
        numero = f'VENT-ANN-{self._numero}'
        self._numero += 1
        vente = Vente.objects.create(
            numero_facture=numero,
            montant_total=Decimal('0'),
            mode_paiement='CASH',
            boutique=self.boutique,
            client_maui=self.terminal,
            devise='CDF',
            paye=True,
            date_vente=timezone.now() - timedelta(hours=heures_ecoulees),
        )
        total = Decimal('0')
        for article, quantite, prix in articles:
            LigneVente.objects.create(
                vente=vente,
                article=article,
                quantite=quantite,
                prix_unitaire=prix,
                devise='CDF',
            )
            total += prix * quantite
        vente.montant_total = total
        vente.save(update_fields=['montant_total'])
        return vente

    def _demander(self, vente, type_demande='FACTURE', article=None, motif=''):
        data = {
            'numero_facture': vente.numero_facture,
            'type_demande': type_demande,
            'motif': motif or 'Erreur de caisse',
        }
        if article is not None:
            data['article_id'] = article.id
        return self.api.post(
            self.url_demander, data=data, content_type='application/json',
            **self.entete
        )

    def _etat(self, vente, type_demande='FACTURE', article=None):
        params = {'numero_facture': vente.numero_facture, 'type_demande': type_demande}
        if article is not None:
            params['article_id'] = article.id
        return self.api.get(self.url_etat, params, **self.entete)


class DemandeAnnulationApiTestCase(DemandeAnnulationBase):
    """Endpoints API du terminal MAUI."""

    def test_demander_annulation_facture(self):
        vente = self._creer_vente(heures_ecoulees=3)
        r = self._demander(vente, motif='Client parti')
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['demande']['statut'], 'EN_ATTENTE')
        self.assertEqual(body['prolongation_minutes'], 60)

        demande = DemandeAnnulationVente.objects.get(vente=vente)
        self.assertEqual(demande.type_demande, 'FACTURE')
        self.assertEqual(demande.statut, 'EN_ATTENTE')
        self.assertEqual(demande.boutique, self.boutique)
        self.assertEqual(demande.terminal, self.terminal)
        self.assertEqual(demande.motif, 'Client parti')

    def test_demander_annulation_article(self):
        vente = self._creer_vente(
            heures_ecoulees=3, articles=[(self.article2, 1, Decimal('2000'))]
        )
        r = self._demander(vente, type_demande='LIGNE', article=self.article2)
        self.assertEqual(r.status_code, 201)
        demande = DemandeAnnulationVente.objects.get(vente=vente)
        self.assertEqual(demande.type_demande, 'LIGNE')
        self.assertEqual(demande.ligne.article, self.article2)
        self.assertEqual(demande.article_nom, 'Huile')

    def test_demander_annulation_article_introuvable(self):
        vente = self._creer_vente(heures_ecoulees=3)
        autre = Article.objects.create(
            code='ART-AUTRE', nom='Inconnu', prix_vente=Decimal('500'),
            boutique=self.boutique, quantite_stock=1,
        )
        r = self._demander(vente, type_demande='LIGNE', article=autre)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()['code'], 'LIGNE_NOT_FOUND')

    def test_demander_est_idempotent(self):
        vente = self._creer_vente(heures_ecoulees=3)
        r1 = self._demander(vente)
        r2 = self._demander(vente)
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()['deja_existante'])
        self.assertEqual(DemandeAnnulationVente.objects.filter(vente=vente).count(), 1)

    def test_etat_dans_le_delai(self):
        vente = self._creer_vente()
        r = self._etat(vente)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body['delai_depasse'])
        self.assertTrue(body['delai_disponible'])
        self.assertTrue(body['peut_annuler'])
        self.assertFalse(body['prolongation_active'])
        self.assertIsNone(body['demande'])

    def test_etat_hors_delai_sans_demande(self):
        vente = self._creer_vente(heures_ecoulees=3)
        r = self._etat(vente)
        body = r.json()
        self.assertTrue(body['delai_depasse'])
        self.assertFalse(body['peut_annuler'])

    def test_annulation_hors_delai_rejetee(self):
        vente = self._creer_vente(heures_ecoulees=3)
        r = self.api.post(
            self.url_annuler,
            data={'numero_facture': vente.numero_facture},
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'CANCELLATION_TIMEOUT')
        self.assertFalse(r.json()['demande_en_attente'])
        vente.refresh_from_db()
        self.assertFalse(vente.est_annulee)

        # Après une demande : le backend signale qu'une demande est en attente
        self._demander(vente)
        r2 = self.api.post(
            self.url_annuler,
            data={'numero_facture': vente.numero_facture},
            content_type='application/json', **self.entete
        )
        self.assertEqual(r2.status_code, 400)
        self.assertTrue(r2.json()['demande_en_attente'])

    def test_annulation_dans_le_delai(self):
        vente = self._creer_vente()
        r = self.api.post(
            self.url_annuler,
            data={'numero_facture': vente.numero_facture, 'motif': 'Erreur'},
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 200)
        vente.refresh_from_db()
        self.assertTrue(vente.est_annulee)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 12)

    def test_prolongation_accordee_debloque_annulation(self):
        vente = self._creer_vente(heures_ecoulees=3)
        self._demander(vente)

        # Le commerçant accorde la prolongation depuis le back-office
        self.web.force_login(self.user)
        r_web = self.web.post(
            reverse('inventory:accorder_extension_annulation', args=[self.boutique.id]),
            {'demande_id': DemandeAnnulationVente.objects.get(vente=vente).id},
        )
        self.assertEqual(r_web.status_code, 302)

        demande = DemandeAnnulationVente.objects.get(vente=vente)
        self.assertEqual(demande.statut, 'ACCEPTEE')
        self.assertEqual(demande.delai_accorde_minutes, 60)
        self.assertAlmostEqual(
            (demande.expire_le - timezone.now()).total_seconds(), 3600, delta=120
        )
        self.assertTrue(demande.prolongation_active)

        # L'état signalé au terminal débloque l'annulation
        r_etat = self._etat(vente)
        body = r_etat.json()
        self.assertTrue(body['prolongation_active'])
        self.assertTrue(body['peut_annuler'])

        r = self.api.post(
            self.url_annuler,
            data={'numero_facture': vente.numero_facture},
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['prolongation_utilisee'])
        vente.refresh_from_db()
        self.assertTrue(vente.est_annulee)

    def test_prolongation_expiree_rejettee(self):
        vente = self._creer_vente(heures_ecoulees=3)
        DemandeAnnulationVente.objects.create(
            boutique=self.boutique,
            terminal=self.terminal,
            vente=vente,
            type_demande='FACTURE',
            numero_facture=vente.numero_facture,
            statut='ACCEPTEE',
            delai_accorde_minutes=60,
            expire_le=timezone.now() - timedelta(minutes=1),
        )
        r = self.api.post(
            self.url_annuler,
            data={'numero_facture': vente.numero_facture},
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'CANCELLATION_TIMEOUT')

    def test_annuler_ligne_dans_le_delai(self):
        vente = self._creer_vente(
            articles=[(self.article, 2, Decimal('1000')),
                      (self.article2, 1, Decimal('2000'))]
        )
        self.assertEqual(vente.montant_total, Decimal('4000'))

        r = self.api.post(
            self.url_annuler_ligne,
            data={'numero_facture': vente.numero_facture, 'article_id': self.article2.id,
                  'motif': 'Mauvais article'},
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['vente']['montant_total'], '2000.00')
        self.assertEqual(body['vente']['lignes_actives'], 1)

        ligne = vente.lignes.get(article=self.article2)
        self.assertTrue(ligne.est_annulee)
        self.assertEqual(ligne.annulee_par, 'T1')
        self.article2.refresh_from_db()
        self.assertEqual(self.article2.quantite_stock, 6)
        self.assertTrue(MouvementStock.objects.filter(
            article=self.article2,
            type_mouvement='RETOUR',
            reference_document=f'ANNUL-LIGNE-{vente.numero_facture}',
        ).exists())

    def test_annuler_ligne_hors_delai_rejetee(self):
        vente = self._creer_vente(heures_ecoulees=3)
        r = self.api.post(
            self.url_annuler_ligne,
            data={'numero_facture': vente.numero_facture, 'article_id': self.article.id},
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'CANCELLATION_TIMEOUT')
        self.assertFalse(vente.lignes.get(article=self.article).est_annulee)

    def test_annuler_ligne_apres_prolongation_article(self):
        vente = self._creer_vente(heures_ecoulees=3)
        self._demander(vente, type_demande='LIGNE', article=self.article)

        demande = DemandeAnnulationVente.objects.get(vente=vente)
        self.web.force_login(self.user)
        self.web.post(
            reverse('inventory:accorder_extension_annulation', args=[self.boutique.id]),
            {'demande_id': demande.id},
        )

        r = self.api.post(
            self.url_annuler_ligne,
            data={'numero_facture': vente.numero_facture, 'article_id': self.article.id},
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['prolongation_utilisee'])
        self.assertTrue(vente.lignes.get(article=self.article).est_annulee)

    def test_annuler_ligne_deja_annulee(self):
        vente = self._creer_vente()
        self.api.post(
            self.url_annuler_ligne,
            data={'numero_facture': vente.numero_facture, 'article_id': self.article.id},
            content_type='application/json', **self.entete
        )
        r = self.api.post(
            self.url_annuler_ligne,
            data={'numero_facture': vente.numero_facture, 'article_id': self.article.id},
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()['code'], 'LIGNE_NOT_FOUND')

    def test_serial_requis(self):
        vente = self._creer_vente()
        r = self.api.post(
            self.url_demander, data={'numero_facture': vente.numero_facture},
            content_type='application/json'
        )
        self.assertIn(r.status_code, (400, 401, 403))


class DemandeAnnulationBackOfficeTestCase(DemandeAnnulationBase):
    """Vues commerçant + alerte du back-office."""

    def setUp(self):
        super().setUp()
        self.vente = self._creer_vente(heures_ecoulees=3)
        self.demande = DemandeAnnulationVente.objects.create(
            boutique=self.boutique,
            terminal=self.terminal,
            vente=self.vente,
            type_demande='FACTURE',
            numero_facture=self.vente.numero_facture,
            motif='Erreur de caisse',
        )
        self.web.force_login(self.user)

    def test_accorder_extension(self):
        r = self.web.post(
            reverse('inventory:accorder_extension_annulation', args=[self.boutique.id]),
            {'demande_id': self.demande.id},
        )
        self.assertEqual(r.status_code, 302)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.statut, 'ACCEPTEE')
        self.assertEqual(self.demande.traite_par, self.user)
        self.assertIsNotNone(self.demande.date_traitement)
        self.assertEqual(self.demande.delai_accorde_minutes, 60)

    def test_refuser_demande(self):
        r = self.web.post(
            reverse('inventory:refuser_demande_annulation', args=[self.boutique.id]),
            {'demande_id': self.demande.id, 'reponse': 'Pas de temps'},
        )
        self.assertEqual(r.status_code, 302)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.statut, 'REFUSEE')
        self.assertEqual(self.demande.reponse, 'Pas de temps')
        self.assertEqual(self.demande.traite_par, self.user)

    def test_refus_invalide_si_deja_traitee(self):
        self.demande.statut = 'REFUSEE'
        self.demande.save(update_fields=['statut'])
        r = self.web.post(
            reverse('inventory:refuser_demande_annulation', args=[self.boutique.id]),
            {'demande_id': self.demande.id},
        )
        self.assertEqual(r.status_code, 302)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.statut, 'REFUSEE')
        self.assertEqual(self.demande.reponse, '')

    def test_action_interdite_hors_boutique(self):
        autre_user = User.objects.create_user(
            username='comm_autre', password='pass1234', email='comm_autre@test.cd'
        )
        autre_commercant = Commercant.objects.create(
            nom_entreprise='AUTRE SARL', nom_responsable='AUTRE',
            email='comm_autre@test.cd', user=autre_user,
        )
        autre_boutique = Boutique.objects.create(
            nom='Boutique AUTRE', commercant=autre_commercant,
            code_boutique='BT-AUT-001',
        )
        self.web.force_login(autre_user)
        # Un autre commerçant ne peut pas traiter la demande d'une boutique étrangère
        r = self.web.post(
            reverse('inventory:accorder_extension_annulation', args=[self.boutique.id]),
            {'demande_id': self.demande.id},
        )
        self.assertEqual(r.status_code, 404)
        self.demande.refresh_from_db()
        self.assertEqual(self.demande.statut, 'EN_ATTENTE')

    def test_get_interdit(self):
        r = self.web.get(
            reverse('inventory:accorder_extension_annulation', args=[self.boutique.id])
        )
        self.assertEqual(r.status_code, 405)

    def test_context_processor_compte_les_demandes(self):
        request = RequestFactory().get('/')
        request.user = self.user
        context = demandes_annulation(request)
        self.assertEqual(context['demandes_annulation_count'], 1)
        self.assertEqual(len(context['demandes_annulation_en_attente']), 1)
        self.assertEqual(context['demandes_annulation_en_attente'][0].id, self.demande.id)

    def test_dashboard_affiche_la_banniere(self):
        r = self.web.get(reverse('inventory:commercant_dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "demande(s) d'annulation en attente")
        self.assertContains(r, self.vente.numero_facture)

    def test_dashboard_sans_demande_pas_de_banniere(self):
        DemandeAnnulationVente.objects.all().delete()
        r = self.web.get(reverse('inventory:commercant_dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "demande(s) d'annulation en attente")
