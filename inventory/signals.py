from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import MouvementStock, NotificationStock, Client, Article
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=MouvementStock)
def creer_notification_stock(sender, instance, created, **kwargs):
    """
    Signal pour créer automatiquement des notifications pour les mouvements de stock.
    Notifie tous les clients MAUI associés à la boutique concernée.
    Types de mouvement notifiés:
    - ENTREE: ajout de stock
    - SORTIE: retrait de stock
    - AJUSTEMENT: ajustement de stock
    """
    if not created:
        return
    
    article = instance.article
    if not article or not article.boutique:
        return
    
    boutique = article.boutique
    
    clients_boutique = Client.objects.filter(
        boutique=boutique,
        est_actif=True
    )
    
    if not clients_boutique.exists():
        logger.info(f"Aucun client actif trouvé pour la boutique {boutique.nom}")
        return
    
    # Déterminer le type de notification et le message selon le mouvement
    if instance.type_mouvement == 'ENTREE':
        type_notif = 'STOCK_AJOUT'
        titre = f"Ajout de stock: {article.nom}"
        message = (
            f"L'article '{article.nom}' ({article.code}) a été ajouté au stock.\n"
            f"Quantité ajoutée: +{instance.quantite}\n"
            f"Stock avant: {instance.stock_avant or 0}\n"
            f"Stock actuel: {instance.stock_apres or article.quantite_stock}"
        )
        action = "ajout"
    elif instance.type_mouvement == 'SORTIE':
        type_notif = 'STOCK_RETRAIT'
        titre = f"Retrait de stock: {article.nom}"
        message = (
            f"L'article '{article.nom}' ({article.code}) a été retiré du stock.\n"
            f"Quantité retirée: {instance.quantite}\n"
            f"Stock avant: {instance.stock_avant or 0}\n"
            f"Stock actuel: {instance.stock_apres or article.quantite_stock}"
        )
        action = "retrait"
    elif instance.type_mouvement == 'AJUSTEMENT':
        type_notif = 'STOCK_AJUSTEMENT'
        titre = f"Ajustement de stock: {article.nom}"
        signe = '+' if instance.quantite > 0 else ''
        message = (
            f"L'article '{article.nom}' ({article.code}) a été ajusté.\n"
            f"Ajustement: {signe}{instance.quantite}\n"
            f"Stock avant: {instance.stock_avant or 0}\n"
            f"Stock actuel: {instance.stock_apres or article.quantite_stock}"
        )
        action = "ajustement"
    else:
        return
    
    if instance.commentaire:
        message += f"\n\nCommentaire: {instance.commentaire}"
    
    donnees_sup = {
        'article_id': article.id,
        'article_code': article.code,
        'article_nom': article.nom,
        'prix_vente': str(article.prix_vente),
        'prix_ancien': str(getattr(instance, 'prix_ancien', None)) if hasattr(instance, 'prix_ancien') else None,
        'devise': article.devise,
        'categorie': article.categorie.nom if article.categorie else None,
        'type_mouvement': instance.type_mouvement,
        'reference_document': instance.reference_document,
        'utilisateur': instance.utilisateur,
        'stock_avant': instance.stock_avant or 0,
        'stock_apres': instance.stock_apres or article.quantite_stock,
    }
    
    notifications_creees = 0
    for client in clients_boutique:
        try:
            NotificationStock.objects.create(
                client=client,
                boutique=boutique,
                type_notification=type_notif,
                titre=titre,
                message=message,
                mouvement_stock=instance,
                article=article,
                quantite_mouvement=instance.quantite,
                quantite_ajoutee=instance.quantite if instance.quantite > 0 else 0,
                stock_avant=instance.stock_avant or 0,
                stock_actuel=instance.stock_apres or article.quantite_stock,
                donnees_supplementaires=donnees_sup
            )
            notifications_creees += 1
            logger.info(f"✓ Notification créée pour {client.nom_terminal}")
        except Exception as e:
            logger.error(f"✗ Erreur création notification pour {client.nom_terminal}: {e}")
    
    logger.info(
        f"📢 {notifications_creees} notification(s) créée(s) pour le {action} de stock "
        f"de {article.nom} dans {boutique.nom}"
    )


