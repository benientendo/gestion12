from decimal import Decimal
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import MouvementStock, NotificationStock, Client, Article, Inventaire, LigneInventaire
from . import journal_valeur_stock as jvs
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


# ──────────────────────────────────────────────────────────────
# SIGNALS JOURNAL VALEUR STOCK
# ──────────────────────────────────────────────────────────────

@receiver(post_save, sender=MouvementStock)
def alimenter_journal_valeur_stock(sender, instance, created, **kwargs):
    """
    Met à jour le JournalValeurStock à chaque nouveau MouvementStock.
    Distingue les transferts (reference_document commence par 'TRANSFERT-')
    des entrées/sorties classiques.
    """
    if not created:
        return

    article = instance.article
    if not article or not article.boutique:
        return

    boutique = article.boutique
    prix_vente = Decimal(str(article.prix_vente or 0))
    quantite = abs(instance.quantite)
    valeur = prix_vente * quantite

    ref = instance.reference_document or ''
    type_mouv = instance.type_mouvement

    try:
        date_mouv = instance.date_mouvement.date()
    except Exception:
        date_mouv = None

    try:
        if type_mouv == 'VENTE':
            # Utiliser le vrai montant de la LigneVente si disponible
            # (prix réel = peut être négocié, différent de article.prix_vente actuel)
            valeur_reelle = None
            if ref:
                try:
                    from .models import LigneVente
                    ligne_vente = LigneVente.objects.filter(
                        vente__numero_facture=ref,
                        article=article
                    ).first()
                    if ligne_vente:
                        valeur_reelle = ligne_vente.prix_unitaire * Decimal(str(abs(instance.quantite)))
                except Exception:
                    pass
            jvs.enregistrer_vente(boutique, valeur_reelle if valeur_reelle is not None else valeur, date_mouv)

        elif type_mouv == 'ENTREE':
            if ref.startswith('TRANSFERT-'):
                jvs.enregistrer_transfert_entrant(boutique, valeur, date_mouv)
            else:
                jvs.enregistrer_approvisionnement(boutique, valeur, date_mouv)

        elif type_mouv == 'SORTIE':
            if ref.startswith('TRANSFERT-'):
                jvs.enregistrer_transfert_sortant(boutique, valeur, date_mouv)
            else:
                jvs.enregistrer_sortie_manuelle(boutique, valeur, date_mouv)

        elif type_mouv == 'AJUSTEMENT':
            # quantite signé : positif = ajout de valeur, négatif = retrait
            impact = prix_vente * Decimal(str(instance.quantite))
            jvs.enregistrer_inventaire(boutique, impact, date_mouv)

        elif type_mouv == 'RETOUR':
            # Retour client = réentrée de stock
            jvs.enregistrer_approvisionnement(boutique, valeur, date_mouv)

    except Exception as e:
        logger.error(f"[JournalValeurStock] Erreur lors de l'enregistrement du mouvement {instance.pk}: {e}")


@receiver(post_save, sender=MouvementStock)
def synchroniser_inventaire_en_cours(sender, instance, created, **kwargs):
    """
    Quand un mouvement de stock se produit (vente, transfert, etc.),
    met à jour le stock_theorique des lignes d'inventaire EN_COURS
    pour que l'inventaire reste synchronisé avec les ventes.
    """
    if not created:
        return

    article = instance.article
    if not article or not article.boutique:
        return

    # Trouver les inventaires en cours pour cette boutique
    inventaires_en_cours = Inventaire.objects.filter(
        boutique=article.boutique,
        statut='EN_COURS'
    )

    for inventaire in inventaires_en_cours:
        lignes = LigneInventaire.objects.filter(
            inventaire=inventaire,
            article=article
        )
        for ligne in lignes:
            # Mettre à jour le stock théorique avec le stock actuel de l'article
            ligne.stock_theorique = article.quantite_stock
            # Recalculer l'écart si stock physique déjà saisi
            if ligne.stock_physique is not None:
                ligne.ecart = ligne.stock_physique - ligne.stock_theorique
                ligne.valeur_ecart = ligne.ecart * ligne.prix_unitaire
            ligne.save(update_fields=['stock_theorique', 'ecart', 'valeur_ecart'])
            logger.info(
                f"[Inventaire] Stock théorique mis à jour pour {article.nom}: "
                f"{ligne.stock_theorique} (inventaire {inventaire.reference})"
            )


# Stockage temporaire du prix_vente avant modification
_prix_vente_avant_save = {}


@receiver(pre_save, sender=Article)
def capturer_prix_vente_avant_modification(sender, instance, **kwargs):
    """Capture le prix de vente avant modification pour calculer l'impact sur la valeur du stock."""
    if instance.pk:
        try:
            ancien = Article.objects.get(pk=instance.pk)
            _prix_vente_avant_save[instance.pk] = ancien.prix_vente
        except Article.DoesNotExist:
            pass


@receiver(post_save, sender=Article)
def enregistrer_impact_modification_prix_vente(sender, instance, created, **kwargs):
    """
    Quand le prix de vente d'un article change, enregistre l'impact
    sur la valeur du stock dans le journal (nouveau_pv - ancien_pv) * qté_stock.
    """
    if created:
        _prix_vente_avant_save.pop(instance.pk, None)
        return

    if not instance.boutique:
        _prix_vente_avant_save.pop(instance.pk, None)
        return

    ancien_prix_vente = _prix_vente_avant_save.pop(instance.pk, None)
    if not ancien_prix_vente:
        return

    if ancien_prix_vente == instance.prix_vente:
        return

    try:
        impact = (
            Decimal(str(instance.prix_vente)) - Decimal(str(ancien_prix_vente))
        ) * Decimal(str(instance.quantite_stock))
        jvs.enregistrer_modification_prix(instance.boutique, impact)
        logger.info(
            f"[JournalValeurStock] Impact prix vente {instance.nom}: {impact} FC"
        )
    except Exception as e:
        logger.error(f"[JournalValeurStock] Erreur impact prix vente article {instance.pk}: {e}")
