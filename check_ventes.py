import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Vente, VenteRejetee, Boutique
from django.utils import timezone
from decimal import Decimal

today = timezone.now().date()
boutique = Boutique.objects.filter(nom='KMC KIMPESE 01').first()

print(f"=== KMC KIMPESE 01 - {today} ===")

# Rejets non traites aujourd'hui
rejets = VenteRejetee.objects.filter(boutique=boutique, date_tentative__date=today, traitee=False)
print(f"\nRejets NON traites aujourd'hui: {rejets.count()}")

# Toutes les ventes aujourd'hui
ventes = Vente.objects.filter(boutique=boutique, date_vente__date=today)
total = sum([v.montant_total for v in ventes])
print(f"Ventes enregistrees aujourd'hui: {ventes.count()}")
print(f"Total recette aujourd'hui: {total} CDF")

# Detail des ventes
print("\nDetail ventes:")
for v in ventes.order_by('date_vente'):
    print(f"  {v.date_vente.strftime('%H:%M')} | {v.numero_facture[:30]} | {v.montant_total} CDF")



