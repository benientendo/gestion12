"""
Validation des saisies d'inventaire par le commerçant (KMC)
==========================================================
Fonctionnalité réservée au commerçant dont le flag
``Commercant.validation_inventaire_requise`` est activé (KMC) :

- la saisie d'un COLLABORATEUR n'écrit plus dans l'inventaire : elle devient
  une ``PropositionInventaire`` EN ATTENTE ;
- le commerçant la vérifie sur une page détaillée puis l'applique (avec
  correction possible de la quantité) ou la refuse (avec motif) ;
- tant qu'il reste des saisies en attente, *Terminer* et *Régulariser* sont
  bloqués : rien n'est appliqué sans le commerçant ;
- les autres commerçants (flag à False) gardent exactement l'ancien
  comportement : régression testée ci-dessous.
"""
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import (
    Article, Boutique, Collaborateur, Commercant, HistoriqueSaisieInventaire,
    Inventaire, LigneInventaire, MouvementStock, PropositionInventaire,
)

User = get_user_model()


class ValidationSaisieBase(TestCase):

    def setUp(self):
        # Commerçant KMC : validation des saisies activée
        self.user_commercant = User.objects.create_user(
            username='kmc_comm', password='x', email='kmc_comm@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='KMC KIMPESE 01', nom_responsable='KMC',
            email='kmc_comm@test.cd', user=self.user_commercant,
            validation_inventaire_requise=True,
        )
        self.boutique = Boutique.objects.create(
            nom='KMC KIMPESE 01', commercant=self.commercant,
            code_boutique='BT-KMC-001',
        )

        self.user_collab = User.objects.create_user(username='kmc_collab', password='x')
        self.collaborateur = Collaborateur.objects.create(
            user=self.user_collab, commercant=self.commercant,
            nom_complet='Jean Compte', code_pin='1234', est_actif=True,
        )
        self.collaborateur.boutiques_autorisees.add(self.boutique)

        self.inventaire = Inventaire.objects.create(
            boutique=self.boutique, reference='INV-KMC-001',
            date_inventaire=date.today(), statut='EN_COURS',
            cree_par=self.user_commercant,
        )
        self.article = Article.objects.create(
            boutique=self.boutique, code='KMC-ART-1', nom='Savon',
            prix_vente=1000, quantite_stock=10,
        )
        self.ligne = LigneInventaire.objects.create(
            inventaire=self.inventaire, article=self.article,
            stock_theorique=10, prix_unitaire=500,
        )
        self.inventaire.calculer_statistiques()

        self.url_ajax = reverse(
            'inventory:saisir_ligne_inventaire_ajax',
            args=[self.boutique.id, self.inventaire.id],
        )
        self.url_saisie = reverse(
            'inventory:saisir_inventaire_boutique',
            args=[self.boutique.id, self.inventaire.id],
        )
        self.url_validation = reverse(
            'inventory:valider_saisies_inventaire_boutique',
            args=[self.boutique.id, self.inventaire.id],
        )

    # -- aides -------------------------------------------------------------
    def _login_collab(self):
        self.client.force_login(self.user_collab)

    def _login_commercant(self):
        self.client.force_login(self.user_commercant)

    def _saisir_ajax(self, qte, remplacer=False, commentaire=''):
        return self.client.post(
            self.url_ajax,
            json.dumps({
                'ligne_id': self.ligne.id,
                'stock_physique': qte,
                'remplacer': remplacer,
                'commentaire': commentaire,
            }),
            content_type='application/json',
        )

    def _proposition(self):
        return self.inventaire.propositions.filter(
            ligne=self.ligne, statut='EN_ATTENTE',
        ).first()


