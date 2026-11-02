"""
Unités des articles (Boucherie) dans la saisie d'inventaire
===========================================================
Le stock reste enregistré en unité de base. La saisie accepte une quantité
exprimée dans l'unité choisie (carton, rame, kg…) et l'affichage décompose
le stock comme la page article : « 2 carton · 5 kg ».
"""
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import (
    Article, Boutique, Categorie, Commercant, Conditionnement, Inventaire,
    LigneInventaire,
)

User = get_user_model()


class InventaireUnitesBoucherieBase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='inv_unites_comm', password='x',
            email='inv_unites@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='INV UNITES SARL', nom_responsable='INV UNITES',
            email='inv_unites@test.cd', user=self.user,
        )
        self.boucherie = Boutique.objects.create(
            nom='Boucherie Inventaire', commercant=self.commercant,
            code_boutique='BT-INV-UNIT-001', type_commerce='BOUCHERIE',
        )
        self.article = Article.objects.create(
            boutique=self.boucherie, code='BUF-INV', nom='Boeuf inventaire',
            prix_vente=1000, quantite_stock=65, unite_base='kg',
        )
        self.carton = Conditionnement.objects.create(
            article=self.article, libelle='carton', coefficient=30, ordre=0,
        )
        self.rame = Conditionnement.objects.create(
            article=self.article, libelle='rame', coefficient=10, ordre=1,
        )
        self.kg = Conditionnement.objects.create(
            article=self.article, libelle='kg', coefficient=1, ordre=2,
        )

        self.inventaire = Inventaire.objects.create(
            boutique=self.boucherie, reference='INV-UNIT-001',
            date_inventaire=date.today(), statut='EN_COURS',
            cree_par=self.user,
        )
        self.ligne = LigneInventaire.objects.create(
            inventaire=self.inventaire, article=self.article,
            stock_theorique=65, prix_unitaire=500,
        )

        self.client.force_login(self.user)
        self.url_page = reverse(
            'inventory:saisir_inventaire_boutique',
            args=[self.boucherie.id, self.inventaire.id],
        )
        self.url_ajax = reverse(
            'inventory:saisir_ligne_inventaire_ajax',
            args=[self.boucherie.id, self.inventaire.id],
        )
        self.url_recherche = reverse(
            'inventory:lignes_recherche_inventaire_ajax',
            args=[self.boucherie.id, self.inventaire.id],
        )


class DecompositionQuantiteTest(InventaireUnitesBoucherieBase):

    def test_decompose_quantite_arbitraire(self):
        self.assertEqual(
            self.article.decomposer_quantite(65),
            [('carton', 2), ('kg', 5)],
        )
        self.assertEqual(
            self.article.decomposer_quantite_formate(65),
            '2 carton · 5 kg',
        )

    def test_decompose_quantite_zero_et_negative(self):
        self.assertEqual(self.article.decomposer_quantite_formate(0), '0 kg')
        self.assertEqual(self.article.decomposer_quantite_formate(-5), '-5 kg')

    def test_stock_decompose_utilise_la_meme_regle(self):
        self.assertEqual(self.article.stock_decompose_formate, '2 carton · 5 kg')

    def test_ligne_inventaire_decompose_snapshot(self):
        self.assertEqual(self.ligne.stock_theorique_decompose, '2 carton · 5 kg')
        self.assertEqual(self.ligne.stock_physique_decompose, '')

        self.ligne.stock_physique = 45
        self.ligne.save()
        self.assertEqual(self.ligne.stock_physique_decompose, '1 carton · 1 rame · 5 kg')

    def test_unites_inventaire_ordre_decroissant_et_base_presente(self):
        self.assertEqual(
            [(u['libelle'], u['coefficient']) for u in self.article.unites_inventaire],
            [('carton', 30), ('rame', 10), ('kg', 1)],
        )

    def test_unites_inventaire_ajoute_l_unite_de_base_si_absente(self):
        self.kg.delete()
        self.assertIn(
            {'coefficient': 1, 'libelle': 'kg'},
            self.article.unites_inventaire,
        )


