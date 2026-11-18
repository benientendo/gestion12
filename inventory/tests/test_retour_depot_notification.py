"""
Alerte côté client (MAUI) quand un article est retourné au dépôt
===============================================================

« Quand on retourne un article **déjà validé**, le client doit avoir une
notification claire. »

Jusqu'ici le terminal ne recevait qu'une « Synchronisation nécessaire »
générique (+ un « Stock mis à jour » trompeur quand le stock n'avait pas
bougé). Le retour envoie maintenant un événement dédié ``retour_depot``
(WebSocket + push FCM) qui distingue explicitement :

- ``quantite_validee`` : la part **déjà validée/reçue** au point de vente
  → le stock diminue réellement ;
- ``quantite_annulee`` : la part encore **en attente de réception** →
  simplement annulée (aucun stock touché).

Vérifié ici :
- ``notify_retour_depot`` : message WS sur ``boutique_<id>`` + push FCM
  au titre explicite, corps distinguant les deux parts, référence incluse ;
- la vue de retour appelle bien l'alerte avec les deux parts (cas déjà
  validé, cas réception annulée, cas mixte) ;
- l'ancien ``sync_required`` reste envoyé : les versions déjà déployées
  de l'app continuent de se synchroniser (aucune rupture) ;
- le consumer WebSocket relaye bien tous les champs au terminal.
"""
import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from inventory.consumers import BoutiqueConsumer
from inventory.models import (
    Article, Boutique, Commercant, FactureApprovisionnement,
    LigneApprovisionnement, TransfertStock,
)
from inventory.websocket_utils import notify_retour_depot

User = get_user_model()


class _LayerWebSocket:
    """Couche de canaux factice : mémorise les group_send (async)."""

    def __init__(self):
        self.messages = []

    async def group_send(self, group, message):
        self.messages.append((group, message))


# ---------------------------------------------------------------------------
# Le helper lui-même
# ---------------------------------------------------------------------------

class NotifyRetourDepotTest(SimpleTestCase):

    def _appels_fcm(self, mock_push):
        """Pushs FCM au titre « Retour au dépôt » (les autres notifs du
        même retour ont des titres différents)."""
        return [
            c for c in mock_push.call_args_list
            if 'Retour au dépôt' in (c.args[1] if len(c.args) > 1 else '')
        ]

    def test_push_fcm_explicite_sur_article_deja_valide(self):
        with patch('inventory.websocket_utils._push_fcm') as push:
            notify_retour_depot(
                boutique_id=7, article_id=12, article_nom='Coca',
                quantite=20, depot_nom='Dépôt Central', stock_apres=130,
                quantite_validee=20, quantite_annulee=0,
                reference='RETOUR-42',
            )

        appels = self._appels_fcm(push)
        self.assertEqual(len(appels), 1)
        _, titre, corps, kwargs = (
            appels[0].args[0], appels[0].args[1], appels[0].args[2],
            appels[0].kwargs,
        )
        self.assertIn('Retour au dépôt', titre)
        self.assertIn('Coca', titre)
        # Les deux parts sont distinguées dans le corps
        self.assertIn('20 x Coca retourné(s) au dépôt Dépôt Central', corps)
        self.assertIn('20 unité(s) déjà validée(s) ici', corps)
        self.assertIn('stock passé à 130', corps)
        self.assertNotIn('annulée', corps)
        self.assertIn('RETOUR-42', corps)
        self.assertEqual(kwargs['data']['type'], 'retour_depot')
        self.assertEqual(kwargs['data']['reference'], 'RETOUR-42')

    def test_push_fcm_signale_la_reception_annulee(self):
        with patch('inventory.websocket_utils._push_fcm') as push:
            notify_retour_depot(
                boutique_id=7, article_id=12, article_nom='Coca',
                quantite=20, depot_nom='Dépôt Central', stock_apres=0,
                quantite_validee=0, quantite_annulee=20,
                reference='RETOUR-ABCD1234',
            )

        _, titre, corps, _ = (
            push.call_args.args[0], push.call_args.args[1],
            push.call_args.args[2], push.call_args.kwargs,
        )
        self.assertIn('Retour au dépôt', titre)
        self.assertIn('20 unité(s) en attente de réception annulée(s)', corps)
        self.assertNotIn('déjà validée', corps)
        self.assertNotIn('stock passé à', corps)   # le stock n'a pas bougé

    def test_websocket_sur_le_groupe_de_la_boutique(self):
        layer = _LayerWebSocket()
        with patch(
            'inventory.websocket_utils.get_channel_layer', return_value=layer,
        ):
            notify_retour_depot(
                boutique_id=7, article_id=12, article_nom='Coca',
                quantite=20, depot_nom='Dépôt Central', stock_apres=130,
                quantite_validee=12, quantite_annulee=8,
                reference='RETOUR-42',
            )

        self.assertEqual(len(layer.messages), 1)
        groupe, message = layer.messages[0]
        self.assertEqual(groupe, 'boutique_7')
        self.assertEqual(message['type'], 'retour_depot')
        self.assertEqual(message['reference'], 'RETOUR-42')
        self.assertEqual(message['quantite'], 20)
        self.assertEqual(message['quantite_validee'], 12)
        self.assertEqual(message['quantite_annulee'], 8)
        self.assertEqual(message['stock_apres'], 130)
        self.assertEqual(message['depot_nom'], 'Dépôt Central')

    def test_echec_websocket_n_empeche_pas_le_push(self):
        """Best effort : le push part même si la couche de canaux casse."""
        layer = _LayerWebSocket()

        async def _casse(group, message):
            raise RuntimeError('canaux KO')

        layer.group_send = _casse
        with patch(
            'inventory.websocket_utils.get_channel_layer', return_value=layer,
        ), patch('inventory.websocket_utils._push_fcm') as push:
            notify_retour_depot(
                boutique_id=7, article_id=12, article_nom='Coca',
                quantite=5, depot_nom='Dépôt Central', stock_apres=0,
                quantite_validee=5, reference='RETOUR-42',
            )

        self.assertEqual(len(self._appels_fcm(push)), 1)


