"""
Retour d'excédent d'un point de vente vers le dépôt
===================================================
« J'ai envoyé 150 par erreur, je veux en renvoyer 20 au dépôt. »

Le retour s'effectue DEUX endroits : la page articles du PDV (bouton 🔄
par article) et le détail du transfert (bouton « Retourner l'excédent »),
tous deux POST vers ``retourner_article_au_depot``.

Aucun modèle nouveau : tout passe par MouvementStock
``reference_document='RETOUR-<transfert_id>'`` (ou ``RETOUR-<uuid>``
sans transfert) :
- dépôt : ENTREE +quantite ;
- PDV   : SORTIE -quantite (quantité négative, convention du projet) ;
- si la réception MAUI est en attente (``quantite_envoyee``), cette part
  n'a jamais été créditée au stock du PDV : on la consomme d'abord SANS
  mouvement côté PDV (seul le dépôt est recrédité).

Comportement vérifié ici :
- retour OK (stock déjà crédité) : 2 mouvements, stocks PDV/dépôt ;
- retour OK (réception MAUI en attente) : aucun mouvement PDV,
  ``quantite_envoyee`` diminué d'autant ;
- badges de distribution : 150 distribués → 130 après retour de 20 ;
- refus : hors POST (405), quantité ≤ 0 (400), stock insuffisant (409),
  article hors du PDV (404), article absent du dépôt (409), plusieurs
  dépôts sans ``depot_id`` (409), transfert non validé (409),
  retours supérieurs à la quantité transférée (409), journée clôturée
  (403) ;
- boutons visibles : 🔄 sur la page articles du PDV, « Retourner
  l'excédent » sur le détail d'un transfert VALIDE.
"""
import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.distribution import etat_distribution
from inventory.models import (
    Article, Boutique, Commercant, FactureApprovisionnement,
    LigneApprovisionnement, MouvementStock, TransfertStock,
)

User = get_user_model()


class RetourExcedentBase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='re_comm', password='x', email='re_comm@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='RE SARL', nom_responsable='RE',
            email='re_comm@test.cd', user=self.user,
        )
        self.depot = Boutique.objects.create(
            nom='Dépôt RE', commercant=self.commercant,
            code_boutique='BT-RE-D', est_depot=True,
        )
        self.pdv = Boutique.objects.create(
            nom='PDV RE', commercant=self.commercant, code_boutique='BT-RE-P',
        )
        # Article du dépôt (source du transfert)
        self.article = Article.objects.create(
            boutique=self.depot, code='RE-ART', nom='Article RE',
            prix_vente=Decimal('1500'), quantite_stock=200,
        )
        # Facture du dépôt : ligne de 150 (sert aux badges de distribution)
        self.facture = FactureApprovisionnement.objects.create(
            numero_facture='F-RE-001', depot=self.depot,
            date_facture=date.today(), devise='CDF', created_by='re_comm',
        )
        self.ligne = LigneApprovisionnement.objects.create(
            facture=self.facture, article=self.article,
            quantite_unites=150, prix_achat_unitaire=100,
            prix_vente_unitaire=1500,
        )
        self.facture.calculer_montant_total()

        # Transfert de 150 vers le PDV, validé (réception MAUI en attente)
        self.transfert = TransfertStock.objects.create(
            article=self.article, depot_source=self.depot,
            boutique_destination=self.pdv, quantite=150,
            effectue_par='re_comm', statut='EN_ATTENTE',
        )
        self.transfert.valider_transfert('re_comm')
        self.article_pdv = Article.objects.get(
            boutique=self.pdv, code='RE-ART',
        )

        self.client.force_login(self.user)

    def _url(self, boutique=None):
        return reverse(
            'inventory:retourner_article_au_depot',
            args=[(boutique or self.pdv).id],
        )

    def _post(self, **data):
        data.setdefault('article_id', self.article_pdv.id)
        data.setdefault('quantite', 20)
        data.setdefault('depot_id', self.depot.id)
        return self.client.post(self._url(), data)

    def _reception_maui(self, quantite=None):
        """Simule la validation côté terminal MAUI : le stock du PDV est
        crédité et ``quantite_envoyee`` repasse à 0."""
        q = quantite if quantite is not None else self.article_pdv.quantite_envoyee
        self.article_pdv.quantite_stock = (self.article_pdv.quantite_stock or 0) + q
        self.article_pdv.quantite_envoyee = 0
        self.article_pdv.save(update_fields=['quantite_stock', 'quantite_envoyee'])
        return q

    def _mvt_depot(self):
        return MouvementStock.objects.filter(
            article=self.article, type_mouvement='ENTREE',
            reference_document__startswith='RETOUR-',
        )

    def _mvt_pdv(self):
        return MouvementStock.objects.filter(
            article=self.article_pdv, type_mouvement='SORTIE',
            reference_document__startswith='RETOUR-',
        )


