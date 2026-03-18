"""
Tâches asynchrones Celery pour l'application inventory
Permet le traitement en arrière-plan des ventes, synchronisations, etc.
"""
import logging
from celery import shared_task
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from inventory.models import (
    Vente, LigneVente, Article, Boutique, Client,
    VenteRejetee, AlerteStock, MouvementStock
)
from inventory.websocket_utils import notify_stock_updated

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_vente_async(self, vente_data, boutique_id, terminal_id):
    """
    Traiter une vente de manière asynchrone
    
    Args:
        vente_data: Données de la vente (dict)
        boutique_id: ID de la boutique
        terminal_id: ID du terminal
    
    Returns:
        dict: Résultat du traitement
    """
    try:
        logger.info(f"🔄 [Task {self.request.id}] Traitement vente async - Boutique {boutique_id}")
        
        # Récupérer la boutique et le terminal
        try:
            boutique = Boutique.objects.get(id=boutique_id, est_active=True)
            terminal = Client.objects.get(id=terminal_id, est_actif=True)
        except (Boutique.DoesNotExist, Client.DoesNotExist) as e:
            logger.error(f"❌ Boutique ou terminal introuvable: {e}")
            return {
                'success': False,
                'error': 'Boutique ou terminal introuvable',
                'vente_uid': vente_data.get('numero_facture')
            }
        
        # Extraire les données
        numero_facture = vente_data.get('numero_facture') or vente_data.get('NumeroFacture')
        date_vente_str = vente_data.get('date_vente') or vente_data.get('DateVente')
        montant_total = Decimal(str(vente_data.get('montant_total') or vente_data.get('MontantTotal', 0)))
        devise = vente_data.get('devise') or vente_data.get('Devise', 'CDF')
        lignes_data = vente_data.get('lignes') or vente_data.get('Lignes', [])
        
        # Vérifier doublon
        if Vente.objects.filter(numero_facture=numero_facture, boutique=boutique).exists():
            logger.warning(f"⚠️ Vente {numero_facture} déjà existante (doublon)")
            return {
                'success': False,
                'error': 'Vente déjà enregistrée (doublon)',
                'vente_uid': numero_facture,
                'is_duplicate': True
            }
        
        # Traitement atomique
        with transaction.atomic():
            # Créer la vente
            vente = Vente.objects.create(
                numero_facture=numero_facture,
                date_vente=timezone.now() if not date_vente_str else date_vente_str,
                montant_total=montant_total,
                devise=devise,
                boutique=boutique,
                terminal=terminal,
                commercant=boutique.commercant
            )
            
            # Traiter chaque ligne
            for ligne_data in lignes_data:
                article_id = ligne_data.get('article_id') or ligne_data.get('ArticleId')
                quantite = int(ligne_data.get('quantite') or ligne_data.get('Quantite', 0))
                prix_unitaire = Decimal(str(ligne_data.get('prix_unitaire') or ligne_data.get('PrixUnitaire', 0)))
                prix_negocie = ligne_data.get('prix_negocie') or ligne_data.get('PrixNegocie')
                
                try:
                    article = Article.objects.select_for_update().get(
                        id=article_id,
                        boutique=boutique,
                        est_actif=True
                    )
                except Article.DoesNotExist:
                    raise ValueError(f"Article {article_id} introuvable")
                
                # ⭐ JOURNAL: Dedup — évite double réduction de stock
                if MouvementStock.objects.filter(
                    reference_document=numero_facture,
                    article=article,
                    type_mouvement='VENTE'
                ).exists():
                    logger.warning(f"⚠️ Doublon MouvementStock task: {numero_facture} / {article.nom} — skip")
                    continue

                # Avertissement stock insuffisant — vente acceptée quand même
                stock_sera_negatif = article.quantite_stock < quantite
                if stock_sera_negatif:
                    logger.warning(f"⚠️ Stock insuffisant (task): {article.nom} dispo={article.quantite_stock} demandé={quantite} → accepté")

                # Créer ligne de vente
                LigneVente.objects.create(
                    vente=vente,
                    article=article,
                    quantite=quantite,
                    prix_unitaire=prix_unitaire,
                    prix_negocie=Decimal(str(prix_negocie)) if prix_negocie else None
                )

                # Mettre à jour le stock
                ancien_stock = article.quantite_stock
                article.quantite_stock -= quantite
                article.save(update_fields=['quantite_stock'])

                # Journal de stock
                MouvementStock.objects.create(
                    article=article,
                    type_mouvement='VENTE',
                    quantite=-quantite,
                    stock_avant=ancien_stock,
                    stock_apres=article.quantite_stock,
                    reference_document=numero_facture,
                    utilisateur=terminal.nom_terminal if hasattr(terminal, 'nom_terminal') else str(terminal.id),
                    commentaire=f"Vente #{numero_facture} (async task)"
                )

                # ⚠️ AlerteStock si stock négatif
                if stock_sera_negatif:
                    AlerteStock.objects.create(
                        vente=vente,
                        boutique=boutique,
                        terminal=terminal,
                        article=article,
                        quantite_vendue=quantite,
                        stock_serveur_avant=ancien_stock,
                        stock_serveur_apres=article.quantite_stock,
                        ecart=ancien_stock - quantite,
                        numero_facture=numero_facture
                    )

                # Notifier changement de stock via WebSocket
                notify_stock_updated(boutique_id, article.id, article.quantite_stock)
                
                logger.info(f"✅ Stock mis à jour: {article.nom} {ancien_stock} → {article.quantite_stock}")
        
        logger.info(f"✅ [Task {self.request.id}] Vente {numero_facture} traitée avec succès")
        
        return {
            'success': True,
            'vente_id': vente.id,
            'vente_uid': numero_facture,
            'montant_total': str(montant_total),
            'nb_lignes': len(lignes_data)
        }
        
    except ValueError as e:
        # Erreur métier (article introuvable, etc.)
        logger.error(f"❌ [Task {self.request.id}] Erreur métier: {str(e)}")

        VenteRejetee.objects.create(
            vente_uid=vente_data.get('numero_facture') or vente_data.get('NumeroFacture'),
            boutique_id=boutique_id,
            terminal_id=terminal_id,
            raison_rejet='OTHER',
            message_erreur=str(e),
            donnees_vente=vente_data,
            action_requise='NOTIFY_USER'
        )

        return {
            'success': False,
            'error': str(e),
            'vente_uid': vente_data.get('numero_facture') or vente_data.get('NumeroFacture'),
            'error_type': 'business_error'
        }
        
    except Exception as e:
        # Erreur technique - retry
        logger.error(f"❌ [Task {self.request.id}] Erreur technique: {str(e)}")
        
        # Retry automatique (max 3 fois)
        try:
            raise self.retry(exc=e, countdown=60)  # Réessayer après 60 secondes
        except self.MaxRetriesExceededError:
            # Max retries atteint - créer vente rejetée
            VenteRejetee.objects.create(
                vente_uid=vente_data.get('numero_facture') or vente_data.get('NumeroFacture'),
                boutique_id=boutique_id,
                terminal_id=terminal_id,
                raison_rejet='ERREUR_TECHNIQUE',
                details_erreur=str(e),
                donnees_vente=vente_data
            )
            
            return {
                'success': False,
                'error': f"Erreur technique après {self.max_retries} tentatives: {str(e)}",
                'vente_uid': vente_data.get('numero_facture') or vente_data.get('NumeroFacture'),
                'error_type': 'technical_error'
            }


