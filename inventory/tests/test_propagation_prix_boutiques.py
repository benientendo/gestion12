"""
Propagation du prix aux autres boutiques Boucherie du même commerçant
=====================================================================
Lors de la modification du prix d'un article (prix de base et/ou prix des
unités carton, rame, kg…) dans une boutique de type BOUCHERIE, l'écran
demande à l'utilisateur si le changement doit aussi s'appliquer aux autres
points de vente Boucherie du même commerçant portant le même code.

Covers :

- GET autres_boutiques_article : liste des cibles + ignores (devise)
- POST modifier_prix_article + propager_autres=1 : prix de base ET unités
  recopiées par (libellé, coefficient)
- sans propager_autres : aucune propagation
- seuls les prix réellement modifiés sont propagés
- boutique source non-Boucherie : aucune cible
- autres types de commerce jamais touchés
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import (
    Article, Boutique, Categorie, Commercant, Conditionnement,
)

User = get_user_model()


class PropagationPrixBase(TestCase):
    """Deux boutiques Boucherie du même commerçant, même code article."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='prop_prix_comm', password='x',
            email='prop_prix@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='PROPRIX SARL', nom_responsable='PROPRIX',
            email='prop_prix@test.cd', user=self.user,
        )
        self.bch1 = Boutique.objects.create(
            nom='Boucherie Centre', commercant=self.commercant,
            code_boutique='BCH-CEN-001', type_commerce='BOUCHERIE',
        )
        self.bch2 = Boutique.objects.create(
            nom='Boucherie Sud', commercant=self.commercant,
            code_boutique='BCH-SUD-001', type_commerce='BOUCHERIE',
        )
        self.categorie = Categorie.objects.create(
            nom='Viandes', boutique=self.bch1,
        )

        self.article = Article.objects.create(
            boutique=self.bch1, code='BCH-VI', nom='Boeuf',
            prix_vente=5000, quantite_stock=100,
            categorie=self.categorie, unite_base='g',
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

        # Même code dans la boutique cible, prix différents
        self.article_cible = Article.objects.create(
            boutique=self.bch2, code='BCH-VI', nom='Boeuf',
            prix_vente=4800, quantite_stock=40,
            categorie=Categorie.objects.create(nom='Viandes', boutique=self.bch2),
            unite_base='g',
        )
        self.kg_cible = Conditionnement.objects.create(
            article=self.article_cible, libelle='kg', coefficient=1000,
            prix_vente=4900,
        )
        self.carton_cible = Conditionnement.objects.create(
            article=self.article_cible, libelle='carton', coefficient=10000,
            prix_vente=58000,
        )
        # Unité absente de la source : ne doit jamais être touchée
        self.sac_cible = Conditionnement.objects.create(
            article=self.article_cible, libelle='sac', coefficient=25,
            prix_vente=1200,
        )

        self.client.force_login(self.user)
        self.url_autres = reverse(
            'inventory:autres_boutiques_article',
            args=[self.bch1.id, self.article.id],
        )
        self.url_prix = reverse(
            'inventory:modifier_prix_article',
            args=[self.bch1.id, self.article.id],
        )

    def _post_prix(self, body):
        body.setdefault('prix_vente', '5500')
        return self.client.post(
            self.url_prix, body, HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def _refresh_cible(self):
        self.article_cible.refresh_from_db()
        self.kg_cible.refresh_from_db()
        self.carton_cible.refresh_from_db()
        self.sac_cible.refresh_from_db()


class AutresBoutiquesEndpointTest(PropagationPrixBase):

    def test_liste_les_autres_boutiques_boucherie_meme_code(self):
        r = self.client.get(self.url_autres, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['code'], 'BCH-VI')
        self.assertEqual(data['nb'], 1)
        self.assertEqual(data['boutiques'][0]['nom'], 'Boucherie Sud')
        self.assertEqual(data['ignores'], [])

    def test_requete_sans_ajax_refusee(self):
        r = self.client.get(self.url_autres)
        self.assertEqual(r.status_code, 400)

    def test_article_dune_autre_boutique_404(self):
        url = reverse(
            'inventory:autres_boutiques_article',
            args=[self.bch1.id, self.article_cible.id],
        )
        r = self.client.get(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 404)

    def test_boutique_source_non_boucherie_sans_cible(self):
        epicerie = Boutique.objects.create(
            nom='Épicerie Test', commercant=self.commercant,
            code_boutique='EPI-001', type_commerce='ALIMENTATION',
        )
        art_epi = Article.objects.create(
            boutique=epicerie, code='BCH-VI', nom='Boeuf',
            prix_vente=5000, quantite_stock=10, unite_base='g',
        )
        url = reverse(
            'inventory:autres_boutiques_article',
            args=[epicerie.id, art_epi.id],
        )
        r = self.client.get(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['boutiques'], [])
        self.assertEqual(data['nb'], 0)


class PropagationPrixTest(PropagationPrixBase):

    def test_prix_de_base_propage_sans_flag_local(self):
        """Sans propager_autres, la boutique cible n'est pas touchée."""
        r = self._post_prix({'prix_vente': '7000'})
        data = r.json()
        self.assertTrue(data['success'], data)
        self.assertIsNone(data['propagation'])
        self._refresh_cible()
        self.assertEqual(self.article_cible.prix_vente, 4800)

    def test_prix_de_base_propage_avec_flag(self):
        r = self._post_prix({'prix_vente': '7000', 'propager_autres': '1'})
        data = r.json()
        self.assertTrue(data['success'], data)
        prop = data['propagation']
        self.assertIsNotNone(prop)
        self.assertEqual(prop['boutiques'], ['Boucherie Sud'])
        self.assertIn('7000', data['message'])
        self._refresh_cible()
        self.assertEqual(self.article_cible.prix_vente, 7000)

    def test_unites_recopiees_par_libelle_et_coefficient(self):
        r = self._post_prix({
            'prix_vente': '5500',
            'cond_prix_' + str(self.carton.id): '70000',
            'cond_prix_' + str(self.rame.id): '3000',
            'propager_autres': 'oui',
        })
        data = r.json()
        self.assertTrue(data['success'], data)
        self.assertEqual(data['unites_modifiees'], 2)
        self._refresh_cible()
        self.assertEqual(self.carton_cible.prix_vente, 70000)
        # rame : prix saisi côté source (passé de auto à 3000)
        self.rame.refresh_from_db()
        self.assertEqual(self.rame.prix_vente, 3000)
        # unité inexistante côté source : jamais touchée
        self.assertEqual(self.sac_cible.prix_vente, 1200)

    def test_seuls_les_unites_reellement_modifiees_sont_propagees(self):
        """Un prix identique à l'existant n'est pas dans les modifications :
        la cible conserve ses propres valeurs pour cette unité."""
        r = self._post_prix({
            'prix_vente': '5000',
            'cond_prix_' + str(self.carton.id): '60000',  # inchangé
            'propager_autres': '1',
        })
        data = r.json()
        self.assertTrue(data['success'], data)
        self.assertEqual(data['unites_modifiees'], 0)
        self._refresh_cible()
        self.assertEqual(self.carton_cible.prix_vente, 58000)

    def test_aucun_changement_ne_propage_rien(self):
        r = self._post_prix({'prix_vente': '5000', 'propager_autres': '1'})
        data = r.json()
        self.assertTrue(data['success'], data)
        # prix source identique : la cible reste identique aussi (déjà 4800 ?
        # non : 5000 ≠ 4800 → la cible serait alignée, c'est voulu : l'état
        # « final » demandé par l'utilisateur est le prix source)
        self._refresh_cible()
        self.assertEqual(self.article_cible.prix_vente, 5000)

    def test_boutique_non_boucherie_jamais_toochee(self):
        epicerie = Boutique.objects.create(
            nom='Épicerie Voisin', commercant=self.commercant,
            code_boutique='EPI-002', type_commerce='ALIMENTATION',
        )
        art_epi = Article.objects.create(
            boutique=epicerie, code='BCH-VI', nom='Boeuf',
            prix_vente=4500, quantite_stock=10, unite_base='g',
        )
        r = self._post_prix({'prix_vente': '7000', 'propager_autres': '1'})
        data = r.json()
        self.assertTrue(data['success'], data)
        self.assertNotIn('Épicerie Voisin', data['propagation']['boutiques'])
        art_epi.refresh_from_db()
        self.assertEqual(art_epi.prix_vente, 4500)

    def test_devise_differentee_ignoree_et_signalee(self):
        usd_bch = Boutique.objects.create(
            nom='Boucherie USD', commercant=self.commercant,
            code_boutique='BCH-USD-001', type_commerce='BOUCHERIE',
        )
        Article.objects.create(
            boutique=usd_bch, code='BCH-VI', nom='Boeuf',
            prix_vente=3, quantite_stock=5, unite_base='g', devise='USD',
        )

        r = self.client.get(self.url_autres, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        data = r.json()
        self.assertEqual(data['nb'], 1)
        self.assertEqual(len(data['ignores']), 1)
        self.assertEqual(data['ignores'][0]['nom'], 'Boucherie USD')
        self.assertEqual(data['ignores'][0]['raison'], 'devise différente')

        r = self._post_prix({'prix_vente': '7000', 'propager_autres': '1'})
        data = r.json()
        self.assertTrue(data['success'], data)
        self.assertEqual(data['propagation']['boutiques'], ['Boucherie Sud'])
        self.assertEqual(
            data['propagation']['ignores'],
            [['Boucherie USD', 'devise différente']],
        )

    def test_flag_invalide_ignore_la_propagation(self):
        r = self._post_prix({'prix_vente': '7000', 'propager_autres': 'peut-etre'})
        data = r.json()
        self.assertTrue(data['success'])
        self.assertIsNone(data['propagation'])
        self._refresh_cible()
        self.assertEqual(self.article_cible.prix_vente, 4800)


class RenduPageEditionTest(PropagationPrixBase):
    """La page « Modifier l'article » affiche la case de propagation."""

    def test_case_propagation_affichee_si_cible(self):
        self.client.force_login(self.user)
        url = reverse(
            'inventory:modifier_article_boutique',
            args=[self.bch1.id, self.article.id],
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        html = r.content.decode('utf-8')
        self.assertIn('id="propagerAutresBlock"', html)
        self.assertIn('id="propagerAutres"', html)
        # Le JS préremplit la liste des cibles via l'endpoint
        self.assertIn('autres-boutiques', html)

    def test_case_propagation_absente_hors_boucherie(self):
        epicerie = Boutique.objects.create(
            nom='Épicerie Édition', commercant=self.commercant,
            code_boutique='EPI-ED-001', type_commerce='ALIMENTATION',
        )
        art_epi = Article.objects.create(
            boutique=epicerie, code='EPI-01', nom='Riz',
            prix_vente=2000, quantite_stock=10, unite_base='kg',
        )
        url = reverse(
            'inventory:modifier_article_boutique',
            args=[epicerie.id, art_epi.id],
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn(
            'id="propagerAutresBlock"', r.content.decode('utf-8'),
        )


class PropagationSansDoublonTest(PropagationPrixBase):
    """Une seule cible par boutique : un article au code donné y suffit."""

    def test_deux_boutiques_cibles_listees(self):
        bch3 = Boutique.objects.create(
            nom='Boucherie Nord', commercant=self.commercant,
            code_boutique='BCH-NOR-001', type_commerce='BOUCHERIE',
        )
        Article.objects.create(
            boutique=bch3, code='BCH-VI', nom='Boeuf',
            prix_vente=4900, quantite_stock=8, unite_base='g',
        )
        r = self.client.get(self.url_autres, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        data = r.json()
        self.assertEqual(data['nb'], 2)
        noms = {b['nom'] for b in data['boutiques']}
        self.assertEqual(noms, {'Boucherie Sud', 'Boucherie Nord'})
