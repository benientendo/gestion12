"""
Retour d'excédent : la facture SOURCE doit être recréditée
===========================================================

Un même article peut figurer sur deux factures différentes (même date ou
dates différentes). Les transferts sont imputés FIFO aux lignes de facture
(cf. inventory/distribution.py) ; un retour doit annuler l'imputation du
transfert d'où la marchandise est réellement partie — jamais les lignes les
plus anciennes au hasard.

Scénario de référence (``RetourFactureSourceBase``) :
  - facture F-A du 01/01 : 100 unités
  - facture F-B du 15/01 : 100 unités
  - transfert T1 = 60  → F-A (60)
  - transfert T2 = 80  → F-A (40) + F-B (40)

Vérifié ici :
- retour sur T2 → recrédite F-B, F-A reste TOUT ;
- retour sur T1 → recrédite F-A, F-B intact ;
- retour sans transfert (RETOUR-<uuid>) → imputations les plus récentes ;
- colonnes recu / distribue / restant / statut mises à jour des DEUX factures ;
- aperçu GET ``?preview=1`` : aucune écriture, identique à la réponse POST ;
- réponse POST : ``factures_source`` + ``quantite_sans_source`` + message ;
- détail du transfert : facture source affichée à l'avance ;
- part sans facture source signalée au lieu d'être créditée en silence.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.distribution import etat_distribution, imputation_transfert
from inventory.models import (
    Article, Boutique, Commercant, FactureApprovisionnement,
    LigneApprovisionnement, MouvementStock, TransfertStock,
)

User = get_user_model()


class RetourFactureSourceBase(TestCase):
    """Deux factures, deux transferts, un même article."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='fs_comm', password='x', email='fs_comm@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='FS SARL', nom_responsable='FS',
            email='fs_comm@test.cd', user=self.user,
        )
        self.depot = Boutique.objects.create(
            nom='Dépôt FS', commercant=self.commercant,
            code_boutique='BT-FS-D', est_depot=True,
        )
        self.pdv = Boutique.objects.create(
            nom='PDV FS', commercant=self.commercant, code_boutique='BT-FS-P',
        )
        self.article = Article.objects.create(
            boutique=self.depot, code='FS-ART', nom='Article FS',
            prix_vente=Decimal('2000'), quantite_stock=400,
        )

        # Facture la plus ancienne : 100 unités
        self.facture_a = FactureApprovisionnement.objects.create(
            numero_facture='F-A', depot=self.depot,
            date_facture=date(2026, 1, 1), devise='CDF', created_by='fs_comm',
        )
        self.ligne_a = LigneApprovisionnement.objects.create(
            facture=self.facture_a, article=self.article,
            quantite_unites=100, prix_achat_unitaire=100,
            prix_vente_unitaire=2000,
        )
        self.facture_a.calculer_montant_total()

        # Facture la plus récente : 100 unités du MÊME article
        self.facture_b = FactureApprovisionnement.objects.create(
            numero_facture='F-B', depot=self.depot,
            date_facture=date(2026, 1, 15), devise='CDF', created_by='fs_comm',
        )
        self.ligne_b = LigneApprovisionnement.objects.create(
            facture=self.facture_b, article=self.article,
            quantite_unites=100, prix_achat_unitaire=100,
            prix_vente_unitaire=2000,
        )
        self.facture_b.calculer_montant_total()

        # T1 = 60 → F-A seule ; T2 = 80 → F-A (40) + F-B (40)
        self.t1 = self._transfert(60)
        self.t2 = self._transfert(80)

        self.article_pdv = Article.objects.get(
            boutique=self.pdv, code='FS-ART',
        )
        self.client.force_login(self.user)

    def _transfert(self, quantite):
        transfert = TransfertStock.objects.create(
            article=self.article, depot_source=self.depot,
            boutique_destination=self.pdv, quantite=quantite,
            effectue_par='fs_comm', statut='EN_ATTENTE',
        )
        transfert.valider_transfert('fs_comm')
        return transfert

    def _url(self):
        return reverse(
            'inventory:retourner_article_au_depot', args=[self.pdv.id],
        )

    def _post(self, quantite, transfert=None, **extra):
        data = {
            'article_id': self.article_pdv.id,
            'quantite': quantite,
            'depot_id': self.depot.id,
        }
        if transfert is not None:
            data['transfert_id'] = transfert.id
        data.update(extra)
        return self.client.post(self._url(), data)

    def _apercu(self, quantite, transfert=None, **extra):
        params = {
            'preview': '1',
            'article_id': self.article_pdv.id,
            'quantite': quantite,
            'depot_id': self.depot.id,
        }
        if transfert is not None:
            params['transfert_id'] = transfert.id
        params.update(extra)
        return self.client.get(self._url(), params)

    def _etat(self):
        """(par_facture, par_ligne) des deux factures de référence."""
        return etat_distribution([self.facture_a, self.facture_b])

    def _ligne(self, par_ligne, ligne):
        return par_ligne[ligne.id]


