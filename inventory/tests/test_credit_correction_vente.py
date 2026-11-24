"""
Vente à crédit — correction et suppression depuis le back-office :
- corriger : quantités, retrait d'article, ajout d'article, acomptes (stock + totaux)
- supprimer : uniquement si rien n'a été encaissé ni remis (retour de stock)
- remise à la création : prix inférieur au catalogue accepté, surcharge refusée
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, Client as TestClient
from django.urls import reverse

from inventory.models import (
    Article, Boutique, Client, ClientAcompte, Commercant, LigneVenteAcompte,
    MouvementStock, PaiementAcompte, VenteAcompte,
)

User = get_user_model()


class BaseCreditTestCase(TestCase):
    """Fixtures communes : commerçant, boutique, terminal, articles, API."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_corr', password='pass1234', email='comm_corr@test.cd'
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='CORR SARL',
            nom_responsable='CORR',
            email='comm_corr@test.cd',
            user=self.user,
        )
        self.boutique = Boutique.objects.create(
            nom='Boutique CORR',
            commercant=self.commercant,
            code_boutique='BT-CORR-001',
        )
        self.terminal = Client.objects.create(
            compte_proprietaire=self.user,
            boutique=self.boutique,
            nom_terminal='T1',
            numero_serie='SERIAL-CORR-001',
            est_actif=True,
        )
        self.article = Article.objects.create(
            code='CORR-1', nom='Televiseur Samsung',
            prix_vente=Decimal('30000'),
            boutique=self.boutique,
            quantite_stock=10,
            est_actif=True, est_valide_client=True,
        )
        self.article2 = Article.objects.create(
            code='CORR-2', nom='Radio Philips',
            prix_vente=Decimal('10000'),
            boutique=self.boutique,
            quantite_stock=5,
            est_actif=True, est_valide_client=True,
        )

        self.api = TestClient(SERVER_NAME='127.0.0.1')
        self.entete = {'HTTP_X_DEVICE_SERIAL': 'SERIAL-CORR-001'}
        self.url_creer = reverse('inventory:api_credit_creer_vente',
                                 args=[self.boutique.id])

    # ── Aides ────────────────────────────────────────────────────────────

    def _payload(self, **kwargs):
        base = {
            'client_id':    None,
            'nom':          'KABILA',
            'prenom':       'Jean',
            'telephone':    '0810000000',
            'adresse':      'Kinshasa',
            'article_nom':  'Televiseur Samsung',
            'prix_total':   float(Decimal('30000') * 2),
            'acompte_initial': 0,
            'commentaire':  '',
        }
        base.update(kwargs)
        return base

    @staticmethod
    def _lignes(*paires):
        """[(article, quantité), …] → payload articles multi-lignes."""
        return [{
            'article_id':   article.id,
            'article_nom':  article.nom,
            'quantite':     quantite,
            'prix_total':   float(article.prix_vente * quantite),
        } for article, quantite in paires]

    def _creer_vente(self, **kwargs):
        """Crée une vente via l'API Android et la renvoie (déjà persistée)."""
        resp = self.api.post(
            self.url_creer, data=self._payload(**kwargs),
            content_type='application/json', **self.entete,
        )
        self.assertIn(resp.status_code, (200, 201), resp.content)
        return VenteAcompte.objects.get(id=resp.json()['vente_id'])

    @staticmethod
    def _encaisser(vente, montant):
        """Enregistre un acompte comme le ferait la vue back-office."""
        paiement = PaiementAcompte.objects.create(
            vente=vente, montant=Decimal(str(montant)), recu_par='test',
        )
        vente.montant_paye += Decimal(str(montant))
        if vente.montant_paye >= vente.prix_total:
            vente.statut = 'SOLDE'
        vente.save()
        return paiement

    def _url_modifier(self, vente):
        return reverse('inventory:modifier_vente_credit',
                       args=[self.boutique.id, vente.id])

    def _url_supprimer(self, vente):
        return reverse('inventory:supprimer_vente_credit',
                       args=[self.boutique.id, vente.id])


