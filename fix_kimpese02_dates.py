#!/usr/bin/env python
"""
Script de diagnostic et correction des dates décalées pour Kimpese 02.
L'horloge de l'appareil Kimpese 02 était décalée de ~7-8h en avance,
causant des date_vente incorrectes dans Django.

Usage:
  python fix_kimpese02_dates.py          # Mode DIAGNOSTIC (lecture seule)
  python fix_kimpese02_dates.py --fix    # Mode CORRECTION (modifie les dates)
"""
import os, sys, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GestionMagazin.settings')
django.setup()

from django.utils import timezone
from datetime import datetime, timedelta
from inventory.models import Vente, Client
import re

MODE_FIX = '--fix' in sys.argv

print("=" * 70)
print(f"  KIMPESE 02 — {'CORRECTION' if MODE_FIX else 'DIAGNOSTIC'} DES DATES")
print("=" * 70)

# 1. Trouver le terminal Kimpese 02
terminaux = Client.objects.filter(nom__icontains='kimpese')
print(f"\nTerminaux trouvés avec 'kimpese':")
for t in terminaux:
    print(f"  - ID={t.id} | {t.nom} | série={t.numero_serie} | boutique={t.boutique}")

# Chercher Kimpese 02 spécifiquement
terminal_k2 = Client.objects.filter(nom__icontains='kimpese 02').first()
if not terminal_k2:
    terminal_k2 = Client.objects.filter(nom__icontains='kimpese').exclude(nom__icontains='01').first()

if not terminal_k2:
    print("\n❌ Terminal Kimpese 02 non trouvé. Vérifier manuellement.")
    # Lister tous les terminaux pour debug
    print("\nTous les terminaux actifs:")
    for t in Client.objects.filter(est_actif=True):
        print(f"  - ID={t.id} | {t.nom} | série={t.numero_serie}")
    sys.exit(1)

print(f"\n✅ Terminal Kimpese 02: ID={terminal_k2.id}, nom={terminal_k2.nom}, série={terminal_k2.numero_serie}")

# 2. Récupérer les ventes de ce terminal
ventes = Vente.objects.filter(client_maui=terminal_k2).order_by('-date_vente')
print(f"\n📊 Total ventes Kimpese 02: {ventes.count()}")

if ventes.count() == 0:
    # Essayer aussi par boutique
    if terminal_k2.boutique:
        ventes = Vente.objects.filter(boutique=terminal_k2.boutique).order_by('-date_vente')
        print(f"   (via boutique: {ventes.count()} ventes)")

# 3. Analyser le décalage via les UIDs
# Format UID: {posId}-{yyyyMMddHHmmssfff}-{shortGuid}
pattern = re.compile(r'-(\d{17})-')  # 17 chiffres = yyyyMMddHHmmssfff

offsets = []
ventes_avec_uid = []

print(f"\n--- Analyse des 30 dernières ventes ---")
for v in ventes[:30]:
    uid = v.numero_facture or ''
    match = pattern.search(uid)
    if match:
        ts_str = match.group(1)  # ex: 20260327171746633
        try:
            # Le timestamp dans l'UID était DateTime.UtcNow (horloge appareil)
            uid_utc = datetime(
                int(ts_str[0:4]), int(ts_str[4:6]), int(ts_str[6:8]),
                int(ts_str[8:10]), int(ts_str[10:12]), int(ts_str[12:14]),
                int(ts_str[14:17]) * 1000  # millisecondes
            )
            uid_utc = timezone.make_aware(uid_utc, timezone.utc)
            
            # date_vente stockée dans Django (déjà aware)
            dv = v.date_vente
            if timezone.is_naive(dv):
                dv = timezone.make_aware(dv)
            
            # Le décalage entre UID (UTC de l'appareil) et date_vente (local de l'appareil)
            # n'est pas utile car les deux utilisent la même horloge fausse
            
            # Ce qui nous intéresse: la date_vente est-elle cohérente?
            # Si l'appareil est en Africa/Kinshasa (UTC+1), 
            # date_vente (DateTime.Now) = uid_utc + 1h
            diff_uid_dv = (dv - uid_utc).total_seconds() / 3600
            
            print(f"  {uid[:30]:<30} | date_vente={dv.strftime('%d/%m %H:%M')} | uid_utc={uid_utc.strftime('%d/%m %H:%M')} | diff={diff_uid_dv:+.1f}h")
            
            ventes_avec_uid.append({
                'vente': v,
                'uid_utc': uid_utc,
                'date_vente': dv,
                'diff_hours': diff_uid_dv,
            })
        except Exception as e:
            print(f"  {uid[:30]:<30} | ERREUR parsing: {e}")
    else:
        print(f"  {uid[:30]:<30} | pas de timestamp dans UID")

