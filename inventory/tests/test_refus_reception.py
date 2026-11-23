"""
Refus de réception par un terminal MAUI : la marchandise revient à l'expéditeur
=============================================================================

« Si un terminal effectue le transfert (MAUI) vers un autre terminal (MAUI)
et que la destination REFUSE, quel est le comportement ? Les quantités
refusées retournent-elles sur le point qui envoie ? »

AVANT : le refus faisait ``quantite_envoyee = 0`` et ``est_valide_client =
True`` côté destination — et RIEN d'autre. La source avait déjà été débitée
par ``valider_transfert`` (SORTIE + mouvement ``TRANSFERT-<id>``) : les
unités refusées disparaissaient du système, sans aucun mouvement de retour
et sans que l'expéditeur soit jamais prévenu (le WebSocket partait vers la
destination seulement).

MAINTENANT : le refus recrédite la source
  - source  : ``quantite_stock`` +quantite, mouvement ENTREE
    ``RETOUR-<transfert_id>`` (mêmes références que le retour d'excédent,
    cf. inventory/distribution.py) ;
  - faits   : les segments du lot sont annulés (LIFO) → la facture source
    perd la quantité « distribuée » ;
  - destination : ``quantite_envoyee`` vidé, ``est_valide_client=True``
    (aucun stock ajouté ici) ;
  - DEUX terminaux notifiés (``refus_reception`` WS + push FCM) ;
  - l'historique affiche « Refusé » (``TransfertStock.date_refus``).

Vérifié ici :
- le stock de la source est recrédité et un ENTREE ``RETOUR-<id>`` est
  écrit, le stock de la destination n'est PAS touché ;
- les badges de distribution reviennent à 0 (facture recréditée) ;
- seul le lot ENCORE EN ATTENTE est recrédité (un lot déjà reçu et revendu
  ne l'est pas) ;
- aucun double recrédit (double clic, ou refus + retour d'excédent) ;
- un stock déclaré depuis le back-office (aucun transfert) n'est pas
  recrédité — la réponse le dit (``quantite_sans_lot``) ;
- l'expéditeur ET la destination sont notifiés ;
- l'historique MAUI affiche « Refusé » ;
- un retour d'excédent ultérieur sur ce lot est refusé (409).
"""
import json
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from inventory.consumers import BoutiqueConsumer
from inventory.distribution import etat_distribution
from inventory.models import (
    Article, Boutique, Client, Commercant, FactureApprovisionnement,
    LigneApprovisionnement, MouvementStock, TransfertStock,
)

User = get_user_model()


class RefusReceptionBase(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='ref_comm', password='x', email='ref_comm@test.cd',
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='REF SARL', nom_responsable='REF',
            email='ref_comm@test.cd', user=self.user,
        )
        self.depot = Boutique.objects.create(
            nom='Dépôt REF', commercant=self.commercant,
            code_boutique='BT-REF-D', est_depot=True,
        )
        self.pdv = Boutique.objects.create(
            nom='PDV REF', commercant=self.commercant,
            code_boutique='BT-REF-P',
        )
        self.terminal = Client.objects.create(
            compte_proprietaire=self.user, boutique=self.pdv,
            nom_terminal='Terminal PDV', numero_serie='SER-REF-001',
        )

        # Article du dépôt (source du transfert)
        self.article = Article.objects.create(
            boutique=self.depot, code='REF-ART', nom='Article REF',
            prix_vente=Decimal('1500'), quantite_stock=200,
            est_actif=True, est_valide_client=True,
        )
        # Facture du dépôt : ligne de 150 (badges de distribution)
        self.facture = FactureApprovisionnement.objects.create(
            numero_facture='F-REF-001', depot=self.depot,
            date_facture=date.today(), devise='CDF', created_by='ref_comm',
        )
        self.ligne = LigneApprovisionnement.objects.create(
            facture=self.facture, article=self.article,
            quantite_unites=150, prix_achat_unitaire=100,
            prix_vente_unitaire=1500,
        )
        self.facture.calculer_montant_total()

        self.api = APIClient()
        self.client.force_login(self.user)

    # -- helpers ----------------------------------------------------------

    def _transfert(self, quantite=150, statut='EN_ATTENTE', reference_lot='LOT-REF'):
        transfert = TransfertStock.objects.create(
            article=self.article, depot_source=self.depot,
            boutique_destination=self.pdv, quantite=quantite,
            effectue_par='ref_comm', statut=statut,
            reference_lot=reference_lot,
        )
        if statut == 'EN_ATTENTE':
            transfert.valider_transfert('ref_comm')
        return transfert

    def _refuser(self, article=None):
        article = article or self.article_pdv
        # Le middleware /api/v2/simple/ exige le numéro de série du terminal
        return self.api.post(
            reverse('api_v2_simple:refuser_article'),
            {'article_id': article.id, 'boutique_id': self.pdv.id},
            format='json',
            HTTP_X_DEVICE_SERIAL='SER-REF-001',
        )

    @property
    def article_pdv(self):
        return Article.objects.get(boutique=self.pdv, code='REF-ART')

    def _mvt_retour_source(self):
        return MouvementStock.objects.filter(
            article=self.article, type_mouvement='ENTREE',
            reference_document__startswith='RETOUR-',
        )

    def _distribue(self):
        self.facture.refresh_from_db()
        _, par_ligne = etat_distribution([self.facture])
        return par_ligne[self.ligne.id]['distribue']