# Variable temporaire pour stocker les prix avant modification
_prix_article_avant_save = {}


@receiver(pre_save, sender=Article)
def capturer_prix_avant_modification(sender, instance, **kwargs):
    """
    Capture le prix avant modification pour détecter les ajustements de prix.
    """
    if instance.pk:
        try:
            ancien_article = Article.objects.get(pk=instance.pk)
            _prix_article_avant_save[instance.pk] = {
                'prix_vente': ancien_article.prix_vente,
                'devise': ancien_article.devise,
            }
        except Article.DoesNotExist:
            pass


@receiver(post_save, sender=Article)
def notifier_ajustement_prix(sender, instance, created, **kwargs):
    """
    Crée des notifications lorsque le prix d'un article est modifié.
    Notifie tous les clients MAUI associés à la boutique.
    """
    if created:
        _prix_article_avant_save.pop(instance.pk, None)
        return
    
    if not instance.boutique or not instance.est_actif:
        _prix_article_avant_save.pop(instance.pk, None)
        return
    
    prix_avant_data = _prix_article_avant_save.pop(instance.pk, None)
    if not prix_avant_data:
        return
    
    prix_ancien = prix_avant_data['prix_vente']
    prix_nouveau = instance.prix_vente
    
    if prix_ancien == prix_nouveau:
        return
    
    boutique = instance.boutique
    clients_boutique = Client.objects.filter(
        boutique=boutique,
        est_actif=True
    )
    
    if not clients_boutique.exists():
        logger.info(f"Aucun client actif trouvé pour la boutique {boutique.nom}")
        return
    
    variation = prix_nouveau - prix_ancien
    pourcentage = (variation / prix_ancien * 100) if prix_ancien > 0 else 0
    signe = '+' if variation > 0 else ''
    
    type_notif = 'AJUSTEMENT_PRIX'
    titre = f"Ajustement de prix: {instance.nom}"
    message = (
        f"Le prix de l'article '{instance.nom}' ({instance.code}) a été modifié.\n"
        f"Ancien prix: {prix_ancien} {instance.devise}\n"
        f"Nouveau prix: {prix_nouveau} {instance.devise}\n"
        f"Variation: {signe}{variation} {instance.devise} ({signe}{pourcentage:.1f}%)"
    )
    
    donnees_sup = {
        'article_id': instance.id,
        'article_code': instance.code,
        'article_nom': instance.nom,
        'prix_ancien': str(prix_ancien),
        'prix_nouveau': str(prix_nouveau),
        'variation': str(variation),
        'pourcentage_variation': f"{pourcentage:.2f}",
        'devise': instance.devise,
        'categorie': instance.categorie.nom if instance.categorie else None,
        'stock_actuel': instance.quantite_stock,
    }
    
    notifications_creees = 0
    for client in clients_boutique:
        try:
            NotificationStock.objects.create(
                client=client,
                boutique=boutique,
                type_notification=type_notif,
                titre=titre,
                message=message,
                article=instance,
                quantite_mouvement=0,
                stock_avant=instance.quantite_stock,
                stock_actuel=instance.quantite_stock,
                donnees_supplementaires=donnees_sup
            )
            notifications_creees += 1
            logger.info(f"✓ Notification de prix créée pour {client.nom_terminal}")
        except Exception as e:
            logger.error(f"✗ Erreur création notification prix pour {client.nom_terminal}: {e}")
    
    logger.info(
        f"💰 {notifications_creees} notification(s) d'ajustement de prix créée(s) "
        f"pour {instance.nom} dans {boutique.nom}"
    )
