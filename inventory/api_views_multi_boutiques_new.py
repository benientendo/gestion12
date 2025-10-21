# api_views_multi_boutiques.py
# API modifiée pour supporter l'architecture multi-boutiques

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
import logging
import json
import uuid
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
from django.utils import timezone
from .models import Boutique, Client, SessionClientMaui, Article, Categorie, Vente, LigneVente, MouvementStock
from .serializers import ArticleSerializer, CategorieSerializer, VenteSerializer

logger = logging.getLogger(__name__)

# ===== AUTHENTIFICATION TERMINAUX MAUI MULTI-BOUTIQUES =====

@api_view(['POST'])
@permission_classes([AllowAny])
def authentifier_client_maui_multi_boutiques(request):
    """
    Authentifie un client MAUI avec son numéro de série et retourne les informations de sa boutique.
    
    Format attendu:
    {
        "numero_serie": "SERIE123456",
        "version_app": "1.0.0"
    }
    
    Réponse:
    {
        "success": true,
        "token_session": "uuid-token",
        "client_id": 1,
        "boutique": {
            "id": 1,
            "nom": "Ma Pharmacie",
            "code_boutique": "PHAR_BOUT_001",
            "type_commerce": "PHARMACIE",
            "ville": "Paris",
            "devise": "EUR"
        },
        "terminal": {
            "nom_terminal": "Terminal Principal",
            "numero_serie": "SERIE123456"
        }
    }
    """
    # Récupérer les données
    numero_serie = request.data.get('numero_serie')
    version_app = request.data.get('version_app', '')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Obtenir l'adresse IP du client
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        adresse_ip = x_forwarded_for.split(',')[0]
    else:
        adresse_ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    
    # Validation
    if not numero_serie:
        return Response({
            'success': False,
            'error': 'Numéro de série requis'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Rechercher le client par numéro de série
        client = Client.objects.select_related('boutique', 'compte_proprietaire').get(
            numero_serie=numero_serie, 
            est_actif=True
        )
        
        # Vérifier que le client a une boutique associée
        if not client.boutique:
            logger.error(f"Client MAUI {numero_serie} n'a pas de boutique associée")
            return Response({
                'success': False,
                'error': 'Terminal non associé à une boutique'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Vérifier que la boutique est active
        if not client.boutique.est_active:
            logger.error(f"Boutique {client.boutique.nom} est inactive")
            return Response({
                'success': False,
                'error': 'Boutique inactive'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Mettre à jour les informations de connexion
        client.derniere_connexion = timezone.now()
        client.derniere_activite = timezone.now()
        client.derniere_adresse_ip = adresse_ip
        client.version_app_maui = version_app
        client.save()
        
        # Créer une nouvelle session
        token_session = str(uuid.uuid4())
        
        # Fermer les anciennes sessions actives pour ce client
        SessionClientMaui.objects.filter(client=client, est_active=True).update(
            est_active=False,
            date_fin=timezone.now()
        )
        
        # Créer la nouvelle session
        session = SessionClientMaui.objects.create(
            client=client,
            token_session=token_session,
            adresse_ip=adresse_ip,
            user_agent=user_agent,
            version_app=version_app,
            est_active=True
        )
        
        logger.info(f"Client MAUI authentifié: {client.nom_terminal} pour boutique {client.boutique.nom}")
        
        return Response({
            'success': True,
            'token_session': token_session,
            'client_id': client.id,
            'boutique': {
                'id': client.boutique.id,
                'nom': client.boutique.nom,
                'code_boutique': client.boutique.code_boutique,
                'type_commerce': client.boutique.type_commerce,
                'ville': client.boutique.ville,
                'devise': client.boutique.devise,
                'alerte_stock_bas': client.boutique.alerte_stock_bas
            },
            'terminal': {
                'nom_terminal': client.nom_terminal,
                'numero_serie': client.numero_serie,
                'description': client.description
            },
            'message': 'Authentification réussie'
        }, status=status.HTTP_200_OK)
        
    except Client.DoesNotExist:
        logger.warning(f"Tentative d'authentification avec numéro de série invalide: {numero_serie}")
        return Response({
            'success': False,
            'error': 'Numéro de série invalide ou terminal inactif'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    except Exception as e:
        logger.error(f"Erreur lors de l'authentification: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur interne du serveur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== VIEWSETS MULTI-BOUTIQUES =====

class ArticleMultiBoutiquesViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les articles avec filtrage par boutique.
    Chaque terminal MAUI ne voit que les articles de sa boutique.
    """
    serializer_class = ArticleSerializer
    
    def get_queryset(self):
        """
        Filtre les articles par boutique_id fourni en paramètre.
        """
        boutique_id = self.request.query_params.get('boutique_id')
        
        if not boutique_id:
            # Si pas de boutique_id, retourner une queryset vide
            return Article.objects.none()
        
        try:
            # Vérifier que la boutique existe et est active
            boutique = Boutique.objects.get(id=boutique_id, est_active=True)
            
            # Retourner les articles actifs de cette boutique
            return Article.objects.filter(
                boutique=boutique,
                est_actif=True
            ).select_related('categorie').order_by('nom')
            
        except Boutique.DoesNotExist:
            logger.error(f"Boutique {boutique_id} non trouvée ou inactive")
            return Article.objects.none()
    
    def create(self, request, *args, **kwargs):
        """
        Crée un article en l'associant automatiquement à la boutique.
        """
        boutique_id = request.data.get('boutique_id')
        
        if not boutique_id:
            return Response({
                'error': 'boutique_id requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            boutique = Boutique.objects.get(id=boutique_id, est_active=True)
            
            # Ajouter la boutique aux données
            data = request.data.copy()
            data['boutique'] = boutique.id
            
            serializer = self.get_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Boutique.DoesNotExist:
            return Response({
                'error': 'Boutique non trouvée ou inactive'
            }, status=status.HTTP_404_NOT_FOUND)


class CategorieMultiBoutiquesViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les catégories avec filtrage par boutique.
    """
    serializer_class = CategorieSerializer
    
    def get_queryset(self):
        """
        Filtre les catégories par boutique_id.
        """
        boutique_id = self.request.query_params.get('boutique_id')
        
        if not boutique_id:
            return Categorie.objects.none()
        
        try:
            boutique = Boutique.objects.get(id=boutique_id, est_active=True)
            return Categorie.objects.filter(boutique=boutique).order_by('nom')
            
        except Boutique.DoesNotExist:
            return Categorie.objects.none()
    
    def create(self, request, *args, **kwargs):
        """
        Crée une catégorie en l'associant à la boutique.
        """
        boutique_id = request.data.get('boutique_id')
        
        if not boutique_id:
            return Response({
                'error': 'boutique_id requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            boutique = Boutique.objects.get(id=boutique_id, est_active=True)
            
            data = request.data.copy()
            data['boutique'] = boutique.id
            
            serializer = self.get_serializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Boutique.DoesNotExist:
            return Response({
                'error': 'Boutique non trouvée'
            }, status=status.HTTP_404_NOT_FOUND)


class VenteMultiBoutiquesViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les ventes avec filtrage par boutique.
    """
    serializer_class = VenteSerializer
    
    def get_queryset(self):
        """
        Filtre les ventes par boutique via le client_maui.
        """
        boutique_id = self.request.query_params.get('boutique_id')
        
        if not boutique_id:
            return Vente.objects.none()
        
        try:
            boutique = Boutique.objects.get(id=boutique_id, est_active=True)
            return Vente.objects.filter(
                client_maui__boutique=boutique
            ).select_related('client_maui').prefetch_related('lignes__article').order_by('-date_vente')
            
        except Boutique.DoesNotExist:
            return Vente.objects.none()
    
    def create(self, request, *args, **kwargs):
        """
        Crée une vente en vérifiant que le client_maui appartient à la bonne boutique.
        """
        boutique_id = request.data.get('boutique_id')
        client_maui_id = request.data.get('client_maui')
        
        if not boutique_id:
            return Response({
                'error': 'boutique_id requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not client_maui_id:
            return Response({
                'error': 'client_maui requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Vérifier que le client appartient à la boutique
            client = Client.objects.get(
                id=client_maui_id,
                boutique_id=boutique_id,
                est_actif=True
            )
            
            # Vérifier que la boutique est active
            if not client.boutique.est_active:
                return Response({
                    'error': 'Boutique inactive'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Traitement de la vente
            with transaction.atomic():
                serializer = self.get_serializer(data=request.data)
                if serializer.is_valid():
                    vente = serializer.save()
                    
                    # Mettre à jour les stocks pour les articles de cette boutique
                    for ligne in vente.lignes.all():
                        if ligne.article.boutique == client.boutique:
                            ligne.article.quantite_stock -= ligne.quantite
                            ligne.article.save()
                            
                            # Créer un mouvement de stock
                            MouvementStock.objects.create(
                                article=ligne.article,
                                type_mouvement='VENTE',
                                quantite=-ligne.quantite,
                                commentaire=f'Vente {vente.numero_facture}'
                            )
                    
                    logger.info(f"Vente {vente.numero_facture} créée pour boutique {client.boutique.nom}")
                    
                    return Response({
                        'status': 'success',
                        'message': f'Vente finalisée pour {client.boutique.nom}',
                        'vente_id': vente.id,
                        'boutique': {
                            'id': client.boutique.id,
                            'nom': client.boutique.nom
                        }
                    }, status=status.HTTP_201_CREATED)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                    
        except Client.DoesNotExist:
            return Response({
                'error': 'Client MAUI non trouvé ou non associé à cette boutique'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Erreur lors de la création de vente: {str(e)}")
            return Response({
                'error': f'Erreur lors de la création: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== ENDPOINTS UTILITAIRES =====

@api_view(['GET'])
@permission_classes([AllowAny])
def get_boutique_info(request, boutique_id):
    """
    Retourne les informations d'une boutique.
    """
    try:
        boutique = Boutique.objects.select_related('commercant').get(
            id=boutique_id, 
            est_active=True
        )
        
        return Response({
            'id': boutique.id,
            'nom': boutique.nom,
            'type_commerce': boutique.type_commerce,
            'ville': boutique.ville,
            'devise': boutique.devise,
            'alerte_stock_bas': boutique.alerte_stock_bas,
            'commercant': {
                'nom_entreprise': boutique.commercant.nom_entreprise,
                'nom_responsable': boutique.commercant.nom_responsable
            },
            'stats': {
                'total_articles': boutique.articles.filter(est_actif=True).count(),
                'total_categories': boutique.categories.count(),
                'total_terminaux': boutique.clients.filter(est_actif=True).count()
            }
        }, status=status.HTTP_200_OK)
        
    except Boutique.DoesNotExist:
        return Response({
            'error': 'Boutique non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([AllowAny])
def update_stock_multi_boutiques(request):
    """
    Met à jour le stock d'un article en vérifiant la boutique.
    """
    article_id = request.data.get('article_id')
    boutique_id = request.data.get('boutique_id')
    nouvelle_quantite = request.data.get('quantite')
    
    if not all([article_id, boutique_id, nouvelle_quantite is not None]):
        return Response({
            'error': 'article_id, boutique_id et quantite requis'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        article = Article.objects.get(
            id=article_id,
            boutique_id=boutique_id,
            est_actif=True
        )
        
        ancienne_quantite = article.quantite_stock
        article.quantite_stock = int(nouvelle_quantite)
        article.save()
        
        # Créer un mouvement de stock
        difference = int(nouvelle_quantite) - ancienne_quantite
        MouvementStock.objects.create(
            article=article,
            type_mouvement='AJUSTEMENT',
            quantite=difference,
            commentaire=f'Ajustement stock: {ancienne_quantite} → {nouvelle_quantite}'
        )
        
        return Response({
            'success': True,
            'message': f'Stock mis à jour pour {article.nom}',
            'ancienne_quantite': ancienne_quantite,
            'nouvelle_quantite': int(nouvelle_quantite)
        }, status=status.HTTP_200_OK)
        
    except Article.DoesNotExist:
        return Response({
            'error': 'Article non trouvé dans cette boutique'
        }, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        return Response({
            'error': 'Quantité invalide'
        }, status=status.HTTP_400_BAD_REQUEST)
