# =====================================================================
# SCRIPT PRODUCTION - Articles non saisis à l'inventaire
# =====================================================================
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Boutique, Inventaire, LigneInventaire, Article, VarianteArticle
from datetime import date

# 1. Trouver la boutique
boutique = Boutique.objects.filter(nom__icontains="KIMPESE 01").first()
if not boutique:
    boutique = Boutique.objects.filter(nom__icontains="KMC").first()
if not boutique:
    print("Boutiques disponibles:")
    for b in Boutique.objects.all():
        print(f"  {b.id}: {b.nom}")
    raise SystemExit("Boutique non trouvee")
print(f"Boutique: {boutique.nom} (ID: {boutique.id})")

# 2. Trouver l'inventaire avec nb_articles=1952 et nb_ecarts=572
inventaires = Inventaire.objects.filter(boutique=boutique).order_by('-date_regularisation')
print(f"\nTous les inventaires de {boutique.nom}:")
for inv in inventaires:
    ecarts_reels = inv.lignes.exclude(ecart=0).count()
    print(f"  {inv.reference} | Date: {inv.date_inventaire} | Statut: {inv.statut} | Regularise: {inv.date_regularisation} | nb_articles={inv.nb_articles} nb_ecarts={inv.nb_ecarts} | Lignes DB: {inv.lignes.count()} | Ecarts reels: {ecarts_reels}")

# Chercher par nb_articles~1952 ou nb_ecarts~572
inventaire = None
for inv in inventaires:
    if inv.nb_articles == 1952 or inv.nb_ecarts == 572:
        inventaire = inv
        break
    if inv.lignes.count() == 1952:
        inventaire = inv
        break

if not inventaire:
    # Fallback: le plus recent regularise
    inventaire = inventaires.filter(statut='REGULARISE').first()
    print(f"\n⚠ Inventaire 1952/572 non trouve, utilisation du plus recent regularise")

if not inventaire:
    raise SystemExit("Aucun inventaire trouve")

print(f"\n>>> Inventaire selectionne: {inventaire.reference} (regularise le {inventaire.date_regularisation})")
print(f"    Nb lignes inventaire: {inventaire.lignes.count()}")
print(f"    Lignes avec stock_physique saisi: {inventaire.lignes.filter(stock_physique__isnull=False).count()}")
print(f"    Lignes avec stock_physique NULL (non compte): {inventaire.lignes.filter(stock_physique__isnull=True).count()}")

# 3. IDs des articles saisis dans l'inventaire
ids_saisis = set(inventaire.lignes.values_list('article_id', flat=True))

# ====== CATEGORIE A: Articles pas du tout dans l'inventaire mais avec stock > 0 ======
non_saisis = Article.objects.filter(
    boutique=boutique, est_actif=True, quantite_stock__gt=0
).exclude(id__in=ids_saisis).order_by('nom')

# ====== CATEGORIE B: Articles dans l'inventaire mais stock_physique jamais rempli (NULL) ET stock_theorique > 0 ======
lignes_non_comptees = inventaire.lignes.filter(
    stock_physique__isnull=True,
    stock_theorique__gt=0
).select_related('article').order_by('article__nom')

# 5. LISTE COMPLETE UNIFIEE: tous les articles avec stock qui n'ont PAS ete comptes
print(f"\n{'='*110}")
print(f"LISTE COMPLETE: ARTICLES AVEC STOCK NON INVENTORIES ({inventaire.reference})")
print(f"Boutique: {boutique.nom}")
print(f"{'='*110}")
print(f"{'#':<5} {'Nom':<38} {'Code':<18} {'Stock':<8} {'Categorie':<22} {'Variantes'}")
print(f"{'-'*110}")

liste_complete = []

# A: pas du tout dans l'inventaire
for a in non_saisis:
    variantes = list(VarianteArticle.objects.filter(article_parent=a, est_actif=True))
    liste_complete.append({
        'nom': a.nom,
        'code': a.code,
        'stock': a.quantite_stock,
        'cat': 'HORS INVENTAIRE',
        'variantes': variantes
    })

# B: dans l'inventaire mais stock_physique=NULL
for ligne in lignes_non_comptees:
    a = ligne.article
    variantes = list(VarianteArticle.objects.filter(article_parent=a, est_actif=True))
    liste_complete.append({
        'nom': a.nom,
        'code': a.code,
        'stock': ligne.stock_theorique,
        'cat': 'NON COMPTE',
        'variantes': variantes
    })

# Trier par nom
liste_complete.sort(key=lambda x: x['nom'])

total_stock = 0
for i, item in enumerate(liste_complete, 1):
    total_stock += item['stock']
    nb_var = len(item['variantes'])
    var_info = f"{nb_var} var." if nb_var > 0 else ""
    print(f"{i:<5} {item['nom'][:37]:<38} {item['code']:<18} {item['stock']:<8} {item['cat']:<22} {var_info}")
    # Afficher les variantes
    for v in item['variantes']:
        stock_v = v.quantite_stock
        print(f"{'':5}  -> {v.nom_variante:<30} Code: {v.code_barre:<15} Stock: {stock_v}")

print(f"{'-'*110}")
print(f"TOTAL: {len(liste_complete)} articles | Stock total non inventorie: {total_stock} unites")
print(f"{'='*110}")
