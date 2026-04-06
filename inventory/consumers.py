"""
WebSocket Consumers pour mises à jour temps réel
Permet aux POS MAUI de recevoir instantanément les changements
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from inventory.models import Boutique, Client

logger = logging.getLogger(__name__)


class BoutiqueConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket pour une boutique spécifique
    Chaque boutique a son propre canal isolé
    """
    
    async def connect(self):
        """Connexion d'un POS au WebSocket"""
        # Récupérer l'ID de la boutique depuis l'URL
        self.boutique_id = self.scope['url_route']['kwargs']['boutique_id']
        self.room_group_name = f'boutique_{self.boutique_id}'
        
        # Récupérer le numéro de série du terminal depuis les headers
        headers = dict(self.scope['headers'])
        self.numero_serie = None
        
        for key, value in headers.items():
            if key.decode('utf-8').lower() in ['x-device-serial', 'device-serial']:
                self.numero_serie = value.decode('utf-8')
                break
        
        # Vérifier que la boutique existe et que le terminal est autorisé
        is_authorized = await self.check_authorization()
        
        if not is_authorized:
            logger.warning(f"❌ Connexion WebSocket refusée - Boutique {self.boutique_id}, Terminal {self.numero_serie}")
            await self.close()
            return
        
        # Rejoindre le groupe de la boutique (isolation stricte)
        try:
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
        except Exception as e:
            logger.error(f"❌ Erreur group_add BoutiqueConsumer (Redis indispo?): {type(e).__name__}: {e}")
            await self.close()
            return
        
        # Accepter la connexion
        await self.accept()
        
        logger.info(f"✅ WebSocket connecté - Boutique {self.boutique_id}, Terminal {self.numero_serie}")
        
        # Envoyer message de confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'boutique_id': self.boutique_id,
            'message': 'Connexion WebSocket établie avec succès',
            'timestamp': self.get_timestamp()
        }))
    
    async def disconnect(self, close_code):
        """Déconnexion d'un POS"""
        try:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        except Exception as e:
            logger.warning(f"⚠️ Erreur group_discard BoutiqueConsumer: {type(e).__name__}: {e}")
        
        logger.info(f"🔌 WebSocket déconnecté - Boutique {self.boutique_id}, Code {close_code}")
    
    async def receive(self, text_data):
        """Réception d'un message du POS (ping/pong pour keep-alive)"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                # Répondre au ping pour maintenir la connexion
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': self.get_timestamp()
                }))
            
        except json.JSONDecodeError:
            logger.error(f"❌ Message WebSocket invalide: {text_data}")
    
    # Handlers pour les différents types d'événements
    
    async def article_updated(self, event):
        """Un article a été modifié (prix, stock, nom, etc.)"""
        await self.send(text_data=json.dumps({
            'type': 'article_updated',
            'article': event['article'],
            'timestamp': self.get_timestamp()
        }))
        logger.info(f"📤 Article mis à jour envoyé - ID {event['article']['id']}")
    
    async def article_created(self, event):
        """Un nouvel article a été créé"""
        await self.send(text_data=json.dumps({
            'type': 'article_created',
            'article': event['article'],
            'timestamp': self.get_timestamp()
        }))
        logger.info(f"📤 Nouvel article envoyé - ID {event['article']['id']}")
    
    async def article_deleted(self, event):
        """Un article a été désactivé/supprimé"""
        await self.send(text_data=json.dumps({
            'type': 'article_deleted',
            'article_id': event['article_id'],
            'timestamp': self.get_timestamp()
        }))
        logger.info(f"📤 Article supprimé envoyé - ID {event['article_id']}")
    
    async def stock_updated(self, event):
        """Le stock d'un article a changé"""
        await self.send(text_data=json.dumps({
            'type': 'stock_updated',
            'article_id': event['article_id'],
            'new_stock': event['new_stock'],
            'timestamp': self.get_timestamp()
        }))
        logger.info(f"📤 Stock mis à jour - Article {event['article_id']}, Stock {event['new_stock']}")
    
    async def price_updated(self, event):
        """Le prix d'un article a changé"""
        await self.send(text_data=json.dumps({
            'type': 'price_updated',
            'article_id': event['article_id'],
            'new_price': event['new_price'],
            'devise': event.get('devise', 'CDF'),
            'timestamp': self.get_timestamp()
        }))
        logger.info(f"📤 Prix mis à jour - Article {event['article_id']}, Prix {event['new_price']}")
    
    async def category_updated(self, event):
        """Une catégorie a été modifiée"""
        await self.send(text_data=json.dumps({
            'type': 'category_updated',
            'category': event['category'],
            'timestamp': self.get_timestamp()
        }))
        logger.info(f"📤 Catégorie mise à jour - ID {event['category']['id']}")
    
    async def sync_required(self, event):
        """Demander au POS de faire une synchronisation complète"""
        await self.send(text_data=json.dumps({
            'type': 'sync_required',
            'reason': event.get('reason', 'Synchronisation demandée'),
            'timestamp': self.get_timestamp()
        }))
        logger.info(f"📤 Sync requise envoyée - Raison: {event.get('reason')}")
    
    # Méthodes utilitaires
    
    @database_sync_to_async
    def check_authorization(self):
        """Vérifier que le terminal est autorisé à se connecter à cette boutique"""
        try:
            # Vérifier que la boutique existe et est active
            boutique = Boutique.objects.filter(
                id=self.boutique_id,
                est_active=True
            ).first()
            
            if not boutique:
                return False
            
            # Si pas de numéro de série, refuser (sécurité)
            if not self.numero_serie:
                return False
            
            # Vérifier que le terminal existe et appartient à cette boutique
            terminal = Client.objects.filter(
                numero_serie=self.numero_serie,
                boutique_id=self.boutique_id,
                est_actif=True
            ).first()
            
            if not terminal:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur vérification autorisation WebSocket: {e}")
            return False
    
    def get_timestamp(self):
        """Retourner le timestamp actuel en ISO format"""
        from django.utils import timezone
        return timezone.now().isoformat()


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Consumer pour les notifications générales (alertes stock, etc.)
    """
    
    async def connect(self):
        """Connexion pour recevoir les notifications"""
        self.boutique_id = self.scope['url_route']['kwargs']['boutique_id']
        self.notification_group_name = f'notifications_{self.boutique_id}'

        # Rejoindre le groupe de notifications avant d'accepter (même pattern que BoutiqueConsumer)
        try:
            await self.channel_layer.group_add(
                self.notification_group_name,
                self.channel_name
            )
        except Exception as e:
            logger.error(f"Erreur group_add NotificationConsumer: {type(e).__name__}: {e}")
            await self.close()
            return

        await self.accept()

        # Envoyer confirmation (évite timeout proxy Scalingo/HAProxy)
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'boutique_id': self.boutique_id,
            'message': 'Notifications WebSocket actives',
            'timestamp': self.get_timestamp()
        }))

        logger.info(f"Notifications WebSocket connectees - Boutique {self.boutique_id}")
    
    async def disconnect(self, close_code):
        """Déconnexion des notifications"""
        await self.channel_layer.group_discard(
            self.notification_group_name,
            self.channel_name
        )
        logger.info(f"🔌 Notifications WebSocket déconnectées - Boutique {self.boutique_id}")
    
    async def stock_alert(self, event):
        """Alerte de stock faible"""
        await self.send(text_data=json.dumps({
            'type': 'stock_alert',
            'article_id': event['article_id'],
            'article_nom': event['article_nom'],
            'stock_actuel': event['stock_actuel'],
            'seuil_alerte': event.get('seuil_alerte', 10),
            'timestamp': self.get_timestamp()
        }))
    
    async def vente_rejected(self, event):
        """Vente rejetée (stock insuffisant, etc.)"""
        await self.send(text_data=json.dumps({
            'type': 'vente_rejected',
            'vente_uid': event['vente_uid'],
            'raison': event['raison'],
            'timestamp': self.get_timestamp()
        }))

    async def dashboard_stats_updated(self, event):
        """Mise à jour des statistiques du dashboard gérant en temps réel"""
        await self.send(text_data=json.dumps({
            'type': 'dashboard_stats_updated',
            'stats': event['stats'],
            'timestamp': self.get_timestamp()
        }))
    
    def get_timestamp(self):
        from django.utils import timezone
        return timezone.now().isoformat()
