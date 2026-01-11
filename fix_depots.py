import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Commercant, Boutique

for c in Commercant.objects.all():
    if not c.boutiques.filter(est_depot=True).exists():
        Boutique.objects.create(
            nom='Depot Central - ' + c.nom_entreprise,
            commercant=c,
            type_commerce='DEPOT',
            est_depot=True,
            est_active=True
        )
        print('Depot cree pour ' + c.nom_entreprise)
    else:
        print(c.nom_entreprise + ' a deja un depot')

print('Termine')
