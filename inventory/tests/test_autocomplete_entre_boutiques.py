"""
Article créé pendant un inventaire → retrouvé auto dans le dépôt / facture fournisseur
=====================================================================================
À la saisie du nom d'article (autocomplétion de la page « Facture fournisseur »,
dépôt comme boutique), les articles des AUTRES points de vente du même commerçant
doivent être proposés : le nom est reconnu, prix/catégorie pré-remplis.

Règles vérifiées :
- l'article d'un autre point de vente est marqué `local: false` dans le JSON ;
- un doublon de nom est résolu en faveur de l'article de la boutique en cours ;
- l'id étranger n'est JAMAIS envoyé à l'enregistrement (sinon DoesNotExist) :
  l'article est alors créé dans la boutique en cours, avec le même code ;
- si ce code y existe déjà, l'article existant est réutilisé (pas d'IntegrityError) ;
- un `article_id` étranger reçu par erreur n'explose pas la requête (message d'erreur).
"""
import json

from django.contrib.messages import get_messages
from django.urls import reverse

from inventory.models import Article, Boutique
from inventory.tests.test_ajout_article_inventaire import AjoutArticleInventaireBase


class AutocompleteEntreBoutiquesBase(AjoutArticleInventaireBase):

    def setUp(self):
        super().setUp()
        self.depot = Boutique.objects.create(
            nom='INV DEPOT', commercant=self.commercant, code_boutique='BT-INV-DEP',
            est_depot=True,
        )
        self.article_depot = Article.objects.create(
            boutique=self.depot, code='DEP-ART-1', nom='Riz 25kg',
            prix_vente=30000, quantite_stock=8,
        )
        self.article_autre = Article.objects.create(
            boutique=self.boutique, code='BT-ART-COPIE', nom='Sucre en poudre',
            prix_vente=2500, prix_achat=1200, quantite_stock=6,
        )
        self.url_depot = reverse('inventory:approvisionner_facture', args=[self.depot.id])
        self.url_boutique = reverse(
            'inventory:approvisionner_facture_boutique', args=[self.boutique.id])

    def _creer_article_inventaire(self, code='INV-NEW-1', nom='Eponge', prix_vente='1500'):
        """Article créé pendant l'inventaire en cours (via la vue AJAX)."""
        url = reverse('inventory:ajouter_article_inventaire_ajax',
                      args=[self.boutique.id, self.inventaire.id])
        r = self.client.post(url, json.dumps({
            'code': code, 'nom': nom, 'prix_vente': prix_vente,
            'categorie_id': self.categorie.id, 'quantite': 5,
        }), content_type='application/json')
        self.assertEqual(r.status_code, 200, r.content)
        return Article.objects.get(boutique=self.boutique, code=code)

    @staticmethod
    def _ligne(code, nom, **extra):
        donnees = {
            'article_id': None, 'code': code, 'nom': nom, 'description': '',
            'categorie_id': None, 'categorie_nom': 'Entretien',
            'type_quantite': 'UNITE', 'prix_vente': 1500,
            'nombre_cartons': 0, 'pieces_par_carton': 1, 'pieces_supplementaires': 0,
            'prix_achat_carton': 0, 'prix_achat_unitaire': 700, 'prix_piece_sup': 0,
            'quantite_unites': 4,
        }
        donnees.update(extra)
        return donnees

    def _post_facture(self, url, numero, lignes):
        return self.client.post(url, {
            'numero_facture': numero,
            'fournisseur_nom': 'Fournisseur Test',
            'date_facture': '',
            'devise': 'CDF',
            'notes': '',
            'articles_json': json.dumps(lignes),
        })

    @staticmethod
    def _articles_json(context):
        return json.loads(context['autocomplete_articles_json'])

    def _erreurs(self, reponse):
        return [str(m) for m in get_messages(reponse.wsgi_request)
                if m.level_tag == 'error']


