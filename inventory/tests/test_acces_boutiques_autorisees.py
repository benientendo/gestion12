"""
Boutiques autorisées d'un collaborateur
=======================================
Le formulaire « Ajouter un collaborateur » permet de cocher des boutiques
(laissées vides = toutes les boutiques du commerçant). Ce champ était
enregistré mais jamais appliqué : un collaborateur pouvait ouvrir n'importe
quel point de vente du commerçant en tapant l'URL.

Contrôles vérifiés ici :
- collaborateur limité → 403 sur toute boutique non cochée (pages ET AJAX de
  saisie/terminer/validation, aucune écriture) ;
- accès conservé sur les boutiques cochées ;
- connexion PIN : jamais redirigé vers une boutique non ouverte ;
- collaborateur sans restriction → toutes les boutiques (comportement antérieur) ;
- le commerçant, lui, garde l'accès à toutes ses boutiques (non-régression).
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import (
    Article, Boutique, Collaborateur, Commercant, Inventaire, LigneInventaire,
    PropositionInventaire,
)

User = get_user_model()


class BoutiquesAutoriseesBase(TestCase):

    def setUp(self):
        self.user_commercant = User.objects.create_user(
            username='ba_comm', password='x', email='ba_comm@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='KMC KIMPESE 01', nom_responsable='KMC',
            email='ba_comm@test.cd', user=self.user_commercant,
            validation_inventaire_requise=True,
        )
        self.boutique_a = Boutique.objects.create(
            nom='KMC PDV A', commercant=self.commercant, code_boutique='BT-BA-A',
        )
        self.boutique_b = Boutique.objects.create(
            nom='KMC PDV B', commercant=self.commercant, code_boutique='BT-BA-B',
        )

        self.user_collab = User.objects.create_user(username='ba_collab', password='x')
        self.collaborateur = Collaborateur.objects.create(
            user=self.user_collab, commercant=self.commercant,
            nom_complet='Paul Compte', code_pin='7788', est_actif=True,
        )

        # Un inventaire en cours dans CHAQUE boutique
        self.inventaire_a = self._inventaire(self.boutique_a, 'INV-BA-A')
        self.inventaire_b = self._inventaire(self.boutique_b, 'INV-BA-B')
        self.article_a = self._article(self.boutique_a, 'BA-ART-A')
        self.article_b = self._article(self.boutique_b, 'BA-ART-B')
        self.ligne_a = self._ligne(self.inventaire_a, self.article_a)
        self.ligne_b = self._ligne(self.inventaire_b, self.article_b)

    def _inventaire(self, boutique, reference):
        return Inventaire.objects.create(
            boutique=boutique, reference=reference,
            date_inventaire=date.today(), statut='EN_COURS',
            cree_par=self.user_commercant,
        )

    def _article(self, boutique, code):
        return Article.objects.create(
            boutique=boutique, code=code, nom=f'Article {code}',
            prix_vente=1000, quantite_stock=10,
        )

    def _ligne(self, inventaire, article):
        return LigneInventaire.objects.create(
            inventaire=inventaire, article=article,
            stock_theorique=10, prix_unitaire=500,
        )

    def _url(self, nom, boutique, inventaire=None):
        args = [boutique.id]
        if inventaire is not None:
            args.append(inventaire.id)
        return reverse(f'inventory:{nom}', args=args)


class CollaborateurRestreintTest(BoutiquesAutoriseesBase):
    """Collaborateur limité à la boutique A uniquement."""

    def setUp(self):
        super().setUp()
        self.collaborateur.boutiques_autorisees.add(self.boutique_a)
        self.client.force_login(self.user_collab)

    def test_acces_conserve_sur_sa_boutique(self):
        for nom, inv in (
            ('entrer_boutique', None),
            ('liste_inventaires_boutique', None),
            ('detail_inventaire_boutique', self.inventaire_a),
            ('saisir_inventaire_boutique', self.inventaire_a),
        ):
            r = self.client.get(self._url(nom, self.boutique_a, inv))
            self.assertEqual(r.status_code, 200, f'{nom} → {r.status_code}')

    def test_acces_refuse_sur_les_autres_boutiques(self):
        for nom, inv in (
            ('entrer_boutique', None),
            ('liste_inventaires_boutique', None),
            ('detail_inventaire_boutique', self.inventaire_b),
            ('saisir_inventaire_boutique', self.inventaire_b),
            ('valider_saisies_inventaire_boutique', self.inventaire_b),
        ):
            r = self.client.get(self._url(nom, self.boutique_b, inv))
            self.assertEqual(r.status_code, 403, f'{nom} → {r.status_code}')

    def test_saisie_ajax_refusee_sans_ecriture(self):
        import json
        r = self.client.post(
            self._url('saisir_ligne_inventaire_ajax', self.boutique_b, self.inventaire_b),
            json.dumps({'ligne_id': self.ligne_b.id, 'stock_physique': 7}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 403)

        self.ligne_b.refresh_from_db()
        self.assertIsNone(self.ligne_b.stock_physique)
        self.assertEqual(PropositionInventaire.objects.count(), 0)

    def test_terminer_refuse_sur_boutique_non_autorisee(self):
        r = self.client.post(
            self._url('terminer_inventaire_boutique', self.boutique_b, self.inventaire_b),
        )
        self.assertEqual(r.status_code, 403)
        self.inventaire_b.refresh_from_db()
        self.assertEqual(self.inventaire_b.statut, 'EN_COURS')

    def test_pin_login_atterrit_sur_sa_boutique(self):
        r = self.client.post(reverse('inventory:login_pin'), {'pin': '7788'})
        self.assertEqual(r.status_code, 302)
        self.assertIn(
            f'/inventaires/{self.inventaire_a.id}/saisir/', r['Location'],
        )
        self.assertNotIn(f'/inventaires/{self.inventaire_b.id}/', r['Location'])

    def test_pin_login_bloque_si_seul_inventaire_dans_une_autre_boutique(self):
        self.inventaire_a.statut = 'ANNULE'
        self.inventaire_a.save(update_fields=['statut'])

        r = self.client.post(reverse('inventory:login_pin'), {'pin': '7788'})
        self.assertEqual(r.status_code, 200)  # rend la page PIN, pas la boutique B
        # (l'apostrophe est échappée en HTML : on cherche un fragment sans elle)
        self.assertContains(r, "pas ouverte pour vous")


class CollaborateurSansRestrictionTest(BoutiquesAutoriseesBase):
    """Liste vide = toutes les boutiques (comportement historique)."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user_collab)

    def test_acces_a_toutes_les_boutiques(self):
        for boutique in (self.boutique_a, self.boutique_b):
            r = self.client.get(self._url('entrer_boutique', boutique))
            self.assertEqual(r.status_code, 200)

    def test_pin_login_peut_atterrir_dans_n_importe_quelle_boutique(self):
        r = self.client.post(reverse('inventory:login_pin'), {'pin': '7788'})
        self.assertEqual(r.status_code, 302)
        self.assertIn('/inventaires/', r['Location'])


class CommercantNonConcerneTest(BoutiquesAutoriseesBase):
    """Le commerçant garde l'accès à toutes ses boutiques (non-régression)."""

    def setUp(self):
        super().setUp()
        # Un collègue restrictif n'a aucun effet sur le commerçant
        self.collaborateur.boutiques_autorisees.add(self.boutique_a)
        self.client.force_login(self.user_commercant)

    def test_commercant_accede_aux_deux_boutiques(self):
        for boutique in (self.boutique_a, self.boutique_b):
            r = self.client.get(self._url('entrer_boutique', boutique))
            self.assertEqual(r.status_code, 200)

    def test_commercant_saisit_et_valide_partout(self):
        import json
        r = self.client.post(
            self._url('saisir_ligne_inventaire_ajax', self.boutique_b, self.inventaire_b),
            json.dumps({'ligne_id': self.ligne_b.id, 'stock_physique': 7}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['success'])

        r = self.client.get(
            self._url('valider_saisies_inventaire_boutique',
                      self.boutique_b, self.inventaire_b),
        )
        self.assertEqual(r.status_code, 200)