class RetourCibleLaBonneFactureTest(RetourFactureSourceBase):
    """Le retour annule l'imputation du TRANSFERT d'où la marchandise sort."""

    def test_imputation_initiale_fifo(self):
        """Règle FIFO : F-A reçoit d'abord (60 + 40), F-B reçoit le reliquat."""
        _, par_ligne = self._etat()
        a = self._ligne(par_ligne, self.ligne_a)
        b = self._ligne(par_ligne, self.ligne_b)
        self.assertEqual(
            (a['recu'], a['distribue'], a['restant'], a['statut']),
            (100, 100, 0, 'TOUT'),
        )
        self.assertEqual(
            (b['recu'], b['distribue'], b['restant'], b['statut']),
            (100, 40, 60, 'PARTIEL'),
        )

    def test_retour_du_transfert_recent_credite_la_facture_recente(self):
        """20 renvoyés depuis T2 → F-B recréditée, F-A reste TOUT."""
        r = self._post(20, transfert=self.t2)
        self.assertEqual(r.status_code, 200, r.content)

        _, par_ligne = self._etat()
        a = self._ligne(par_ligne, self.ligne_a)
        b = self._ligne(par_ligne, self.ligne_b)
        self.assertEqual(a['distribue'], 100)      # inchangée
        self.assertEqual(a['statut'], 'TOUT')
        self.assertEqual(b['distribue'], 20)       # 40 - 20
        self.assertEqual(b['restant'], 80)
        self.assertEqual(b['statut'], 'PARTIEL')

    def test_retour_de_l_ancien_transfert_credite_l_ancienne_facture(self):
        """20 renvoyés depuis T1 → F-A recréditée, F-B intacte."""
        r = self._post(20, transfert=self.t1)
        self.assertEqual(r.status_code, 200, r.content)

        _, par_ligne = self._etat()
        a = self._ligne(par_ligne, self.ligne_a)
        b = self._ligne(par_ligne, self.ligne_b)
        self.assertEqual(a['distribue'], 80)       # 100 - 20
        self.assertEqual(a['restant'], 20)
        self.assertEqual(a['statut'], 'PARTIEL')
        self.assertEqual(b['distribue'], 40)       # inchangée
        self.assertEqual(b['statut'], 'PARTIEL')

    def test_retour_sans_transfert_credite_l_imputation_la_plus_recente(self):
        """RETOUR-<uuid> : on annule les imputations les plus récentes (F-B)."""
        r = self._post(20)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(
            r.json()['reference'].startswith('RETOUR-'),
        )
        self.assertNotEqual(r.json()['reference'], f'RETOUR-{self.t2.id}')

        _, par_ligne = self._etat()
        self.assertEqual(self._ligne(par_ligne, self.ligne_a)['distribue'], 100)
        self.assertEqual(self._ligne(par_ligne, self.ligne_b)['distribue'], 20)

    def test_retour_partiel_reparti_dans_l_ordre_inverse(self):
        """60 renvoyés depuis T2 : d'abord F-B (40), puis F-A (20)."""
        r = self._post(60, transfert=self.t2)
        self.assertEqual(r.status_code, 200, r.content)

        _, par_ligne = self._etat()
        a = self._ligne(par_ligne, self.ligne_a)
        b = self._ligne(par_ligne, self.ligne_b)
        self.assertEqual(a['distribue'], 80)       # 60 (T1) + 40 - 20
        self.assertEqual(b['distribue'], 0)        # 40 - 40
        self.assertEqual(b['statut'], 'AUCUN')
        self.assertEqual(b['restant'], 100)

    def test_retour_total_du_transfert(self):
        """80 renvoyés depuis T2 : F-B à zéro, F-A garde les 60 de T1."""
        r = self._post(80, transfert=self.t2)
        self.assertEqual(r.status_code, 200, r.content)

        _, par_ligne = self._etat()
        a = self._ligne(par_ligne, self.ligne_a)
        b = self._ligne(par_ligne, self.ligne_b)
        self.assertEqual(a['distribue'], 60)
        self.assertEqual(a['restant'], 40)
        self.assertEqual(b['distribue'], 0)

    def test_retours_successifs_du_meme_transfert(self):
        """Deux retours sur T2 s'accumulent sur F-B."""
        self._post(20, transfert=self.t2)
        r = self._post(10, transfert=self.t2)
        self.assertEqual(r.status_code, 200, r.content)

        _, par_ligne = self._etat()
        self.assertEqual(self._ligne(par_ligne, self.ligne_a)['distribue'], 100)
        self.assertEqual(self._ligne(par_ligne, self.ligne_b)['distribue'], 10)

    def test_colonnes_des_deux_factures_misees_a_jour(self):
        """recu / distribue / restant / statut + facture.etat, avant/après."""
        par_facture, _ = self._etat()
        self.assertEqual(
            (par_facture[self.facture_a.id]['recu'],
             par_facture[self.facture_a.id]['distribue'],
             par_facture[self.facture_a.id]['restant'],
             par_facture[self.facture_a.id]['statut']),
            (100, 100, 0, 'TOUT'),
        )
        self.assertEqual(
            (par_facture[self.facture_b.id]['recu'],
             par_facture[self.facture_b.id]['distribue'],
             par_facture[self.facture_b.id]['restant'],
             par_facture[self.facture_b.id]['statut']),
            (100, 40, 60, 'PARTIEL'),
        )

        self._post(30, transfert=self.t2)

        par_facture, par_ligne = self._etat()
        # Les attributs « etat » sont posés sur les objets factures
        self.assertEqual(self.facture_a.etat['distribue'], 100)
        self.assertEqual(self.facture_b.etat['distribue'], 10)
        self.assertEqual(self.facture_b.etat['restant'], 90)
        self.assertEqual(self.facture_b.etat['statut'], 'PARTIEL')
        self.assertEqual(
            self._ligne(par_ligne, self.ligne_b)['restant'], 90,
        )
        self.assertEqual(par_facture[self.facture_b.id]['restant'], 90)


