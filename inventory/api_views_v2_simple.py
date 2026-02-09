"""
API v2 Multi-Boutiques SIMPLIFIÉE (Sans Authentification)
========================================================

Version simplifiée pour tests et développement initial.
L'authentification sera ajoutée plus tard.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db.models import Sum, Q
from django.db import transaction, IntegrityError  # ⭐ Pour les transactions atomiques et gestion des doublons
from django.conf import settings
import json
import logging

from .models import Client, Boutique, Article, Categorie, Vente, LigneVente, MouvementStock, ArticleNegocie, RetourArticle, VenteRejetee, VarianteArticle
from .serializers import ArticleSerializer, CategorieSerializer, VenteSerializer, ArticleNegocieSerializer, RetourArticleSerializer

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_status_v2_simple(request):
    """
    Endpoint de diagnostic pour l'API v2 simplifiée
    """
    return Response({
        'api_version': 'v2-simple',
        'status': 'active',
        'message': 'API v2 Multi-Boutiques SIMPLIFIÉE (sans authentification)',
        'authentication': 'disabled',
        'endpoints': {
            'status': '/api/v2/simple/status/',
            'articles': '/api/v2/simple/articles/?boutique_id=X',
            'categories': '/api/v2/simple/categories/?boutique_id=X',
            'ventes': '/api/v2/simple/ventes/',
            'boutiques': '/api/v2/simple/boutiques/',
            'terminal_info': '/api/v2/simple/terminal/<numero_serie>/'
        },
        'note': 'Aucune authentification requise - Version de développement'
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def boutiques_list_simple(request):
    """
    Liste de toutes les boutiques disponibles
    """
    try:
        boutiques = Boutique.objects.filter(est_active=True)
        
        boutiques_data = []
        for boutique in boutiques:
            # Compter les terminaux et articles
            nb_terminaux = boutique.clients.filter(est_actif=True).count()
            nb_articles = boutique.articles.filter(est_actif=True).count()
            
            boutiques_data.append({
                'id': boutique.id,
                'nom': boutique.nom,
                'type_commerce': boutique.type_commerce,
                'ville': boutique.ville,
                'adresse': boutique.adresse,
                'devise': boutique.devise,
                'nb_terminaux': nb_terminaux,
                'nb_articles': nb_articles,
                'est_active': boutique.est_active
            })
        
        return Response({
            'success': True,
            'count': len(boutiques_data),
            'boutiques': boutiques_data
        })
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des boutiques: {str(e)}")
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def pos_status_simple(request):
    boutique_id = request.GET.get('boutique_id')
    numero_serie = request.GET.get('numero_serie')
    if not boutique_id and not numero_serie:
        numero_serie = (
            request.headers.get('X-Device-Serial') or
            request.headers.get('Device-Serial') or
            request.headers.get('Serial-Number') or
            request.META.get('HTTP_X_DEVICE_SERIAL') or
            request.META.get('HTTP_DEVICE_SERIAL')
        )
    boutique = None
    terminal = None
    try:
        if boutique_id:
            boutique = get_object_or_404(Boutique, id=boutique_id)
        elif numero_serie:
            terminal = Client.objects.select_related('boutique').filter(
                numero_serie=numero_serie
            ).first()
            if terminal and terminal.boutique:
                boutique = terminal.boutique
        if not boutique:
            return Response({
                'success': False,
                'code': 'POS_UNKNOWN_BOUTIQUE',
                'message': 'Boutique introuvable pour ce terminal',
                'numero_serie': numero_serie
            }, status=status.HTTP_404_NOT_FOUND)
        if not boutique.est_active:
            return Response({
                'success': False,
                'code': 'POS_BOUTIQUE_INACTIVE',
                'message': 'Boutique désactivée, POS indisponible',
                'boutique_id': boutique.id
            }, status=status.HTTP_403_FORBIDDEN)
        if not boutique.pos_autorise:
            return Response({
                'success': True,
                'pos_allowed': False,
                'code': 'POS_DISABLED',
                'message': 'POS désactivé au niveau de la boutique',
                'boutique_id': boutique.id
            }, status=status.HTTP_200_OK)
        return Response({
            'success': True,
            'pos_allowed': True,
            'code': 'POS_OK',
            'message': 'POS autorisé pour cette boutique',
            'boutique_id': boutique.id
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Erreur lors de la vérification POS: {str(e)}")
        return Response({
            'success': False,
            'code': 'POS_INTERNAL_ERROR',
            'message': 'Erreur interne du serveur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def terminal_info_simple(request, numero_serie):
    """
    Informations sur un terminal MAUI par son numéro de série
    """
    try:
        terminal = Client.objects.select_related('boutique').get(
            numero_serie=numero_serie
        )
        
        return Response({
            'success': True,
            'terminal': {
                'id': terminal.id,
                'numero_serie': terminal.numero_serie,
                'nom_terminal': terminal.nom_terminal,
                'est_actif': terminal.est_actif,
                'version_app_maui': terminal.version_app_maui,
                'derniere_activite': terminal.derniere_activite.isoformat() if terminal.derniere_activite else None
            },
            'boutique': {
                'id': terminal.boutique.id,
                'nom': terminal.boutique.nom,
                'type_commerce': terminal.boutique.type_commerce,
                'ville': terminal.boutique.ville,
                'devise': terminal.boutique.devise
            } if terminal.boutique else None
        })
        
    except Client.DoesNotExist:
        return Response({
            'error': 'Terminal non trouvé',
            'code': 'TERMINAL_NOT_FOUND'
        }, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du terminal: {str(e)}")
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def articles_by_serial_simple(request, numero_serie):
    """
    Liste des articles d'une boutique via le numéro de série du terminal (SANS AUTHENTIFICATION)
    Endpoint ultra-simple pour MAUI
    """
    try:
        # Récupérer le terminal par son numéro de série
        terminal = Client.objects.select_related('boutique').filter(
            numero_serie=numero_serie,
            est_actif=True
        ).first()
        
        if not terminal:
            return Response({
                'success': False,
                'error': 'Terminal non trouvé ou inactif',
                'code': 'TERMINAL_NOT_FOUND',
                'numero_serie': numero_serie
            }, status=status.HTTP_404_NOT_FOUND)
        
        if not terminal.boutique:
            return Response({
                'success': False,
                'error': 'Terminal non associé à une boutique',
                'code': 'NO_BOUTIQUE',
                'numero_serie': numero_serie
            }, status=status.HTTP_400_BAD_REQUEST)
        
        boutique = terminal.boutique
        
        # Récupérer les articles de cette boutique
        articles = Article.objects.filter(
            boutique=boutique,
            est_actif=True
        ).select_related('categorie').order_by('nom')
        
        # Sérialiser les articles
        articles_data = ArticleSerializer(articles, many=True).data
        
        logger.info(f"✅ Articles récupérés pour terminal {numero_serie}: {articles.count()} articles")
        
        return Response({
            'success': True,
            'count': articles.count(),
            'boutique_id': boutique.id,
            'boutique_nom': boutique.nom,
            'taux_dollar': str(boutique.commercant.taux_dollar),
            'terminal': {
                'numero_serie': terminal.numero_serie,
                'nom_terminal': terminal.nom_terminal
            },
            'articles': articles_data
        })
        
    except Exception as e:
        logger.error(f"❌ Erreur récupération articles pour {numero_serie}: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def articles_list_simple(request):
    """
    Liste des articles d'une boutique (sans authentification)
    Supporte 2 modes:
    1. Par boutique_id: /api/v2/simple/articles/?boutique_id=2
    2. Par numéro de série (header): X-Device-Serial ou Device-Serial
    """
    boutique_id = request.GET.get('boutique_id')
    
    # Si pas de boutique_id, essayer de récupérer via le numéro de série dans les headers
    if not boutique_id:
        # Chercher le numéro de série dans les headers
        numero_serie = (
            request.headers.get('X-Device-Serial') or 
            request.headers.get('Device-Serial') or
            request.headers.get('Serial-Number') or
            request.META.get('HTTP_X_DEVICE_SERIAL') or
            request.META.get('HTTP_DEVICE_SERIAL')
        )
        
        if numero_serie:
            logger.info(f"🔍 Tentative de récupération articles via numéro de série: {numero_serie}")
            
            # Récupérer le terminal et sa boutique
            try:
                terminal = Client.objects.select_related('boutique').filter(
                    numero_serie=numero_serie,
                    est_actif=True
                ).first()
                
                if terminal and terminal.boutique:
                    boutique_id = terminal.boutique.id
                    logger.info(f"✅ Terminal trouvé: {terminal.nom_terminal} → Boutique ID: {boutique_id}")
                else:
                    logger.warning(f"⚠️ Terminal non trouvé ou sans boutique: {numero_serie}")
            except Exception as e:
                logger.error(f"❌ Erreur recherche terminal: {str(e)}")
    
    if not boutique_id:
        return Response({
            'error': 'Paramètre boutique_id requis OU numéro de série dans les headers',
            'code': 'MISSING_BOUTIQUE_ID',
            'examples': {
                'method1': '/api/v2/simple/articles/?boutique_id=2',
                'method2': 'Header: X-Device-Serial: VOTRE_NUMERO_SERIE'
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Vérifier que la boutique existe
        boutique = get_object_or_404(Boutique, id=boutique_id, est_active=True)
        
        # Récupérer les articles de cette boutique
        articles = Article.objects.filter(
            boutique=boutique,
            est_actif=True
        ).select_related('categorie').order_by('nom')
        
        # Sérialiser les articles
        articles_data = ArticleSerializer(articles, many=True).data
        
        return Response({
            'success': True,
            'count': articles.count(),
            'boutique_id': boutique.id,
            'boutique_nom': boutique.nom,
            'taux_dollar': str(boutique.commercant.taux_dollar),
            'articles': articles_data
        })
        
    except Boutique.DoesNotExist:
        return Response({
            'error': 'Boutique non trouvée',
            'code': 'BOUTIQUE_NOT_FOUND'
        }, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des articles: {str(e)}")
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def articles_deleted_simple(request):
    """
    Liste des IDs d'articles supprimés/désactivés pour synchronisation MAUI
    
    Paramètres:
    - boutique_id: ID de la boutique (requis ou via header X-Device-Serial)
    - since: Date ISO depuis laquelle récupérer les suppressions (optionnel)
    
    Exemple: /api/v2/simple/articles/deleted/?boutique_id=2&since=2025-12-01T00:00:00
    """
    boutique_id = request.GET.get('boutique_id')
    since = request.GET.get('since')
    
    # Si pas de boutique_id, essayer via le numéro de série
    if not boutique_id:
        numero_serie = (
            request.headers.get('X-Device-Serial') or 
            request.headers.get('Device-Serial') or
            request.META.get('HTTP_X_DEVICE_SERIAL')
        )
        
        if numero_serie:
            try:
                terminal = Client.objects.select_related('boutique').filter(
                    numero_serie=numero_serie,
                    est_actif=True
                ).first()
                
                if terminal and terminal.boutique:
                    boutique_id = terminal.boutique.id
            except Exception as e:
                logger.error(f"❌ Erreur recherche terminal: {str(e)}")
    
    if not boutique_id:
        return Response({
            'error': 'Paramètre boutique_id requis',
            'code': 'MISSING_BOUTIQUE_ID'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        boutique = get_object_or_404(Boutique, id=boutique_id, est_active=True)
        
        # Récupérer les articles désactivés de cette boutique
        articles_query = Article.objects.filter(
            boutique=boutique,
            est_actif=False,
            date_suppression__isnull=False
        )
        
        # Filtrer par date si fourni
        if since:
            try:
                since_date = parse_datetime(since)
                if since_date:
                    articles_query = articles_query.filter(date_suppression__gte=since_date)
            except Exception:
                pass
        
        # Récupérer les IDs et infos minimales
        deleted_articles = articles_query.values('id', 'code', 'nom', 'date_suppression')
        
        deleted_data = []
        for article in deleted_articles:
            deleted_data.append({
                'id': article['id'],
                'code': article['code'],
                'nom': article['nom'],
                'date_suppression': article['date_suppression'].isoformat() if article['date_suppression'] else None
            })
        
        logger.info(f"📍 Articles supprimés récupérés pour boutique {boutique_id}: {len(deleted_data)}")
        
        return Response({
            'success': True,
            'boutique_id': boutique.id,
            'count': len(deleted_data),
            'deleted_articles': deleted_data,
            'message': 'MAUI doit supprimer ces articles de son cache local'
        })
        
    except Exception as e:
        logger.error(f"Erreur récupération articles supprimés: {str(e)}")
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def variantes_list_simple(request):
    """
    Liste des variantes d'articles d'une boutique pour synchronisation MAUI
    
    Paramètres:
    - boutique_id: ID de la boutique (requis ou via header X-Device-Serial)
    
    Exemple: /api/v2/simple/variantes/?boutique_id=2
    """
    boutique_id = request.GET.get('boutique_id')
    
    # Si pas de boutique_id, essayer via le numéro de série
    if not boutique_id:
        numero_serie = (
            request.headers.get('X-Device-Serial') or 
            request.headers.get('Device-Serial') or
            request.META.get('HTTP_X_DEVICE_SERIAL')
        )
        
        if numero_serie:
            try:
                terminal = Client.objects.select_related('boutique').filter(
                    numero_serie=numero_serie,
                    est_actif=True
                ).first()
                
                if terminal and terminal.boutique:
                    boutique_id = terminal.boutique.id
            except Exception as e:
                logger.error(f"❌ Erreur recherche terminal: {str(e)}")
    
    if not boutique_id:
        return Response({
            'error': 'Paramètre boutique_id requis',
            'code': 'MISSING_BOUTIQUE_ID'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        boutique = get_object_or_404(Boutique, id=boutique_id, est_active=True)
        
        # Récupérer toutes les variantes actives des articles de cette boutique
        variantes = VarianteArticle.objects.filter(
            article_parent__boutique=boutique,
            est_actif=True
        ).select_related('article_parent')
        
        variantes_data = []
        for variante in variantes:
            variantes_data.append({
                'id': variante.id,
                'article_parent_id': variante.article_parent.id,
                'code_barre': variante.code_barre,
                'nom_variante': variante.nom_variante,
                'type_attribut': variante.type_attribut,
                'quantite_stock': variante.quantite_stock,
                'est_actif': variante.est_actif,
                'prix_vente': str(variante.prix_vente),
                'devise': variante.devise,
                'nom_complet': variante.nom_complet
            })
        
        logger.info(f"🏷️ Variantes récupérées pour boutique {boutique_id}: {len(variantes_data)}")
        
        return Response({
            'success': True,
            'boutique_id': boutique.id,
            'count': len(variantes_data),
            'variantes': variantes_data
        })
        
    except Exception as e:
        logger.error(f"❌ Erreur récupération variantes: {str(e)}")
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def categories_list_simple(request):
    """
    Liste des catégories d'une boutique (sans authentification)
    Supporte 2 modes:
    1. Par boutique_id: /api/v2/simple/categories/?boutique_id=2
    2. Par numéro de série (header): X-Device-Serial ou Device-Serial
    """
    boutique_id = request.GET.get('boutique_id')
    
    # Si pas de boutique_id, essayer de récupérer via le numéro de série dans les headers
    if not boutique_id:
        # Chercher le numéro de série dans les headers
        numero_serie = (
            request.headers.get('X-Device-Serial') or 
            request.headers.get('Device-Serial') or
            request.headers.get('Serial-Number') or
            request.META.get('HTTP_X_DEVICE_SERIAL') or
            request.META.get('HTTP_DEVICE_SERIAL')
        )
        
        if numero_serie:
            logger.info(f"🔍 Tentative de récupération catégories via numéro de série: {numero_serie}")
            
            # Récupérer le terminal et sa boutique
            try:
                terminal = Client.objects.select_related('boutique').filter(
                    numero_serie=numero_serie,
                    est_actif=True
                ).first()
                
                if terminal and terminal.boutique:
                    boutique_id = terminal.boutique.id
                    logger.info(f"✅ Terminal trouvé: {terminal.nom_terminal} → Boutique ID: {boutique_id}")
                else:
                    logger.warning(f"⚠️ Terminal non trouvé ou sans boutique: {numero_serie}")
            except Exception as e:
                logger.error(f"❌ Erreur recherche terminal: {str(e)}")
    
    if not boutique_id:
        return Response({
            'error': 'Paramètre boutique_id requis OU numéro de série dans les headers',
            'code': 'MISSING_BOUTIQUE_ID',
            'examples': {
                'method1': '/api/v2/simple/categories/?boutique_id=2',
                'method2': 'Header: X-Device-Serial: VOTRE_NUMERO_SERIE'
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Vérifier que la boutique existe
        boutique = get_object_or_404(Boutique, id=boutique_id, est_active=True)
        
        # Récupérer les catégories de cette boutique
        categories = Categorie.objects.filter(
            boutique=boutique
        ).order_by('nom')
        
        # Sérialiser les catégories
        categories_data = CategorieSerializer(categories, many=True).data
        
        return Response({
            'success': True,
            'count': categories.count(),
            'boutique_id': boutique.id,
            'boutique_nom': boutique.nom,
            'categories': categories_data
        })
        
    except Boutique.DoesNotExist:
        return Response({
            'error': 'Boutique non trouvée',
            'code': 'BOUTIQUE_NOT_FOUND'
        }, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des catégories: {str(e)}")
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def create_vente_simple(request):
    """
    Créer une vente (sans authentification)
    Supporte 2 modes:
    1. Par boutique_id + numero_serie dans le body
    2. Par numéro de série dans le header X-Device-Serial
    """
    # Logs de debug
    logger.info(f"🔍 Création vente - Headers: {dict(request.headers)}")
    logger.info(f"🔍 Création vente - Body: {request.data}")
    
    boutique_id = request.data.get('boutique_id')
    numero_serie = request.data.get('numero_serie')
    
    # Si pas de numéro de série dans le body, chercher dans les headers
    if not numero_serie:
        numero_serie = (
            request.headers.get('X-Device-Serial') or 
            request.headers.get('Device-Serial') or
            request.headers.get('Serial-Number') or
            request.META.get('HTTP_X_DEVICE_SERIAL') or
            request.META.get('HTTP_DEVICE_SERIAL')
        )
        logger.info(f"🔍 Numéro série détecté dans headers: {numero_serie}")
    else:
        logger.info(f"🔍 Numéro série dans body: {numero_serie}")
    
    if not numero_serie:
        logger.warning(f"⚠️ Aucun numéro de série trouvé - Headers: {list(request.headers.keys())}")
        return Response({
            'error': 'Paramètre numero_serie requis (body ou header)',
            'code': 'MISSING_SERIAL',
            'examples': {
                'method1': 'Body: {"numero_serie": "XXX", ...}',
                'method2': 'Header: X-Device-Serial: XXX'
            },
            'debug': {
                'headers_received': list(request.headers.keys()),
                'body_keys': list(request.data.keys())
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Si pas de boutique_id, le récupérer via le terminal
    if not boutique_id:
        try:
            terminal = Client.objects.select_related('boutique').filter(
                numero_serie=numero_serie,
                est_actif=True
            ).first()
            
            if terminal and terminal.boutique:
                boutique_id = terminal.boutique.id
                logger.info(f"✅ Boutique détectée automatiquement: {boutique_id} pour terminal {numero_serie}")
            else:
                return Response({
                    'error': 'Terminal non trouvé ou sans boutique',
                    'code': 'TERMINAL_NOT_FOUND'
                }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"❌ Erreur détection boutique: {str(e)}")
    
    if not boutique_id:
        return Response({
            'error': 'Impossible de déterminer la boutique',
            'code': 'MISSING_BOUTIQUE_ID'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Vérifier que la boutique existe
        boutique = get_object_or_404(Boutique, id=boutique_id, est_active=True)
        
        # Vérifier que le terminal existe et appartient à cette boutique
        terminal = Client.objects.filter(
            numero_serie=numero_serie,
            boutique=boutique,
            est_actif=True
        ).first()
        
        if not terminal:
            return Response({
                'error': 'Terminal non trouvé pour cette boutique',
                'code': 'TERMINAL_NOT_FOUND'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Préparer les données de vente
        vente_data = request.data.copy()
        
        # Générer numéro de facture si absent
        numero_facture = vente_data.get('numero_facture')
        if not numero_facture:
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            numero_facture = f"VENTE-{boutique.id}-{timestamp}"
            logger.info(f"📝 Numéro de facture généré automatiquement: {numero_facture}")
        
        # ⭐ TRANSACTION ATOMIQUE : Tout ou rien
        with transaction.atomic():
            # ⭐ CRÉER LA VENTE AVEC ISOLATION PAR BOUTIQUE
            date_str = vente_data.get('date_vente') or vente_data.get('date')
            if date_str:
                date_vente = parse_datetime(date_str)
                if date_vente is None:
                    date_vente = timezone.now()
                elif timezone.is_naive(date_vente):
                    # Interpréter la date naïve comme étant dans le timezone de Django (Europe/Paris)
                    date_vente = timezone.make_aware(date_vente)
                else:
                    # Si la date est déjà aware, s'assurer qu'elle est dans le bon timezone
                    date_vente = date_vente.astimezone(timezone.get_current_timezone())
            else:
                date_vente = timezone.now()
            
            # Déterminer la devise de la vente
            devise_vente = vente_data.get('devise', 'CDF')
            
            vente = Vente.objects.create(
                numero_facture=numero_facture,
                date_vente=date_vente,
                montant_total=0,  # Sera calculé avec les lignes
                montant_total_usd=0 if devise_vente == 'USD' else None,
                devise=devise_vente,
                mode_paiement=vente_data.get('mode_paiement', 'CASH'),
                paye=vente_data.get('paye', True),
                boutique=boutique,  # ⭐ ISOLATION: Lien direct avec la boutique
                client_maui=terminal,
                adresse_ip_client=request.META.get('REMOTE_ADDR'),
                version_app_maui=terminal.version_app_maui
            )
            logger.info(f"✅ Vente créée avec boutique: {boutique.nom} (ID: {boutique.id})")
            
            montant_total = 0
            montant_total_usd = 0
            lignes_creees = []
            
            # Traiter chaque ligne de vente
            for ligne_data in vente_data.get('lignes', []):
                article_id = ligne_data.get('article_id')
                quantite = ligne_data.get('quantite', 1)
                
                # Vérifier que l'article appartient à la boutique
                try:
                    article = Article.objects.get(
                        id=article_id,
                        boutique=boutique,
                        est_actif=True
                    )
                except Article.DoesNotExist:
                    # La transaction sera automatiquement annulée
                    raise Exception(f'Article {article_id} non trouvé dans cette boutique')
                
                # Vérifier le stock disponible
                if article.quantite_stock < quantite:
                    # La transaction sera automatiquement annulée
                    raise Exception(f'Stock insuffisant pour {article.nom}')
                
                # Créer la ligne de vente avec support USD
                devise_ligne = ligne_data.get('devise', devise_vente)
                
                # ⭐ Déterminer les prix selon la devise
                if devise_ligne == 'USD':
                    # Pour vente USD: le prix principal EST en USD
                    # Priorité: prix_unitaire_usd > prix_unitaire (si envoyé comme USD) > article.prix_vente_usd
                    prix_unitaire_usd = (
                        ligne_data.get('prix_unitaire_usd') or 
                        ligne_data.get('prix_unitaire') or  # ⭐ MAUI peut envoyer le prix USD ici
                        article.prix_vente_usd or 
                        0
                    )
                    prix_unitaire = 0  # Pas de CDF pour vente USD
                    logger.info(f"💵 Ligne USD: prix_unitaire_usd={prix_unitaire_usd}")
                else:
                    # Pour vente CDF: utiliser prix_unitaire comme prix principal
                    prix_unitaire = ligne_data.get('prix_unitaire') or article.prix_vente
                    prix_unitaire_usd = ligne_data.get('prix_unitaire_usd') or article.prix_vente_usd or 0
                
                # 💰 Gérer les négociations
                prix_original = ligne_data.get('prix_original') or ligne_data.get('prixOriginal')
                est_negocie = ligne_data.get('est_negocie') or ligne_data.get('estNegocie', False)
                motif_reduction = ligne_data.get('motif_reduction') or ligne_data.get('motifReduction') or ''
                
                # 🔍 Auto-détection: si prix_original non fourni, utiliser le prix de l'article
                if not prix_original:
                    prix_original = float(article.prix_vente if devise_ligne != 'USD' else (article.prix_vente_usd or 0))
                
                # Auto-détection si prix négocié (prix différent du prix original)
                try:
                    prix_orig_decimal = float(prix_original)
                    prix_unit_decimal = float(prix_unitaire if devise_ligne != 'USD' else prix_unitaire_usd)
                    if abs(prix_orig_decimal - prix_unit_decimal) > 0.01:
                        est_negocie = True
                        logger.info(f"💰 RÉDUCTION DÉTECTÉE: {article.nom} - Original: {prix_orig_decimal} → Vendu: {prix_unit_decimal}")
                except (ValueError, TypeError):
                    pass
                
                ligne_vente = LigneVente.objects.create(
                    vente=vente,
                    article=article,
                    quantite=quantite,
                    prix_unitaire=prix_unitaire,
                    prix_unitaire_usd=prix_unitaire_usd,
                    devise=devise_ligne,
                    prix_original=prix_original,
                    est_negocie=est_negocie,
                    motif_reduction=motif_reduction
                )
                
                # Mettre à jour le stock
                stock_avant = article.quantite_stock  # ⭐ Capturer AVANT la modification
                article.quantite_stock -= quantite
                article.save(update_fields=['quantite_stock'])
                
                # Créer un mouvement de stock avec traçabilité complète
                symbole_devise = '$' if devise_ligne == 'USD' else 'FC'
                prix_affiche = prix_unitaire_usd if devise_ligne == 'USD' else prix_unitaire
                MouvementStock.objects.create(
                    article=article,
                    type_mouvement='VENTE',
                    quantite=-quantite,
                    stock_avant=stock_avant,
                    stock_apres=article.quantite_stock,
                    reference_document=vente.numero_facture,
                    utilisateur=terminal.nom_terminal,
                    commentaire=f"Vente #{vente.numero_facture} - Prix: {prix_affiche} {symbole_devise}"
                )
                
                # ⭐ Accumuler les montants selon la devise
                if devise_ligne == 'USD':
                    # Pour USD: accumuler en USD
                    montant_total_usd += (prix_unitaire_usd or 0) * quantite
                    montant_total += prix_unitaire * quantite  # CDF si fourni
                else:
                    # Pour CDF: accumuler en CDF
                    montant_total += prix_unitaire * quantite
                    if prix_unitaire_usd:
                        montant_total_usd += prix_unitaire_usd * quantite
                
                # Sous-total selon la devise de la ligne
                sous_total = (prix_unitaire_usd * quantite) if devise_ligne == 'USD' else (prix_unitaire * quantite)
                lignes_creees.append({
                    'article_nom': article.nom,
                    'quantite': quantite,
                    'prix_unitaire': str(prix_unitaire),
                    'prix_unitaire_usd': str(prix_unitaire_usd) if prix_unitaire_usd else None,
                    'devise': devise_ligne,
                    'sous_total': str(sous_total)
                })
            
            # Mettre à jour le montant total de la vente
            logger.info(f"💰 Montant total calculé: {montant_total} CDF / {montant_total_usd} USD (devise: {devise_vente})")
            vente.montant_total = montant_total
            
            # ⭐ Toujours sauvegarder montant_total_usd pour ventes USD
            if devise_vente == 'USD':
                vente.montant_total_usd = montant_total_usd
                vente.save(update_fields=['montant_total', 'montant_total_usd'])
            else:
                # Pour CDF, sauvegarder USD si disponible
                if montant_total_usd > 0:
                    vente.montant_total_usd = montant_total_usd
                    vente.save(update_fields=['montant_total', 'montant_total_usd'])
                else:
                    vente.save(update_fields=['montant_total'])
            logger.info(f"✅ Montant sauvegardé: {vente.montant_total} {vente.devise}")
            
            # Vérification de sécurité - Recharger depuis la base
            vente.refresh_from_db()
            logger.info(f"🔍 Vérification après reload: {vente.montant_total} CDF")
        
        return Response({
            'success': True,
            'vente': {
                'id': vente.id,
                'numero_facture': vente.numero_facture,
                'devise': vente.devise,
                'montant_total': str(montant_total),
                'montant_total_usd': str(montant_total_usd) if montant_total_usd > 0 else None,
                'mode_paiement': vente.mode_paiement,
                'date_vente': vente.date_vente.isoformat(),
                'lignes': lignes_creees
            },
            'boutique_id': boutique.id,
            'terminal_id': terminal.id
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"❌ Erreur lors de la création de la vente: {str(e)}")
        logger.error(f"❌ Traceback complet:\n{error_details}")
        logger.error(f"❌ Données reçues: {request.data}")
        
        return Response({
            'error': f'Erreur lors de la création de la vente: {str(e)}',
            'code': 'INTERNAL_ERROR',
            'details': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def historique_ventes_simple(request):
    """
    Récupérer l'historique des ventes d'une boutique (sans authentification)
    Supporte filtrage par date et pagination
    """
    boutique_id = request.GET.get('boutique_id')
    
    # Si pas de boutique_id, essayer de récupérer via le numéro de série dans les headers
    if not boutique_id:
        numero_serie = (
            request.headers.get('X-Device-Serial') or 
            request.headers.get('Device-Serial') or
            request.headers.get('Serial-Number') or
            request.META.get('HTTP_X_DEVICE_SERIAL') or
            request.META.get('HTTP_DEVICE_SERIAL')
        )
        
        if numero_serie:
            try:
                terminal = Client.objects.select_related('boutique').filter(
                    numero_serie=numero_serie,
                    est_actif=True
                ).first()
                
                if terminal and terminal.boutique:
                    boutique_id = terminal.boutique.id
                    logger.info(f"✅ Boutique détectée pour historique: {boutique_id}")
            except Exception as e:
                logger.error(f"❌ Erreur détection boutique: {str(e)}")
    
    if not boutique_id:
        return Response({
            'error': 'Paramètre boutique_id requis OU numéro de série dans les headers',
            'code': 'MISSING_BOUTIQUE_ID'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        boutique = get_object_or_404(Boutique, id=boutique_id, est_active=True)
        
        # Filtres optionnels
        date_debut = request.GET.get('date_debut')
        date_fin = request.GET.get('date_fin')
        limit = int(request.GET.get('limit', 50))
        
        # ⭐ ISOLATION: Récupérer UNIQUEMENT les ventes de cette boutique
        ventes = Vente.objects.filter(
            boutique=boutique  # ⭐ Filtrage direct par boutique
        ).select_related('client_maui', 'boutique').prefetch_related('lignes__article')
        
        logger.info(f"🔍 Filtrage ventes par boutique ID: {boutique.id}")
        
        # Filtrer par date si fourni
        if date_debut:
            from datetime import datetime
            ventes = ventes.filter(date_vente__gte=datetime.fromisoformat(date_debut))
        if date_fin:
            from datetime import datetime
            ventes = ventes.filter(date_vente__lte=datetime.fromisoformat(date_fin))
        
        ventes = ventes.order_by('-date_vente')[:limit]
        
        # Calculer les statistiques
        from django.db.models import Sum, Count
        stats = ventes.aggregate(
            total_ventes=Count('id'),
            chiffre_affaires=Sum('montant_total')
        )
        
        # Sérialiser les ventes
        ventes_data = []
        for vente in ventes:
            lignes = []
            for ligne in vente.lignes.all():
                lignes.append({
                    'article_nom': ligne.article.nom,
                    'article_code': ligne.article.code,
                    'quantite': ligne.quantite,
                    'prix_unitaire': str(ligne.prix_unitaire),
                    'sous_total': str(ligne.prix_unitaire * ligne.quantite)
                })
            
            ventes_data.append({
                'id': vente.id,
                'numero_facture': vente.numero_facture,
                'date_vente': vente.date_vente.isoformat(),
                'montant_total': str(vente.montant_total),
                'mode_paiement': vente.mode_paiement,
                'paye': vente.paye,
                'terminal': vente.client_maui.nom_terminal if vente.client_maui else None,
                'lignes': lignes
            })
        
        return Response({
            'success': True,
            'boutique_id': boutique.id,
            'boutique_nom': boutique.nom,
            'statistiques': {
                'total_ventes': stats['total_ventes'] or 0,
                'chiffre_affaires': str(stats['chiffre_affaires'] or 0)
            },
            'ventes': ventes_data,
            'count': len(ventes_data)
        })
        
    except Exception as e:
        logger.error(f"Erreur récupération historique: {str(e)}")
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def statistiques_boutique_simple(request):
    """
    Récupérer les statistiques d'une boutique (CA, ventes, stock)
    """
    boutique_id = request.GET.get('boutique_id')
    
    # Si pas de boutique_id, essayer via header
    if not boutique_id:
        numero_serie = (
            request.headers.get('X-Device-Serial') or 
            request.META.get('HTTP_X_DEVICE_SERIAL')
        )
        
        if numero_serie:
            try:
                terminal = Client.objects.select_related('boutique').filter(
                    numero_serie=numero_serie,
                    est_actif=True
                ).first()
                
                if terminal and terminal.boutique:
                    boutique_id = terminal.boutique.id
            except Exception:
                pass
    
    if not boutique_id:
        return Response({
            'error': 'Paramètre boutique_id requis',
            'code': 'MISSING_BOUTIQUE_ID'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        from datetime import datetime, timedelta
        from django.db.models import Sum, Count
        
        boutique = get_object_or_404(Boutique, id=boutique_id, est_active=True)
        
        # Statistiques générales
        total_articles = Article.objects.filter(boutique=boutique, est_actif=True).count()
        total_categories = Categorie.objects.filter(boutique=boutique).count()
        
        # Ventes du jour
        aujourd_hui = datetime.now().date()
        ventes_jour = Vente.objects.filter(
            boutique=boutique,
            date_vente__date=aujourd_hui
        ).aggregate(
            nombre=Count('id'),
            ca=Sum('montant_total')
        )
        
        # Ventes du mois
        debut_mois = aujourd_hui.replace(day=1)
        ventes_mois = Vente.objects.filter(
            boutique=boutique,
            date_vente__date__gte=debut_mois
        ).aggregate(
            nombre=Count('id'),
            ca=Sum('montant_total')
        )
        
        # Articles en stock bas
        articles_stock_bas = Article.objects.filter(
            boutique=boutique,
            est_actif=True,
            quantite_stock__lte=boutique.alerte_stock_bas
        ).count()
        
        # 💰 NÉGOCIATIONS - Statistiques des prix négociés
        lignes_negociees_jour = LigneVente.objects.filter(
            vente__boutique=boutique,
            vente__date_vente__date=aujourd_hui,
            est_negocie=True
        ).aggregate(
            nombre=Count('id'),
            total_reduction=Sum(F('prix_original') - F('prix_unitaire'))
        )
        
        lignes_negociees_mois = LigneVente.objects.filter(
            vente__boutique=boutique,
            vente__date_vente__date__gte=debut_mois,
            est_negocie=True
        ).aggregate(
            nombre=Count('id'),
            total_reduction=Sum(F('prix_original') - F('prix_unitaire'))
        )
        
        return Response({
            'success': True,
            'boutique': {
                'id': boutique.id,
                'nom': boutique.nom,
                'type': boutique.type_boutique,
                'ville': boutique.ville
            },
            'statistiques': {
                'articles': {
                    'total': total_articles,
                    'stock_bas': articles_stock_bas
                },
                'categories': {
                    'total': total_categories
                },
                'ventes_jour': {
                    'nombre': ventes_jour['nombre'] or 0,
                    'chiffre_affaires': str(ventes_jour['ca'] or 0)
                },
                'ventes_mois': {
                    'nombre': ventes_mois['nombre'] or 0,
                    'chiffre_affaires': str(ventes_mois['ca'] or 0)
                },
                'negociations_jour': {
                    'nombre': lignes_negociees_jour['nombre'] or 0,
                    'montant_reduit': str(lignes_negociees_jour['total_reduction'] or 0)
                },
                'negociations_mois': {
                    'nombre': lignes_negociees_mois['nombre'] or 0,
                    'montant_reduit': str(lignes_negociees_mois['total_reduction'] or 0)
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur statistiques: {str(e)}")
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([AllowAny])
def update_stock_simple(request, article_id):
    """
    Mettre à jour le stock d'un article (sans authentification)
    """
    boutique_id = request.data.get('boutique_id')
    nouvelle_quantite = request.data.get('quantite_stock')
    
    if not boutique_id:
        return Response({
            'error': 'Paramètre boutique_id requis',
            'code': 'MISSING_BOUTIQUE_ID'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if nouvelle_quantite is None:
        return Response({
            'error': 'Paramètre quantite_stock requis',
            'code': 'MISSING_QUANTITY'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Vérifier que la boutique existe
        boutique = get_object_or_404(Boutique, id=boutique_id, est_active=True)
        
        # Vérifier que l'article appartient à cette boutique
        article = get_object_or_404(Article, id=article_id, boutique=boutique)
        
        # Sauvegarder l'ancienne quantité
        ancienne_quantite = article.quantite_stock
        
        # Mettre à jour le stock
        article.quantite_stock = nouvelle_quantite
        article.save(update_fields=['quantite_stock'])
        
        # Créer un mouvement de stock avec traçabilité complète
        difference = nouvelle_quantite - ancienne_quantite
        type_mouvement = 'AJUSTEMENT' if difference != 0 else 'AJUSTEMENT'
        
        MouvementStock.objects.create(
            article=article,
            type_mouvement=type_mouvement,
            quantite=difference,
            stock_avant=ancienne_quantite,  # ⭐ NOUVEAU
            stock_apres=nouvelle_quantite,  # ⭐ NOUVEAU
            reference_document=f"AJUST-{article.id}",  # ⭐ NOUVEAU
            utilisateur="API",  # ⭐ NOUVEAU
            commentaire=f"Ajustement stock API - Prix achat: {article.prix_achat} CDF"
        )
        
        return Response({
            'success': True,
            'article': {
                'id': article.id,
                'nom': article.nom,
                'code': article.code,
                'ancienne_quantite': ancienne_quantite,
                'nouvelle_quantite': nouvelle_quantite,
                'difference': difference
            },
            'boutique_id': boutique.id
        })
        
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du stock: {str(e)}")
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def sync_ventes_simple(request):
    """
    Synchronisation de plusieurs ventes depuis MAUI (sans authentification)
    Accepte un tableau de ventes à créer
    
    Format attendu:
    [
        {
            "numero_facture": "VENTE-001",
            "mode_paiement": "CASH",
            "paye": true,
            "lignes": [
                {
                    "article_id": 6,
                    "quantite": 1,
                    "prix_unitaire": 40000
                }
            ]
        }
    ]
    """
    try:
        # ⭐ CORRECTION CHUNKED ENCODING: Lire le body brut si request.data est vide
        # Django runserver ne gère pas bien Transfer-Encoding: chunked
        raw_body = request.body
        
        # Logging conditionnel (seulement en mode DEBUG)
        from django.conf import settings
        if settings.DEBUG:
            logger.debug(f"🔍 === SYNC VENTES ===")
            logger.debug(f"🔍 Content-Type: {request.content_type}")
            logger.debug(f"🔍 Body length: {len(raw_body) if raw_body else 0} bytes")
            if raw_body and len(raw_body) < 2000:
                logger.debug(f"🔍 Body: {raw_body.decode('utf-8', errors='ignore')}")
        
        # Parser le JSON depuis le body brut si request.data est vide
        import json
        if raw_body and (not request.data or (isinstance(request.data, dict) and len(request.data) == 0)):
            try:
                parsed_data = json.loads(raw_body.decode('utf-8'))
                logger.info(f"✅ Body parsé manuellement: {type(parsed_data)}")
                logger.info(f"✅ Clés trouvées: {list(parsed_data.keys()) if isinstance(parsed_data, dict) else 'list'}")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Erreur parsing JSON: {e}")
                parsed_data = request.data
        else:
            parsed_data = request.data
            
        logger.info(f"🔍 Data type final: {type(parsed_data)}")
        logger.info(f"🔍 Data preview: {str(parsed_data)[:500] if parsed_data else 'EMPTY'}")
        
        # Récupérer le numéro de série du terminal depuis les headers
        numero_serie = (
            request.headers.get('X-Device-Serial') or 
            request.headers.get('Device-Serial') or
            request.headers.get('Serial-Number') or
            request.META.get('HTTP_X_DEVICE_SERIAL') or
            request.META.get('HTTP_DEVICE_SERIAL')
        )
        
        logger.info(f"🔍 Numéro de série détecté: {numero_serie}")
        
        if not numero_serie:
            logger.warning("⚠️ Tentative de synchronisation sans numéro de série")
            logger.warning(f"⚠️ Headers disponibles: {list(request.headers.keys())}")
            return Response({
                'error': 'Numéro de série du terminal requis dans les headers',
                'code': 'MISSING_SERIAL',
                'header_required': 'X-Device-Serial'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Récupérer le terminal et sa boutique
        try:
            terminal = Client.objects.select_related('boutique').get(
                numero_serie=numero_serie,
                est_actif=True
            )
            boutique = terminal.boutique
            
            if not boutique:
                logger.error(f"❌ Terminal {numero_serie} sans boutique associée")
                return Response({
                    'error': 'Terminal non associé à une boutique',
                    'code': 'NO_BOUTIQUE'
                }, status=status.HTTP_400_BAD_REQUEST)
                
            logger.info(f"🔄 Synchronisation ventes pour boutique: {boutique.nom} (Terminal: {terminal.nom_terminal})")
            
        except Client.DoesNotExist:
            logger.error(f"❌ Terminal non trouvé: {numero_serie}")
            return Response({
                'error': 'Terminal non trouvé ou inactif',
                'code': 'TERMINAL_NOT_FOUND'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Récupérer les données des ventes
        # ⭐ COMPATIBILITÉ MAUI: Accepter les deux formats + PascalCase
        # Format 1 (Django): [{"numero_facture": "...", "lignes": [...]}]
        # Format 2 (MAUI snake_case): {"pos_id": "...", "ventes": [...]}
        # Format 3 (MAUI PascalCase): {"PosId": "...", "Ventes": [...]}
        # ⭐ Utiliser parsed_data (body parsé manuellement si chunked encoding)
        raw_data = parsed_data
        
        # ⭐ CORRECTION: Accepter PascalCase (Ventes) et snake_case (ventes)
        ventes_key = None
        pos_id_key = None
        if isinstance(raw_data, dict):
            # Chercher la clé ventes (PascalCase ou snake_case)
            if 'Ventes' in raw_data:
                ventes_key = 'Ventes'
                pos_id_key = 'PosId'
            elif 'ventes' in raw_data:
                ventes_key = 'ventes'
                pos_id_key = 'pos_id'
        
        if ventes_key:
            # Format MAUI: extraire le tableau de ventes et convertir les champs
            pos_id = raw_data.get(pos_id_key) or raw_data.get('PosId') or raw_data.get('pos_id', 'N/A')
            logger.info(f"📱 Format MAUI détecté (pos_id: {pos_id}, clé: {ventes_key})")
            ventes_maui = raw_data.get(ventes_key, [])
            ventes_data = []
            for v in ventes_maui:
                # ⭐ Accepter PascalCase et snake_case pour chaque champ
                vente_convertie = {
                    'numero_facture': v.get('VenteUid') or v.get('vente_uid') or v.get('numero_facture'),
                    'date_vente': v.get('Date') or v.get('date') or v.get('date_vente'),
                    'montant_total': v.get('Total') or v.get('total') or v.get('montant_total'),
                    'montant_total_usd': v.get('TotalUsd') or v.get('total_usd') or v.get('montant_total_usd'),
                    'devise': v.get('Devise') or v.get('devise', 'CDF'),
                    'mode_paiement': v.get('ModePaiement') or v.get('mode_paiement', 'CASH'),
                    'paye': v.get('Paye') if 'Paye' in v else v.get('paye', True),
                    'lignes': v.get('Items') or v.get('items') or v.get('lignes', [])
                }
                # ⭐ Convertir aussi les lignes (Items) en format Django
                lignes_converties = []
                for item in vente_convertie.get('lignes', []):
                    ligne_convertie = {
                        'article_id': item.get('ArticleId') or item.get('article_id'),
                        'quantite': item.get('Quantite') or item.get('quantite'),
                        'prix_unitaire': item.get('PrixUnitaire') or item.get('prix_unitaire'),
                        'prix_unitaire_usd': item.get('PrixUnitaireUsd') or item.get('prix_unitaire_usd'),
                        'devise': item.get('Devise') or item.get('devise', 'CDF')
                    }
                    lignes_converties.append(ligne_convertie)
                vente_convertie['lignes'] = lignes_converties
                ventes_data.append(vente_convertie)
            logger.info(f"📱 {len(ventes_data)} ventes MAUI converties")
        elif isinstance(raw_data, list):
            # Format Django standard
            ventes_data = raw_data
        else:
            logger.error(f"❌ Format invalide reçu: {type(raw_data)} - clés: {list(raw_data.keys()) if isinstance(raw_data, dict) else 'N/A'}")
            return Response({
                'error': 'Format invalide: un tableau de ventes ou un objet {ventes: [...]} est attendu',
                'code': 'INVALID_FORMAT'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not ventes_data:
            return Response({
                'error': 'Aucune vente à synchroniser',
                'code': 'EMPTY_DATA'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"📦 Nombre de ventes à synchroniser: {len(ventes_data)}")
        
        # Traiter chaque vente
        ventes_creees = []
        ventes_erreurs = []
        
        for index, vente_data in enumerate(ventes_data):
            try:
                # ⭐ TRANSACTION ATOMIQUE : Chaque vente est tout ou rien
                with transaction.atomic():
                    logger.info(f"🔄 Traitement vente {index + 1}/{len(ventes_data)}")
                    
                    # ⭐ VALIDATION CRITIQUE: Vérifier le boutique_id si fourni
                    boutique_id_recu = vente_data.get('boutique_id')
                    
                    if boutique_id_recu:
                        # Si boutique_id est fourni, vérifier qu'il correspond à la boutique du terminal
                        if int(boutique_id_recu) != boutique.id:
                            logger.error(f"❌ SÉCURITÉ: Tentative d'accès à une autre boutique!")
                            logger.error(f"   Terminal boutique: {boutique.id}, Demandé: {boutique_id_recu}")
                            ventes_erreurs.append({
                                'numero_facture': vente_data.get('numero_facture', f'vente_{index}'),
                                'erreur': 'Accès refusé: boutique non autorisée',
                                'code': 'BOUTIQUE_MISMATCH'
                            })
                            continue
                        logger.info(f"✅ Boutique ID validé: {boutique_id_recu}")
                    else:
                        logger.info(f"ℹ️ Boutique ID non fourni, utilisation de la boutique du terminal: {boutique.id}")
                    
                    # Générer le numéro de facture si absent
                    numero_facture = vente_data.get('numero_facture')
                    if not numero_facture:
                        from datetime import datetime
                        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                        numero_facture = f"VENTE-{boutique.id}-{timestamp}-{index}"
                        logger.info(f"📝 Numéro de facture généré: {numero_facture}")
                    
                    # ⭐ Vérifier si la vente existe déjà GLOBALEMENT (contrainte unique)
                    vente_existante = Vente.objects.filter(
                        numero_facture=numero_facture
                    ).first()
                    
                    if vente_existante:
                        logger.warning(f"⚠️ Vente {numero_facture} existe déjà (ID: {vente_existante.id}, boutique: {vente_existante.boutique_id})")
                        ventes_erreurs.append({
                            'numero_facture': numero_facture,
                            'erreur': 'Vente déjà existante',
                            'code': 'DUPLICATE',
                            'vente_existante_id': vente_existante.id
                        })
                        continue
                    
                    # ⭐ CRÉER LA VENTE AVEC ISOLATION STRICTE
                    date_str = vente_data.get('date_vente') or vente_data.get('date')
                    if date_str:
                        date_vente = parse_datetime(date_str)
                        if date_vente is None:
                            date_vente = timezone.now()
                        elif timezone.is_naive(date_vente):
                            # Interpréter la date naïve comme étant dans le timezone de Django (Europe/Paris)
                            date_vente = timezone.make_aware(date_vente)
                        else:
                            # Si la date est déjà aware, s'assurer qu'elle est dans le bon timezone
                            date_vente = date_vente.astimezone(timezone.get_current_timezone())
                    else:
                        date_vente = timezone.now()
                    
                    # Déterminer la devise de la vente
                    devise_vente = vente_data.get('devise', 'CDF')
                    
                    vente = Vente.objects.create(
                        numero_facture=numero_facture,
                        date_vente=date_vente,
                        montant_total=0,  # Sera calculé avec les lignes
                        montant_total_usd=0 if devise_vente == 'USD' else None,
                        devise=devise_vente,
                        mode_paiement=vente_data.get('mode_paiement', 'CASH'),
                        paye=vente_data.get('paye', True),
                        boutique=boutique,  # ⭐ ISOLATION: Lien direct avec la boutique
                        client_maui=terminal,
                        adresse_ip_client=request.META.get('REMOTE_ADDR'),
                        version_app_maui=terminal.version_app_maui
                    )
                    logger.info(f"✅ Vente créée: {numero_facture} (ID: {vente.id}) → Boutique {boutique.nom} (ID: {boutique.id}) - Devise: {devise_vente}")
                    
                    montant_total = 0
                    montant_total_usd = 0
                    lignes_creees = []
                    
                    # Traiter chaque ligne de vente
                    for ligne_data in vente_data.get('lignes', []):
                        article_id = ligne_data.get('article_id')
                        quantite = ligne_data.get('quantite', 1)
                        
                        # Vérifier que l'article appartient à la boutique
                        try:
                            article = Article.objects.get(
                                id=article_id,
                                boutique=boutique,
                                est_actif=True
                            )
                        except Article.DoesNotExist:
                            # Erreur enrichie avec détails pour traçabilité
                            raise ValueError(f'ARTICLE_NOT_FOUND|{article_id}||0|0|Article {article_id} non trouvé dans cette boutique')
                        
                        # Vérifier le stock disponible
                        if article.quantite_stock < quantite:
                            # Erreur enrichie: RAISON|article_id|article_nom|stock_demande|stock_dispo|message
                            raise ValueError(f'INSUFFICIENT_STOCK|{article.id}|{article.nom}|{quantite}|{article.quantite_stock}|Stock insuffisant pour {article.nom} (dispo: {article.quantite_stock}, demandé: {quantite})')
                        
                        # Créer la ligne de vente avec support USD
                        prix_unitaire = ligne_data.get('prix_unitaire', article.prix_vente)
                        prix_unitaire_usd = ligne_data.get('prix_unitaire_usd') or article.prix_vente_usd
                        devise_ligne = ligne_data.get('devise', devise_vente)
                        
                        # 💰 Gérer les négociations
                        prix_original = ligne_data.get('prix_original') or ligne_data.get('prixOriginal')
                        est_negocie = ligne_data.get('est_negocie') or ligne_data.get('estNegocie', False)
                        motif_reduction = ligne_data.get('motif_reduction') or ligne_data.get('motifReduction') or ''
                        
                        # 🔍 Auto-détection: si prix_original non fourni, utiliser le prix de l'article
                        if not prix_original:
                            prix_original = float(article.prix_vente)
                        
                        # Auto-détection si prix négocié (prix différent du prix original)
                        try:
                            prix_orig_decimal = float(prix_original)
                            prix_unit_decimal = float(prix_unitaire)
                            if abs(prix_orig_decimal - prix_unit_decimal) > 0.01:
                                est_negocie = True
                                logger.info(f"💰 RÉDUCTION DÉTECTÉE: {article.nom} - Original: {prix_orig_decimal} → Vendu: {prix_unit_decimal}")
                        except (ValueError, TypeError):
                            pass
                        
                        ligne_vente = LigneVente.objects.create(
                            vente=vente,
                            article=article,
                            quantite=quantite,
                            prix_unitaire=prix_unitaire,
                            prix_unitaire_usd=prix_unitaire_usd,
                            devise=devise_ligne,
                            prix_original=prix_original,
                            est_negocie=est_negocie,
                            motif_reduction=motif_reduction
                        )
                        
                        # Mettre à jour le stock
                        stock_avant = article.quantite_stock  # ⭐ Capturer AVANT la modification
                        article.quantite_stock -= quantite
                        article.save(update_fields=['quantite_stock'])
                        
                        # Créer un mouvement de stock avec traçabilité complète
                        MouvementStock.objects.create(
                            article=article,
                            type_mouvement='VENTE',
                            quantite=-quantite,
                            stock_avant=stock_avant,  # ⭐ NOUVEAU
                            stock_apres=article.quantite_stock,  # ⭐ NOUVEAU
                            reference_document=vente.numero_facture,  # ⭐ NOUVEAU
                            utilisateur=terminal.nom_terminal,  # ⭐ NOUVEAU
                            commentaire=f"Vente #{vente.numero_facture} - Prix: {prix_unitaire} CDF"
                        )
                        
                        montant_total += prix_unitaire * quantite
                        montant_total_usd = (montant_total_usd or 0) + (prix_unitaire_usd * quantite if prix_unitaire_usd else 0)
                        lignes_creees.append({
                            'article_nom': article.nom,
                            'article_code': article.code,
                            'quantite': quantite,
                            'prix_unitaire': str(prix_unitaire),
                            'prix_unitaire_usd': str(prix_unitaire_usd) if prix_unitaire_usd else None,
                            'devise': devise_ligne,
                            'sous_total': str(prix_unitaire * quantite)
                        })
                    
                    # Mettre à jour le montant total de la vente
                    logger.info(f"💰 SYNC - Montant total calculé: {montant_total} CDF / {montant_total_usd} USD")
                    vente.montant_total = montant_total
                    if devise_vente == 'USD' and montant_total_usd:
                        vente.montant_total_usd = montant_total_usd
                        vente.save(update_fields=['montant_total', 'montant_total_usd'])
                    else:
                        vente.save(update_fields=['montant_total'])
                    logger.info(f"✅ SYNC - Montant sauvegardé: {vente.montant_total} {vente.devise}")
                    
                    ventes_creees.append({
                        'numero_facture': vente.numero_facture,
                        'status': 'created',
                        'id': vente.id,
                        'boutique_id': boutique.id,
                        'boutique_nom': boutique.nom,
                        'montant_total': str(vente.montant_total),
                        'lignes_count': len(lignes_creees),
                        'lignes': lignes_creees
                    })
                    
                    logger.info(f"✅ Vente {numero_facture} synchronisée:")
                    logger.info(f"   - Boutique: {boutique.id} ({boutique.nom})")
                    logger.info(f"   - Lignes: {len(lignes_creees)}")
                    logger.info(f"   - Montant: {montant_total} CDF")
                
            except ValueError as ve:
                # Erreur de validation enrichie (format: RAISON|article_id|article_nom|stock_demande|stock_dispo|message)
                error_str = str(ve)
                error_parts = error_str.split('|')
                
                if len(error_parts) >= 6:
                    raison_code = error_parts[0]
                    article_id_err = int(error_parts[1]) if error_parts[1] else None
                    article_nom_err = error_parts[2]
                    stock_demande = int(error_parts[3]) if error_parts[3] else None
                    stock_dispo = int(error_parts[4]) if error_parts[4] else None
                    message_err = error_parts[5]
                else:
                    raison_code = 'OTHER'
                    article_id_err = None
                    article_nom_err = ''
                    stock_demande = None
                    stock_dispo = None
                    message_err = error_str
                
                logger.error(f"❌ Erreur validation vente {index + 1}: {message_err}")
                
                # Sauvegarder dans VenteRejetee pour traçabilité
                try:
                    VenteRejetee.objects.create(
                        vente_uid=vente_data.get('numero_facture', f'UNKNOWN_{index}'),
                        terminal=terminal,
                        boutique=boutique,
                        date_vente_originale=parse_datetime(vente_data.get('date_vente') or vente_data.get('date') or ''),
                        donnees_vente=vente_data,
                        raison_rejet=raison_code,
                        message_erreur=message_err,
                        article_concerne_id=article_id_err,
                        article_concerne_nom=article_nom_err,
                        stock_demande=stock_demande,
                        stock_disponible=stock_dispo,
                        action_requise='NOTIFY_USER'
                    )
                    logger.info(f"📝 Vente rejetée enregistrée: {vente_data.get('numero_facture', 'N/A')}")
                except Exception as save_err:
                    logger.warning(f"⚠️ Impossible de sauvegarder le rejet: {save_err}")
                
                # Ajouter à la liste des erreurs avec détails enrichis
                ventes_erreurs.append({
                    'index': index + 1,
                    'numero_facture': vente_data.get('numero_facture', 'N/A'),
                    'erreur': message_err,
                    'code': raison_code,
                    'article_id': article_id_err,
                    'article_nom': article_nom_err,
                    'stock_demande': stock_demande,
                    'stock_disponible': stock_dispo
                })
                
            except IntegrityError as ie:
                # ⭐ Erreur de duplication (race condition ou contrainte unique)
                logger.warning(f"⚠️ IntegrityError pour vente {index + 1}: {str(ie)}")
                
                # Vérifier si c'est un doublon de numero_facture
                numero_facture = vente_data.get('numero_facture', f'UNKNOWN_{index}')
                vente_existante = Vente.objects.filter(numero_facture=numero_facture).first()
                
                if vente_existante:
                    logger.info(f"✅ Vente {numero_facture} existe déjà (ID: {vente_existante.id}) - considérée comme succès")
                    # Traiter comme un succès (la vente existe déjà)
                    ventes_creees.append({
                        'numero_facture': numero_facture,
                        'status': 'already_exists',
                        'id': vente_existante.id,
                        'boutique_id': vente_existante.boutique_id,
                        'message': 'Vente déjà synchronisée précédemment'
                    })
                else:
                    # Vraie erreur d'intégrité (autre contrainte)
                    ventes_erreurs.append({
                        'index': index + 1,
                        'numero_facture': numero_facture,
                        'erreur': f'Erreur intégrité: {str(ie)}',
                        'code': 'INTEGRITY_ERROR'
                    })
                
            except Exception as e:
                # Autres erreurs non prévues
                logger.error(f"❌ Erreur création vente {index + 1}: {str(e)}")
                
                # Sauvegarder dans VenteRejetee
                try:
                    VenteRejetee.objects.create(
                        vente_uid=vente_data.get('numero_facture', f'UNKNOWN_{index}'),
                        terminal=terminal,
                        boutique=boutique,
                        donnees_vente=vente_data,
                        raison_rejet='OTHER',
                        message_erreur=str(e),
                        action_requise='NOTIFY_MANAGER'
                    )
                except Exception as save_err:
                    logger.warning(f"⚠️ Impossible de sauvegarder le rejet: {save_err}")
                
                ventes_erreurs.append({
                    'index': index + 1,
                    'numero_facture': vente_data.get('numero_facture', 'N/A'),
                    'erreur': str(e),
                    'code': 'OTHER'
                })
        
        # Retourner le résumé avec informations d'isolation
        logger.info(f"✅ Synchronisation terminée:")
        logger.info(f"   - Créées: {len(ventes_creees)}")
        logger.info(f"   - Erreurs: {len(ventes_erreurs)}")
        
        # ⭐ COMPATIBILITÉ MAUI: Inclure les champs "accepted" et "rejected" attendus par MAUI
        accepted_list = [v['numero_facture'] for v in ventes_creees]
        
        # Enrichir rejected avec plus de détails pour le client MAUI
        rejected_list = []
        for e in ventes_erreurs:
            rejected_item = {
                'vente_uid': e.get('numero_facture', 'N/A'),
                'reason': e.get('code', 'OTHER'),
                'message': e.get('erreur', 'Erreur inconnue'),
                'action': 'NOTIFY_USER'
            }
            # Ajouter les détails si disponibles
            if e.get('article_id'):
                rejected_item['article_id'] = e['article_id']
                rejected_item['article_nom'] = e.get('article_nom', '')
            if e.get('stock_disponible') is not None:
                rejected_item['stock_disponible'] = e['stock_disponible']
            if e.get('stock_demande') is not None:
                rejected_item['stock_demande'] = e['stock_demande']
            rejected_list.append(rejected_item)
        
        # ⭐ NOUVEAU: Collecter les mises à jour de stock pour les articles concernés par des rejets
        stock_updates = []
        articles_en_erreur = set()
        for e in ventes_erreurs:
            if e.get('article_id'):
                articles_en_erreur.add(e['article_id'])
        
        if articles_en_erreur:
            articles_actuels = Article.objects.filter(id__in=articles_en_erreur, boutique=boutique)
            for art in articles_actuels:
                stock_updates.append({
                    'article_id': art.id,
                    'code': art.code,
                    'nom': art.nom,
                    'stock_actuel': art.quantite_stock,
                    'prix_actuel': str(art.prix_vente)
                })
        
        return Response({
            'success': True,
            'message': f'{len(ventes_creees)} vente(s) synchronisée(s) avec succès',
            # ⭐ Format MAUI
            'accepted': accepted_list,
            'rejected': rejected_list,
            # ⭐ NOUVEAU: Mises à jour de stock pour les articles en erreur
            'stock_updates': stock_updates,
            # Format Django (rétrocompatibilité)
            'ventes_creees': len(ventes_creees),
            'ventes_erreurs': len(ventes_erreurs),
            'details': {
                'creees': ventes_creees,
                'erreurs': ventes_erreurs if ventes_erreurs else []
            },
            'boutique': {
                'id': boutique.id,
                'nom': boutique.nom,
                'code': boutique.code_boutique if hasattr(boutique, 'code_boutique') else None
            },
            'terminal': {
                'id': terminal.id,
                'nom': terminal.nom_terminal,
                'numero_serie': numero_serie
            },
            'statistiques': {
                'total_envoyees': len(ventes_data),
                'reussies': len(ventes_creees),
                'erreurs': len(ventes_erreurs)
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"❌ Erreur synchronisation ventes: {str(e)}")
        import traceback
        logger.error(f"❌ Traceback complet:\n{traceback.format_exc()}")
        
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR',
            'details': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def creer_article_negocie_simple(request):
    numero_serie = (
        request.headers.get('X-Device-Serial')
        or request.headers.get('Device-Serial')
        or request.headers.get('Serial-Number')
        or request.META.get('HTTP_X_DEVICE_SERIAL')
        or request.META.get('HTTP_DEVICE_SERIAL')
    )

    if not numero_serie:
        return Response({
            'error': 'Numéro de série du terminal requis dans les headers',
            'code': 'MISSING_SERIAL'
        }, status=status.HTTP_400_BAD_REQUEST)

    terminal = Client.objects.select_related('boutique').filter(
        numero_serie=numero_serie,
        est_actif=True
    ).first()

    if not terminal or not terminal.boutique:
        return Response({
            'error': 'Terminal non trouvé ou sans boutique',
            'code': 'TERMINAL_NOT_FOUND'
        }, status=status.HTTP_404_NOT_FOUND)

    boutique = terminal.boutique
    data = request.data

    code_article = data.get('code_article')
    if not code_article:
        return Response({
            'error': 'code_article requis',
            'code': 'MISSING_CODE_ARTICLE'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        montant_negocie = data['montant_negocie']
        date_raw = data['date_operation']
    except KeyError as e:
        return Response({
            'error': f'Champ manquant: {str(e)}',
            'code': 'MISSING_FIELD'
        }, status=status.HTTP_400_BAD_REQUEST)

    date_operation = parse_datetime(date_raw) or timezone.now()

    # Quantité négociée (MAUI envoie déjà la quantité)
    quantite_raw = data.get('quantite', 1)
    try:
        quantite = int(quantite_raw)
        if quantite <= 0:
            quantite = 1
    except (TypeError, ValueError):
        quantite = 1

    article = Article.objects.filter(
        code=code_article,
        boutique=boutique,
        est_actif=True
    ).first()

    obj = ArticleNegocie.objects.create(
        boutique=boutique,
        terminal=terminal,
        article=article,
        code_article=code_article,
        quantite=quantite,
        montant_negocie=montant_negocie,
        devise=data.get('devise') or boutique.devise,
        date_operation=date_operation,
        motif=data.get('motif') or '',
        reference_vente=data.get('reference_vente') or '',
    )

    return Response({'id': obj.id}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def creer_retour_article_simple(request):
    numero_serie = (
        request.headers.get('X-Device-Serial')
        or request.headers.get('Device-Serial')
        or request.headers.get('Serial-Number')
        or request.META.get('HTTP_X_DEVICE_SERIAL')
        or request.META.get('HTTP_DEVICE_SERIAL')
    )

    if not numero_serie:
        return Response({
            'error': 'Numéro de série du terminal requis dans les headers',
            'code': 'MISSING_SERIAL'
        }, status=status.HTTP_400_BAD_REQUEST)

    terminal = Client.objects.select_related('boutique').filter(
        numero_serie=numero_serie,
        est_actif=True
    ).first()

    if not terminal or not terminal.boutique:
        return Response({
            'error': 'Terminal non trouvé ou sans boutique',
            'code': 'TERMINAL_NOT_FOUND'
        }, status=status.HTTP_404_NOT_FOUND)

    boutique = terminal.boutique
    data = request.data

    code_article = data.get('code_article')
    if not code_article:
        return Response({
            'error': 'code_article requis',
            'code': 'MISSING_CODE_ARTICLE'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        montant_retourne = data['montant_retourne']
        date_raw = data['date_operation']
    except KeyError as e:
        return Response({
            'error': f'Champ manquant: {str(e)}',
            'code': 'MISSING_FIELD'
        }, status=status.HTTP_400_BAD_REQUEST)

    date_operation = parse_datetime(date_raw) or timezone.now()

    # Quantité retournée (MAUI envoie déjà la quantité)
    quantite_raw = data.get('quantite', 1)
    try:
        quantite = int(quantite_raw)
        if quantite <= 0:
            quantite = 1
    except (TypeError, ValueError):
        quantite = 1

    article = Article.objects.filter(
        code=code_article,
        boutique=boutique,
        est_actif=True
    ).first()

    retour = RetourArticle.objects.create(
        boutique=boutique,
        terminal=terminal,
        article=article,
        code_article=code_article,
        quantite=quantite,
        montant_retourne=montant_retourne,
        devise=data.get('devise') or boutique.devise,
        date_operation=date_operation,
        motif=data.get('motif') or '',
        reference_vente=data.get('reference_vente') or '',
    )

    return Response({'id': retour.id}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def historique_articles_negocies_simple(request):
    numero_serie = (
        request.headers.get('X-Device-Serial')
        or request.headers.get('Device-Serial')
        or request.headers.get('Serial-Number')
        or request.META.get('HTTP_X_DEVICE_SERIAL')
        or request.META.get('HTTP_DEVICE_SERIAL')
    )

    if not numero_serie:
        return Response({
            'error': 'Numéro de série du terminal requis dans les headers',
            'code': 'MISSING_SERIAL'
        }, status=status.HTTP_400_BAD_REQUEST)

    terminal = Client.objects.select_related('boutique').filter(
        numero_serie=numero_serie,
        est_actif=True
    ).first()

    if not terminal or not terminal.boutique:
        return Response({
            'error': 'Terminal non trouvé ou sans boutique',
            'code': 'TERMINAL_NOT_FOUND'
        }, status=status.HTTP_404_NOT_FOUND)

    boutique = terminal.boutique
    par_terminal = request.query_params.get('par_terminal')
    limit_param = request.query_params.get('limit')
    try:
        limit = int(limit_param) if limit_param is not None else 100
    except ValueError:
        limit = 100

    qs = ArticleNegocie.objects.filter(boutique=boutique)
    if par_terminal and par_terminal.lower() in ('1', 'true', 'yes', 'on'):
        qs = qs.filter(terminal=terminal)

    qs = qs.select_related('boutique', 'terminal', 'article').order_by('-date_operation', '-created_at')[:limit]
    serializer = ArticleNegocieSerializer(qs, many=True)

    return Response({
        'success': True,
        'count': qs.count(),
        'boutique_id': boutique.id,
        'boutique_nom': boutique.nom,
        'par_terminal': bool(par_terminal and par_terminal.lower() in ('1', 'true', 'yes', 'on')),
        'results': serializer.data,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def historique_retours_articles_simple(request):
    numero_serie = (
        request.headers.get('X-Device-Serial')
        or request.headers.get('Device-Serial')
        or request.headers.get('Serial-Number')
        or request.META.get('HTTP_X_DEVICE_SERIAL')
        or request.META.get('HTTP_DEVICE_SERIAL')
    )

    if not numero_serie:
        return Response({
            'error': 'Numéro de série du terminal requis dans les headers',
            'code': 'MISSING_SERIAL'
        }, status=status.HTTP_400_BAD_REQUEST)

    terminal = Client.objects.select_related('boutique').filter(
        numero_serie=numero_serie,
        est_actif=True
    ).first()

    if not terminal or not terminal.boutique:
        return Response({
            'error': 'Terminal non trouvé ou sans boutique',
            'code': 'TERMINAL_NOT_FOUND'
        }, status=status.HTTP_404_NOT_FOUND)

    boutique = terminal.boutique
    par_terminal = request.query_params.get('par_terminal')
    limit_param = request.query_params.get('limit')
    try:
        limit = int(limit_param) if limit_param is not None else 100
    except ValueError:
        limit = 100

    qs = RetourArticle.objects.filter(boutique=boutique)
    if par_terminal and par_terminal.lower() in ('1', 'true', 'yes', 'on'):
        qs = qs.filter(terminal=terminal)

    qs = qs.select_related('boutique', 'terminal', 'article').order_by('-date_operation', '-created_at')[:limit]
    serializer = RetourArticleSerializer(qs, many=True)

    return Response({
        'success': True,
        'count': qs.count(),
        'boutique_id': boutique.id,
        'boutique_nom': boutique.nom,
        'par_terminal': bool(par_terminal and par_terminal.lower() in ('1', 'true', 'yes', 'on')),
        'results': serializer.data,
    }, status=status.HTTP_200_OK)


# =============================================================================
# ⭐ RÉCONCILIATION : Vérifier la cohérence entre MAUI et Django
# =============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
def reconcilier_ventes(request):
    """
    Endpoint de réconciliation pour vérifier la cohérence entre MAUI et Django.
    
    MAUI envoie la liste de ses ventes locales (références) et Django répond :
    - Quelles ventes sont présentes dans Django mais pas dans MAUI
    - Quelles ventes MAUI a mais Django n'a pas
    - Le total des ventes Django pour la période
    
    Payload attendu:
    {
        "references_maui": ["REF-001", "REF-002", ...],
        "date_debut": "2024-12-17T00:00:00",  // optionnel
        "date_fin": "2024-12-17T23:59:59"     // optionnel
    }
    """
    try:
        # Récupérer le terminal via le header
        numero_serie = (
            request.headers.get('X-Device-Serial') or 
            request.headers.get('Device-Serial') or
            request.META.get('HTTP_X_DEVICE_SERIAL')
        )
        
        if not numero_serie:
            return Response({
                'error': 'Numéro de série requis',
                'code': 'MISSING_SERIAL'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            terminal = Client.objects.select_related('boutique').get(
                numero_serie=numero_serie,
                est_actif=True
            )
            boutique = terminal.boutique
        except Client.DoesNotExist:
            return Response({
                'error': 'Terminal non trouvé',
                'code': 'TERMINAL_NOT_FOUND'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Parser les données
        data = request.data
        references_maui = set(data.get('references_maui', []) or data.get('ReferencesMaui', []))
        date_debut_str = data.get('date_debut') or data.get('DateDebut')
        date_fin_str = data.get('date_fin') or data.get('DateFin')
        
        # Construire la requête pour les ventes Django
        ventes_django_qs = Vente.objects.filter(
            client_maui=terminal,
            boutique=boutique
        )
        
        # Filtrer par date si fourni
        if date_debut_str:
            date_debut = parse_datetime(date_debut_str)
            if date_debut:
                if timezone.is_naive(date_debut):
                    date_debut = timezone.make_aware(date_debut)
                ventes_django_qs = ventes_django_qs.filter(date_vente__gte=date_debut)
        
        if date_fin_str:
            date_fin = parse_datetime(date_fin_str)
            if date_fin:
                if timezone.is_naive(date_fin):
                    date_fin = timezone.make_aware(date_fin)
                ventes_django_qs = ventes_django_qs.filter(date_vente__lte=date_fin)
        
        # Récupérer toutes les ventes Django pour ce terminal
        ventes_django = list(ventes_django_qs.values('numero_facture', 'montant_total', 'date_vente'))
        references_django = {v['numero_facture'] for v in ventes_django}
        
        # Calculer les différences
        dans_django_pas_maui = references_django - references_maui
        dans_maui_pas_django = references_maui - references_django
        en_commun = references_django & references_maui
        
        # Calculer les totaux
        total_django = sum(float(v['montant_total']) for v in ventes_django)
        
        # Détails des ventes manquantes dans MAUI
        ventes_manquantes_details = [
            {
                'reference': v['numero_facture'],
                'montant': float(v['montant_total']),
                'date': v['date_vente'].isoformat() if v['date_vente'] else None
            }
            for v in ventes_django if v['numero_facture'] in dans_django_pas_maui
        ]
        
        logger.info(f"🔄 Réconciliation pour {terminal.nom_terminal}:")
        logger.info(f"   - Ventes Django: {len(references_django)}")
        logger.info(f"   - Ventes MAUI: {len(references_maui)}")
        logger.info(f"   - En commun: {len(en_commun)}")
        logger.info(f"   - Dans Django, pas MAUI: {len(dans_django_pas_maui)}")
        logger.info(f"   - Dans MAUI, pas Django: {len(dans_maui_pas_django)}")
        
        return Response({
            'success': True,
            'terminal': terminal.nom_terminal,
            'boutique': boutique.nom,
            'coherent': len(dans_django_pas_maui) == 0 and len(dans_maui_pas_django) == 0,
            'stats': {
                'ventes_django': len(references_django),
                'ventes_maui': len(references_maui),
                'en_commun': len(en_commun),
                'total_django': total_django
            },
            'differences': {
                'dans_django_pas_maui': list(dans_django_pas_maui),
                'dans_maui_pas_django': list(dans_maui_pas_django),
                'ventes_manquantes_details': ventes_manquantes_details
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ Erreur réconciliation: {str(e)}")
        return Response({
            'error': str(e),
            'code': 'RECONCILIATION_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ═══════════════════════════════════════════════════════════════════════════════
# ⭐ ANNULATION DE VENTE
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([AllowAny])
def annuler_vente_simple(request):
    """
    Annule une vente et restaure le stock des articles concernés.
    
    Format attendu:
    {
        "numero_facture": "VENTE-001",
        "motif": "Erreur de caisse"  // Optionnel
    }
    
    Retourne:
    {
        "success": true,
        "message": "Vente annulée avec succès",
        "vente": {...},
        "stock_restaure": [...]
    }
    """
    try:
        # Récupérer le numéro de série du terminal depuis les headers
        numero_serie = (
            request.headers.get('X-Device-Serial') or 
            request.headers.get('Device-Serial') or
            request.META.get('HTTP_X_DEVICE_SERIAL')
        )
        
        if not numero_serie:
            return Response({
                'error': 'Numéro de série du terminal requis',
                'code': 'MISSING_SERIAL'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Récupérer le terminal
        try:
            terminal = Client.objects.select_related('boutique').get(
                numero_serie=numero_serie,
                est_actif=True
            )
            boutique = terminal.boutique
        except Client.DoesNotExist:
            return Response({
                'error': 'Terminal non trouvé ou inactif',
                'code': 'TERMINAL_NOT_FOUND'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Récupérer les données de la requête
        data = request.data
        numero_facture = data.get('numero_facture') or data.get('NumeroFacture') or data.get('reference')
        motif = data.get('motif') or data.get('Motif') or 'Annulation demandée par le terminal'
        
        if not numero_facture:
            return Response({
                'error': 'Numéro de facture requis',
                'code': 'MISSING_NUMERO_FACTURE'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"🔄 Demande d'annulation vente: {numero_facture} par {terminal.nom_terminal}")
        
        # Rechercher la vente
        try:
            vente = Vente.objects.select_related('boutique').prefetch_related('lignes__article').get(
                numero_facture=numero_facture,
                boutique=boutique
            )
        except Vente.DoesNotExist:
            return Response({
                'error': f'Vente {numero_facture} non trouvée dans cette boutique',
                'code': 'VENTE_NOT_FOUND'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Vérifier si déjà annulée
        if vente.est_annulee:
            return Response({
                'error': 'Cette vente a déjà été annulée',
                'code': 'ALREADY_CANCELLED',
                'date_annulation': vente.date_annulation.isoformat() if vente.date_annulation else None
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ⭐ VÉRIFIER LE DÉLAI D'ANNULATION (1 HEURE)
        from datetime import timedelta
        delai_annulation = timedelta(hours=1)
        temps_ecoule = timezone.now() - vente.date_vente
        
        if temps_ecoule > delai_annulation:
            return Response({
                'error': 'Le délai d\'annulation (1 heure) est dépassé',
                'code': 'CANCELLATION_TIMEOUT',
                'date_vente': vente.date_vente.isoformat(),
                'temps_ecoule_minutes': int(temps_ecoule.total_seconds() / 60),
                'delai_max_minutes': 60
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ⭐ TRANSACTION ATOMIQUE : Annulation + Restauration stock
        with transaction.atomic():
            stock_restaure = []
            
            # Restaurer le stock pour chaque ligne de vente
            for ligne in vente.lignes.all():
                article = ligne.article
                quantite = ligne.quantite
                stock_avant = article.quantite_stock
                
                # Restaurer le stock
                article.quantite_stock += quantite
                article.save(update_fields=['quantite_stock'])
                
                # Créer un mouvement de stock pour traçabilité
                MouvementStock.objects.create(
                    article=article,
                    type_mouvement='RETOUR',
                    quantite=quantite,  # Positif car c'est un retour
                    stock_avant=stock_avant,
                    stock_apres=article.quantite_stock,
                    reference_document=f"ANNUL-{vente.numero_facture}",
                    utilisateur=terminal.nom_terminal,
                    commentaire=f"Annulation vente #{vente.numero_facture} - Motif: {motif}"
                )
                
                stock_restaure.append({
                    'article_id': article.id,
                    'code': article.code,
                    'nom': article.nom,
                    'quantite_restauree': quantite,
                    'stock_avant': stock_avant,
                    'stock_apres': article.quantite_stock
                })
                
                logger.info(f"   ↩️ Stock restauré: {article.nom} +{quantite} ({stock_avant} → {article.quantite_stock})")
            
            # Marquer la vente comme annulée
            vente.est_annulee = True
            vente.date_annulation = timezone.now()
            vente.motif_annulation = motif
            vente.annulee_par = terminal.nom_terminal
            vente.save(update_fields=['est_annulee', 'date_annulation', 'motif_annulation', 'annulee_par'])
            
            logger.info(f"✅ Vente {numero_facture} annulée avec succès")
        
        return Response({
            'success': True,
            'message': f'Vente {numero_facture} annulée avec succès',
            'vente': {
                'numero_facture': vente.numero_facture,
                'montant_total': str(vente.montant_total),
                'date_vente': vente.date_vente.isoformat(),
                'date_annulation': vente.date_annulation.isoformat(),
                'motif': motif
            },
            'stock_restaure': stock_restaure,
            'boutique': {
                'id': boutique.id,
                'nom': boutique.nom
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"❌ Erreur annulation vente: {str(e)}")
        import traceback
        logger.error(f"❌ Traceback:\n{traceback.format_exc()}")
        return Response({
            'error': 'Erreur lors de l\'annulation',
            'code': 'CANCELLATION_ERROR',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 💰 RAPPORT DES NÉGOCIATIONS DE PRIX
# =============================================================================

@api_view(['GET'])
@permission_classes([AllowAny])
def rapport_negociations_simple(request):
    """
    💰 Rapport détaillé des négociations de prix
    
    Params:
        - boutique_id: ID de la boutique
        - date_debut: Date de début (YYYY-MM-DD)
        - date_fin: Date de fin (YYYY-MM-DD)
        - page: Numéro de page (défaut: 1)
        - limit: Nombre d'éléments par page (défaut: 50)
    
    Retourne:
        - Liste des lignes de vente négociées avec détails
        - Statistiques globales de négociation
    """
    from datetime import datetime, timedelta
    from django.core.paginator import Paginator
    
    boutique_id = request.GET.get('boutique_id')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 50))
    
    # Récupérer boutique via header si pas en paramètre
    if not boutique_id:
        numero_serie = request.headers.get('X-Device-Serial')
        if numero_serie:
            terminal = Client.objects.filter(numero_serie=numero_serie, est_actif=True).first()
            if terminal and terminal.boutique:
                boutique_id = terminal.boutique.id
    
    if not boutique_id:
        return Response({
            'error': 'Paramètre boutique_id requis',
            'code': 'MISSING_BOUTIQUE_ID'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        boutique = get_object_or_404(Boutique, id=boutique_id, est_active=True)
        
        # Filtrer les lignes négociées
        lignes_query = LigneVente.objects.filter(
            vente__boutique=boutique,
            est_negocie=True
        ).select_related('vente', 'article').order_by('-vente__date_vente')
        
        # Filtrer par dates si spécifiées
        if date_debut:
            lignes_query = lignes_query.filter(vente__date_vente__date__gte=date_debut)
        if date_fin:
            lignes_query = lignes_query.filter(vente__date_vente__date__lte=date_fin)
        
        # Statistiques globales
        stats = lignes_query.aggregate(
            total_lignes=Count('id'),
            total_reduction=Sum(F('prix_original') - F('prix_unitaire')),
            total_quantite=Sum('quantite')
        )
        
        # Pagination
        paginator = Paginator(lignes_query, limit)
        page_obj = paginator.get_page(page)
        
        # Formater les résultats
        lignes_data = []
        for ligne in page_obj:
            reduction = float(ligne.prix_original - ligne.prix_unitaire) if ligne.prix_original else 0
            reduction_pct = ligne.reduction_pourcentage
            
            lignes_data.append({
                'id': ligne.id,
                'vente': {
                    'id': ligne.vente.id,
                    'numero_facture': ligne.vente.numero_facture,
                    'date': ligne.vente.date_vente.isoformat(),
                    'nom_client': ligne.vente.nom_client or 'Client anonyme'
                },
                'article': {
                    'id': ligne.article.id,
                    'code': ligne.article.code,
                    'nom': ligne.article.nom
                },
                'quantite': ligne.quantite,
                'prix_original': str(ligne.prix_original),
                'prix_negocie': str(ligne.prix_unitaire),
                'reduction_unitaire': str(reduction),
                'reduction_totale': str(reduction * ligne.quantite),
                'reduction_pourcentage': reduction_pct,
                'devise': ligne.devise
            })
        
        return Response({
            'success': True,
            'boutique': {
                'id': boutique.id,
                'nom': boutique.nom
            },
            'statistiques': {
                'total_negociations': stats['total_lignes'] or 0,
                'total_reduction': str(stats['total_reduction'] or 0),
                'total_articles_negocies': stats['total_quantite'] or 0
            },
            'pagination': {
                'page': page,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            },
            'negociations': lignes_data
        })
        
    except Exception as e:
        logger.error(f"❌ Erreur rapport négociations: {str(e)}")
        return Response({
            'error': 'Erreur lors de la génération du rapport',
            'code': 'REPORT_ERROR',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
