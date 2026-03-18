"""
WebSocket URL routing pour l'application inventory
Définit les routes WebSocket pour les mises à jour temps réel
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # WebSocket pour les mises à jour d'une boutique spécifique
    # ws://serveur.com/ws/boutique/2/
    re_path(r'ws/boutique/(?P<boutique_id>\d+)/$', consumers.BoutiqueConsumer.as_asgi()),
    
    # WebSocket pour les notifications d'une boutique
    # ws://serveur.com/ws/notifications/2/
    re_path(r'ws/notifications/(?P<boutique_id>\d+)/$', consumers.NotificationConsumer.as_asgi()),
]
