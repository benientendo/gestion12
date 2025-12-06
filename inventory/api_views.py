from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
import logging
import json
import uuid
from datetime import datetime, timedelta
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils import timezone
from .models import Article, Categorie, Vente, Client, SessionClientMaui
from .serializers import (
    ArticleSerializer, 
    CategorieSerializer,
    VenteSerializer
)
from rest_framework.permissions import AllowAny, IsAuthenticated

# Fonction d'assistance pour récupérer un article
def get_article_by_id(article_id):
    """Récupère un article par son ID ou retourne une erreur 404"""
    try:
        return Article.objects.get(id=article_id)
    except Article.DoesNotExist:
        raise ObjectDoesNotExist(f"Article avec ID {article_id} non trouvé")

# ===== AUTHENTIFICATION CLIENTS MAUI =====

@api_view(['POST'])
@permission_classes([AllowAny])
def authentifier_client_maui(request):
    """
    Authentifie un client MAUI avec son numéro de série et ses informations.
    
    Format attendu:
    {
        "numero_serie": "SERIE123456",
        "nom_boutique": "Ma Pharmacie",
        "proprietaire": "Jean Dupont",
        "version_app": "1.0.0",
        "adresse_ip": "192.168.1.100"
    }
    
    Réponse en cas de succès:
    {
        "success": true,
        "token_session": "uuid-token",
        "client_id": 1,
        "message": "Authentification réussie"
    }
    """
    logger = logging.getLogger(__name__)
    
    # Récupérer les données
    numero_serie = request.data.get('numero_serie')
    nom_boutique = request.data.get('nom_boutique', '')
    proprietaire = request.data.get('proprietaire', '')
    version_app = request.data.get('version_app', '')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Obtenir l'adresse IP du client
    adresse_ip = request.data.get('adresse_ip')
    if not adresse_ip:
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
        client = Client.objects.get(numero_serie=numero_serie, est_actif=True)
        
        # Mettre à jour les informations de connexion
        client.derniere_connexion = timezone.now()
        client.derniere_activite = timezone.now()
        
        # Mettre à jour les informations si fournies
        if nom_boutique and nom_boutique != client.nom_boutique:
            client.nom_boutique = nom_boutique
        if proprietaire and proprietaire != client.proprietaire:
            client.proprietaire = proprietaire
            
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
        
        logger.info(f"Client MAUI authentifié: {client.nom_terminal} ({numero_serie})")
        
        # Préparer les informations de réponse avec boutique
        response_data = {
            'success': True,
            'token_session': token_session,
            'client_id': client.id,
            'message': 'Authentification réussie',
            
            # ⭐ AJOUT: Informations utilisateur
            'user': {
                'id': client.compte_proprietaire.id if client.compte_proprietaire else None,
                'username': client.compte_proprietaire.username if client.compte_proprietaire else None
            },
            
            # ⭐ AJOUT: Informations complètes du terminal (client_maui)
            'client_maui': None  # Par défaut
        }
        
        # ⭐ AJOUT: Si le terminal a une boutique, inclure toutes les infos
        if client.boutique:
            response_data['client_maui'] = {
                'id': client.id,
                'numero_serie': client.numero_serie,
                'nom_terminal': client.nom_terminal,
                'boutique_id': client.boutique.id,
                'boutique': {
                    'id': client.boutique.id,
                    'nom': client.boutique.nom,
                    'code': client.boutique.code_boutique,
                    'commercant': client.boutique.commercant.nom_entreprise if hasattr(client.boutique, 'commercant') else '',
                    'type_commerce': client.boutique.type_commerce,
                    'devise': client.boutique.devise
                }
            }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Client.DoesNotExist:
        logger.warning(f"Tentative d'authentification avec numéro de série invalide: {numero_serie}")
        return Response({
            'success': False,
            'error': 'Numéro de série invalide ou client inactif'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    except Exception as e:
        logger.error(f"Erreur lors de l'authentification: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur interne du serveur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def verifier_session_maui(request):
    """
    Vérifie si une session MAUI est toujours valide.
    
    Format attendu:
    {
        "token_session": "uuid-token"
    }
    """
    token_session = request.data.get('token_session')
    
    if not token_session:
        return Response({
            'success': False,
            'error': 'Token de session requis'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        session = SessionClientMaui.objects.get(
            token_session=token_session,
            est_active=True
        )
        
        # Vérifier si la session n'est pas expirée (24h par défaut)
        if session.date_debut < timezone.now() - timedelta(hours=24):
            session.est_active = False
            session.date_fin = timezone.now()
            session.save()
            
            return Response({
                'success': False,
                'error': 'Session expirée'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Mettre à jour la dernière activité du client
        session.client.derniere_activite = timezone.now()
        session.client.save()
        
        return Response({
            'success': True,
            'client_id': session.client.id,
            'nom_boutique': session.client.nom_boutique,
            'message': 'Session valide'
        }, status=status.HTTP_200_OK)
        
    except SessionClientMaui.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Session invalide'
        }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([AllowAny])
def deconnecter_client_maui(request):
    """
    Déconnecte un client MAUI en fermant sa session.
    
    Format attendu:
    {
        "token_session": "uuid-token"
    }
    """
    token_session = request.data.get('token_session')
    
    if not token_session:
        return Response({
            'success': False,
            'error': 'Token de session requis'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        session = SessionClientMaui.objects.get(
            token_session=token_session,
            est_active=True
        )
        
        session.est_active = False
        session.date_fin = timezone.now()
        session.save()
        
        return Response({
            'success': True,
            'message': 'Déconnexion réussie'
        }, status=status.HTTP_200_OK)
        
    except SessionClientMaui.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Session non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)

# ===== FIN AUTHENTIFICATION CLIENTS MAUI =====

def get_client_from_token(request):
    """
    Fonction utilitaire pour récupérer le client MAUI à partir du token de session.
    """
    token_session = request.headers.get('X-MAUI-Token') or request.data.get('token_session')
    
    if not token_session:
        return None, "Token de session MAUI requis"
    
    try:
        session = SessionClientMaui.objects.get(
            token_session=token_session,
            est_active=True
        )
        
        # Vérifier si la session n'est pas expirée (24h par défaut)
        if session.date_debut < timezone.now() - timedelta(hours=24):
            session.est_active = False
            session.date_fin = timezone.now()
            session.save()
            return None, "Session expirée"
        
        # Mettre à jour la dernière activité
        session.client.derniere_activite = timezone.now()
        session.client.save()
        
        return session.client, None
        
    except SessionClientMaui.DoesNotExist:
        return None, "Session invalide"

class ArticleViewSet(viewsets.ModelViewSet):
    queryset = Article.objects.all()
    serializer_class = ArticleSerializer
    permission_classes = [AllowAny]
    
    @action(detail=True, methods=['put'], url_path='stock')
    def update_stock(self, request, pk=None):
        """Endpoint pour mettre à jour le stock d'un article
        
        Format attendu des données:
        {
            "quantite": 10,  # Quantité pour le stock
            "type_mouvement": "AJUSTEMENT",  # Type de mouvement: ACHAT, AJUSTEMENT, etc.
            "mode": "absolu",  # Mode de mise à jour: "absolu" (définir la valeur exacte) ou "relatif" (ajouter/enlever)
            "note": "Ajustement manuel" # Optionnel, note explicative
        }
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            article = self.get_object()
            
            # Validation des données
            quantite = request.data.get('quantite')
            type_mouvement = request.data.get('type_mouvement', 'AJUSTEMENT')
            mode = request.data.get('mode', 'absolu').lower()  # absolu par défaut pour compat. descendante
            note = request.data.get('note', '')
            
            if quantite is None:
                return Response(
                    {'error': 'Le paramètre "quantite" est requis'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                quantite = int(quantite)
            except (ValueError, TypeError):
                return Response(
                    {'error': 'La quantité doit être un nombre entier'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # NOUVELLE APPROCHE: Utilisation de la fonction update_stock_by_article_id
            from .utils import update_stock_by_article_id
            
            # Déterminer le type d'opération en fonction du mode
            if mode == 'absolu':
                # Mode absolu: définir la valeur exacte du stock
                stock_avant = article.quantite_stock
                
                # Si la nouvelle valeur est supérieure, c'est un ajout
                if quantite > stock_avant:
                    difference = quantite - stock_avant
                    is_sale = False
                    details = {'ancien_stock': stock_avant, 'nouveau_stock': quantite, 'note': note}
                    success, message, mouvement = update_stock_by_article_id(
                        article_id=article.id,
                        quantite=difference,  # La différence à ajouter
                        type_mouvement=type_mouvement,
                        reference="",
                        utilisateur=request.user.username if request.user.is_authenticated else 'API',
                        details=details,
                        is_sale=False  # Ajout au stock
                    )
                # Si la nouvelle valeur est inférieure, c'est une réduction
                elif quantite < stock_avant:
                    difference = stock_avant - quantite
                    is_sale = True
                    details = {'ancien_stock': stock_avant, 'nouveau_stock': quantite, 'note': note}
                    success, message, mouvement = update_stock_by_article_id(
                        article_id=article.id,
                        quantite=difference,  # La différence à retirer
                        type_mouvement=type_mouvement,
                        reference="",
                        utilisateur=request.user.username if request.user.is_authenticated else 'API',
                        details=details,
                        is_sale=True  # Retrait du stock
                    )
                else:
                    # Stock inchangé, pas de mouvement à créer
                    return Response({
                        'success': True,
                        'message': f'Stock inchangé: {quantite}',
                        'article': ArticleSerializer(article, context={'request': request}).data
                    }, status=status.HTTP_200_OK)
            else:  # mode == 'relatif'
                # Mode relatif: ajouter ou soustraire au stock existant
                # Si quantite est négative, c'est une vente (retrait)
                is_sale = quantite < 0
                quantite_abs = abs(quantite)  # Toujours travailler avec des quantités positives
                details = {'ajustement': quantite, 'note': note}
                
                success, message, mouvement = update_stock_by_article_id(
                    article_id=article.id,
                    quantite=quantite_abs,
                    type_mouvement=type_mouvement,
                    reference="",
                    utilisateur=request.user.username if request.user.is_authenticated else 'API',
                    details=details,
                    is_sale=is_sale
                )
            
            # Récupérer l'article mis à jour pour retourner les détails actualisés
            article.refresh_from_db()
            
            # Préparer les détails du mouvement pour la réponse
            mouvement_details = None
            if mouvement:
                mouvement_details = {
                    'id': mouvement.id,
                    'type': mouvement.type_mouvement,
                    'quantite': mouvement.quantite,
                    'stock_avant': mouvement.stock_avant,
                    'stock_apres': mouvement.stock_apres,
                    'note': mouvement.note
                }
            
            return Response({
                'success': success,
                'message': message,
                'article': ArticleSerializer(article, context={'request': request}).data,
                'mouvement': mouvement_details
            }, status=status.HTTP_200_OK)
            
        except Article.DoesNotExist:
            return Response(
                {'error': f'Article avec ID {pk} non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du stock: {e}")
            return Response(
                {'error': f'Erreur lors de la mise à jour du stock: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def par_code(self, request):
        import logging
        import json
        import urllib.parse
        from decimal import Decimal, InvalidOperation
        from django.core.exceptions import ValidationError
        
        # Configuration du logging avancé
        logging.basicConfig(level=logging.DEBUG, 
                            format='%(asctime)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)
        
        # Log détaillé des paramètres de requête
        logger.debug(f'Requête complète reçue: {request.query_params}')
        logger.debug(f'Méthode de requête: {request.method}')
        logger.debug(f'En-têtes de la requête: {request.headers}')
        
        # Récupérer le code
        code = request.query_params.get('code')
        logger.info(f'Code reçu brut: {code}')
        
        if not code:
            return Response(
                {'error': 'Paramètre code manquant'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Tentatives multiples de parsing du code
        try:
            # Décoder l'URL si nécessaire
            code = urllib.parse.unquote(code)
            logger.info(f'Code après décodage URL: {code}')
            
            # Cas 1 : JSON encodé deux fois
            try:
                code_data = json.loads(json.loads(code))
                code = code_data.get('code') or code_data
                logger.info('Code parsé comme JSON double')
            except (json.JSONDecodeError, TypeError):
                # Cas 2 : JSON simple
                try:
                    code_data = json.loads(code)
                    code = code_data.get('code') or code
                    logger.info('Code parsé comme JSON simple')
                except (json.JSONDecodeError, TypeError):
                    # Cas 3 : chaîne simple
                    logger.info('Code traité comme chaîne simple')
                    pass
        except Exception as e:
            logger.error(f"Erreur de parsing : {e}")
        
        # Nettoyer et normaliser le code
        code = str(code).strip()
        logger.info(f'Code final: {code}')
        
        try:
            # Rechercher l'article par code
            logger.debug(f'Recherche de l\'article avec le code: {code}')
            logger.debug(f'Tous les codes d\'articles en base :')
            for art in Article.objects.all():
                logger.debug(f'- Code: {art.code}, Nom: {art.nom}')
            
            article = Article.objects.get(code=code)
            logger.info(f'Article trouvé: {article}')
            logger.debug(f'Détails de l\'article :\n- Nom: {article.nom}\n- Prix de vente: {article.prix_vente}\n- Code: {article.code}')
            
            # Validation explicite du prix
            try:
                # Convertir le prix en Decimal
                prix = Decimal(str(article.prix_vente))
                logger.info(f'Prix original: {article.prix_vente}')
                logger.info(f'Prix converti: {prix}')
                
                # Vérifications supplémentaires
                if prix < 0:
                    logger.error(f'Prix négatif: {prix}')
                    return Response(
                        {'error': 'Prix négatif non autorisé'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Vérifier le nombre de décimales
                if len(str(prix).split('.')[-1]) > 2:
                    logger.error(f'Trop de décimales: {prix}')
                    return Response(
                        {'error': 'Prix avec plus de 2 décimales'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Préparer les données de l'article avec un statut de confirmation
                serializer = self.get_serializer(article)
                return Response({
                    'status': 'confirmation_required',
                    'article': serializer.data,
                    'message': 'Voulez-vous ajouter cet article à la liste ?'
                })
            
            except (InvalidOperation, ValueError) as e:
                logger.error(f'Erreur de conversion de prix: {e}')
                return Response(
                    {'error': f'Prix invalide: {article.prix_vente}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        except Article.DoesNotExist:
            return Response(
                {'error': 'Article non trouvé'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Débogage : imprimer tous les codes d'articles
        print(f"Code recherché : {code}")
        print("Tous les codes d'articles :")
        for article in Article.objects.all():
            print(f"- {article.code}")
        
        try:
            # Recherche flexible : ignorer les espaces et la casse
            article = Article.objects.get(code__iexact=code)
            
            # Vérifier les scans récents
            from django.utils import timezone
            from datetime import timedelta
            
            # Vérifier s'il y a eu un scan récent du même article
            time_threshold = timezone.now() - timedelta(minutes=5)  # 5 minutes
            scan_recent = ScanRecent.objects.filter(
                article=article, 
                date_scan__gte=time_threshold
            ).first()
            
            if scan_recent:
                return Response({
                    'status': 'duplicate_scan',
                    'article': serializer.data,
                    'message': 'Cet article est déjà dans la liste. Voulez-vous augmenter sa quantité ?'
                })
            
            # Validation explicite du prix
            try:
                # Convertir le prix en Decimal
                from decimal import Decimal, InvalidOperation
                prix = Decimal(str(article.prix_vente))
                logger.info(f'Prix original: {article.prix_vente}')
                logger.info(f'Prix converti: {prix}')
                
                # Vérifications supplémentaires
                if prix < 0:
                    logger.error(f'Prix négatif: {prix}')
                    return Response(
                        {'error': 'Prix négatif non autorisé'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Vérifier le nombre de décimales
                if len(str(prix).split('.')[-1]) > 2:
                    logger.error(f'Trop de décimales: {prix}')
                    return Response(
                        {'error': 'Prix avec plus de 2 décimales'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Sérialiser l'article
                serializer = self.get_serializer(article)
                return Response(serializer.data)
            
            except (InvalidOperation, ValueError) as e:
                logger.error(f'Erreur de conversion de prix: {e}')
                return Response(
                    {'error': f'Prix invalide: {article.prix_vente}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Article.DoesNotExist:
            return Response(
                {'error': f'Article avec le code {code} non trouvé', 
                 'codes_disponibles': list(Article.objects.values_list('code', flat=True))},
                status=status.HTTP_404_NOT_FOUND
            )

class CategorieViewSet(viewsets.ModelViewSet):
    queryset = Categorie.objects.all()
    serializer_class = CategorieSerializer
    

# Constante pour marquer le début et la fin des blocs d'information MAUI dans le terminal
MAUI_BLOCK_START = "\n" + "="*80 + "\n" + "DONNÉES BRUTES MAUI - DÉBUT" + "\n" + "="*80
MAUI_BLOCK_END = "="*80 + "\n" + "DONNÉES BRUTES MAUI - FIN" + "\n" + "="*80 + "\n"

@api_view(['POST'])
@permission_classes([AllowAny])  # Remplacer par IsAuthenticated en production
def update_stock_efficient(request):
    """
    Endpoint efficace pour mettre à jour le stock d'un article avec des détails améliorés pour l'historique.
    
    Format attendu des données:
    {
        "article_id": 18,  # ID de l'article à mettre à jour
        "quantite": 5,     # Quantité à ajouter ou retirer
        "operation": "VENTE", # Type d'opération: VENTE, ACHAT, AJUSTEMENT, etc.
        "reference": "FAC-123", # Optionnel, référence du document associé
        "details": {       # Optionnel, détails supplémentaires pour l'historique
            "prix_unitaire": 60000,
            "client": "Nom du client"
        },
        "is_sale": true     # Si true, la quantité sera soustraite du stock, sinon ajoutée
    }
    
    Réponse en cas de succès:
    {
        "success": true,
        "message": "Stock mis à jour...",
        "article": { ... détails de l'article ... },
        "mouvement": { ... détails du mouvement ... }
    }
    """
    from .utils import update_stock_by_article_id
    from .serializers import ArticleSerializer
    from .models import Article
    
    # Journal pour débogage
    logger = logging.getLogger(__name__)
    logger.info(f"Requête de mise à jour du stock reçue: {request.data}")
    
    # Récupérer et valider les données
    article_id = request.data.get('article_id')
    quantite = request.data.get('quantite')
    operation = request.data.get('operation', 'VENTE')
    reference = request.data.get('reference', '')
    details = request.data.get('details', {})
    is_sale = request.data.get('is_sale', True)  # Par défaut, c'est une vente (réduction de stock)
    
    # Validation basique
    if not article_id:
        return Response({'error': "ID d'article requis"}, status=status.HTTP_400_BAD_REQUEST)
    
    if not quantite or not isinstance(quantite, int) and not isinstance(quantite, str):
        return Response({'error': "Quantité valide requise"}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        # Convertir article_id en entier
        article_id = int(article_id)
        
        # Récupérer l'utilisateur si disponible
        utilisateur = None
        if request.user and request.user.is_authenticated:
            utilisateur = request.user.username
        
        # Effectuer la mise à jour du stock
        success, message, mouvement = update_stock_by_article_id(
            article_id=article_id,
            quantite=quantite,
            type_mouvement=operation,
            reference=reference,
            utilisateur=utilisateur or "API",
            details=details,
            is_sale=is_sale
        )
        
        if success:
            # Récupérer l'article mis à jour
            article = Article.objects.get(id=article_id)
            
            # Préparer les détails du mouvement
            mouvement_details = None
            if mouvement:
                mouvement_details = {
                    'id': mouvement.id,
                    'article_id': article_id,
                    'article_nom': article.nom,
                    'article_code': article.code,
                    'type_mouvement': mouvement.type_mouvement,
                    'quantite': mouvement.quantite,
                    'stock_avant': mouvement.stock_avant,
                    'stock_apres': mouvement.stock_apres,
                    'date_mouvement': mouvement.date_mouvement.strftime('%Y-%m-%d %H:%M:%S'),
                    'reference': mouvement.reference,
                    'note': mouvement.note
                }
            
            # Retourner le succès avec les détails
            return Response({
                'success': True,
                'message': message,
                'article': ArticleSerializer(article, context={'request': request}).data,
                'mouvement': mouvement_details
            }, status=status.HTTP_200_OK)
        else:
            # Retourner l'erreur
            return Response({
                'success': False,
                'message': message
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du stock: {str(e)}")
        return Response({
            'success': False,
            'message': f"Erreur lors de la mise à jour du stock: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VenteViewSet(viewsets.ModelViewSet):
    queryset = Vente.objects.all()
    serializer_class = VenteSerializer
    permission_classes = [AllowAny]
    

    
    def get_serializer(self, *args, **kwargs):
        # Ajouter le request au context du serializer
        serializer_class = self.get_serializer_class()
        kwargs.setdefault('context', self.get_serializer_context())
        return serializer_class(*args, **kwargs)
    
    @action(detail=False, methods=['post'])
    def finaliser_vente(self, request):
        """
        Endpoint pour finaliser une vente et mettre à jour les stocks.
        Cette méthode permet à l'application MAUI de mettre à jour directement les stocks.
        
        Format attendu des données:
        {
            "token_session": "uuid-token-session",  # Token de session MAUI
            "numero_facture": "FAC123",
            "montant_total": 150.50,
            "mode_paiement": "CASH",
            "version_app": "1.0.0",  # Version de l'app MAUI
            "lignes": [
                {"article_id": 1, "quantite": 2, "prix_unitaire": 25.0},
                {"article_id": 3, "quantite": 1, "prix_unitaire": 100.50}
            ]
        }
        """
        import logging
        from django.db import transaction
        
        logger = logging.getLogger(__name__)
        
        # Authentifier le client MAUI
        client_maui, error_message = get_client_from_token(request)
        if not client_maui:
            return Response({
                'error': 'Authentification requise',
                'details': error_message
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Validation des données reçues
        if not request.data:
            return Response({
                'error': 'Aucune donnée reçue',
                'details': 'Le payload JSON est vide. Veuillez envoyer au minimum: {"reference": "FAC-001", "total": 1000, "lignes": [...]}'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Vérifier les articles et les stocks disponibles
        lignes = request.data.get('lignes', [])
        articles_insuffisants = []
        
        for ligne in lignes:
            article_id = ligne.get('article_id')
            quantite = ligne.get('quantite', 0)
            
            try:
                article = Article.objects.get(id=article_id)
                if article.quantite_stock < quantite:
                    articles_insuffisants.append({
                        'id': article.id,
                        'nom': article.nom,
                        'stock_disponible': article.quantite_stock,
                        'quantite_demandee': quantite
                    })
            except Article.DoesNotExist:
                return Response(
                    {'error': f'Article avec ID {article_id} non trouvé'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Si stock insuffisant, retourner une erreur
        if articles_insuffisants:
            return Response({
                'error': 'Stock insuffisant',
                'details': articles_insuffisants
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtenir l'adresse IP du client
        adresse_ip = request.META.get('HTTP_X_FORWARDED_FOR')
        if adresse_ip:
            adresse_ip = adresse_ip.split(',')[0]
        else:
            adresse_ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        
        # Si tout est OK, procéder à l'enregistrement avec transaction atomique
        try:
            with transaction.atomic():
                # Créer la vente avec les informations du client MAUI
                vente_data = {
                    'numero_facture': request.data.get('numero_facture'),
                    'montant_total': request.data.get('montant_total'),
                    'mode_paiement': request.data.get('mode_paiement'),
                    'paye': True,
                    'lignes_data': lignes,
                    'client_maui': client_maui.id,
                    'adresse_ip_client': adresse_ip,
                    'version_app_maui': request.data.get('version_app', '')
                }
                
                serializer = self.get_serializer(data=vente_data, context={'request': request})
                
                if serializer.is_valid():
                    vente = serializer.save()
                    
                    logger.info(f"Vente {vente.numero_facture} créée par le client MAUI {client_maui.nom_boutique}")
                    
                    return Response({
                        'status': 'success',
                        'message': f'Vente finalisée et stocks mis à jour par {client_maui.nom_boutique}',
                        'vente_id': vente.id,
                        'client_maui': {
                            'id': client_maui.id,
                            'nom_boutique': client_maui.nom_boutique,
                            'proprietaire': client_maui.proprietaire
                        }
                    }, status=status.HTTP_201_CREATED)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                    
        except Exception as e:
            logger.error(f"Erreur lors de la finalisation de la vente: {str(e)}")
            return Response({
                'error': f'Erreur lors de la finalisation: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def create(self, request, *args, **kwargs):
        from decimal import Decimal
        from datetime import datetime
        
        logger = logging.getLogger(__name__)
        
        # Déterminer si la requête vient de MAUI en vérifiant le User-Agent ou d'autres headers
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        is_maui = 'MAUI' in user_agent or 'Xamarin' in user_agent or '.NET' in user_agent
        
        # On peut aussi vérifier le Content-Type ou d'autres patterns spécifiques à MAUI
        if not is_maui and request.content_type and 'application/json' in request.content_type:
            # Vérifier si le format des données correspond à celui attendu de MAUI
            if any(key in request.data for key in ['reference', 'total', 'lignesData', 'lignes']):
                is_maui = True
        
        # Si c'est une requête MAUI, afficher les données brutes dans le terminal
        if is_maui:
            print(MAUI_BLOCK_START)
            print(f"HORODATAGE: {datetime.now().isoformat()}")
            print("\nDONNÉES BRUTES REÇUES DE MAUI:")
            print(json.dumps(request.data, indent=4, default=str))
            print("\nCONTENT-TYPE:", request.content_type)
            print("\nUSER-AGENT:", user_agent)
        
        # Log des données reçues pour le débogage
        print("\n============= DONNÉES BRUTES REÇUES DANS CREATE VENTE =============\n")
        print(f"Type: {type(request.data)}")
        print(f"Content-Type: {request.content_type}")
        
        # Log aussi le body brut pour voir ce qui arrive vraiment
        # Note: On ne peut pas accéder à request.body après avoir lu request.data
        # print(f"Body brut: {request.body}")  # Commenté car cause RawPostDataException
        
        logger.error("\n============= DONNÉES BRUTES REÇUES DANS CREATE VENTE =============\n")
        logger.error(f"Type: {type(request.data)}")
        logger.error(f"Content-Type: {request.content_type}")
        
        try:
            # Afficher le contenu exact pour le débogage
            if hasattr(request.data, 'dict'):
                # Pour les QueryDict
                logger.error(json.dumps(request.data.dict(), indent=2))
            else:
                # Pour les dictionnaires standard
                logger.error(json.dumps(request.data, indent=2))
        except Exception as e:
            logger.error(f"Erreur lors de la sérialisation des données: {e}")
            for key, value in request.data.items():
                logger.error(f"{key}: {type(value)} = {value}")
        
        logger.error("\n==============================================================\n")
        
        # Adapter les données pour le format reçu de l'application MAUI
        adapted_data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        
        # ⭐ GESTION DE LA DATE DE VENTE ENVOYÉE PAR MAUI
        # MAUI envoie typiquement: "2025-12-05T11:58:32" (heure locale du terminal)
        date_str = adapted_data.get('date_vente') or adapted_data.get('date')
        if date_str:
            try:
                # Utiliser fromisoformat pour le format "yyyy-MM-ddTHH:mm:ss"
                date_vente = datetime.fromisoformat(str(date_str))
            except Exception:
                # Fallback uniquement si format inattendu
                date_vente = timezone.now()
            adapted_data['date_vente'] = date_vente
        # Si aucune date n'est fournie, on laisse le modèle appliquer son default (timezone.now)

        # Format spécifique pour le client MAUI observé dans les logs
        # Mapping des clés du format MAUI vers le format Django
        maui_mapping = {
            'reference': 'numero_facture',  # MAUI utilise 'reference' au lieu de 'numero_facture'
            'total': 'montant_total',      # MAUI utilise 'total' au lieu de 'montant_total'
            'lignes': 'lignes_data'        # MAUI utilise 'lignes' au lieu de 'lignes_data'
        }
        
        # Appliquer le mapping MAUI
        for maui_key, django_key in maui_mapping.items():
            if maui_key in adapted_data:
                adapted_data[django_key] = adapted_data[maui_key]
        
        # Mapping standard pour les autres clés camelCase
        camel_mapping = {
            'numeroFacture': 'numero_facture',
            'montantTotal': 'montant_total',
            'modePaiement': 'mode_paiement',
            'lignesData': 'lignes_data'
        }
        
        # Appliquer le mapping camelCase
        for camel_key, snake_key in camel_mapping.items():
            if camel_key in adapted_data:
                adapted_data[snake_key] = adapted_data[camel_key]
        
        # Gestion des formats de nombres décimaux (virgule vs point)
        if 'montant_total' in adapted_data and isinstance(adapted_data['montant_total'], str):
            adapted_data['montant_total'] = float(adapted_data['montant_total'].replace(',', '.'))
        elif 'total' in adapted_data and isinstance(adapted_data['total'], str):
            adapted_data['montant_total'] = float(adapted_data['total'].replace(',', '.'))
        
        # Adapter les lignes de vente
        lignes_data = []
        lignes_source = None
        
        # Déterminer la source des lignes (plusieurs formats possibles)
        if 'lignes_data' in adapted_data:
            lignes_source = adapted_data['lignes_data']
        elif 'lignes' in adapted_data:
            lignes_source = adapted_data['lignes']
        elif 'lignesData' in adapted_data:
            lignes_source = adapted_data['lignesData']
            
        if lignes_source:
            for ligne in lignes_source:
                normalized_ligne = {}
                
                # ID de l'article
                article_id = None
                if 'articleId' in ligne:
                    article_id = ligne['articleId']
                elif 'article_id' in ligne:
                    article_id = ligne['article_id']
                
                # Vérifier si l'ID de l'article est valide
                if article_id == 0 or article_id is None:
                    logger.warning(f"ID d'article non valide: {article_id}, recherche de valeurs alternatives")
                    # Tentative de récupération d'un ID valide depuis l'article lié
                    if 'article' in ligne and ligne['article'] and isinstance(ligne['article'], dict):
                        if 'id' in ligne['article']:
                            article_id = ligne['article']['id']
                            logger.info(f"ID d'article récupéré depuis l'objet article: {article_id}")
                    
                    # Si l'ID est invalide mais que nous avons un prix unitaire, essayons de trouver l'article par son prix
                    if (article_id == 0 or article_id is None) and 'prix_unitaire' in ligne:
                        from .models import Article
                        from decimal import Decimal
                        
                        prix_unitaire_str = str(ligne['prix_unitaire']).replace(',', '.')
                        try:
                            prix_unitaire = Decimal(prix_unitaire_str)
                            
                            # Rechercher un article avec un prix similaire (marge de 0.01)
                            articles = Article.objects.filter(
                                prix_vente__range=(prix_unitaire - Decimal('0.01'), prix_unitaire + Decimal('0.01'))
                            )
                            
                            # Si nous avons trouvé un article correspondant au prix
                            if articles.exists():
                                article_trouve = articles.first()
                                article_id = article_trouve.id
                                logger.info(f"Article trouvé par correspondance de prix: {article_id} - {article_trouve.nom} à {article_trouve.prix_vente}")
                            else:
                                logger.warning(f"Aucun article trouvé avec le prix unitaire {prix_unitaire}")
                                
                        except (ValueError, TypeError) as e:
                            logger.error(f"Erreur lors de la conversion du prix unitaire '{prix_unitaire_str}': {str(e)}")
                
                # Si l'ID est toujours invalide, essayons d'identifier l'article par son nom ou code (si disponible)
                if (article_id == 0 or article_id is None) and 'article' in ligne and isinstance(ligne['article'], dict):
                    from .models import Article
                    article_data = ligne['article']
                    
                    # Essayer de trouver par nom
                    if 'nom' in article_data and article_data['nom']:
                        articles = Article.objects.filter(nom__iexact=article_data['nom'])
                        if articles.exists():
                            article_trouve = articles.first()
                            article_id = article_trouve.id
                            logger.info(f"Article trouvé par nom: {article_id} - {article_trouve.nom}")
                    
                    # Essayer de trouver par code
                    elif 'code' in article_data and article_data['code']:
                        articles = Article.objects.filter(code__iexact=article_data['code'])
                        if articles.exists():
                            article_trouve = articles.first()
                            article_id = article_trouve.id
                            logger.info(f"Article trouvé par code: {article_id} - {article_trouve.code}")
                
                # Si l'ID est toujours invalide et nous avons un libellé, essayons de trouver par libellé
                if (article_id == 0 or article_id is None) and 'libelle' in ligne and ligne['libelle']:
                    try:
                        article = get_article_by_id(None)
                        article_id = article.id
                        logger.info(f"Article trouvé par libellé: {article_id} - {article.nom}")
                    except ObjectDoesNotExist:
                        return Response(
                            {'error': f"Aucun article trouvé avec le libellé {ligne['libelle']}"},
                            status=status.HTTP_404_NOT_FOUND
                        )
                
                # Si l'ID est toujours invalide, retourner une erreur
                if article_id == 0 or article_id is None:
                    return Response(
                        {'error': "Aucun article valide trouvé pour cette ligne de vente"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Vérifier l'existence de l'article et le stock disponible
                try:
                    article = get_article_by_id(article_id)
                    quantite = ligne.get('quantite', ligne.get('quantité', 1))
                    if article.quantite_stock < quantite:
                        return Response(
                            {'error': f"Stock insuffisant pour l'article {article.nom}. Stock disponible: {article.quantite_stock}, Quantité demandée: {quantite}"},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    normalized_ligne['article_id'] = article_id
                except ObjectDoesNotExist as e:
                    return Response(
                        {'error': str(e)},
                        status=status.HTTP_404_NOT_FOUND
                    )
                    
                normalized_ligne['article_id'] = article_id
                
                # Quantité
                if 'quantite' in ligne:
                    normalized_ligne['quantite'] = int(ligne['quantite'])
                elif 'quantité' in ligne:
                    normalized_ligne['quantite'] = int(ligne['quantité'])
                else:
                    normalized_ligne['quantite'] = 1  # Valeur par défaut
                
                # Prix unitaire
                if 'prixUnitaire' in ligne:
                    normalized_ligne['prix_unitaire'] = float(str(ligne['prixUnitaire']).replace(',', '.'))
                elif 'prix_unitaire' in ligne:
                    normalized_ligne['prix_unitaire'] = float(str(ligne['prix_unitaire']).replace(',', '.'))
                
                # Montant de la ligne (calculé si non fourni)
                if 'montantLigne' in ligne and ligne['montantLigne']:
                    normalized_ligne['montant_ligne'] = float(str(ligne['montantLigne']).replace(',', '.'))
                elif 'montant_ligne' in ligne and ligne['montant_ligne']:
                    normalized_ligne['montant_ligne'] = float(str(ligne['montant_ligne']).replace(',', '.'))
                else:
                    # Calcul automatique du montant de la ligne
                    normalized_ligne['montant_ligne'] = normalized_ligne['quantite'] * normalized_ligne['prix_unitaire']
                
                lignes_data.append(normalized_ligne)
            
            # Mettre à jour les données adaptées avec les lignes normalisées
            adapted_data['lignes_data'] = lignes_data
            
            # Recalculer le montant total si nécessaire
            if 'montant_total' not in adapted_data or adapted_data.get('montant_total', 0) == 0:
                montant_total = sum(ligne['montant_ligne'] for ligne in lignes_data)
                adapted_data['montant_total'] = montant_total
                logger.info(f"Montant total recalculé: {montant_total}")
                
            # Si c'est une requête MAUI, afficher les données adaptées
            if is_maui:
                print("\nDONNÉES ADAPTÉES:")
                print(json.dumps(adapted_data, indent=4, default=str))
        
        # Vérifier que les données essentielles sont présentes
        if not adapted_data.get('lignes_data') and not lignes_source:
            return Response({
                'error': 'Aucun article dans la vente',
                'details': 'Veuillez ajouter au moins un article avec: {"lignes": [{"article_id": 1, "quantite": 1, "prix_unitaire": 1000}]}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not adapted_data.get('montant_total') and not lignes_source:
            return Response({
                'error': 'Montant total manquant',
                'details': 'Veuillez spécifier le montant total avec: {"total": 1000} ou {"montant_total": 1000}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # S'assurer que tous les champs obligatoires sont présents
        if 'numero_facture' not in adapted_data or not adapted_data['numero_facture']:
            # Générer un numéro de facture si non fourni
            from datetime import datetime
            adapted_data['numero_facture'] = f"FAC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            logger.info(f"Numéro de facture généré: {adapted_data['numero_facture']}")
        
        if 'paye' not in adapted_data:
            adapted_data['paye'] = True  # Par défaut, la vente est marquée comme payée
        
        if 'mode_paiement' not in adapted_data:
            adapted_data['mode_paiement'] = "CASH"  # Mode de paiement par défaut
        
        # Vérifier que toutes les lignes ont un article valide et un stock suffisant
        for ligne in adapted_data.get('lignes_data', []):
            article_id = ligne.get('article_id')
            if not article_id:
                return Response(
                    {'error': "Toutes les lignes doivent avoir un article valide"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                article = get_article_by_id(article_id)
                quantite = ligne.get('quantite', 1)
                if article.quantite_stock < quantite:
                    return Response(
                        {'error': f"Stock insuffisant pour l'article {article.nom}. Stock disponible: {article.quantite_stock}, Quantité demandée: {quantite}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except ObjectDoesNotExist as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_404_NOT_FOUND
                )
            
        # Log des données adaptées
        logger.error("\n============= DONNÉES ADAPTÉES DANS CREATE VENTE =============\n")
        try:
            logger.error(json.dumps(adapted_data, default=str, indent=2))
        except Exception as e:
            logger.error(f"Erreur lors de la sérialisation des données adaptées: {e}")
        
        # Créer le serializer avec les données adaptées
        serializer = self.get_serializer(data=adapted_data)
        
        # Vérifier la validité
        if not serializer.is_valid():
            logger.error("\n============= ERREURS DE VALIDATION =============\n")
            logger.error(json.dumps(serializer.errors, indent=2))
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Sauvegarder la vente
        try:
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            
            # Si c'est une requête MAUI, afficher la réponse
            if is_maui:
                print("\nRÉPONSE ENVOYÉE:")
                print(json.dumps(serializer.data, indent=4, default=str))
                print(MAUI_BLOCK_END)
            
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
                headers=headers
            )
        except Exception as e:
            logger.error(f"Erreur lors de la création de la vente: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    

