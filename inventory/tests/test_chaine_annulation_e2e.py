"""
Vérification fonctionnelle de BOUT EN BOUT de la chaîne « demande
d'annulation » (délai d'1 h dépassé), pour une facture ET pour un article :

  terminal MAUI (API)  →  refus initial (TIMEOUT)  →  demande EN_ATTENTE
  →  alerte back-office (badge + bandeau dashboard)  →  ACCORD (+1 h fixe)
  →  état MAUI (prolongation_active / peut_annuler)  →  annulation réelle
  →  stock restauré + vente/ligne annulée

Un 3e scénario vérifie le REFUS : la demande reste bloquée pour le terminal.

Chaque étape est affichée (print) pour lecture humaine et vérifiée par assertions.
"""
from decimal import Decimal

from django.test import RequestFactory
from django.urls import reverse

from inventory.context_processors import demandes_annulation
from inventory.models import DemandeAnnulationVente

from .test_demande_annulation import DemandeAnnulationBase


def _etape(n, titre, detail=""):
    print(f"\n  [{n}] {titre}" + (f"\n       {detail}" if detail else ""))


class ChaineAnnulationFactureE2ETest(DemandeAnnulationBase):
    """Facture entière : délai dépassé → demande → accord → annulation."""

    def test_chaine_complete_facture(self):
        self.web.force_login(self.user)
        stock_avant = self.article.quantite_stock  # 10
        vente = self._creer_vente(
            heures_ecoulees=2, articles=[(self.article, 2, Decimal('1000'))]
        )
        print(f"\n{'=' * 72}\nCHAÎNE FACTURE — {vente.numero_facture} (vente il y a 2 h)\n{'=' * 72}")

        # 1. Le serveur refuse l'annulation directe (délai 1 h dépassé)
        _etape(1, "MAUI tente l'annulation directe")
        r = self.api.post(
            self.url_annuler,
            data={'numero_facture': vente.numero_facture},
            content_type='application/json', **self.entete,
        )
        body = r.json()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(body['code'], 'CANCELLATION_TIMEOUT')
        self.assertTrue(body['demande_possible'])
        vente.refresh_from_db()
        self.assertFalse(vente.est_annulee)
        print(f"       ✔ 400 {body['code']} — demande_possible={body['demande_possible']}, "
              f"vente annulée={vente.est_annulee}")

        # 2. L'état dit au terminal que le bouton est bloqué
        _etape(2, "MAUI interroge l'état (réactivation du bouton)")
        body = self._etat(vente).json()
        self.assertTrue(body['delai_depasse'])
        self.assertFalse(body['peut_annuler'])
        self.assertFalse(body['prolongation_active'])
        print(f"       ✔ delai_depasse={body['delai_depasse']}, "
              f"peut_annuler={body['peut_annuler']} → popup « 📨 Demander »")

        # 3. Le terminal envoie la demande au commerçant
        _etape(3, "MAUI envoie la demande d'annulation")
        r = self._demander(vente, motif='Erreur de caisse')
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['demande']['statut'], 'EN_ATTENTE')
        self.assertEqual(body['prolongation_minutes'], 60)
        demande = DemandeAnnulationVente.objects.get(vente=vente)
        print(f"       ✔ 201 — demande #{demande.id} {demande.statut}, "
              f"motif « {demande.motif} », prolongation = {body['prolongation_minutes']} min")

        # 4. Le back-office affiche l'alerte (badge + bandeau)
        _etape(4, "Back-office : badge + bandeau du dashboard")
        request = RequestFactory().get('/')
        request.user = self.user
        ctx = demandes_annulation(request)
        self.assertEqual(ctx['demandes_annulation_count'], 1)
        r = self.web.get(reverse('inventory:commercant_dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "demande(s) d'annulation en attente")
        self.assertContains(r, vente.numero_facture)
        print(f"       ✔ badge = {ctx['demandes_annulation_count']} ; "
              f"bandeau + {vente.numero_facture} présents dans le dashboard")

        # 5. Le commerçant ACCORDE la prolongation (+1 h fixe)
        _etape(5, "Commerçant clique sur « Accorder »")
        r = self.web.post(
            reverse('inventory:accorder_extension_annulation', args=[self.boutique.id]),
            {'demande_id': demande.id},
        )
        self.assertEqual(r.status_code, 302)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, 'ACCEPTEE')
        self.assertEqual(demande.traite_par, self.user)
        self.assertEqual(demande.delai_accorde_minutes, 60)
        self.assertIsNotNone(demande.expire_le)
        print(f"       ✔ 302 — statut {demande.statut} par {demande.traite_par}, "
              f"+{demande.delai_accorde_minutes} min (expire le {demande.expire_le:%H:%M})")

        # 6. Le terminal voit la prolongation se réactiver
        _etape(6, "MAUI re-vérifie l'état avant d'annuler")
        body = self._etat(vente).json()
        self.assertTrue(body['prolongation_active'])
        self.assertTrue(body['peut_annuler'])
        self.assertGreater(body['minutes_restantes'], 0)
        print(f"       ✔ prolongation_active={body['prolongation_active']}, "
              f"peut_annuler={body['peut_annuler']}, "
              f"minutes_restantes={body['minutes_restantes']}")

        # 7. Idempotence : renvoyer la demande ne crée pas de doublon
        _etape(7, "MAUI renvoie une demande (idempotence)")
        r = self._demander(vente, motif='Erreur de caisse')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['deja_autorise'])
        self.assertEqual(
            DemandeAnnulationVente.objects.filter(vente=vente).count(), 1
        )
        print("       ✔ 200 deja_autorise=True — toujours 1 seule demande")

        # 8. L'annulation est désormais acceptée et restaure le stock
        _etape(8, "MAUI annule la facture (motif : erreur de caisse)")
        r = self.api.post(
            self.url_annuler,
            data={
                'numero_facture': vente.numero_facture,
                'motif': 'Erreur de caisse',
                'motif_code': 'ERREUR_COMMANDE',
            },
            content_type='application/json', **self.entete,
        )
        self.assertEqual(r.status_code, 200, r.content)
        vente.refresh_from_db()
        self.assertTrue(vente.est_annulee)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, stock_avant + 2)
        print(f"       ✔ 200 — vente annulée={vente.est_annulee}, "
              f"stock {stock_avant} → {self.article.quantite_stock} (+2 restaurés)")

        # 9. L'alerte disparaît du back-office
        _etape(9, "Back-office : l'alerte a disparu")
        r = self.web.get(reverse('inventory:commercant_dashboard'))
        self.assertNotContains(r, "demande(s) d'annulation en attente")
        print("       ✔ bandeau retiré (demande traitée)")


