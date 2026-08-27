"""
Utilitaires pour envoyer des événements WebSocket
Permet de notifier les POS en temps réel depuis n'importe quelle vue
"""
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


def _push_fcm(boutique_id, titre, corps, data=None):
    """🔔 PUSH FCM (même si l'app MAUI est fermée) — silencieux si non configuré."""
    try:
        from .services.firebase_push import envoyer_push_boutique
        envoyer_push_boutique(boutique_id, titre, corps, data=data)
    except Exception as e:
        logger.error(f"❌ Erreur push FCM ({titre}): {e}")


def notify_article_updated(boutique_id, article):
    """
    Notifier tous les POS qu'un article a été modifié
    
    Args:
        boutique_id: ID de la boutique
        article: Instance du modèle Article
    """
    try:
        channel_layer = get_channel_layer()
        room_group_name = f'boutique_{boutique_id}'
        
        article_data = {
            'id': article.id,
            'code': article.code,
            'nom': article.nom,
            'prix_vente': str(article.prix_vente),
            'prix_vente_usd': str(article.prix_vente_usd) if article.prix_vente_usd else None,
            'devise': article.devise,
            'quantite_stock': article.quantite_stock,
            'est_actif': article.est_actif,
            'categorie_id': article.categorie_id,
            'categorie_nom': article.categorie.nom if article.categorie else None,
            'last_updated': article.last_updated.isoformat() if hasattr(article, 'last_updated') else None,
            'version': article.version if hasattr(article, 'version') else None,
        }
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'article_updated',
                'article': article_data
            }
        )
        
        logger.info(f"🔔 WebSocket: Article {article.id} mis à jour envoyé à boutique {boutique_id}")

    except Exception as e:
        logger.error(f"❌ Erreur envoi WebSocket article_updated: {e}")

    _push_fcm(
        boutique_id,
        "Article modifié",
        f"{article.nom} a été mis à jour (code {article.code}).",
        data={'type': 'article_updated', 'article_id': article.id}
    )


def notify_article_created(boutique_id, article):
    """
    Notifier tous les POS qu'un nouvel article a été créé
    
    Args:
        boutique_id: ID de la boutique
        article: Instance du modèle Article
    """
    try:
        channel_layer = get_channel_layer()
        room_group_name = f'boutique_{boutique_id}'
        
        article_data = {
            'id': article.id,
            'code': article.code,
            'nom': article.nom,
            'prix_vente': str(article.prix_vente),
            'prix_vente_usd': str(article.prix_vente_usd) if article.prix_vente_usd else None,
            'devise': article.devise,
            'quantite_stock': article.quantite_stock,
            'est_actif': article.est_actif,
            'categorie_id': article.categorie_id,
            'categorie_nom': article.categorie.nom if article.categorie else None,
            'date_creation': article.date_creation.isoformat(),
        }
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'article_created',
                'article': article_data
            }
        )
        
        logger.info(f"🔔 WebSocket: Nouvel article {article.id} envoyé à boutique {boutique_id}")
        
    except Exception as e:
        logger.error(f"❌ Erreur envoi WebSocket article_created: {e}")

    # 🔔 PUSH FCM (même si l'app est fermée)
    _push_fcm(
        boutique_id,
        "Nouvel article",
        f"{article.nom} a été ajouté au catalogue.",
        data={'type': 'article_created', 'article_id': article.id}
    )


def notify_article_deleted(boutique_id, article_id, article_nom=None):
    """
    Notifier tous les POS qu'un article a été supprimé/désactivé
    
    Args:
        boutique_id: ID de la boutique
        article_id: ID de l'article supprimé
        article_nom: Nom de l'article (optionnel)
    """
    try:
        channel_layer = get_channel_layer()
        notification_group_name = f'notifications_{boutique_id}'
        
        async_to_sync(channel_layer.group_send)(
            notification_group_name,
            {
                'type': 'article_deleted',
                'article_id': article_id
            }
        )
        
        logger.info(f"🔔 WebSocket: Article {article_id} supprimé envoyé à boutique {boutique_id}")
        
    except Exception as e:
        logger.error(f"❌ Erreur envoi WebSocket article_deleted: {e}")

    _push_fcm(
        boutique_id,
        "Article supprimé",
        f"L'article {article_nom or f'#{article_id}'} a été supprimé.",
        data={'type': 'article_deleted', 'article_id': article_id}
    )