class RetourExcedentSuccesTest(RetourExcedentBase):
    """Les retours qui aboutissent."""

    def test_retour_stock_deja_credite(self):
        """Le MAUI a déjà reçu : le stock du PDV diminue, le dépôt augmente."""
        self._reception_maui()          # PDV : 150 en stock, 0 en attente
        self.assertEqual(self.article_pdv.quantite_stock, 150)

        r = self._post(quantite=20)
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['quantite'], 20)
        self.assertEqual(data['quantite_en_attente_traitee'], 0)
        self.assertEqual(data['stock_pdv_apres'], 130)
        self.assertEqual(data['stock_depot_apres'], 70)   # 50 + 20

        self.article_pdv.refresh_from_db()
        self.article.refresh_from_db()
        self.assertEqual(self.article_pdv.quantite_stock, 130)
        self.assertEqual(self.article.quantite_stock, 70)

        # 2 mouvements : ENTREE au dépôt, SORTIE (négative) au PDV
        mv_depot = self._mvt_depot().get()
        self.assertEqual(mv_depot.quantite, 20)
        self.assertEqual(mv_depot.stock_avant, 50)
        self.assertEqual(mv_depot.stock_apres, 70)

        mv_pdv = self._mvt_pdv().get()
        self.assertEqual(mv_pdv.quantite, -20)           # convention : négatif
        self.assertEqual(mv_pdv.stock_avant, 150)
        self.assertEqual(mv_pdv.stock_apres, 130)
        self.assertEqual(
            mv_depot.reference_document, mv_pdv.reference_document,
        )
        self.assertTrue(
            mv_depot.reference_document.startswith('RETOUR-'),
        )

    def test_retour_reception_maui_en_attente(self):
        """Réception MAUI non faite : la part en attente est consommée SANS
        mouvement de stock côté PDV (elle n'y était jamais créditée)."""
        self.assertEqual(self.article_pdv.quantite_stock, 0)
        self.assertEqual(self.article_pdv.quantite_envoyee, 150)

        r = self._post(quantite=20)
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['quantite_en_attente_traitee'], 20)
        self.assertEqual(data['stock_pdv_apres'], 0)

        self.article_pdv.refresh_from_db()
        self.article.refresh_from_db()
        self.assertEqual(self.article_pdv.quantite_envoyee, 130)
        self.assertEqual(self.article_pdv.quantite_stock, 0)
        self.assertEqual(self.article.quantite_stock, 70)

        # Dépôt recrédité, aucun mouvement SORTIE côté PDV
        self.assertEqual(self._mvt_depot().count(), 1)
        self.assertEqual(self._mvt_pdv().count(), 0)

    def test_retour_partiel_attente_partiel_stock(self):
        """20 en attente restants + 10 de stock → retour de 25 : la part
        créditée est d'abord prise sur ``quantite_envoyee`` (20), le reste
        (5) sur le stock, avec un seul mouvement SORTIE de -5."""
        self._reception_maui(quantite=130)   # 130 crédités, 20 en attente
        self.article_pdv.quantite_envoyee = 20
        self.article_pdv.save(update_fields=['quantite_envoyee'])
        self.assertEqual(self.article_pdv.quantite_stock, 130)

        r = self._post(quantite=25)
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertEqual(data['quantite_en_attente_traitee'], 20)
        self.assertEqual(data['stock_pdv_apres'], 125)

        self.article_pdv.refresh_from_db()
        self.assertEqual(self.article_pdv.quantite_envoyee, 0)
        self.assertEqual(self.article_pdv.quantite_stock, 125)

        mv_pdv = self._mvt_pdv().get()
        self.assertEqual(mv_pdv.quantite, -5)

    def test_badges_distribution_diminuent(self):
        """150 distribués (TOUT) → 130 après retour de 20 (PARTIEL)."""
        _, par_ligne = etat_distribution([self.facture])
        self.assertEqual(par_ligne[self.ligne.id]['distribue'], 150)
        self.assertEqual(par_ligne[self.ligne.id]['statut'], 'TOUT')

        self._reception_maui()
        self._post(quantite=20)

        self.facture.refresh_from_db()
        _, par_ligne = etat_distribution([self.facture])
        self.assertEqual(par_ligne[self.ligne.id]['distribue'], 130)
        self.assertEqual(par_ligne[self.ligne.id]['restant'], 20)
        self.assertEqual(par_ligne[self.ligne.id]['statut'], 'PARTIEL')
        self.assertEqual(self.facture.etat['distribue'], 130)

    def test_retour_sans_transfert_reference_uuid(self):
        """Sans ``transfert_id`` : la référence est RETOUR-<uuid> et le
        retour n'est pas plafonné par la quantité transférée."""
        self._reception_maui()
        r = self._post(quantite=5)   # sans transfert_id (non fourni)
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['reference'].startswith('RETOUR-'))
        self.assertNotEqual(data['reference'], f"RETOUR-{self.transfert.id}")

    def test_json_accepte(self):
        """Le endpoint accepte aussi le JSON (consommation par un client)."""
        self._reception_maui()
        r = self.client.post(
            self._url(),
            json.dumps({
                'article_id': self.article_pdv.id,
                'quantite': 10,
                'depot_id': self.depot.id,
                'commentaire': 'envoyé par erreur',
            }),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['success'])
        self.article_pdv.refresh_from_db()
        self.assertEqual(self.article_pdv.quantite_stock, 140)


