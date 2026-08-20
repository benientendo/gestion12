# -*- coding: utf-8 -*-
"""
🔥 Test des notifications push FCM (Firebase Cloud Messaging).

Vérifie l'intégration de bout en bout : envoie une notification de TEST aux
terminaux FCM enregistrés d'une boutique.

Prérequis (une seule fois) :
  1. Déposer le compte de service Firebase sur le serveur (Console Firebase
     → Paramètres du projet → Comptes de service → Générer une clé privée).
  2. Définir la variable d'environnement du serveur :
       GOOGLE_APPLICATION_CREDENTIALS=<chemin vers le JSON du compte de service>
     (ou FIREBASE_SERVICE_ACCOUNT_JSON=contenu JSON — utile sur Scalingo)

Usage :
  python test_push_fcm.py 12          -> envoie un test à la boutique 12
  python test_push_fcm.py 12 "Message" "Titre"
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gestion_magazin.settings")
django.setup()

from inventory.models import Client
from inventory.services.firebase_push import envoyer_push_boutique, _creds_prets

boutique_id = int(sys.argv[1]) if len(sys.argv) > 1 else 12
titre = sys.argv[2] if len(sys.argv) > 2 else "🔔 Test notification"
corps = sys.argv[3] if len(sys.argv) > 3 else "Notification de test depuis le serveur (FCM)."

if not _creds_prets():
    print("❌ FCM non configuré sur ce serveur.")
    print("   Définissez GOOGLE_APPLICATION_CREDENTIALS (ou FIREBASE_SERVICE_ACCOUNT_JSON).")
    sys.exit(1)

terminaux = Client.objects.filter(
    boutique_id=boutique_id, est_actif=True
).exclude(fcm_token="").exclude(fcm_token__isnull=True)
print(f"Terminaux FCM enregistrés pour la boutique {boutique_id} : {terminaux.count()}")
if terminaux.count() == 0:
    print("⚠️ Aucun jeton FCM enregistré — lancez l'app Android et connectez-vous pour qu'elle s'enregistre.")
    sys.exit(0)

envois = envoyer_push_boutique(boutique_id, titre, corps, data={"type": "test_notification"})
print(f"✅ {envois} notification(s) envoyée(s) !")
print(f"   Titre : {titre}")
print(f"   Corps : {corps}")
print("   Si le terminal reçoit le message même app fermée → FCM opérationnel.")