class CorrectionVenteCreditTestCase(BaseCreditTestCase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def _post_modifier(self, vente, **champs):
        return self.client.post(self._url_modifier(vente), data=champs)

    # ── Quantités ────────────────────────────────────────────────────────

    def test_augmenter_quantite_debite_le_stock_et_recalcule_le_total(self):
        vente = self._creer_vente(
            articles=self._lignes((self.article, 2), (self.article2, 1)))
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 8)   # 10 − 2

        ligne_tv = vente.lignes.get(article=self.article)
        resp = self._post_modifier(
            vente, **{f'qte_{ligne_tv.id}': '4',
                      f'qte_{vente.lignes.get(article=self.article2).id}': '1'})
        self.assertEqual(resp.status_code, 302)

        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 6)   # 8 − 2 de plus
        ligne_tv.refresh_from_db()
        self.assertEqual(ligne_tv.quantite, 4)
        self.assertEqual(ligne_tv.prix_total, Decimal('120000.00'))

        vente.refresh_from_db()
        self.assertEqual(vente.prix_total, Decimal('130000.00'))
        self.assertEqual(vente.quantite, 5)
        self.assertEqual(vente.seuil_retrait, Decimal('130000.00'))

        mv = MouvementStock.objects.filter(
            article=self.article, type_mouvement='VENTE').order_by('-id').first()
        self.assertEqual(mv.quantite, -2)
        self.assertEqual(mv.reference_document, vente.reference)

    def test_diminuer_quantite_rend_le_stock(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 4)))
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 6)

        ligne = vente.lignes.get()
        self._post_modifier(vente, **{f'qte_{ligne.id}': '1'})

        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 9)
        vente.refresh_from_db()
        self.assertEqual(vente.prix_total, Decimal('30000.00'))
        self.assertEqual(vente.quantite, 1)

        mv = MouvementStock.objects.filter(
            article=self.article, type_mouvement='RETOUR').get()
        self.assertEqual(mv.quantite, 3)
        self.assertEqual(mv.reference_document, f"CORR-CREDIT-{vente.reference}")

    def test_retirer_un_article_rend_son_stock(self):
        vente = self._creer_vente(
            articles=self._lignes((self.article, 2), (self.article2, 3)))
        self.article.refresh_from_db()
        self.article2.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 8)
        self.assertEqual(self.article2.quantite_stock, 2)

        ligne_radio = vente.lignes.get(article=self.article2)
        resp = self._post_modifier(
            vente, **{f'suppr_{ligne_radio.id}': '1',
                      f'qte_{vente.lignes.get(article=self.article).id}': '2'})
        self.assertEqual(resp.status_code, 302)

        self.assertFalse(vente.lignes.filter(article=self.article2).exists())
        self.article2.refresh_from_db()
        self.assertEqual(self.article2.quantite_stock, 5)   # 2 + 3 rendus

        vente.refresh_from_db()
        self.assertEqual(vente.prix_total, Decimal('60000.00'))
        self.assertEqual(vente.quantite, 2)

    def test_ajouter_un_article_debite_le_stock(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 1)))
        self.article2.refresh_from_db()
        self.assertEqual(self.article2.quantite_stock, 5)

        resp = self._post_modifier(
            vente,
            **{f'qte_{vente.lignes.get().id}': '1',
               'add_article': [str(self.article2.id), ''],
               'add_qte':     ['2', '']})
        self.assertEqual(resp.status_code, 302)

        self.assertTrue(vente.lignes.filter(article=self.article2).exists())
        self.article2.refresh_from_db()
        self.assertEqual(self.article2.quantite_stock, 3)

        vente.refresh_from_db()
        self.assertEqual(vente.prix_total, Decimal('50000.00'))
        self.assertEqual(vente.quantite, 3)

    def test_stock_insuffisant_annule_toute_la_correction(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        self.article2.refresh_from_db()
        self.assertEqual(self.article2.quantite_stock, 5)

        # +1 TV (ok) mais +9 Radio (stock 5) → tout doit être annulé
        resp = self._post_modifier(
            vente,
            **{f'qte_{vente.lignes.get().id}': '3',
               'add_article': [str(self.article2.id), ''],
               'add_qte':     ['9', '']})
        self.assertEqual(resp.status_code, 302)

        vente.refresh_from_db()
        self.assertEqual(vente.prix_total, Decimal('60000.00'))   # inchangé
        self.assertEqual(vente.quantite, 2)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 8)           # 10 − 2
        self.article2.refresh_from_db()
        self.assertEqual(self.article2.quantite_stock, 5)          # intact
        # Aucun mouvement de correction n'a été commité
        self.assertFalse(MouvementStock.objects.filter(
            reference_document=f"CORR-CREDIT-{vente.reference}").exists())

    def test_quantite_nulle_ou_invalide_rejetee(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        ligne = vente.lignes.get()

        resp = self._post_modifier(vente, **{f'qte_{ligne.id}': '0'})
        self.assertEqual(resp.status_code, 302)
        vente.refresh_from_db()
        self.assertEqual(vente.prix_total, Decimal('60000.00'))

        resp = self._post_modifier(vente, **{f'qte_{ligne.id}': 'abc'})
        self.assertEqual(resp.status_code, 302)
        vente.refresh_from_db()
        self.assertEqual(vente.prix_total, Decimal('60000.00'))

    def test_retirer_tous_les_articles_refuse(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        ligne = vente.lignes.get()
        self._post_modifier(vente, **{f'suppr_{ligne.id}': '1'})

        vente.refresh_from_db()
        self.assertEqual(vente.lignes.count(), 1)      # rien n'a été retiré
        self.assertEqual(vente.prix_total, Decimal('60000.00'))
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 8)

    # ── Acomptes ─────────────────────────────────────────────────────────

    def test_correction_d_un_acompte_recalcule_montant_paye(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        paiement = self._encaisser(vente, 10000)
        self.assertEqual(vente.montant_paye, Decimal('10000'))

        resp = self._post_modifier(
            vente,
            **{f'qte_{vente.lignes.get().id}': '2',
               f'pay_{paiement.id}': '15000'})
        self.assertEqual(resp.status_code, 302)

        paiement.refresh_from_db()
        self.assertEqual(paiement.montant, Decimal('15000'))
        vente.refresh_from_db()
        self.assertEqual(vente.montant_paye, Decimal('15000'))
        self.assertEqual(vente.statut, 'EN_COURS')

    def test_suppression_d_un_acompte_recalcule_et_reouvre_la_vente(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 1)))
        paiement = self._encaisser(vente, 30000)      # facture soldée
        self.assertEqual(vente.statut, 'SOLDE')

        resp = self._post_modifier(
            vente,
            **{f'qte_{vente.lignes.get().id}': '1',
               f'pay_suppr_{paiement.id}': '1'})
        self.assertEqual(resp.status_code, 302)

        self.assertFalse(PaiementAcompte.objects.filter(id=paiement.id).exists())
        vente.refresh_from_db()
        self.assertEqual(vente.montant_paye, Decimal('0'))
        self.assertEqual(vente.statut, 'EN_COURS')

    def test_total_inferieur_aux_acomptes_refuse_sans_ecriture(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        self._encaisser(vente, 50000)                 # > 1 × 30 000
        ligne = vente.lignes.get()

        resp = self._post_modifier(vente, **{f'qte_{ligne.id}': '1'})
        self.assertEqual(resp.status_code, 302)

        vente.refresh_from_db()
        self.assertEqual(vente.quantite, 2)            # inchangé
        self.assertEqual(vente.prix_total, Decimal('60000.00'))
        self.assertEqual(vente.montant_paye, Decimal('50000'))
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 8)

    def test_vente_payee_integralement_passe_en_solde(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        ligne = vente.lignes.get()

        # 2 → 1 unité : total 30 000, puis acompte de 30 000 saisi dans la foulée
        self._post_modifier(
            vente, **{f'qte_{ligne.id}': '1', 'add_article': [''], 'add_qte': ['']})
        vente.refresh_from_db()
        self.assertEqual(vente.prix_total, Decimal('30000.00'))

        self._encaisser(vente, 30000)
        self.assertEqual(vente.statut, 'SOLDE')

    # ── Blocages ─────────────────────────────────────────────────────────

    def test_vente_annulee_non_modifiable(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        vente.statut = 'ANNULE'
        vente.save()
        ligne = vente.lignes.get()

        resp = self._post_modifier(vente, **{f'qte_{ligne.id}': '5'})
        self.assertEqual(resp.status_code, 302)
        vente.refresh_from_db()
        self.assertEqual(vente.quantite, 2)
        self.assertEqual(vente.prix_total, Decimal('60000.00'))

    def test_article_deja_recupere_non_modifiable(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        vente.article_recupere = True
        vente.save()
        ligne = vente.lignes.get()

        resp = self._post_modifier(vente, **{f'qte_{ligne.id}': '5'})
        self.assertEqual(resp.status_code, 302)
        vente.refresh_from_db()
        self.assertEqual(vente.quantite, 2)

    def test_page_de_correction_s_affiche(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        resp = self.client.get(self._url_modifier(vente))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'inventory/credit/modifier_vente_credit.html')
        self.assertIsNone(resp.context['modifiable'])
        self.assertEqual(len(resp.context['lignes']), 1)

    def test_page_de_correction_indique_le_blocage(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        vente.article_recupere = True
        vente.save()
        resp = self.client.get(self._url_modifier(vente))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('remis au client', resp.context['modifiable'])

    def test_get_ne_modifie_rien(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        resp = self.client.get(self._url_modifier(vente))
        self.assertEqual(resp.status_code, 200)
        vente.refresh_from_db()
        self.assertEqual(vente.quantite, 2)
        self.assertEqual(vente.prix_total, Decimal('60000.00'))

    def test_boutique_inconnue_404_lors_de_la_correction(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        ligne = vente.lignes.get()
        url = reverse('inventory:modifier_vente_credit',
                      args=[9999, vente.id])
        resp = self.client.post(url, data={f'qte_{ligne.id}': '9'})
        self.assertEqual(resp.status_code, 404)
        vente.refresh_from_db()
        self.assertEqual(vente.quantite, 2)

    # ── Ancien format (vente sans LigneVenteAcompte) ─────────────────────

    def test_ligne_ancien_format_est_materialisee_lors_de_la_correction(self):
        """Vente d'avant les lignes (aucune LigneVenteAcompte) : la correction crée la ligne."""
        client_credit = ClientAcompte.objects.create(
            boutique=self.boutique, nom='HISTORIQUE', prenom='Client')
        vente = VenteAcompte.objects.create(
            boutique=self.boutique,
            client=client_credit,
            article_nom='Article libre',
            quantite=1,
            prix_total=Decimal('25000'),
            seuil_retrait=Decimal('25000'),
        )
        self.assertFalse(vente.lignes.exists())

        resp = self.client.post(self._url_modifier(vente), data={'qte_legacy': '2'})
        self.assertEqual(resp.status_code, 302)

        vente.refresh_from_db()
        self.assertEqual(vente.lignes.count(), 1)
        ligne = vente.lignes.get()
        self.assertEqual(ligne.quantite, 2)
        self.assertEqual(ligne.prix_total, Decimal('50000.00'))
        self.assertEqual(vente.prix_total, Decimal('50000.00'))
        self.assertEqual(vente.quantite, 2)
        self.assertEqual(vente.article_nom, 'Article libre')


class SuppressionVenteCreditTestCase(BaseCreditTestCase):

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_suppression_rend_le_stock_et_efface_la_vente(self):
        vente = self._creer_vente(
            articles=self._lignes((self.article, 2), (self.article2, 1)))
        reference = vente.reference
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 8)

        resp = self.client.post(self._url_supprimer(vente))
        self.assertEqual(resp.status_code, 302)

        self.assertFalse(VenteAcompte.objects.filter(reference=reference).exists())
        self.assertFalse(LigneVenteAcompte.objects.filter(
            article__in=[self.article, self.article2]).exists())

        self.article.refresh_from_db()
        self.article2.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)
        self.assertEqual(self.article2.quantite_stock, 5)

        mvs = MouvementStock.objects.filter(
            reference_document=f"ANNUL-CREDIT-{reference}")
        self.assertEqual(mvs.count(), 2)
        self.assertTrue(all(m.type_mouvement == 'RETOUR' for m in mvs))

    def test_suppression_refusee_des_qu_un_acompte_existe(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        self._encaisser(vente, 1000)

        resp = self.client.post(self._url_supprimer(vente))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(VenteAcompte.objects.filter(id=vente.id).exists())
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 8)     # stock intact

    def test_suppression_refusee_si_article_recupere(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        vente.article_recupere = True
        vente.save()

        resp = self.client.post(self._url_supprimer(vente))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(VenteAcompte.objects.filter(id=vente.id).exists())
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 8)

    def test_get_ne_supprime_pas(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        resp = self.client.get(self._url_supprimer(vente))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(VenteAcompte.objects.filter(id=vente.id).exists())
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 8)

    def test_suppression_d_une_vente_annulee_ne_double_pas_le_retour(self):
        """La vente annulée a déjà rendu son stock : la suppression ne le rend pas 2×."""
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        vente.statut = 'ANNULE'
        vente.save()
        # Le stock a déjà été rendu par l'annulation
        self.article.quantite_stock = 10
        self.article.save(update_fields=['quantite_stock'])
        MouvementStock.objects.filter(
            article=self.article, type_mouvement='RETOUR').delete()

        resp = self.client.post(self._url_supprimer(vente))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(VenteAcompte.objects.filter(id=vente.id).exists())

        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)    # pas de double retour
        self.assertFalse(MouvementStock.objects.filter(
            article=self.article, type_mouvement='RETOUR').exists())

    def test_boutique_inconnue_404_lors_de_la_suppression(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        url = reverse('inventory:supprimer_vente_credit', args=[9999, vente.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(VenteAcompte.objects.filter(id=vente.id).exists())

    def test_detail_affiche_les_boutons_seligibles(self):
        vente = self._creer_vente(articles=self._lignes((self.article, 2)))
        url = reverse('inventory:detail_vente_credit',
                      args=[self.boutique.id, vente.id])

        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['peut_corriger'])
        self.assertTrue(resp.context['peut_supprimer'])

        self._encaisser(vente, 5000)
        resp = self.client.get(url)
        self.assertTrue(resp.context['peut_corriger'])
        self.assertFalse(resp.context['peut_supprimer'])

        vente.article_recupere = True
        vente.save()
        resp = self.client.get(url)
        self.assertFalse(resp.context['peut_corriger'])
        self.assertFalse(resp.context['peut_supprimer'])


class RemiseVenteCreditTestCase(BaseCreditTestCase):
    """Règle de prix : surcharge interdite, remise autorisée et tracée."""

    def test_prix_inferieur_au_catalogue_accepte_comme_remise(self):
        resp = self.api.post(
            self.url_creer,
            data=self._payload(articles=[{
                'article_id':   self.article.id,
                'article_nom':  self.article.nom,
                'quantite':     2,
                'prix_total':   50000,          # catalogue 60 000 → remise 10 000
            }]),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 201, resp.content)

        vente = VenteAcompte.objects.get()
        ligne = vente.lignes.get()
        self.assertEqual(ligne.prix_total, Decimal('50000.00'))
        self.assertEqual(ligne.remise, Decimal('10000.00'))
        self.assertEqual(ligne.prix_unitaire, Decimal('25000.00'))
        self.assertEqual(vente.prix_total, Decimal('50000.00'))
        self.assertEqual(vente.seuil_retrait, Decimal('50000.00'))

    def test_surcharge_toujours_rejetee(self):
        resp = self.api.post(
            self.url_creer,
            data=self._payload(articles=[{
                'article_id':   self.article.id,
                'article_nom':  self.article.nom,
                'quantite':     2,
                'prix_total':   70000,          # catalogue 60 000
            }]),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('surcharge', resp.json()['error'].lower())
        self.assertFalse(VenteAcompte.objects.exists())

    def test_ecart_d_arrondi_reste_aucune_remise(self):
        resp = self.api.post(
            self.url_creer,
            data=self._payload(articles=[{
                'article_id':   self.article.id,
                'article_nom':  self.article.nom,
                'quantite':     2,
                'prix_total':   60000.4,        # catalogue 60 000
            }]),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        ligne = VenteAcompte.objects.get().lignes.get()
        self.assertEqual(ligne.prix_total, Decimal('60000.00'))
        self.assertEqual(ligne.remise, Decimal('0'))
        self.assertEqual(ligne.prix_unitaire, Decimal('30000.00'))

    def test_remise_cumulee_lors_de_la_fusion_de_lignes(self):
        self.api.post(
            self.url_creer,
            data=self._payload(articles=[{
                'article_id':   self.article.id,
                'article_nom':  self.article.nom,
                'quantite':     1,
                'prix_total':   25000,          # remise 5 000
            }]),
            content_type='application/json', **self.entete,
        )
        resp = self.api.post(
            self.url_creer,
            data=self._payload(
                nom='KABILA', prenom='Jean', telephone='0810000000',
                articles=[{
                    'article_id':   self.article.id,
                    'article_nom':  self.article.nom,
                    'quantite':     1,
                    'prix_total':   25000,      # remise 5 000
                }]),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 201, resp.content)

        vente = VenteAcompte.objects.get()
        self.assertEqual(vente.lignes.count(), 1)
        ligne = vente.lignes.get()
        self.assertEqual(ligne.quantite, 2)
        self.assertEqual(ligne.prix_total, Decimal('50000.00'))
        self.assertEqual(ligne.remise, Decimal('10000.00'))

    def test_detail_et_liste_exposent_la_remise(self):
        self.api.post(
            self.url_creer,
            data=self._payload(articles=[{
                'article_id':   self.article.id,
                'article_nom':  self.article.nom,
                'quantite':     2,
                'prix_total':   50000,
            }]),
            content_type='application/json', **self.entete,
        )
        vente = VenteAcompte.objects.get()

        liste = self.api.get(
            f'/api/credit/boutique/{self.boutique.id}/ventes/', **self.entete)
        self.assertEqual(liste.status_code, 200)
        donnees = [d for d in liste.json()['ventes'] if d['id'] == vente.id][0]
        self.assertEqual(donnees['remise'], 10000.0)
        self.assertEqual(donnees['lignes'][0]['remise'], 10000.0)

        detail = self.api.get(
            reverse('inventory:api_credit_detail_vente', args=[vente.id]),
            **self.entete)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['remise'], 10000.0)

    def test_correction_conserve_une_remise_existante(self):
        self.client.force_login(self.user)
        self.api.post(
            self.url_creer,
            data=self._payload(articles=[{
                'article_id':   self.article.id,
                'article_nom':  self.article.nom,
                'quantite':     2,
                'prix_total':   50000,          # remise 10 000
            }]),
            content_type='application/json', **self.entete,
        )
        vente = VenteAcompte.objects.get()
        ligne = vente.lignes.get()

        self.client.post(self._url_modifier(vente),
                         data={f'qte_{ligne.id}': '3'})

        vente.refresh_from_db()
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite, 3)
        self.assertEqual(ligne.prix_total, Decimal('75000.00'))   # 25 000 × 3
        self.assertEqual(ligne.remise, Decimal('15000.00'))       # proportionnel
        self.assertEqual(vente.prix_total, Decimal('75000.00'))
