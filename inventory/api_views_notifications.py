from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
import logging

from .models import NotificationStock, Client
from .serializers import NotificationStockSerializer, NotificationStockDetailSerializer

logger = logging.getLogger(__name__)


class NotificationStockViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour gérer les notifications de stock des clients MAUI.
    
    Endpoints:
    - GET /api/v2/notifications/ : Liste des notifications du client
    - GET /api/v2/notifications/unread/ : Liste des notifications non lues
    - GET /api/v2/notifications/{id}/ : Détail d'une notification
    - POST /api/v2/notifications/{id}/mark_as_read/ : Marquer comme lue
    - POST /api/v2/notifications/mark_all_as_read/ : Marquer toutes comme lues
    """
    
    serializer_class = NotificationStockSerializer
    
    def get_queryset(self):
        """
        Retourne les notifications du client authentifié.
        Filtre selon le terminal MAUI (numero_serie dans les headers).
        """
        numero_serie = self.request.headers.get('X-Device-Serial')
        
        if not numero_serie:
            logger.warning("Tentative d'accès aux notifications sans X-Device-Serial")
            return NotificationStock.objects.none()
        
        try:
            client = Client.objects.get(numero_serie=numero_serie, est_actif=True)
        except Client.DoesNotExist:
            logger.warning(f"Client avec numéro de série {numero_serie} introuvable")
            return NotificationStock.objects.none()
        
        queryset = NotificationStock.objects.filter(
            client=client
        ).select_related(
            'client', 'boutique', 'article', 'mouvement_stock'
        ).order_by('-date_creation')
        
        return queryset
    
    def get_serializer_class(self):
        """Utilise le serializer détaillé pour retrieve."""
        if self.action == 'retrieve':
            return NotificationStockDetailSerializer
        return NotificationStockSerializer
    
    def list(self, request, *args, **kwargs):
        """Liste toutes les notifications du client avec pagination."""
        queryset = self.get_queryset()
        
        lue_param = request.query_params.get('lue')
        if lue_param is not None:
            if lue_param.lower() in ['true', '1', 'yes']:
                queryset = queryset.filter(lue=True)
            elif lue_param.lower() in ['false', '0', 'no']:
                queryset = queryset.filter(lue=False)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        
        non_lues = queryset.filter(lue=False).count()
        
        return Response({
            'count': queryset.count(),
            'non_lues': non_lues,
            'results': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Retourne uniquement les notifications non lues."""
        queryset = self.get_queryset().filter(lue=False)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'count': queryset.count(),
            'results': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def count_unread(self, request):
        """Retourne le nombre de notifications non lues."""
        queryset = self.get_queryset().filter(lue=False)
        return Response({
            'count': queryset.count()
        })
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Marque une notification comme lue."""
        notification = self.get_object()
        
        if notification.lue:
            return Response({
                'status': 'already_read',
                'message': 'Cette notification a déjà été marquée comme lue.'
            })
        
        notification.marquer_comme_lue()
        
        logger.info(
            f"Notification {notification.id} marquée comme lue par "
            f"{notification.client.nom_terminal}"
        )
        
        serializer = NotificationStockDetailSerializer(notification)
        return Response({
            'status': 'success',
            'message': 'Notification marquée comme lue.',
            'notification': serializer.data
        })
    
    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        """Marque toutes les notifications non lues comme lues."""
        queryset = self.get_queryset().filter(lue=False)
        count = queryset.count()
        
        if count == 0:
            return Response({
                'status': 'no_unread',
                'message': 'Aucune notification non lue.'
            })
        
        now = timezone.now()
        queryset.update(lue=True, date_lecture=now)
        
        numero_serie = request.headers.get('X-Device-Serial')
        logger.info(
            f"{count} notification(s) marquée(s) comme lue(s) par "
            f"le client {numero_serie}"
        )
        
        return Response({
            'status': 'success',
            'message': f'{count} notification(s) marquée(s) comme lue(s).',
            'count': count
        })
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Retourne les notifications récentes (dernières 24h)."""
        from datetime import timedelta
        
        depuis = timezone.now() - timedelta(hours=24)
        queryset = self.get_queryset().filter(date_creation__gte=depuis)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'count': queryset.count(),
            'non_lues': queryset.filter(lue=False).count(),
            'results': serializer.data
        })
    
    def retrieve(self, request, *args, **kwargs):
        """
        Récupère le détail d'une notification.
        Automatiquement marquée comme lue lors de la consultation.
        """
        instance = self.get_object()
        
        if not instance.lue:
            instance.marquer_comme_lue()
            logger.info(
                f"Notification {instance.id} automatiquement marquée comme lue "
                f"lors de la consultation par {instance.client.nom_terminal}"
            )
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
