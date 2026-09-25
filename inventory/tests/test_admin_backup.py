from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from inventory.services.scalingo_backups import ScalingoBackupError, is_configured, latest_backup_download_url


class ScalingoBackupServiceTests(SimpleTestCase):
    configuration = {
        'SCALINGO_API_URL': 'https://api.osc-fr1.scalingo.com',
        'SCALINGO_APP': 'gestionnumerique',
        'SCALINGO_API_TOKEN': 'api-token',
        'SCALINGO_DB_API_URL': 'https://db-api.osc-fr1.scalingo.com',
        'SCALINGO_DB_ADDON_ID': 'addon-id',
    }

    @override_settings(**configuration)
    def test_configuration(self):
        self.assertTrue(is_configured())

    @override_settings(**{**configuration, 'SCALINGO_API_TOKEN': ''})
    def test_configuration_incomplete(self):
        self.assertFalse(is_configured())

    @override_settings(**configuration)
    @patch('inventory.services.scalingo_backups.requests.get')
    @patch('inventory.services.scalingo_backups.requests.post')
    def test_latest_backup_download_url(self, post, get):
        token_response = Mock(status_code=200)
        token_response.json.return_value = {'addon': {'token': 'database-token'}}
        list_response = Mock(status_code=200)
        list_response.json.return_value = {
            'database_backups': [
                {'id': 'old', 'status': 'done', 'created_at': '2026-01-01T00:00:00Z'},
                {'id': 'pending', 'status': 'pending', 'created_at': '2026-01-02T00:00:00Z'},
                {'id': 'latest', 'status': 'done', 'created_at': '2026-01-03T00:00:00Z'},
            ],
        }
        archive_response = Mock(status_code=200)
        archive_response.json.return_value = {
            'download_url': 'https://db-api.osc-fr1.scalingo.com/api/backups/latest/download?token=secret',
        }
        post.return_value = token_response
        get.side_effect = [list_response, archive_response]

        self.assertEqual(
            latest_backup_download_url(),
            'https://db-api.osc-fr1.scalingo.com/api/backups/latest/download?token=secret',
        )
        self.assertEqual(get.call_count, 2)
        self.assertIn('/backups', get.call_args_list[0].args[0])
        self.assertIn('/backups/latest/archive', get.call_args_list[1].args[0])

    @override_settings(**configuration)
    @patch('inventory.services.scalingo_backups.requests.get')
    @patch('inventory.services.scalingo_backups.requests.post')
    def test_rejects_non_https_download_url(self, post, get):
        token_response = Mock(status_code=200)
        token_response.json.return_value = {'addon': {'token': 'database-token'}}
        list_response = Mock(status_code=200)
        list_response.json.return_value = {
            'database_backups': [
                {'id': 'latest', 'status': 'done', 'created_at': '2026-01-03T00:00:00Z'},
            ],
        }
        archive_response = Mock(status_code=200)
        archive_response.json.return_value = {
            'download_url': 'https://example.com/backup.sql',
        }
        post.return_value = token_response
        get.side_effect = [list_response, archive_response]

        with self.assertRaises(ScalingoBackupError):
            latest_backup_download_url()

    @override_settings(**configuration)
    @patch('inventory.services.scalingo_backups.requests.get')
    @patch('inventory.services.scalingo_backups.requests.post')
    def test_raises_when_no_completed_backup(self, post, get):
        token_response = Mock(status_code=200)
        token_response.json.return_value = {'addon': {'token': 'database-token'}}
        list_response = Mock(status_code=200)
        list_response.json.return_value = {
            'database_backups': [
                {'id': 'pending', 'status': 'pending', 'created_at': '2026-01-02T00:00:00Z'},
            ],
        }
        post.return_value = token_response
        get.return_value = list_response

        with self.assertRaises(ScalingoBackupError):
            latest_backup_download_url()


class ScalingoBackupAdminViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password',
        )
        self.url = reverse('inventory:admin_telecharger_sauvegarde_scalingo')

    def test_superuser_redirects_to_signed_download(self):
        self.client.force_login(self.user)
        with patch('inventory.admin_views.latest_backup_download_url', return_value='https://db-api.osc-fr1.scalingo.com/backup.sql'):
            response = self.client.get(self.url)

        self.assertRedirects(
            response,
            'https://db-api.osc-fr1.scalingo.com/backup.sql',
            fetch_redirect_response=False,
        )
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_error_returns_to_dashboard(self):
        self.client.force_login(self.user)
        with patch('inventory.admin_views.latest_backup_download_url', side_effect=ScalingoBackupError('Sauvegarde indisponible')):
            response = self.client.get(self.url)

        self.assertRedirects(response, reverse('inventory:admin_dashboard'))

    def test_non_superuser_is_denied(self):
        user = get_user_model().objects.create_user(username='staff', password='password')
        self.client.force_login(user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
