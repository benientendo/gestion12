# ✅ CHECKLIST DE DÉPLOIEMENT - SYNCHRONISATION TEMPS RÉEL

## 📋 AVANT DE COMMENCER

### Prérequis installés

- [ ] Python 3.9+ installé
- [ ] Redis installé (Memurai pour Windows ou Docker)
- [ ] Packages Python installés :
  ```powershell
  pip install -r requirements_websocket.txt
  pip install -r requirements_celery.txt
  ```
- [ ] Migrations Django appliquées :
  ```powershell
  python manage.py makemigrations
  python manage.py migrate
  ```

---

## 🔧 CONFIGURATION

### Base de données

- [ ] Champs `last_updated` et `version` ajoutés aux modèles
- [ ] Migration créée et appliquée
- [ ] Données existantes migrées (version=1 par défaut)

### Settings.py

- [ ] `INSTALLED_APPS` contient `daphne` (en premier)
- [ ] `INSTALLED_APPS` contient `channels`
- [ ] `ASGI_APPLICATION` configuré
- [ ] `CHANNEL_LAYERS` configuré avec Redis
- [ ] `CELERY_BROKER_URL` configuré
- [ ] `CELERY_RESULT_BACKEND` configuré
- [ ] `CELERY_TIMEZONE` = 'Africa/Kinshasa'

### Fichiers créés

- [ ] `gestion_magazin/celery.py` existe
- [ ] `gestion_magazin/__init__.py` importe Celery
- [ ] `gestion_magazin/asgi.py` configuré pour WebSocket
- [ ] `inventory/consumers.py` créé
- [ ] `inventory/routing.py` créé
- [ ] `inventory/websocket_utils.py` créé
- [ ] `inventory/tasks.py` créé

---

## 🧪 TESTS LOCAUX

### Test 1 : Redis

```powershell
python -c "import redis; r = redis.Redis(); print('✅ Redis OK' if r.ping() else '❌ Redis KO')"
```

- [ ] Redis répond correctement

### Test 2 : WebSocket

```powershell
# Terminal 1 : Démarrer Daphne
daphne -b 0.0.0.0 -p 8000 gestion_magazin.asgi:application

# Terminal 2 : Tester la connexion
python scripts/test_websocket.py
```

- [ ] Connexion WebSocket établie
- [ ] Message `connection_established` reçu
- [ ] Ping/Pong fonctionne

### Test 3 : Celery

```powershell
# Terminal 1 : Démarrer workers
celery -A gestion_magazin worker --loglevel=info --concurrency=4 --pool=solo

# Terminal 2 : Django shell
python manage.py shell
>>> from inventory.tasks import process_vente_async
>>> task = process_vente_async.delay({'numero_facture': 'TEST-001', 'montant_total': 5000, 'devise': 'CDF', 'lignes': []}, 2, 1)
>>> print(task.id)
>>> import time; time.sleep(5)
>>> print(task.status)
>>> print(task.result)
```

- [ ] Tâche créée avec succès
- [ ] Tâche traitée par le worker
- [ ] Résultat accessible

### Test 4 : Flower

```powershell
celery -A gestion_magazin flower --port=5555
# Ouvrir http://localhost:5555
```

- [ ] Dashboard Flower accessible
- [ ] Workers visibles
- [ ] Tâches affichées

### Test 5 : Intégration complète

1. **Démarrer tous les services** :
   ```powershell
   .\scripts\start_all.ps1
   ```

2. **Connecter un client WebSocket** :
   ```powershell
   python scripts/test_websocket.py
   ```

3. **Modifier un article dans Django admin** :
   - [ ] WebSocket reçoit `article_updated`
   - [ ] Données correctes dans le message

4. **Envoyer une vente via API** :
   ```powershell
   curl -X POST http://localhost:8000/api/v2/simple/ventes/?boutique_id=2&terminal_id=1 \
     -H "Content-Type: application/json" \
     -d '[{"numero_facture":"TEST-002","montant_total":5000,"devise":"CDF","lignes":[]}]'
   ```
   - [ ] Réponse immédiate reçue
   - [ ] `task_id` présent dans la réponse
   - [ ] Tâche visible dans Flower
   - [ ] Vente créée en base après traitement

---

## 🚀 DÉPLOIEMENT PRODUCTION

### Serveur Linux (Ubuntu/Debian)

#### 1. Installation Redis

```bash
sudo apt update
sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

- [ ] Redis installé et démarré
- [ ] Redis écoute sur 127.0.0.1:6379

#### 2. Configuration Nginx

```nginx
# /etc/nginx/sites-available/gestion_magazin

