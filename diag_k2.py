"""
Diagnostic et correction des dates Kimpese 02 (ID=62)

Usage:
  python diag_k2.py            # Diagnostic seul
  python diag_k2.py --fix      # Appliquer les corrections
"""

import os, sys, django
from datetime import timedelta
from collections import defaultdict

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from django.utils import timezone
from inventory.models import Vente, Client

MODE_FIX = '--fix' in sys.argv
now = timezone.now()

print(f"=== Heure serveur: {now.strftime('%d/%m/%Y %H:%M:%S')} ===\n")

# 🔒 FORCER LE BON TERMINAL
# 🔒 FORCER PAR NUMERO DE SERIE (LE PLUS FIABLE)
k2 = Client.objects.filter(numero_serie="DESKTOP-QRU50NU").first()

if not k2:
    print("❌ Terminal QRU50NU introuvable")
    sys.exit(1)

print(f"=== KIMPESE 02: ID={k2.id} | {k2.nom_terminal} | serie={k2.numero_serie} ===")

# -----------------------------
# 1. Charger les ventes
# -----------------------------
ventes_k2 = Vente.objects.filter(client_maui=k2).order_by('-date_vente')
total = ventes_k2.count()

print(f"Total ventes: {total}")

if total == 0:
    print("\n❌ Aucune vente trouvée pour ce terminal")
    sys.exit()

# -----------------------------
# 2. Séparer FUTURE / OK
# -----------------------------
ventes_futures = []
ventes_ok = []

for v in ventes_k2:
    if v.date_vente and v.date_vente > now + timedelta(minutes=30):
        ventes_futures.append(v)
    else:
        ventes_ok.append(v)

print(f"\nVentes FUTURE (>30min): {len(ventes_futures)}")
print(f"Ventes OK: {len(ventes_ok)}")

# -----------------------------
# 3. Affichage anomalies
# -----------------------------
if ventes_futures:
    print("\n--- VENTES A CORRIGER ---")
    for v in ventes_futures[:20]:
        dv = timezone.localtime(v.date_vente)
        ecart = (v.date_vente - now).total_seconds() / 3600
        print(f"{(v.numero_facture or '')[:30]:<30} | {dv.strftime('%d/%m %H:%M')} | +{ecart:.1f}h")

# -----------------------------
# 4. MODE FIX
# -----------------------------
if MODE_FIX and ventes_futures:

    print(f"\n=== CORRECTION EN COURS ({len(ventes_futures)} ventes) ===")

    par_jour = defaultdict(list)

    for v in ventes_futures:
        jour = timezone.localtime(v.date_vente).date()
        par_jour[jour].append(v)

    total_corrigees = 0

    for jour, ventes_jour in sorted(par_jour.items()):

        print(f"\nJour {jour} → {len(ventes_jour)} ventes")

        for v in ventes_jour:
            ancienne = v.date_vente

            # 🔧 Correction : ramener dans le passé
            ecart = ancienne - now
            nouvelle = now - timedelta(seconds=abs(ecart.total_seconds()))

            v.date_vente = nouvelle
            v.save(update_fields=['date_vente'])

            total_corrigees += 1

            if total_corrigees <= 5:
                print(f"{v.numero_facture[:25]} : corrigé")

    print(f"\n✅ TOTAL corrigé: {total_corrigees}")

elif not MODE_FIX:
    print("\n⚠️ Mode diagnostic. Ajouter --fix pour corriger.")

else:
    print("\n✔ Rien à corriger.")