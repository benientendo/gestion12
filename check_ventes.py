import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Vente, Boutique
from django.utils import timezone
from datetime import datetime
import pytz

boutique = Boutique.objects.filter(nom='KMC KIMPESE 01').first()

# Corriger les 2 ventes - utiliser la date reelle du UID
corrections = [
    {
        'numero_facture': '-DT6213K-20260304174449860-19f76e28',
        'date_correcte': datetime(2026, 3, 4, 17, 44, 49, tzinfo=pytz.UTC)
    },
    {
        'numero_facture': '-DT6213K-20260304182805450-f446bc5c',
        'date_correcte': datetime(2026, 3, 4, 18, 28, 5, tzinfo=pytz.UTC)
    },
]

for corr in corrections:
    vente = Vente.objects.filter(numero_facture=corr['numero_facture']).first()
    if vente:
        ancienne_date = vente.date_vente
        vente.date_vente = corr['date_correcte']
        vente.save()
        print(f"Corrige: {corr['numero_facture'][:30]}")
        print(f"  Avant: {ancienne_date}")
        print(f"  Apres: {vente.date_vente}")
    else:
        print(f"Vente non trouvee: {corr['numero_facture']}")

print("\nVerification finale:")
from django.utils import timezone as tz
today = tz.now().date()
import datetime as dt
yesterday = today - dt.timedelta(days=1)

v_hier = Vente.objects.filter(boutique=boutique, date_vente__date=yesterday)
v_auj = Vente.objects.filter(boutique=boutique, date_vente__date=today)
print(f"KMC KIMPESE 01 - Ventes hier (4 mars): {v_hier.count()} = {sum(v.montant_total for v in v_hier)} CDF")
print(f"KMC KIMPESE 01 - Ventes aujourd'hui (5 mars): {v_auj.count()} = {sum(v.montant_total for v in v_auj)} CDF")