class RechercheLignesUnitesTest(InventaireUnitesBoucherieBase):

    def test_json_recherche_expose_decompositions_et_unites(self):
        r = self.client.get(self.url_recherche, {'q': 'Boeuf'})
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['results']), 1)
        ligne = data['results'][0]
        self.assertTrue(ligne['est_boucherie'])
        self.assertEqual(ligne['stock_theorique_decompose'], '2 carton · 5 kg')
        self.assertEqual(ligne['stock_physique_decompose'], '')
        self.assertEqual(
            [u['libelle'] for u in ligne['unites']],
            ['carton', 'rame', 'kg'],
        )


class SaisieRapideUnitesTest(InventaireUnitesBoucherieBase):

    def _post_ajax(self, body):
        body.setdefault('ligne_id', self.ligne.id)
        return self.client.post(
            self.url_ajax, data=json.dumps(body), content_type='application/json',
        )

    def test_saisie_en_carton_convertie_en_unite_de_base(self):
        r = self._post_ajax({'stock_physique': 2, 'unite_coefficient': 30})
        data = r.json()
        self.assertTrue(data['success'], data)
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.stock_physique, 60)
        self.assertEqual(self.ligne.ecart, -5)
        self.assertEqual(data['stock_physique_decompose'], '2 carton')
        self.assertEqual(data['stock_theorique_decompose'], '2 carton · 5 kg')

    def test_correction_en_rame_remplace_en_unite_de_base(self):
        self.ligne.stock_physique = 10
        self.ligne.save()

        r = self._post_ajax({
            'stock_physique': 3,
            'unite_coefficient': 10,
            'remplacer': True,
        })
        self.assertTrue(r.json()['success'])
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.stock_physique, 30)

    def test_coefficient_inconnu_ignore(self):
        r = self._post_ajax({'stock_physique': 2, 'unite_coefficient': 999})
        self.assertTrue(r.json()['success'])
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.stock_physique, 2)

    def test_meme_saisie_hors_boucherie_non_multipliee(self):
        general = Boutique.objects.create(
            nom='General Inventaire', commercant=self.commercant,
            code_boutique='BT-INV-UNIT-002', type_commerce='GENERAL',
        )
        article = Article.objects.create(
            boutique=general, code='SAV-INV', nom='Savon inventaire',
            prix_vente=500, quantite_stock=20, unite_base='pcs',
        )
        inventaire = Inventaire.objects.create(
            boutique=general, reference='INV-UNIT-002',
            date_inventaire=date.today(), statut='EN_COURS', cree_par=self.user,
        )
        ligne = LigneInventaire.objects.create(
            inventaire=inventaire, article=article,
            stock_theorique=20, prix_unitaire=100,
        )
        url = reverse(
            'inventory:saisir_ligne_inventaire_ajax',
            args=[general.id, inventaire.id],
        )
        r = self.client.post(
            url,
            data=json.dumps({
                'ligne_id': ligne.id,
                'stock_physique': 2,
                'unite_coefficient': 30,
            }),
            content_type='application/json',
        )
        self.assertTrue(r.json()['success'])
        ligne.refresh_from_db()
        self.assertEqual(ligne.stock_physique, 2)
        self.assertEqual(ligne.stock_physique_decompose, '2 pcs')