class RefusReceptionSuccesTest(RefusReceptionBase):

    def test_la_source_est_creditee(self):
        """150 envoyés puis refusés : le dépôt repasse à 200, la destination
        à 0 en stock ET 0 en attente."""
        transfert = self._transfert(150)
        self.article_pdv  # crée l'article côté destination
        self.assertEqual(self.article.quantite_stock, 50)      # débité
        self.assertEqual(self.article_pdv.quantite_envoyee, 150)
        self.assertEqual(self.article_pdv.quantite_stock, 0)

        r = self._refuser()
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['quantite_refusee'], 150)
        self.assertEqual(data['quantite_returenee'], 150)
        self.assertEqual(data['quantite_sans_lot'], 0)
        self.assertEqual(data['source_nom'], 'Dépôt REF')

        self.article.refresh_from_db()
        pdv = self.article_pdv
        self.assertEqual(self.article.quantite_stock, 200)     # recrédité
        self.assertEqual(pdv.quantite_stock, 0)                # jamais touché
        self.assertEqual(pdv.quantite_envoyee, 0)
        self.assertTrue(pdv.est_valide_client)

        mv = self._mvt_retour_source().get()
        self.assertEqual(mv.quantite, 150)
        self.assertEqual(mv.reference_document, f'RETOUR-{transfert.id}')
        self.assertEqual(mv.stock_avant, 50)
        self.assertEqual(mv.stock_apres, 200)

        # La destination n'a AUCUN mouvement : rien n'y était jamais entré
        self.assertFalse(
            MouvementStock.objects.filter(
                article__boutique=self.pdv,
                reference_document__startswith='RETOUR-',
            ).exists(),
        )

    def test_badges_distribution_annules(self):
        """150 distribués (TOUT) → 0 après refus (AUCUN) : la facture source
        est bien recréditée par le refus."""
        self._transfert(150)
        self.assertEqual(self._distribue(), 150)

        r = self._refuser()
        self.assertEqual(r.status_code, 200, r.content)

        self.assertEqual(self._distribue(), 0)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.etat['distribue'], 0)
        self.assertEqual(self.facture.etat['restant'], 150)

    def test_seul_le_lot_en_attente_est_credite(self):
        """Lot A reçu puis revendu, lot B en attente : le refus ne touche
        QUE le lot B — on ne recrédite jamais un lot déjà consommé."""
        lot_a = self._transfert(150)
        pdv = self.article_pdv
        # Réception MAUI du lot A : le stock du PDV est crédité
        pdv.quantite_stock = 150
        pdv.quantite_envoyee = 0
        pdv.est_valide_client = True
        pdv.save()
        # Lot B plus récent, encore en attente
        lot_b = self._transfert(40)

        pdv.refresh_from_db()
        self.assertEqual(pdv.quantite_envoyee, 40)

        r = self._refuser()
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertEqual(data['quantite_returenee'], 40)

        references = set(
            self._mvt_retour_source().values_list('reference_document', flat=True)
        )
        self.assertEqual(references, {f'RETOUR-{lot_b.id}'})

        lot_a.refresh_from_db()
        lot_b.refresh_from_db()
        self.assertIsNone(lot_a.date_refus)
        self.assertIsNotNone(lot_b.date_refus)

    def test_deux_lots_en_attente_tous_credites(self):
        self._transfert(150)
        self._transfert(40)
        pdv = self.article_pdv
        self.assertEqual(pdv.quantite_envoyee, 190)

        r = self._refuser()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['quantite_returenee'], 190)
        self.assertEqual(self._mvt_retour_source().count(), 2)
        self.assertEqual(self._distribue(), 0)

    def test_double_refus_acun_double_credite(self):
        """Double clic sur « Refuser » : la seconde requête ne réécrit rien."""
        self._transfert(150)
        self.assertEqual(self._refuser().status_code, 200)

        r = self._refuser()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['already_refused'])

        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 200)     # pas 250/350
        self.assertEqual(self._mvt_retour_source().count(), 1)

    def test_refus_sans_transfert_n_ecrit_rien(self):
        """Stock déclaré directement depuis le back-office : aucun point n'a
        été débité, donc rien à recréditer — la réponse le dit."""
        pdv = Article.objects.create(
            boutique=self.pdv, code='SANS-TRANSFERT', nom='Sans transfert',
            prix_vente=Decimal('500'), quantite_stock=0,
            est_actif=True, est_valide_client=False, quantite_envoyee=25,
        )

        r = self._refuser(pdv)
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['quantite_refusee'], 25)
        self.assertEqual(data['quantite_returenee'], 0)
        self.assertEqual(data['quantite_sans_lot'], 25)

        pdv.refresh_from_db()
        self.assertEqual(pdv.quantite_envoyee, 0)
        self.assertTrue(pdv.est_valide_client)
        self.assertEqual(self._mvt_retour_source().count(), 0)

    def test_article_deja_valide_sans_attente(self):
        """Déjà validé, rien en attente : pas de réécriture ni de notification."""
        self._transfert(150)
        pdv = self.article_pdv
        pdv.quantite_stock = 150
        pdv.quantite_envoyee = 0
        pdv.est_valide_client = True
        pdv.save()

        r = self._refuser()
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['already_refused'])
        self.assertEqual(self._mvt_retour_source().count(), 0)

    def test_appariement_par_nom_meme_code_different(self):
        """L'article source et l'article de destination peuvent porter des
        codes différents : l'appariement se fait aussi par nom."""
        autre_code = Article.objects.create(
            boutique=self.pdv, code='AUTRE-CODE', nom='Article REF',
            prix_vente=Decimal('1500'), quantite_stock=0,
            est_actif=True, est_valide_client=False,
        )
        TransfertStock.objects.create(
            article=self.article, depot_source=self.depot,
            boutique_destination=self.pdv, quantite=30,
            effectue_par='ref_comm', statut='EN_ATTENTE',
        ).valider_transfert('ref_comm')

        # La destination a déjà « Article REF » sous un autre code :
        # valider_transfert l'a reutilisé (règle nom).
        autre_code.refresh_from_db()
        self.assertEqual(autre_code.quantite_envoyee, 30)

        r = self._refuser(autre_code)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['quantite_returenee'], 30)


