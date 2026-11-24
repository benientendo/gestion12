"""
Colonnes du journal de valeur de stock : Transfert IN / Stock ajouté / Inventaire
================================================================================

Le commerçant a défini la répartition attendue des trois colonnes d'entrée :

- « Transfert IN »  : UNIQUEMENT des flux entre boutiques — TRANSFERT-…,
  TRANSFERT-BTQ-… et les transferts dépôt→PDV confirmés par validation MAUI ;
- « Stock ajouté »  : les ajouts saisis dans le back-office (régulations
  REGUL-/AJUST-, factures), les retours clients et les retours de refus de
  réception (RETOUR-…) ;
- « Inventaire »    : l'écart net des comptages valorisé au prix de vente,
  après régularisation d'un inventaire (réf. INV-… et instantanés MAUI).

AVANT : les retours de refus (RETOUR-) figuraient en « Transfert IN », les
transferts reçus via validation MAUI (réf. VALIDATION-) en « Stock ajouté », et
une régularisation d'inventaire (réf. INV-) alimentait « Stock ajouté » /
« Stock sorti » — la colonne « Inventaire » restait donc à 0.

Vérifié ici :
- la classification et la valeur viennent d'une source unique
  (``journal_valeur_stock``), utilisée par l'écriture, le détail cliquable et
  la reconstruction ;
- le détail d'une colonne totalise EXACTEMENT la valeur affichée (« Cohérent ») ;
- un transfert confirmé par validation MAUI entre en « Transfert IN », une
  régulation back-office validée de la même façon en « Stock ajouté » ;
- un instantané MAUI qui fait BAISSER le stock inscrit un impact négatif
  (l'ancien code utilisait la valeur absolue) ;
- ``reclasser_colonnes_depuis_mouvements`` répare l'historique sans toucher
  aux colonnes à source propre (Ventes, Modif. prix, Réduction).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, Client as TestClient
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from inventory.journal_valeur_stock import (
    COLONNES_MOUVEMENTS,
    colonne_mouvement,
    reclasser_colonnes_depuis_mouvements,
    valeur_mouvement,
)
from inventory.models import (
    Article, Boutique, Client, Commercant, JournalValeurStock, MouvementStock,
    TransfertStock,
)

User = get_user_model()

PV = Decimal('1500')


class Base(TestCase):
    """Fixtures : dépôt + PDV + terminal MAUI, comme les parcours de transfert."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_jvs', password='x', email='comm_jvs@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='JVS SARL', nom_responsable='JVS',
            email='comm_jvs@test.cd', user=self.user,
        )
        self.depot = Boutique.objects.create(
            nom='Dépôt JVS', commercant=self.commercant,
            code_boutique='BT-JVS-D', est_depot=True,
        )
        self.pdv = Boutique.objects.create(
            nom='PDV JVS', commercant=self.commercant,
            code_boutique='BT-JVS-P',
        )
        self.terminal = Client.objects.create(
            compte_proprietaire=self.user, boutique=self.pdv,
            nom_terminal='Terminal JVS', numero_serie='SER-JVS-001',
        )
        # Solde de 200 pour alimenter les transferts, mais SANS mouvement
        # d'ouverture (OUVERTURE-) : les tests portent sur le classement des
        # mouvements qu'ils créent eux-mêmes, pas sur le solde de départ.
        self.article_depot = Article(
            boutique=self.depot, code='JVS-ART', nom='Article JVS',
            prix_vente=PV, quantite_stock=200,
            est_actif=True, est_valide_client=True,
        )
        self.article_depot.sans_mouvement_initial = True
        self.article_depot.save()
        self.api = APIClient()
        self.web = TestClient()
        self.web.force_login(self.user)

    # -- helpers ----------------------------------------------------------

    @property
    def article(self):
        """Article du PDV (créé au premier transfert)."""
        return Article.objects.get(boutique=self.pdv, code='JVS-ART')

    def _journal(self, boutique=None):
        return JournalValeurStock.objects.get(
            boutique=boutique or self.pdv, date=timezone.localdate(),
        )

    def _colonnes(self, boutique=None):
        ligne = self._journal(boutique or self.depot)
        return {c: getattr(ligne, c) for c in COLONNES_MOUVEMENTS}

    def _mouvement(self, type_mouvement, quantite, reference='',
                   article=None, stock_avant=None, stock_apres=None):
        article = article or self.article_depot
        champs = {}
        if stock_avant is not None:
            champs['stock_avant'] = stock_avant
        if stock_apres is not None:
            champs['stock_apres'] = stock_apres
        return MouvementStock.objects.create(
            article=article,
            type_mouvement=type_mouvement,
            quantite=quantite,
            reference_document=reference,
            **champs,
        )

    def _transfert(self, quantite=60):
        transfert = TransfertStock.objects.create(
            article=self.article_depot, depot_source=self.depot,
            boutique_destination=self.pdv, quantite=quantite,
            effectue_par='comm_jvs', statut='EN_ATTENTE',
            reference_lot='LOT-JVS',
        )
        transfert.valider_transfert('comm_jvs')
        return transfert

    def _valider_sur_terminal(self, article, quantite):
        return self.api.post(
            reverse('api_v2_simple:valider_article'),
            {'article_id': article.id, 'quantite_validee': quantite,
             'boutique_id': article.boutique_id},
            format='json',
            HTTP_X_DEVICE_SERIAL='SER-JVS-001',
        )


