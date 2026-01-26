from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Q, F, Count, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json
import logging

from .models import Commercant, Boutique, Vente, Article, MouvementStock, RapportCaisse
from .models_bilan import BilanGeneral, IndicateurPerformance

logger = logging.getLogger(__name__)

# ===== SÉRIALISEURS POUR LES BILANS =====

class BilanGeneralSerializer(serializers.ModelSerializer):
    """Sérialiseur pour le modèle BilanGeneral"""
    boutique_nom = serializers.CharField(source='boutique.nom', read_only=True)
    commercant_nom = serializers.CharField(source='commercant.nom_entreprise', read_only=True)
    statut_display = serializers.CharField(source='get_statut_display', read_only=True)
    periode_display = serializers.CharField(source='get_periode_display', read_only=True)
    
    class Meta:
        model = BilanGeneral
        fields = [
            'id', 'titre', 'description', 'periode', 'periode_display',
            'date_debut', 'date_fin', 'date_generation',
            'commercant', 'commercant_nom', 'boutique', 'boutique_nom',
            'statut', 'statut_display', 'valide_par', 'date_validation',
            'chiffre_affaires_total', 'chiffre_affaires_total_usd',
            'cout_achats_marchandises', 'marge_brute', 'taux_marge_brute',
            'depenses_operationnelles', 'depenses_personnel', 'depenses_loyer',
            'depenses_services', 'autres_depenses', 'resultat_operationnel',
            'resultat_net', 'nombre_ventes', 'panier_moyen', 'taux_conversion',
            'valeur_stock_initiale', 'valeur_stock_finale', 'variation_stock',
            'donnees_detaillees', 'created_at', 'updated_at'
        ]
        read_only_fields = ['date_generation', 'created_at', 'updated_at']

class BilanCreateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la création de bilans"""
    
    class Meta:
        model = BilanGeneral
        fields = [
            'titre', 'description', 'periode', 'date_debut', 'date_fin',
            'commercant', 'boutique'
        ]
    
    def validate(self, data):
        """Validation des données du bilan"""
        date_debut = data.get('date_debut')
        date_fin = data.get('date_fin')
        
        if date_debut and date_fin and date_debut >= date_fin:
            raise serializers.ValidationError("La date de début doit être antérieure à la date de fin.")
        
        return data

class IndicateurPerformanceSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les indicateurs de performance"""
    categorie_display = serializers.CharField(source='get_categorie_display', read_only=True)
    periodicite_display = serializers.CharField(source='get_periodicite_display', read_only=True)
    en_alerte = serializers.SerializerMethodField()
    
    class Meta:
        model = IndicateurPerformance
        fields = [
            'id', 'nom', 'description', 'categorie', 'categorie_display',
            'periodicite', 'periodicite_display', 'formule',
            'valeur_actuelle', 'valeur_precedente', 'variation_pourcentage',
            'objectif', 'seuil_alerte', 'en_alerte',
            'boutique', 'commercant', 'date_derniere_maj', 'created_at'
        ]
        read_only_fields = ['date_derniere_maj', 'created_at']
    
    def get_en_alerte(self, obj):
        return obj.est_en_alerte()

