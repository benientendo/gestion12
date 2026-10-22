"""
Création d'une boutique : nom en double → message d'erreur (plus d'erreur 500)
==============================================================================
Le formulaire ne contient pas le champ « commercant », donc Django ne peut pas
appliquer le unique_together (commercant, nom). Sans contrôle, un nom déjà
utilisé provoquait un IntegrityError → erreur 500 (cas « Mbolongo »).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import Boutique, Commercant

User = get_user_model()


class CreerBoutiqueBase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='bout_comm', password='x', email='bout_comm@test.cd')
        self.commercant = Commercant.objects.create(
            nom_entreprise='Mbolongo SARL', nom_responsable='Mbolongo',
            email='bout_comm@test.cd', user=self.user, max_boutiques=5,
        )
        # Le dépôt par défaut du commerçant porte déjà MBOL_BOUT_001 : on laisse
        # le code s'autogénérer pour la boutique existante (MBOL_BOUT_002).
        self.boutique_existante = Boutique.objects.create(
            nom='Mbolongo', commercant=self.commercant,
            type_commerce='BOUCHERIE',
        )
        self.url = reverse('inventory:commercant_creer_boutique')
        self.client.force_login(self.user)

    def _post(self, nom, type_commerce='BOUCHERIE'):
        return self.client.post(self.url, {
            'nom': nom, 'description': '', 'type_commerce': type_commerce,
            'adresse': '', 'ville': '', 'code_postal': '', 'telephone': '', 'email': '',
        })


class CreerBoutiqueDoublonTest(CreerBoutiqueBase):

    def test_nom_en_double_renvoie_un_message_et_non_une_erreur_500(self):
        r = self._post('Mbolongo')
        self.assertEqual(r.status_code, 200)  # formulaire réaffiché, pas de 500
        messages = [str(m) for m in r.context['messages']]
        self.assertTrue(any('existe déjà' in m for m in messages), messages)
        self.assertEqual(
            Boutique.objects.filter(commercant=self.commercant, nom='Mbolongo').count(), 1)

    def test_nom_neuf_cree_la_boutique(self):
        r = self._post('Boucherie Mbolongo', 'BOUCHERIE')
        self.assertEqual(r.status_code, 302)
        nouvelle = Boutique.objects.get(commercant=self.commercant, nom='Boucherie Mbolongo')
        self.assertEqual(nouvelle.type_commerce, 'BOUCHERIE')
        self.assertFalse(nouvelle.est_depot)
        self.assertTrue(nouvelle.code_boutique)

    def test_type_depot_positionne_le_flag(self):
        r = self._post('Dépôt Annexe', 'DEPOT')
        self.assertEqual(r.status_code, 302)
        nouvelle = Boutique.objects.get(commercant=self.commercant, nom='Dépôt Annexe')
        self.assertTrue(nouvelle.est_depot)


class CodeBoutiqueSansCollisionTest(TestCase):
    """Le code auto-généré doit éviter les codes déjà attribués à un autre commerçant."""

    def test_code_evite_une_collision_entre_commercants(self):
        user1 = User.objects.create_user(username='c1', password='x', email='c1@t.cd')
        user2 = User.objects.create_user(username='c2', password='x', email='c2@t.cd')
        autre = Commercant.objects.create(
            nom_entreprise='Autre TEST', email='c1@t.cd', user=user1, max_boutiques=5)
        # Autre TEST : dépôt auto AUTR_BOUT_001 ; on prend TEST_BOUT_002 pour lui.
        Boutique.objects.create(
            nom='Preexistante', commercant=autre, code_boutique='TEST_BOUT_002')
        cible = Commercant.objects.create(
            nom_entreprise='TEST SARL', email='c2@t.cd', user=user2, max_boutiques=5)
        # TEST SARL : dépôt auto TEST_BOUT_001 ; la boutique suivante voudrait
        # TEST_BOUT_002 (déjà pris par « autre ») et doit passer à TEST_BOUT_003.
        nouvelle = Boutique.objects.create(nom='TEST boutique 2', commercant=cible)
        self.assertEqual(nouvelle.code_boutique, 'TEST_BOUT_003')
