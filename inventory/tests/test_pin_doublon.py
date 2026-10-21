"""
Connexion PIN robuste : code PIN en double et plantages imprévus
================================================================
`Collaborateur.code_pin` n'a AUCUNE contrainte unique et la connexion PIN
cherche sur toute la plateforme avec `.get()` → deux collaborateurs actifs
portant le même PIN levaient MultipleObjectsReturned → erreur 500 sur
`/login/pin/` (constaté en production).

- PIN en double : message explicite, page PIN rendue (200) ;
- création de collaborateur : PIN déjà pris → refus ;
- réactivation : PIN repris par un autre actif → refus ;
- plantage inattendu après connexion → message technique, jamais de 500.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import Boutique, Collaborateur, Commercant

User = get_user_model()


class PinDoubleBase(TestCase):

    def setUp(self):
        self.user_commercant = User.objects.create_user(
            username='pin_comm', password='x', email='pin_comm@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='PIN SARL',
            nom_responsable='PIN',
            email='pin_comm@test.cd',
            user=self.user_commercant,
        )
        self.boutique = Boutique.objects.create(
            nom='PIN PDV', commercant=self.commercant, code_boutique='BT-PIN-001',
        )

        def collab(username, nom, pin):
            user = User.objects.create_user(username=username, password='x')
            return Collaborateur.objects.create(
                user=user, commercant=self.commercant, nom_complet=nom,
                code_pin=pin, est_actif=True,
            )

        self.christel = collab('pin_christel', 'Christel', '4321')
        self.autre = collab('pin_autre', 'Autre Agent', '4321')

    def _post_pin(self, pin='4321'):
        return self.client.post(reverse('inventory:login_pin'), {'pin': pin})


class PinEnDoubleTest(PinDoubleBase):

    def test_pin_partage_rend_un_message_et_non_500(self):
        r = self._post_pin()
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'utilisé par plusieurs collaborateurs')

    def test_pin_unique_connexion_toujours_fonctionnelle(self):
        self.autre.code_pin = '9876'
        self.autre.save(update_fields=['code_pin'])

        r = self._post_pin('4321')
        # Pas d'inventaire ici → page PIN avec message, l'utilisateur est connecté.
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Aucun inventaire en cours')
        self.assertIn('_auth_user_id', self.client.session)

    def test_pin_invalide_rend_message_clair(self):
        r = self._post_pin('0000')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Code PIN invalide')

    def test_pin_trop_court_rend_message_clair(self):
        r = self._post_pin('12')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '4 chiffres')

    def test_utilisateur_desactive_rend_un_message(self):
        """Django lève PermissionDenied dans auth.login() → pas de 500."""
        self.autre.code_pin = '9876'
        self.autre.save(update_fields=['code_pin'])
        self.autre.user.is_active = False
        self.autre.user.save(update_fields=['is_active'])

        r = self._post_pin('9876')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'désactivé')


class CreationCollaborateurPinTest(PinDoubleBase):

    def _post(self, data=None):
        payload = {
            'username': 'nouvel_agent', 'password': 'secret',
            'nom_complet': 'Nouvel Agent', 'code_pin': '4321',
            'role': 'INVENTAIRE',
        }
        payload.update(data or {})
        return self.client.post(reverse('inventory:ajouter_collaborateur'), payload,
                                follow=True)

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user_commercant)

    def test_pin_deja_utilise_rejete_la_creation(self):
        r = self._post()
        self.assertContains(r, 'déjà utilisé')
        self.assertFalse(User.objects.filter(username='nouvel_agent').exists())

    def test_pin_trop_court_rejete_la_creation(self):
        r = self._post({'code_pin': '12'})
        self.assertContains(r, '4 chiffres')
        self.assertFalse(User.objects.filter(username='nouvel_agent').exists())

    def test_pin_libre_cree_le_collaborateur(self):
        r = self._post({'code_pin': '5555'})
        self.assertContains(r, 'créé avec succès')
        nouveau = Collaborateur.objects.get(user__username='nouvel_agent')
        self.assertEqual(nouveau.code_pin, '5555')


class ReactivationPinTest(PinDoubleBase):

    def test_reactivation_refusee_si_pin_repris(self):
        self.client.force_login(self.user_commercant)
        self.christel.est_actif = False
        self.christel.save(update_fields=['est_actif'])

        # Autre agent conserve le PIN 4321 de façon active.
        r = self.client.post(
            reverse('inventory:toggle_collaborateur_statut', args=[self.christel.id]),
            follow=True,
        )
        self.assertContains(r, 'déjà utilisé')
        self.christel.refresh_from_db()
        self.assertFalse(self.christel.est_actif)

    def test_reactivation_autorisee_si_pin_libre(self):
        self.client.force_login(self.user_commercant)
        # Christel change de PIN pour que 4321 soit libre.
        self.christel.code_pin = '1111'
        self.christel.save(update_fields=['code_pin'])
        self.autre.est_actif = False
        self.autre.save(update_fields=['est_actif'])

        r = self.client.post(
            reverse('inventory:toggle_collaborateur_statut', args=[self.autre.id]),
            follow=True,
        )
        self.assertContains(r, 'activé')
        self.autre.refresh_from_db()
        self.assertTrue(self.autre.est_actif)


class PlantageImprevuTest(PinDoubleBase):

    def test_erreur_post_connexion_affichee_sans_500(self):
        """Une exception interne doit devenir un message, pas une page 500."""
        self.autre.code_pin = '0000'
        self.autre.save(update_fields=['code_pin'])

        with patch(
            'inventory.views_pin_login.accueil_collaborateur',
            side_effect=RuntimeError('bug interne'),
        ):
            r = self._post_pin('0000')

        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Erreur technique')
        self.assertContains(r, 'bug interne')
