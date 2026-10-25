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

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import (
    Article, Boutique, Categorie, Commercant, Conditionnement, Inventaire,
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
        self.assertNotContains(r, 'Prix des unités')


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