class RefusReceptionEtRetourTest(RefusReceptionBase):
    """Interactions avec le retour d'excédent déjà en production."""

    def test_retour_ulterieur_sur_lot_refuse_bloque(self):
        transfert = self._transfert(150)
        self.assertEqual(self._refuser().status_code, 200)

        r = self.client.post(
            reverse('inventory:retourner_article_au_depot', args=[self.pdv.id]),
            {'article_id': self.article_pdv.id, 'quantite': 1,
             'depot_id': self.depot.id, 'transfert_id': transfert.id},
        )
        self.assertEqual(r.status_code, 409, r.content)
        # Aucun recrédit supplémentaire
        self.assertEqual(self._mvt_retour_source().count(), 1)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 200)

    def test_retour_d_excedent_partiel_puis_refus(self):
        """Retour d'excédent de 100 sur 150, puis refus du reste : le refus
        ne recrédite QUE ce qui n'a pas encore été recrédité."""
        transfert = self._transfert(150)
        self.article_pdv  # crée l'article destination

        r = self.client.post(
            reverse('inventory:retourner_article_au_depot', args=[self.pdv.id]),
            {'article_id': self.article_pdv.id, 'quantite': 100,
             'depot_id': self.depot.id, 'transfert_id': transfert.id},
        )
        self.assertEqual(r.status_code, 200, r.content)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 150)   # 50 + 100

        r = self._refuser()
        self.assertEqual(r.status_code, 200, r.content)
        # Le refus ne remet que les 50 unités encore « distribuées »
        self.assertEqual(r.json()['quantite_returenee'], 50)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 200)


