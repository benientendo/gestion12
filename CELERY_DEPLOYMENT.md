# 🚀 DÉPLOIEMENT CELERY - GUIDE COMPLET

## ✅ Ce qui a été fait

1. ✅ Celery installé (celery, flower, kombu)
2. ✅ `gestion_magazin/celery.py` créé (configuration)
3. ✅ `gestion_magazin/__init__.py` modifié (import Celery)
4. ✅ `settings.py` configuré (broker Redis, timezone, etc.)
5. ✅ `inventory/tasks.py` créé (tâches asynchrones)

---

## 📋 DÉMARRAGE RAPIDE

### Étape 1 : Vérifier que Redis fonctionne

```powershell
# Redis doit être démarré (voir WEBSOCKET_INSTALLATION.md)
python -c "import redis; r = redis.Redis(); print('Redis OK' if r.ping() else 'Redis KO')"
```

### Étape 2 : Démarrer les workers Celery

```powershell
cd c:\Users\PC\Documents\GestionMagazin

# Démarrer 4 workers en parallèle
celery -A gestion_magazin worker --loglevel=info --concurrency=4 --pool=solo
```

Vous devriez voir :
```
 -------------- celery@HOSTNAME v5.3.6
---- **** -----
--- * ***  * -- Windows-10.0.19041-SP0 2026-03-15 14:00:00
-- * - **** ---
- ** ---------- [config]
- ** ---------- .> app:         gestion_magazin:0x...
- ** ---------- .> transport:   redis://127.0.0.1:6379/0
- ** ---------- .> results:     redis://127.0.0.1:6379/0
- *** --- * --- .> concurrency: 4 (solo)
-- ******* ---- .> task events: OFF
--- ***** -----
 -------------- [queues]
                .> celery           exchange=celery(direct) key=celery

[tasks]
  . inventory.tasks.process_vente_async
  . inventory.tasks.process_multiple_ventes
  . inventory.tasks.cleanup_old_tasks
  . inventory.tasks.send_daily_report

[2026-03-15 14:00:00,000: INFO/MainProcess] Connected to redis://127.0.0.1:6379/0
[2026-03-15 14:00:00,000: INFO/MainProcess] celery@HOSTNAME ready.
```

### Étape 3 : Démarrer Flower (monitoring)

```powershell
# Dans un autre terminal
celery -A gestion_magazin flower --port=5555
```

Ouvrir dans le navigateur : **http://localhost:5555**

Vous verrez :
- Nombre de workers actifs
- Tâches en cours
- Tâches terminées
- Statistiques en temps réel

---

## 🔧 UTILISATION DANS LE CODE

### Modifier l'API sync_ventes pour utiliser Celery

Modifiez `inventory/api_views_v2_simple.py` :

```python
from inventory.tasks import process_vente_async

@api_view(['POST'])
@permission_classes([AllowAny])
def sync_ventes_simple(request):
    """
    Synchroniser les ventes - VERSION ASYNCHRONE avec Celery
    """
    ventes_data = request.data
    
    # Récupérer boutique et terminal
    boutique_id = request.GET.get('boutique_id')
    terminal_id = request.GET.get('terminal_id')
    
    # ... validation ...
    
    # ✨ NOUVEAU : Envoyer à la queue Celery au lieu de traiter directement
    accepted = []
    rejected = []
    
    for vente_data in ventes_data:
        try:
            # Lancer la tâche asynchrone
            task = process_vente_async.delay(
                vente_data, 
                boutique.id, 
                terminal.id
            )
            
            accepted.append({
                'vente_uid': vente_data.get('numero_facture'),
                'task_id': task.id,
                'status': 'queued'
            })
            
            logger.info(f"✅ Vente {vente_data.get('numero_facture')} mise en queue - Task {task.id}")
            
        except Exception as e:
            rejected.append({
                'vente_uid': vente_data.get('numero_facture'),
                'error': str(e)
            })
    
    return Response({
        'success': True,
        'message': f'{len(accepted)} ventes en cours de traitement',
        'accepted': accepted,
        'rejected': rejected,
        'processing_mode': 'async'
    })
```

---

## 📊 VÉRIFIER LE STATUT D'UNE TÂCHE

### Endpoint API pour vérifier le statut

Créez un nouveau endpoint dans `api_views_v2_simple.py` :

```python
from celery.result import AsyncResult

@api_view(['GET'])
@permission_classes([AllowAny])
def check_task_status(request, task_id):
    """
    Vérifier le statut d'une tâche Celery
    """
    task = AsyncResult(task_id)
    
    response_data = {
        'task_id': task_id,
        'status': task.status,  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
        'ready': task.ready(),
    }
    
    if task.ready():
        if task.successful():
            response_data['result'] = task.result
        else:
            response_data['error'] = str(task.info)
    
    return Response(response_data)
```

### Utilisation côté MAUI

```csharp
// Après avoir envoyé les ventes
var response = await SyncVentes(ventes);
var taskIds = response.Accepted.Select(a => a.TaskId).ToList();

// Vérifier le statut après 5 secondes
await Task.Delay(5000);

foreach (var taskId in taskIds)
{
    var status = await CheckTaskStatus(taskId);
    
    if (status.Status == "SUCCESS")
    {
        Debug.WriteLine($"✅ Vente traitée avec succès");
    }
    else if (status.Status == "FAILURE")
    {
        Debug.WriteLine($"❌ Erreur: {status.Error}");
    }
    else
    {
        Debug.WriteLine($"⏳ En cours de traitement...");
    }
}
```

