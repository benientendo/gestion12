"""
Utilitaires pour envoyer des événements WebSocket
Permet de notifier les POS en temps réel depuis n'importe quelle vue
"""
import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


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


def notify_article_deleted(boutique_id, article_id):
    """
    Notifier tous les POS qu'un article a été supprimé/désactivé
    
    Args:
        boutique_id: ID de la boutique
        article_id: ID de l'article supprimé
    """
    try:
        channel_layer = get_channel_layer()
        room_group_name = f'boutique_{boutique_id}'
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'article_deleted',
                'article_id': article_id
            }
        )
        
        logger.info(f"🔔 WebSocket: Article {article_id} supprimé envoyé à boutique {boutique_id}")
        
    except Exception as e:
        logger.error(f"❌ Erreur envoi WebSocket article_deleted: {e}")


def notify_stock_updated(boutique_id, article_id, new_stock):
    """
    Notifier tous les POS qu'un stock a changé
    
    Args:
        boutique_id: ID de la boutique
        article_id: ID de l'article
        new_stock: Nouveau stock
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


def notify_price_updated(boutique_id, article_id, new_price, devise='CDF'):
    """
    Notifier tous les POS qu'un prix a changé
    
    Args:
        boutique_id: ID de la boutique
        article_id: ID de l'article
        new_price: Nouveau prix
        devise: Devise du prix (CDF ou USD)
    """
    try:
        channel_layer = get_channel_layer()
        room_group_name = f'boutique_{boutique_id}'
        
        async_to_sync(channel_layer.group_send)(
            room_group_name,
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
    Demander à tous les POS de faire une synchronisation complète
    
    Args:
        boutique_id: ID de la boutique
        reason: Raison de la synchronisation
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
        
        logger.info(f"🔔 WebSocket: Sync requise envoyée à boutique {boutique_id} - {reason}")
        
    except Exception as e:
        logger.error(f"❌ Erreur envoi WebSocket sync_required: {e}")


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