class ClassificationColonnesTest(Base):
    """Qui atterrit dans quelle colonne, et pour combien."""

    def test_regularisation_inventaire_dans_la_colonne_inventaire(self):
        # Manque constaté : +5 unités × 1500 = +7500
        self._mouvement('ENTREE', 5, reference='INV-12')
        journal = self._journal(self.depot)
        self.assertEqual(journal.montant_inventaire, Decimal('7500'))
        self.assertEqual(journal.valeur_stock_ajoute, Decimal('0'))

    def test_regularisation_inventaire_en_excedent_retire_de_la_valeur(self):
        # Excédent constaté : 3 unités × 1500 = −4500 (pas « Stock sorti »)
        self._mouvement('SORTIE', -3, reference='INV-12')
        journal = self._journal(self.depot)
        self.assertEqual(journal.montant_inventaire, Decimal('-4500'))
        self.assertEqual(journal.valeur_stock_sorti, Decimal('0'))

    def test_retour_de_refus_dans_stock_ajoute(self):
        self._mouvement('ENTREE', 40, reference='RETOUR-9')
        journal = self._journal(self.depot)
        self.assertEqual(journal.valeur_stock_ajoute, Decimal('60000'))
        self.assertEqual(journal.valeur_transfert_entrant, Decimal('0'))

    def test_transfert_entrant_dans_transfert_in(self):
        self._mouvement('ENTREE', 40, reference='TRANSFERT-9')
        journal = self._journal(self.depot)
        self.assertEqual(journal.valeur_transfert_entrant, Decimal('60000'))
        self.assertEqual(journal.valeur_stock_ajoute, Decimal('0'))

    def test_transfert_entre_boutiques_dans_transfert_in(self):
        self._mouvement('ENTREE', 10, reference='TRANSFERT-BTQ-1-2')
        journal = self._journal(self.depot)
        self.assertEqual(journal.valeur_transfert_entrant, Decimal('15000'))

    def test_transfert_sortant_dans_transfert_out(self):
        self._mouvement('SORTIE', -40, reference='TRANSFERT-9')
        journal = self._journal(self.depot)
        self.assertEqual(journal.valeur_transfert_sortant, Decimal('60000'))
        self.assertEqual(journal.valeur_stock_sorti, Decimal('0'))

    def test_sortie_hors_transfert_dans_stock_sorti(self):
        self._mouvement('SORTIE', -40, reference='RETOUR-9')
        journal = self._journal(self.depot)
        self.assertEqual(journal.valeur_stock_sorti, Decimal('60000'))
        self.assertEqual(journal.valeur_transfert_sortant, Decimal('0'))

    def test_regulation_back_office_dans_stock_ajoute(self):
        self._mouvement('ENTREE', 25, reference='REGUL-WEB-20260101000000')
        journal = self._journal(self.depot)
        self.assertEqual(journal.valeur_stock_ajoute, Decimal('37500'))

    def test_validation_maui_sans_transfert_dans_stock_ajoute(self):
        """Validation d'un stock saisi dans le back-office : ce n'est PAS un
        transfert entre boutiques, même si le terminal confirme."""
        local = Article.objects.create(
            boutique=self.pdv, code='LOCAL', nom='Local',
            prix_vente=PV, quantite_stock=0,
            est_actif=True, est_valide_client=True,
        )
        self._mouvement('ENTREE', 30, reference='VALIDATION-BT-JVS-P-1',
                        article=local)
        journal = self._journal()
        self.assertEqual(journal.valeur_stock_ajoute, Decimal('45000'))
        self.assertEqual(journal.valeur_transfert_entrant, Decimal('0'))

    def test_retour_client_dans_stock_ajoute(self):
        self._mouvement('RETOUR', 2, reference='ANNUL-LIGNE-FA-1')
        journal = self._journal(self.depot)
        self.assertEqual(journal.valeur_stock_ajoute, Decimal('3000'))

    def test_regularisation_historique_hors_journal(self):
        """INIT-/REGL- : bookkeeping, aucun flux de valeur."""
        self._mouvement('ENTREE', 100, reference='INIT-1')
        self.assertFalse(
            JournalValeurStock.objects.filter(boutique=self.depot).exists()
        )
        self.assertIsNone(colonne_mouvement(
            self._mouvement('SORTIE', -5, reference='REGL-1'),
        ))

    def test_instantane_maui_en_diminution_prend_un_signe_negatif(self):
        """MAUI Windows enregistre la quantité en valeur absolue : le signe
        doit venir des stocks, sinon un manque AJOUTERAIT de la valeur."""
        mouvement = self._mouvement(
            'AJUSTEMENT', 20, reference='inventaire',
            stock_avant=100, stock_apres=80,
        )
        self.assertEqual(colonne_mouvement(mouvement), 'montant_inventaire')
        self.assertEqual(valeur_mouvement(mouvement), Decimal('-30000'))
        self.assertEqual(self._journal(self.depot).montant_inventaire,
                         Decimal('-30000'))

    def test_regulation_back_office_par_definition_dans_stock_ajoute(self):
        """« Ajuster le stock → Définir » : un ajout est un ajout."""
        self._mouvement(
            'AJUSTEMENT', 15, reference='AJUST-BT-JVS-D-1',
            stock_avant=10, stock_apres=25,
        )
        journal = self._journal(self.depot)
        self.assertEqual(journal.valeur_stock_ajoute, Decimal('22500'))
        self.assertEqual(journal.montant_inventaire, Decimal('0'))

        JournalValeurStock.objects.all().delete()
        self._mouvement(
            'AJUSTEMENT', 15, reference='AJUST-BT-JVS-D-1',
            stock_avant=25, stock_apres=10,
        )
        journal = self._journal(self.depot)
        self.assertEqual(journal.valeur_stock_sorti, Decimal('22500'))
        self.assertEqual(journal.montant_inventaire, Decimal('0'))


