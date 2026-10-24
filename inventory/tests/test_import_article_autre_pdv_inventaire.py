"""
Import d'un article depuis un autre point de vente PENDANT l'inventaire
=======================================================================
Pendant la saisie, on peut rechercher un article dans les AUTRES boutiques du
même commerçant et de MÊME type, l'importer dans la boutique courante (prix,
unités et conditionnements copiés), puis saisir la quantité comptée.
"""
import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import (
    Article, Boutique, Categorie, Commercant, Conditionnement,
    Inventaire, LigneInventaire,
)

User = get_user_model()


class ImportAutrePdvBase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='imp_comm', password='x', email='imp_comm@test.cd')
        self.commercant = Commercant.objects.create(
            nom_entreprise='IMP SARL', nom_responsable='IMP',
            email='imp_comm@test.cd', user=self.user, max_boutiques=10)

        self.boutique = Boutique.objects.create(
            nom='IMP PDV 1', commercant=self.commercant, code_boutique='BT-IMP-001',
            type_commerce='BOUCHERIE')
        self.autre_pdv = Boutique.objects.create(
            nom='IMP PDV 2', commercant=self.commercant, code_boutique='BT-IMP-002',
            type_commerce='BOUCHERIE')
        self.pdv_autre_type = Boutique.objects.create(
            nom='IMP Pharmacie', commercant=self.commercant, code_boutique='BT-IMP-003',
            type_commerce='PHARMACIE')

        # Autre commerçant, même type
        self.user2 = User.objects.create_user(
            username='autre_comm', password='x', email='autre_comm@test.cd')
        self.autre_commercant = Commercant.objects.create(
            nom_entreprise='AUTRE SARL', email='autre_comm@test.cd',
            user=self.user2, max_boutiques=10)
        self.pdv_autre_commercant = Boutique.objects.create(
            nom='Autre Boucherie', commercant=self.autre_commercant,
            code_boutique='BT-AUT-001', type_commerce='BOUCHERIE')

        self.categorie = Categorie.objects.create(nom='Viandes', boutique=self.autre_pdv)
        self.article_source = Article.objects.create(
            boutique=self.autre_pdv, code='IMP-SRC-1', nom='Poulet entier',
            prix_achat=Decimal('4500'), prix_vente=Decimal('6500'),
            quantite_stock=10, categorie=self.categorie, unite_base='kg',
            pieces_par_carton=12,
        )
        Conditionnement.objects.create(
            article=self.article_source, libelle='Sac', coefficient=25)

        self.article_local_meme_code = None  # rempli au besoin

        self.inventaire = Inventaire.objects.create(
            boutique=self.boutique, reference='INV-IMP-001',
            date_inventaire=date.today(), statut='EN_COURS',
            cree_par=self.user)
        self.inventaire.calculer_statistiques()

        self.client.force_login(self.user)
        self.url_search = reverse(
            'inventory:articles_autres_pdv_inventaire_ajax',
            args=[self.boutique.id, self.inventaire.id])
        self.url_add = reverse(
            'inventory:ajouter_article_inventaire_ajax',
            args=[self.boutique.id, self.inventaire.id])

    def _post(self, **body):
        return self.client.post(
            self.url_add, json.dumps(body), content_type='application/json')


class RechercheAutresPdvTest(ImportAutrePdvBase):

    def test_retrouve_l_article_des_autres_pdv_du_mem_type(self):
        r = self.client.get(self.url_search, {'q': 'Poulet'})
        self.assertEqual(r.status_code, 200)
        results = r.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], self.article_source.id)
        self.assertEqual(results[0]['boutique_nom'], self.autre_pdv.nom)
        self.assertEqual(results[0]['prix_vente'], 6500.0)
        self.assertEqual(results[0]['unite_base'], 'kg')
        self.assertEqual(results[0]['categorie_nom'], 'Viandes')

    def test_ignore_les_pdv_d_un_autre_type(self):
        Article.objects.create(
            boutique=self.pdv_autre_type, code='IMP-PH-1', nom='Poulet gellé',
            prix_vente=Decimal('1000'), quantite_stock=3)
        results = self.client.get(self.url_search, {'q': 'Poulet'}).json()['results']
        self.assertEqual([a['id'] for a in results], [self.article_source.id])

    def test_ignore_les_pdv_d_un_autre_commercant(self):
        Article.objects.create(
            boutique=self.pdv_autre_commercant, code='IMP-AU-1', nom='Poulet bio',
            prix_vente=Decimal('1000'), quantite_stock=3)
        results = self.client.get(self.url_search, {'q': 'Poulet'}).json()['results']
        self.assertEqual([a['id'] for a in results], [self.article_source.id])

    def test_ignore_les_articles_de_sa_propre_boutique(self):
        Article.objects.create(
            boutique=self.boutique, code='IMP-LOC-1', nom='Poulet local',
            prix_vente=Decimal('1000'), quantite_stock=3)
        results = self.client.get(self.url_search, {'q': 'Poulet'}).json()['results']
        self.assertEqual([a['id'] for a in results], [self.article_source.id])

    def test_requete_courte_ne_retourne_rien(self):
        self.assertEqual(self.client.get(self.url_search, {'q': 'P'}).json()['results'], [])

    def test_sans_requete_retourne_la_liste_importable(self):
        results = self.client.get(self.url_search).json()['results']
        self.assertEqual([a['id'] for a in results], [self.article_source.id])


