import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GestionMagazin.settings')
django.setup()

from inventory.models import JournalValeurStock, Article
from decimal import Decimal

entries = JournalValeurStock.objects.all()
count = 0

for e in entries:
    arts = Article.objects.filter(
        boutique=e.boutique, est_actif=True,
        quantite_stock__gt=0, devise='CDF'
    )
    total = Decimal('0')
    for a in arts:
        total += Decimal(str(a.quantite_stock)) * Decimal(str(a.prix_vente))
    e.valeur_stock_reel = total
    e.save(update_fields=['valeur_stock_reel'])
    count += 1

print(f"Recalcule {count} entrees du journal avec prix_vente (CDF)")
