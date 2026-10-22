"""
Rapport d'inventaire imprimable : valeur des articles comptés, au prix de vente
===============================================================================
- Les pages détail (boutique et dépôt) affichent la valeur du stock COMPTÉ
  (seuls les articles inventorier avec une quantité saisie), au PRIX DE VENTE.
- Une route lecture seule imprime un procès-verbal signable (3 signatures).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from inventory.models import (
    Article, Boutique, ClotureJournee, Commercant, Inventaire, LigneInventaire,
)
from inventory.views_commercant import _totaux_valeur_inventaire

User = get_user_model()


class ValeurInventaireBase(TestCase):
    """3 articles : surplus +2, manque −3, un non compté."""

    def setUp(self):
        self.user_commercant = User.objects.create_user(
            username='pv_comm', password='x', email='pv_comm@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='PV SARL', nom_responsable='Gérant Propriétaire',
            email='pv_comm@test.cd', user=self.user_commercant,
        )
        self.boutique = Boutique.objects.create(
            nom='PV PDV', commercant=self.commercant, code_boutique='BT-PV-001',
        )
        self.depot = Boutique.objects.create(
            nom='PV Dépôt', commercant=self.commercant, est_depot=True,
            code_boutique='DP-PV-001',
        )

        self.art_surplus = Article.objects.create(
            boutique=self.boutique, code='PV-A', nom='Savon',
            prix_achat=Decimal('100'), prix_vente=Decimal('200'), quantite_stock=12,
        )
        self.art_manque = Article.objects.create(
            boutique=self.boutique, code='PV-B', nom='Eponge',
            prix_achat=Decimal('50'), prix_vente=Decimal('80'), quantite_stock=5,
        )
        self.art_non_compte = Article.objects.create(
            boutique=self.boutique, code='PV-C', nom='Balai',
            prix_achat=Decimal('20'), prix_vente=Decimal('30'), quantite_stock=4,
        )

        self.inventaire = Inventaire.objects.create(
            boutique=self.boutique, reference='INV-PV-001',
            date_inventaire=date.today(), statut='TERMINE',
            cree_par=self.user_commercant,
        )
        LigneInventaire.objects.create(
            inventaire=self.inventaire, article=self.art_surplus,
            stock_theorique=10, stock_physique=12, prix_unitaire=Decimal('100'),
        )
        LigneInventaire.objects.create(
            inventaire=self.inventaire, article=self.art_manque,
            stock_theorique=8, stock_physique=5, prix_unitaire=Decimal('50'),
        )
        LigneInventaire.objects.create(
            inventaire=self.inventaire, article=self.art_non_compte,
            stock_theorique=4, stock_physique=None, prix_unitaire=Decimal('30'),
        )
        self.inventaire.calculer_statistiques()

        self.client.force_login(self.user_commercant)


class TotauxValeurInventaireTest(ValeurInventaireBase):

    def test_totaux_prix_de_vente_des_seuls_articles_comptes(self):
        totaux = _totaux_valeur_inventaire(self.inventaire.lignes.all())
        # Seuls les 2 articles comptés sont valorisés, au prix de vente :
        # 12×200 + 5×80 = 2800 (l'article non compté est exclu)
        self.assertEqual(totaux['valeur_stock_vente'], Decimal('2800'))
        self.assertNotIn('valeur_stock_achat', totaux)
        # surplus +2 → 2×200 ; manque −3 → 3×80
        self.assertEqual(totaux['valeur_ecart_positif_vente'], Decimal('400'))
        self.assertEqual(totaux['valeur_ecart_negatif_vente'], Decimal('240'))

    def test_lignes_non_comptees_exclues_du_total(self):
        totaux = _totaux_valeur_inventaire(
            LigneInventaire.objects.filter(stock_physique__isnull=True)
        )
        self.assertEqual(totaux['valeur_stock_vente'], Decimal(0))
        self.assertEqual(totaux['valeur_ecart_positif_vente'], Decimal(0))
        self.assertEqual(totaux['valeur_ecart_negatif_vente'], Decimal(0))


class PageDetailValeurStockTest(ValeurInventaireBase):

    def test_detail_boutique_affiche_valeur_vente_des_comptes(self):
        r = self.client.get(reverse(
            'inventory:detail_inventaire_boutique',
            args=[self.boutique.id, self.inventaire.id]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['valeur_stock_vente'], Decimal('2800'))
        self.assertContains(r, 'Valeur du stock compté (prix de vente)')
        self.assertNotContains(r, 'Valeur stock (achat)')
        self.assertContains(r, 'Imprimer le rapport')

    def test_detail_depot_affiche_valeur_vente_des_comptes(self):
        inventaire_depot = Inventaire.objects.create(
            boutique=self.depot, reference='INV-PV-DEP-001',
            date_inventaire=date.today(), statut='EN_COURS',
            cree_par=self.user_commercant,
        )
        article = Article.objects.create(
            boutique=self.depot, code='PV-D', nom='Bidon',
            prix_achat=Decimal('10'), prix_vente=Decimal('25'), quantite_stock=6,
        )
        LigneInventaire.objects.create(
            inventaire=inventaire_depot, article=article,
            stock_theorique=6, stock_physique=6, prix_unitaire=Decimal('10'),
        )
        inventaire_depot.calculer_statistiques()

        r = self.client.get(reverse(
            'inventory:detail_inventaire',
            args=[self.depot.id, inventaire_depot.id]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['valeur_stock_vente'], Decimal('150'))
        self.assertContains(r, 'Valeur du stock compté (prix de vente)')


class RapportImprimableTest(ValeurInventaireBase):

    def test_imprimer_boutique(self):
        r = self.client.get(reverse(
            'inventory:imprimer_inventaire_boutique',
            args=[self.boutique.id, self.inventaire.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Procès-verbal d'inventaire")
        self.assertContains(r, 'INV-PV-001')
        self.assertContains(r, 'Valeur du stock compté')
        self.assertContains(r, '2 800')  # 12×200 + 5×80, seuls articles comptés
        self.assertNotContains(r, 'Valeur achat')  # plus de colonne / valeur d'achat
        self.assertContains(r, 'Déclaration et engagement')
        self.assertContains(r, 'Inventaire effectué par')
        self.assertContains(r, 'Approuvé par le Propriétaire')
        self.assertContains(r, 'Signature')
        # Détail des lignes : seuls les articles saisis figurent au tableau
        self.assertContains(r, 'Savon')
        self.assertContains(r, 'Eponge')
        # Article non saisi : exclu du tableau (les alertes latérales peuvent
        # malgré tout citer son nom, on vérifie donc le code propre au tableau)
        self.assertNotContains(r, '<code>PV-C</code>')
        self.assertEqual(
            sorted(l.article.code for l in r.context['lignes']), ['PV-A', 'PV-B'])
        self.assertContains(r, 'article(s) saisis')
        self.assertEqual(r.context['nb_saisis'], 2)
        self.assertEqual(r.context['nb_non_saisis'], 1)
        self.assertEqual(r.context['nb_articles'], 3)

    def test_imprimer_depot(self):
        inventaire_depot = Inventaire.objects.create(
            boutique=self.depot, reference='INV-PV-DEP-002',
            date_inventaire=date.today(), statut='REGULARISE',
            cree_par=self.user_commercant,
        )
        article = Article.objects.create(
            boutique=self.depot, code='PV-D2', nom='Bidon',
            prix_achat=Decimal('10'), prix_vente=Decimal('25'), quantite_stock=6,
        )
        LigneInventaire.objects.create(
            inventaire=inventaire_depot, article=article,
            stock_theorique=4, stock_physique=6, prix_unitaire=Decimal('10'),
        )
        inventaire_depot.calculer_statistiques()

        r = self.client.get(reverse(
            'inventory:imprimer_inventaire',
            args=[self.depot.id, inventaire_depot.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Dépôt « PV Dépôt »')
        self.assertEqual(r.context['valeur_stock_vente'], Decimal('150'))
        self.assertEqual(r.context['valeur_ecart_positif_vente'], Decimal('50'))

    def test_imprimer_anonyme_redirige_vers_login(self):
        self.client.logout()
        r = self.client.get(reverse(
            'inventory:imprimer_inventaire_boutique',
            args=[self.boutique.id, self.inventaire.id]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r['Location'])

    def test_imprimer_non_bloque_par_cloture_de_journee(self):
        """Lecture seule : la clôture de journée ne doit pas bloquer l'impression."""
        ClotureJournee.objects.create(
            boutique=self.boutique, date_jour=timezone.localdate(),
            statut=ClotureJournee.STATUT_VALIDEE,
        )
        r = self.client.get(reverse(
            'inventory:imprimer_inventaire_boutique',
            args=[self.boutique.id, self.inventaire.id]))
        self.assertEqual(r.status_code, 200)