class RetourFacturesMemeDateTest(RetourFactureSourceBase):
    """Même date de facture : l'ordre d'enregistrement départage."""

    def setUp(self):
        super().setUp()
        # On remet les deux factures à la même date : F-A enregistrée
        # d'abord (id plus petit) doit rester la première servie.
        self.facture_a.date_facture = date(2026, 2, 2)
        self.facture_a.save(update_fields=['date_facture'])
        self.facture_b.date_facture = date(2026, 2, 2)
        self.facture_b.save(update_fields=['date_facture'])

    def test_retour_sur_transfert_recent_credite_la_derniere_facture(self):
        _, par_ligne = self._etat()
        # F-A (enregistrée en premier) sert d'abord : T1=60, puis T2=40
        self.assertEqual(self._ligne(par_ligne, self.ligne_a)['distribue'], 100)
        self.assertEqual(self._ligne(par_ligne, self.ligne_b)['distribue'], 40)

        self._post(20, transfert=self.t2)

        _, par_ligne = self._etat()
        self.assertEqual(self._ligne(par_ligne, self.ligne_a)['distribue'], 100)
        self.assertEqual(self._ligne(par_ligne, self.ligne_b)['distribue'], 20)


class RetourSansFactureSourceTest(RetourFactureSourceBase):
    """Ce qui n'appartient à aucune facture n'est pas recrédité en silence."""

    def test_part_sans_source_signalee(self):
        # Un troisième transfert de 100 alors que les deux factures n'ont
        # plus que 60 unités à imputer : 40 unités sont parties sans facture.
        t3 = self._transfert(100)
        _, par_ligne = self._etat()
        self.assertEqual(self._ligne(par_ligne, self.ligne_b)['distribue'], 100)

        r = self._post(80, transfert=t3)   # ≤ 100 envoyés : accepté
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()

        # Seules les 60 unités imputées à F-B sont recréditées
        self.assertEqual(
            [(c['numero_facture'], c['quantite']) for c in data['factures_source']],
            [('F-B', 60)],
        )
        self.assertEqual(data['quantite_sans_source'], 20)
        self.assertIn('sans facture source', data['message'])

        _, par_ligne = self._etat()
        b = self._ligne(par_ligne, self.ligne_b)
        self.assertEqual(b['distribue'], 40)       # 100 - 60, pas moins
        self.assertEqual(b['restant'], 60)

    def test_aucune_facture_au_depot(self):
        """Aucune ligne de facture : le retour déplace le stock, sans crédit."""
        FactureApprovisionnement.objects.filter(depot=self.depot).delete()

        r = self._post(10, transfert=self.t2)
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertEqual(data['factures_source'], [])
        self.assertEqual(data['quantite_sans_source'], 10)

        self.article_pdv.refresh_from_db()
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 400 - 140 + 10)


