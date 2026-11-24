"""
Réduction de prix sur un article d'une vente à crédit (API MAUI) :
- payload {"montant"} / {"pourcentage"} / {"reset"} = remise TOTALE visée
- plafond : prix catalogue (jamais de surcharge), plancher : acomptes versés
- la réduction ne touche jamais au stock
"""
from decimal import Decimal

from django.urls import reverse

from inventory.models import (
    ClientAcompte, LigneVenteAcompte, MouvementStock, VenteAcompte,
)
from inventory.tests.test_credit_correction_vente import BaseCreditTestCase


class RemiseLigneCreditApiTestCase(BaseCreditTestCase):

    def setUp(self):
        super().setUp()
        self.vente = self._creer_vente(
            articles=self._lignes((self.article, 2)))       # catalogue 60 000
        self.ligne = self.vente.lignes.get()
        self.url = reverse('inventory:api_credit_reduire_ligne',
                           args=[self.vente.id, self.ligne.id])

    def _post(self, payload, url=None, headers=None):
        return self.api.post(
            url if url is not None else self.url, data=payload,
            content_type='application/json',
            **(self.entete if headers is None else headers),
        )

    def _recharger(self):
        self.vente.refresh_from_db()
        self.ligne.refresh_from_db()
        return self.vente, self.ligne

    # ── Remise par montant / pourcentage / reset ────────────────────────

    def test_reduire_de_montant(self):
        resp = self._post({'montant': 10000})
        self.assertEqual(resp.status_code, 200, resp.content)

        vente, ligne = self._recharger()
        self.assertEqual(ligne.remise, Decimal('10000.00'))
        self.assertEqual(ligne.prix_total, Decimal('50000.00'))
        self.assertEqual(ligne.prix_unitaire, Decimal('25000.00'))
        self.assertEqual(vente.prix_total, Decimal('50000.00'))
        self.assertEqual(vente.seuil_retrait, Decimal('50000.00'))
        self.assertEqual(vente.statut, 'EN_COURS')

        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['remise'], 10000.0)
        self.assertEqual(data['prix_total'], 50000.0)
        self.assertEqual(data['montant_restant'], 50000.0)

    def test_reduire_de_pourcentage(self):
        resp = self._post({'pourcentage': 10})
        self.assertEqual(resp.status_code, 200, resp.content)

        vente, ligne = self._recharger()
        self.assertEqual(ligne.remise, Decimal('6000.00'))       # 10 % de 60 000
        self.assertEqual(ligne.prix_total, Decimal('54000.00'))
        self.assertEqual(vente.prix_total, Decimal('54000.00'))

    def test_reset_remet_le_prix_catalogue(self):
        self._post({'montant': 20000})
        resp = self._post({'reset': True})
        self.assertEqual(resp.status_code, 200, resp.content)

        vente, ligne = self._recharger()
        self.assertEqual(ligne.remise, Decimal('0'))
        self.assertEqual(ligne.prix_total, Decimal('60000.00'))
        self.assertEqual(ligne.prix_unitaire, Decimal('30000.00'))
        self.assertEqual(vente.prix_total, Decimal('60000.00'))
        self.assertEqual(resp.json()['remise'], 0.0)

    def test_saisie_identique_deux_fois_est_idempotente(self):
        """« 10 % » deux fois = toujours 10 % (pas d'empilement)."""
        self._post({'pourcentage': 10})
        self._post({'pourcentage': 10})

        vente, ligne = self._recharger()
        self.assertEqual(ligne.remise, Decimal('6000.00'))
        self.assertEqual(ligne.prix_total, Decimal('54000.00'))
        self.assertEqual(vente.prix_total, Decimal('54000.00'))

    def test_remise_annulee_puis_reappliquee(self):
        self._post({'montant': 15000})
        self._post({'reset': True})
        self._post({'pourcentage': 50})

        _, ligne = self._recharger()
        self.assertEqual(ligne.remise, Decimal('30000.00'))
        self.assertEqual(ligne.prix_total, Decimal('30000.00'))

    # ── Garde-fous ──────────────────────────────────────────────────────

    def test_remise_superieure_au_catalogue_refusee(self):
        resp = self._post({'montant': 99999})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('trop élevée', resp.json()['error'])

        _, ligne = self._recharger()
        self.assertEqual(ligne.prix_total, Decimal('60000.00'))
        self.assertEqual(ligne.remise, Decimal('0'))

    def test_pourcentage_100_refuse(self):
        resp = self._post({'pourcentage': 100})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('compris entre 0 et 100', resp.json()['error'])

    def test_remise_egale_au_catalogue_refusee(self):
        """100 % (montant = prix catalogue) laisserait le prix à 0 : refusé."""
        resp = self._post({'montant': 60000})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('supérieur à 0', resp.json()['error'])

    def test_pourcentage_negatif_refuse(self):
        resp = self._post({'pourcentage': -5})
        self.assertEqual(resp.status_code, 400)

    def test_montant_negatif_refuse(self):
        resp = self._post({'montant': -1000})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('négative', resp.json()['error'])

    def test_aucun_parametre_refuse(self):
        resp = self._post({})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('montant', resp.json()['error'])

    def test_valeur_non_numerique_refusee(self):
        resp = self._post({'montant': 'beaucoup'})
        self.assertEqual(resp.status_code, 400)

    def test_reduction_sous_les_acomptes_refusee(self):
        self._encaisser(self.vente, 55000)          # facture EN_COURS
        resp = self._post({'montant': 10000})       # prix → 50 000 < 55 000
        self.assertEqual(resp.status_code, 400)
        self.assertIn('acomptes', resp.json()['error'])

        vente, ligne = self._recharger()
        self.assertEqual(ligne.prix_total, Decimal('60000.00'))
        self.assertEqual(vente.montant_paye, Decimal('55000'))
        self.assertEqual(vente.statut, 'EN_COURS')

    def test_reduction_jusqu_au_montant_deja_paye_autorisee(self):
        self._encaisser(self.vente, 50000)
        resp = self._post({'montant': 10000})       # prix → 50 000 = payé
        self.assertEqual(resp.status_code, 200, resp.content)

        vente, _ = self._recharger()
        self.assertEqual(vente.prix_total, Decimal('50000.00'))
        self.assertEqual(vente.statut, 'SOLDE')

    def test_vente_annulee_refusee(self):
        self.vente.statut = 'ANNULE'
        self.vente.save()
        resp = self._post({'montant': 5000})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('non active', resp.json()['error'])

    def test_vente_soldee_refusee(self):
        self._encaisser(self.vente, 60000)          # → SOLDE
        resp = self._post({'montant': 5000})
        self.assertEqual(resp.status_code, 400)

    def test_article_deja_recupere_refuse(self):
        self.vente.article_recupere = True
        self.vente.save()
        resp = self._post({'montant': 5000})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('remis au client', resp.json()['error'])

    # ── Périmètre / sécurité ────────────────────────────────────────────

    def test_get_methode_refusee(self):
        resp = self.api.get(self.url, **self.entete)
        self.assertEqual(resp.status_code, 405)

    def test_ligne_d_une_autre_vente_introuvable(self):
        # Client différent : pas de fusion de facture, 2e vente réelle
        autre = self._creer_vente(nom='MUKENDA', telephone='0822222222',
                                  articles=self._lignes((self.article2, 1)))
        self.assertNotEqual(autre.id, self.vente.id)
        url = reverse('inventory:api_credit_reduire_ligne',
                      args=[self.vente.id, autre.lignes.get().id])
        resp = self._post({'montant': 1000}, url=url)
        self.assertEqual(resp.status_code, 404)

    def test_vente_d_une_autre_boutique_introuvable(self):
        url = reverse('inventory:api_credit_reduire_ligne', args=[9999, self.ligne.id])
        resp = self._post({'montant': 1000}, url=url)
        self.assertEqual(resp.status_code, 404)

    def test_serial_absent_403(self):
        resp = self._post({'montant': 1000}, headers={})
        self.assertEqual(resp.status_code, 403)

    def test_serial_inconnu_403(self):
        resp = self._post({'montant': 1000},
                          headers={'HTTP_X_DEVICE_SERIAL': 'INCONNU'})
        self.assertEqual(resp.status_code, 403)

    # ── Effets de bord ──────────────────────────────────────────────────

    def test_la_reduction_ne_touche_pas_au_stock(self):
        self.article.refresh_from_db()
        stock_avant = self.article.quantite_stock

        self._post({'montant': 25000})

        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, stock_avant)
        self.assertFalse(MouvementStock.objects.filter(
            reference_document=f"CORR-CREDIT-{self.vente.reference}").exists())
        self.assertFalse(MouvementStock.objects.filter(
            article=self.article, type_mouvement='RETOUR',
            reference_document__contains=self.vente.reference).exists())

    def test_le_detail_reflete_la_remise(self):
        self._post({'montant': 10000})

        resp = self.api.get(
            reverse('inventory:api_credit_detail_vente', args=[self.vente.id]),
            **self.entete)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['remise'], 10000.0)
        self.assertEqual(data['prix_total'], 50000.0)
        self.assertEqual(data['lignes'][0]['remise'], 10000.0)
        self.assertEqual(data['lignes'][0]['prix_total'], 50000.0)

    def test_ligne_sans_article_plafonnee_au_prix_actuel(self):
        """Ancien format (aucun article au catalogue) : on ne peut que réduire."""
        client_credit = ClientAcompte.objects.create(
            boutique=self.boutique, nom='LIBRE', prenom='Client')
        vente = VenteAcompte.objects.create(
            boutique=self.boutique,
            client=client_credit,
            article_nom='Article libre',
            quantite=1,
            prix_total=Decimal('25000'),
            seuil_retrait=Decimal('25000'),
        )
        ligne = LigneVenteAcompte.objects.create(
            vente=vente,
            article_nom='Article libre',
            quantite=1,
            prix_unitaire=Decimal('25000'),
            prix_total=Decimal('25000'),
        )
        url = reverse('inventory:api_credit_reduire_ligne',
                      args=[vente.id, ligne.id])

        resp = self._post({'montant': 5000}, url=url)
        self.assertEqual(resp.status_code, 200, resp.content)
        ligne.refresh_from_db()
        self.assertEqual(ligne.prix_total, Decimal('20000.00'))
        self.assertEqual(ligne.remise, Decimal('5000.00'))

        # Plafond = prix d'origine de la ligne : impossible de dépasser 25 000
        resp = self._post({'montant': 30000}, url=url)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('trop élevée', resp.json()['error'])
        ligne.refresh_from_db()
        self.assertEqual(ligne.prix_total, Decimal('20000.00'))

        # Et on peut remonter jusqu'au prix d'origine (reset)
        resp = self._post({'reset': True}, url=url)
        self.assertEqual(resp.status_code, 200, resp.content)
        ligne.refresh_from_db()
        self.assertEqual(ligne.prix_total, Decimal('25000.00'))
        self.assertEqual(ligne.remise, Decimal('0'))

    def test_le_plafond_utilise_le_prix_catalogue_actuel(self):
        """La remise est calculée sur le prix catalogue ACTUEL de l'article."""
        self.article.prix_vente = Decimal('25000')
        self.article.save(update_fields=['prix_vente'])

        resp = self._post({'pourcentage': 10})
        self.assertEqual(resp.status_code, 200, resp.content)

        _, ligne = self._recharger()
        self.assertEqual(ligne.remise, Decimal('5000.00'))    # 10 % de 50 000
        self.assertEqual(ligne.prix_total, Decimal('45000.00'))