class AutocompleteFactureTest(AutocompleteEntreBoutiquesBase):

    def test_facture_depot_retrouve_l_article_cree_pendant_l_inventaire(self):
        article = self._creer_article_inventaire(nom='Eponge')

        r = self.client.get(self.url_depot)
        self.assertEqual(r.status_code, 200)
        self.assertIn('Eponge', r.context['autocomplete_article_noms'])

        entries = {a['nom']: a for a in self._articles_json(r.context)}
        self.assertFalse(entries['Eponge']['local'])
        self.assertEqual(entries['Eponge']['id'], article.id)
        self.assertTrue(entries['Riz 25kg']['local'])

    def test_facture_boutique_retrouve_l_article_du_depot(self):
        r = self.client.get(self.url_boutique)
        self.assertEqual(r.status_code, 200)
        self.assertIn('Riz 25kg', r.context['autocomplete_article_noms'])

        entries = {a['nom']: a for a in self._articles_json(r.context)}
        self.assertFalse(entries['Riz 25kg']['local'])
        self.assertTrue(entries['Savon']['local'])

    def test_le_nom_est_visible_dans_le_datalist_rendu(self):
        self._creer_article_inventaire(nom='Eponge')
        # Page du dépôt : nom de l'article créé dans la boutique
        self.assertContains(self.client.get(self.url_depot), 'Eponge')
        # Page facture de la boutique : nom de l'article du dépôt
        self.assertContains(self.client.get(self.url_boutique), 'Riz 25kg')

    def test_doublon_de_nom_priorite_a_l_article_local(self):
        Article.objects.create(
            boutique=self.depot, code='DEP-ART-2', nom='Sucre en poudre',
            prix_vente=2700, quantite_stock=3,
        )
        r = self.client.get(self.url_depot)
        entries = [a for a in self._articles_json(r.context) if a['nom'] == 'Sucre en poudre']
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0]['local'])
        self.assertEqual(entries[0]['code'], 'DEP-ART-2')

    def test_articles_legacy_marques_non_locaux(self):
        r = self.client.get(self.url_depot)
        legacy = [a for a in self._articles_json(r.context) if a.get('legacy')]
        for entry in legacy:
            self.assertFalse(entry['local'])


class EnregistrementFactureTest(AutocompleteEntreBoutiquesBase):

    def test_post_depot_cree_une_copie_locale_avec_le_mem_code(self):
        r = self._post_facture(self.url_depot, 'FAC-COPIE-1', [
            self._ligne('BT-ART-COPIE', 'Sucre en poudre'),
        ])
        self.assertEqual(r.status_code, 302)
        self.assertFalse(self._erreurs(r))

        copie = Article.objects.get(boutique=self.depot, code='BT-ART-COPIE')
        self.assertEqual(copie.nom, 'Sucre en poudre')
        self.assertEqual(copie.quantite_stock, 4)

    def test_post_depot_reutilise_une_copie_deja_presente(self):
        Article.objects.create(
            boutique=self.depot, code='BT-ART-COPIE', nom='Sucre en poudre',
            prix_vente=2700, quantite_stock=10,
        )
        r = self._post_facture(self.url_depot, 'FAC-COPIE-2', [
            self._ligne('BT-ART-COPIE', 'Sucre en poudre'),
        ])
        self.assertEqual(r.status_code, 302)

        self.assertEqual(
            Article.objects.filter(boutique=self.depot, code='BT-ART-COPIE').count(), 1)
        copie = Article.objects.get(boutique=self.depot, code='BT-ART-COPIE')
        self.assertEqual(copie.quantite_stock, 14)

    def test_post_depot_article_local_reference_sans_modification(self):
        r = self._post_facture(self.url_depot, 'FAC-LOCALE-1', [
            self._ligne('DEP-ART-1', 'Riz 25kg',
                        article_id=self.article_depot.id, prix_vente=31000),
        ])
        self.assertEqual(r.status_code, 302)
        self.article_depot.refresh_from_db()
        self.assertEqual(self.article_depot.quantite_stock, 12)

    def test_post_avec_id_etranger_n_explose_pas_la_requete(self):
        r = self._post_facture(self.url_depot, 'FAC-ETRANGER-1', [
            self._ligne('BT-ART-COPIE', 'Sucre en poudre',
                        article_id=self.article_autre.id),
        ])
        # Exception attrapée : pas de 500, un message explique le refus
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self._erreurs(r))
        self.assertFalse(
            Article.objects.filter(boutique=self.depot, code='BT-ART-COPIE').exists())

    def test_post_boutique_cree_une_copie_avec_le_code_du_depot(self):
        r = self._post_facture(self.url_boutique, 'FAC-BT-1', [
            self._ligne('DEP-ART-1', 'Riz 25kg'),
        ])
        self.assertEqual(r.status_code, 302, self._erreurs(r))
        self.assertFalse(self._erreurs(r))
        copie = Article.objects.get(boutique=self.boutique, code='DEP-ART-1')
        self.assertEqual(copie.quantite_stock, 4)

    def test_post_boutique_avec_article_du_depot_reference_n_est_pas_pris(self):
        r = self._post_facture(self.url_boutique, 'FAC-BT-2', [
            self._ligne('DEP-ART-1', 'Riz 25kg',
                        article_id=self.article_depot.id, prix_vente=31000),
        ])
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self._erreurs(r))
        self.article_depot.refresh_from_db()
        self.assertEqual(self.article_depot.quantite_stock, 8)