# 4. Calculer l'offset moyen
if ventes_avec_uid:
    diffs = [v['diff_hours'] for v in ventes_avec_uid]
    avg_diff = sum(diffs) / len(diffs)
    print(f"\n📐 Différence moyenne UID_UTC → date_vente: {avg_diff:+.1f}h")
    print(f"   (attendu: +1.0h pour Africa/Kinshasa UTC+1)")
    
    if abs(avg_diff - 1.0) < 0.5:
        print(f"   ✅ Le timezone de l'appareil semble correct (UTC+1)")
    else:
        print(f"   ⚠️ Le timezone de l'appareil semble incorrect!")

# 5. Pour déterminer le vrai offset, comparer avec les ventes de Kimpese 01 (référence correcte)
terminal_k1 = Client.objects.filter(nom__icontains='kimpese 01').first()
if not terminal_k1:
    terminal_k1 = Client.objects.filter(nom__icontains='kimpese').filter(nom__icontains='01').first()

if terminal_k1:
    print(f"\n--- Comparaison avec Kimpese 01 (ID={terminal_k1.id}) ---")
    ventes_k1 = Vente.objects.filter(client_maui=terminal_k1).order_by('-date_vente')[:5]
    for v in ventes_k1:
        print(f"  K1: {v.numero_facture[:30]:<30} | date_vente={v.date_vente.strftime('%d/%m %H:%M')}")
    
    ventes_k2_recentes = ventes[:5]
    for v in ventes_k2_recentes:
        print(f"  K2: {(v.numero_facture or 'N/A')[:30]:<30} | date_vente={v.date_vente.strftime('%d/%m %H:%M')}")

# 6. Demander le décalage exact à l'utilisateur ou le calculer
print(f"\n" + "=" * 70)
print(f"PROCHAINE ÉTAPE:")
print(f"  Le décalage doit être déterminé en comparant une vente")
print(f"  dont on connaît l'heure réelle.")
print(f"  Exemple du user: vente à 10h réelle → affichée 17h32 → offset ≈ +7.5h")
print(f"")
print(f"  Pour corriger, relancer avec:")
print(f"    python fix_kimpese02_dates.py --fix --offset=-7.5")
print(f"=" * 70)

# Mode FIX
if MODE_FIX:
    offset_arg = [a for a in sys.argv if a.startswith('--offset=')]
    if not offset_arg:
        print("\n❌ Spécifier --offset=HEURES (ex: --offset=-7.5)")
        sys.exit(1)
    
    offset_hours = float(offset_arg[0].split('=')[1])
    offset_delta = timedelta(hours=offset_hours)
    
    print(f"\n🔧 APPLICATION DE L'OFFSET: {offset_hours:+.1f}h sur toutes les ventes Kimpese 02")
    print(f"   ({ventes.count()} ventes à corriger)")
    
    confirm = input("   Confirmer? (oui/non): ").strip().lower()
    if confirm != 'oui':
        print("   Annulé.")
        sys.exit(0)
    
    count = 0
    for v in ventes:
        old_date = v.date_vente
        new_date = old_date + offset_delta
        v.date_vente = new_date
        v.save(update_fields=['date_vente'])
        count += 1
        if count <= 5:
            print(f"   ✅ {v.numero_facture[:25]} : {old_date.strftime('%d/%m %H:%M')} → {new_date.strftime('%d/%m %H:%M')}")
    
    if count > 5:
        print(f"   ... et {count - 5} autres ventes corrigées")
    
    print(f"\n✅ {count} ventes corrigées avec offset {offset_hours:+.1f}h")
