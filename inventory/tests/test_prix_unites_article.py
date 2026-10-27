"""
Prix des unités (Boucherie) dans le modal « Modifier Prix » du back office
==========================================================================
Le bouton Action → Prix ne modifiait que Article.prix_vente : les prix des
unités (demi, carton, rame, kg…) ne sont éditables que par le formulaire
d'édition complet. Ici :

- le modal affiche les unités de l'article (boutique BOUCHERIE uniquement)
- le POST modifier_prix_article accepte cond_prix_<id> par conditionnement
  (vide = repasser en prix auto = prix de base × coefficient)
- prix négatif refusé, conditionnement d'un autre article ignoré
"""
from datetime import date
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import (
    Article, Boutique, Categorie, Commercant, Conditionnement, Inventaire,
    LigneInventaire,
)

User = get_user_model()


class PrixUnitesBoucherieBase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='prix_unite_comm', password='x', email='prix_unite@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='PRIX UNITE SARL', nom_responsable='PRIX UNITE',
            email='prix_unite@test.cd', user=self.user,
        )
        self.boucherie = Boutique.objects.create(
            nom='Boucherie Test', commercant=self.commercant,
            code_boutique='BT-BCH-001', type_commerce='BOUCHERIE',
        )
        self.categorie = Categorie.objects.create(
            nom='Viandes', boutique=self.boucherie,
        )
        self.article = Article.objects.create(
            boutique=self.boucherie, code='BCH-VI', nom='Boeuf',
            prix_vente=5000, quantite_stock=100, categorie=self.categorie,
            unite_base='g',
        )
        self.kg = Conditionnement.objects.create(
            article=self.article, libelle='kg', coefficient=1000,
        )
        self.carton = Conditionnement.objects.create(
            article=self.article, libelle='carton', coefficient=10000,
            prix_vente=60000,
        )
        self.rame = Conditionnement.objects.create(
            article=self.article, libelle='rame', coefficient=500,
        )

        self.autre_article = Article.objects.create(
            boutique=self.boucherie, code='BCH-AG', nom='Agneau',
            prix_vente=6000, quantite_stock=50, categorie=self.categorie,
            unite_base='g',
        )
        self.autre_cond = Conditionnement.objects.create(
            article=self.autre_article, libelle='kg', coefficient=1000,
            prix_vente=7000,
        )

        self.client.force_login(self.user)
        self.url = reverse(
            'inventory:modifier_prix_article',
            args=[self.boucherie.id, self.article.id],
        )

    def _post(self, body):
        body.setdefault('prix_vente', '5500')
        return self.client.post(
            self.url, body, HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )


