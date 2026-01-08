import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Vente, VenteRejetee, Boutique, Client
from django.utils import timezone
from datetime import datetime, timedelta

today = timezone.now().date()

print("=== TERMINAUX MAUI ACTIFS ===")
terminals = Client.objects.filter(est_actif=True)
for t in terminals:
    print(f"  - {t.nom_terminal}: {t.numero_serie}")
    print(f"    Boutique: {t.boutique.nom if t.boutique else 'N/A'}")
    print(f"    Derniere sync: {t.derniere_synchro if hasattr(t, 'derniere_synchro') else 'N/A'}")
print(f"Date actuelle: {timezone.now()}")
print(f"Date du jour: {today}")

print("\n=== VENTES AUJOURDHUI (1er Janvier) ===")
ventes_today = Vente.objects.filter(date_vente__date=today)
print(f"Ventes trouvees: {ventes_today.count()}")
for v in ventes_today[:5]:
    print(f"  - {v.numero_facture}: {v.montant_total} CDF - {v.date_vente}")

print("\n=== VENTES HIER (31 Decembre) ===")
yesterday = today - timedelta(days=1)
ventes_yesterday = Vente.objects.filter(date_vente__date=yesterday)
print(f"Ventes trouvees: {ventes_yesterday.count()}")

print("\n=== DERNIERES VENTES TOUTES DATES ===")
last_ventes = Vente.objects.all().order_by('-date_vente')[:5]
for v in last_ventes:
    print(f"  - {v.numero_facture}: {v.montant_total} CDF - {v.date_vente}")

print("\n=== VENTES REJETEES AUJOURDHUI ===")
rejets_today = VenteRejetee.objects.filter(date_tentative__date=today)
print(f"Ventes rejetees: {rejets_today.count()}")
for r in rejets_today[:10]:
    print(f"  - UID: {r.vente_uid}")
    print(f"    Raison: {r.get_raison_rejet_display()}")
    print(f"    Message: {r.message_erreur[:100] if r.message_erreur else 'N/A'}")
    print(f"    Boutique: {r.boutique.nom if r.boutique else 'N/A'}")
    print()

print("\n=== VENTES REJETEES RECENTES (TOUTES DATES) ===")
rejets_all = VenteRejetee.objects.all().order_by('-date_tentative')[:5]
for r in rejets_all:
    print(f"  - {r.date_tentative}: {r.get_raison_rejet_display()}")

print("\n=== STATISTIQUES PAR BOUTIQUE ===")
for b in Boutique.objects.filter(est_depot=False):
    ventes_b = Vente.objects.filter(boutique=b, date_vente__date=today).count()
    rejets_b = VenteRejetee.objects.filter(boutique=b, date_tentative__date=today).count()
    print(f"  {b.nom}: {ventes_b} ventes, {rejets_b} rejets aujourd'hui")
