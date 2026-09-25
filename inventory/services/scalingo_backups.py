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
        'SCALINGO_DB_ADDON_ID': database_id,
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


def _get_database_token(configuration):
    app = quote(configuration['app'], safe='')
    database_id = quote(configuration['database_id'], safe='')
    url = f"{configuration['api_url']}/v1/apps/{app}/addons/{database_id}/token"
    try:
        response = requests.post(
            url,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f"Bearer {configuration['api_token']}",
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.warning('Scalingo: impossible de demander le jeton de la base: %s', type(exc).__name__)
        raise ScalingoBackupError('Le service Scalingo est momentanément indisponible.') from exc

    if response.status_code >= 400:
        logger.warning('Scalingo: échange du jeton refusé avec le statut %s', response.status_code)
        raise ScalingoBackupError('Le jeton API Scalingo est invalide ou expiré.')

    try:
        payload = response.json()
        token = payload.get('addon', {}).get('token') or payload.get('token')
    except (TypeError, ValueError) as exc:
        raise ScalingoBackupError('Réponse Scalingo invalide lors de l’authentification.') from exc

    if not token:
        raise ScalingoBackupError('Scalingo n’a pas renvoyé de jeton de base de données.')

    return token


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
    database_token = _get_database_token(configuration)
    database_id = quote(configuration['database_id'], safe='')
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
