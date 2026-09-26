import logging
from urllib.parse import quote, urlparse

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ScalingoBackupError(Exception):
    pass


def _configuration():
    api_url = getattr(settings, 'SCALINGO_API_URL', '').rstrip('/')
    app = getattr(settings, 'SCALINGO_APP', '')
    api_token = getattr(settings, 'SCALINGO_API_TOKEN', '')
    database_api_url = getattr(settings, 'SCALINGO_DB_API_URL', '').rstrip('/')
    database_id = getattr(settings, 'SCALINGO_DB_ADDON_ID', '')

    values = {
        'SCALINGO_API_URL': api_url,
        'SCALINGO_APP': app,
        'SCALINGO_API_TOKEN': api_token,
        'SCALINGO_DB_API_URL': database_api_url,
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ScalingoBackupError(
            'Configuration Scalingo incomplète : ' + ', '.join(missing) + ' manquante(s).'
        )

    return {
        'api_url': api_url,
        'app': app,
        'api_token': api_token,
        'database_api_url': database_api_url,
        'database_id': database_id,
    }


def is_configured():
    try:
        _configuration()
    except ScalingoBackupError:
        return False
    return True


def _exchange_api_token(configuration):
    auth_api_url = getattr(settings, 'SCALINGO_AUTH_API_URL', 'https://auth.scalingo.com').rstrip('/')
    if not auth_api_url:
        auth_api_url = 'https://auth.scalingo.com'

    url = f'{auth_api_url}/v1/tokens/exchange'
    try:
        response = requests.post(
            url,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            auth=('', configuration['api_token']),
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.warning('Scalingo: échange du jeton impossible: %s', type(exc).__name__)
        raise ScalingoBackupError('Le service d’authentification Scalingo est momentanément indisponible.') from exc

    if response.status_code in (401, 403):
        raise ScalingoBackupError('Le jeton API Scalingo est invalide ou expiré.')
    if response.status_code == 429:
        raise ScalingoBackupError('Scalingo a trop de requêtes en attente. Réessayez dans quelques instants.')
    if response.status_code >= 400:
        logger.warning('Scalingo: échange du jeton refusé avec le statut %s', response.status_code)
        raise ScalingoBackupError('Scalingo a refusé le jeton API fourni.')

    try:
        payload = response.json()
        bearer_token = payload.get('token')
    except (TypeError, ValueError) as exc:
        raise ScalingoBackupError('Réponse Scalingo invalide lors de l’authentification.') from exc

    if not bearer_token:
        raise ScalingoBackupError('Scalingo n’a pas renvoyé de jeton Bearer.')

    return bearer_token


def _is_postgresql_addon(addon):
    provider = addon.get('addon_provider') or {}
    plan = addon.get('plan') or {}
    provider_label = ' '.join(str(provider.get(key) or '') for key in ('id', 'name'))
    plan_name = str(plan.get('name') or '')

    return 'postgresql' in provider_label.lower() or plan_name.lower().startswith('postgresql')


def _find_postgresql_addon_id(configuration, bearer_token):
    app = quote(configuration['app'], safe='')
    url = f'{configuration["api_url"]}/v1/apps/{app}/addons'
    try:
        response = requests.get(
            url,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {bearer_token}',
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.warning('Scalingo: liste des addons impossible: %s', type(exc).__name__)
        raise ScalingoBackupError('Le service Scalingo est momentanément indisponible.') from exc

    if response.status_code in (401, 403):
        raise ScalingoBackupError('Accès Scalingo refusé. Vérifiez le jeton API.')
    if response.status_code == 404:
        raise ScalingoBackupError('L’application Scalingo est introuvable.')
    if response.status_code >= 400:
        logger.warning('Scalingo: liste des addons refusée avec le statut %s', response.status_code)
        raise ScalingoBackupError('Scalingo n’a pas pu lister les addons de l’application.')

    try:
        payload = response.json()
    except (TypeError, ValueError) as exc:
        raise ScalingoBackupError('Réponse Scalingo invalide pour la liste des addons.') from exc

    addons = payload.get('addons') or []
    postgresql_addons = [
        addon for addon in addons
        if addon.get('id') and not addon.get('deprovisioned_at') and _is_postgresql_addon(addon)
    ]
    if not postgresql_addons:
        raise ScalingoBackupError('Scalingo n’a trouvé aucun addon PostgreSQL sur cette application.')

    configured_id = configuration.get('database_id')
    if configured_id:
        for addon in postgresql_addons:
            if configured_id in (addon.get('id'), addon.get('resource_id')):
                return addon['id']

    if len(postgresql_addons) == 1:
        return postgresql_addons[0]['id']

    raise ScalingoBackupError(
        'Plusieurs addons PostgreSQL sont présents. Définissez SCALINGO_DB_ADDON_ID avec le bon identifiant.'
    )


def _get_database_context(configuration):
    bearer_token = _exchange_api_token(configuration)
    database_id = _find_postgresql_addon_id(configuration, bearer_token)
    addon_id = quote(database_id, safe='')
    url = f"{configuration['api_url']}/v1/apps/{quote(configuration['app'], safe='')}/addons/{addon_id}/token"
    try:
        response = requests.post(
            url,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {bearer_token}',
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.warning('Scalingo: impossible de demander le jeton de la base: %s', type(exc).__name__)
        raise ScalingoBackupError('Le service Scalingo est momentanément indisponible.') from exc

    if response.status_code in (401, 403):
        raise ScalingoBackupError('Accès Scalingo refusé. Vérifiez le jeton API et l’identifiant de l’addon.')
    if response.status_code == 404:
        raise ScalingoBackupError('L’identifiant de l’addon PostgreSQL est introuvable.')
    if response.status_code == 429:
        raise ScalingoBackupError('Scalingo a trop de requêtes en attente. Réessayez dans quelques instants.')
    if response.status_code >= 400:
        logger.warning('Scalingo: jeton addon refusé avec le statut %s', response.status_code)
        raise ScalingoBackupError('Scalingo n’a pas pu autoriser l’accès à la base de données.')

    try:
        payload = response.json()
        token = payload.get('addon', {}).get('token') or payload.get('token')
    except (TypeError, ValueError) as exc:
        raise ScalingoBackupError('Réponse Scalingo invalide lors de l’authentification.') from exc

    if not token:
        raise ScalingoBackupError('Scalingo n’a pas renvoyé de jeton de base de données.')

    return database_id, token


def _database_request(configuration, database_token, path):
    url = f"{configuration['database_api_url']}{path}"
    try:
        response = requests.get(
            url,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {database_token}',
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.warning('Scalingo: appel base de données impossible: %s', type(exc).__name__)
        raise ScalingoBackupError('Le service de sauvegarde Scalingo est momentanément indisponible.') from exc

    if response.status_code >= 400:
        logger.warning('Scalingo: appel sauvegardes refusé avec le statut %s', response.status_code)
        raise ScalingoBackupError('Scalingo n’a pas pu fournir la sauvegarde demandée.')

    try:
        return response.json()
    except (TypeError, ValueError) as exc:
        raise ScalingoBackupError('Réponse Scalingo invalide pour les sauvegardes.') from exc


def _validate_download_url(url, configuration):
    parsed = urlparse(url)
    expected_host = urlparse(configuration['database_api_url']).hostname
    if parsed.scheme != 'https' or parsed.hostname != expected_host or not parsed.netloc:
        raise ScalingoBackupError('Scalingo a renvoyé une URL de téléchargement non sécurisée.')

    return url


def latest_backup_download_url():
    configuration = _configuration()
    database_id, database_token = _get_database_context(configuration)
    database_id = quote(database_id, safe='')
    payload = _database_request(
        configuration,
        database_token,
        f'/api/databases/{database_id}/backups',
    )

    backups = payload.get('database_backups') or payload.get('backups') or []
    completed_backups = [
        backup for backup in backups
        if backup.get('status') == 'done' and backup.get('id')
    ]
    if not completed_backups:
        raise ScalingoBackupError('Aucune sauvegarde terminée n’est disponible sur Scalingo.')

    latest_backup = max(
        completed_backups,
        key=lambda backup: backup.get('created_at') or '',
    )
    archive_payload = _database_request(
        configuration,
        database_token,
        f'/api/databases/{database_id}/backups/{quote(latest_backup["id"], safe="")}/archive',
    )
    download_url = archive_payload.get('download_url')
    if not download_url:
        raise ScalingoBackupError('Scalingo n’a pas renvoyé de lien de téléchargement.')

    return _validate_download_url(download_url, configuration)