# ===== VUES API POUR LES BILANS =====

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def bilans_api(request):
    """API pour lister et créer des bilans"""
    if request.method == 'GET':
        # Récupérer le commerçant de l'utilisateur
        try:
            commercant = request.user.profil_commercant
        except Commercant.DoesNotExist:
            return Response(
                {'error': 'Utilisateur non autorisé'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Filtres
        periode = request.GET.get('periode')
        statut = request.GET.get('statut')
        boutique_id = request.GET.get('boutique')
        date_debut = request.GET.get('date_debut')
        date_fin = request.GET.get('date_fin')
        
        bilans_qs = BilanGeneral.objects.filter(
            Q(commercant=commercant) | Q(boutique__commercant=commercant)
        )
        
        if periode:
            bilans_qs = bilans_qs.filter(periode=periode)
        if statut:
            bilans_qs = bilans_qs.filter(statut=statut)
        if boutique_id:
            bilans_qs = bilans_qs.filter(boutique_id=boutique_id)
        if date_debut:
            bilans_qs = bilans_qs.filter(date_generation__gte=date_debut)
        if date_fin:
            bilans_qs = bilans_qs.filter(date_generation__lte=date_fin)
        
        bilans = bilans_qs.order_by('-date_generation')
        serializer = BilanGeneralSerializer(bilans, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': bilans.count()
        })
    
    elif request.method == 'POST':
        # Création d'un nouveau bilan
        try:
            commercant = request.user.profil_commercant
        except Commercant.DoesNotExist:
            return Response(
                {'error': 'Utilisateur non autorisé'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = BilanCreateSerializer(data=request.data)
        if serializer.is_valid():
            try:
                bilan = serializer.save()
                
                # Générer les données du bilan
                if bilan.generer_donnees():
                    response_serializer = BilanGeneralSerializer(bilan)
                    return Response({
                        'success': True,
                        'message': 'Bilan créé avec succès',
                        'data': response_serializer.data
                    }, status=status.HTTP_201_CREATED)
                else:
                    bilan.delete()
                    return Response({
                        'success': False,
                        'error': 'Erreur lors de la génération des données du bilan'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except Exception as e:
                logger.error(f"Erreur lors de la création du bilan: {str(e)}")
                return Response({
                    'success': False,
                    'error': f'Erreur lors de la création: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'error': 'Données invalides',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def bilan_detail_api(request, bilan_id):
    """API pour les détails, modification et suppression d'un bilan"""
    try:
        commercant = request.user.profil_commercant
    except Commercant.DoesNotExist:
        return Response(
            {'error': 'Utilisateur non autorisé'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        bilan = BilanGeneral.objects.get(id=bilan_id)
    except BilanGeneral.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Bilan non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Vérifier les autorisations
    if bilan.commercant != commercant and (not bilan.boutique or bilan.boutique.commercant != commercant):
        return Response(
            {'error': 'Accès non autorisé à ce bilan'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        serializer = BilanGeneralSerializer(bilan)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    elif request.method == 'PUT':
        # Mise à jour du bilan (uniquement titre et description si en brouillon)
        if bilan.statut != 'BROUILLON':
            return Response({
                'success': False,
                'error': 'Seuls les bilans en brouillon peuvent être modifiés'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = BilanCreateSerializer(bilan, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            response_serializer = BilanGeneralSerializer(bilan)
            return Response({
                'success': True,
                'message': 'Bilan mis à jour avec succès',
                'data': response_serializer.data
            })
        
        return Response({
            'success': False,
            'error': 'Données invalides',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        # Suppression du bilan (uniquement si en brouillon)
        if bilan.statut != 'BROUILLON':
            return Response({
                'success': False,
                'error': 'Seuls les bilans en brouillon peuvent être supprimés'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        bilan.delete()
        return Response({
            'success': True,
            'message': 'Bilan supprimé avec succès'
        })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def valider_bilan_api(request, bilan_id):
    """API pour valider un bilan"""
    try:
        commercant = request.user.profil_commercant
    except Commercant.DoesNotExist:
        return Response(
            {'error': 'Utilisateur non autorisé'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        bilan = BilanGeneral.objects.get(id=bilan_id)
    except BilanGeneral.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Bilan non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Vérifier les autorisations
    if bilan.commercant != commercant and (not bilan.boutique or bilan.boutique.commercant != commercant):
        return Response(
            {'error': 'Accès non autorisé à ce bilan'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    if bilan.statut != 'BROUILLON':
        return Response({
            'success': False,
            'error': 'Ce bilan ne peut plus être validé'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        bilan.valider(request.user.username)
        serializer = BilanGeneralSerializer(bilan)
        return Response({
            'success': True,
            'message': 'Bilan validé avec succès',
            'data': serializer.data
        })
    except Exception as e:
        logger.error(f"Erreur lors de la validation du bilan: {str(e)}")
        return Response({
            'success': False,
            'error': f'Erreur lors de la validation: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ===== VUES API POUR LES INDICATEURS =====

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def indicateurs_api(request):
    """API pour lister et créer des indicateurs de performance"""
    try:
        commercant = request.user.profil_commercant
    except Commercant.DoesNotExist:
        return Response(
            {'error': 'Utilisateur non autorisé'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        # Filtres
        categorie = request.GET.get('categorie')
        boutique_id = request.GET.get('boutique')
        
        indicateurs_qs = IndicateurPerformance.objects.filter(
            Q(commercant=commercant) | Q(boutique__commercant=commercant)
        )
        
        if categorie:
            indicateurs_qs = indicateurs_qs.filter(categorie=categorie)
        if boutique_id:
            indicateurs_qs = indicateurs_qs.filter(boutique_id=boutique_id)
        
        indicateurs = indicateurs_qs.order_by('categorie', 'nom')
        serializer = IndicateurPerformanceSerializer(indicateurs, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'count': indicateurs.count()
        })
    
    elif request.method == 'POST':
        # Création d'un nouvel indicateur
        serializer = IndicateurPerformanceSerializer(data=request.data)
        if serializer.is_valid():
            try:
                indicateur = serializer.save(commercant=commercant)
                response_serializer = IndicateurPerformanceSerializer(indicateur)
                return Response({
                    'success': True,
                    'message': 'Indicateur créé avec succès',
                    'data': response_serializer.data
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Erreur lors de la création de l'indicateur: {str(e)}")
                return Response({
                    'success': False,
                    'error': f'Erreur lors de la création: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'success': False,
            'error': 'Données invalides',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rafraichir_indicateurs_api(request):
    """API pour rafraîchir tous les indicateurs"""
    try:
        commercant = request.user.profil_commercant
        boutiques = commercant.boutiques.filter(est_active=True)
    except Commercant.DoesNotExist:
        return Response(
            {'error': 'Utilisateur non autorisé'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        indicateurs = IndicateurPerformance.objects.filter(
            Q(commercant=commercant) | Q(boutique__in=boutiques)
        )
        
        resultats = []
        for indicateur in indicateurs:
            # Mettre à jour l'indicateur
            from .views_bilan import _mettre_a_jour_indicateur
            _mettre_a_jour_indicateur(indicateur, boutiques)
            indicateur.calculer_variation()
            
            serializer = IndicateurPerformanceSerializer(indicateur)
            resultats.append(serializer.data)
        
        return Response({
            'success': True,
            'message': 'Indicateurs rafraîchis avec succès',
            'data': resultats
        })
        
    except Exception as e:
        logger.error(f"Erreur lors du rafraîchissement des indicateurs: {str(e)}")
        return Response({
            'success': False,
            'error': f'Erreur lors du rafraîchissement: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ===== VUES API POUR LES STATISTIQUES EN TEMPS RÉEL =====

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def statistiques_temps_reel_api(request):
    """API pour les statistiques en temps réel"""
    try:
        commercant = request.user.profil_commercant
        boutiques = commercant.boutiques.filter(est_active=True)
    except Commercant.DoesNotExist:
        return Response(
            {'error': 'Utilisateur non autorisé'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        from .views_bilan import _calculer_indicateurs_temps_reel
        indicateurs = _calculer_indicateurs_temps_reel(commercant, boutiques)
        
        return Response({
            'success': True,
            'data': indicateurs
        })
        
    except Exception as e:
        logger.error(f"Erreur lors du calcul des statistiques: {str(e)}")
        return Response({
            'success': False,
            'error': f'Erreur lors du calcul: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ventes_par_jour_api(request):
    """API pour les ventes par jour (pour graphiques)"""
    try:
        commercant = request.user.profil_commercant
        boutiques = commercant.boutiques.filter(est_active=True)
    except Commercant.DoesNotExist:
        return Response(
            {'error': 'Utilisateur non autorisé'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Paramètres
    jours = int(request.GET.get('jours', 30))  # Par défaut 30 jours
    
    try:
        from django.db.models.functions import TruncDate
        
        date_debut = timezone.now() - timedelta(days=jours)
        
        ventes_par_jour = Vente.objects.filter(
            boutique__in=boutiques,
            date_vente__gte=date_debut,
            est_annulee=False
        ).annotate(
            jour=TruncDate('date_vente')
        ).values('jour').annotate(
            nb_ventes=Count('id'),
            ca_total=Sum('montant_total'),
            ca_usd_total=Sum('montant_total_usd')
        ).order_by('jour')
        
        resultats = [
            {
                'date': v['jour'].strftime('%Y-%m-%d'),
                'nb_ventes': v['nb_ventes'],
                'ca_cdf': float(v['ca_total'] or 0),
                'ca_usd': float(v['ca_usd_total'] or 0)
            }
            for v in ventes_par_jour
        ]
        
        return Response({
            'success': True,
            'data': resultats
        })
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des ventes par jour: {str(e)}")
        return Response({
            'success': False,
            'error': f'Erreur: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def top_articles_api(request):
    """API pour les articles les plus vendus"""
    try:
        commercant = request.user.profil_commercant
        boutiques = commercant.boutiques.filter(est_active=True)
    except Commercant.DoesNotExist:
        return Response(
            {'error': 'Utilisateur non autorisé'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Paramètres
    limite = int(request.GET.get('limite', 10))  # Par défaut top 10
    jours = int(request.GET.get('jours', 30))  # Par défaut 30 derniers jours
    
    try:
        date_debut = timezone.now() - timedelta(days=jours)
        
        from .models import LigneVente
        
        top_articles = LigneVente.objects.filter(
            vente__boutique__in=boutiques,
            vente__date_vente__gte=date_debut,
            vente__est_annulee=False
        ).values(
            'article__nom', 'article__code', 'article__id'
        ).annotate(
            quantite_totale=Sum('quantite'),
            total_vente=Sum(F('quantite') * F('prix_unitaire'))
        ).order_by('-quantite_totale')[:limite]
        
        resultats = [
            {
                'id': a['article__id'],
                'nom': a['article__nom'],
                'code': a['article__code'],
                'quantite': a['quantite_totale'],
                'total': float(a['total_vente'])
            }
            for a in top_articles
        ]
        
        return Response({
            'success': True,
            'data': resultats
        })
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des top articles: {str(e)}")
        return Response({
            'success': False,
            'error': f'Erreur: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def performance_categories_api(request):
    """API pour la performance par catégorie"""
    try:
        commercant = request.user.profil_commercant
        boutiques = commercant.boutiques.filter(est_active=True)
    except Commercant.DoesNotExist:
        return Response(
            {'error': 'Utilisateur non autorisé'}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Paramètres
    jours = int(request.GET.get('jours', 30))  # Par défaut 30 derniers jours
    
    try:
        date_debut = timezone.now() - timedelta(days=jours)
        
        from .models import LigneVente
        
        categories_perf = LigneVente.objects.filter(
            vente__boutique__in=boutiques,
            vente__date_vente__gte=date_debut,
            vente__est_annulee=False
        ).values(
            'article__categorie__nom'
        ).annotate(
            quantite_totale=Sum('quantite'),
            total_vente=Sum(F('quantite') * F('prix_unitaire'))
        ).order_by('-total_vente')
        
        resultats = [
            {
                'categorie': c['article__categorie__nom'] or 'Non catégorisé',
                'quantite': c['quantite_totale'],
                'total': float(c['total_vente'])
            }
            for c in categories_perf
        ]
        
        return Response({
            'success': True,
            'data': resultats
        })
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la performance par catégorie: {str(e)}")
        return Response({
            'success': False,
            'error': f'Erreur: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
