# -*- coding: utf-8 -*-
"""
Service de notifications PUSH (FCM - Firebase Cloud Messaging).

🔔 Envoie une notification au terminal MAUI même si l'application est fermée.
Complète le WebSocket (temps réel, app ouverte).

Configuration (variables d'environnement) :
  GOOGLE_APPLICATION_CREDENTIALS=<chemin vers le JSON du compte de service Firebase>
  (ou FIREBASE_SERVICE_ACCOUNT_JSON contenu du JSON côté Scalingo)

Les terminaux enregistrent leur jeton via POST /api/v2/simple/terminal/token/
(stocké dans Client.fcm_token).

Le service est OPTIONNEL : sans compte de service, tout est désactivé proprement.
"""
import json
import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)

# 🎵 Son de notification Android (doit correspondre à un fichier présent dans
# Resources/Raw de l'app MAUI, ex. notification_sound.wav → res/raw)
SON_NOTIFICATION = "notification_sound"
CANAL_NOTIFICATION = "notifications"


def _config_android_notification():
    """Config Android (son + canal + priorité) pour que la notification
    retentisse même quand l'app est en arrière-plan."""
    try:
        from firebase_admin import messaging
        return messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                sound=SON_NOTIFICATION,
                channel_id=CANAL_NOTIFICATION,
                priority="high",
            ),
        )
    except Exception:
        return None


def _creds_prets():
    """Vérifie que les identifiants Firebase sont disponibles."""
    if getattr(settings, 'FIREBASE_DISABLED', False):
        return False
    if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        return True
    if os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON'):
        return True
    return False


def envoyer_push_boutique(boutique_id, titre, corps, data=None):
    """
    Envoie une notification push à TOUS les terminaux MAUI de la boutique.

    Args:
        boutique_id: ID de la boutique
        titre: Titre de la notification
        corps: Message
        data: dict optionnel transmis à l'app (ex: {"type": "sync_required"})
    """
    try:
        if not _creds_prets():
            logger.warning(f"🔔 FCM: credentials non configurés, push ignoré pour boutique {boutique_id}")
            return 0

        from inventory.models import Client
        tokens = list(
            Client.objects.filter(
                boutique_id=boutique_id,
                est_actif=True,
            ).exclude(fcm_token='').exclude(fcm_token__isnull=True)
            .values_list('fcm_token', flat=True)
        )
        if not tokens:
            logger.warning(f"🔔 FCM: aucun token pour boutique {boutique_id}")
            return 0

        logger.info(f"🔔 FCM: {len(tokens)} token(s) trouvé(s) pour boutique {boutique_id}")

        import firebase_admin
        from firebase_admin import credentials, messaging

        if not firebase_admin._apps:
            # Initialisation une seule fois
            env_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
            if env_path and os.path.exists(env_path):
                cred = credentials.Certificate(env_path)
            else:
                cred = credentials.Certificate(
                    json.loads(os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON', '{}'))
                )
            firebase_admin.initialize_app(cred)

        sent = 0
        for token in tokens:
            try:
                message = messaging.Message(
                    notification=messaging.Notification(title=titre, body=corps),
                    data={k: str(v) for k, v in (data or {}).items()},
                    android=_config_android_notification(),
                    token=token,
                )
                messaging.send(message)
                sent += 1
            except Exception as e:
                logger.error(f"❌ FCM: échec envoi vers token {token[:20]}...: {e}")
        logger.info(
            f"🔔 FCM: {sent}/{len(tokens)} envoyé(s) (boutique {boutique_id})"
        )
        return sent

    except Exception as e:
        logger.error(f"❌ Erreur envoi push FCM (boutique {boutique_id}): {e}")
        return 0


def envoyer_push_terminal(terminal, titre, corps, data=None):
    """Envoie une notification push à UN terminal spécifique."""
    try:
        if not _creds_prets():
            return False
        if not terminal or not terminal.fcm_token:
            return False

        import firebase_admin
        from firebase_admin import credentials, messaging

        if not firebase_admin._apps:
            env_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
            if env_path and os.path.exists(env_path):
                cred = credentials.Certificate(env_path)
            else:
                cred = credentials.Certificate(
                    json.loads(os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON', '{}'))
                )
            firebase_admin.initialize_app(cred)

        message = messaging.Message(
            notification=messaging.Notification(title=titre, body=corps),
            data={k: str(v) for k, v in (data or {}).items()},
            android=_config_android_notification(),
            token=terminal.fcm_token,
        )
        messaging.send(message)
        logger.info(f"🔔 FCM: notification envoyée à {terminal.nom_terminal}")
        return True

    except Exception as e:
        logger.error(f"❌ Erreur push FCM terminal {getattr(terminal, 'id', '?')}: {e}")
        return False