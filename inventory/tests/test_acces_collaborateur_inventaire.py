"""
Accès inventaire par un collaborateur (connexion code PIN)
==========================================================
`commercant_required` (celui de views_commercant) laisse passer les
collaborateurs, mais eux n'ont aucun `profil_commercant` : lire cet attribut
levait RelatedObjectDoesNotExist → erreur 500.

- connexion PIN avec inventaire en cours → page de saisie ;
- connexion PIN sans inventaire → message explicite (plus de dashboard) ;
- dashboard, liste d'inventaires, entrer boutique et stats : accessibles ;
- le commerçant conserve son dashboard.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import (
    Article, Boutique, Collaborateur, Commercant, Inventaire, LigneInventaire,
)

User = get_user_model()


class AccesCollaborateurInventaireBase(TestCase):

    def setUp(self):
        self.user_commercant = User.objects.create_user(
            username='acc_comm', password='x', email='acc_comm@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='ACC SARL',
            nom_responsable='ACC',
            email='acc_comm@test.cd',
            user=self.user_commercant,
        )
        self.boutique = Boutique.objects.create(
            nom='ACC PDV',
            commercant=self.commercant,
            code_boutique='BT-ACC-001',
        )

        self.user_collab = User.objects.create_user(username='acc_collab', password='x')
        self.collaborateur = Collaborateur.objects.create(
            user=self.user_collab,
            commercant=self.commercant,
            nom_complet='Jean Compte',
            code_pin='1234',
            est_actif=True,
        )
        self.collaborateur.boutiques_autorisees.add(self.boutique)

        self.inventaire = Inventaire.objects.create(
            boutique=self.boutique,
            reference='INV-ACC-001',
            date_inventaire=date.today(),
            statut='EN_COURS',
            cree_par=self.user_commercant,
        )
        article = Article.objects.create(
            code='ACC-ART-1', nom='Savon', boutique=self.boutique,
            prix_vente=1000, quantite_stock=10,
        )
        LigneInventaire.objects.create(
            inventaire=self.inventaire, article=article,
            stock_theorique=10, prix_unitaire=1000,
        )

    def _login_pin(self):
        return self.client.post(reverse('inventory:login_pin'), {'pin': '1234'},
                                follow=True)


class ConnexionPinTest(AccesCollaborateurInventaireBase):

    def test_pin_avec_inventaire_en_cours_vers_la_saisie(self):
        r = self._login_pin()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.request['PATH_INFO'],
            f'/commercant/boutiques/{self.boutique.id}/inventaires/{self.inventaire.id}/saisir/',
        )

    def test_pin_sans_inventaire_en_cours_ne_plante_pas(self):
        """Auparavant : redirect vers le dashboard commerçant → erreur 500."""
        self.inventaire.statut = 'TERMINE'
        self.inventaire.save(update_fields=['statut'])

        r = self._login_pin()

        self.assertEqual(r.status_code, 200)
        self.assertIn('/login/pin/', r.request['PATH_INFO'])
        self.assertContains(r, 'Aucun inventaire en cours')

    def test_pin_invalide_rend_la_page_pin(self):
        r = self.client.post(reverse('inventory:login_pin'), {'pin': '9999'},
                             follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Code PIN invalide')


class PagesInventaireCollaborateurTest(AccesCollaborateurInventaireBase):

    def setUp(self):
        super().setUp()
        self._login_pin()

    def test_dashboard_ne_plante_pas(self):
        """base.html pointe vers ce dashboard (logo + menu) : 500 avant."""
        r = self.client.get(reverse('inventory:commercant_dashboard'), follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Savon')

    def test_liste_des_inventaires_accessible(self):
        r = self.client.get(
            reverse('inventory:liste_inventaires_boutique', args=[self.boutique.id]),
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'INV-ACC-001')

    def test_entrer_boutique_accessible(self):
        """Fil d'Ariane « Retour au point de vente » des pages d'inventaire."""
        r = self.client.get(
            reverse('inventory:entrer_boutique', args=[self.boutique.id]),
        )
        self.assertEqual(r.status_code, 200)

    def test_stats_boutique_accessible(self):
        r = self.client.get(
            reverse('inventory:commercant_api_stats_boutique', args=[self.boutique.id]),
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r['Content-Type'].startswith('application/json'))

    def test_bouton_gestion_collaborateurs_masque(self):
        r = self.client.get(
            reverse('inventory:liste_inventaires_boutique', args=[self.boutique.id]),
        )
        self.assertNotContains(r, 'Gérer les collaborateurs')

    def test_saisie_et_detail_inventaire_accessibles(self):
        args = [self.boutique.id, self.inventaire.id]
        for name in ('saisir_inventaire_boutique', 'detail_inventaire_boutique',
                     'tableau_bord_inventaire'):
            r = self.client.get(reverse(f'inventory:{name}', args=args))
            self.assertEqual(r.status_code, 200, name)


class DashboardCommercantTest(AccesCollaborateurInventaireBase):
    """Régression : le commerçant garde son dashboard."""

    def test_commercant_voir_son_dashboard(self):
        self.client.force_login(self.user_commercant)
        r = self.client.get(reverse('inventory:commercant_dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'ACC PDV')
