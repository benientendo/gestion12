"""
Bouton « Imprimer » de la LISTE du journal de valeur du stock
=============================================================
La page du journal (une ligne par jour) propose maintenant un bouton
Imprimer, sur le même modèle que le détail d'une valeur :

- à l'écran : en-tête, carte « valeur stock actuelle » et filtre de dates
  masqués à l'impression (classe ``no-print``) ;
- à l'impression : en-tête structuré réservé (classe ``print-only``) avec
  boutique, période affichée, valeur stock actuelle, nombre de jours et
  date d'édition ;
- le tableau s'imprime en entier (zone défilante neutralisée), avec
  bordures et en-tête de colonnes répété sur chaque page ;
- navigation, badges d'aide et liens restent lisibles mais discrets.

Contrôles :
- le bouton est présent et correctement structuré ;
- l'en-tête structuré porte bien la période et la valeur demandées ;
- les éléments d'écran seuls sont exclus de l'impression ;
- les règles CSS d'impression sont en place.
"""
from django.contrib.humanize.templatetags.humanize import intcomma
from django.urls import reverse
from django.utils import timezone

from inventory.models import JournalValeurStock
from inventory.tests.test_demande_annulation import DemandeAnnulationBase


class ImprimerListeJournalTestCase(DemandeAnnulationBase):

    def setUp(self):
        super().setUp()
        self.web.force_login(self.user)
        self.journal, _ = JournalValeurStock.objects.get_or_create(
            boutique=self.boutique, date=timezone.localdate(),
        )

    def _journal(self, params=None):
        r = self.web.get(
            reverse('inventory:journal_valeur_stock_boutique',
                    args=[self.boutique.id]),
            params or {},
        )
        self.assertEqual(r.status_code, 200)
        return r

    def _bloc_imprime(self, params=None):
        """Bloc en-tête structuré réservé à l'impression."""
        html = self._journal(params).content.decode('utf-8')
        return html.split('class="print-only mb-3"', 1)[1]

    # ──────────────────────────────────────────────
    # Présence et structure du bouton
    # ──────────────────────────────────────────────

    def test_bouton_imprimer_present(self):
        r = self._journal()
        self.assertContains(r, 'window.print()')
        self.assertContains(
            r, 'class="btn btn-outline-primary" onclick="window.print()"',
        )
        self.assertContains(r, '<i class="fas fa-print"></i> Imprimer')

    def test_retour_au_dashboard_present(self):
        # Le bouton de retour n'est pas perdu en route
        r = self._journal()
        self.assertContains(r, reverse(
            'inventory:entrer_boutique', args=[self.boutique.id],
        ))

    # ──────────────────────────────────────────────
    # En-tête structuré réservé à l'impression
    # ──────────────────────────────────────────────

    def test_entete_imprime_present(self):
        r = self._journal()
        self.assertContains(r, 'class="print-only mb-3"')
        # Le bloc est bien fermé (sinon tout le HTML suivant serait imprimé)
        html = r.content.decode('utf-8')
        self.assertIn('Édité le', html.split('class="print-only mb-3"', 1)[1])

    def test_entete_imprime_porte_la_boutique_et_la_periode(self):
        debut = timezone.localdate().replace(day=1)
        fin = timezone.localdate()

        bloc = self._bloc_imprime({
            'date_debut': debut.isoformat(),
            'date_fin': fin.isoformat(),
        })
        self.assertIn(self.boutique.nom, bloc)
        self.assertIn('Journal de valeur du stock', bloc)
        self.assertIn('Période du', bloc)
        self.assertIn(debut.strftime('%d/%m/%Y'), bloc)
        self.assertIn(fin.strftime('%d/%m/%Y'), bloc)

    def test_entete_imprime_porte_la_valeur_et_le_nombre_de_jours(self):
        r = self._journal()
        html = r.content.decode('utf-8')
        lignes = list(r.context['lignes'])

        bloc = html.split('class="print-only mb-3"', 1)[1]
        self.assertIn('Valeur stock actuelle', bloc)
        self.assertIn('Jours renseignés', bloc)
        self.assertIn('FC', bloc)
        # Le nombre de jours imprimé est bien celui du tableau affiché
        self.assertIn(f'<td class="text-end">{len(lignes)}</td>', bloc)
        tableau = html.split('journal-table mb-0">', 1)[1]
        corps = tableau.split('<tbody>', 1)[1].split('</tbody>', 1)[0]
        self.assertEqual(corps.count('<tr>'), len(lignes))

    def test_entete_imprime_signale_la_date_d_edition(self):
        bloc = self._bloc_imprime()
        self.assertIn('Édité le', bloc)
        self.assertIn('Gestion Magazin', bloc)

    def test_entete_imprime_reprend_le_montant_formate(self):
        # La valeur affichée est celle du dashboard, formatée avec intcomma
        valeur = self._journal().context['valeur_stock_actuelle']
        self.assertGreater(valeur, 0)
        bloc = self._bloc_imprime()
        self.assertIn(intcomma(int(valeur)), bloc)

    # ──────────────────────────────────────────────
    # Éléments d'écran exclus de l'impression
    # ──────────────────────────────────────────────

    def test_titre_et_actions_masques_a_l_impression(self):
        r = self._journal()
        # L'en-tête écran (titre + boutons Imprimer / Retour) est no-print
        self.assertContains(r, '<div class="row mb-3 no-print">')

    def test_carte_valeur_et_filtre_masques_a_l_impression(self):
        html = self._journal().content.decode('utf-8')
        # La carte « valeur stock actuelle » (reprise dans l'en-tête imprimé)
        self.assertIn(
            '<!-- Valeur stock actuelle (écran : reprise dans '
            "l'en-tête structuré) -->\n    <div class=\"row mb-3 no-print\">",
            html,
        )
        # Le filtre de dates est dans cette même rangée no-print
        self.assertIn('<input type="date" name="date_debut"', html)

    def test_les_actions_ecran_sont_avant_le_bloc_imprime(self):
        html = self._journal().content.decode('utf-8')
        pos_bloc = html.find('class="print-only mb-3"')
        self.assertGreater(pos_bloc, 0)
        # Le bouton Imprimer et le retour dashboard sont dans l'en-tête
        # écran, AVANT le bloc réservé à l'impression
        self.assertIn('window.print()', html[:pos_bloc])
        self.assertIn(
            reverse('inventory:entrer_boutique', args=[self.boutique.id]),
            html[:pos_bloc],
        )
        self.assertNotIn('window.print()', html[pos_bloc:])
        # La carte « valeur stock actuelle » de l'écran suit le bloc imprimé
        # (elle est reprise dans le bloc, puis masquée à l'impression)
        self.assertGreater(
            html.find('Valeur stock actuelle (CDF)'), pos_bloc,
        )

    # ──────────────────────────────────────────────
    # Mise en page d'impression du tableau
    # ──────────────────────────────────────────────

    def test_regle_css_d_impression_presente(self):
        html = self._journal().content.decode('utf-8')
        self.assertIn('@media print', html)
        # La zone défilante est neutralisée : toutes les lignes s'impriment
        self.assertIn('.table-responsive { max-height: none !important;', html)
        # En-tête de colonnes répété sur chaque page imprimée
        self.assertIn('.journal-table thead { display: table-header-group; }',
                      html)
        # Navigation et pied de page jamais imprimés
        self.assertIn('.topbar, footer', html)
        # Les badges d'aide (« Cliquez sur une valeur ») sont masqués
        self.assertIn('.card-header .badge { display: none !important; }', html)

    def test_le_tableau_des_lignes_s_imprime(self):
        # Les valeurs du journal restent cliquables à l'écran ; à l'impression
        # le tableau est bordé et lisible
        html = self._journal().content.decode('utf-8')
        self.assertIn('.journal-table th, .journal-table td {', html)
        self.assertIn('border: 1px solid #999 !important;', html)

    def test_sans_donnee_le_journal_s_imprime_quand_meme(self):
        # Aucune ligne sur une période vide : le bouton reste disponible
        r = self._journal({
            'date_debut': '2000-01-01',
            'date_fin': '2000-01-02',
        })
        self.assertContains(r, 'window.print()')
        self.assertContains(r, 'Aucune donnée pour cette période')
        self.assertIn('<th>Jours renseignés</th>',
                      r.content.decode('utf-8').split(
                          'class="print-only mb-3"', 1)[1])