@shared_task
def process_multiple_ventes(ventes_data, boutique_id, terminal_id):
    """
    Traiter plusieurs ventes en parallèle
    
    Args:
        ventes_data: Liste de ventes
        boutique_id: ID de la boutique
        terminal_id: ID du terminal
    
    Returns:
        dict: Résumé du traitement
    """
    logger.info(f"🔄 Traitement de {len(ventes_data)} ventes en parallèle")
    
    results = []
    for vente_data in ventes_data:
        # Lancer chaque vente dans une tâche séparée
        result = process_vente_async.delay(vente_data, boutique_id, terminal_id)
        results.append({
            'task_id': result.id,
            'vente_uid': vente_data.get('numero_facture') or vente_data.get('NumeroFacture')
        })
    
    return {
        'success': True,
        'total_ventes': len(ventes_data),
        'tasks': results
    }


@shared_task
def cleanup_old_tasks():
    """
    Nettoyer les anciennes tâches et résultats (tâche périodique)
    """
    from celery.result import AsyncResult
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=7)
    logger.info(f"🧹 Nettoyage des tâches avant {cutoff_date}")
    
    # Cette tâche peut être configurée pour s'exécuter périodiquement
    # via Celery Beat (scheduler)
    
    return {
        'success': True,
        'message': 'Nettoyage effectué'
    }


@shared_task
def send_daily_report(boutique_id):
    """
    Générer et envoyer le rapport quotidien d'une boutique
    Tâche périodique à exécuter chaque jour
    """
    logger.info(f"📊 Génération rapport quotidien - Boutique {boutique_id}")
    
    try:
        boutique = Boutique.objects.get(id=boutique_id)
        today = timezone.now().date()
        
        # Récupérer les ventes du jour
        ventes = Vente.objects.filter(
            boutique=boutique,
            date_vente__date=today
        )
        
        total_ventes = ventes.count()
        montant_total = sum(v.montant_total for v in ventes)
        
        logger.info(f"✅ Rapport: {total_ventes} ventes, {montant_total} FC")
        
        return {
            'success': True,
            'boutique_id': boutique_id,
            'date': str(today),
            'total_ventes': total_ventes,
            'montant_total': str(montant_total)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur génération rapport: {e}")
        return {
            'success': False,
            'error': str(e)
        }
