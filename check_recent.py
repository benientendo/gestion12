import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Article
from django.utils import timezone
from datetime import timedelta

recent = Article.objects.filter(date_creation__gte=timezone.now()-timedelta(hours=2)).order_by('-date_creation')[:10]
print("Articles créés dans les 2 dernières heures:")
for a in recent:
    print(f"  ID:{a.id} | {a.nom} | Boutique:{a.boutique.nom} | est_valide_client={a.est_valide_client}")

pending = Article.objects.filter(est_valide_client=False)
print(f"\nTotal articles avec est_valide_client=False: {pending.count()}")
for a in pending[:5]:
    print(f"  ID:{a.id} | {a.nom} | Boutique:{a.boutique.nom}")
