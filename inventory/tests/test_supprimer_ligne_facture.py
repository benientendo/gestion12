"""
Suppression d'une ligne de facture du dépôt enregistrée par erreur
===================================================================
Dans « Mes factures » du dépôt, une ligne peut être supprimée UNIQUEMENT si
l'article n'a pas encore été distribué vers les points de vente (aucun
transfert VALIDÉ imputé à la ligne, cf. inventory/distribution.py).

Comportement vérifié ici :
- suppression OK : ligne supprimée, stock du dépôt annulé (mouvement SORTIE
  rattaché à la facture), montant total recalculé ;
- refus (409) si la ligne a été (même partiellement) distribuée ;
- refus (409) si le stock du dépôt est insuffisant pour annuler la ligne ;
- refus hors POST (405), mauvais dépôt / facture d'un autre commerçant (404),
  collaborateur sans profil commerçant (403) ;
- bouton 🗑 visible uniquement sur une ligne non distribuée.
"""
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import (
    Article, Boutique, Collaborateur, Commercant, FactureApprovisionnement,
    LigneApprovisionnement, MouvementStock, TransfertStock,
)

User = get_user_model()


class SupprimerLigneFactureBase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='sl_comm', password='x', email='sl_comm@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='DÉPÔT SL', nom_responsable='SL',
            email='sl_comm@test.cd', user=self.user,
        )
        self.depot = Boutique.objects.create(
            nom='Dépôt central', commercant=self.commercant,
            code_boutique='BT-SL-D', est_depot=True,
        )
        self.pdv = Boutique.objects.create(
            nom='PDV SL', commercant=self.commercant, code_boutique='BT-SL-P',
        )
        self.article = Article.objects.create(
            boutique=self.depot, code='SL-ART', nom='Article SL',
            prix_vente=1500, quantite_stock=10,
        )
        self.facture = FactureApprovisionnement.objects.create(
            numero_facture='F-SL-001', depot=self.depot,
            date_facture=date.today(), devise='CDF', created_by='sl_comm',
        )
        self.ligne = self._ligne(self.article, quantite=4, prix=100)
        self.facture.calculer_montant_total()

    def _ligne(self, article, quantite, prix):
        return LigneApprovisionnement.objects.create(
            facture=self.facture, article=article,
            quantite_unites=quantite,
            prix_achat_unitaire=prix, prix_vente_unitaire=prix + 500,
        )

    def _url(self, depot=None, facture=None, ligne=None):
        return reverse('inventory:supprimer_ligne_facture', args=[
            (depot or self.depot).id,
            (facture or self.facture).id,
            (ligne or self.ligne).id,
        ])

    def _post(self, url=None, **kwargs):
        return self.client.post(
            url or self._url(),
            json.dumps({'confirm': True}),
            content_type='application/json',
            **kwargs,
        )

    def _distribuer(self, quantite=2):
        """Transfert VALIDÉ : la ligne devient (partiellement) distribuée."""
        return TransfertStock.objects.create(
            article=self.article, depot_source=self.depot,
            boutique_destination=self.pdv, quantite=quantite,
            effectue_par='sl_comm', valide_par='sl_comm', statut='VALIDE',
        )

    def _mouvements_facture(self):
        """Mouvements créés par la suppression (un signal en crée déjà à la
        création de l'article : on ne compte que ceux de la facture)."""
        return MouvementStock.objects.filter(
            reference_document=f'FACT-{self.facture.id}',
        ).count()


class SuppressionLigneNonDistribueeTest(SupprimerLigneFactureBase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_suppression_ok_annule_stock_et_recalcule_total(self):
        r = self._post()
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['nb_lignes'], 0)
        self.assertEqual(data['facture_total'], 0.0)

        # Ligne supprimée
        self.assertFalse(
            LigneApprovisionnement.objects.filter(id=self.ligne.id).exists(),
        )

        # Stock du dépôt annulé d'autant (10 - 4)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 6)

        # Mouvement SORTIE rattaché à la facture
        mv = MouvementStock.objects.get(
            article=self.article,
            reference_document=f'FACT-{self.facture.id}',
        )
        self.assertEqual(mv.type_mouvement, 'SORTIE')
        self.assertEqual(mv.quantite, 4)
        self.assertEqual(mv.stock_avant, 10)
        self.assertEqual(mv.stock_apres, 6)
        self.assertEqual(mv.reference_document, f'FACT-{self.facture.id}')
        self.assertIn('enregistré par erreur', mv.commentaire)

        # Facture recalculée
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.montant_total, 0)

    def test_suppression_d_une_ligne_parmi_plusieurs(self):
        autre = Article.objects.create(
            boutique=self.depot, code='SL-ART2', nom='Article SL 2',
            prix_vente=2000, quantite_stock=5,
        )
        ligne2 = self._ligne(autre, quantite=6, prix=50)
        self.facture.calculer_montant_total()

        r = self._post()
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['nb_lignes'], 1)
        # Reste la ligne 2 : 6 x 50 = 300
        self.assertEqual(data['facture_total'], 300.0)

        ligne2.refresh_from_db()
        autre.refresh_from_db()
        self.assertEqual(autre.quantite_stock, 5)  # pas touché
        self.assertEqual(
            MouvementStock.objects.filter(
                article=self.article,
                reference_document=f'FACT-{self.facture.id}',
            ).count(), 1,
        )

    def test_detail_affiche_le_bouton(self):
        r = self.client.get(
            reverse('inventory:detail_facture_depot',
                    args=[self.depot.id, self.facture.id]),
        )
        self.assertEqual(r.status_code, 200)
        # onclick du bouton (la fonction JS est de toute façon dans la page)
        self.assertContains(r, 'onclick="supprimerLigne(')