class FormulaireTableauUnitesTest(InventaireUnitesBoucherieBase):

    def test_post_tableau_convertit_carton_en_unite_de_base(self):
        r = self.client.post(self.url_page, {
            'stock_physique_' + str(self.ligne.id): '2',
            'unite_coefficient_' + str(self.ligne.id): '30',
            'continuer': '1',
        })
        self.assertEqual(r.status_code, 302)
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.stock_physique, 60)

    def test_correction_tableau_convertit_rame_en_unite_de_base(self):
        self.ligne.stock_physique = 60
        self.ligne.save()

        r = self.client.post(self.url_page, {
            'stock_corrige_' + str(self.ligne.id): '3',
            'unite_coefficient_' + str(self.ligne.id): '10',
        })
        self.assertEqual(r.status_code, 302)
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.stock_physique, 30)

    def test_template_boucherie_affiche_decomposition_et_selecteur_unite(self):
        r = self.client.get(self.url_page, {'filtre': 'tous'})
        self.assertEqual(r.status_code, 200)
        contenu = r.content.decode()
        self.assertIn('2 carton · 5 kg', contenu)
        self.assertIn('unite_coefficient_' + str(self.ligne.id), contenu)
        self.assertIn('unite-select', contenu)

    def test_template_hors_boucherie_sans_selecteur_unite(self):
        general = Boutique.objects.create(
            nom='General Affichage', commercant=self.commercant,
            code_boutique='BT-INV-UNIT-003', type_commerce='GENERAL',
        )
        article = Article.objects.create(
            boutique=general, code='SAV-AFF', nom='Savon affichage',
            prix_vente=500, quantite_stock=20, unite_base='pcs',
        )
        inventaire = Inventaire.objects.create(
            boutique=general, reference='INV-UNIT-003',
            date_inventaire=date.today(), statut='EN_COURS', cree_par=self.user,
        )
        ligne = LigneInventaire.objects.create(
            inventaire=inventaire, article=article,
            stock_theorique=20, prix_unitaire=100,
        )
        url = reverse(
            'inventory:saisir_inventaire_boutique',
            args=[general.id, inventaire.id],
        )
        r = self.client.get(url, {'filtre': 'tous'})
        self.assertEqual(r.status_code, 200)
        contenu = r.content.decode()
        self.assertNotIn('unite_coefficient_' + str(ligne.id), contenu)


class EcartDecomposeTest(InventaireUnitesBoucherieBase):
    """Écarts et procès-verbal affichés en carton / rame / kg (Boucherie).

    La décomposition suit les conditionnements de CHAQUE article : elle est
    calculée par ligne (`LigneInventaire.ecart_decompose`), jamais globale.
    """

    def test_ecart_positif_decompose(self):
        self.ligne.stock_physique = 100  # théorique 65 → +35 = 1 carton · 5 kg
        self.ligne.save()
        self.ligne.refresh_from_db()
        self.assertTrue(self.ligne.affiche_unites)
        self.assertEqual(self.ligne.ecart, 35)
        self.assertEqual(self.ligne.ecart_decompose, '+1 carton · 5 kg')

    def test_ecart_negatif_decompose_sur_la_valeur_absolue(self):
        self.ligne.stock_physique = 30  # théorique 65 → -35 = manque 1 carton · 5 kg
        self.ligne.save()
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.ecart, -35)
        # Jamais de « + » à l'intérieur d'un manque
        self.assertEqual(self.ligne.ecart_decompose, '-1 carton · 5 kg')

    def test_ecart_nul_et_non_saisi(self):
        self.assertEqual(self.ligne.ecart_decompose, '0')
        self.ligne.stock_physique = 65
        self.ligne.save()
        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.ecart_decompose, '0')

    def test_ecart_hors_boucherie_inchange(self):
        general = Boutique.objects.create(
            nom='General Ecart', commercant=self.commercant,
            code_boutique='BT-INV-UNIT-004', type_commerce='GENERAL',
        )
        article = Article.objects.create(
            boutique=general, code='SAV-ECART', nom='Savon écart',
            prix_vente=500, quantite_stock=20, unite_base='pcs',
        )
        inventaire = Inventaire.objects.create(
            boutique=general, reference='INV-UNIT-004',
            date_inventaire=date.today(), statut='EN_COURS', cree_par=self.user,
        )
        ligne = LigneInventaire.objects.create(
            inventaire=inventaire, article=article,
            stock_theorique=20, prix_unitaire=100, stock_physique=17,
        )
        self.assertFalse(ligne.affiche_unites)
        self.assertEqual(ligne.ecart, -3)
        self.assertEqual(ligne.ecart_decompose, '-3')

    def test_saisie_ajax_expose_ecart_decompose(self):
        r = self.client.post(
            self.url_ajax,
            data=json.dumps({
                'ligne_id': self.ligne.id,
                'stock_physique': 2,
                'unite_coefficient': 30,
            }),
            content_type='application/json',
        )
        data = r.json()
        self.assertTrue(data['success'], data)
        self.assertEqual(data['ecart'], -5)
        self.assertEqual(data['ecart_decompose'], '-5 kg')

    def test_recherche_ajax_expose_ecart_decompose(self):
        self.ligne.stock_physique = 100
        self.ligne.save()
        data = self.client.get(self.url_recherche, {'q': 'Boeuf'}).json()
        self.assertEqual(data['results'][0]['ecart_decompose'], '+1 carton · 5 kg')


