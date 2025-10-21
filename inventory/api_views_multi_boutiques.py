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
from .models_multi_commercants import Boutique, TerminalMaui, SessionTerminalMaui
from .models_modifications import Article, Categorie, Vente, LigneVente, MouvementStock
from .serializers import ArticleSerializer, CategorieSerializer, VenteSerializer

logger = logging.getLogger(__name__)

# ===== AUTHENTIFICATION TERMINAUX MAUI =====

@api_view(['POST'])
@permission_classes([AllowAny])
def authentifier_terminal_maui(request):
    """
    Authentifie un terminal MAUI avec son numéro de série et l'associe à sa boutique.
    
    Format attendu:
    {
        "numero_serie": "SERIE123456",
        "nom_terminal": "Caisse 1",
        "nom_utilisateur": "Jean Dupont",
        "version_app": "1.0.0"
    }
    
    Réponse:
    {
        "success": true,
        "token_session": "uuid-token",
        "terminal_id": 1,
        "boutique": {
            "id": 1,
            "nom": "Ma Pharmacie",
            "code_boutique": "PHAR_BOUT_001",
            "type_commerce": "PHARMACIE"
        }
    }
    """
    
    # Récupérer les données
    numero_serie = request.data.get('numero_serie')
    nom_terminal = request.data.get('nom_terminal', '')
    nom_utilisateur = request.data.get('nom_utilisateur', '')
    version_app = request.data.get('version_app', '')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Obtenir l'adresse IP
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
        # Rechercher le terminal par numéro de série
        terminal = TerminalMaui.objects.select_related('boutique__commercant').get(
            numero_serie=numero_serie, 
            est_actif=True,
            boutique__est_active=True,
            boutique__commercant__est_actif=True
        )
        
        # Mettre à jour les informations de connexion
        terminal.derniere_connexion = timezone.now()
        terminal.derniere_activite = timezone.now()
        terminal.derniere_adresse_ip = adresse_ip
        
        # Mettre à jour les informations si fournies
        if nom_terminal and nom_terminal != terminal.nom_terminal:
            terminal.nom_terminal = nom_terminal
        if nom_utilisateur and nom_utilisateur != terminal.nom_utilisateur:
            terminal.nom_utilisateur = nom_utilisateur
        if version_app:
            terminal.version_app_maui = version_app
            
        terminal.save()
        
        # Créer une nouvelle session
        token_session = str(uuid.uuid4())
        
        # Fermer les anciennes sessions actives pour ce terminal
        SessionTerminalMaui.objects.filter(terminal=terminal, est_active=True).update(
            est_active=False,
            date_fin=timezone.now()
        )
        
        # Créer la nouvelle session
        session = SessionTerminalMaui.objects.create(
            terminal=terminal,
            token_session=token_session,
            adresse_ip=adresse_ip,
            user_agent=user_agent,
            version_app=version_app,
            est_active=True
        )
        
        logger.info(f"Terminal MAUI authentifié: {terminal.nom_terminal} - Boutique: {terminal.boutique.nom}")
        
        return Response({
            'success': True,
            'token_session': token_session,
            'terminal_id': terminal.id,
            'boutique': {
                'id': terminal.boutique.id,
                'nom': terminal.boutique.nom,
                'code_boutique': terminal.boutique.code_boutique,
                'type_commerce': terminal.boutique.type_commerce,
                'devise': terminal.boutique.devise,
                'commercant': terminal.boutique.commercant.nom_entreprise
            },
            'terminal': {
                'nom': terminal.nom_terminal,
                'utilisateur': terminal.nom_utilisateur
            },
            'message': 'Authentification réussie'
        }, status=status.HTTP_200_OK)
        
    except TerminalMaui.DoesNotExist:
        logger.warning(f"Tentative d'authentification avec numéro de série invalide: {numero_serie}")
        return Response({
            'success': False,
            'error': 'Numéro de série invalide, terminal inactif ou boutique fermée'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    except Exception as e:
        logger.error(f"Erreur lors de l'authentification: {str(e)}")
        return Response({
            'success': False,
            'error': 'Erreur interne du serveur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def get_terminal_from_token(request):
    """
    Fonction utilitaire pour récupérer le terminal MAUI à partir du token de session.
    """
    token_session = request.headers.get('X-MAUI-Token') or request.data.get('token_session')
    
    if not token_session:
        return None, None, "Token de session MAUI requis"
    
    try:
        session = SessionTerminalMaui.objects.select_related(
            'terminal__boutique__commercant'
        ).get(
            token_session=token_session,
            est_active=True
        )
        
        # Vérifier si la session n'est pas expirée (24h par défaut)
        if session.date_debut < timezone.now() - timedelta(hours=24):
            session.est_active = False
            session.date_fin = timezone.now()
            session.save()
            return None, None, "Session expirée"
        
        # Mettre à jour la dernière activité
        session.terminal.derniere_activite = timezone.now()
        session.terminal.save()
        
        return session.terminal, session.terminal.boutique, None
        
    except SessionTerminalMaui.DoesNotExist:
        return None, None, "Session invalide"

# ===== API ARTICLES PAR BOUTIQUE =====

class ArticleBoutiqueViewSet(viewsets.ModelViewSet):
    """ViewSet pour les articles d'une boutique spécifique"""
    serializer_class = ArticleSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        """Retourne les articles de la boutique du terminal authentifié"""
        # Pour les tests, on peut retourner tous les articles
        # En production, il faudra filtrer par boutique
        return Article.objects.all()
    
    def list(self, request):
        """Liste les articles de la boutique du terminal"""
        terminal, boutique, error = get_terminal_from_token(request)
        if error:
            return Response({
                'error': 'Authentification requise',
                'details': error
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Récupérer les articles de la boutique
        articles = Article.objects.filter(
            boutique=boutique,
            est_actif=True
        ).select_related('categorie').order_by('nom')
        
        serializer = self.get_serializer(articles, many=True)
        
        return Response({
            'success': True,
            'boutique': {
                'id': boutique.id,
                'nom': boutique.nom,
                'code_boutique': boutique.code_boutique
            },
            'articles': serializer.data,
            'count': articles.count()
        })
    
    @action(detail=False, methods=['get'])
    def par_code(self, request):
        """Recherche un article par code dans la boutique du terminal"""
        terminal, boutique, error = get_terminal_from_token(request)
        if error:
            return Response({
                'error': 'Authentification requise',
                'details': error
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        code = request.query_params.get('code')
        if not code:
            return Response(
                {'error': 'Paramètre code manquant'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Rechercher l'article dans la boutique
            article = Article.objects.get(
                code=code,
                boutique=boutique,
                est_actif=True
            )
            
            serializer = self.get_serializer(article)
            return Response({
                'success': True,
                'article': serializer.data
            })
            
        except Article.DoesNotExist:
            return Response({
                'error': f'Article avec le code {code} non trouvé dans cette boutique',
                'boutique': boutique.nom
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['put'], url_path='stock')
    def update_stock(self, request, pk=None):
        """Met à jour le stock d'un article de la boutique"""
        terminal, boutique, error = get_terminal_from_token(request)
        if error:
            return Response({
                'error': 'Authentification requise',
                'details': error
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            # Vérifier que l'article appartient à la boutique
            article = Article.objects.get(
                id=pk,
                boutique=boutique,
                est_actif=True
            )
            
            # Traitement de la mise à jour du stock
            quantite = request.data.get('quantite')
            type_mouvement = request.data.get('type_mouvement', 'AJUSTEMENT')
            mode = request.data.get('mode', 'absolu')
            note = request.data.get('note', '')
            
            if quantite is None:
                return Response(
                    {'error': 'Le paramètre "quantite" est requis'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Utiliser la fonction utilitaire pour mettre à jour le stock
            from .utils import update_stock_by_article_id
            
            stock_avant = article.quantite_stock
            
            if mode == 'absolu':
                if quantite > stock_avant:
                    difference = quantite - stock_avant
                    is_sale = False
                elif quantite < stock_avant:
                    difference = stock_avant - quantite
                    is_sale = True
                else:
                    return Response({
                        'success': True,
                        'message': f'Stock inchangé: {quantite}',
                        'article': ArticleSerializer(article).data
                    })
            else:  # mode relatif
                is_sale = quantite < 0
                difference = abs(quantite)
            
            success, message, mouvement = update_stock_by_article_id(
                article_id=article.id,
                quantite=difference,
                type_mouvement=type_mouvement,
                reference="",
                utilisateur=terminal.nom_utilisateur or 'Terminal MAUI',
                details={'terminal': terminal.nom_terminal, 'boutique': boutique.nom, 'note': note},
                is_sale=is_sale
            )
            
            article.refresh_from_db()
            
            return Response({
                'success': success,
                'message': message,
                'article': ArticleSerializer(article).data,
                'boutique': boutique.nom
            })
            
        except Article.DoesNotExist:
            return Response(
                {'error': f'Article avec ID {pk} non trouvé dans cette boutique'},
                status=status.HTTP_404_NOT_FOUND
            )

# ===== API VENTES PAR BOUTIQUE =====

class VenteBoutiqueViewSet(viewsets.ModelViewSet):
    """ViewSet pour les ventes d'une boutique spécifique"""
    serializer_class = VenteSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        return Vente.objects.all()
    
    @action(detail=False, methods=['post'])
    def finaliser_vente(self, request):
        """
        Finalise une vente pour la boutique du terminal authentifié.
        
        Format attendu:
        {
            "token_session": "uuid-token",
            "numero_facture": "FAC123",
            "montant_total": 150.50,
            "mode_paiement": "CASH",
            "lignes": [
                {"article_id": 1, "quantite": 2, "prix_unitaire": 25.0},
                {"article_id": 3, "quantite": 1, "prix_unitaire": 100.50}
            ]
        }
        """
        
        # Authentifier le terminal
        terminal, boutique, error = get_terminal_from_token(request)
        if error:
            return Response({
                'error': 'Authentification requise',
                'details': error
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Validation des données
        if not request.data:
            return Response({
                'error': 'Aucune donnée reçue'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        lignes = request.data.get('lignes', [])
        if not lignes:
            return Response({
                'error': 'Aucune ligne de vente fournie'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier les articles et stocks (seulement dans la boutique)
        articles_insuffisants = []
        
        for ligne in lignes:
            article_id = ligne.get('article_id')
            quantite = ligne.get('quantite', 0)
            
            try:
                article = Article.objects.get(
                    id=article_id,
                    boutique=boutique,
                    est_actif=True
                )
                if article.quantite_stock < quantite:
                    articles_insuffisants.append({
                        'id': article.id,
                        'nom': article.nom,
                        'stock_disponible': article.quantite_stock,
                        'quantite_demandee': quantite
                    })
            except Article.DoesNotExist:
                return Response({
                    'error': f'Article avec ID {article_id} non trouvé dans cette boutique'
                }, status=status.HTTP_404_NOT_FOUND)
        
        if articles_insuffisants:
            return Response({
                'error': 'Stock insuffisant',
                'details': articles_insuffisants
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Traitement de la vente avec transaction atomique
        try:
            with transaction.atomic():
                # Créer la vente
                vente = Vente.objects.create(
                    numero_facture=request.data.get('numero_facture'),
                    montant_total=request.data.get('montant_total'),
                    mode_paiement=request.data.get('mode_paiement'),
                    paye=True,
                    boutique=boutique,
                    terminal_maui=terminal,
                    adresse_ip_client=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                    version_app_maui=request.data.get('version_app', ''),
                    nom_client=request.data.get('nom_client', ''),
                    telephone_client=request.data.get('telephone_client', '')
                )
                
                # Créer les lignes de vente et mettre à jour les stocks
                for ligne_data in lignes:
                    article = Article.objects.get(
                        id=ligne_data['article_id'],
                        boutique=boutique
                    )
                    
                    # Créer la ligne de vente
                    ligne_vente = LigneVente.objects.create(
                        vente=vente,
                        article=article,
                        quantite=ligne_data['quantite'],
                        prix_unitaire=ligne_data['prix_unitaire']
                    )
                    
                    # Mettre à jour le stock
                    from .utils import update_stock_by_article_id
                    update_stock_by_article_id(
                        article_id=article.id,
                        quantite=ligne_data['quantite'],
                        type_mouvement='VENTE',
                        reference=vente.numero_facture,
                        utilisateur=terminal.nom_utilisateur or 'Terminal MAUI',
                        details={
                            'terminal': terminal.nom_terminal,
                            'boutique': boutique.nom,
                            'prix_unitaire': ligne_data['prix_unitaire']
                        },
                        is_sale=True
                    )
                
                logger.info(f"Vente {vente.numero_facture} finalisée - Boutique: {boutique.nom} - Terminal: {terminal.nom_terminal}")
                
                return Response({
                    'success': True,
                    'message': f'Vente finalisée avec succès dans {boutique.nom}',
                    'vente': {
                        'id': vente.id,
                        'numero_facture': vente.numero_facture,
                        'montant_total': vente.montant_total,
                        'boutique': boutique.nom,
                        'terminal': terminal.nom_terminal
                    }
                }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Erreur lors de la finalisation de vente: {str(e)}")
            return Response({
                'success': False,
                'error': f'Erreur lors de la finalisation: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ===== ENDPOINTS DE COMPATIBILITÉ =====

# Maintenir la compatibilité avec l'ancienne API
ArticleViewSet = ArticleBoutiqueViewSet
VenteViewSet = VenteBoutiqueViewSet
