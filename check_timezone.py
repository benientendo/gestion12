import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from django.conf import settings
from django.utils import timezone
from datetime import datetime

print("=" * 50)
print("CONFIGURATION TIMEZONE DJANGO")
print("=" * 50)
print(f"TIME_ZONE configuré: {settings.TIME_ZONE}")
print(f"USE_TZ: {settings.USE_TZ}")
print()
print(f"Heure système PC: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Heure UTC Django: {timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
print(f"Heure locale Django: {timezone.localtime(timezone.now()).strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Vérifier une notification récente
from inventory.models import NotificationStock

derniere_notif = NotificationStock.objects.order_by('-date_creation').first()
if derniere_notif:
    print("DERNIÈRE NOTIFICATION:")
    print(f"  ID: {derniere_notif.id}")
    print(f"  Titre: {derniere_notif.titre}")
    print(f"  Date création (UTC): {derniere_notif.date_creation}")
    print(f"  Date création (locale): {timezone.localtime(derniere_notif.date_creation).strftime('%d/%m/%Y à %H:%M')}")
    if hasattr(derniere_notif, 'date_creation_formatee') and derniere_notif.date_creation_formatee:
        print(f"  Date formatée (API): {derniere_notif.date_creation_formatee}")
else:
    print("Aucune notification trouvée")

print("=" * 50)