class ChaineAnnulationArticleE2ETest(DemandeAnnulationBase):
    """Un seul article : même chaîne, avec restauration partielle du total."""

    def test_chaine_complete_article(self):
        self.web.force_login(self.user)
        # Facture : Savon x2 (2 000) + Huile x1 (2 000) = 4 000
        vente = self._creer_vente(heures_ecoulees=2, articles=[
            (self.article, 2, Decimal('1000')),
            (self.article2, 1, Decimal('2000')),
        ])
        stock_huile_avant = self.article2.quantite_stock  # 5
        print(f"\n{'=' * 72}\nCHAÎNE ARTICLE — {vente.numero_facture} "
              f"(annulation de « {self.article2.nom} »)\n{'=' * 72}")
        self.assertEqual(vente.montant_total, Decimal('4000'))

        # 1. Refus direct (délai dépassé)
        _etape(1, "MAUI tente l'annulation directe de l'article")
        r = self.api.post(
            self.url_annuler_ligne,
            data={'numero_facture': vente.numero_facture, 'article_id': self.article2.id},
            content_type='application/json', **self.entete,
        )
        body = r.json()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(body['code'], 'CANCELLATION_TIMEOUT')
        print(f"       ✔ 400 {body['code']}")

        # 2. État de la ligne
        _etape(2, "MAUI interroge l'état de la ligne")
        body = self._etat(vente, 'LIGNE', self.article2).json()
        self.assertTrue(body['delai_depasse'])
        self.assertFalse(body['peut_annuler'])
        self.assertFalse(body['ligne_annulee'])
        print(f"       ✔ delai_depasse={body['delai_depasse']}, "
              f"ligne_annulee={body['ligne_annulee']}")

        # 3. Demande pour CET article
        _etape(3, "MAUI envoie la demande (type LIGNE)")
        r = self._demander(vente, 'LIGNE', self.article2, motif='Mauvais article')
        self.assertEqual(r.status_code, 201)
        demande = DemandeAnnulationVente.objects.get(vente=vente)
        self.assertEqual(demande.type_demande, 'LIGNE')
        self.assertEqual(demande.ligne.article, self.article2)
        self.assertEqual(demande.article_nom, 'Huile')
        print(f"       ✔ 201 — demande #{demande.id} {demande.type_demande} "
              f"« {demande.article_nom} »")

        # 4. Badge back-office
        _etape(4, "Back-office : alerte visible")
        r = self.web.get(reverse('inventory:commercant_dashboard'))
        self.assertContains(r, "demande(s) d'annulation en attente")
        self.assertContains(r, vente.numero_facture)
        print("       ✔ bandeau + numéro de facture affichés")

        # 5. Accord
        _etape(5, "Commerçant accorde la prolongation")
        r = self.web.post(
            reverse('inventory:accorder_extension_annulation', args=[self.boutique.id]),
            {'demande_id': demande.id},
        )
        self.assertEqual(r.status_code, 302)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, 'ACCEPTEE')
        print(f"       ✔ statut {demande.statut} (+{demande.delai_accorde_minutes} min)")

        # 6. État débloqué pour la ligne
        _etape(6, "MAUI re-vérifie l'état de la ligne")
        body = self._etat(vente, 'LIGNE', self.article2).json()
        self.assertTrue(body['prolongation_active'])
        self.assertTrue(body['peut_annuler'])
        print(f"       ✔ prolongation_active={body['prolongation_active']}, "
              f"peut_annuler={body['peut_annuler']}")

        # 7. Annulation réelle de l'article
        _etape(7, "MAUI annule l'article (motif : erreur de commande)")
        r = self.api.post(
            self.url_annuler_ligne,
            data={
                'numero_facture': vente.numero_facture,
                'article_id': self.article2.id,
                'motif': 'Erreur de commande',
                'motif_code': 'ERREUR_COMMANDE',
            },
            content_type='application/json', **self.entete,
        )
        self.assertEqual(r.status_code, 200, r.content)
        vente.refresh_from_db()
        self.article2.refresh_from_db()
        self.article.refresh_from_db()
        ligne_huile = vente.lignes.get(article=self.article2)
        ligne_savon = vente.lignes.get(article=self.article)
        self.assertTrue(ligne_huile.est_annulee)
        self.assertFalse(ligne_savon.est_annulee)  # l'autre article reste valide
        self.assertEqual(vente.montant_total, Decimal('2000'))  # 4 000 - 2 000
        self.assertEqual(self.article2.quantite_stock, stock_huile_avant + 1)
        print(f"       ✔ 200 — ligne « Huile » annulée={ligne_huile.est_annulee}, "
              f"ligne « Savon » intacte={not ligne_savon.est_annulee}\n"
              f"       ✔ total {Decimal('4000')} → {vente.montant_total}, "
              f"stock Huile {stock_huile_avant} → {self.article2.quantite_stock}")


