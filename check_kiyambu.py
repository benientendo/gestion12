import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()
from inventory.models import Article, Boutique
depot = Boutique.objects.filter(nom__icontains='kiyambu').first()
if depot:
    total = Article.objects.filter(boutique=depot).count()
    actifs = Article.objects.filter(boutique=depot, est_actif=True).count()
    stock_zero = Article.objects.filter(boutique=depot, est_actif=True, quantite_stock=0).count()
    print(f"Depot: {depot.nom} (id={depot.id})")
    print(f"Articles total: {total}")
    print(f"Articles actifs: {actifs}")
    print(f"Articles stock=0: {stock_zero}")
else:
    depots = Boutique.objects.filter(est_depot=True).values_list('id', 'nom')
    print("Depot KIYAMBU non trouve. Depots existants:")
    for d in depots:
        print(f"  id={d[0]} nom={d[1]}")
