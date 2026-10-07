"""
Motifs d'annulation (choix par coche sur le terminal MAUI) :
- ERREUR_COMMANDE    → l'article est REMIS EN STOCK
- ARTICLE_DEFECTUEUX → pas de retour en stock, la valeur est reclassée en
                       « Stock sorti » du journal de valeur (traçabilité
                       cliquable dans le back-office) et retirée de « Ventes ».
Le montant de l'article est toujours retiré du CA (montant_total réduit,
vente entière marquée est_annulee).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, Client as TestClient
from django.urls import reverse
from django.utils import timezone

from inventory.models import (
    Article, Boutique, Client, Commercant, DemandeAnnulationVente,
    JournalValeurStock, LigneVente, MouvementStock, Vente,
)
from inventory.ca_remboursements import ca_net, encaisse_total, remboursements
from inventory.tests.test_demande_annulation import DemandeAnnulationBase

User = get_user_model()


class AnnulationMotifApiTestCase(DemandeAnnulationBase):
    """Règles stock / journal selon le motif choisi."""

    def setUp(self):
        super().setUp()
        # Vente déjà effectuée : le stock local Django a été décrémenté
        self.article.quantite_stock = 8
        self.article.save(update_fields=['quantite_stock'])
        self.article2.quantite_stock = 4
        self.article2.save(update_fields=['quantite_stock'])

    def _tracer_vente(self, vente):
        """Mouvements VENTE + journal comme en production."""
        for ligne in vente.lignes.all():
            stock_apres = ligne.article.quantite_stock
            MouvementStock.objects.create(
                article=ligne.article,
                type_mouvement='VENTE',
                quantite=ligne.quantite,
                stock_avant=stock_apres + ligne.quantite,
                stock_apres=stock_apres,
                reference_document=vente.numero_facture,
                utilisateur='T1',
                commentaire=f"Vente {vente.numero_facture}",
            )

    def _journal_du_jour(self):
        return JournalValeurStock.objects.get(
            boutique=self.boutique, date=timezone.localdate()
        )

    # ─────────────────────────────────────────────
    # Annulation D'UN ARTICLE
    # ─────────────────────────────────────────────

    def test_ligne_article_defectueux_sortie_sans_retour(self):
        vente = self._creer_vente(
            articles=[(self.article, 2, Decimal('1000')),
                      (self.article2, 1, Decimal('2000'))]
        )
        self._tracer_vente(vente)
        restant_avant = self._journal_du_jour().valeur_stock_restant
        reel_avant = self._journal_du_jour().valeur_stock_reel

        r = self.api.post(
            self.url_annuler_ligne,
            data={
                'numero_facture': vente.numero_facture,
                'article_id': self.article.id,
                'motif': 'Article défectueux',
                'motif_code': 'ARTICLE_DEFECTUEUX',
            },
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['motif_code'], 'ARTICLE_DEFECTUEUX')
        self.assertFalse(body['remis_en_stock'])
        self.assertEqual(body['ligne']['quantite_restauree'], 0)
        self.assertEqual(body['ligne']['valeur_sortie'], '2000.00')

        # 1. Le stock N'EST PAS remis en stock
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 8)

        # 2. Trace SORTIE dans le journal (ANNUL-DEF-)
        self.assertTrue(MouvementStock.objects.filter(
            article=self.article,
            type_mouvement='SORTIE',
            reference_document=f'ANNUL-DEF-{vente.numero_facture}',
        ).exists())
        self.assertFalse(MouvementStock.objects.filter(
            article=self.article,
            type_mouvement='RETOUR',
            reference_document=f'ANNUL-LIGNE-{vente.numero_facture}',
        ).exists())

        # 3. Journal : +2000 en « Stock sorti », -2000 en « Ventes »
        #    (4000 de ventes au départ), le reste de la journée est inchangé
        journal = self._journal_du_jour()
        self.assertEqual(journal.valeur_stock_sorti, Decimal('2000'))
        self.assertEqual(journal.valeur_ventes, Decimal('2000'))
        self.assertEqual(journal.valeur_stock_restant, restant_avant)
        self.assertEqual(journal.valeur_stock_reel, reel_avant)

        # 4. Ligne tracée avec le code du motif
        ligne = vente.lignes.get(article=self.article)
        self.assertTrue(ligne.est_annulee)
        self.assertEqual(ligne.motif_annulation_code, 'ARTICLE_DEFECTUEUX')
        self.assertEqual(ligne.motif_annulation, 'Article défectueux')

        # 5. Montant retiré du total (= retiré du CA)
        vente.refresh_from_db()
        self.assertEqual(vente.montant_total, Decimal('2000.00'))
        self.assertFalse(vente.est_annulee)

    def test_ligne_achat_par_erreur_remet_en_stock(self):
        vente = self._creer_vente(articles=[(self.article, 2, Decimal('1000'))])
        self._tracer_vente(vente)
        restant_avant = self._journal_du_jour().valeur_stock_restant
        ajoute_avant = self._journal_du_jour().valeur_stock_ajoute

        r = self.api.post(
            self.url_annuler_ligne,
            data={
                'numero_facture': vente.numero_facture,
                'article_id': self.article.id,
                'motif': 'Achat par erreur du client',
                'motif_code': 'ERREUR_COMMANDE',
            },
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['motif_code'], 'ERREUR_COMMANDE')
        self.assertTrue(body['remis_en_stock'])
        self.assertIsNone(body['ligne']['valeur_sortie'])

        # Remis en stock + mouvement RETOUR
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)
        self.assertTrue(MouvementStock.objects.filter(
            article=self.article,
            type_mouvement='RETOUR',
            reference_document=f'ANNUL-LIGNE-{vente.numero_facture}',
        ).exists())
        self.assertFalse(MouvementStock.objects.filter(
            reference_document=f'ANNUL-DEF-{vente.numero_facture}',
        ).exists())

        # Journal : entrée de stock (retour) + ventes inchangées
        journal = self._journal_du_jour()
        self.assertEqual(journal.valeur_stock_sorti, Decimal('0'))
        self.assertEqual(
            journal.valeur_stock_ajoute, ajoute_avant + Decimal('2000')
        )
        self.assertEqual(journal.valeur_ventes, Decimal('2000'))
        self.assertEqual(journal.valeur_stock_restant, restant_avant + Decimal('2000'))

        ligne = vente.lignes.get(article=self.article)
        self.assertEqual(ligne.motif_annulation_code, 'ERREUR_COMMANDE')

    def test_ligne_libelle_seul_detecte_le_motif(self):
        vente = self._creer_vente(articles=[(self.article, 2, Decimal('1000'))])
        self._tracer_vente(vente)

        r = self.api.post(
            self.url_annuler_ligne,
            data={
                'numero_facture': vente.numero_facture,
                'article_id': self.article.id,
                'motif': 'Article défectueux',
            },
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['motif_code'], 'ARTICLE_DEFECTUEUX')
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 8)

    def test_ligne_texte_libre_conserve_le_retour_en_stock(self):
        """Compatibilité : un ancien texte libre remet en stock."""
        vente = self._creer_vente(articles=[(self.article, 2, Decimal('1000'))])
        self._tracer_vente(vente)

        r = self.api.post(
            self.url_annuler_ligne,
            data={
                'numero_facture': vente.numero_facture,
                'article_id': self.article.id,
                'motif': 'Erreur de saisie caisse',
            },
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['motif_code'], '')
        self.assertTrue(r.json()['remis_en_stock'])
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)

    # ─────────────────────────────────────────────
    # Annulation de la FACTURE ENTIÈRE
    # ─────────────────────────────────────────────

    def test_facture_article_defectueux_aucun_retour(self):
        vente = self._creer_vente(
            articles=[(self.article, 2, Decimal('1000')),
                      (self.article2, 1, Decimal('2000'))]
        )
        self._tracer_vente(vente)

        r = self.api.post(
            self.url_annuler,
            data={
                'numero_facture': vente.numero_facture,
                'motif': 'Article défectueux',
                'motif_code': 'ARTICLE_DEFECTUEUX',
            },
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['motif_code'], 'ARTICLE_DEFECTUEUX')
        self.assertFalse(body['remis_en_stock'])

        # Aucun article remis en stock
        self.article.refresh_from_db()
        self.article2.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 8)
        self.assertEqual(self.article2.quantite_stock, 4)
        for ligne in body['stock_restaure']:
            self.assertFalse(ligne['remis_en_stock'])
            self.assertEqual(ligne['quantite_restauree'], 0)
            self.assertIn('valeur_sortie', ligne)

        # Deux traces de sortie, aucun retour
        self.assertEqual(MouvementStock.objects.filter(
            reference_document=f'ANNUL-DEF-{vente.numero_facture}',
            type_mouvement='SORTIE',
        ).count(), 2)
        self.assertFalse(MouvementStock.objects.filter(
            reference_document=f'ANNUL-{vente.numero_facture}',
            type_mouvement='RETOUR',
        ).exists())

        # Vente + lignes tracées, CA annulé
        vente.refresh_from_db()
        self.assertTrue(vente.est_annulee)
        self.assertEqual(vente.motif_annulation_code, 'ARTICLE_DEFECTUEUX')
        self.assertEqual(
            vente.lignes.filter(est_annulee=True).count(), 2
        )
        self.assertTrue(all(
            l.motif_annulation_code == 'ARTICLE_DEFECTUEUX'
            for l in vente.lignes.all()
        ))

    def test_facture_achat_par_erreur_remet_tout_en_stock(self):
        vente = self._creer_vente(
            articles=[(self.article, 2, Decimal('1000')),
                      (self.article2, 1, Decimal('2000'))]
        )
        self._tracer_vente(vente)

        r = self.api.post(
            self.url_annuler,
            data={
                'numero_facture': vente.numero_facture,
                'motif': 'Achat par erreur du client',
                'motif_code': 'ERREUR_COMMANDE',
            },
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['remis_en_stock'])

        self.article.refresh_from_db()
        self.article2.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)
        self.assertEqual(self.article2.quantite_stock, 5)
        self.assertTrue(MouvementStock.objects.filter(
            reference_document=f'ANNUL-{vente.numero_facture}',
            type_mouvement='RETOUR',
        ).count() >= 2)

        vente.refresh_from_db()
        self.assertTrue(vente.est_annulee)
        self.assertEqual(vente.motif_annulation_code, 'ERREUR_COMMANDE')

    def test_facture_ne_restocke_pas_une_ligne_deja_annulee(self):
        """Une ligne annulée individuellement ne doit pas être re-stockée deux fois."""
        vente = self._creer_vente(
            articles=[(self.article, 2, Decimal('1000')),
                      (self.article2, 1, Decimal('2000'))]
        )
        self._tracer_vente(vente)

        # Annulation individuelle de l'article 1 (retour en stock : 8 → 10)
        r = self.api.post(
            self.url_annuler_ligne,
            data={
                'numero_facture': vente.numero_facture,
                'article_id': self.article.id,
                'motif': 'Achat par erreur du client',
                'motif_code': 'ERREUR_COMMANDE',
            },
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)

        # Annulation de la facture entière : l'article 1 n'est pas restocké une 2e fois
        r2 = self.api.post(
            self.url_annuler,
            data={
                'numero_facture': vente.numero_facture,
                'motif': 'Achat par erreur du client',
                'motif_code': 'ERREUR_COMMANDE',
            },
            content_type='application/json', **self.entete
        )
        self.assertEqual(r2.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)
        self.assertEqual(MouvementStock.objects.filter(
            article=self.article,
            type_mouvement='RETOUR',
            reference_document=f'ANNUL-{vente.numero_facture}',
        ).count(), 0)
        # La 2e ligne (article2) est bien restockée
        self.article2.refresh_from_db()
        self.assertEqual(self.article2.quantite_stock, 5)


class AnnulationMotifBackOfficeTestCase(DemandeAnnulationBase):
    """Traçabilité back-office : journal de valeur cliquable."""

    def setUp(self):
        super().setUp()
        self.web.force_login(self.user)
        self.article.quantite_stock = 8
        self.article.save(update_fields=['quantite_stock'])
        self.vente = self._creer_vente(
            articles=[(self.article, 2, Decimal('1000'))]
        )
        MouvementStock.objects.create(
            article=self.article,
            type_mouvement='VENTE',
            quantite=2,
            stock_avant=10,
            stock_apres=8,
            reference_document=self.vente.numero_facture,
            utilisateur='T1',
            commentaire=f"Vente {self.vente.numero_facture}",
        )
        self.journal = JournalValeurStock.objects.get(
            boutique=self.boutique, date=timezone.localdate()
        )

    def _annuler_article_defectueux(self):
        r = self.api.post(
            self.url_annuler_ligne,
            data={
                'numero_facture': self.vente.numero_facture,
                'article_id': self.article.id,
                'motif': 'Article défectueux',
                'motif_code': 'ARTICLE_DEFECTUEUX',
            },
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 200)
        self.journal.refresh_from_db()
        return r

    def _detail(self, champ):
        return self.web.get(reverse(
            'inventory:detail_valeur_journal',
            args=[self.boutique.id, self.journal.id, champ],
        ))

    def test_detail_stock_sorti_affiche_la_sortie(self):
        self._annuler_article_defectueux()

        r = self._detail('valeur_stock_sorti')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.article.nom)
        self.assertContains(r, 'ANNUL-DEF-')
        # Le détail totalise exactement la valeur du journal (aucun écart)
        self.assertContains(r, 'Coherent')

    def test_detail_ventes_recompense_la_valeur_sortie(self):
        self._annuler_article_defectueux()

        r = self._detail('valeur_ventes')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Annulation défectueuse')
        self.assertContains(r, 'Coherent')

    def test_detail_stock_ajoute_sans_annulation_defectueuse(self):
        r = self._detail('valeur_stock_sorti')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Aucun mouvement de ce type')

    def test_journal_coherent_apres_annulation_defectueuse(self):
        self._annuler_article_defectueux()

        self.journal.refresh_from_db()
        self.assertEqual(self.journal.valeur_stock_sorti, Decimal('2000'))
        self.assertEqual(self.journal.valeur_ventes, Decimal('0'))
        # Formule de cohérence : rien n'a changé côté valeur réelle
        self.assertEqual(
            self.journal.valeur_stock_restant,
            self.journal.valeur_stock_precedent + self.journal.montant_inventaire
            + self.journal.valeur_stock_ajoute + self.journal.valeur_transfert_entrant
            + self.journal.impact_modification_prix
            - self.journal.valeur_stock_sorti - self.journal.valeur_transfert_sortant
            - self.journal.valeur_ventes,
        )


class AnnulationAffichageListeFacturesTestCase(DemandeAnnulationBase):
    """Articles annulés affichés en ROUGE (nom, quantité, valeur, cas) dans la liste des factures."""

    def setUp(self):
        super().setUp()
        self.web.force_login(self.user)
        self.article.quantite_stock = 8
        self.article.save(update_fields=['quantite_stock'])

    def _annuler_un_article(self, motif, code):
        vente = self._creer_vente(
            articles=[(self.article, 2, Decimal('1000')),
                      (self.article2, 1, Decimal('500'))]
        )
        r = self.api.post(
            self.url_annuler_ligne,
            data={
                'numero_facture': vente.numero_facture,
                'article_id': self.article.id,
                'motif': motif,
                'motif_code': code,
            },
            content_type='application/json', **self.entete
        )
        self.assertEqual(r.status_code, 200)
        return vente

    def test_affichage_cas_article_defectueux(self):
        vente = self._annuler_un_article('Article défectueux', 'ARTICLE_DEFECTUEUX')
        ligne = vente.lignes.get(article=self.article)

        self.assertFalse(ligne.remis_en_stock)
        self.assertIn('Article défectueux', ligne.statut_annulation)
        self.assertIn('non remis en stock', ligne.statut_annulation)

        self.assertEqual([l.id for l in vente.lignes_annulees], [ligne.id])
        self.assertEqual(vente.nb_articles_actifs, 1)

    def test_affichage_cas_achat_par_erreur(self):
        vente = self._annuler_un_article('Achat par erreur du client', 'ERREUR_COMMANDE')
        ligne = vente.lignes.get(article=self.article)

        self.assertTrue(ligne.remis_en_stock)
        self.assertIn('Achat par erreur du client', ligne.statut_annulation)
        self.assertIn('remis en stock', ligne.statut_annulation)
        self.assertNotIn('non remis en stock', ligne.statut_annulation)
        self.assertEqual(len(vente.lignes_annulees), 1)

    def test_liste_factures_affiche_l_article_annule(self):
        vente = self._annuler_un_article('Article défectueux', 'ARTICLE_DEFECTUEUX')

        r = self.web.get(reverse(
            'inventory:commercant_ventes_boutique', args=[self.boutique.id]
        ))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Article(s) annulé(s)')
        self.assertContains(r, self.article.nom)
        self.assertContains(r, 'non remis en stock')
        self.assertContains(r, vente.numero_facture)


class CaNetAnnulationDifferieeTestCase(DemandeAnnulationBase):
    """Un remboursement est impute au CA du JOUR d'annulation :
    la journee de la vente (cloturee) ne bouge pas."""

    def setUp(self):
        super().setUp()
        self.web.force_login(self.user)

    def _perimetre(self):
        return Vente.objects.filter(boutique=self.boutique, paye=True)

    def _annuler_article_differe(self, vente, article, motif, code):
        """Annule un article d'une vente d'hier (prolongation accordee)."""
        self._demander(vente, type_demande='LIGNE', article=article)
        r_web = self.web.post(
            reverse('inventory:accorder_extension_annulation', args=[self.boutique.id]),
            {'demande_id': DemandeAnnulationVente.objects.get(vente=vente).id},
        )
        self.assertEqual(r_web.status_code, 302)
        r = self.api.post(
            self.url_annuler_ligne,
            data={
                'numero_facture': vente.numero_facture,
                'article_id': article.id,
                'motif': motif,
                'motif_code': code,
            },
            content_type='application/json', **self.entete,
        )
        self.assertEqual(r.status_code, 200)
        return r

    def _annuler_vente_differee(self, vente, motif, code):
        """Annule toute une vente d'hier (prolongation accordee)."""
        self._demander(vente)
        r_web = self.web.post(
            reverse('inventory:accorder_extension_annulation', args=[self.boutique.id]),
            {'demande_id': DemandeAnnulationVente.objects.get(vente=vente).id},
        )
        self.assertEqual(r_web.status_code, 302)
        r = self.api.post(
            self.url_annuler,
            data={
                'numero_facture': vente.numero_facture,
                'motif': motif,
                'motif_code': code,
            },
            content_type='application/json', **self.entete,
        )
        self.assertEqual(r.status_code, 200)
        return r

    def test_annulation_differee_reduit_le_ca_du_jour(self):
        vente = self._creer_vente(
            heures_ecoulees=26, articles=[(self.article, 2, Decimal('1000'))]
        )
        hier = vente.date_vente.date()
        aujourd_hui = timezone.localdate()
        self.assertNotEqual(hier, aujourd_hui)

        self._annuler_article_differe(
            vente, self.article, 'Article défectueux', 'ARTICLE_DEFECTUEUX'
        )

        # La journee de la vente (cloturee) reste inchangee
        self.assertEqual(
            ca_net(
                self._perimetre().filter(date_vente__date=hier),
                self._perimetre(), hier, hier,
            ),
            Decimal('2000'),
        )
        # Le remboursement est impute au CA d'aujourd'hui
        self.assertEqual(
            remboursements(self._perimetre(), aujourd_hui, aujourd_hui),
            Decimal('2000'),
        )
        self.assertEqual(
            ca_net(
                self._perimetre().filter(date_vente__date=aujourd_hui),
                self._perimetre(), aujourd_hui, aujourd_hui,
            ),
            Decimal('-2000'),
        )

    def test_annulation_totale_differee_imputee_au_jour_d_annulation(self):
        vente = self._creer_vente(
            heures_ecoulees=26, articles=[(self.article, 2, Decimal('1000'))]
        )
        hier = vente.date_vente.date()
        aujourd_hui = timezone.localdate()

        self._annuler_vente_differee(
            vente, 'Achat par erreur du client', 'ERREUR_COMMANDE'
        )
        vente.refresh_from_db()
        self.assertTrue(vente.est_annulee)
        # montant_total n'est pas modifie par une annulation totale
        self.assertEqual(vente.montant_total, Decimal('2000'))

        self.assertEqual(
            ca_net(
                self._perimetre().filter(date_vente__date=hier),
                self._perimetre(), hier, hier,
            ),
            Decimal('2000'),
        )
        self.assertEqual(
            remboursements(self._perimetre(), aujourd_hui, aujourd_hui),
            Decimal('2000'),
        )
        self.assertEqual(
            ca_net(
                self._perimetre().filter(date_vente__date=aujourd_hui),
                self._perimetre(), aujourd_hui, aujourd_hui,
            ),
            Decimal('-2000'),
        )

    def test_annulation_du_jour_conserve_le_ca_net(self):
        vente = self._creer_vente(articles=[
            (self.article, 2, Decimal('1000')),
            (self.article2, 1, Decimal('500')),
        ])
        r = self.api.post(
            self.url_annuler_ligne,
            data={
                'numero_facture': vente.numero_facture,
                'article_id': self.article.id,
                'motif': 'Article défectueux',
                'motif_code': 'ARTICLE_DEFECTUEUX',
            },
            content_type='application/json', **self.entete,
        )
        self.assertEqual(r.status_code, 200)

        # La facture du jour reste au montant encaisse (2500 - 2000 rembourse)
        aujourd_hui = timezone.localdate()
        self.assertEqual(
            ca_net(
                self._perimetre().filter(date_vente__date=aujourd_hui),
                self._perimetre(), aujourd_hui, aujourd_hui,
            ),
            Decimal('500'),
        )

    def test_dashboard_commercant_integre_le_remboursement(self):
        vente = self._creer_vente(
            heures_ecoulees=26, articles=[(self.article, 2, Decimal('1000'))]
        )
        self._annuler_article_differe(
            vente, self.article, 'Achat par erreur du client', 'ERREUR_COMMANDE'
        )

        r = self.web.get(reverse('inventory:commercant_dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['recette_jour'], Decimal('-2000'))
        self.assertEqual(r.context['remboursements_jour'], Decimal('2000'))

    def test_dashboard_boutique_integre_le_remboursement(self):
        vente = self._creer_vente(
            heures_ecoulees=26, articles=[(self.article, 2, Decimal('1000'))]
        )
        self._annuler_article_differe(
            vente, self.article, 'Article défectueux', 'ARTICLE_DEFECTUEUX'
        )

        r = self.web.get(reverse('inventory:entrer_boutique', args=[self.boutique.id]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['ca_jour'], Decimal('-2000'))
        self.assertEqual(r.context['remboursements_jour'], Decimal('2000'))

    def test_stats_websocket_net_des_remboursements(self):
        from inventory.api_views_v2_simple import _compute_dashboard_stats

        vente = self._creer_vente(
            heures_ecoulees=26, articles=[(self.article, 2, Decimal('1000'))]
        )
        self._annuler_article_differe(
            vente, self.article, 'Article défectueux', 'ARTICLE_DEFECTUEUX'
        )

        stats = _compute_dashboard_stats(self.boutique)
        self.assertEqual(stats['ca_jour'], -2000.0)
        self.assertEqual(stats['remboursements_jour'], 2000.0)

    def test_liste_factures_affiche_la_date_de_remboursement(self):
        vente = self._creer_vente(articles=[(self.article, 2, Decimal('1000'))])
        r = self.api.post(
            self.url_annuler_ligne,
            data={
                'numero_facture': vente.numero_facture,
                'article_id': self.article.id,
                'motif': 'Article défectueux',
                'motif_code': 'ARTICLE_DEFECTUEUX',
            },
            content_type='application/json', **self.entete,
        )
        self.assertEqual(r.status_code, 200)

        r = self.web.get(reverse(
            'inventory:commercant_ventes_boutique', args=[self.boutique.id]
        ))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'remboursement imputé au CA du jour')
        self.assertContains(r, 'Remboursé le')