class RefusReceptionNotificationsTest(RefusReceptionBase):

    def test_les_deux_boutiques_sont_notifiees(self):
        self._transfert(150)

        with patch(
            'inventory.websocket_utils.notify_refus_reception',
        ) as refus, patch(
            'inventory.websocket_utils.notify_stock_updated',
        ) as stock, patch(
            'inventory.websocket_utils.notify_sync_required',
        ) as sync, patch(
            'inventory.websocket_utils.notify_article_updated',
        ) as art, patch(
            'inventory.websocket_utils._push_fcm',
        ):
            r = self._refuser()
        self.assertEqual(r.status_code, 200, r.content)

        # L'EXPÉDITEUR est enfin prévenu (il ne l'était jamais avant)
        refus.assert_called_once()
        args = refus.call_args.args
        kwargs = refus.call_args.kwargs
        self.assertEqual(args[0], self.depot.id)      # source
        self.assertEqual(args[2], self.pdv.id)        # destination
        self.assertEqual(args[6], 150)                # quantité
        self.assertEqual(kwargs['stock_source'], 200)
        self.assertTrue(str(kwargs['reference']).startswith('RETOUR-'))

        # Le stock de la source est poussé en WebSocket (sans push redondant)
        stock.assert_called_once()
        self.assertEqual(stock.call_args.args[0], self.depot.id)
        self.assertFalse(stock.call_args.kwargs.get('push_fcm', True))

        # Les deux côtés reçoivent aussi un motif de synchro
        synchros = [c.args[0] for c in sync.call_args_list]
        self.assertIn(self.pdv.id, synchros)
        self.assertIn(self.depot.id, synchros)

        # Le catalogue de la destination reste synchronisé
        art.assert_called_once()

    def test_push_fcm_explicite_des_deux_cotes(self):
        self._transfert(150)
        with patch('inventory.websocket_utils._push_fcm') as push:
            r = self._refuser()
        self.assertEqual(r.status_code, 200, r.content)

        titres = [c.args[1] for c in push.call_args_list]
        self.assertTrue(
            any('Retour refusé' in t for t in titres),
            titres,
        )
        self.assertTrue(
            any('Réception refusée' in t for t in titres),
            titres,
        )
        corps_source = next(
            c.args[2] for c in push.call_args_list
            if 'Retour refusé' in c.args[1]
        )
        self.assertIn('150 x Article REF refusé(s) par PDV REF', corps_source)
        self.assertIn('Stock source passé à 200', corps_source)

    def test_helper_websocket_sur_les_deux_groupes(self):
        from inventory.websocket_utils import notify_refus_reception

        class Layer:
            def __init__(self):
                self.messages = []

            async def group_send(self, group, message):
                self.messages.append((group, message))

        layer = Layer()
        with patch(
            'inventory.websocket_utils.get_channel_layer', return_value=layer,
        ), patch('inventory.websocket_utils._push_fcm'):
            notify_refus_reception(
                11, 'Dépôt', 22, 'Boutique', 5, 'Article',
                30, stock_source=170, reference='RETOUR-9',
            )

        groupes = sorted(g for g, _ in layer.messages)
        self.assertEqual(groupes, ['boutique_11', 'boutique_22'])
        roles = sorted(m['role'] for _, m in layer.messages)
        self.assertEqual(roles, ['destination', 'source'])
        for _, message in layer.messages:
            self.assertEqual(message['type'], 'refus_reception')
            self.assertEqual(message['quantite'], 30)
            self.assertEqual(message['reference'], 'RETOUR-9')


