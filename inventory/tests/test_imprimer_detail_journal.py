"""
Bouton « Imprimer » du détail d'une valeur du journal de stock
==============================================================
Chaque page de détail (Stock réel, Stock ajouté, Ventes, Réduction,
Transfert IN/OUT, Inventaire, Modif. prix, Stock préc., Stock sorti)
propose un bouton Imprimer qui produit un rapport structuré :

- à l'écran : en-tête + boutons masqués à l'impression (classe no-print) ;
- à l'impression : en-tête structuré réservé (classe print-only) avec
  boutique, date du journal, valeur, total du détail, écart, description,
  message de cohérence et date d'édition ;
- le tableau s'imprime en entier (plus de zone défilante), avec bordures
  et en-tête de colonnes répété sur chaque page.

Contrôles :
- le bouton est présent sur CHAQUE valeur du journal ;
- l'en-tête structuré porte bien la valeur demandée ;
- les valeurs sans détail (mode info) impriment aussi ;
- l'écran seul (titre, bouton, carte valeur) est exclu de l'impression.
"""
from django.contrib.humanize.templatetags.humanize import intcomma
from django.urls import reverse
from django.utils import timezone

from inventory.models import JournalValeurStock
from inventory.tests.test_demande_annulation import DemandeAnnulationBase
from inventory.views_commercant import LIBELLES_DETAIL_JOURNAL


class ImprimerDetailJournalTestCase(DemandeAnnulationBase):

    def setUp(self):
        super().setUp()
        self.web.force_login(self.user)
        self.journal, _ = JournalValeurStock.objects.get_or_create(
            boutique=self.boutique, date=timezone.localdate(),
        )

    def _detail(self, champ):
        return self.web.get(reverse(
            'inventory:detail_valeur_journal',
            args=[self.boutique.id, self.journal.id, champ],
        ))

    def _bloc_imprime(self, champ):
        """Bloc en-tête structuré réservé à l'impression."""
        r = self._detail(champ)
        self.assertEqual(r.status_code, 200)
        return r.content.decode('utf-8').split('class="print-only mb-3"', 1)[1]

    # ──────────────────────────────────────────────
    # Présence du bouton sur toutes les valeurs
    # ──────────────────────────────────────────────

    def test_bouton_imprimer_sur_chaque_valeur(self):
        for champ, (libelle, _desc) in LIBELLES_DETAIL_JOURNAL.items():
            r = self._detail(champ)
            self.assertEqual(r.status_code, 200, f'{champ} → {r.status_code}')
            self.assertContains(
                r, 'window.print()', msg_prefix=f'bouton manquant ({libelle})',
            )
            self.assertContains(
                r, 'class="btn btn-outline-primary" onclick="window.print()"',
                msg_prefix=f'bouton non structuré ({libelle})',
            )

    def test_titre_et_action_masques_a_l_impression(self):
        r = self._detail('valeur_stock_reel')
        self.assertEqual(r.status_code, 200)
        # L'en-tête écran (titre + boutons) porte la classe no-print
        self.assertContains(r, '<div class="row mb-3 no-print">')
        # Et le bloc print-only existe bien
        self.assertContains(r, 'class="print-only mb-3"')

    # ──────────────────────────────────────────────
    # En-tête structuré réservé à l'impression
    # ──────────────────────────────────────────────

    def test_entete_imprime_porte_la_valeur(self):
        r = self._detail('valeur_stock_reel')
        html = r.content.decode('utf-8')

        bloc = html.split('class="print-only mb-3"', 1)[1]
        self.assertIn(self.boutique.nom, bloc)
        self.assertIn('Stock réel', bloc)
        self.assertIn('Journal de valeur du stock du', bloc)
        self.assertIn('Valeur du journal', bloc)
        self.assertIn('Détail totalisé', bloc)
        self.assertIn('Édité le', bloc)
        self.assertIn('Gestion Magazin', bloc)
        # La description de la valeur est reprise dans l'en-tête
        self.assertIn('quantité × prix de vente', bloc)

    def test_entete_imprime_signale_l_ecart(self):
        # Détail calculé à partir des articles, valeur du journal forcée à
        # autre chose → l'écart est annoncé dans l'en-tête imprimé.
        self.journal.valeur_stock_reel = 1
        self.journal.save()

        bloc = self._bloc_imprime('valeur_stock_reel')
        self.assertIn('<th>Écart</th>', bloc)
        # (l'apostrophe est échappée en HTML : fragment sans elle)
        self.assertIn('initiation INIT-/REGL- et soldes initiaux exclus', bloc)

    def test_entete_imprime_signale_la_coherence(self):
        total = sum(
            art.quantite_stock * (art.prix_vente or 0)
            for art in self.boutique.articles.filter(
                est_actif=True, quantite_stock__gt=0, devise='CDF',
            )
        )
        self.assertGreater(total, 0)
        self.journal.valeur_stock_reel = total
        self.journal.save()

        bloc = self._bloc_imprime('valeur_stock_reel')
        self.assertIn('Cohérent', bloc)
        self.assertIn('<th>Écart</th>', bloc)

    def test_entete_imprime_sans_ecart_en_mode_info(self):
        # « Stock préc. » : mode info, pas de tableau → pas de ligne d'écart
        r = self._detail('valeur_stock_precedent')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode('utf-8')
        self.assertIn('window.print()', html)
        bloc = html.split('class="print-only mb-3"', 1)[1]
        self.assertIn('Stock préc.', bloc)
        self.assertNotIn('<th>Écart</th>', bloc)
        # Le message explicatif, lui, s'imprime avec la carte de détail
        self.assertIn('valeur réelle du stock', html)

    def test_entete_imprime_reprend_le_montant_formate(self):
        self.journal.valeur_stock_reel = 1234567
        self.journal.save()

        bloc = self._bloc_imprime('valeur_stock_reel')
        self.assertIn(intcomma('1234567'), bloc)

    # ──────────────────────────────────────────────
    # Mise en page d'impression du tableau
    # ──────────────────────────────────────────────

    def test_regle_css_d_impression_presente(self):
        r = self._detail('valeur_stock_reel')
        html = r.content.decode('utf-8')
        self.assertIn('@media print', html)
        # La zone défilante est neutralisée : toutes les lignes s'impriment
        self.assertIn('.table-responsive { max-height: none !important;', html)
        # En-tête de colonnes répété sur chaque page imprimée
        self.assertIn('.detail-table thead { display: table-header-group; }', html)
        # Navigation et pied de page jamais imprimés
        self.assertIn('.topbar, footer', html)
