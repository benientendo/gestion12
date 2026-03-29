"""
Nettoyage des ventes pour débuter le 29 propre

Usage:
  python clean_29.py            # Diagnostic seul
  python clean_29.py --fix      # Appliquer les corrections
"""

import os, sys, django
from datetime import datetime, time, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from django.utils import timezone
from inventory.models import Vente, Client

MODE_FIX = '--fix' in sys.argv
now = timezone.now()

print(f"=== Heure serveur: {now.strftime('%d/%m/%Y %H:%M:%S')} ===\n")

# 🔒 Terminal Kimpese 02
try:
    k2 = Client.objects.get(id=62)
except Client.DoesNotExist:
    print("❌ Terminal ID=62 introuvable")
    sys.exit(1)

print(f"=== KIMPESE 02: ID={k2.id} | {k2.nom_terminal} | serie={k2.numero_serie} ===")

# -----------------------------
# 1. Déterminer période à nettoyer
# -----------------------------
jour_29 = now.date()  # aujourd'hui 29
debut_29 = timezone.make_aware(datetime.combine(jour_29, time(0, 0, 0)))
fin_29 = timezone.make_aware(datetime.combine(jour_29, time(5, 59, 59)))  # avant 06h

# -----------------------------
# 2. Sélectionner ventes à nettoyer
# -----------------------------
ventes_a_cleaner = Vente.objects.filter(
    client_maui=k2,
    date_vente__gte=debut_29,
    date_vente__lte=fin_29
).order_by('date_vente')

total = ventes_a_cleaner.count()
print(f"Ventes du 29 avant 06h à nettoyer: {total}")

if total == 0:
    print("✔ Rien à nettoyer")
    sys.exit()

# -----------------------------
# 3. Diagnostic / Affichage
# -----------------------------
print("\n--- VENTES A RECALER ---")
for v in ventes_a_cleaner[:20]:
    dv = timezone.localtime(v.date_vente)
    print(f"{(v.numero_facture or '')[:30]:<30} | {dv.strftime('%d/%m %H:%M:%S')}")

# -----------------------------
# 4. MODE FIX
# -----------------------------
if MODE_FIX:

    # Recala toutes les ventes à la veille 28 23:59:59
    veille = jour_29 - timedelta(days=1)
    nouvelle_heure = time(23, 59, 59)

    total_corrigees = 0
    for v in ventes_a_cleaner:
        ancienne = v.date_vente
        v.date_vente = timezone.make_aware(datetime.combine(veille, nouvelle_heure))
        v.save(update_fields=['date_vente'])
        total_corrigees += 1
        if total_corrigees <= 5:
            print(f"{v.numero_facture[:25]} : {ancienne} → {v.date_vente}")

    print(f"\n✅ TOTAL recalées: {total_corrigees}")

else:
    print("\n⚠️ Mode diagnostic. Ajouter --fix pour nettoyer.")