class ApercuRetourTest(RetourFactureSourceBase):
    """L'aperçu GET ne doit RIEN écrire, et dire la même chose que le POST."""

    def test_apercu_renvoie_la_source_sans_ecrire(self):
        r = self._apercu(20, transfert=self.t2)
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()

        self.assertTrue(data['success'])
        self.assertEqual(len(data['factures_source']), 1)
        credit = data['factures_source'][0]
        self.assertEqual(credit['numero_facture'], 'F-B')
        self.assertEqual(credit['date_facture'], '2026-01-15')
        self.assertEqual(credit['quantite'], 20)
        self.assertEqual(data['quantite_sans_source'], 0)

        # Aucune écriture : pas de mouvement RETOUR-, stocks inchangés
        self.assertFalse(
            MouvementStock.objects.filter(
                reference_document__startswith='RETOUR-',
            ).exists(),
        )
        self.article_pdv.refresh_from_db()
        self.article.refresh_from_db()
        self.assertEqual(self.article_pdv.quantite_envoyee, 140)
        self.assertEqual(self.article.quantite_stock, 400 - 140)

    def test_apercu_identique_a_la_reponse_post(self):
        apercu = self._apercu(35, transfert=self.t2).json()
        reponse = self._post(35, transfert=self.t2).json()

        self.assertEqual(apercu['factures_source'], reponse['factures_source'])
        self.assertEqual(
            apercu['quantite_sans_source'], reponse['quantite_sans_source'],
        )

    def test_apercu_sans_transfert(self):
        """L'aperçu de la page articles (sans transfert_id) fonctionne aussi."""
        data = self._apercu(20).json()
        self.assertTrue(data['success'])
        self.assertEqual(data['factures_source'][0]['numero_facture'], 'F-B')

    def test_apercu_refuse_hors_preview(self):
        """Un GET sans ?preview=1 reste un 405 (aucun effet de bord)."""
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 405)
        self.assertFalse(
            MouvementStock.objects.filter(
                reference_document__startswith='RETOUR-',
            ).exists(),
        )

    def test_apercu_sans_stock_suffisant_comme_le_post(self):
        """L'aperçu applique les MÊMES refus que l'exécution."""
        r = self._apercu(9999)
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('Stock insuffisant', r.json()['error'])
        self.assertFalse(
            MouvementStock.objects.filter(
                reference_document__startswith='RETOUR-',
            ).exists(),
        )


class ReponseEtAffichageTest(RetourFactureSourceBase):
    """La source est visible : dans la réponse, et sur le détail du transfert."""

    def test_reponse_post_contient_la_source(self):
        r = self._post(20, transfert=self.t2)
        data = r.json()

        self.assertTrue(data['success'])
        self.assertEqual(data['quantite'], 20)
        self.assertEqual(len(data['factures_source']), 1)
        self.assertEqual(data['factures_source'][0]['numero_facture'], 'F-B')
        self.assertEqual(data['factures_source'][0]['quantite'], 20)
        self.assertEqual(data['quantite_sans_source'], 0)
        self.assertIn('F-B', data['message'])

    def test_reponse_post_sans_source_le_signale(self):
        # Une facture de 10 unités en plus : sur un transfert de 100,
        # 70 unités sont imputées (F-B 60 + F-D 10), 30 non.
        facture = FactureApprovisionnement.objects.create(
            numero_facture='F-D', depot=self.depot,
            date_facture=date(2026, 4, 1), devise='CDF', created_by='fs_comm',
        )
        LigneApprovisionnement.objects.create(
            facture=facture, article=self.article,
            quantite_unites=10, prix_achat_unitaire=100,
            prix_vente_unitaire=2000,
        )
        t = self._transfert(100)

        r = self._post(90, transfert=t)
        data = r.json()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(
            sum(c['quantite'] for c in data['factures_source']), 70,
        )
        self.assertEqual(data['quantite_sans_source'], 20)
        self.assertIn('20 unité(s) sans facture source', data['message'])

    def test_detail_transfert_affiche_la_facture_source(self):
        r = self.client.get(
            reverse('inventory:detail_transfert', args=[self.t2.id]),
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertContains(r, 'Facture(s) source de ce transfert')
        # Les deux factures dont la marchandise de T2 est sortie
        self.assertContains(r, 'F-A')
        self.assertContains(r, 'F-B')

    def test_detail_transfert_reflete_les_retours_deja_faits(self):
        self._post(40, transfert=self.t2)   # annule F-B en entier

        imputation = imputation_transfert(self.t2)
        self.assertEqual(
            [(f['numero_facture'], f['quantite']) for f in imputation],
            [('F-A', 40)],                 # F-B n'a plus rien à dire
        )

        r = self.client.get(
            reverse('inventory:detail_transfert', args=[self.t2.id]),
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertContains(r, 'F-A')

    def test_imputation_transfert_sans_retour(self):
        imputation = imputation_transfert(self.t2)
        self.assertEqual(
            [(f['numero_facture'], f['quantite']) for f in imputation],
            [('F-A', 40), ('F-B', 40)],
        )
        # Un transfert en attente n'a aucune source
        en_attente = TransfertStock.objects.create(
            article=self.article, depot_source=self.depot,
            boutique_destination=self.pdv, quantite=5,
            effectue_par='fs_comm', statut='EN_ATTENTE',
        )
        self.assertEqual(imputation_transfert(en_attente), [])
