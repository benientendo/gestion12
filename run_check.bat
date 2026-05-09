@echo off
echo from inventory.models import Article, Boutique > _tmp_check.py
echo depot = Boutique.objects.filter(nom__icontains='kiyambu').first() >> _tmp_check.py
echo if depot: >> _tmp_check.py
echo     print(f'Depot: {depot.nom} id={depot.id}') >> _tmp_check.py
echo     print(f'Articles actifs: {Article.objects.filter(boutique=depot, est_actif=True).count()}') >> _tmp_check.py
echo     print(f'Articles total: {Article.objects.filter(boutique=depot).count()}') >> _tmp_check.py
echo     print(f'Stock zero: {Article.objects.filter(boutique=depot, est_actif=True, quantite_stock=0).count()}') >> _tmp_check.py
echo else: >> _tmp_check.py
echo     print('KIYAMBU non trouve') >> _tmp_check.py
echo     for d in Boutique.objects.filter(est_depot=True): print(f'  {d.id}: {d.nom}') >> _tmp_check.py
scalingo --app gestionnumerique run python manage.py shell < _tmp_check.py
del _tmp_check.py
