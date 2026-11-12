# -*- coding: utf-8 -*-
"""
Diagnostic serveur (incident « serveur Scalingo bloqué »)
=========================================================

Trois familles de contrôles, sans accès aux logs Scalingo :

1. /healthz/ : endpoint public de disponibilité (base + cache) ;
2. temps d'attente Redis : une connexion Redis qui bloque ne doit plus
   pouvoir figer une requête web (cache, channel layer, broker) ;
3. push FCM : l'envoi vers Google ne doit JAMAIS avoir lieu dans le fil
   de la requête web (timeout 120 s par défaut → figement de daphne).
"""
import time
from unittest import mock

from django.test import SimpleTestCase

from gestion_magazin import settings as settings_projet
from inventory.services import firebase_push
from inventory.tests.test_demande_annulation import DemandeAnnulationBase


# ─────────────────────────────────────────────────────────────
# 1. Endpoint /healthz/
# ─────────────────────────────────────────────────────────────
class HealthzTestCase(DemandeAnnulationBase):

    def test_healthz_repond_200_avec_etat(self):
        r = self.web.get('/healthz/')
        self.assertEqual(r.status_code, 200)
        etat = r.json()
        self.assertEqual(etat['statut'], 'ok')
        self.assertTrue(etat['base'])
        self.assertIn('cache', etat)

    def test_healthz_est_public(self):
        """Aucune connexion exigée : le monitoring doit pouvoir l'appeler."""
        r = self.web.get('/healthz/')
        # Pas de redirection vers /login/
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/json')


# ─────────────────────────────────────────────────────────────
# 2. Temps d'attente Redis
# ─────────────────────────────────────────────────────────────
class TempsAttenteRedisTestCase(SimpleTestCase):

    def test_url_redis_completee_par_des_timeouts(self):
        url = settings_projet._redis_avec_temps_attente('redis://h:6379/0')
        self.assertIn('socket_connect_timeout=5', url)
        self.assertIn('socket_timeout=10', url)
        self.assertTrue(url.startswith('redis://h:6379/0?'))

    def test_url_deja_configuree_non_dupliquee(self):
        configuree = 'redis://h:6379/0?socket_timeout=3'
        self.assertEqual(
            settings_projet._redis_avec_temps_attente(configuree), configuree,
        )

    def test_url_absente_inchangee(self):
        self.assertIsNone(settings_projet._redis_avec_temps_attente(None))
        self.assertEqual(settings_projet._redis_avec_temps_attente(''), '')


# ─────────────────────────────────────────────────────────────
# 3. Push FCM non bloquant
# ─────────────────────────────────────────────────────────────
class PushNonBloquantTestCase(DemandeAnnulationBase):

    def setUp(self):
        super().setUp()
        self.terminal.fcm_token = 'jeton-1'
        self.terminal.save(update_fields=['fcm_token'])

    def _creds(self, valeur=True):
        return mock.patch.object(firebase_push, '_creds_prets', return_value=valeur)

    def test_sans_credentials_retourne_zero(self):
        with self._creds(False):
            self.assertEqual(
                firebase_push.envoyer_push_boutique(self.boutique.id, 'T', 'C'), 0,
            )
            self.assertFalse(
                firebase_push.envoyer_push_terminal(self.terminal, 'T', 'C'),
            )

    def test_boutique_delage_en_arriere_plan(self):
        """La requête rend la main sans appeler Google (envoi délégué)."""
        capture = {}

        def faux_soumettre(job):
            capture['job'] = job
            return True

        with self._creds(), \
                mock.patch.object(firebase_push, '_soumettre', side_effect=faux_soumettre), \
                mock.patch.object(firebase_push, '_envoyer_aux_tokens', return_value=1) as envoi:
            nb = firebase_push.envoyer_push_boutique(self.boutique.id, 'T', 'C')

            # Rend la main avec le nombre de terminaux VISÉS
            self.assertEqual(nb, 1)
            # Aucun envoi réel dans le fil de la requête
            envoi.assert_not_called()

            # Le job fourni à la file est bien l'envoi différé
            self.assertIn('job', capture)
            capture['job']()
            envoi.assert_called_once()

    def test_terminal_delage_en_arriere_plan(self):
        capture = {}

        def faux_soumettre(job):
            capture['job'] = job
            return True

        with self._creds(), \
                mock.patch.object(firebase_push, '_soumettre', side_effect=faux_soumettre), \
                mock.patch.object(firebase_push, '_envoyer_au_terminal', return_value=True) as envoi:
            ok = firebase_push.envoyer_push_terminal(self.terminal, 'T', 'C')

            self.assertTrue(ok)
            envoi.assert_not_called()

            capture['job']()
            envoi.assert_called_once_with('T1', 'jeton-1', 'T', 'C', None)

    def test_mode_synchrone_envoie_immediatement(self):
        """Les endpoints de test conservent un envoi réel et attendu."""
        with self._creds(), \
                mock.patch.object(firebase_push, '_envoyer_aux_tokens', return_value=1) as envoi:
            nb = firebase_push.envoyer_push_boutique(
                self.boutique.id, 'T', 'C', synchrone=True,
            )
            self.assertEqual(nb, 1)
            envoi.assert_called_once()

    def test_file_saturee_ne_bloque_pas(self):
        """4 envois en cours → le 5e est refusé, la requête n'attend pas."""
        acquis = [
            firebase_push._file_envoi.acquire(blocking=False)
            for _ in range(firebase_push.MAX_ENVOIS_SIMULTANES)
        ]
        try:
            self.assertTrue(all(acquis))
            self.assertFalse(firebase_push._soumettre(lambda: None))
        finally:
            for _ in acquis:
                firebase_push._file_envoi.release()

    def test_soumetre_executable_en_fond(self):
        """Le job tourne réellement dans un thread et libère la file."""
        faits = []
        self.assertTrue(firebase_push._soumettre(lambda: faits.append(1)))
        for _ in range(200):  # attente bornée sur l'exécution du thread
            if faits:
                break
            time.sleep(0.01)
        self.assertEqual(faits, [1])

        # La file est entièrement libérée après exécution
        reacquis = [
            firebase_push._file_envoi.acquire(blocking=False)
            for _ in range(firebase_push.MAX_ENVOIS_SIMULTANES)
        ]
        try:
            self.assertTrue(all(reacquis))
        finally:
            for _ in reacquis:
                firebase_push._file_envoi.release()