class SaisieCollaborateurTest(ValidationSaisieBase):
    """Le collaborateur propose, il n'applique rien."""

    def test_saisie_devient_proposition_sans_ecriture_dans_inventaire(self):
        self._login_collab()
        r = self._saisir_ajax(7)

        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['en_attente'])
        self.assertEqual(data['stock_physique'], 7)

        self.ligne.refresh_from_db()
        self.assertIsNone(self.ligne.stock_physique)

        prop = self._proposition()
        self.assertIsNotNone(prop)
        self.assertEqual(prop.quantite_proposee, 7)
        self.assertEqual(prop.nom_saisi_par, 'Jean Compte')
        self.assertEqual(prop.saisi_par, self.user_collab)

    def test_aucun_historique_tant_que_non_valide(self):
        self._login_collab()
        self._saisir_ajax(7)
        self.assertEqual(
            HistoriqueSaisieInventaire.objects.filter(inventaire=self.inventaire).count(),
            0,
        )

    def test_deux_saisies_cumulent_dans_une_seule_proposition(self):
        self._login_collab()
        self._saisir_ajax(7)
        self._saisir_ajax(5)

        self.assertEqual(self.inventaire.propositions.count(), 1)
        self.assertEqual(self._proposition().quantite_proposee, 12)

    def test_correction_remplace_la_proposition(self):
        self._login_collab()
        self._saisir_ajax(7)
        self._saisir_ajax(3, remplacer=True)

        self.assertEqual(self.inventaire.propositions.count(), 1)
        self.assertEqual(self._proposition().quantite_proposee, 3)

    def test_la_base_de_partie_est_prise_en_compte(self):
        """Le commerçant a déjà saisi 4 → le collaborateur ajoute 3 → 7."""
        self.ligne.stock_physique = 4
        self.ligne.save(update_fields=['stock_physique'])

        self._login_collab()
        self._saisir_ajax(3)

        self.assertEqual(self._proposition().quantite_proposee, 7)

    def test_page_saisie_affiche_le_badge_en_attente(self):
        self._login_collab()
        self._saisir_ajax(7)

        r = self.client.get(self.url_saisie)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'en attente de validation')

    def test_prix_non_modifiable_par_le_collaborateur(self):
        self._login_collab()
        r = self.client.post(self.url_saisie, {
            f'prix_vente_{self.ligne.id}': '9999',
            f'stock_physique_{self.ligne.id}': '7',
        }, follow=True)

        self.assertEqual(r.status_code, 200)
        self.article.refresh_from_db()
        self.assertEqual(self.article.prix_vente, 1000)
        # La quantité, elle, devient bien une proposition
        self.assertEqual(self._proposition().quantite_proposee, 7)

        messages = [m.message for m in r.context['messages']]
        self.assertTrue(any('Prix non modifiés' in m for m in messages), messages)


class ValidationCommercantTest(ValidationSaisieBase):
    """Le commerçant vérifie la page détaillée puis applique ou refuse."""

    def _saisir_en_attente(self, qte=7):
        self._login_collab()
        self._saisir_ajax(qte)
        self._login_commercant()

    def test_page_validation_interdite_au_collaborateur(self):
        self._login_collab()
        self._saisir_ajax(7)

        r = self.client.get(self.url_validation, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn('saisir', r.request['PATH_INFO'])

    def test_page_validation_detaillee_pour_le_commercant(self):
        self._saisir_en_attente(7)

        r = self.client.get(self.url_validation)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Savon')            # article
        self.assertContains(r, 'Jean Compte')      # qui a compté
        self.assertContains(r, '10')               # stock théorique
        self.assertContains(r, '>7<')              # quantité proposée
        self.assertContains(r, '-3')               # écart résultant

    def test_valider_applique_la_saisie_a_inventaire(self):
        self._saisir_en_attente(7)
        prop = self._proposition()

        r = self.client.post(self.url_validation, {
            'action': 'valider', 'proposition_id': prop.id,
        })
        self.assertEqual(r.status_code, 302)

        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.stock_physique, 7)
        self.assertEqual(self.ligne.ecart, -3)

        prop.refresh_from_db()
        self.assertEqual(prop.statut, 'VALIDEE')
        self.assertEqual(prop.traite_par, self.user_commercant)
        self.assertIsNotNone(prop.date_traitement)
        self.assertEqual(prop.quantite_appliquee, 7)

        hist = HistoriqueSaisieInventaire.objects.filter(inventaire=self.inventaire)
        self.assertEqual(hist.count(), 1)
        self.assertIn('Validé par', hist.first().commentaire)

    def test_valider_avec_quantite_corrigee(self):
        self._saisir_en_attente(7)
        prop = self._proposition()

        self.client.post(self.url_validation, {
            'action': 'valider', 'proposition_id': prop.id,
            'quantite_retenu': '9',
        })

        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.stock_physique, 9)
        prop.refresh_from_db()
        self.assertEqual(prop.statut, 'VALIDEE')
        self.assertEqual(prop.quantite_appliquee, 9)
        self.assertIn(
            'corrigée : 7 → 9',
            HistoriqueSaisieInventaire.objects.first().commentaire,
        )

    def test_refuser_n_applique_rien(self):
        self._saisir_en_attente(7)
        prop = self._proposition()

        self.client.post(self.url_validation, {
            'action': 'refuser', 'proposition_id': prop.id,
            'motif_refus': 'Comptage incohérent',
        })

        self.ligne.refresh_from_db()
        self.assertIsNone(self.ligne.stock_physique)
        prop.refresh_from_db()
        self.assertEqual(prop.statut, 'REFUSEE')
        self.assertEqual(prop.motif_refus, 'Comptage incohérent')
        self.assertEqual(
            HistoriqueSaisieInventaire.objects.filter(inventaire=self.inventaire).count(),
            0,
        )

    def test_valider_tout_traite_toutes_les_saisies(self):
        article2 = Article.objects.create(
            boutique=self.boutique, code='KMC-ART-2', nom='Eponge',
            prix_vente=500, quantite_stock=2,
        )
        ligne2 = LigneInventaire.objects.create(
            inventaire=self.inventaire, article=article2,
            stock_theorique=2, prix_unitaire=250,
        )
        self._login_collab()
        self._saisir_ajax(7)
        self.client.post(self.url_ajax, json.dumps({
            'ligne_id': ligne2.id, 'stock_physique': 5,
        }), content_type='application/json')
        self._login_commercant()

        self.client.post(self.url_validation, {'action': 'valider_tout'})

        self.assertEqual(
            self.inventaire.propositions.filter(statut='EN_ATTENTE').count(), 0,
        )
        self.ligne.refresh_from_db()
        ligne2.refresh_from_db()
        self.assertEqual(self.ligne.stock_physique, 7)
        self.assertEqual(ligne2.stock_physique, 5)