class ValidationMauiTransfertTest(Base):
    """Le terminal qui confirme un envoi du dépôt alimente « Transfert IN »."""

    def test_validation_dun_transfert_est_un_transfert_entrant(self):
        transfert = self._transfert(60)
        pdv_article = self.article
        self.assertIsNotNone(pdv_article.date_envoi)   # marqueur posé par la source

        r = self._valider_sur_terminal(pdv_article, 60)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json().get('success'), r.content)

        mouvement = MouvementStock.objects.get(article=pdv_article)
        self.assertEqual(mouvement.type_mouvement, 'ENTREE')
        self.assertEqual(mouvement.reference_document, f'TRANSFERT-{transfert.id}')

        journal = self._journal()
        self.assertEqual(journal.valeur_transfert_entrant, Decimal('90000'))
        self.assertEqual(journal.valeur_stock_ajoute, Decimal('0'))

        pdv_article.refresh_from_db()
        self.assertIsNone(pdv_article.date_envoi)     # marqueur consommé

    def test_validation_sans_envoi_depot_reste_un_ajout(self):
        """Stock ajouté depuis le back-office puis validé en boutique :
        référence VALIDATION- et colonne « Stock ajouté »."""
        local = Article.objects.create(
            boutique=self.pdv, code='LOCAL-2', nom='Local 2',
            prix_vente=PV, quantite_stock=0,
            est_actif=True, est_valide_client=False, quantite_envoyee=25,
            date_envoi=None,
        )

        r = self._valider_sur_terminal(local, 25)
        self.assertEqual(r.status_code, 200, r.content)

        local.refresh_from_db()
        mouvement = MouvementStock.objects.get(article=local)
        self.assertTrue(
            mouvement.reference_document.startswith('VALIDATION-'),
            mouvement.reference_document,
        )
        journal = self._journal()
        self.assertEqual(journal.valeur_stock_ajoute, Decimal('37500'))
        self.assertEqual(journal.valeur_transfert_entrant, Decimal('0'))

    def test_refus_de_reception_efface_le_marqueur(self):
        """Un refus vide l'envoi en attente : le marqueur ne doit pas survivre
        et faire passer la prochaine régulation en « Transfert IN »."""
        self._transfert(60)
        pdv_article = self.article
        self.assertIsNotNone(pdv_article.date_envoi)

        r = self.api.post(
            reverse('api_v2_simple:refuser_article'),
            {'article_id': pdv_article.id, 'boutique_id': self.pdv.id},
            format='json',
            HTTP_X_DEVICE_SERIAL='SER-JVS-001',
        )
        self.assertEqual(r.status_code, 200, r.content)

        pdv_article.refresh_from_db()
        self.assertIsNone(pdv_article.date_envoi)