upstream django {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name votre-domaine.com;

    # HTTP → HTTPS redirect
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name votre-domaine.com;

    ssl_certificate /etc/letsencrypt/live/votre-domaine.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/votre-domaine.com/privkey.pem;

    # WebSocket support
    location /ws/ {
        proxy_pass http://django;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    # API et pages Django
    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Fichiers statiques
    location /static/ {
        alias /var/www/gestion_magazin/staticfiles/;
    }

    location /media/ {
        alias /var/www/gestion_magazin/media/;
    }
}
```

- [ ] Configuration Nginx créée
- [ ] SSL configuré (Let's Encrypt)
- [ ] WebSocket proxy configuré

#### 3. Service Systemd - Daphne

```ini
# /etc/systemd/system/daphne.service

[Unit]
Description=Daphne ASGI Server
After=network.target redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/gestion_magazin
Environment="PATH=/var/www/gestion_magazin/venv/bin"
ExecStart=/var/www/gestion_magazin/venv/bin/daphne \
    -b 127.0.0.1 \
    -p 8000 \
    gestion_magazin.asgi:application
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

- [ ] Service créé
- [ ] Activé : `sudo systemctl enable daphne`
- [ ] Démarré : `sudo systemctl start daphne`
- [ ] Statut OK : `sudo systemctl status daphne`

#### 4. Service Systemd - Celery Worker

```ini
# /etc/systemd/system/celery-worker.service

[Unit]
Description=Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/var/www/gestion_magazin
Environment="PATH=/var/www/gestion_magazin/venv/bin"
ExecStart=/var/www/gestion_magazin/venv/bin/celery -A gestion_magazin worker \
    --loglevel=info \
    --concurrency=4 \
    --pidfile=/var/run/celery/worker.pid \
    --logfile=/var/log/celery/worker.log
ExecStop=/var/www/gestion_magazin/venv/bin/celery -A gestion_magazin control shutdown
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

- [ ] Dossiers créés : `sudo mkdir -p /var/run/celery /var/log/celery`
- [ ] Permissions : `sudo chown www-data:www-data /var/run/celery /var/log/celery`
- [ ] Service activé et démarré
- [ ] Logs visibles : `tail -f /var/log/celery/worker.log`

#### 5. Service Systemd - Celery Beat (optionnel)

```ini
# /etc/systemd/system/celery-beat.service

[Unit]
Description=Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/gestion_magazin
Environment="PATH=/var/www/gestion_magazin/venv/bin"
ExecStart=/var/www/gestion_magazin/venv/bin/celery -A gestion_magazin beat \
    --loglevel=info \
    --pidfile=/var/run/celery/beat.pid \
    --logfile=/var/log/celery/beat.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

- [ ] Service créé (si tâches périodiques nécessaires)
- [ ] Activé et démarré

#### 6. Flower (monitoring - optionnel)

```ini
# /etc/systemd/system/flower.service

[Unit]
Description=Flower Celery Monitoring
After=network.target redis.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/gestion_magazin
Environment="PATH=/var/www/gestion_magazin/venv/bin"
ExecStart=/var/www/gestion_magazin/venv/bin/celery -A gestion_magazin flower \
    --port=5555 \
    --basic_auth=admin:votre_mot_de_passe_securise
Restart=always

[Install]
WantedBy=multi-user.target
```

- [ ] Service créé
- [ ] Mot de passe sécurisé configuré
- [ ] Accessible via reverse proxy Nginx

---

## 🔒 SÉCURITÉ

### Configuration production

- [ ] `DEBUG = False` dans settings.py
- [ ] `SECRET_KEY` généré et sécurisé (variable d'environnement)
- [ ] `ALLOWED_HOSTS` configuré correctement
- [ ] HTTPS activé (certificat SSL)
- [ ] WebSocket sur WSS (wss://)
- [ ] Flower protégé par authentification
- [ ] Redis protégé (bind 127.0.0.1 uniquement)
- [ ] Firewall configuré (ports 80, 443 ouverts uniquement)

### Permissions fichiers

```bash
sudo chown -R www-data:www-data /var/www/gestion_magazin
sudo chmod -R 755 /var/www/gestion_magazin
sudo chmod 600 /var/www/gestion_magazin/.env
```

- [ ] Permissions correctes

---

## 📊 MONITORING

### Logs à surveiller

```bash
# Django/Daphne
sudo journalctl -u daphne -f

# Celery workers
tail -f /var/log/celery/worker.log

# Celery beat
tail -f /var/log/celery/beat.log

# Nginx
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log

# Redis
sudo journalctl -u redis -f
```

- [ ] Logs accessibles et surveillés

### Métriques à suivre

- [ ] Nombre de connexions WebSocket actives
- [ ] Nombre de tâches Celery en queue
- [ ] Temps moyen de traitement des tâches
- [ ] Taux d'erreur des tâches
- [ ] Utilisation mémoire Redis
- [ ] Latence WebSocket

---

## 🧪 TESTS POST-DÉPLOIEMENT

### Test 1 : WebSocket en production

```javascript
// Console navigateur
const ws = new WebSocket('wss://votre-domaine.com/ws/boutique/2/');
ws.onopen = () => console.log('✅ Connecté');
ws.onmessage = (e) => console.log('📥', JSON.parse(e.data));
```

- [ ] Connexion WSS établie
- [ ] Messages reçus correctement

### Test 2 : API ventes avec Celery

```bash
curl -X POST https://votre-domaine.com/api/v2/simple/ventes/?boutique_id=2&terminal_id=1 \
  -H "Content-Type: application/json" \
  -d '[{"numero_facture":"PROD-001","montant_total":5000,"devise":"CDF","lignes":[]}]'
```

- [ ] Réponse < 1 seconde
- [ ] `task_id` présent
- [ ] Vente traitée en arrière-plan

### Test 3 : Charge

```bash
# Envoyer 100 ventes simultanément
for i in {1..100}; do
  curl -X POST https://votre-domaine.com/api/v2/simple/ventes/?boutique_id=2&terminal_id=1 \
    -H "Content-Type: application/json" \
    -d "[{\"numero_facture\":\"LOAD-$i\",\"montant_total\":5000,\"devise\":\"CDF\",\"lignes\":[]}]" &
done
wait
```

- [ ] Toutes les requêtes répondent rapidement
- [ ] Aucun timeout
- [ ] Toutes les ventes traitées

---

## 📱 CLIENT MAUI

### Configuration

- [ ] `WebSocketService.cs` intégré dans le projet
- [ ] URL serveur configurée (wss:// en production)
- [ ] Numéro de série du terminal configuré
- [ ] Événements WebSocket connectés aux handlers
- [ ] Mise à jour SQLite local implémentée
- [ ] Reconnexion automatique testée

### Tests

- [ ] Connexion WebSocket établie au démarrage
- [ ] Mises à jour reçues en temps réel
- [ ] Reconnexion après perte de connexion
- [ ] Synchronisation incrémentale fonctionne
- [ ] Ventes envoyées avec réponse rapide

---

## 🎯 VALIDATION FINALE

### Scénario complet

1. **POS A** : Modifier un prix dans Django admin
   - [ ] **POS B, C, D** reçoivent la mise à jour < 1 seconde

2. **POS A** : Vendre un article
   - [ ] Réponse immédiate au POS
   - [ ] Stock mis à jour en base
   - [ ] **POS B, C, D** reçoivent la mise à jour de stock

3. **Django** : Ajouter un nouveau produit
   - [ ] Tous les POS reçoivent le nouveau produit
   - [ ] Notification affichée sur les POS

4. **Charge** : 50 ventes simultanées depuis 5 POS
   - [ ] Toutes les réponses < 1 seconde
   - [ ] Toutes les ventes traitées correctement
   - [ ] Aucune perte de données

---

## ✅ CHECKLIST FINALE

- [ ] Redis fonctionne et est sécurisé
- [ ] Daphne démarré et accessible
- [ ] Celery workers actifs (4 minimum)
- [ ] Flower accessible (si activé)
- [ ] WebSocket fonctionne (ws:// ou wss://)
- [ ] API ventes utilise Celery
- [ ] Notifications WebSocket intégrées dans les vues
- [ ] Client MAUI connecté et fonctionnel
- [ ] Tests de charge réussis
- [ ] Monitoring en place
- [ ] Logs configurés
- [ ] Sauvegardes Redis configurées
- [ ] Documentation à jour

---

## 🆘 EN CAS DE PROBLÈME

### Redis ne démarre pas
```bash
sudo systemctl status redis
sudo journalctl -u redis -n 50
```

### WebSocket ne se connecte pas
```bash
# Vérifier Daphne
sudo systemctl status daphne
# Vérifier Nginx
sudo nginx -t
sudo systemctl reload nginx
```

### Celery ne traite pas les tâches
```bash
# Vérifier workers
sudo systemctl status celery-worker
# Voir les logs
tail -f /var/log/celery/worker.log
# Redémarrer
sudo systemctl restart celery-worker
```

### Performances dégradées
```bash
# Vérifier Redis
redis-cli INFO stats
# Augmenter le nombre de workers
# Modifier concurrency dans celery-worker.service
```

---

## 📞 SUPPORT

- Documentation : Voir fichiers `*.md` dans le projet
- Logs : `/var/log/celery/` et `journalctl`
- Monitoring : Flower (http://localhost:5555)
- Tests : `scripts/test_websocket.py`

**Bon déploiement ! 🚀**