class GardeFousTest(ValidationSaisieBase):
    """Rien ne s'applique (ni se clôt) sans le commerçant."""

    def _saisir_en_attente(self, qte=7):
        self._login_collab()
        self._saisir_ajax(qte)
        self._login_commercant()

    def test_bloque_terminer_tant_que_des_saisies_attendent(self):
        self._saisir_en_attente(7)

        r = self.client.post(reverse(
            'inventory:terminer_inventaire_boutique',
            args=[self.boutique.id, self.inventaire.id],
        ))

        self.inventaire.refresh_from_db()
        self.assertEqual(self.inventaire.statut, 'EN_COURS')
        self.assertIn('valider-saisies', r['Location'])

    def test_bloque_regulariser_tant_que_des_saisies_attendent(self):
        self._saisir_en_attente(7)
        self.inventaire.statut = 'TERMINE'
        self.inventaire.save(update_fields=['statut'])

        r = self.client.post(reverse(
            'inventory:regulariser_inventaire_boutique',
            args=[self.boutique.id, self.inventaire.id],
        ))

        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)  # inchangé
        self.assertIn('valider-saisies', r['Location'])

    def test_collaborateur_ne_peut_pas_terminer(self):
        self._saisir_en_attente(7)
        self._login_collab()

        self.client.post(reverse(
            'inventory:terminer_inventaire_boutique',
            args=[self.boutique.id, self.inventaire.id],
        ))

        self.inventaire.refresh_from_db()
        self.assertEqual(self.inventaire.statut, 'EN_COURS')

    def test_collaborateur_ne_peut_pas_regulariser(self):
        self._saisir_en_attente(7)
        self.inventaire.statut = 'TERMINE'
        self.inventaire.save(update_fields=['statut'])
        self._login_collab()

        self.client.post(reverse(
            'inventory:regulariser_inventaire_boutique',
            args=[self.boutique.id, self.inventaire.id],
        ))

        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)

    def test_collaborateur_ne_peut_pas_demarrer_un_inventaire(self):
        self.inventaire.delete()
        self._login_collab()

        r = self.client.post(reverse(
            'inventory:nouvel_inventaire_boutique', args=[self.boutique.id],
        ), {'date_inventaire': date.today().isoformat()})

        self.assertEqual(r.status_code, 302)
        self.assertEqual(Inventaire.objects.filter(boutique=self.boutique).count(), 0)

    def test_collaborateur_annule_sa_proposition_sans_toucher_inventaire(self):
        self._login_collab()
        self._saisir_ajax(7)
        # Une valeur appliquée par le commerçant ne doit jamais être effacée
        self.ligne.stock_physique = 4
        self.ligne.save(update_fields=['stock_physique'])

        self.client.post(reverse(
            'inventory:reset_ligne_inventaire_ajax',
            args=[self.boutique.id, self.inventaire.id],
        ), json.dumps({'ligne_id': self.ligne.id}), content_type='application/json')

        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.stock_physique, 4)
        self.assertEqual(self._proposition(), None)

    def test_chaine_complete_valider_terminer_regularise_le_stock(self):
        """Bout en bout : proposition → validation → terminer → régularisation."""
        self._saisir_en_attente(7)
        prop = self._proposition()

        # 1. Le commerçant applique la saisie
        self.client.post(self.url_validation, {
            'action': 'valider', 'proposition_id': prop.id,
        })
        # 2. Il clôture l'inventaire
        self.client.post(reverse(
            'inventory:terminer_inventaire_boutique',
            args=[self.boutique.id, self.inventaire.id],
        ))
        self.inventaire.refresh_from_db()
        self.assertEqual(self.inventaire.statut, 'TERMINE')

        # 3. Il régularise : le stock tient enfin compte du comptage (7 au lieu
        #    de 10) avec un mouvement de sortie de 3 unités
        self.client.post(reverse(
            'inventory:regulariser_inventaire_boutique',
            args=[self.boutique.id, self.inventaire.id],
        ))
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 7)

        mvt = MouvementStock.objects.filter(
            article=self.article, type_mouvement='SORTIE',
        )
        self.assertEqual(mvt.count(), 1)
        self.assertEqual(mvt.first().quantite, 3)