class DetailColonneCoherentTest(Base):
    """Le détail cliquable doit totaliser exactement la valeur de la colonne."""

    def _detail(self, champ, boutique=None):
        boutique = boutique or self.depot
        journal = self._journal(boutique)
        return self.web.get(reverse(
            'inventory:detail_valeur_journal',
            args=[boutique.id, journal.id, champ],
        ))

    def test_detail_transfert_in_totalise_la_colonne(self):
        self._mouvement('ENTREE', 60, reference='TRANSFERT-9')
        r = self._detail('valeur_transfert_entrant')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertContains(r, 'Article JVS')
        self.assertContains(r, 'Cohérent')       # écart = 0

    def test_detail_inventaire_totalise_la_colonne(self):
        self._mouvement('ENTREE', 5, reference='INV-12')
        r = self._detail('montant_inventaire')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertContains(r, 'Cohérent')

    def test_detail_stock_ajoute_n_inclut_pas_les_transferts(self):
        self._mouvement('ENTREE', 60, reference='TRANSFERT-9')
        self._mouvement('ENTREE', 40, reference='RETOUR-9')
        r = self._detail('valeur_stock_ajoute')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertContains(r, 'RETOUR-9')
        self.assertNotContains(r, 'TRANSFERT-9')
        self.assertContains(r, 'Cohérent')

    def test_page_du_journal_affiche_les_libelles(self):
        self._mouvement('ENTREE', 40, reference='TRANSFERT-9')
        r = self.web.get(reverse(
            'inventory:journal_valeur_stock_boutique', args=[self.depot.id],
        ))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Transfert IN')
        self.assertContains(r, 'Stock ajouté')
        self.assertContains(r, 'Inventaire')


class ReclassificationHistoriqueTest(Base):
    """Réparation de l'historique après un changement de règles."""

    def test_reclassement_reecrit_les_colonnes_sans_toucher_aux_autres(self):
        self._mouvement('ENTREE', 40, reference='RETOUR-9')       # → Stock ajouté
        self._mouvement('ENTREE', 60, reference='TRANSFERT-9')    # → Transfert IN
        self._mouvement('ENTREE', 5, reference='INV-12')          # → Inventaire

        journal = self._journal(self.depot)
        # Simulation de l'ancienne répartition (celle d'avant le correctif)
        JournalValeurStock.objects.filter(pk=journal.pk).update(
            montant_inventaire=Decimal('0'),
            valeur_stock_ajoute=Decimal('150000'),
            valeur_transfert_entrant=Decimal('0'),
        )
        journal.refresh_from_db()
        self.assertEqual(journal.valeur_stock_ajoute, Decimal('150000'))

        reecrites = reclasser_colonnes_depuis_mouvements(self.depot)
        self.assertEqual(reecrites, 1)

        journal.refresh_from_db()
        self.assertEqual(journal.montant_inventaire, Decimal('7500'))
        self.assertEqual(journal.valeur_stock_ajoute, Decimal('60000'))
        self.assertEqual(journal.valeur_transfert_entrant, Decimal('90000'))
        # La somme des colonnes est inchangée : seul le classement bouge
        self.assertEqual(
            journal.valeur_stock_ajoute + journal.valeur_transfert_entrant
            + journal.montant_inventaire,
            Decimal('157500'),
        )

    def test_reclassement_ne_touche_pas_ventes_ni_modif_prix(self):
        self._mouvement('VENTE', -4, reference='FA-1')
        self._mouvement('ENTREE', 10, reference='RETOUR-9')

        journal = self._journal(self.depot)
        ventes = journal.valeur_ventes
        reclasser_colonnes_depuis_mouvements(self.depot)
        journal.refresh_from_db()
        self.assertEqual(journal.valeur_ventes, ventes)
        self.assertEqual(journal.impact_modification_prix, Decimal('0'))

    def test_reclassement_est_idempotent(self):
        self._mouvement('ENTREE', 40, reference='RETOUR-9')
        self._mouvement('ENTREE', 60, reference='TRANSFERT-9')

        reclasser_colonnes_depuis_mouvements(self.depot)
        premier = self._colonnes()
        reclasser_colonnes_depuis_mouvements(self.depot)
        second = self._colonnes()
        self.assertEqual(premier, second)

    def test_reclassement_recalcule_la_chaine(self):
        self._mouvement('ENTREE', 40, reference='RETOUR-9')
        journal = self._journal(self.depot)
        attendu = journal.valeur_stock_restant

        reclasser_colonnes_depuis_mouvements(self.depot)
        journal.refresh_from_db()
        self.assertEqual(journal.valeur_stock_restant, attendu)
