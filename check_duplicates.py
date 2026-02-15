#!/usr/bin/env python
# Script pour detecter les articles avec quantites doublees - KMC LUKALA (ID 44)

from inventory.models import Article, Boutique, MouvementStock
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta

boutique_id = 44
print("=== ANALYSE KMC LUKALA (ID 44) ===")

# 1. Articles avec plusieurs validations
print("\n1. ARTICLES AVEC PLUSIEURS VALIDATIONS:")
multi = MouvementStock.objects.filter(
    article__boutique_id=boutique_id,
    reference_document__startswith="VALIDATION-"
).values("article__id", "article__nom", "article__code", "article__quantite_stock").annotate(
    nb=Count("id"), total=Sum("quantite")
).filter(nb__gt=1).order_by("-nb")

for a in multi[:15]:
    print(f"  {a['article__nom'][:35]} | {a['nb']} valid. | +{a['total']} | stock={a['article__quantite_stock']}")

# 2. Mouvements recents de validation
print("\n2. VALIDATIONS RECENTES (7 jours):")
recent = MouvementStock.objects.filter(
    article__boutique_id=boutique_id,
    reference_document__startswith="VALIDATION-",
    date_mouvement__gte=timezone.now() - timedelta(days=7)
).select_related("article").order_by("-date_mouvement")[:20]

for mv in recent:
    print(f"  {mv.date_mouvement.strftime('%m-%d %H:%M')} | {mv.article.nom[:30]} | +{mv.quantite} | stock={mv.article.quantite_stock}")

# 3. Articles ou stock = 2x derniere validation
print("\n3. STOCK POSSIBLEMENT DOUBLE:")
for mv in recent:
    if mv.quantite > 0 and mv.article.quantite_stock == mv.quantite * 2:
        print(f"  !! {mv.article.nom} | valid={mv.quantite} | stock={mv.article.quantite_stock}")

# 4. Verifier si validation cote MAUI aussi ajoute stock
print("\n4. ARTICLES EN ATTENTE VALIDATION:")
pending = Article.objects.filter(boutique_id=boutique_id, est_valide_client=False, est_actif=True)
for a in pending[:10]:
    print(f"  {a.nom[:35]} | envoyee={a.quantite_envoyee} | stock={a.quantite_stock}")

print("\n=== FIN ===")
