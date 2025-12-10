"""
Vue de test pour vérifier la gestion des timezone
"""

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json


@csrf_exempt
@require_http_methods(["GET", "POST"])
def test_timezone(request):
    """
    Endpoint de test pour vérifier la gestion des timezone
    """
    
    if request.method == 'GET':
        # Retourner les informations de timezone actuelles
        return JsonResponse({
            'timezone_actif': str(timezone.get_current_timezone()),
            'heure_serveur': timezone.now().isoformat(),
            'heure_locale': timezone.localtime(timezone.now()).isoformat(),
            'use_tz': timezone.use_tz,
        })
    
    elif request.method == 'POST':
        # Analyser les dates reçues et montrer comment elles sont interprétées
        try:
            data = json.loads(request.body)
            
            result = {
                'timezone_actif': str(timezone.get_current_timezone()),
                'donnees_recues': data,
                'dates_interpretees': {}
            }
            
            # Analyser chaque champ de date
            for key, value in data.items():
                if 'date' in key.lower() and isinstance(value, str):
                    from django.utils.dateparse import parse_datetime
                    parsed = parse_datetime(value)
                    if parsed:
                        if timezone.is_naive(parsed):
                            # Date naïve - on la rend aware
                            aware = timezone.make_aware(parsed)
                            result['dates_interpretees'][key] = {
                                'original': value,
                                'parse': parsed.isoformat(),
                                'aware': aware.isoformat(),
                                'locale': timezone.localtime(aware).isoformat(),
                                'type': 'naive_converted'
                            }
                        else:
                            # Date déjà aware
                            result['dates_interpretees'][key] = {
                                'original': value,
                                'aware': parsed.isoformat(),
                                'locale': timezone.localtime(parsed).isoformat(),
                                'type': 'already_aware'
                            }
            
            return JsonResponse(result)
            
        except Exception as e:
            return JsonResponse({
                'error': str(e),
                'timezone_actif': str(timezone.get_current_timezone()),
                'heure_serveur': timezone.now().isoformat()
            }, status=400)
