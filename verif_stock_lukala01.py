"""
Vérification des calculs de stock pour KMC LUKALA 01
-----------------------------------------------------
Compare le stock stocké en base (Article.quantite_stock) avec :
  1. La somme des MouvementStock (journal officiel)
  2. Le recalcul manuel : ventes - approvisionnements - transferts - inventaires

Usage (Scalingo) :
  scalingo --app gestion-magazin-app run python verif_stock_lukala01.py
"""

import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from django.db.models import Sum, Q
from inventory.models import (
    Boutique, Article, MouvementStock, LigneVente,
    LigneApprovisionnement, TransfertStock
)

NOM_BOUTIQUE = "LUKALA 01"

# ── 1. Trouver la boutique ──────────────────────────────────────────────────
try:
    boutique = Boutique.objects.get(nom__iexact=NOM_BOUTIQUE)
except Boutique.DoesNotExist:
    # Recherche partielle si nom exact inconnu
    resultats = Boutique.objects.filter(nom__icontains="LUKALA")
    print("Boutique exacte non trouvée. Boutiques contenant 'LUKALA' :")
    for b in resultats:
        print(f"  id={b.id}  nom='{b.nom}'")
    raise SystemExit("Corrigez NOM_BOUTIQUE et relancez.")

print(f"\n{'='*70}")
print(f"  VÉRIFICATION DU STOCK — {boutique.nom.upper()} (id={boutique.id})")
print(f"{'='*70}\n")

articles = Article.objects.filter(boutique=boutique, est_actif=True).order_by('nom')
print(f"  Nombre d'articles actifs : {articles.count()}\n")

# ── 2. Colonnes d'en-tête ──────────────────────────────────────────────────
fmt = "{:<35} {:>8} {:>10} {:>10} {:>9} {:>9} {:>9} {:>9} {:>8}"
print(fmt.format(
    "Article", "Stocké", "Journal Σ", "Écart",
    "Entrées", "Ventes", "Ajust.", "Transfert", "Inventaire"
))
print("-" * 110)

# ── 3. Compteurs globaux ────────────────────────────────────────────────────
total_articles     = 0
total_divergences  = 0
total_stocke       = 0
total_journal      = 0

divergences = []   # (article, stocké, journal, écart)

for art in articles:
    total_articles += 1

    # --- Journal : somme de tous les MouvementStock ---
    mouvements = MouvementStock.objects.filter(article=art)
    stock_journal = mouvements.aggregate(s=Sum('quantite'))['s'] or 0

    # --- Décomposition par type ---
    def somme_type(*types):
        return mouvements.filter(type_mouvement__in=types).aggregate(s=Sum('quantite'))['s'] or 0

    entrees     = somme_type('ENTREE')
    ventes_mvt  = somme_type('VENTE')
    ajustements = somme_type('AJUSTEMENT')
    transferts  = somme_type('SORTIE')   # SORTIE = transfert sortant / retrait
    inventaire  = somme_type('RETOUR')   # parfois utilisé pour régularisation

    stocke = art.quantite_stock
    ecart  = stocke - stock_journal

    total_stocke  += stocke
    total_journal += stock_journal

    if ecart != 0:
        total_divergences += 1
        divergences.append({
            'nom': art.nom[:34],
            'stocke': stocke,
            'journal': stock_journal,
            'ecart': ecart,
            'entrees': entrees,
            'ventes': ventes_mvt,
            'ajust': ajustements,
            'transfert': transferts,
            'inventaire': inventaire,
        })
        flag = "  ← DIVERGENCE"
    else:
        flag = ""

    print(fmt.format(
        art.nom[:34],
        stocke,
        stock_journal,
        ecart if ecart != 0 else "-",
        entrees,
        ventes_mvt,
        ajustements,
        transferts,
        inventaire,
    ) + flag)

# ── 4. Totaux ───────────────────────────────────────────────────────────────
print("-" * 110)
print(fmt.format(
    "TOTAL", total_stocke, total_journal,
    total_stocke - total_journal, "", "", "", "", ""
))

# ── 5. Résumé divergences ────────────────────────────────────────────────────
print(f"\n{'='*70}")
print(f"  RÉSUMÉ")
print(f"{'='*70}")
print(f"  Articles analysés    : {total_articles}")
print(f"  Stock total stocké   : {total_stocke}")
print(f"  Stock total journal  : {total_journal}")
print(f"  Divergences trouvées : {total_divergences}")

if divergences:
    print(f"\n  ⚠️  ARTICLES AVEC DIVERGENCE :")
    print(f"  {'Article':<35} {'Stocké':>8} {'Journal':>8} {'Écart':>8}")
    print(f"  {'-'*65}")
    for d in divergences:
        signe = "+" if d['ecart'] > 0 else ""
        print(f"  {d['nom']:<35} {d['stocke']:>8} {d['journal']:>8} {signe}{d['ecart']:>7}")
    print(f"\n  Légende écart : positif = stocké > journal (stock gonflé)")
    print(f"                  négatif = stocké < journal (stock sous-évalué)")
else:
    print("\n  ✅  Aucune divergence — tous les stocks correspondent au journal.")

# ── 6. Vérification croisée via LigneVente ──────────────────────────────────
print(f"\n{'='*70}")
print(f"  VÉRIFICATION CROISÉE : ventes enregistrées vs mouvements VENTE")
print(f"{'='*70}")

for art in articles:
    # Quantité totale vendue selon LigneVente
    qtv_vente = LigneVente.objects.filter(
        article=art,
        vente__boutique=boutique,
        vente__est_annulee=False,
        vente__paye=True
    ).aggregate(s=Sum('quantite'))['s'] or 0

    # Quantité selon MouvementStock type=VENTE (valeur absolue)
    qtv_mvt = abs(
        MouvementStock.objects.filter(article=art, type_mouvement='VENTE')
        .aggregate(s=Sum('quantite'))['s'] or 0
    )

    ecart = qtv_vente - qtv_mvt
    if ecart != 0:
        print(f"  ⚠️  {art.nom[:45]:<45}  LigneVente={qtv_vente}  MvtVente={qtv_mvt}  écart={ecart:+d}")

print("\n  (Aucune ligne = ventes et mouvements VENTE cohérents)\n")
print("  Script terminé.\n")
