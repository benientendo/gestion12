import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Article
from django.utils import timezone

# Articles en attente de validation SANS quantite a valider
a_corriger = Article.objects.filter(est_valide_client=False, quantite_envoyee=0, est_actif=True)
nb = a_corriger.count()
print(f'Articles a corriger: {nb}')
for a in a_corriger[:30]:
    print(f'  - {a.nom} | boutique={a.boutique.nom if a.boutique else "?"} | stock={a.quantite_stock}')
if nb > 30:
    print(f'  ... et {nb - 30} autres')

# Correction bulk
updated = a_corriger.update(est_valide_client=True, date_validation=timezone.now())
print(f'\nCorrige: {updated} articles passes a est_valide_client=True')
