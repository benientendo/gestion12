import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Boutique, Article

b = Boutique.objects.get(nom__iexact='LUKALA 01')
arts = Article.objects.filter(boutique=b, est_actif=True, quantite_stock__gt=0)

print(f"Total articles avec stock > 0 : {arts.count()}")
print("\nEchantillon (10 premiers) :")
print(f"{'Nom':<40} {'Qte':>6} {'P.Achat':>10} {'P.Vente':>10} {'Devise':>6}")
print("-" * 75)
for a in arts.order_by('-quantite_stock')[:10]:
    print(f"{a.nom[:39]:<40} {a.quantite_stock:>6} {float(a.prix_achat or 0):>10,.0f} {float(a.prix_vente or 0):>10,.0f} {a.devise:>6}")

# Compter ceux avec prix_achat > 0
avec_pa = arts.filter(prix_achat__gt=0).count()
avec_pv = arts.filter(prix_vente__gt=0).count()
print(f"\nArticles avec prix_achat > 0 : {avec_pa}")
print(f"Articles avec prix_vente > 0 : {avec_pv}")
