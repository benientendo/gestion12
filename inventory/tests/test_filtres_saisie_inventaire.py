"""
Filtres « Saisis » / « Non saisis » et correction d'une quantité saisie
======================================================================
Page de saisie d'inventaire d'une boutique :

- « Saisis » n'affiche que les articles comptés avec au moins 1
- « Non saisis » n'affiche que les articles jamais comptés
- rechercher un article déjà saisi l'affiche directement, même sous
  « Non saisis » (et même s'il n'appartient pas aux 50 premières lignes)
- corriger une valeur déjà saisie la REMPLACE au lieu de l'accumuler
  (tableau = stock_corrige_<id>, panneau rapide = remplacer: true)
"""
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import (
    Article, Boutique, Categorie, Commercant, HistoriqueSaisieInventaire,
    Inventaire, LigneInventaire,
)

User = get_user_model()


class FiltresSaisieInventaireBase(TestCase):

    def setUp(self):
        self.user_commercant = User.objects.create_user(
            username='filtre_comm', password='x', email='filtre_comm@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='FILTRE SARL', nom_responsable='FILTRE',
            email='filtre_comm@test.cd', user=self.user_commercant,
        )
        self.boutique = Boutique.objects.create(
            nom='FILTRE PDV', commercant=self.commercant, code_boutique='BT-FIL-001',
        )
        self.categorie = Categorie.objects.create(nom='Entretien', boutique=self.boutique)

        self.inventaire = Inventaire.objects.create(
            boutique=self.boutique, reference='INV-FILTRE-001',
            date_inventaire=date.today(), statut='EN_COURS',
            cree_par=self.user_commercant,
        )

        # Jamais compté
        self.article_vide = Article.objects.create(
            boutique=self.boutique, code='F-SAV', nom='Savon',
            prix_vente=1000, quantite_stock=12, categorie=self.categorie,
        )
        self.ligne_vide = LigneInventaire.objects.create(
            inventaire=self.inventaire, article=self.article_vide,
            stock_theorique=12, prix_unitaire=500,
        )

        # Compté avec une quantité
        self.article_cinq = Article.objects.create(
            boutique=self.boutique, code='F-EPO', nom='Eponge',
            prix_vente=500, quantite_stock=10, categorie=self.categorie,
        )
        self.ligne_cinq = LigneInventaire.objects.create(
            inventaire=self.inventaire, article=self.article_cinq,
            stock_theorique=10, prix_unitaire=250, stock_physique=5,
        )

        # Compté à zéro (compté, mais sans quantité)
        self.article_zero = Article.objects.create(
            boutique=self.boutique, code='F-BAL', nom='Balai',
            prix_vente=2000, quantite_stock=4, categorie=self.categorie,
        )
        self.ligne_zero = LigneInventaire.objects.create(
            inventaire=self.inventaire, article=self.article_zero,
            stock_theorique=4, prix_unitaire=900, stock_physique=0,
        )

        self.inventaire.calculer_statistiques()
        self.client.force_login(self.user_commercant)

        self.url_page = reverse(
            'inventory:saisir_inventaire_boutique',
            args=[self.boutique.id, self.inventaire.id],
        )
        self.url_ajax = reverse(
            'inventory:saisir_ligne_inventaire_ajax',
            args=[self.boutique.id, self.inventaire.id],
        )
        self.url_recherche = reverse(
            'inventory:lignes_recherche_inventaire_ajax',
            args=[self.boutique.id, self.inventaire.id],
        )

    def _noms_page(self, **params):
        r = self.client.get(self.url_page, params)
        self.assertEqual(r.status_code, 200)
        return [l.article.nom for l in r.context['lignes']]

    def _post_json(self, url, body):
        return self.client.post(url, json.dumps(body), content_type='application/json')


class FiltresEtatTest(FiltresSaisieInventaireBase):

    def test_filtre_saisis_affiche_uniquement_au_moins_une_unite(self):
        """« Saisis » : compté avec au moins 1 (le compté à zéro est exclu)."""
        self.assertEqual(self._noms_page(filtre='saisis'), ['Eponge'])

    def test_filtre_non_saisis_affiche_uniquement_les_jamais_comptes(self):
        self.assertEqual(self._noms_page(filtre='non_saisis'), ['Savon'])

    def test_filtre_tous_affiche_tout(self):
        self.assertEqual(
            self._noms_page(filtre='tous'), ['Balai', 'Eponge', 'Savon'],
        )

    def test_filtre_par_defaut_est_non_saisis(self):
        self.assertEqual(self._noms_page(), ['Savon'])

    def test_compteurs_des_boutons(self):
        r = self.client.get(self.url_page)
        self.assertEqual(r.context['nb_non_saisis'], 1)
        # tous les comptés (5 et 0) : progression
        self.assertEqual(r.context['nb_saisis'], 2)
        # correspond au filtre « Saisis » : au moins 1
        self.assertEqual(r.context['nb_saisis_quantite'], 1)