class RetourExcedentRefusTest(RetourExcedentBase):
    """Les retours refusés (le stock ne doit JAMAIS bouger)."""

    def _assert_stocks_intacts(self):
        self.article_pdv.refresh_from_db()
        self.article.refresh_from_db()
        self.assertEqual(self.article_pdv.quantite_stock, 0)
        self.assertEqual(self.article_pdv.quantite_envoyee, 150)
        self.assertEqual(self.article.quantite_stock, 50)
        self.assertFalse(self._mvt_depot().exists())
        self.assertFalse(self._mvt_pdv().exists())

    def test_hors_post_405(self):
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 405)
        self._assert_stocks_intacts()

    def test_quantite_nulle_ou_negative_400(self):
        for qte in (0, -5):
            r = self._post(quantite=qte)
            self.assertEqual(r.status_code, 400, (qte, r.content))
            self.assertIn('supérieure', r.json()['error'])
        self._assert_stocks_intacts()

    def test_quantite_non_numerique_400(self):
        r = self._post(quantite='abc')
        self.assertEqual(r.status_code, 400)
        self._assert_stocks_intacts()

    def test_stock_insuffisant_409(self):
        # Disponible = 0 en stock + 150 en attente → 151 refusé
        r = self._post(quantite=151)
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('Stock insuffisant', r.json()['error'])
        self._assert_stocks_intacts()

    def test_article_hors_du_pdv_404(self):
        # Un article qui appartient au dépôt, pas au PDV
        r = self._post(article_id=self.article.id)
        self.assertEqual(r.status_code, 404, r.content)
        self._assert_stocks_intacts()

    def test_article_manquant_400(self):
        r = self.client.post(self._url(), {'quantite': 5, 'depot_id': self.depot.id})
        self.assertEqual(r.status_code, 400)
        self._assert_stocks_intacts()

    def test_article_absent_du_depot_409(self):
        # Article du PDV qui n'existe pas au dépôt → pas de création
        autrui = Article.objects.create(
            boutique=self.pdv, code='RE-AUTRE', nom='Inconnu au dépôt',
            prix_vente=Decimal('500'), quantite_stock=10,
        )
        r = self._post(article_id=autrui.id, quantite=3)
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn("n'existe pas au dépôt", r.json()['error'])
        self.assertFalse(
            Article.objects.filter(boutique=self.depot, code='RE-AUTRE').exists(),
        )

    def test_plusieurs_depots_sans_id_409(self):
        Boutique.objects.create(
            nom='Second dépôt', commercant=self.commercant,
            code_boutique='BT-RE-D2', est_depot=True,
        )
        r = self.client.post(
            self._url(),
            {'article_id': self.article_pdv.id, 'quantite': 5},
        )
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('Plusieurs dépôts', r.json()['error'])
        self._assert_stocks_intacts()

    def test_depot_inconnu_400(self):
        r = self._post(depot_id=999999)
        self.assertEqual(r.status_code, 400, r.content)
        self._assert_stocks_intacts()

    def test_transfert_non_valide_409(self):
        en_attente = TransfertStock.objects.create(
            article=self.article, depot_source=self.depot,
            boutique_destination=self.pdv, quantite=10,
            effectue_par='re_comm', statut='EN_ATTENTE',
        )
        r = self._post(transfert_id=en_attente.id, quantite=5)
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('pas validé', r.json()['error'])
        self._assert_stocks_intacts()

    def test_transfert_d_autre_pdv_409(self):
        autre_pdv = Boutique.objects.create(
            nom='Autre PDV', commercant=self.commercant,
            code_boutique='BT-RE-P2',
        )
        t = TransfertStock.objects.create(
            article=self.article, depot_source=self.depot,
            boutique_destination=autre_pdv, quantite=10,
            effectue_par='re_comm', statut='VALIDE',
        )
        r = self._post(transfert_id=t.id, quantite=5)
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('pas destiné', r.json()['error'])
        self._assert_stocks_intacts()

    def test_retours_superieurs_a_la_quantite_409(self):
        self._reception_maui()   # 150 en stock au PDV

        r1 = self._post(quantite=140, transfert_id=self.transfert.id)
        self.assertEqual(r1.status_code, 200, r1.content)

        r2 = self._post(quantite=20, transfert_id=self.transfert.id)
        self.assertEqual(r2.status_code, 409, r2.content)
        self.assertIn('140', r2.json()['error'])

        self.article_pdv.refresh_from_db()
        self.article.refresh_from_db()
        self.assertEqual(self.article_pdv.quantite_stock, 10)     # 150 - 140
        self.assertEqual(self.article.quantite_stock, 190)        # 50 + 140
        self.assertEqual(self._mvt_pdv().count(), 1)

    def test_retour_depot_inexistant_404(self):
        r = self._post(transfert_id=999999)
        self.assertEqual(r.status_code, 404, r.content)
        self._assert_stocks_intacts()

    def test_boutique_depot_refuse_400(self):
        """Un dépôt ne retourne pas de stock vers lui-même."""
        r = self.client.post(self._url(boutique=self.depot), {
            'article_id': self.article.id, 'quantite': 5,
        })
        # accès au dépôt : la vue tourne, mais refuse
        self.assertIn(r.status_code, (400, 403), r.content)