---

## 🎯 COMPARAISON AVANT/APRÈS

### AVANT (Traitement synchrone)

```
POS envoie 50 ventes → Django traite 1 par 1 → 100 secondes
POS attend 100 secondes ⏳
Risque de timeout ❌
```

### APRÈS (Celery asynchrone)

```
POS envoie 50 ventes → Queue Redis → Réponse immédiate (0.5s) ✅
4 Workers Celery traitent en parallèle → 25 secondes
POS continue à fonctionner pendant le traitement ✅
Retry automatique en cas d'erreur ✅
```

---

## 🔄 TÂCHES PÉRIODIQUES (Celery Beat)

Pour exécuter des tâches automatiquement (rapports quotidiens, nettoyage, etc.) :

### Installation

```powershell
pip install django-celery-beat
```

### Configuration dans settings.py

```python
INSTALLED_APPS = [
    # ...
    'django_celery_beat',
]

# Tâches périodiques
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'rapport-quotidien': {
        'task': 'inventory.tasks.send_daily_report',
        'schedule': crontab(hour=18, minute=0),  # Tous les jours à 18h
        'args': (2,)  # boutique_id
    },
    'nettoyage-hebdomadaire': {
        'task': 'inventory.tasks.cleanup_old_tasks',
        'schedule': crontab(day_of_week=1, hour=2, minute=0),  # Lundi 2h
    },
}
```

### Démarrer le scheduler

```powershell
# Dans un 3ème terminal
celery -A gestion_magazin beat --loglevel=info
```

---

## 🛡️ PRODUCTION - SYSTEMD SERVICES

### Créer service worker

Créez `/etc/systemd/system/celery-worker.service` :

```ini
[Unit]
Description=Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/var/www/gestion_magazin
ExecStart=/var/www/gestion_magazin/venv/bin/celery -A gestion_magazin worker \
    --loglevel=info \
    --concurrency=4 \
    --pidfile=/var/run/celery/worker.pid \
    --logfile=/var/log/celery/worker.log
ExecStop=/var/www/gestion_magazin/venv/bin/celery -A gestion_magazin control shutdown
Restart=always

[Install]
WantedBy=multi-user.target
```

### Créer service beat

Créez `/etc/systemd/system/celery-beat.service` :

```ini
[Unit]
Description=Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/gestion_magazin
ExecStart=/var/www/gestion_magazin/venv/bin/celery -A gestion_magazin beat \
    --loglevel=info \
    --pidfile=/var/run/celery/beat.pid \
    --logfile=/var/log/celery/beat.log
Restart=always

[Install]
WantedBy=multi-user.target
```

### Activer et démarrer

```bash
sudo systemctl daemon-reload
sudo systemctl enable celery-worker celery-beat
sudo systemctl start celery-worker celery-beat

# Vérifier le statut
sudo systemctl status celery-worker
sudo systemctl status celery-beat
```

---

## 📈 MONITORING ET LOGS

### Voir les logs en temps réel

```powershell
# Logs workers
tail -f /var/log/celery/worker.log

# Logs beat
tail -f /var/log/celery/beat.log
```

### Flower - Dashboard web

Accéder à **http://serveur:5555** pour voir :
- Nombre de tâches par seconde
- Temps moyen de traitement
- Taux de succès/échec
- Workers actifs
- Graphiques en temps réel

---

## 🧪 TESTS

### Test 1 : Tâche simple

```python
# Dans Django shell
python manage.py shell

from inventory.tasks import process_vente_async

# Lancer une tâche de test
vente_data = {
    'numero_facture': 'TEST-001',
    'montant_total': 5000,
    'devise': 'CDF',
    'lignes': []
}

task = process_vente_async.delay(vente_data, 2, 1)
print(f"Task ID: {task.id}")

# Vérifier le résultat après quelques secondes
import time
time.sleep(5)
print(f"Status: {task.status}")
print(f"Result: {task.result}")
```

### Test 2 : Charge importante

```python
# Envoyer 100 ventes simultanément
from inventory.tasks import process_multiple_ventes

ventes = [
    {
        'numero_facture': f'TEST-{i}',
        'montant_total': 1000 * i,
        'devise': 'CDF',
        'lignes': []
    }
    for i in range(100)
]

result = process_multiple_ventes.delay(ventes, 2, 1)
print(f"100 ventes en queue - Task ID: {result.id}")
```

---

## ✅ RÉSUMÉ

**Celery est maintenant configuré et prêt !**

- ✅ Workers traitent les ventes en arrière-plan
- ✅ Retry automatique en cas d'erreur
- ✅ Monitoring avec Flower
- ✅ Tâches périodiques possibles
- ✅ Scalable (ajoutez plus de workers si besoin)

**Commandes essentielles** :
```powershell
# Démarrer workers
celery -A gestion_magazin worker --loglevel=info --concurrency=4 --pool=solo

# Démarrer monitoring
celery -A gestion_magazin flower --port=5555

# Démarrer scheduler (tâches périodiques)
celery -A gestion_magazin beat --loglevel=info
```

**Prochaine étape** : Intégrer dans vos vues Django existantes !
