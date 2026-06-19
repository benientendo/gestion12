"""
Articles dont la valeur de stock >= 1 550 000 FC — LUKALA 01
Lecture seule. Aucune modification.
valeur = quantite_stock * prix_vente
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Boutique, Article

SEUIL = 1_000_000
boutique = Boutique.objects.get(nom__iexact='LUKALA 01')

articles = Article.objects.filter(
    boutique=boutique,
    est_actif=True,
    quantite_stock__gt=0,
    prix_vente__gt=0,
)

lignes = []
for a in articles:
    valeur = int(a.quantite_stock) * float(a.prix_vente)
    if valeur >= SEUIL:
        lignes.append((valeur, a.nom, a.quantite_stock, float(a.prix_vente)))

lignes.sort(reverse=True)

print(f"\n{'='*75}")
print(f"  Articles avec valeur de stock >= {SEUIL:,} FC — LUKALA 01")
print(f"{'='*75}")
print(f"  {'Article':<40} {'Qte':>7} {'P.Vente':>10} {'Valeur FC':>13}")
print(f"  {'-'*72}")
for valeur, nom, qte, pv in lignes:
    print(f"  {nom[:39]:<40} {qte:>7,} {pv:>10,.0f} {valeur:>13,.0f}")

print(f"  {'-'*72}")
print(f"  Total articles : {len(lignes)}")
print(f"  Cumul valeur   : {sum(v for v,*_ in lignes):>13,.0f} FC")
print(f"{'='*75}\n")