def notify_stock_updated(boutique_id, article_id, new_stock, article_nom=None, push_fcm=True):
    """
    Notifier tous les POS qu'un stock a changé
    
    Args:
        boutique_id: ID de la boutique
        article_id: ID de l'article
        new_stock: Nouveau stock
        article_nom: Nom de l'article (optionnel, pour le push FCM)
        push_fcm: Envoyer un push FCM (actif par défaut)
    """
    try:
        channel_layer = get_channel_layer()
        room_group_name = f'boutique_{boutique_id}'
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'stock_updated',
                'article_id': article_id,
                'new_stock': new_stock
            }
        )
        
        logger.info(f"🔔 WebSocket: Stock article {article_id} → {new_stock} envoyé à boutique {boutique_id}")

    except Exception as e:
        logger.error(f"❌ Erreur envoi WebSocket stock_updated: {e}")

    if push_fcm:
        _push_fcm(
            boutique_id,
            "Stock mis à jour",
            f"Le stock de l'article #{article_id} est passé à {new_stock}."
            + (f" ({article_nom})" if article_nom else ""),
            data={'type': 'stock_updated', 'article_id': article_id, 'new_stock': new_stock}
        )


def notify_price_updated(boutique_id, article_id, new_price, devise='CDF', article_nom=None):
    """
    Notifier tous les POS qu'un prix a changé
    
    Args:
        boutique_id: ID de la boutique
        article_id: ID de l'article
        new_price: Nouveau prix
        devise: Devise du prix (CDF ou USD)
        article_nom: Nom de l'article (optionnel)
    """
    try:
        channel_layer = get_channel_layer()
        notification_group_name = f'notifications_{boutique_id}'
        
        async_to_sync(channel_layer.group_send)(
            notification_group_name,
            {
                'type': 'price_updated',
                'article_id': article_id,
                'new_price': str(new_price),
                'devise': devise
            }
        )
        
        logger.info(f"🔔 WebSocket: Prix article {article_id} → {new_price} {devise} envoyé à boutique {boutique_id}")
        
    except Exception as e:
        logger.error(f"❌ Erreur envoi WebSocket price_updated: {e}")

    _push_fcm(
        boutique_id,
        "Prix modifié",
        f"Le prix de {article_nom or f'#{article_id}'} est maintenant {new_price} {devise}.",
        data={'type': 'price_updated', 'article_id': article_id}
    )


def notify_category_updated(boutique_id, category):
    """
    Notifier tous les POS qu'une catégorie a été modifiée
    
    Args:
        boutique_id: ID de la boutique
        category: Instance du modèle Categorie
    """
    try:
        channel_layer = get_channel_layer()
        room_group_name = f'boutique_{boutique_id}'
        
        category_data = {
            'id': category.id,
            'nom': category.nom,
            'description': category.description,
            'last_updated': category.last_updated.isoformat() if hasattr(category, 'last_updated') else None,
        }
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'category_updated',
                'category': category_data
            }
        )
        
        logger.info(f"🔔 WebSocket: Catégorie {category.id} mise à jour envoyée à boutique {boutique_id}")
        
    except Exception as e:
        logger.error(f"❌ Erreur envoi WebSocket category_updated: {e}")


def notify_sync_required(boutique_id, reason="Synchronisation demandée"):
    """
    Notifier tous les POS qu'une synchronisation est requise
    
    Args:
        boutique_id: ID de la boutique
        reason: Motif de la synchronisation
    """
    try:
        channel_layer = get_channel_layer()
        room_group_name = f'boutique_{boutique_id}'
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'sync_required',
                'reason': reason
            }
        )
        
        logger.info(f"🔔 WebSocket: Sync requise envoyée à boutique {boutique_id} ({reason})")
        
    except Exception as e:
        logger.error(f"❌ Erreur envoi WebSocket sync_required: {e}")

    # 🔔 PUSH FCM (même si l'app est fermée)
    _push_fcm(
        boutique_id,
        "Synchronisation nécessaire",
        reason,
        data={'type': 'sync_required', 'reason': reason}
    )


def notify_stock_alert(boutique_id, article_id, article_nom, stock_actuel, seuil_alerte=10):
    """
    Envoyer une alerte de stock faible
    
    Args:
        boutique_id: ID de la boutique
        article_id: ID de l'article
        article_nom: Nom de l'article
        stock_actuel: Stock actuel
        seuil_alerte: Seuil d'alerte
    """
    try:
        channel_layer = get_channel_layer()
        notification_group_name = f'notifications_{boutique_id}'
        
        async_to_sync(channel_layer.group_send)(
            notification_group_name,
            {
                'type': 'stock_alert',
                'article_id': article_id,
                'article_nom': article_nom,
                'stock_actuel': stock_actuel,
                'seuil_alerte': seuil_alerte
            }
        )
        
        logger.info(f"🔔 WebSocket: Alerte stock {article_nom} ({stock_actuel}) envoyée à boutique {boutique_id}")
        
    except Exception as e:
        logger.error(f"❌ Erreur envoi WebSocket stock_alert: {e}")


