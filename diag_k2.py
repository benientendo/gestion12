import os, sys, django, re
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()
from django.utils import timezone
from datetime import datetime, timedelta
from inventory.models import Vente, Client

print("=== TOUS LES TERMINAUX ===")
for t in Client.objects.filter(est_actif=True):
    nt = t.nom_terminal or ''
    print(f"ID={t.id} | {nt} | serie={t.numero_serie} | boutique_id={t.boutique_id}")

print("\n=== TERMINAUX KIMPESE ===")
for t in Client.objects.filter(est_actif=True):
    nt = (t.nom_terminal or '').lower()
    if 'kimpese' in nt or 'kimp' in nt:
        print(f"\nTerminal: ID={t.id} | {t.nom_terminal} | serie={t.numero_serie}")
        ventes = Vente.objects.filter(client_maui=t).order_by('-date_vente')[:15]
        print(f"  Dernieres {ventes.count()} ventes:")
        pat = re.compile(r'-(\d{17})-')
        for v in ventes:
            uid = v.numero_facture or ''
            m = pat.search(uid)
            uid_info = ''
            if m:
                ts = m.group(1)
                try:
                    uid_dt = datetime(int(ts[0:4]),int(ts[4:6]),int(ts[6:8]),int(ts[8:10]),int(ts[10:12]),int(ts[12:14]))
                    uid_info = f" | uid_utc={uid_dt.strftime('%d/%m %H:%M')}"
                except:
                    pass
            dv = v.date_vente
            if dv:
                dv_local = timezone.localtime(dv)
                print(f"  {uid[:40]:<40} | dv={dv_local.strftime('%d/%m/%Y %H:%M')}{uid_info} | {v.montant_total}")
            else:
                print(f"  {uid[:40]:<40} | dv=None{uid_info}")

print("\n=== VENTES AUJOURD'HUI ===")
today = timezone.now().date()
print(f"Date serveur: {timezone.now().strftime('%d/%m/%Y %H:%M:%S')}")
for v in Vente.objects.filter(date_vente__date=today).order_by('-date_vente')[:20]:
    dv = timezone.localtime(v.date_vente)
    terminal = v.client_maui.nom_terminal if v.client_maui else 'N/A'
    print(f"  {(v.numero_facture or '')[:40]:<40} | {terminal:<20} | {dv.strftime('%d/%m %H:%M')} | {v.montant_total}")
