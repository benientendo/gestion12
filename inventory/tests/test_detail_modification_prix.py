"""
Détail « Modif. prix » du journal de valeur (back-office)
=========================================================
Clic sur le montant de la colonne « Modif. prix » → la page détail liste les
articles dont le prix de vente a changé ce jour-là : ancien prix, nouveau prix,
variation (%), stock au moment du changement, impact sur la valeur et auteur.
L'impact des détails doit totaliser la valeur affichée dans le journal.
"""
from decimal import Decimal

from django.contrib.humanize.templatetags.humanize import intcomma
from django.urls import reverse
from django.utils import timezone

from inventory.models import DetailModificationPrix, JournalValeurStock
from inventory.tests.test_demande_annulation import DemandeAnnulationBase


class DetailModificationPrixTestCase(DemandeAnnulationBase):

    def setUp(self):
        super().setUp()
        self.web.force_login(self.user)

    # ──────────────────────────────────────────────
    # Aides
    # ──────────────────────────────────────────────

    def _journal_du_jour(self):
        return JournalValeurStock.objects.get(
            boutique=self.boutique, date=timezone.localdate()
        )

    def _modifier_prix(self, article, prix):
        """Modification de prix passée par le back-office (XHR, comme l'UI)."""
        return self.web.post(
            reverse('inventory:modifier_prix_article', args=[
                self.boutique.id, article.id,
            ]),
            data={'prix_vente': str(prix)},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def _detail(self, journal=None):
        journal = journal or self._journal_du_jour()
        return self.web.get(reverse(
            'inventory:detail_valeur_journal',
            args=[self.boutique.id, journal.id, 'impact_modification_prix'],
        ))

    # ──────────────────────────────────────────────
    # Enregistrement du détail
    # ──────────────────────────────────────────────

    def test_modification_prix_cree_une_ligne_de_detail(self):
        r = self._modifier_prix(self.article, '1500')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['success'])

        self.assertEqual(DetailModificationPrix.objects.count(), 1)
        d = DetailModificationPrix.objects.get()
        self.assertEqual(d.journal, self._journal_du_jour())
        self.assertEqual(d.article, self.article)
        self.assertEqual(d.article_nom, 'Savon')
        self.assertEqual(d.article_code, 'ART-ANN-1')
        self.assertEqual(d.devise, 'CDF')
        self.assertEqual(d.ancien_prix, Decimal('1000'))
        self.assertEqual(d.nouveau_prix, Decimal('1500'))
        self.assertEqual(d.quantite_stock, 10)
        # (1500 − 1000) × 10 en stock = 5000
        self.assertEqual(d.impact, Decimal('5000'))
        # Traçabilité : on sait QUI a modifié le prix
        self.assertTrue(d.utilisateur)

    def test_impact_du_detail_alimente_le_journal(self):
        self._modifier_prix(self.article, '1500')

        journal = self._journal_du_jour()
        self.assertEqual(journal.impact_modification_prix, Decimal('5000'))

    def test_prix_inchange_ne_cree_aucun_detail(self):
        DetailModificationPrix.objects.all().delete()
        self.article.save()  # enregistrement sans changement de prix

        self.assertEqual(DetailModificationPrix.objects.count(), 0)

    def test_detail_pour_chaque_article_modifie(self):
        self._modifier_prix(self.article, '1500')   # (1500 − 1000) × 10 = +5000
        self._modifier_prix(self.article2, '1750')  # (1750 − 2000) × 5  = −1250

        self.assertEqual(DetailModificationPrix.objects.count(), 2)
        journal = self._journal_du_jour()
        self.assertEqual(journal.impact_modification_prix, Decimal('3750'))

        r = self._detail()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Savon')
        self.assertContains(r, 'Huile')

    # ──────────────────────────────────────────────
    # Affichage : clic sur le montant
    # ──────────────────────────────────────────────

    def test_montant_du_journal_renvoie_vers_le_detail(self):
        self._modifier_prix(self.article, '1500')
        journal = self._journal_du_jour()

        r = self.web.get(reverse(
            'inventory:journal_valeur_stock_boutique', args=[self.boutique.id],
        ))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, reverse(
            'inventory:detail_valeur_journal',
            args=[self.boutique.id, journal.id, 'impact_modification_prix'],
        ))

    def test_detail_affiche_les_articles_et_les_prix(self):
        self._modifier_prix(self.article, '1500')

        r = self._detail()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Savon')
        self.assertContains(r, 'ART-ANN-1')
        self.assertContains(r, intcomma('1000'))
        self.assertContains(r, intcomma('1500'))
        self.assertContains(r, intcomma('5000'))
        # Cohérence : le détail totalise exactement la valeur du journal
        self.assertContains(r, 'Coherent')

    def test_detail_est_coherent_meme_apres_deux_modifications(self):
        self._modifier_prix(self.article, '1500')
        self._modifier_prix(self.article2, '1750')

        r = self._detail()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Coherent')
        self.assertContains(r, intcomma('3750'))

    # ──────────────────────────────────────────────
    # Cas sans détail (journée sans modification, données historiques)
    # ──────────────────────────────────────────────

    def test_journee_sans_modification_affiche_un_message(self):
        JournalValeurStock.objects.get_or_create(
            boutique=self.boutique, date=timezone.localdate(),
        )

        r = self._detail()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Aucun prix de vente')

    def test_valeur_sans_detail_signale_les_donnees_historiques(self):
        # Valeur présente dans le journal mais aucun détail enregistré
        # (modification effectuée avant la mise en place du traçage).
        journal, _ = JournalValeurStock.objects.get_or_create(
            boutique=self.boutique, date=timezone.localdate(),
        )
        journal.impact_modification_prix = Decimal('5000')
        journal.save()
        self.assertEqual(journal.details_modification_prix.count(), 0)

        r = self._detail(journal)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Le journal totalise')
        self.assertNotContains(r, 'Coherent')
