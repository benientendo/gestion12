# -*- coding: utf-8 -*-
"""
Endpoint de disponibilité du serveur : /healthz/

Réponse publique (sans connexion) destinée au monitoring :
  - 200 {"statut": "ok", "base": true, "cache": true}  → tout va bien ;
  - 503 {"statut": "erreur", "base": false, ...}       → PostgreSQL ne
    répond plus (le cache reste informatif : il ne fait pas tomber la
    page, mais son état est affiché pour diagnostiquer un addon Redis
    gelé).

Usage : à brancher comme « Health check path » dans le dashboard Scalingo
(Application → Settings → Health check), ou en alerte de uptime.
"""
import logging

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def healthz(request):
    """Vérifie brièvement la base et le cache, puis répond en JSON."""
    etat = {'statut': 'ok', 'base': False, 'cache': False}
    code = 200

    # 1) PostgreSQL : indispensable, son échec passe l'endpoint en 503
    try:
        with connection.cursor() as curseur:
            curseur.execute('SELECT 1')
            curseur.fetchone()
        etat['base'] = True
    except Exception as exc:
        logger.error('healthz: base de données indisponible: %s', exc)
        etat['statut'] = 'erreur'
        code = 503

    # 2) Cache/Redis : informatif seulement (un cache gelé ne bloque pas
    #    la requête grâce aux temps d'attente, mais il faut le voir)
    try:
        cache.set('healthz', '1', 10)
        etat['cache'] = cache.get('healthz') == '1'
    except Exception as exc:
        logger.warning('healthz: cache indisponible: %s', exc)
        etat['cache'] = False

    return JsonResponse(etat, status=code)
