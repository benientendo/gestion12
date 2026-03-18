"""
ASGI config for gestion_magazin project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')

# ⚠️ IMPORTANT: get_asgi_application() DOIT être appelé en premier
# pour initialiser le registre Django AVANT tout import de models/consumers
from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

# Ces imports se font APRÈS l'initialisation Django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from inventory.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    # HTTP requests → Django
    "http": django_asgi_app,

    # WebSocket requests → Channels
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ),
})