class ModeHistoriqueInchangeTest(TestCase):
    """Régression : un commerçant SANS flag garde l'ancien fonctionnement."""

    def setUp(self):
        self.user_commercant = User.objects.create_user(
            username='old_comm', password='x', email='old_comm@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='AUTRE SARL', nom_responsable='AUTRE',
            email='old_comm@test.cd', user=self.user_commercant,
            validation_inventaire_requise=False,
        )
        self.boutique = Boutique.objects.create(
            nom='AUTRE PDV', commercant=self.commercant,
            code_boutique='BT-OLD-001',
        )
        self.user_collab = User.objects.create_user(username='old_collab', password='x')
        self.collaborateur = Collaborateur.objects.create(
            user=self.user_collab, commercant=self.commercant,
            nom_complet='Paul Compte', code_pin='4321', est_actif=True,
        )
        self.inventaire = Inventaire.objects.create(
            boutique=self.boutique, reference='INV-OLD-001',
            date_inventaire=date.today(), statut='EN_COURS',
            cree_par=self.user_commercant,
        )
        self.article = Article.objects.create(
            boutique=self.boutique, code='OLD-ART-1', nom='Savon',
            prix_vente=1000, quantite_stock=10,
        )
        self.ligne = LigneInventaire.objects.create(
            inventaire=self.inventaire, article=self.article,
            stock_theorique=10, prix_unitaire=500,
        )
        self.url_ajax = reverse(
            'inventory:saisir_ligne_inventaire_ajax',
            args=[self.boutique.id, self.inventaire.id],
        )
        self.url_saisie = reverse(
            'inventory:saisir_inventaire_boutique',
            args=[self.boutique.id, self.inventaire.id],
        )

    def test_saisie_directe_sans_flag(self):
        self.client.force_login(self.user_collab)
        r = self.client.post(self.url_ajax, json.dumps({
            'ligne_id': self.ligne.id, 'stock_physique': 7,
        }), content_type='application/json')

        self.assertTrue(r.json()['success'])
        self.assertNotIn('en_attente', r.json())

        self.ligne.refresh_from_db()
        self.assertEqual(self.ligne.stock_physique, 7)
        self.assertEqual(self.inventaire.propositions.count(), 0)
        self.assertEqual(
            HistoriqueSaisieInventaire.objects.filter(inventaire=self.inventaire).count(),
            1,
        )

    def test_prix_toujours_modifiable_sans_flag(self):
        self.client.force_login(self.user_collab)
        self.client.post(self.url_saisie, {
            f'prix_vente_{self.ligne.id}': '9999',
            f'stock_physique_{self.ligne.id}': '7',
        })

        self.article.refresh_from_db()
        self.assertEqual(self.article.prix_vente, 9999)
        self.assertEqual(self.inventaire.propositions.count(), 0)

    def test_page_de_validation_sans_proposition(self):
        """La page existe mais est vide : aucun impact pour les autres."""
        self.client.force_login(self.user_commercant)
        r = self.client.get(reverse(
            'inventory:valider_saisies_inventaire_boutique',
            args=[self.boutique.id, self.inventaire.id],
        ))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Aucune saisie en attente de validation')