class RechercheArticleDejaSaisiTest(FiltresSaisieInventaireBase):

    def test_recherche_sous_filtre_non_saisis_affiche_l_article_saisi(self):
        noms = self._noms_page(filtre='non_saisis', q='Eponge')
        self.assertEqual(noms, ['Eponge'])

    def test_recherche_sous_filtre_saisis_affiche_un_article_non_compte(self):
        noms = self._noms_page(filtre='saisis', q='Savon')
        self.assertEqual(noms, ['Savon'])

    def test_recherche_serveur_retrouve_l_article_deja_saisi(self):
        r = self.client.get(self.url_recherche, {'q': 'Eponge'})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['ligne_id'], self.ligne_cinq.id)
        self.assertEqual(data['results'][0]['stock_physique'], 5)

    def test_recherche_serveur_retrouve_l_article_non_encore_compte(self):
        r = self.client.get(self.url_recherche, {'q': 'Savon'})
        self.assertEqual(len(r.json()['results']), 1)
        self.assertIsNone(r.json()['results'][0]['stock_physique'])


class CorrectionQuantiteTest(FiltresSaisieInventaireBase):

    def test_post_remplace_la_valeur_et_accumule_les_nouvelles_saisies(self):
        """Tableau : valeur touchée → remplaçée, valeur vierge → posée."""
        r = self.client.post(self.url_page, {
            'stock_physique_' + str(self.ligne_vide.id): '7',
            'stock_corrige_' + str(self.ligne_cinq.id): '3',
        })
        self.assertEqual(r.status_code, 302)

        self.ligne_vide.refresh_from_db()
        self.assertEqual(self.ligne_vide.stock_physique, 7)
        self.ligne_cinq.refresh_from_db()
        self.assertEqual(self.ligne_cinq.stock_physique, 3)
        # ligne non touchée : inchangée
        self.ligne_zero.refresh_from_db()
        self.assertEqual(self.ligne_zero.stock_physique, 0)

        hist = HistoriqueSaisieInventaire.objects.filter(
            ligne_inventaire=self.ligne_cinq,
        ).order_by('-id').first()
        self.assertEqual(hist.commentaire, 'Correction : 5 → 3')
        self.assertEqual(hist.stock_physique_saisi, 3)

    def test_correction_sans_commentaire_n_ecrase_pas_les_lignes_vides(self):
        self.client.post(self.url_page, {
            'stock_corrige_' + str(self.ligne_cinq.id): '9',
        })
        self.ligne_cinq.refresh_from_db()
        self.assertEqual(self.ligne_cinq.stock_physique, 9)
        self.assertEqual(self.ligne_cinq.ecart, -1)

    def test_saisie_rapide_sans_remplacer_accumule(self):
        """Comportement production inchangé : la saisie rapide additionne."""
        r = self._post_json(self.url_ajax, {
            'ligne_id': self.ligne_cinq.id, 'stock_physique': 5,
        })
        self.assertTrue(r.json()['success'])
        self.ligne_cinq.refresh_from_db()
        self.assertEqual(self.ligne_cinq.stock_physique, 10)

    def test_saisie_rapide_avec_remplacer_corrige(self):
        self._post_json(self.url_ajax, {
            'ligne_id': self.ligne_cinq.id, 'stock_physique': 5,
        })
        r = self._post_json(self.url_ajax, {
            'ligne_id': self.ligne_cinq.id, 'stock_physique': 4,
            'remplacer': True,
        })
        self.assertTrue(r.json()['success'])
        self.ligne_cinq.refresh_from_db()
        self.assertEqual(self.ligne_cinq.stock_physique, 4)

        hist = HistoriqueSaisieInventaire.objects.filter(
            ligne_inventaire=self.ligne_cinq,
        ).order_by('-id').first()
        self.assertEqual(hist.commentaire, 'Correction : 10 → 4')
        self.assertEqual(hist.stock_physique_saisi, 4)

    def test_saisie_rapide_premiere_quantite(self):
        r = self._post_json(self.url_ajax, {
            'ligne_id': self.ligne_vide.id, 'stock_physique': 6,
        })
        self.assertTrue(r.json()['success'])
        self.ligne_vide.refresh_from_db()
        self.assertEqual(self.ligne_vide.stock_physique, 6)