class ImportArticlePendantInventaireTest(ImportAutrePdvBase):

    def test_import_cree_l_article_et_saisit_la_quantite(self):
        r = self._post(autre_article_id=self.article_source.id, quantite=7)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['article_cree'])
        self.assertEqual(data['importe_depuis'], self.autre_pdv.nom)

        article = Article.objects.get(boutique=self.boutique, code='IMP-SRC-1')
        self.assertEqual(article.nom, 'Poulet entier')
        self.assertEqual(article.prix_achat, Decimal('4500'))
        self.assertEqual(article.prix_vente, Decimal('6500'))
        self.assertEqual(article.unite_base, 'kg')
        self.assertEqual(article.pieces_par_carton, 12)
        self.assertEqual(article.quantite_stock, 0)
        self.assertTrue(article.est_valide_client)
        # Catégorie recopiée localement
        self.assertIsNotNone(article.categorie)
        self.assertEqual(article.categorie.boutique_id, self.boutique.id)
        self.assertEqual(article.categorie.nom, 'Viandes')
        # Conditionnement copié (Boucherie)
        conds = list(article.conditionnements.values_list('libelle', 'coefficient'))
        self.assertEqual(conds, [('Sac', 25)])

        # Ligne d'inventaire : théorique 0, quantité comptée saisie
        ligne = LigneInventaire.objects.get(
            inventaire=self.inventaire, article=article)
        self.assertEqual(ligne.stock_theorique, 0)
        self.assertEqual(ligne.stock_physique, 7)
        self.assertEqual(ligne.ecart, 7)

    def test_import_sans_quantite_laisse_la_ligne_non_saisie(self):
        r = self._post(autre_article_id=self.article_source.id)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIsNone(data['stock_physique'])
        ligne = LigneInventaire.objects.get(id=data['ligne_id'])
        self.assertIsNone(ligne.stock_physique)

    def test_prix_saisi_remplace_ceux_de_la_source(self):
        r = self._post(autre_article_id=self.article_source.id,
                       prix_vente='7000', prix_achat='5000')
        self.assertEqual(r.status_code, 200)
        article = Article.objects.get(boutique=self.boutique, code='IMP-SRC-1')
        self.assertEqual(article.prix_vente, Decimal('7000'))
        self.assertEqual(article.prix_achat, Decimal('5000'))

    def test_article_deja_present_est_reutilise(self):
        Article.objects.create(
            boutique=self.boutique, code='IMP-SRC-1', nom='Poulet entier',
            prix_vente=Decimal('6000'), quantite_stock=4)
        r = self._post(autre_article_id=self.article_source.id, quantite=9)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertFalse(data['article_cree'])
        self.assertEqual(Article.objects.filter(
            boutique=self.boutique, code='IMP-SRC-1').count(), 1)
        ligne = LigneInventaire.objects.get(id=data['ligne_id'])
        # Le stock théorique de la boutique courante fait foi
        self.assertEqual(ligne.stock_theorique, 4)
        self.assertEqual(ligne.stock_physique, 9)
        self.assertEqual(ligne.ecart, 5)

    def test_import_depuis_un_pdv_d_un_autre_type_refuse(self):
        autre = Article.objects.create(
            boutique=self.pdv_autre_type, code='IMP-PH-1', nom='Sirop',
            prix_vente=Decimal('1000'), quantite_stock=3)
        r = self._post(autre_article_id=autre.id, quantite=1)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Article.objects.filter(boutique=self.boutique).exists())

    def test_import_depuis_un_autre_commercant_refuse(self):
        autre = Article.objects.create(
            boutique=self.pdv_autre_commercant, code='IMP-AU-1', nom='Steak',
            prix_vente=Decimal('1000'), quantite_stock=3)
        r = self._post(autre_article_id=autre.id, quantite=1)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Article.objects.filter(boutique=self.boutique).exists())

    def test_import_depuis_sa_propre_boutique_refuse(self):
        local = Article.objects.create(
            boutique=self.boutique, code='IMP-LOC-1', nom='Local',
            prix_vente=Decimal('1000'), quantite_stock=3)
        r = self._post(autre_article_id=local.id, quantite=1)
        self.assertEqual(r.status_code, 400)