def notify_dashboard_stats(boutique_id, stats):
    """
    Pousser les statistiques du dashboard en temps réel vers le navigateur du gérant
    
    Args:
        boutique_id: ID de la boutique
        stats: dict avec ca_jour, ca_jour_usd, ca_mois, ca_mois_usd, nb_ventes_jour, nb_ventes_mois
    """
    try:
        channel_layer = get_channel_layer()
        notification_group_name = f'notifications_{boutique_id}'

        async_to_sync(channel_layer.group_send)(
            notification_group_name,
            {
                'type': 'dashboard_stats_updated',
                'stats': stats,
            }
        )

        logger.info(f"🔔 WebSocket: Stats dashboard boutique {boutique_id} → ca_jour={stats.get('ca_jour')} CDF")

    except Exception as e:
        logger.error(f"❌ Erreur envoi WebSocket dashboard_stats_updated: {e}")


def notify_vente_rejected(boutique_id, vente_uid, raison):
    """
    Notifier qu'une vente a été rejetée
    
    Args:
        boutique_id: ID de la boutique
        vente_uid: UID de la vente rejetée
        raison: Raison du rejet
    """
    try:
        channel_layer = get_channel_layer()
        notification_group_name = f'notifications_{boutique_id}'
        
        async_to_sync(channel_layer.group_send)(
            notification_group_name,
            {
                'type': 'vente_rejected',
                'vente_uid': vente_uid,
                'raison': raison
            }
        )
        
        logger.info(f"🔔 WebSocket: Vente {vente_uid} rejetée envoyée à boutique {boutique_id}")
        
    except Exception as e:
        logger.error(f"❌ Erreur envoi WebSocket vente_rejected: {e}")


def notify_banner_created(boutique_id, banner_id, banner_titre):
    """
    Notifier les POS qu'une nouvelle bannière publicitaire est disponible.
    
    Args:
        boutique_id: ID de la boutique (None = toutes les boutiques)
        banner_id: ID de la bannière
        banner_titre: Titre de la bannière
    """
    try:
        channel_layer = get_channel_layer()
        
        if boutique_id:
            room_group_name = f'boutique_{boutique_id}'
            async_to_sync(channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'banner_created',
                    'banner_id': banner_id,
                    'banner_titre': banner_titre,
                }
            )
        else:
            from .models import Boutique
            for b in Boutique.objects.filter(est_active=True):
                async_to_sync(channel_layer.group_send)(
                    f'boutique_{b.id}',
                    {
                        'type': 'banner_created',
                        'banner_id': banner_id,
                        'banner_titre': banner_titre,
                    }
                )
        
        logger.info(f"🔔 WebSocket: Bannière '{banner_titre}' (#{banner_id}) notifiée")
        
    except Exception as e:
        logger.error(f"❌ Erreur envoi WebSocket banner_created: {e}")

    _push_fcm(
        boutique_id,
        "📢 Nouvelle bannière",
        banner_titre,
        data={'type': 'banner_created', 'banner_id': banner_id}
    )


def notify_merchant_message(commercant_id, message_id, message_titre, message_type):
    """
    Notifier un commerçant qu'il a reçu un nouveau message.
    """
    try:
        from .models import Boutique
        boutiques = Boutique.objects.filter(commercant_id=commercant_id, est_active=True)
        for b in boutiques:
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f'boutique_{b.id}',
                    {
                        'type': 'merchant_message',
                        'message_id': message_id,
                        'message_titre': message_titre,
                        'message_type': message_type,
                    }
                )
            except Exception as e:
                logger.error(f"❌ Erreur WebSocket message commerçant boutique {b.id}: {e}")

        logger.info(f"🔔 WebSocket: Message '{message_titre}' notifié au commerçant #{commercant_id}")
    except Exception as e:
        logger.error(f"❌ Erreur notification message commerçant: {e}")

    # Push FCM
    try:
        from .models import Client
        terminals = Client.objects.filter(
            boutique__commercant_id=commercant_id,
            est_actif=True,
            fcm_token__isnull=False
        ).exclude(fcm_token='')

        for terminal in terminals:
            try:
                _push_fcm_to_token(
                    terminal.fcm_token,
                    f"📩 {message_titre}",
                    f"Type: {message_type}",
                    data={'type': 'merchant_message', 'message_id': message_id}
                )
            except Exception as e:
                logger.error(f"❌ FCM message commerçant terminal {terminal.numero_serie}: {e}")
    except Exception as e:
        logger.error(f"❌ Erreur FCM message commerçant: {e}")


def _push_fcm_to_token(token, title, body, data=None):
    """Envoyer un push FCM à un token spécifique."""
    try:
        from firebase_admin import messaging
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            token=token,
        )
        messaging.send(message)
    except Exception as e:
        logger.error(f"❌ FCM push échoué: {e}")