class ChaineAnnulationRefuseeE2ETest(DemandeAnnulationBase):
    """Refus du commerçant : le terminal reste bloqué."""

    def test_refus_bloque_l_annulation(self):
        self.web.force_login(self.user)
        vente = self._creer_vente(heures_ecoulees=2)
        print(f"\n{'=' * 72}\nCHAÎNE REFUS — {vente.numero_facture}\n{'=' * 72}")

        _etape(1, "MAUI envoie la demande")
        r = self._demander(vente, motif='Essai')
        self.assertEqual(r.status_code, 201)
        demande = DemandeAnnulationVente.objects.get(vente=vente)

        _etape(2, "Commerçant REFUSE la demande")
        r = self.web.post(
            reverse('inventory:refuser_demande_annulation', args=[self.boutique.id]),
            {'demande_id': demande.id, 'reponse': 'Vente trop ancienne'},
        )
        self.assertEqual(r.status_code, 302)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, 'REFUSEE')
        self.assertEqual(demande.reponse, 'Vente trop ancienne')
        print(f"       ✔ statut {demande.statut} — réponse « {demande.reponse} »")

        _etape(3, "MAUI re-vérifie l'état : toujours bloqué")
        body = self._etat(vente).json()
        self.assertFalse(body['prolongation_active'])
        self.assertFalse(body['peut_annuler'])
        self.assertEqual(body['demande']['statut'], 'REFUSEE')
        print(f"       ✔ peut_annuler={body['peut_annuler']}, "
              f"prolongation_active={body['prolongation_active']}")

        _etape(4, "MAUI tente l'annulation : refusée par le serveur")
        r = self.api.post(
            self.url_annuler,
            data={'numero_facture': vente.numero_facture},
            content_type='application/json', **self.entete,
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'CANCELLATION_TIMEOUT')
        vente.refresh_from_db()
        self.assertFalse(vente.est_annulee)
        print(f"       ✔ 400 CANCELLATION_TIMEOUT — vente annulée={vente.est_annulee}")

        _etape(5, "Back-office : plus d'alerte après traitement")
        r = self.web.get(reverse('inventory:commercant_dashboard'))
        self.assertNotContains(r, "demande(s) d'annulation en attente")
        print("       ✔ bandeau retiré (demande traitée)")
