#!/usr/bin/env python
"""Diagnostic: CA du jour Kimpese 02"""
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'gestion_magazin.settings'
django.setup()

from inventory.models import Vente, Boutique, LigneVente
from django.utils import timezone
from django.db.models import Sum, Q

# Trouver la boutique
b = Boutique.objects.filter(nom__icontains='kimpese').exclude(nom__icontains='01').first()
if not b:
    b = Boutique.objects.filter(nom__icontains='kimpese 02').first()
print(f"Boutique: {b.nom} (ID: {b.id})")

now = timezone.now()
today = now.date()
print(f"Server now: {now}")
print(f"Today (localtime): {today}")
print(f"Timezone: {timezone.get_current_timezone()}")
print()

# Requete identique a _compute_dashboard_stats
ventes_base = Q(paye=True, est_annulee=False) & (Q(boutique=b) | Q(client_maui__boutique=b))
ventes_jour = Vente.objects.filter(ventes_base, date_vente__date=today).distinct().order_by('date_vente')

print(f"=== VENTES DU JOUR ({today}) ===")
print(f"Nombre: {ventes_jour.count()}")
total_cdf = 0
total_usd = 0
for v in ventes_jour:
    local_time = timezone.localtime(v.date_vente)
    print(f"  #{v.id} | {v.numero_facture[:35]:35s} | {local_time.strftime('%H:%M:%S')} (UTC: {v.date_vente.strftime('%H:%M:%S')}) | {v.montant_total} {v.devise} | boutique_id={v.boutique_id} | terminal={v.client_maui_id}")
    if v.devise == 'CDF':
        total_cdf += v.montant_total
    elif v.devise == 'USD':
        total_usd += v.montant_total

print(f"\nTotal CDF: {total_cdf}")
print(f"Total USD: {total_usd}")

# Verifier aussi les ventes d'hier pour les cas timezone
yesterday = today - __import__('datetime').timedelta(days=1)
ventes_hier = Vente.objects.filter(ventes_base, date_vente__date=yesterday).distinct()
ca_hier = ventes_hier.filter(devise='CDF').aggregate(t=Sum('montant_total'))['t'] or 0
print(f"\nCA hier ({yesterday}): {ca_hier} CDF ({ventes_hier.count()} ventes)")

# Verifier les terminaux de cette boutique
from inventory.models import ClientMaui
terminals = ClientMaui.objects.filter(boutique=b)
for t in terminals:
    print(f"  Terminal: {t.nom_terminal} (ID: {t.id}, serial: {t.serial_number})")