class RapportEtDetailEcartDecomposeTest(InventaireUnitesBoucherieBase):
    """Procès-verbal, détail et régularisation affichent l'écart décomposé."""

    def _url(self, nom, statut=None):
        if statut:
            self.inventaire.statut = statut
            self.inventaire.save()
        return reverse(
            'inventory:' + nom,
            args=[self.boucherie.id, self.inventaire.id],
        )

    def test_proces_verbal_affiche_ecart_decompose(self):
        self.ligne.stock_physique = 100  # +35
        self.ligne.save()

        r = self.client.get(self._url('imprimer_inventaire_boutique'))
        self.assertEqual(r.status_code, 200)
        contenu = r.content.decode()
        self.assertIn('+1 carton · 5 kg', contenu)
        self.assertIn('2 carton · 5 kg', contenu)   # théorique décomposé
        self.assertIn('3 carton · 1 rame', contenu)  # compté (100)
        self.assertTrue(r.context['est_boucherie'])

    def test_proces_verbal_hors_boucherie_en_nombre_brut(self):
        general = Boutique.objects.create(
            nom='General PV', commercant=self.commercant,
            code_boutique='BT-INV-UNIT-005', type_commerce='GENERAL',
        )
        article = Article.objects.create(
            boutique=general, code='SAV-PV', nom='Savon PV',
            prix_vente=500, quantite_stock=20, unite_base='pcs',
        )
        inventaire = Inventaire.objects.create(
            boutique=general, reference='INV-UNIT-005',
            date_inventaire=date.today(), statut='EN_COURS', cree_par=self.user,
        )
        LigneInventaire.objects.create(
            inventaire=inventaire, article=article,
            stock_theorique=20, prix_unitaire=100, stock_physique=17,
        )
        r = self.client.get(reverse(
            'inventory:imprimer_inventaire_boutique',
            args=[general.id, inventaire.id],
        ))
        self.assertEqual(r.status_code, 200)
        contenu = r.content.decode()
        self.assertFalse(r.context['est_boucherie'])
        self.assertIn('-3', contenu)
        self.assertNotIn('carton', contenu)

    def test_detail_affiche_ecarts_decomploses(self):
        self.ligne.stock_physique = 100  # +35
        self.ligne.save()

        r = self.client.get(self._url('detail_inventaire_boutique'))
        self.assertEqual(r.status_code, 200)
        contenu = r.content.decode()
        self.assertIn('+1 carton · 5 kg', contenu)   # écart positif
        self.assertIn('2 carton · 5 kg', contenu)    # théorique décomposé

    def test_regularisation_affiche_ecarts_decomploses(self):
        self.ligne.stock_physique = 30  # -35
        self.ligne.save()

        r = self.client.get(
            self._url('regulariser_inventaire_boutique', statut='TERMINE'))
        self.assertEqual(r.status_code, 200)
        contenu = r.content.decode()
        self.assertIn('-1 carton · 5 kg', contenu)
        self.assertNotIn('>-35<', contenu)

    def test_tableau_de_bord_affiche_stock_non_saisi_decompose(self):
        r = self.client.get(self._url('tableau_bord_inventaire'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('2 carton · 5 kg', r.content.decode())
