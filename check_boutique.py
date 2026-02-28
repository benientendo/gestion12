import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()
from inventory.models import Boutique, Stock
from django.utils import timezone
b = Boutique.objects.get(id=44)
print("Nom:", b.nom)
print("Commercant:", b.commercant.nom_entreprise)
stocks = Stock.objects.filter(boutique_id=44)
print("Nombre articles:", stocks.count())
updated = stocks.update(quantite=0, prix_vente=0, date_mise_a_jour=timezone.now())
print(updated, "articles reinitialises avec succes")
