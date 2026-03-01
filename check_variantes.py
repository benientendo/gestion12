from inventory.models import Article, VarianteArticle

print("=== Variantes en production ===")
print(f"Total variantes: {VarianteArticle.objects.count()}")

for v in VarianteArticle.objects.all()[:10]:
    print(f"ID:{v.id} | {v.nom_variante} | code: {v.code_barre} | Parent: {v.article_parent.nom} | actif: {v.est_actif}")

print("\n=== Articles avec variantes ===")
for a in Article.objects.filter(variantes__isnull=False).distinct()[:10]:
    print(f"ID:{a.id} | {a.nom} | a_variantes: {a.a_variantes} | nb_variantes: {a.nb_variantes}")
