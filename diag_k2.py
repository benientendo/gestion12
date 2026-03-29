import os, sys, django, re
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()
from django.utils import timezone
from datetime import datetime, timedelta
from inventory.models import Vente, Client

print("=== TERMINAUX KIMPESE ===")
for t in Client.objects.all():
    if 'kimpese' in (t.nom or '').lower():
        print(f"ID={t.id} | {t.nom} | serie={t.numero_serie} | boutique_id={t.boutique_id}")
        ventes = Vente.objects.filter(client_maui=t).order_by('-date_vente')[:10]
        print(f"  Dernières {ventes.count()} ventes:")
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
                print(f"  {uid[:35]:<35} | dv={dv_local.strftime('%d/%m/%Y %H:%M')}{uid_info} | total={v.montant_total}")
            else:
                print(f"  {uid[:35]:<35} | dv=None{uid_info}")

print("\n=== TOUTES LES VENTES AUJOURD'HUI ===")
today = timezone.now().date()
for v in Vente.objects.filter(date_vente__date=today).order_by('-date_vente')[:20]:
    dv = timezone.localtime(v.date_vente)
    terminal = v.client_maui.nom if v.client_maui else 'N/A'
    print(f"  {(v.numero_facture or '')[:35]:<35} | {terminal:<20} | {dv.strftime('%d/%m %H:%M')} | {v.montant_total}")