# ---------------------------------------------------------------------------
# Consumer : ce que reçoit réellement le terminal
# ---------------------------------------------------------------------------

class ConsumerRetourDepotTest(SimpleTestCase):

    def test_le_handler_reenvoie_tous_les_champs(self):
        from unittest.mock import AsyncMock
        consommateur = BoutiqueConsumer()
        consommateur.send = AsyncMock()

        event = {
            'type': 'retour_depot',
            'reference': 'RETOUR-42',
            'article_id': 12,
            'article_nom': 'Coca',
            'quantite': 20,
            'quantite_validee': 20,
            'quantite_annulee': 0,
            'stock_apres': 130,
            'depot_nom': 'Dépôt Central',
        }
        async_to_sync(consommateur.retour_depot)(event)

        consommateur.send.assert_awaited_once()
        payload = json.loads(consommateur.send.call_args.kwargs['text_data'])
        self.assertEqual(payload['type'], 'retour_depot')
        for cle in ('reference', 'article_id', 'article_nom', 'quantite',
                    'quantite_validee', 'quantite_annulee', 'stock_apres',
                    'depot_nom'):
            self.assertEqual(payload[cle], event[cle])
        self.assertIn('timestamp', payload)


# ---------------------------------------------------------------------------
# Intégration : la vue de retour déclenche bien l'alerte
# ---------------------------------------------------------------------------

class AlerteRetourCoteClientTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='al_comm', password='x', email='al_comm@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='AL SARL', nom_responsable='AL',
            email='al_comm@test.cd', user=self.user,
        )
        self.depot = Boutique.objects.create(
            nom='Dépôt AL', commercant=self.commercant,
            code_boutique='BT-AL-D', est_depot=True,
        )
        self.pdv = Boutique.objects.create(
            nom='PDV AL', commercant=self.commercant, code_boutique='BT-AL-P',
        )
        self.article = Article.objects.create(
            boutique=self.depot, code='AL-ART', nom='Article AL',
            prix_vente=Decimal('1500'), quantite_stock=200,
        )
        self.facture = FactureApprovisionnement.objects.create(
            numero_facture='F-AL-001', depot=self.depot,
            date_facture=date.today(), devise='CDF', created_by='al_comm',
        )
        LigneApprovisionnement.objects.create(
            facture=self.facture, article=self.article,
            quantite_unites=150, prix_achat_unitaire=100,
            prix_vente_unitaire=1500,
        )
        self.facture.calculer_montant_total()

        transfert = TransfertStock.objects.create(
            article=self.article, depot_source=self.depot,
            boutique_destination=self.pdv, quantite=150,
            effectue_par='al_comm', statut='EN_ATTENTE',
        )
        transfert.valider_transfert('al_comm')
        self.transfert = transfert
        self.article_pdv = Article.objects.get(boutique=self.pdv, code='AL-ART')

        self.client.force_login(self.user)
        self.url = reverse(
            'inventory:retourner_article_au_depot', args=[self.pdv.id],
        )

    def _post(self, quantite=20, **extra):
        data = {
            'article_id': self.article_pdv.id,
            'quantite': quantite,
            'depot_id': self.depot.id,
        }
        data.update(extra)
        return self.client.post(self.url, data)

    def _retours(self, mock_push):
        """Les pushes « Retour au dépôt » émis pendant le POST."""
        return [
            {
                'boutique': c.args[0],
                'titre': c.args[1],
                'corps': c.args[2],
                'data': c.kwargs.get('data') or {},
            }
            for c in mock_push.call_args_list
            if 'Retour au dépôt' in (c.args[1] if len(c.args) > 1 else '')
        ]

    def _reception_maui(self, quantite):
        """Validation côté terminal : le stock du PDV est crédité."""
        self.article_pdv.quantite_stock = (
            (self.article_pdv.quantite_stock or 0) + quantite
        )
        self.article_pdv.quantite_envoyee = 0
        self.article_pdv.save(update_fields=['quantite_stock', 'quantite_envoyee'])

    def test_article_deja_valide_alerte_le_client(self):
        """Le stock du PDV a déjà été crédité : l'alerte le dit."""
        self._reception_maui(150)

        with patch('inventory.websocket_utils._push_fcm') as push:
            r = self._post(20)

        self.assertEqual(r.status_code, 200, r.content)
        retours = self._retours(push)
        self.assertEqual(len(retours), 1)
        alerte = retours[0]
        self.assertEqual(alerte['boutique'], self.pdv.id)
        self.assertIn('Article AL', alerte['titre'])
        self.assertIn('20 unité(s) déjà validée(s) ici', alerte['corps'])
        self.assertIn('stock passé à 130', alerte['corps'])
        self.assertNotIn('annulée', alerte['corps'])
        self.assertTrue(alerte['data']['reference'].startswith('RETOUR-'))
        self.assertEqual(alerte['data']['quantite_validee'], '20')

    def test_reception_encore_en_attente_signalee_comme_annulee(self):
        """Aucune validation MAUI : la part est « annulée », pas « validée »."""
        self.assertEqual(self.article_pdv.quantite_envoyee, 150)
        self.assertEqual(self.article_pdv.quantite_stock, 0)

        with patch('inventory.websocket_utils._push_fcm') as push:
            r = self._post(20)

        self.assertEqual(r.status_code, 200, r.content)
        alerte = self._retours(push)[0]
        self.assertIn('20 unité(s) en attente de réception annulée(s)',
                      alerte['corps'])
        self.assertNotIn('déjà validée', alerte['corps'])
        self.assertEqual(alerte['data']['quantite_validee'], '0')
        self.assertEqual(alerte['data']['quantite_annulee'], '20')

    def test_retour_mixte_les_deux_parts_dans_le_meme_message(self):
        """10 en attente + 50 en stock : 30 retournés = 10 annulés + 20 validés."""
        self.article_pdv.quantite_stock = 50
        self.article_pdv.quantite_envoyee = 10
        self.article_pdv.save(update_fields=['quantite_stock', 'quantite_envoyee'])

        with patch('inventory.websocket_utils._push_fcm') as push:
            r = self._post(30)

        self.assertEqual(r.status_code, 200, r.content)
        alerte = self._retours(push)[0]
        self.assertIn('10 unité(s) en attente de réception annulée(s)',
                      alerte['corps'])
        self.assertIn('20 unité(s) déjà validée(s) ici', alerte['corps'])
        self.assertEqual(alerte['data']['quantite_validee'], '20')
        self.assertEqual(alerte['data']['quantite_annulee'], '10')

    def test_websocket_et_sync_toujours_envoyes(self):
        """L'événement dédié part en WS, et l'ancien sync_required est
        conservé pour les versions déjà déployées de l'app (aucune rupture)."""
        layer = _LayerWebSocket()
        with patch(
            'inventory.websocket_utils.get_channel_layer', return_value=layer,
        ), patch('inventory.websocket_utils._push_fcm'):
            r = self._post(20)

        self.assertEqual(r.status_code, 200, r.content)
        types = [m['type'] for _, m in layer.messages]
        self.assertIn('retour_depot', types)
        self.assertIn('sync_required', types)
        self.assertIn('stock_updated', types)

        retour = next(m for _, m in layer.messages if m['type'] == 'retour_depot')
        self.assertEqual(retour['quantite'], 20)
        self.assertEqual(retour['article_nom'], 'Article AL')
        self.assertEqual(retour['depot_nom'], 'Dépôt AL')
        self.assertTrue(retour['reference'].startswith('RETOUR-'))

    def test_aucune_alerte_si_le_retour_est_refuse(self):
        with patch('inventory.websocket_utils._push_fcm') as push:
            r = self._post(9999)

        self.assertEqual(r.status_code, 409)
        self.assertEqual(self._retours(push), [])

    def _pushs_stock(self, push, article_id):
        return [
            c for c in push.call_args_list
            if (c.kwargs.get('data') or {}).get('type') == 'stock_updated'
            and (c.kwargs.get('data') or {}).get('article_id') == article_id
        ]

    def test_push_stock_trompeur_si_le_stock_n_bouge_pas(self):
        """Réception encore en attente : le stock du PDV est inchangé —
        pas de push « Le stock est passé à X » qui contredirait l'alerte."""
        self.assertEqual(self.article_pdv.quantite_stock, 0)

        with patch('inventory.websocket_utils._push_fcm') as push:
            r = self._post(20)

        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(self._pushs_stock(push, self.article_pdv.id), [])

    def test_push_stock_quand_le_stock_diminue_reellement(self):
        """Article déjà validé : le vrai nouveau stock est bien poussé."""
        self._reception_maui(150)

        with patch('inventory.websocket_utils._push_fcm') as push:
            r = self._post(20)

        self.assertEqual(r.status_code, 200, r.content)
        maj = self._pushs_stock(push, self.article_pdv.id)
        self.assertEqual(len(maj), 1)
        self.assertEqual(maj[0].kwargs['data']['new_stock'], 130)