class PrixUnitesPOSTTest(PrixUnitesBoucherieBase):

    def test_modifie_prix_de_base_et_prix_des_unites(self):
        r = self._post({
            'prix_vente': '5500',
            'cond_prix_' + str(self.carton.id): '70000',
            'cond_prix_' + str(self.rame.id): '3000',
            'cond_prix_' + str(self.kg.id): '',
        })
        data = r.json()
        self.assertTrue(data['success'], data)
        self.assertEqual(data['unites_modifiees'], 2)

        self.article.refresh_from_db()
        self.assertEqual(self.article.prix_vente, 5500)
        self.carton.refresh_from_db()
        self.assertEqual(self.carton.prix_vente, 70000)
        self.rame.refresh_from_db()
        self.assertEqual(self.rame.prix_vente, 3000)
        # champ vidé → prix auto (5500 × 1000)
        self.kg.refresh_from_db()
        self.assertIsNone(self.kg.prix_vente)
        self.assertEqual(self.kg.prix_vente_effectif, 5500 * 1000)

    def test_aucun_prix_unite_saisi_ne_change_rien(self):
        r = self._post({'prix_vente': '5500'})
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['unites_modifiees'], 0)
        self.carton.refresh_from_db()
        self.assertEqual(self.carton.prix_vente, 60000)

    def test_prix_unite_identique_compte_comme_inchange(self):
        r = self._post({
            'prix_vente': '5500',
            'cond_prix_' + str(self.carton.id): '60000',
        })
        self.assertEqual(r.json()['unites_modifiees'], 0)

    def test_prix_unite_negatif_refuse_et_rien_n_est_enregistre(self):
        r = self._post({
            'prix_vente': '5500',
            'cond_prix_' + str(self.carton.id): '-100',
        })
        data = r.json()
        self.assertFalse(data['success'])
        self.assertIn('carton', data['message'])
        self.article.refresh_from_db()
        self.assertEqual(self.article.prix_vente, 5000)
        self.carton.refresh_from_db()
        self.assertEqual(self.carton.prix_vente, 60000)

    def test_conditionnement_d_un_autre_article_est_ignore(self):
        r = self._post({
            'prix_vente': '5500',
            'cond_prix_' + str(self.autre_cond.id): '99999',
        })
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['unites_modifiees'], 0)
        self.autre_cond.refresh_from_db()
        self.assertEqual(self.autre_cond.prix_vente, 7000)

    def test_sans_conditionnement_fonctionne_comme_avant(self):
        boutique = Boutique.objects.create(
            nom='Commerce Général', commercant=self.commercant,
            code_boutique='BT-GEN-001', type_commerce='GENERAL',
        )
        article = Article.objects.create(
            boutique=boutique, code='GEN-01', nom='Savon',
            prix_vente=1000, quantite_stock=10,
        )
        url = reverse(
            'inventory:modifier_prix_article', args=[boutique.id, article.id],
        )
        r = self.client.post(
            url, {'prix_vente': '1200', 'cond_prix_1': '5000'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['unites_modifiees'], 0)
        article.refresh_from_db()
        self.assertEqual(article.prix_vente, 1200)


class PrixUnitesAffichageTest(PrixUnitesBoucherieBase):

    def test_modal_prix_affiche_les_unites_boucherie(self):
        r = self.client.get(
            reverse('inventory:commercant_articles_boutique', args=[self.boucherie.id]),
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="prixUnitesContainer"')
        self.assertContains(r, 'Prix des unités')
        # le modal ne rend pas les inputs côté serveur (construits en JS)
        self.assertNotContains(r, 'name="cond_prix_' + str(self.carton.id) + '"')
        # le bouton Prix porte les unités de l'article
        self.assertContains(r, f'{self.carton.id}:carton:10000:60000.00')
        self.assertContains(r, f'{self.rame.id}:rame:500:')

    def test_pas_de_bloc_unites_hors_boucherie(self):
        boutique = Boutique.objects.create(
            nom='Quincaillerie', commercant=self.commercant,
            code_boutique='BT-QIN-001', type_commerce='QUINCAILLERIE',
        )
        Article.objects.create(
            boutique=boutique, code='QIN-01', nom='Marteau',
            prix_vente=2500, quantite_stock=5,
        )
        r = self.client.get(
            reverse('inventory:commercant_articles_boutique', args=[boutique.id]),
        )
        self.assertEqual(r.status_code, 200)
        # le bloc n'existe que pour les boutiques de type Boucherie
        self.assertNotContains(r, 'id="prixUnitesContainer"')
        self.assertNotContains(r, 'data-prix-unites')


class PrixUnitesRechercheAjaxTest(PrixUnitesBoucherieBase):
    """La recherche AJAX doit fournir les unités aux boutons Prix des
    lignes filtrées et du dropdown de recherche rapide."""

    def _search(self, q='Boeuf'):
        r = self.client.get(
            reverse('inventory:articles_search_ajax', args=[self.boucherie.id]),
            {'q': q},
        )
        self.assertEqual(r.status_code, 200)
        return r.json()['articles']

    def test_recherche_retourne_prix_unites_au_format_complet(self):
        articles = self._search()
        self.assertEqual(len(articles), 1)
        data = articles[0]
        self.assertEqual(
            data['prix_unites'],
            f'{self.kg.id}:kg:1000:|'
            f'{self.carton.id}:carton:10000:60000.00|'
            f'{self.rame.id}:rame:500:',
        )
        # le format stock (libelle:coefficient) reste inchangé
        self.assertEqual(data['conditionnements'], 'kg:1000|carton:10000|rame:500')

    def test_recherche_hors_boucherie_sans_prix_unites(self):
        boutique = Boutique.objects.create(
            nom='Quincaillerie', commercant=self.commercant,
            code_boutique='BT-QIN-002', type_commerce='QUINCAILLERIE',
        )
        Article.objects.create(
            boutique=boutique, code='QIN-02', nom='Marteau',
            prix_vente=2500, quantite_stock=5,
        )
        r = self.client.get(
            reverse('inventory:articles_search_ajax', args=[boutique.id]),
            {'q': 'Marteau'},
        )
        self.assertEqual(r.json()['articles'][0]['prix_unites'], '')


class PrixUnitesScannerGlobalTest(PrixUnitesBoucherieBase):
    """Le scanner global (présent sur tous les écrans) doit aussi permettre de
    modifier les prix des unités d'un article de Boucherie."""

    def test_verification_renvoie_les_unites_boucherie(self):
        r = self.client.get(
            reverse('inventory:verifier_code_barre_global'),
            {'code': 'BCH-VI', 'boutique_id': self.boucherie.id},
        )
        data = r.json()
        self.assertTrue(data['existe'], data)
        unites = data['article']['unites']
        self.assertEqual(
            [(u['id'], u['libelle'], u['coefficient'], u['prix']) for u in unites],
            [
                (self.kg.id, 'kg', 1000, None),
                (self.carton.id, 'carton', 10000, 60000.0),
                (self.rame.id, 'rame', 500, None),
            ],
        )

    def test_modification_globale_change_prix_des_unites(self):
        r = self.client.post(
            reverse('inventory:modifier_article_global'),
            {
                'article_id': self.article.id,
                'prix_vente': '5500',
                'cond_prix_' + str(self.carton.id): '72000',
                'cond_prix_' + str(self.kg.id): '',
            },
        )
        data = r.json()
        self.assertTrue(data['success'], data)
        self.article.refresh_from_db()
        self.assertEqual(self.article.prix_vente, 5500)
        self.carton.refresh_from_db()
        self.assertEqual(self.carton.prix_vente, 72000)
        self.kg.refresh_from_db()
        self.assertIsNone(self.kg.prix_vente)

    def test_modification_globale_refuse_prix_unite_negatif(self):
        r = self.client.post(
            reverse('inventory:modifier_article_global'),
            {
                'article_id': self.article.id,
                'prix_vente': '5500',
                'cond_prix_' + str(self.carton.id): '-1',
            },
        )
        data = r.json()
        self.assertFalse(data['success'])
        self.assertIn('carton', data['message'])
        self.carton.refresh_from_db()
        self.assertEqual(self.carton.prix_vente, 60000)

    def test_verification_hors_boucherie_sans_unites(self):
        boutique = Boutique.objects.create(
            nom='Quincaillerie', commercant=self.commercant,
            code_boutique='BT-QIN-003', type_commerce='QUINCAILLERIE',
        )
        Article.objects.create(
            boutique=boutique, code='QIN-03', nom='Marteau',
            prix_vente=2500, quantite_stock=5,
        )
        r = self.client.get(
            reverse('inventory:verifier_code_barre_global'),
            {'code': 'QIN-03', 'boutique_id': boutique.id},
        )
        self.assertEqual(r.json()['article']['unites'], [])


class PrixUnitesRechercheCodeBarreTest(PrixUnitesBoucherieBase):
    """Le modal de recherche par code-barres de l'écran Article doit aussi
    afficher et enregistrer les prix des unités."""

    def test_verification_renvoie_les_unites_boucherie(self):
        r = self.client.get(
            reverse('inventory:verifier_code_barre', args=[self.boucherie.id]),
            {'code': 'BCH-VI'},
        )
        data = r.json()
        self.assertTrue(data['existe'], data)
        self.assertEqual(
            [(u['id'], u['libelle'], u['coefficient'], u['prix'])
             for u in data['article']['unites']],
            [
                (self.kg.id, 'kg', 1000, None),
                (self.carton.id, 'carton', 10000, 60000.0),
                (self.rame.id, 'rame', 500, None),
            ],
        )

    def test_modification_enregistre_les_prix_des_unites(self):
        r = self.client.post(
            reverse('inventory:modifier_article_existant', args=[self.boucherie.id]),
            {
                'article_id': self.article.id,
                'prix_vente': '5500',
                'cond_prix_' + str(self.carton.id): '72000',
                'cond_prix_' + str(self.kg.id): '',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        data = r.json()
        self.assertTrue(data['success'], data)
        self.article.refresh_from_db()
        self.assertEqual(self.article.prix_vente, 5500)
        self.carton.refresh_from_db()
        self.assertEqual(self.carton.prix_vente, 72000)
        self.kg.refresh_from_db()
        self.assertIsNone(self.kg.prix_vente)
        self.assertIn('carton', data['message'])

    def test_modification_refuse_prix_unite_negatif(self):
        r = self.client.post(
            reverse('inventory:modifier_article_existant', args=[self.boucherie.id]),
            {
                'article_id': self.article.id,
                'prix_vente': '5500',
                'cond_prix_' + str(self.carton.id): '-5',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        data = r.json()
        self.assertFalse(data['success'])
        self.assertIn('carton', data['message'])
        self.article.refresh_from_db()
        self.assertEqual(self.article.prix_vente, 5000)
        self.carton.refresh_from_db()
        self.assertEqual(self.carton.prix_vente, 60000)

    def test_verification_hors_boucherie_sans_unites(self):
        boutique = Boutique.objects.create(
            nom='Quincaillerie', commercant=self.commercant,
            code_boutique='BT-QIN-004', type_commerce='QUINCAILLERIE',
        )
        Article.objects.create(
            boutique=boutique, code='QIN-04', nom='Marteau',
            prix_vente=2500, quantite_stock=5,
        )
        r = self.client.get(
            reverse('inventory:verifier_code_barre', args=[boutique.id]),
            {'code': 'QIN-04'},
        )
        self.assertEqual(r.json()['article']['unites'], [])


class PrixUnitesInventaireTest(PrixUnitesBoucherieBase):
    """La saisie rapide d'inventaire doit aussi permettre de modifier les prix
    des unités (kg, demi, carton…) de l'article compté."""

    def setUp(self):
        super().setUp()
        self.inventaire = Inventaire.objects.create(
            boutique=self.boucherie, reference='INV-TEST-UNITES',
            date_inventaire=date.today(), cree_par=self.user,
        )
        self.ligne = LigneInventaire.objects.create(
            inventaire=self.inventaire, article=self.article,
            stock_theorique=100, prix_unitaire=0,
        )
        self.autre_ligne = LigneInventaire.objects.create(
            inventaire=self.inventaire, article=self.autre_article,
            stock_theorique=50, prix_unitaire=0,
        )
        self.url_ajax = reverse(
            'inventory:saisir_ligne_inventaire_ajax',
            args=[self.boucherie.id, self.inventaire.id],
        )

    def _post_ajax(self, body):
        body.setdefault('ligne_id', self.ligne.id)
        body.setdefault('stock_physique', 10)
        return self.client.post(
            self.url_ajax, data=json.dumps(body), content_type='application/json',
        )

    def test_recherche_lignes_renvoie_les_unites(self):
        r = self.client.get(
            reverse('inventory:lignes_recherche_inventaire_ajax',
                    args=[self.boucherie.id, self.inventaire.id]),
            {'q': 'Boeuf'},
        )
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(
            [(u['id'], u['libelle'], u['prix']) for u in data['results'][0]['unites']],
            [(self.kg.id, 'kg', None), (self.carton.id, 'carton', 60000.0),
             (self.rame.id, 'rame', None)],
        )

    def test_saisie_rapide_enregistre_les_prix_des_unites(self):
        r = self._post_ajax({
            'prix_vente': 5500,
            'cond_prix': {
                str(self.carton.id): '72000',
                str(self.kg.id): '',
                str(self.autre_cond.id): '99999',
            },
        })
        data = r.json()
        self.assertTrue(data['success'], data)
        self.assertEqual(data['unites_modifiees'], 1)

        self.article.refresh_from_db()
        self.assertEqual(self.article.prix_vente, 5500)
        self.carton.refresh_from_db()
        self.assertEqual(self.carton.prix_vente, 72000)
        self.kg.refresh_from_db()
        self.assertIsNone(self.kg.prix_vente)
        # conditionnement d'un autre article : jamais touché
        self.autre_cond.refresh_from_db()
        self.assertEqual(self.autre_cond.prix_vente, 7000)

    def test_saisie_rapide_refuse_prix_unite_negatif(self):
        r = self._post_ajax({
            'prix_vente': 5500,
            'cond_prix': {str(self.carton.id): '-10'},
        })
        self.assertEqual(r.status_code, 400)
        data = r.json()
        self.assertFalse(data['success'])
        self.assertIn('carton', data['error'])
        self.ligne.refresh_from_db()
        self.assertIsNone(self.ligne.stock_physique)
        self.article.refresh_from_db()
        self.assertEqual(self.article.prix_vente, 5000)
        self.carton.refresh_from_db()
        self.assertEqual(self.carton.prix_vente, 60000)

    def test_saisie_rapide_hors_boucherie_ignore_les_unites(self):
        boutique = Boutique.objects.create(
            nom='Quincaillerie', commercant=self.commercant,
            code_boutique='BT-QIN-005', type_commerce='QUINCAILLERIE',
        )
        article = Article.objects.create(
            boutique=boutique, code='QIN-05', nom='Marteau',
            prix_vente=2500, quantite_stock=5,
        )
        inventaire = Inventaire.objects.create(
            boutique=boutique, reference='INV-TEST-GEN',
            date_inventaire=date.today(), cree_par=self.user,
        )
        ligne = LigneInventaire.objects.create(
            inventaire=inventaire, article=article,
            stock_theorique=5, prix_unitaire=0,
        )
        r = self.client.post(
            reverse('inventory:saisir_ligne_inventaire_ajax',
                    args=[boutique.id, inventaire.id]),
            data=json.dumps({
                'ligne_id': ligne.id, 'stock_physique': 7,
                'cond_prix': {'1': '999'},
            }),
            content_type='application/json',
        )
        data = r.json()
        self.assertTrue(data['success'], data)
        self.assertEqual(data['unites_modifiees'], 0)
        self.assertEqual(data['unites'], [])
