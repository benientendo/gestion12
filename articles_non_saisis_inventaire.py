"""
Script: Trouver les articles NON saisis lors d'un inventaire régularisé.
Usage: python manage.py shell < articles_non_saisis_inventaire.py
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Boutique, Inventaire, LigneInventaire, Article, VarianteArticle
from django.db.models import Q

# --- PARAMÈTRES ---
BOUTIQUE_NOM = "KMC KIMPESE 01"
# Date approximative de régularisation (23 mai 2025)
DATE_REGULARISATION = "2025-05-23"

# --- Trouver la boutique ---
boutique = Boutique.objects.filter(nom__icontains="KMC KIMPESE 01").first()
if not boutique:
    # Essayer d'autres variantes de nom
    boutique = Boutique.objects.filter(nom__icontains="KIMPESE 01").first()

if not boutique:
    print("❌ Boutique 'KMC KIMPESE 01' non trouvée.")
    print("Boutiques disponibles:")
    for b in Boutique.objects.all():
        print(f"  - {b.id}: {b.nom}")
    exit()

print(f"✅ Boutique trouvée: {boutique.nom} (ID: {boutique.id})")

# --- Trouver l'inventaire régularisé autour du 23/05 ---
inventaires = Inventaire.objects.filter(
    boutique=boutique,
    statut='REGULARISE'
).order_by('-date_regularisation')

# Filtrer autour de la date du 23/05
from datetime import date, timedelta
target_date = date(2025, 5, 23)
inventaire = None

for inv in inventaires:
    if inv.date_regularisation:
        diff = abs((inv.date_regularisation.date() - target_date).days)
        if diff <= 3:  # Tolérance de 3 jours
            inventaire = inv
            break

if not inventaire:
    # Prendre le plus récent régularisé
    inventaire = inventaires.first()

if not inventaire:
    print("❌ Aucun inventaire régularisé trouvé pour cette boutique.")
    print("Inventaires disponibles:")
    for inv in Inventaire.objects.filter(boutique=boutique):
        print(f"  - {inv.reference} | Statut: {inv.statut} | Date: {inv.date_inventaire} | Régularisé: {inv.date_regularisation}")
    exit()

print(f"✅ Inventaire: {inventaire.reference}")
print(f"   Date inventaire: {inventaire.date_inventaire}")
print(f"   Régularisé le: {inventaire.date_regularisation}")
print(f"   Nb articles saisis: {inventaire.lignes.count()}")
print()

# --- Récupérer les IDs des articles qui ONT été saisis dans l'inventaire ---
articles_saisis_ids = set(
    inventaire.lignes.values_list('article_id', flat=True)
)

# --- Trouver les articles NON saisis mais qui avaient du stock ---
# On regarde les articles actifs de la boutique qui ne sont PAS dans les lignes d'inventaire
articles_non_saisis = Article.objects.filter(
    boutique=boutique,
    est_actif=True
).exclude(
    id__in=articles_saisis_ids
).order_by('nom')

# Filtrer ceux qui ont du stock > 0 (actuel - pas modifié par la régularisation)
articles_avec_stock = articles_non_saisis.filter(quantite_stock__gt=0)

print("=" * 90)
print(f"📋 ARTICLES AVEC STOCK NON SAISIS À L'INVENTAIRE ({inventaire.reference})")
print(f"   Boutique: {boutique.nom}")
print(f"   Total articles non saisis avec stock > 0 : {articles_avec_stock.count()}")
print("=" * 90)
print()
print(f"{'#':<4} {'Nom':<35} {'Code':<15} {'Stock actuel':<12} {'Prix achat':<12} {'Valeur stock'}")
print("-" * 90)

total_valeur = 0
total_articles = 0

for i, art in enumerate(articles_avec_stock, 1):
    valeur = art.quantite_stock * float(art.prix_achat)
    total_valeur += valeur
    total_articles += 1
    print(f"{i:<4} {art.nom[:34]:<35} {art.code:<15} {art.quantite_stock:<12} {float(art.prix_achat):<12,.0f} {valeur:,.0f}")
    
    # Vérifier les variantes de cet article
    variantes = VarianteArticle.objects.filter(article_parent=art, est_actif=True)
    for var in variantes:
        if var.quantite_stock > 0:
            print(f"{'':4}  ↳ Variante: {var.nom_variante:<25} Code: {var.code_barre:<12} Stock: {var.quantite_stock}")

print("-" * 90)
print(f"TOTAL: {total_articles} articles | Valeur stock estimée: {total_valeur:,.0f} FC")
print()

# --- Aussi chercher les variantes non liées à un article parent saisi ---
print("=" * 90)
print(f"📋 VARIANTES avec stock propre (articles parent actifs de la boutique)")
print("=" * 90)
variantes_boutique = VarianteArticle.objects.filter(
    article_parent__boutique=boutique,
    article_parent__est_actif=True,
    est_actif=True,
    quantite_stock__gt=0
).exclude(
    article_parent_id__in=articles_saisis_ids
).select_related('article_parent').order_by('article_parent__nom', 'nom_variante')

if variantes_boutique.exists():
    print(f"\n{'#':<4} {'Article parent':<30} {'Variante':<20} {'Code-barre':<15} {'Stock variante'}")
    print("-" * 90)
    for i, var in enumerate(variantes_boutique, 1):
        print(f"{i:<4} {var.article_parent.nom[:29]:<30} {var.nom_variante[:19]:<20} {var.code_barre:<15} {var.quantite_stock}")
    print(f"\nTotal variantes non saisies avec stock: {variantes_boutique.count()}")
else:
    print("\nAucune variante avec stock propre trouvée parmi les articles non saisis.")

# --- Résumé complet (tous les articles non saisis, même stock = 0) ---
print()
print("=" * 90)
print(f"ℹ️  RÉSUMÉ COMPLET:")
print(f"   Articles totaux dans la boutique (actifs): {Article.objects.filter(boutique=boutique, est_actif=True).count()}")
print(f"   Articles saisis dans l'inventaire: {len(articles_saisis_ids)}")
print(f"   Articles NON saisis (total): {articles_non_saisis.count()}")
print(f"   Articles NON saisis AVEC stock > 0: {articles_avec_stock.count()}")
print(f"   Valeur totale du stock non inventorié: {total_valeur:,.0f} FC")
print("=" * 90)
