"""
Configuration Celery pour gestion_magazin
Permet le traitement asynchrone des tâches (ventes, synchronisation, etc.)
"""
import os
from celery import Celery

# Définir le module de settings Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')

# Créer l'application Celery
app = Celery('gestion_magazin')

# Charger la configuration depuis Django settings
# namespace='CELERY' signifie que toutes les configs Celery doivent avoir le préfixe CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-découvrir les tâches dans tous les fichiers tasks.py des apps Django
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Tâche de debug pour tester Celery"""
    print(f'Request: {self.request!r}')
