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

⚠️ Deux règles de sécurité serveur (incident « serveur bloqué ») :
  1. timeout HTTP COURT (10 s au lieu de 120 s par défaut) ;
  2. l'envoi se fait dans un thread DÉMON en arrière-plan : une requête
     web n'attend JAMAIS la réponse de Google (sauf `synchrone=True`,
     réservé aux endpoints de test).
"""
import json
import logging
import os
import threading

from django.conf import settings

logger = logging.getLogger(__name__)

# 🎵 Son de notification Android (doit correspondre à un fichier présent dans
# Resources/Raw de l'app MAUI, ex. notification_sound.wav → res/raw)
SON_NOTIFICATION = "notification_sound"
CANAL_NOTIFICATION = "notifications"

# ⏱️ Timeout HTTP (secondes). firebase_admin attend PAR DÉFAUT 120 s par
# appel, avec jusqu'à 4 nouvelles tentatives sur erreur 500/503 : un appel
# Google qui traîne bloquait le fil de la requête web (daphne) et pouvait
# figer tout le serveur. On borne à 10 s.
HTTP_TIMEOUT_SECONDS = 10

# 👷 File d'envoi en arrière-plan : 4 envois simultanés maximum. Au-delà la
# notification est sacrifiée (mieux vaut perdre un push que de figer le
# serveur) — les threads sont des démons : jamais d'attente à l'arrêt.
MAX_ENVOIS_SIMULTANES = 4
_file_envoi = threading.Semaphore(MAX_ENVOIS_SIMULTANES)


def _soumettre(job):
    """
    Lance `job` dans un thread démon sans jamais bloquer l'appelant.

    Retourne False si la file est saturée (l'envoi est alors abandonné).
    """
    if not _file_envoi.acquire(blocking=False):
        logger.warning(
            "🔔 FCM: file d'envoi saturée (%s en cours), notification abandonnée",
            MAX_ENVOIS_SIMULTANES,
        )
        return False

    def _rouler():
        try:
            job()
        except Exception as exc:  # noqa: BLE001 - un échec d'envoi ne tue pas la file
            logger.error(f"❌ FCM: échec de l'envoi en arrière-plan: {exc}")
        finally:
            _file_envoi.release()

    threading.Thread(target=_rouler, daemon=True, name='fcm-push').start()
    return True


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


def _app_firebase():
    """
    Retourne l'app Firebase, initialisée UNE SEULE fois avec un timeout
    HTTP court (couvre l'envoi des messages et le rafraîchissement du
    jeton d'accès).
    """
    import firebase_admin
    from firebase_admin import credentials

    if not firebase_admin._apps:
        env_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if env_path and os.path.exists(env_path):
            cred = credentials.Certificate(env_path)
        else:
            cred = credentials.Certificate(
                json.loads(os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON', '{}'))
            )
        firebase_admin.initialize_app(
            cred, options={'httpTimeout': HTTP_TIMEOUT_SECONDS},
        )
    return firebase_admin.get_app()


def _envoyer_aux_tokens(boutique_id, titre, corps, data, tokens):
    """Envoie le message à chaque token (appel bloquant : à lancer dans un
    thread de la file `_file_envoi` ou en mode `synchrone=True`)."""
    from firebase_admin import messaging

    _app_firebase()
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


def envoyer_push_boutique(boutique_id, titre, corps, data=None, synchrone=False):
    """
    Envoie une notification push à TOUS les terminaux MAUI de la boutique.

    Args:
        boutique_id: ID de la boutique
        titre: Titre de la notification
        corps: Message de la notification
        data: dict optionnel transmis à l'app (ex: {"type": "sync_required"})
        synchrone: True pour attendre réellement l'envoi (endpoints de test
            uniquement). Par défaut (False) l'envoi part en arrière-plan et
            la requête web ne s'arrête jamais sur Google.

    Retourne le nombre de terminaux visés (ou envoyés si synchrone=True).
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

        if synchrone:
            return _envoyer_aux_tokens(boutique_id, titre, corps, data, tokens)

        # Envoi détaché : la requête web repart immédiatement.
        soumis = _soumettre(
            lambda: _envoyer_aux_tokens(boutique_id, titre, corps, data, tokens)
        )
        return len(tokens) if soumis else 0

    except Exception as e:
        logger.error(f"❌ Erreur envoi push FCM (boutique {boutique_id}): {e}")
        return 0


def _envoyer_au_terminal(nom_terminal, token, titre, corps, data):
    """Envoie le message à UN terminal (blocage limité à HTTP_TIMEOUT_SECONDS)."""
    from firebase_admin import messaging

    _app_firebase()
    message = messaging.Message(
        notification=messaging.Notification(title=titre, body=corps),
        data={k: str(v) for k, v in (data or {}).items()},
        android=_config_android_notification(),
        token=token,
    )
    messaging.send(message)
    logger.info(f"🔔 FCM: notification envoyée à {nom_terminal}")
    return True


def envoyer_push_terminal(terminal, titre, corps, data=None, synchrone=False):
    """
    Envoie une notification push à UN terminal spécifique.

    Le jeton est lu dans le fil de la requête (requête ORM locale), puis
    l'envoi HTTP part en arrière-plan : la requête ne bloque jamais.
    Retourne True si l'envoi a été soumis (ou effectué si synchrone=True).
    """
    try:
        if not _creds_prets():
            return False
        if not terminal or not terminal.fcm_token:
            return False

        nom_terminal = terminal.nom_terminal
        token = terminal.fcm_token

        if synchrone:
            return _envoyer_au_terminal(nom_terminal, token, titre, corps, data)

        return _soumettre(
            lambda: _envoyer_au_terminal(nom_terminal, token, titre, corps, data)
        )

    except Exception as e:
        logger.error(f"❌ Erreur push FCM terminal {getattr(terminal, 'id', '?')}: {e}")
        return False