class PrixAvantRemiseBackofficeTestCase(BaseCreditTestCase):
    """Le back-office affiche le prix AVANT remise (prix catalogue) partout."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.vente = self._creer_vente(
            articles=self._lignes((self.article, 2)))       # catalogue 60 000
        self.ligne = self.vente.lignes.get()
        self._post({'montant': 10000})                      # paye 50 000
        self.vente.refresh_from_db()
        self.ligne.refresh_from_db()

    def _post(self, payload, url=None, headers=None):
        return self.api.post(
            url if url is not None else reverse(
                'inventory:api_credit_reduire_ligne',
                args=[self.vente.id, self.ligne.id]),
            data=payload, content_type='application/json',
            **(self.entete if headers is None else headers),
        )

    # -- Detail ----------------------------------------------------------

    def test_detail_expose_prix_avant_remise(self):
        resp = self.client.get(reverse('inventory:detail_vente_credit',
                                       args=[self.boutique.id, self.vente.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['remise_totale'], Decimal('10000.00'))
        self.assertEqual(resp.context['prix_avant_remise'], Decimal('60000.00'))

    def test_detail_affiche_prix_avant_remise_en_html(self):
        resp = self.client.get(reverse('inventory:detail_vente_credit',
                                       args=[self.boutique.id, self.vente.id]))
        html = resp.content.decode('utf-8')
        self.assertIn('Avant remise', html)
        self.assertIn('Prix avant remise (prix catalogue)', html)
        # Prix catalogue 60 000 affiche (espaces insécables ou non)
        self.assertIn('60000', html.replace('\xa0', '').replace(' ', ''))

    def test_detail_sans_remise_n_affiche_pas_avant_remise(self):
        vente = self._creer_vente(nom='SANSREMISE', telephone='0833333333',
                                  articles=self._lignes((self.article2, 1)))
        resp = self.client.get(reverse('inventory:detail_vente_credit',
                                       args=[self.boutique.id, vente.id]))
        html = resp.content.decode('utf-8')
        self.assertNotIn('Avant remise', html)
        self.assertNotIn('Prix avant remise (prix catalogue)', html)

    # -- Liste -----------------------------------------------------------

    def test_liste_annotee_remise_et_prix_avant_remise(self):
        resp = self.client.get(reverse('inventory:liste_ventes_credit',
                                       args=[self.boutique.id]))
        self.assertEqual(resp.status_code, 200)
        lignes = {v.id: v for v in resp.context['ventes']}
        vente = lignes[self.vente.id]
        self.assertEqual(vente.remise_totale, Decimal('10000.00'))
        self.assertEqual(vente.prix_avant_remise, Decimal('60000.00'))

        html = resp.content.decode('utf-8')
        self.assertIn('avant remise', html)

    def test_liste_sans_remise_n_annotepas_avant_remise(self):
        plain = self._creer_vente(nom='PLAIN', telephone='0844444444',
                                  articles=self._lignes((self.article2, 1)))
        resp = self.client.get(reverse('inventory:liste_ventes_credit',
                                       args=[self.boutique.id]))
        ventes = {v.id: v for v in resp.context['ventes']}
        v = ventes[plain.id]
        self.assertEqual(v.remise_totale, Decimal('0'))
        self.assertEqual(v.prix_avant_remise, v.prix_total)

    def test_liste_recherche_filtre_garde_les_annotations(self):
        resp = self.client.get(
            reverse('inventory:liste_ventes_credit', args=[self.boutique.id]),
            {'q': self.vente.reference},
        )
        ventes = list(resp.context['ventes'])
        self.assertEqual(len(ventes), 1)
        self.assertEqual(ventes[0].remise_totale, Decimal('10000.00'))
        self.assertEqual(ventes[0].prix_avant_remise, Decimal('60000.00'))

    # -- Correction ------------------------------------------------------

    def test_page_correction_affiche_prix_avant_remise(self):
        resp = self.client.get(reverse('inventory:modifier_vente_credit',
                                       args=[self.boutique.id, self.vente.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['prix_avant_remise'], Decimal('60000.00'))
        html = resp.content.decode('utf-8')
        self.assertIn('Avant remise', html)
        self.assertIn('60000', html.replace('\xa0', '').replace(' ', ''))

    def test_ligne_editable_transport_prix_avant_remise(self):
        from inventory.views_credit import _lignes_editables
        lignes = _lignes_editables(self.vente)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['remise'], Decimal('10000.00'))
        self.assertEqual(lignes[0]['prix_avant_remise'], Decimal('60000.00'))

    # -- Recu ------------------------------------------------------------

    def test_recu_affiche_prix_avant_remise(self):
        paiement = self._encaisser(self.vente, 5000)
        resp = self.client.get(reverse('inventory:recu_paiement',
                                       args=[self.boutique.id, paiement.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['prix_avant_remise'], Decimal('60000.00'))
        html = resp.content.decode('utf-8')
        self.assertIn('Prix avant remise', html)

    # -- Propriete modele ------------------------------------------------

    def test_propriete_prix_avant_remise_de_la_ligne(self):
        self.assertEqual(self.ligne.prix_avant_remise, Decimal('60000.00'))
        self.assertTrue(self.ligne.a_une_remise)

        self._post({'reset': True})
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.prix_avant_remise, Decimal('60000.00'))
        self.assertFalse(self.ligne.a_une_remise)