class SuppressionRefuseeTest(SupprimerLigneFactureBase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_refuse_si_distribue(self):
        self._distribuer(quantite=2)

        r = self._post()
        self.assertEqual(r.status_code, 409)
        self.assertFalse(r.json()['success'])
        self.assertIn('distribué', r.json()['error'])

        # Rien n'a bougé
        self.assertTrue(
            LigneApprovisionnement.objects.filter(id=self.ligne.id).exists(),
        )
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)
        self.assertEqual(self._mouvements_facture(), 0)

    def test_refuse_si_distribue_entierement(self):
        self._distribuer(quantite=4)
        r = self._post()
        self.assertEqual(r.status_code, 409)

    def test_refuse_si_stock_insuffisant(self):
        self.article.quantite_stock = 2
        self.article.save(update_fields=['quantite_stock'])

        r = self._post()
        self.assertEqual(r.status_code, 409)
        self.assertIn('insuffisant', r.json()['error'])

        self.assertTrue(
            LigneApprovisionnement.objects.filter(id=self.ligne.id).exists(),
        )
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 2)
        self.assertEqual(self._mouvements_facture(), 0)

    def test_refuse_hors_post(self):
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 405)
        self.assertTrue(
            LigneApprovisionnement.objects.filter(id=self.ligne.id).exists(),
        )

    def test_refuse_si_facture_d_un_autre_depot(self):
        # Même commerçant, mais l'URL pointe vers un autre dépôt
        depot2 = Boutique.objects.create(
            nom='Dépôt 2', commercant=self.commercant,
            code_boutique='BT-SL-D2', est_depot=True,
        )
        r = self._post(self._url(depot=depot2))
        self.assertEqual(r.status_code, 404)
        self.assertTrue(
            LigneApprovisionnement.objects.filter(id=self.ligne.id).exists(),
        )

    def test_refuse_si_autre_commercant(self):
        user2 = User.objects.create_user(
            username='sl_comm2', password='x', email='sl_comm2@test.cd',
        )
        autre_commercant = Commercant.objects.create(
            nom_entreprise='Autre dépôt', nom_responsable='Autre',
            email='sl_comm2@test.cd', user=user2,
        )
        depot2 = Boutique.objects.create(
            nom='Dépôt étranger', commercant=autre_commercant,
            code_boutique='BT-AUTRE', est_depot=True,
        )
        facture2 = FactureApprovisionnement.objects.create(
            numero_facture='F-AUTRE-1', depot=depot2,
            date_facture=date.today(), devise='CDF',
        )
        ligne2 = LigneApprovisionnement.objects.create(
            facture=facture2, article=self.article,
            quantite_unites=1, prix_achat_unitaire=10,
            prix_vente_unitaire=20,
        )

        r = self._post(self._url(depot=depot2, facture=facture2, ligne=ligne2))
        self.assertEqual(r.status_code, 404)
        self.assertTrue(
            LigneApprovisionnement.objects.filter(id=ligne2.id).exists(),
        )

    def test_refuse_si_collaborateur_sans_profil_commercant(self):
        user_collab = User.objects.create_user(username='sl_collab', password='x')
        Collaborateur.objects.create(
            user=user_collab, commercant=self.commercant,
            nom_complet='Collab SL', code_pin='9911', est_actif=True,
        )
        self.client.force_login(user_collab)

        r = self._post()
        self.assertEqual(r.status_code, 403)
        self.assertTrue(
            LigneApprovisionnement.objects.filter(id=self.ligne.id).exists(),
        )
        self.assertEqual(self._mouvements_facture(), 0)


class BoutonSelonDistributionTest(SupprimerLigneFactureBase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def _page(self):
        return self.client.get(
            reverse('inventory:detail_facture_depot',
                    args=[self.depot.id, self.facture.id]),
        )

    def test_bouton_present_si_non_distribue(self):
        r = self._page()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'onclick="supprimerLigne(')

    def test_bouton_absent_si_distribue(self):
        self._distribuer(quantite=1)
        r = self._page()
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'onclick="supprimerLigne(')
