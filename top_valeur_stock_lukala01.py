"""
Top articles par valeur de stock — LUKALA 01
--------------------------------------------
Trie les articles par valeur de stock (quantite_stock * prix_achat) décroissant.
Affiche la somme cumulative pour identifier les articles qui font monter
la valeur totale au-delà de 1 550 000 FC.
"""

import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Boutique, Article

SEUIL_FC = 1_550_000
NOM_BOUTIQUE = "LUKALA 01"

boutique = Boutique.objects.get(nom__iexact=NOM_BOUTIQUE)

articles = (
    Article.objects
    .filter(boutique=boutique, est_actif=True, quantite_stock__gt=0)
    .values('nom', 'code', 'quantite_stock', 'prix_achat', 'prix_vente')
)

# Calcul valeur individuelle et tri décroissant
lignes = []
for a in articles:
    try:
        pa   = float(a['prix_achat'] or 0)
        pv   = float(a['prix_vente'] or 0)
        qte  = int(a['quantite_stock'])
        # Pour les boutiques, prix_achat = 0 → on utilise prix_vente comme référence
        ref  = pv if pa == 0 else pa
        val  = round(ref * qte, 2)
        valv = round(pv * qte, 2)
    except Exception:
        continue
    if val > 0:
        lignes.append({
            'nom':    a['nom'],
            'code':   a['code'] or '',
            'qte':    qte,
            'pa':     pa,
            'pv':     pv,
            'ref':    ref,
            'val':    val,
            'valv':   valv,
        })

lignes.sort(key=lambda x: x['val'], reverse=True)

# ── Affichage ────────────────────────────────────────────────────────────────
print(f"\n{'='*95}")
print(f"  TOP ARTICLES PAR VALEUR STOCK — {NOM_BOUTIQUE}  (seuil affiché : {SEUIL_FC:,} FC)")
print(f"{'='*95}")

note_prix = "(prix_vente utilisé car prix_achat=0 pour les boutiques)"
print(f"  Note : {note_prix}")
hdr = "{:>4} {:<40} {:>6} {:>10} {:>12} {:>14} {:>14}"
print(hdr.format("Rg", "Article", "Qté", "P.Vente", "Val.Stock FC", "Val.Vente FC", "Cumul FC"))
print("-" * 95)

cumul = 0.0
seuil_atteint = False

for i, l in enumerate(lignes, 1):
    cumul += l['val']

    if not seuil_atteint and cumul >= SEUIL_FC:
        seuil_atteint = True
        print(f"{'':>4} {'':->40} {'':->6} {'':->10} {'':->12} {'':->14} {'':->14}  ← SEUIL {SEUIL_FC:,} FC ATTEINT")

    flag = ""
    if l['val'] >= 200_000:
        flag = "  *** VALEUR ELEVEE"
    elif l['qte'] >= 500 and l['pv'] >= 1_000:
        flag = "  *** QTE IMPORTANTE"

    print(hdr.format(
        i,
        l['nom'][:39],
        f"{l['qte']:,}",
        f"{l['pv']:,.0f}",
        f"{l['val']:,.0f}",
        f"{l['valv']:,.0f}",
        f"{cumul:,.0f}",
    ) + flag)

# ── Résumé ───────────────────────────────────────────────────────────────────
print("=" * 95)
articles_au_seuil = sum(1 for l in lignes if sum(x['val'] for x in lignes[:lignes.index(l)+1]) <= SEUIL_FC + l['val'])
valeur_totale = sum(l['val'] for l in lignes)
valeur_vente_totale = sum(l['valv'] for l in lignes)

print(f"\n  Articles avec valeur > 0        : {len(lignes)}")
print(f"  Valeur totale stock (achat)      : {valeur_totale:>15,.0f} FC")
print(f"  Valeur totale stock (vente)      : {valeur_vente_totale:>15,.0f} FC")
print(f"  Marge potentielle                : {valeur_vente_totale - valeur_totale:>15,.0f} FC")

# Top 5 contributeurs
print(f"\n  TOP 5 articles les plus lourds en valeur :")
for l in lignes[:5]:
    pct = l['val'] / valeur_totale * 100 if valeur_totale else 0
    print(f"    {l['nom'][:45]:<45}  {l['val']:>12,.0f} FC  ({pct:.1f}%  du total)  Qté={l['qte']:,}")

# Articles suspects : quantité très élevée ET prix élevé
suspects = [l for l in lignes if l['val'] >= 500_000]
if suspects:
    print(f"\n  ⚠️  ARTICLES SUSPECTS (valeur unitaire >= 500 000 FC) :")
    for l in suspects:
        print(f"    {l['nom'][:45]:<45}  Qté={l['qte']:>6,}  P.vente={l['pv']:>8,.0f} FC  => {l['val']:>12,.0f} FC")
else:
    print("\n  ✅  Aucun article avec valeur >= 500 000 FC.")

print("\n  Script terminé.\n")
