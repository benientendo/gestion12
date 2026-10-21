"""
Ajout d'un article pendant un inventaire en cours
=================================================
Depuis la page de saisie, on peut rattacher un article absent de l'inventaire
(article créé au vol, ou créé dans la boutique après le démarrage).

L'article rejoint l'inventaire avec un stock théorique de 0 : la quantité
comptée devient un écart, repris par la régularisation (stock final = compté).
"""
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import (
    Article, Boutique, Categorie, Collaborateur, Commercant, HistoriqueSaisieInventaire,
    Inventaire, LigneInventaire, MouvementStock,
)

User = get_user_model()


class AjoutArticleInventaireBase(TestCase):

    def setUp(self):
        self.user_commercant = User.objects.create_user(
            username='inv_comm', password='x', email='inv_comm@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='INV SARL', nom_responsable='INV',
            email='inv_comm@test.cd', user=self.user_commercant,
        )
        self.boutique = Boutique.objects.create(
            nom='INV PDV', commercant=self.commercant, code_boutique='BT-INV-001',
        )
        self.categorie = Categorie.objects.create(nom='Entretien', boutique=self.boutique)

        self.article_existant = Article.objects.create(
            boutique=self.boutique, code='INV-ART-1', nom='Savon',
            prix_vente=1000, quantite_stock=12,
        )

        self.inventaire = Inventaire.objects.create(
            boutique=self.boutique, reference='INV-TEST-001',
            date_inventaire=date.today(), statut='EN_COURS',
            cree_par=self.user_commercant,
        )
        LigneInventaire.objects.create(
            inventaire=self.inventaire, article=self.article_existant,
            stock_theorique=12, prix_unitaire=1000,
        )
        self.inventaire.calculer_statistiques()

        self.client.force_login(self.user_commercant)

        self.url = reverse('inventory:ajouter_article_inventaire_ajax',
                           args=[self.boutique.id, self.inventaire.id])

    def _post(self, **body):
        return self.client.post(self.url, json.dumps(body), content_type='application/json')


