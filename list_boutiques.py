from inventory.models import Boutique
for b in Boutique.objects.filter(est_active=True):
    print(f"{b.id}: {b.nom}")