class RefusReceptionHistoriqueTest(RefusReceptionBase):

    def _historique(self, numero_serie='SER-REF-001'):
        return self.api.get(
            reverse('api_maui_desktop:historique_transferts_maui'),
            HTTP_X_DEVICE_SERIAL=numero_serie,
        )

    def test_historique_affiche_refuse(self):
        transfert = self._transfert(150)

        r = self._historique()
        self.assertEqual(r.status_code, 200, r.content)
        lot = r.json()['transferts'][0]
        self.assertEqual(lot['statut'], 'VALIDE')       # pas de rupture de filtre
        self.assertEqual(lot['statut_libelle'], 'Validé')
        self.assertFalse(lot['refuse'])

        self.assertEqual(self._refuser().status_code, 200)

        r = self._historique()
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        lot = data['transferts'][0]
        self.assertEqual(lot['statut'], 'VALIDE')
        self.assertEqual(lot['statut_libelle'], 'Refusé')
        self.assertTrue(lot['refuse'])
        self.assertTrue(lot['date_refus'])
        self.assertEqual(data['stats']['refuses'], 1)
        self.assertEqual(data['stats']['valides'], 0)
        transfert.refresh_from_db()
        self.assertIsNotNone(transfert.date_refus)

    def test_historique_refus_partiel(self):
        """Lot à deux lignes dont une seule est refusée : libellé « Refusé
        (partiel) », l'autre ligne reste « Validé »."""
        autre = Article.objects.create(
            boutique=self.depot, code='REF-ART-2', nom='Article REF 2',
            prix_vente=Decimal('900'), quantite_stock=100,
            est_actif=True, est_valide_client=True,
        )
        lot_refuse = self._transfert(150)
        lot_epargne = TransfertStock.objects.create(
            article=autre, depot_source=self.depot,
            boutique_destination=self.pdv, quantite=10,
            effectue_par='ref_comm', statut='EN_ATTENTE',
            reference_lot=lot_refuse.reference_lot,
        )
        lot_epargne.valider_transfert('ref_comm')

        pdv_autre = Article.objects.get(boutique=self.pdv, code='REF-ART-2')
        self.assertEqual(self._refuser().status_code, 200)

        r = self._historique()
        lots = {l['reference_lot']: l for l in r.json()['transferts']}
        lot = lots[lot_refuse.reference_lot]
        self.assertEqual(lot['statut_libelle'], 'Refusé (partiel)')
        self.assertTrue(lot['refuse'])

        # L'autre ligne du même lot n'était pas en attente : intacte
        pdv_autre.refresh_from_db()
        self.assertEqual(pdv_autre.quantite_envoyee, 10)
        lot_epargne.refresh_from_db()
        self.assertIsNone(lot_epargne.date_refus)


class ConsumerRefusReceptionTest(SimpleTestCase):
    """Ce que reçoit réellement le terminal côté WebSocket."""

    def test_le_handler_reenvoie_tous_les_champs(self):
        consommateur = BoutiqueConsumer()
        consommateur.send = AsyncMock()

        event = {
            'type': 'refus_reception',
            'role': 'source',
            'reference': 'RETOUR-42',
            'article_id': 12,
            'article_nom': 'Coca',
            'quantite': 20,
            'source_nom': 'Dépôt Central',
            'destination_nom': 'Boutique Nord',
            'stock_source': 170,
        }
        async_to_sync(consommateur.refus_reception)(event)

        consommateur.send.assert_awaited_once()
        payload = json.loads(consommateur.send.call_args.kwargs['text_data'])
        self.assertEqual(payload['type'], 'refus_reception')
        for cle in ('role', 'reference', 'article_id', 'article_nom',
                    'quantite', 'source_nom', 'destination_nom', 'stock_source'):
            self.assertEqual(payload[cle], event[cle])
        self.assertIn('timestamp', payload)
