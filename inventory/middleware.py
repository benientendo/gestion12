"""
Middleware pour gérer correctement les fuseaux horaires entre MAUI et Django
"""

from django.utils import timezone
from django.utils.dateparse import parse_datetime
import json
import re


class TimezoneMiddleware:
    """
    Middleware pour normaliser les dates dans les requêtes API
    Force l'interprétation des dates naïves dans le timezone de Django
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Traitement des dates dans les données de requête
        if hasattr(request, 'body') and request.body:
            try:
                body_str = request.body.decode('utf-8')
                if body_str and body_str.strip():
                    # Tenter de parser et normaliser les dates
                    normalized_body = self._normalize_dates_in_json(body_str)
                    if normalized_body != body_str:
                        # Remplacer le body avec les dates normalisées
                        request._body = normalized_body.encode('utf-8')
                        # Réinitialiser les données parsées
                        if hasattr(request, 'POST'):
                            request.POST = {}
                        if hasattr(request, 'data'):
                            request.data = {}
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass  # Ignorer les erreurs de parsing
                
        response = self.get_response(request)
        return response
    
    def _normalize_dates_in_json(self, json_str):
        """Normalise les dates dans une chaîne JSON"""
        # Pattern pour trouver les dates ISO 8601
        date_pattern = r'"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)"'
        
        def replace_date(match):
            date_str = match.group(1)
            try:
                parsed_date = parse_datetime(date_str)
                if parsed_date and timezone.is_naive(parsed_date):
                    # Rendre la date aware avec le timezone de Django
                    aware_date = timezone.make_aware(parsed_date)
                    # Retourner en format ISO mais avec le bon timezone
                    return f'"{aware_date.isoformat()}"'
            except:
                pass
            return match.group(0)
        
        return re.sub(date_pattern, replace_date, json_str)


class ForceTimezoneMiddleware:
    """
    Middleware plus simple qui force le timezone pour toutes les opérations
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Activer le timezone de Django pour cette requête
        timezone.activate(timezone.get_current_timezone())
        response = self.get_response(request)
        return response