class AjoutArticleTest(AjoutArticleInventaireBase):

    def test_article_inconnu_cree_l_article_et_la_ligne(self):
        r = self._post(code='INV-NEW-1', nom='Eponge', prix_vente='1500',
                       categorie_id=self.categorie.id, quantite=5)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['article_cree'])
        self.assertTrue(data['ligne_creee'])

        article = Article.objects.get(boutique=self.boutique, code='INV-NEW-1')
        self.assertEqual(article.nom, 'Eponge')
        self.assertEqual(article.quantite_stock, 0)
        self.assertEqual(article.prix_vente, 1500)
        self.assertEqual(article.categorie_id, self.categorie.id)

        ligne = LigneInventaire.objects.get(inventaire=self.inventaire, article=article)
        self.assertEqual(ligne.stock_theorique, 0)
        self.assertEqual(ligne.stock_physique, 5)
        self.assertEqual(ligne.ecart, 5)
        self.assertEqual(
            HistoriqueSaisieInventaire.objects.filter(ligne_inventaire=ligne).count(), 1
        )

        self.inventaire.refresh_from_db()
        self.assertEqual(self.inventaire.nb_articles, 2)

    def test_article_existant_sans_ligne_est_rattache(self):
        """Article créé dans la boutique APRÈS le démarrage de l'inventaire."""
        article = Article.objects.create(
            boutique=self.boutique, code='INV-LATE', nom='Arrivee tardive',
            prix_vente=700, quantite_stock=7,
        )
        nb_articles = Article.objects.filter(boutique=self.boutique).count()

        r = self._post(code='INV-LATE', quantite=9)

        self.assertTrue(r.json()['success'])
        self.assertFalse(r.json()['article_cree'])
        self.assertEqual(
            Article.objects.filter(boutique=self.boutique).count(), nb_articles
        )
        ligne = LigneInventaire.objects.get(inventaire=self.inventaire, article=article)
        self.assertEqual(ligne.stock_theorique, 7)
        self.assertEqual(ligne.stock_physique, 9)
        self.assertEqual(ligne.ecart, 2)

    def test_code_en_double_ne_cree_qu_une_seule_ligne(self):
        self._post(code='INV-DUP', nom='Doublon')
        r2 = self._post(code='INV-DUP', nom='Doublon')

        data = r2.json()
        self.assertTrue(data['success'])
        self.assertFalse(data['article_cree'])
        self.assertFalse(data['ligne_creee'])
        self.assertEqual(
            Article.objects.filter(boutique=self.boutique, code='INV-DUP').count(), 1
        )
        self.assertEqual(LigneInventaire.objects.filter(
            inventaire=self.inventaire, article__code='INV-DUP').count(), 1)

    def test_code_vide_genere_un_code(self):
        r = self._post(nom='Sans code', quantite=3)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['article_code'])
        ligne = LigneInventaire.objects.get(id=data['ligne_id'])
        self.assertEqual(ligne.stock_physique, 3)

    def test_sans_quantite_la_ligne_reste_non_saisie(self):
        r = self._post(code='INV-NOQTE', nom='Non compte')
        data = r.json()
        self.assertIsNone(data['stock_physique'])
        self.assertEqual(data['ecart'], 0)
        self.assertEqual(data['nb_saisis'], 0)
        self.assertEqual(data['nb_total'], 2)

    def test_nom_obligatoire(self):
        r = self._post(code='INV-X')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()['success'])

    def test_prix_achat_enregistre_et_devient_le_prix_unitaire(self):
        r = self._post(code='INV-PA', nom='Produit PA', prix_achat='800',
                       prix_vente='1500', quantite=3)
        self.assertTrue(r.json()['success'])
        self.assertEqual(r.json()['prix_achat'], 800.0)

        article = Article.objects.get(boutique=self.boutique, code='INV-PA')
        self.assertEqual(article.prix_achat, 800)
        self.assertEqual(article.prix_vente, 1500)

        ligne = LigneInventaire.objects.get(inventaire=self.inventaire, article=article)
        self.assertEqual(ligne.prix_unitaire, 800)
        self.assertEqual(r.json()['prix_unitaire_ligne'], 800.0)
        self.assertEqual(ligne.ecart, 3)
        self.assertEqual(ligne.valeur_ecart, 2400)

    def test_sans_prix_achat_le_prix_unitaire_est_le_prix_de_vente(self):
        r = self._post(code='INV-PA2', nom='Produit PV', prix_vente='1000')
        self.assertTrue(r.json()['success'])
        ligne = LigneInventaire.objects.get(id=r.json()['ligne_id'])
        self.assertEqual(ligne.prix_unitaire, 1000)

    def test_prix_achat_renseigne_sur_un_article_existant(self):
        r = self._post(code='INV-ART-1', prix_achat='600')
        self.assertTrue(r.json()['success'])
        self.assertFalse(r.json()['article_cree'])

        article = Article.objects.get(boutique=self.boutique, code='INV-ART-1')
        self.assertEqual(article.prix_achat, 600)
        self.assertEqual(article.prix_vente, 1000)

        ligne = LigneInventaire.objects.get(inventaire=self.inventaire, article=article)
        self.assertEqual(ligne.prix_unitaire, 600)

    def test_collegue_peut_ajouter(self):
        user_collab = User.objects.create_user(username='inv_collab', password='x')
        Collaborateur.objects.create(
            user=user_collab, commercant=self.commercant,
            nom_complet='Agent Compte', code_pin='7777', est_actif=True,
        )
        self.client.force_login(user_collab)
        r = self._post(code='INV-COLLAB', nom='Article agent')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['success'])

    def test_anonyme_redirige_vers_la_connexion(self):
        self.client.logout()
        r = self._post(code='INV-ANON', nom='Anonyme')
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Article.objects.filter(code='INV-ANON').exists())


class RegularisationDuNouvelArticleTest(AjoutArticleInventaireBase):
    """Le nouvel article doit être repris par la régularisation de l'inventaire."""

    def _terminer_et_regulariser(self):
        self.client.force_login(self.user_commercant)
        args = [self.boutique.id, self.inventaire.id]
        self.client.post(reverse('inventory:terminer_inventaire_boutique', args=args))
        self.client.post(reverse('inventory:regulariser_inventaire_boutique', args=args),
                         follow=True)

    def test_stock_compte_applique_a_la_regularisation(self):
        r = self._post(code='INV-REG', nom='Produit compte', quantite=5)
        article_id = r.json()['article_id']

        self._terminer_et_regulariser()

        article = Article.objects.get(id=article_id)
        self.assertEqual(article.quantite_stock, 5)

        ligne = LigneInventaire.objects.get(inventaire=self.inventaire, article_id=article_id)
        self.assertTrue(ligne.est_regularise)

        mvt = MouvementStock.objects.filter(
            article=article, reference_document=f"INV-{self.inventaire.id}"
        )
        self.assertEqual(mvt.count(), 1)
        self.assertEqual(mvt.get().type_mouvement, 'ENTREE')
        self.assertEqual(mvt.get().quantite, 5)

        self.inventaire.refresh_from_db()
        self.assertEqual(self.inventaire.statut, 'REGULARISE')

    def test_article_non_compte_passe_en_stock_nul(self):
        r = self._post(code='INV-REG2', nom='Non compte du tout')
        article_id = r.json()['article_id']
        # Au moins une ligne saisie, sinon l'inventaire ne peut pas être terminé.
        self._post(code='INV-ART-1', quantite=12)

        self._terminer_et_regulariser()

        article = Article.objects.get(id=article_id)
        self.assertEqual(article.quantite_stock, 0)
        ligne = LigneInventaire.objects.get(inventaire=self.inventaire, article_id=article_id)
        self.assertTrue(ligne.est_regularise)
