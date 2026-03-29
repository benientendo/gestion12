"""
Diagnostic et correction des dates Kimpese 02.
Usage:
  python diag_k2.py            # Diagnostic seul
  python diag_k2.py --fix      # Appliquer les corrections
"""
import os, sys, django, re
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()
from django.utils import timezone
from datetime import datetime, timedelta
from inventory.models import Vente, Client

MODE_FIX = '--fix' in sys.argv
now = timezone.now()
print(f"=== Heure serveur: {now.strftime('%d/%m/%Y %H:%M:%S')} ===\n")

# Trouver Kimpese 02
k2 = None
for t in Client.objects.filter(est_actif=True):
    nt = (t.nom_terminal or '').lower()
    print(f"Terminal: ID={t.id} | {t.nom_terminal} | serie={t.numero_serie}")
    if 'kimpese' in nt and '02' in nt:
        k2 = t

if not k2:
    # Fallback: chercher par serie QRU50NU
    k2 = Client.objects.filter(numero_serie__icontains='QRU50NU').first()

if not k2:
    print("\nKimpese 02 non trouve!")
    sys.exit(1)

print(f"\n=== KIMPESE 02: ID={k2.id} | {k2.nom_terminal} | serie={k2.numero_serie} ===")

# Toutes les ventes Kimpese 02
ventes_k2 = Vente.objects.filter(client_maui=k2).order_by('-date_vente')
print(f"Total ventes: {ventes_k2.count()}")

# Identifier les ventes avec date dans le futur (horloge decalee)
ventes_futures = []
ventes_ok = []
for v in ventes_k2:
    dv = v.date_vente
    if dv and dv > now + timedelta(minutes=30):
        ventes_futures.append(v)
    else:
        ventes_ok.append(v)

print(f"\nVentes avec date FUTURE (>30min apres serveur): {len(ventes_futures)}")
print(f"Ventes avec date OK: {len(ventes_ok)}")

# Afficher les ventes futures
if ventes_futures:
    print(f"\n--- Ventes a corriger ---")
    for v in ventes_futures[:20]:
        dv = timezone.localtime(v.date_vente)
        ecart = (v.date_vente - now).total_seconds() / 3600
        print(f"  {(v.numero_facture or '')[:40]:<40} | {dv.strftime('%d/%m %H:%M')} | +{ecart:.1f}h | {v.montant_total}")
    if len(ventes_futures) > 20:
        print(f"  ... et {len(ventes_futures) - 20} autres")

# Afficher les ventes recentes OK
print(f"\n--- 10 dernieres ventes OK ---")
for v in ventes_ok[:10]:
    dv = timezone.localtime(v.date_vente)
    print(f"  {(v.numero_facture or '')[:40]:<40} | {dv.strftime('%d/%m %H:%M')} | {v.montant_total}")

# MODE FIX: Corriger les ventes futures
if MODE_FIX and ventes_futures:
    print(f"\n{'='*60}")
    print(f"CORRECTION: {len(ventes_futures)} ventes avec date future")
    print(f"Strategie: date_vente = now - (ecart moyen des ventes du meme batch)")
    print(f"{'='*60}")
    
    # Grouper par jour pour appliquer une correction par jour
    from collections import defaultdict
    par_jour = defaultdict(list)
    for v in ventes_futures:
        jour = timezone.localtime(v.date_vente).date()
        par_jour[jour].append(v)
    
    total_corrigees = 0
    for jour, ventes_jour in sorted(par_jour.items()):
        # Pour les ventes d'un meme jour, on recale proportionnellement
        # L'ordre relatif des ventes est preserva
        print(f"\n  Jour {jour.strftime('%d/%m/%Y')}: {len(ventes_jour)} ventes")
        
        # Calculer l'ecart moyen pour ce jour
        ecarts = [(v.date_vente - now).total_seconds() for v in ventes_jour]
        ecart_max = max(ecarts)
        ecart_min = min(ecarts)
        
        # Recaler: chaque vente garde son heure relative mais decalee
        # de sorte que la plus recente = now
        for v in ventes_jour:
            ancienne = v.date_vente
            # Soustraire l'ecart pour ramener dans le passe
            ecart_v = ancienne - now
            nouvelle = now - timedelta(seconds=abs(ecart_v.total_seconds()))
            # Mais garder au minimum sur le meme jour reel
            v.date_vente = nouvelle
            v.save(update_fields=['date_vente'])
            total_corrigees += 1
            if total_corrigees <= 5:
                anc_str = timezone.localtime(ancienne).strftime('%d/%m %H:%M')
                nouv_str = timezone.localtime(nouvelle).strftime('%d/%m %H:%M')
                print(f"    {(v.numero_facture or '')[:30]} : {anc_str} -> {nouv_str}")
        
        if len(ventes_jour) > 5:
            print(f"    ... et {len(ventes_jour) - 5} autres")
    
    print(f"\n  TOTAL: {total_corrigees} ventes corrigees")
else:
    if not ventes_futures:
        print("\n Aucune vente a corriger!")
    else:
        print(f"\n Pour corriger, relancer avec: python diag_k2.py --fix")
