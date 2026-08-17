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


class TerminalAuthMiddleware:
    """
    🔐 Sécurité: exige un terminal enregistré et actif pour les endpoints
    sensibles de l'API v2 simple (/api/v2/simple/).

    Le terminal s'identifie via le header 'X-Device-Serial'. Un terminal est
    valide s'il existe un Client actif (est_actif=True) avec ce numéro de série.

    Les endpoints d'enregistrement/diagnostic restent anonymes:
      - /api/v2/simple/status/
      - /api/v2/simple/pos/status/
      - /api/v2/simple/boutiques/
      - /api/v2/simple/terminal/<serial>/
      - /api/v2/simple/articles/terminal/<serial>/

    Tout autre endpoint sous /api/v2/simple/ (ventes, stock, articles, annulations…)
    renvoie 401 si le header est absent ou le terminal inconnu/inactif.
    """

    # Chemins anonymes (enregistrement, diagnostic) — prefixés par /api/v2/simple/
    ANONYME_PREFIXES = (
        '/api/v2/simple/status/',
        '/api/v2/simple/pos/status/',
        '/api/v2/simple/boutiques/',
        '/api/v2/simple/terminal/',
        '/api/v2/simple/articles/terminal/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Ne s'applique qu'à l'API v2 simple
        if not path.startswith('/api/v2/simple/'):
            return self.get_response(request)

        # Endpoints anonymes (enregistrement/diagnostic)
        if any(path.startswith(prefix) for prefix in self.ANONYME_PREFIXES):
            return self.get_response(request)

        numero_serie = (
            request.headers.get('X-Device-Serial') or
            request.headers.get('Device-Serial') or
            request.headers.get('Serial-Number') or
            request.META.get('HTTP_X_DEVICE_SERIAL') or
            request.META.get('HTTP_DEVICE_SERIAL')
        )

        if not numero_serie:
            from django.http import JsonResponse
            return JsonResponse(
                {
                    'error': 'Terminal requis',
                    'code': 'MISSING_SERIAL',
                    'header_required': 'X-Device-Serial'
                },
                status=401
            )

        from inventory.models import Client
        terminal_valide = Client.objects.filter(
            numero_serie=numero_serie,
            est_actif=True
        ).exists()

        if not terminal_valide:
            from django.http import JsonResponse
            return JsonResponse(
                {
                    'error': 'Terminal non enregistré ou inactif',
                    'code': 'TERMINAL_UNAUTHORIZED'
                },
                status=401
            )

        # Attacher le terminal à la requête pour les vues (optionnel)
        request.terminal_serial = numero_serie

        return self.get_response(request)
