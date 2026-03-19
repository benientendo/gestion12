"""
Script de diagnostic pour vérifier l'état des stocks variants de la boutique 44 (KMC KIMPESE 01)

Ce script analyse :
1. Combien d'articles ont des variants
2. Quel est le stock sur les variants vs le stock sur le parent
3. Si les stocks ont déjà été transférés ou non

Usage:
    python manage.py shell < diagnostic_variants_boutique44.py
"""

from inventory.models import Article, VarianteArticle, Boutique
from django.db.models import Sum, Count

print("\n" + "="*80)
print("🔍 DIAGNOSTIC VARIANTS - BOUTIQUE 44 (KMC KIMPESE 01)")
print("="*80 + "\n")

# Récupérer la boutique
try:
    boutique = Boutique.objects.get(id=44)
    print(f"✅ Boutique trouvée : {boutique.nom} (ID: {boutique.id})")
except Boutique.DoesNotExist:
    print("❌ Boutique 44 introuvable !")
    exit()

print("\n" + "-"*80)
print("📊 ANALYSE DES ARTICLES AVEC VARIANTS")
print("-"*80 + "\n")

# Récupérer tous les articles de la boutique ayant des variants
articles_avec_variants = Article.objects.filter(
    boutique_id=44,
    variantes__isnull=False
).distinct().prefetch_related('variantes')

print(f"📦 Nombre d'articles avec variants : {articles_avec_variants.count()}\n")

if articles_avec_variants.count() == 0:
    print("✅ Aucun article avec variant dans cette boutique")
    exit()

# Analyser chaque article
total_stock_parents = 0
total_stock_variants = 0
articles_a_migrer = []

for article in articles_avec_variants:
    variants = article.variantes.filter(est_actif=True)
    
    if not variants.exists():
        continue
    
    stock_parent = article.quantite_stock
    somme_stock_variants = variants.aggregate(total=Sum('quantite_stock'))['total'] or 0
    stock_total = stock_parent + somme_stock_variants
    
    print(f"📦 {article.nom} (ID: {article.id})")
    print(f"   ├─ Stock parent : {stock_parent}")
    print(f"   ├─ Variants ({variants.count()}) :")
    
    for variant in variants:
        if variant.quantite_stock > 0:
            print(f"   │  ├─ {variant.nom_variante} (code: {variant.code_barre}): {variant.quantite_stock} unités")
    
    print(f"   ├─ Somme stocks variants : {somme_stock_variants}")
    print(f"   └─ STOCK TOTAL : {stock_total}")
    
    # Déterminer si migration nécessaire
    if somme_stock_variants > 0:
        print(f"   ⚠️  MIGRATION NÉCESSAIRE : {somme_stock_variants} unités à transférer au parent")
        articles_a_migrer.append({
            'article': article,
            'stock_a_transferer': somme_stock_variants,
            'variants': list(variants)
        })
    else:
        print(f"   ✅ Stock déjà sur le parent uniquement")
    
    print()
    
    total_stock_parents += stock_parent
    total_stock_variants += somme_stock_variants

print("\n" + "="*80)
print("📊 RÉSUMÉ GLOBAL")
print("="*80 + "\n")

print(f"Articles avec variants : {articles_avec_variants.count()}")
print(f"Stock total sur parents : {total_stock_parents} unités")
print(f"Stock total sur variants : {total_stock_variants} unités")
print(f"STOCK TOTAL RÉEL : {total_stock_parents + total_stock_variants} unités")

print("\n" + "-"*80)

if len(articles_a_migrer) > 0:
    print(f"⚠️  MIGRATION NÉCESSAIRE")
    print("-"*80 + "\n")
    print(f"Articles à migrer : {len(articles_a_migrer)}")
    print(f"Stock à transférer : {total_stock_variants} unités")
    print("\n💡 Commande à exécuter :")
    print("   python manage.py migrer_stocks_variants --boutique-id 44")
else:
    print(f"✅ AUCUNE MIGRATION NÉCESSAIRE")
    print("-"*80 + "\n")
    print("Les stocks sont déjà sur les parents uniquement.")
    print("Vous pouvez déployer la nouvelle version MAUI directement.")

print("\n" + "="*80 + "\n")
