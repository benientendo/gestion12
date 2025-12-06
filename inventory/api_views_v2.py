"""
API v2 Multi-Boutiques avec Isolation des Données
================================================

Cette API garantit une isolation complète des données par boutique basée sur le numéro de série du terminal MAUI.
Chaque terminal ne peut accéder qu'aux données de sa boutique associée.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from django.db.models import Sum, Q
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from datetime import datetime, time
import json
import logging

from .models import (
    Client, Boutique, Article, Categorie, Vente, LigneVente, 
    MouvementStock, SessionClientMaui, RapportCaisse
)
from .serializers import ArticleSerializer, CategorieSerializer, VenteSerializer, RapportCaisseSerializer

logger = logging.getLogger(__name__)


# ===== FONCTIONS UTILITAIRES =====

def get_boutique_from_terminal(numero_serie):
    """
    Récupère la boutique associée à un terminal MAUI via son numéro de série.
    Retourne None si le terminal n'existe pas ou n'est pas actif.
    """
    try:
        terminal = Client.objects.select_related('boutique__commercant').get(
            numero_serie=numero_serie,
            est_actif=True
        )
        
        if not terminal.boutique or not terminal.boutique.est_active:
            return None
            
        return terminal.boutique
    except Client.DoesNotExist:
        return None


def validate_boutique_access(request, boutique_id):
    """
    Valide que l'utilisateur a accès à la boutique spécifiée.
    Retourne la boutique si l'accès est autorisé, sinon lève une exception.
    """
    try:
        boutique = Boutique.objects.select_related('commercant').get(
            id=boutique_id,
            est_active=True
        )
        
        # Vérifier que l'utilisateur est le commerçant propriétaire
        if hasattr(request.user, 'profil_commercant'):
            if boutique.commercant != request.user.profil_commercant:
                raise ValidationError("Accès refusé à cette boutique")
        else:
            # Pour les terminaux MAUI, vérifier via le numéro de série
            terminal = Client.objects.filter(
                compte_proprietaire=request.user,
                boutique=boutique,
                est_actif=True
            ).first()
            
            if not terminal:
                raise ValidationError("Terminal non autorisé pour cette boutique")
        
        return boutique
        
    except Boutique.DoesNotExist:
        raise ValidationError("Boutique non trouvée ou inactive")


# ===== AUTHENTIFICATION MAUI =====

@api_view(['POST'])
def maui_auth_v2(request):
    """
    Authentification MAUI v2 avec association automatique à la boutique.
    
    Paramètres:
    - numero_serie: Numéro de série unique du terminal
    - version_app: Version de l'application MAUI (optionnel)
    
    Retourne:
    - token: Token JWT pour les appels API
    - boutique_id: ID de la boutique associée au terminal
    - informations complètes de la boutique
    """
    numero_serie = request.data.get('numero_serie')
    version_app = request.data.get('version_app', '')
    
    if not numero_serie:
        return Response({
            'error': 'Numéro de série requis',
            'code': 'MISSING_SERIAL'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Trouver le terminal et sa boutique associée
        terminal = Client.objects.select_related(
            'boutique__commercant__user'
        ).get(
            numero_serie=numero_serie,
            est_actif=True
        )
        
        # Vérifier que la boutique est active
        if not terminal.boutique:
            return Response({
                'error': 'Terminal non associé à une boutique',
                'code': 'NO_BOUTIQUE'
            }, status=status.HTTP_403_FORBIDDEN)
            
        if not terminal.boutique.est_active:
            return Response({
                'error': 'Boutique désactivée',
                'code': 'BOUTIQUE_INACTIVE'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Mettre à jour les informations de connexion
        terminal.derniere_connexion = timezone.now()
        terminal.derniere_activite = timezone.now()
        terminal.version_app_maui = version_app
        if hasattr(request, 'META'):
            terminal.derniere_adresse_ip = request.META.get('REMOTE_ADDR')
        terminal.save(update_fields=[
            'derniere_connexion', 'derniere_activite', 
            'version_app_maui', 'derniere_adresse_ip'
        ])
        
        # Créer le token JWT pour le compte propriétaire
        user = terminal.compte_proprietaire
        refresh = RefreshToken.for_user(user)
        
        # Préparer les informations de réponse
        boutique = terminal.boutique
        
        response_data = {
            'token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'expires_in': 3600,  # 1 heure
            
            # Informations utilisateur
            'user': {
                'id': user.id,
                'username': user.username
            },
            
            # ⭐ IMPORTANT: Format compatible avec MAUI
            # MAUI cherche "client_maui" avec boutique imbriquée
            'client_maui': {
                'id': terminal.id,
                'numero_serie': terminal.numero_serie,
                'nom_terminal': terminal.nom_terminal,
                'derniere_connexion': terminal.derniere_connexion.isoformat() if terminal.derniere_connexion else None,
                
                # Informations boutique imbriquées (CRITIQUE pour l'isolation)
                'boutique_id': boutique.id,
                'boutique': {
                    'id': boutique.id,
                    'nom': boutique.nom,
                    'code': boutique.code_boutique,
                    'commercant': boutique.commercant.nom_entreprise,
                    'type_commerce': boutique.type_commerce,
                    'ville': boutique.ville,
                    'devise': boutique.devise
                }
            }
        }
        
        logger.info(f"Authentification réussie - Terminal: {numero_serie}, Boutique: {boutique.nom} (ID: {boutique.id})")
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Client.DoesNotExist:
        logger.warning(f"Tentative d'authentification avec numéro de série inexistant: {numero_serie}")
        return Response({
            'error': 'Terminal non autorisé ou inexistant',
            'code': 'TERMINAL_NOT_FOUND'
        }, status=status.HTTP_403_FORBIDDEN)
    
    except Exception as e:
        logger.error(f"Erreur lors de l'authentification MAUI: {str(e)}")
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== ARTICLES API V2 =====

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def articles_list_v2(request):
    """
    Liste des articles filtrés par boutique.
    
    Paramètres obligatoires:
    - boutique_id: ID de la boutique
    
    Paramètres optionnels:
    - search: Recherche par nom ou code
    - categorie_id: Filtrage par catégorie
    - actifs_seulement: true/false (défaut: true)
    """
    boutique_id = request.GET.get('boutique_id')
    
    if not boutique_id:
        return Response({
            'error': 'Paramètre boutique_id requis',
            'code': 'MISSING_BOUTIQUE_ID'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Valider l'accès à la boutique
        boutique = validate_boutique_access(request, boutique_id)
        
        # Filtrer les articles par boutique
        articles = Article.objects.filter(boutique=boutique)
        
        # Filtres optionnels
        search = request.GET.get('search', '').strip()
        if search:
            articles = articles.filter(
                Q(nom__icontains=search) | 
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        categorie_id = request.GET.get('categorie_id')
        if categorie_id:
            articles = articles.filter(categorie_id=categorie_id)
        
        actifs_seulement = request.GET.get('actifs_seulement', 'true').lower() == 'true'
        if actifs_seulement:
            articles = articles.filter(est_actif=True)
        
        # Sérialiser et retourner
        articles = articles.select_related('categorie').order_by('nom')
        serializer = ArticleSerializer(articles, many=True)
        
        logger.info(f"Articles récupérés - Boutique: {boutique.nom}, Nombre: {articles.count()}")
        
        return Response({
            'success': True,
            'count': articles.count(),
            'boutique_id': boutique.id,
            'boutique_nom': boutique.nom,
            'articles': serializer.data
        }, status=status.HTTP_200_OK)
        
    except ValidationError as e:
        return Response({
            'error': str(e),
            'code': 'ACCESS_DENIED'
        }, status=status.HTTP_403_FORBIDDEN)
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des articles: {str(e)}")
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_stock_v2(request, article_id):
    """
    Mise à jour du stock d'un article avec isolation par boutique.
    
    Paramètres:
    - boutique_id: ID de la boutique
    - quantite_stock: Nouvelle quantité en stock
    - type_mouvement: Type de mouvement (ENTREE, SORTIE, AJUSTEMENT)
    - commentaire: Commentaire optionnel
    """
    boutique_id = request.data.get('boutique_id')
    
    if not boutique_id:
        return Response({
            'error': 'Paramètre boutique_id requis',
            'code': 'MISSING_BOUTIQUE_ID'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Valider l'accès à la boutique
        boutique = validate_boutique_access(request, boutique_id)
        
        # CRITIQUE: Vérifier que l'article appartient à cette boutique
        article = get_object_or_404(
            Article, 
            id=article_id, 
            boutique=boutique  # Isolation par boutique
        )
        
        # Récupérer les paramètres
        nouvelle_quantite = request.data.get('quantite_stock')
        type_mouvement = request.data.get('type_mouvement', 'AJUSTEMENT')
        commentaire = request.data.get('commentaire', '')
        
        if nouvelle_quantite is None:
            return Response({
                'error': 'Paramètre quantite_stock requis',
                'code': 'MISSING_QUANTITY'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            nouvelle_quantite = int(nouvelle_quantite)
            if nouvelle_quantite < 0:
                raise ValueError("Quantité négative")
        except (ValueError, TypeError):
            return Response({
                'error': 'Quantité invalide',
                'code': 'INVALID_QUANTITY'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculer la différence
        ancienne_quantite = article.quantite_stock
        difference = nouvelle_quantite - ancienne_quantite
        
        # Mettre à jour l'article
        article.quantite_stock = nouvelle_quantite
        article.save(update_fields=['quantite_stock'])
        
        # Enregistrer le mouvement de stock
        if difference != 0:
            MouvementStock.objects.create(
                article=article,
                type_mouvement=type_mouvement,
                quantite=difference,
                commentaire=commentaire or f"Mise à jour via API v2 - Boutique: {boutique.nom}"
            )
        
        logger.info(f"Stock mis à jour - Article: {article.nom}, Boutique: {boutique.nom}, Ancienne quantité: {ancienne_quantite}, Nouvelle quantité: {nouvelle_quantite}")
        
        return Response({
            'success': True,
            'article_id': article.id,
            'article_nom': article.nom,
            'ancienne_quantite': ancienne_quantite,
            'nouvelle_quantite': nouvelle_quantite,
            'difference': difference,
            'boutique_id': boutique.id
        }, status=status.HTTP_200_OK)
        
    except ValidationError as e:
        return Response({
            'error': str(e),
            'code': 'ACCESS_DENIED'
        }, status=status.HTTP_403_FORBIDDEN)
    
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du stock: {str(e)}")
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== CATÉGORIES API V2 =====

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def categories_list_v2(request):
    """
    Liste des catégories filtrées par boutique.
    """
    boutique_id = request.GET.get('boutique_id')
    
    if not boutique_id:
        return Response({
            'error': 'Paramètre boutique_id requis',
            'code': 'MISSING_BOUTIQUE_ID'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Valider l'accès à la boutique
        boutique = validate_boutique_access(request, boutique_id)
        
        # Filtrer les catégories par boutique
        categories = Categorie.objects.filter(boutique=boutique).order_by('nom')
        
        serializer = CategorieSerializer(categories, many=True)
        
        return Response({
            'success': True,
            'count': categories.count(),
            'boutique_id': boutique.id,
            'categories': serializer.data
        }, status=status.HTTP_200_OK)
        
    except ValidationError as e:
        return Response({
            'error': str(e),
            'code': 'ACCESS_DENIED'
        }, status=status.HTTP_403_FORBIDDEN)
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des catégories: {str(e)}")
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== VENTES API V2 =====

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_vente_v2(request):
    """
    Création d'une vente avec isolation par boutique.
    
    Paramètres:
    - boutique_id: ID de la boutique
    - numero_facture: Numéro de facture unique
    - mode_paiement: Mode de paiement
    - lignes: Liste des lignes de vente
    """
    boutique_id = request.data.get('boutique_id')
    
    if not boutique_id:
        return Response({
            'error': 'Paramètre boutique_id requis',
            'code': 'MISSING_BOUTIQUE_ID'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Valider l'accès à la boutique
        boutique = validate_boutique_access(request, boutique_id)
        
        # Trouver le terminal MAUI associé à l'utilisateur et à la boutique
        terminal = Client.objects.filter(
            compte_proprietaire=request.user,
            boutique=boutique,
            est_actif=True
        ).first()
        
        if not terminal:
            return Response({
                'error': 'Terminal non trouvé pour cette boutique',
                'code': 'TERMINAL_NOT_FOUND'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Préparer les données de vente
        vente_data = request.data.copy()
        
        date_str = vente_data.get('date_vente') or vente_data.get('date')
        if date_str:
            date_vente = parse_datetime(date_str)
            if date_vente is None:
                date_vente = timezone.now()
            elif timezone.is_naive(date_vente):
                date_vente = timezone.make_aware(date_vente)
        else:
            date_vente = timezone.now()
        
        # Créer la vente
        vente = Vente.objects.create(
            numero_facture=vente_data.get('numero_facture'),
            date_vente=date_vente,
            montant_total=0,  # Sera calculé avec les lignes
            mode_paiement=vente_data.get('mode_paiement', 'CASH'),
            paye=vente_data.get('paye', True),
            client_maui=terminal,
            adresse_ip_client=request.META.get('REMOTE_ADDR'),
            version_app_maui=terminal.version_app_maui
        )
        
        montant_total = 0
        lignes_creees = []
        
        # Traiter chaque ligne de vente
        for ligne_data in vente_data.get('lignes', []):
            article_id = ligne_data.get('article_id')
            quantite = ligne_data.get('quantite', 1)
            
            # CRITIQUE: Vérifier que l'article appartient à la boutique
            try:
                article = Article.objects.get(
                    id=article_id,
                    boutique=boutique,  # Isolation par boutique
                    est_actif=True
                )
            except Article.DoesNotExist:
                # Annuler la vente si un article n'appartient pas à la boutique
                vente.delete()
                return Response({
                    'error': f'Article {article_id} non trouvé dans cette boutique',
                    'code': 'ARTICLE_NOT_FOUND'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Vérifier le stock disponible
            if article.quantite_stock < quantite:
                vente.delete()
                return Response({
                    'error': f'Stock insuffisant pour {article.nom} (disponible: {article.quantite_stock}, demandé: {quantite})',
                    'code': 'INSUFFICIENT_STOCK'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Créer la ligne de vente
            prix_unitaire = ligne_data.get('prix_unitaire', article.prix_vente)
            ligne_vente = LigneVente.objects.create(
                vente=vente,
                article=article,
                quantite=quantite,
                prix_unitaire=prix_unitaire
            )
            
            # Décrémenter le stock
            article.quantite_stock -= quantite
            article.save(update_fields=['quantite_stock'])
            
            # Enregistrer le mouvement de stock
            MouvementStock.objects.create(
                article=article,
                type_mouvement='VENTE',
                quantite=-quantite,
                commentaire=f"Vente {vente.numero_facture} - Terminal: {terminal.nom_terminal}"
            )
            
            montant_total += ligne_vente.total_ligne
            lignes_creees.append({
                'article_id': article.id,
                'article_nom': article.nom,
                'quantite': quantite,
                'prix_unitaire': float(prix_unitaire),
                'total_ligne': float(ligne_vente.total_ligne)
            })
        
        # Mettre à jour le montant total
        vente.montant_total = montant_total
        vente.save(update_fields=['montant_total'])
        
        logger.info(f"Vente créée - Facture: {vente.numero_facture}, Boutique: {boutique.nom}, Montant: {montant_total}")
        
        return Response({
            'success': True,
            'vente_id': vente.id,
            'numero_facture': vente.numero_facture,
            'montant_total': float(montant_total),
            'boutique_id': boutique.id,
            'terminal_id': terminal.id,
            'lignes': lignes_creees,
            'date_vente': vente.date_vente.isoformat()
        }, status=status.HTTP_201_CREATED)
        
    except ValidationError as e:
        return Response({
            'error': str(e),
            'code': 'ACCESS_DENIED'
        }, status=status.HTTP_403_FORBIDDEN)
    
    except Exception as e:
        logger.error(f"Erreur lors de la création de la vente: {str(e)}")
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== INFORMATIONS BOUTIQUE =====

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def boutique_info_v2(request, boutique_id):
    """
    Informations détaillées d'une boutique.
    """
    try:
        # Valider l'accès à la boutique
        boutique = validate_boutique_access(request, boutique_id)
        
        # Calculer les statistiques
        nb_articles = boutique.articles.filter(est_actif=True).count()
        nb_categories = boutique.categories.count()
        nb_ventes_aujourd_hui = boutique.nombre_ventes_aujourd_hui()
        ca_aujourd_hui = boutique.chiffre_affaires_aujourd_hui()
        
        return Response({
            'success': True,
            'boutique': {
                'id': boutique.id,
                'nom': boutique.nom,
                'code_boutique': boutique.code_boutique,
                'type_commerce': boutique.type_commerce,
                'ville': boutique.ville,
                'devise': boutique.devise,
                'commercant': boutique.commercant.nom_entreprise,
                'date_creation': boutique.date_creation.isoformat()
            },
            'statistiques': {
                'nb_articles': nb_articles,
                'nb_categories': nb_categories,
                'nb_ventes_aujourd_hui': nb_ventes_aujourd_hui,
                'ca_aujourd_hui': float(ca_aujourd_hui)
            }
        }, status=status.HTTP_200_OK)
        
    except ValidationError as e:
        return Response({
            'error': str(e),
            'code': 'ACCESS_DENIED'
        }, status=status.HTTP_403_FORBIDDEN)
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des informations boutique: {str(e)}")
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== VALIDATION SESSION =====

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_session_v2(request):
    """
    Validation d'une session MAUI active.
    """
    numero_serie = request.data.get('numero_serie')
    
    if not numero_serie:
        return Response({
            'error': 'Numéro de série requis',
            'code': 'MISSING_SERIAL'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Vérifier que le terminal existe et est actif
        terminal = Client.objects.select_related('boutique').get(
            numero_serie=numero_serie,
            compte_proprietaire=request.user,
            est_actif=True
        )
        
        if not terminal.boutique or not terminal.boutique.est_active:
            return Response({
                'error': 'Boutique inactive ou non associée',
                'code': 'BOUTIQUE_INACTIVE'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Mettre à jour la dernière activité
        terminal.derniere_activite = timezone.now()
        terminal.save(update_fields=['derniere_activite'])
        
        return Response({
            'success': True,
            'valid': True,
            'boutique_id': terminal.boutique.id,
            'terminal_id': terminal.id,
            'derniere_activite': terminal.derniere_activite.isoformat()
        }, status=status.HTTP_200_OK)
        
    except Client.DoesNotExist:
        return Response({
            'error': 'Terminal non trouvé ou non autorisé',
            'code': 'TERMINAL_NOT_FOUND'
        }, status=status.HTTP_403_FORBIDDEN)
    
    except Exception as e:
        logger.error(f"Erreur lors de la validation de session: {str(e)}")
        return Response({
            'error': 'Erreur interne du serveur',
            'code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RapportCaisseListCreateView(APIView):
    """Création et liste des rapports de caisse via header X-Device-Serial.

    - POST /api/v2/rapports-caisse/
      Body JSON:
      {
        "detail": "Cloture du soir, panne réseau 30 minutes, sortie carburant.",
        "depense": 50000,
        "devise": "CDF",
        "date_rapport": "2025-11-30T21:00:00Z"  # optionnel
      }

    - GET /api/v2/rapports-caisse/
      Filtres optionnels:
        ?date_min=2025-11-01
        ?date_max=2025-11-30
        ?par_terminal=true
    """

    permission_classes = [AllowAny]

    def _get_terminal_and_boutique(self, request):
        numero_serie = (
            request.headers.get('X-Device-Serial')
            or request.headers.get('Device-Serial')
            or request.headers.get('Serial-Number')
            or request.META.get('HTTP_X_DEVICE_SERIAL')
            or request.META.get('HTTP_DEVICE_SERIAL')
        )

        if not numero_serie:
            return None, None, Response({
                'error': 'Header X-Device-Serial requis',
                'code': 'MISSING_SERIAL',
                'header_required': 'X-Device-Serial',
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            terminal = Client.objects.select_related('boutique').get(
                numero_serie=numero_serie,
                est_actif=True,
            )
        except Client.DoesNotExist:
            logger.warning(f"Terminal MAUI inconnu ou inactif: {numero_serie}")
            return None, None, Response({
                'error': 'Terminal non autorisé ou inexistant',
                'code': 'TERMINAL_NOT_FOUND',
            }, status=status.HTTP_401_UNAUTHORIZED)

        boutique = terminal.boutique
        if not boutique or not boutique.est_active:
            return terminal, None, Response({
                'error': 'Boutique introuvable ou désactivée pour ce terminal',
                'code': 'BOUTIQUE_INACTIVE',
            }, status=status.HTTP_403_FORBIDDEN)

        return terminal, boutique, None

    def _apply_date_filters(self, queryset, request):
        date_min_str = request.query_params.get('date_min')
        date_max_str = request.query_params.get('date_max')

        def _to_datetime(value, is_max=False):
            if not value:
                return None
            dt = parse_datetime(value)
            if dt is not None:
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt)
                return dt
            d = parse_date(value)
            if d is not None:
                if is_max:
                    combined = datetime.combine(d, time.max)
                else:
                    combined = datetime.combine(d, time.min)
                return timezone.make_aware(combined)
            return None

        if date_min_str:
            dt_min = _to_datetime(date_min_str, is_max=False)
            if dt_min is None:
                raise ValueError(f"Format date_min invalide: {date_min_str}")
            queryset = queryset.filter(date_rapport__gte=dt_min)

        if date_max_str:
            dt_max = _to_datetime(date_max_str, is_max=True)
            if dt_max is None:
                raise ValueError(f"Format date_max invalide: {date_max_str}")
            queryset = queryset.filter(date_rapport__lte=dt_max)

        return queryset

    def get(self, request, format=None):
        terminal, boutique, error_response = self._get_terminal_and_boutique(request)
        if error_response is not None:
            return error_response

        queryset = RapportCaisse.objects.filter(boutique=boutique)

        par_terminal = request.query_params.get('par_terminal')
        if par_terminal and par_terminal.lower() in ('1', 'true', 'yes', 'on'):
            queryset = queryset.filter(terminal=terminal)

        try:
            queryset = self._apply_date_filters(queryset, request)
        except ValueError as e:
            return Response({
                'error': str(e),
                'code': 'INVALID_DATE_FORMAT',
                'expected': 'ISO 8601, ex: 2025-11-30 ou 2025-11-30T00:00:00Z',
            }, status=status.HTTP_400_BAD_REQUEST)

        queryset = queryset.order_by('-date_rapport', '-created_at')

        serializer = RapportCaisseSerializer(queryset, many=True)
        return Response({
            'success': True,
            'count': queryset.count(),
            'boutique_id': boutique.id,
            'boutique_nom': boutique.nom,
            'par_terminal': bool(par_terminal and par_terminal.lower() in ('1', 'true', 'yes', 'on')),
            'results': serializer.data,
        }, status=status.HTTP_200_OK)

    def post(self, request, format=None):
        terminal, boutique, error_response = self._get_terminal_and_boutique(request)
        if error_response is not None:
            return error_response

        data = request.data.copy()
        if not data.get('date_rapport'):
            data['date_rapport'] = timezone.now()

        serializer = RapportCaisseSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        rapport = serializer.save(
            boutique=boutique,
            terminal=terminal,
            est_synchronise=True,
        )

        out_serializer = RapportCaisseSerializer(rapport)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_status_v2(request):
    """
    Endpoint de diagnostic pour l'API v2
    Accessible sans authentification pour debug
    """
    from django.conf import settings
    
    return Response({
        'api_version': 'v2',
        'status': 'active',
        'message': 'API v2 Multi-Boutiques opérationnelle',
        'debug': settings.DEBUG,
        'endpoints': {
            'auth': '/api/v2/auth/maui/',
            'articles': '/api/v2/articles/?boutique_id=X',
            'categories': '/api/v2/categories/?boutique_id=X',
            'ventes': '/api/v2/ventes/',
            'status': '/api/v2/status/'
        },
        'note': 'Tous les endpoints (sauf status) nécessitent une authentification'
    })
