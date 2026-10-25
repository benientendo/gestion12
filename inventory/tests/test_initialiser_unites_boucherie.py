"""
Commande initialiser_unites_boucherie
======================================
La carte « Prix » du back office n'affiche les unités (kg, demi, rame,
carton) que si l'article a des conditionnements. Beaucoup d'articles de
Boucherie en production n'en ont pas : cette commande les initialise.

- simulation par défaut, --apply pour écrire
- jamais d'écrasement d'unités existantes
- coefficients selon l'unité de base (g -> x1000)
"""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from inventory.models import (
    Article, Boutique, Categorie, Commercant, Conditionnement,
)

User = get_user_model()


class InitialiserUnitesBoucherieTestCase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='init_unites_comm', password='x', email='init_unites@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='INIT UNITES SARL', nom_responsable='INIT UNITES',
            email='init_unites@test.cd', user=self.user,
        )
        self.boucherie = Boutique.objects.create(
            nom='Boucherie Test', commercant=self.commercant,
            code_boutique='BT-INIT-001', type_commerce='BOUCHERIE',
        )
        self.categorie = Categorie.objects.create(
            nom='Viandes', boutique=self.boucherie,
        )
        self.art_kg = Article.objects.create(
            boutique=self.boucherie, code='INI-KG', nom='Boeuf',
            prix_vente=5000, quantite_stock=10, categorie=self.categorie,
            unite_base='kg',
        )
        self.art_g = Article.objects.create(
            boutique=self.boucherie, code='INI-G', nom='Porc',
            prix_vente=8, quantite_stock=10, categorie=self.categorie,
            unite_base='g',
        )
        self.art_vide = Article.objects.create(
            boutique=self.boucherie, code='INI-V', nom='Abats',
            prix_vente=2000, quantite_stock=10, categorie=self.categorie,
            unite_base='',
        )
        self.art_pourvu = Article.objects.create(
            boutique=self.boucherie, code='INI-P', nom='Agneau',
            prix_vente=6000, quantite_stock=10, categorie=self.categorie,
            unite_base='kg',
        )
        Conditionnement.objects.create(
            article=self.art_pourvu, libelle='kg', coefficient=1,
            prix_vente=6000,
        )

        self.autre_boucherie = Boutique.objects.create(
            nom='Boucherie Autre', commercant=self.commercant,
            code_boutique='BT-INIT-002', type_commerce='BOUCHERIE',
        )
        self.art_autre = Article.objects.create(
            boutique=self.autre_boucherie, code='INI-A', nom='Poulet',
            prix_vente=4000, quantite_stock=5, unite_base='kg',
        )

        self.general = Boutique.objects.create(
            nom='Commerce General', commercant=self.commercant,
            code_boutique='BT-INIT-003', type_commerce='GENERAL',
        )
        self.art_general = Article.objects.create(
            boutique=self.general, code='INI-GEN', nom='Savon',
            prix_vente=1000, quantite_stock=5, unite_base='kg',
        )

    def _run(self, *args):
        out = StringIO()
        call_command('initialiser_unites_boucherie', *args,
                     stdout=out, no_color=True)
        return out.getvalue()

    def _coeffs(self, article):
        return list(
            article.conditionnements.order_by('ordre')
            .values_list('libelle', 'coefficient')
        )

    # ----- simulation -----

    def test_simulation_par_defaut_n_ecrit_rien(self):
        sortie = self._run()
        self.assertIn('SIMULATION', sortie)
        self.assertEqual(Conditionnement.objects.count(), 1)  # seul art_pourvu

    def test_simulation_annonce_les_articles_creables(self):
        sortie = self._run()
        self.assertIn('Boeuf', sortie)
        self.assertIn('seraient créés', sortie)

    # ----- écriture -----

    def test_apply_cree_unites_standard_pour_base_kg(self):
        self._run('--apply')
        self.assertEqual(
            self._coeffs(self.art_kg),
            [('kg', 1), ('demi', 5), ('rame', 10), ('carton', 30)],
        )
        # prix laissés vides -> prix auto = prix de base × coefficient
        kg = self.art_kg.conditionnements.get(libelle='kg')
        self.assertIsNone(kg.prix_vente)
        self.assertEqual(kg.prix_vente_effectif, 5000)
        carton = self.art_kg.conditionnements.get(libelle='carton')
        self.assertEqual(carton.prix_vente_effectif, 5000 * 30)

    def test_apply_base_g_coefficients_x1000(self):
        self._run('--apply')
        self.assertEqual(
            self._coeffs(self.art_g),
            [('kg', 1000), ('demi', 5000), ('rame', 10000), ('carton', 30000)],
        )

    def test_apply_ne_cree_pas_de_version_ni_de_mouvement(self):
        version_avant = self.art_kg.version
        self._run('--apply')
        self.art_kg.refresh_from_db()
        self.assertEqual(self.art_kg.version, version_avant)

    # ----- garde-fous -----

    def test_article_deja_pourvu_est_ignore_sans_ecrasement(self):
        self._run('--apply')
        self.assertEqual(
            self._coeffs(self.art_pourvu), [('kg', 1)],
        )

    def test_article_sans_unite_base_est_ignore(self):
        self._run('--apply')
        self.assertFalse(self.art_vide.conditionnements.exists())
        sortie = self._run('--apply')
        self.assertIn('unité de base vide', sortie)

    def test_articles_d_une_autre_boucherie_traites(self):
        self._run('--apply')
        self.assertTrue(self.art_autre.conditionnements.exists())

    def test_articles_hors_boucherie_jamais_touches(self):
        self._run('--apply')
        self.assertFalse(self.art_general.conditionnements.exists())

    def test_boutique_id_limite_le_traitement(self):
        self._run('--apply', '--boutique-id', str(self.autre_boucherie.id))
        self.assertTrue(self.art_autre.conditionnements.exists())
        self.assertFalse(self.art_kg.conditionnements.exists())

    def test_boutique_id_hors_boucherie_erreur(self):
        sortie = self._run('--apply', '--boutique-id', str(self.general.id))
        self.assertIn('introuvable', sortie)
        self.assertFalse(Conditionnement.objects.filter(article=self.art_general).exists())