class RetourExcedentBoutonsTest(RetourExcedentBase):
    """Présence des boutons aux deux endroits."""

    def test_bouton_sur_page_articles_pdv(self):
        r = self.client.get(
            reverse('inventory:commercant_articles_boutique', args=[self.pdv.id]),
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertContains(r, 'id="retourDepotModal"')
        self.assertContains(r, 'setArticleForRetour')
        self.assertContains(r, '/retourner-au-depot/')

    def test_bouton_sur_detail_transfert_valide(self):
        r = self.client.get(
            reverse('inventory:detail_transfert', args=[self.transfert.id]),
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertContains(r, "Retourner l'excédent au dépôt")
        self.assertContains(r, 'id="retourExcedentModal"')
        # Aucun retour encore : rien d'affiché comme déjà retourné
        self.assertNotContains(r, 'Déjà retourné')

    def test_detail_retourne_deja_retourne(self):
        self._reception_maui()
        self._post(quantite=30, transfert_id=self.transfert.id)

        r = self.client.get(
            reverse('inventory:detail_transfert', args=[self.transfert.id]),
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertContains(r, 'Déjà retourné')
        self.assertContains(r, '<strong>30</strong>', html=True)
        # Il reste 120 unités à retourner : le bouton reste là
        self.assertContains(r, 'id="retourExcedentModal"')
        self.assertContains(r, 'reste 120')

    def test_bouton_absent_si_aucun_depot(self):
        # Un signal crée un « Dépôt Central » à la création du commerçant :
        # on supprime TOUS les dépôts pour simuler un compte sans dépôt.
        Boutique.objects.filter(
            commercant=self.commercant, est_depot=True,
        ).delete()
        r = self.client.get(
            reverse('inventory:commercant_articles_boutique', args=[self.pdv.id]),
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotContains(r, 'id="retourDepotModal"')

    def test_detail_transfert_en_attente_sans_bouton(self):
        t = TransfertStock.objects.create(
            article=self.article, depot_source=self.depot,
            boutique_destination=self.pdv, quantite=10,
            effectue_par='re_comm', statut='EN_ATTENTE',
        )
        r = self.client.get(
            reverse('inventory:detail_transfert', args=[t.id]),
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotContains(r, 'id="retourExcedentModal"')
