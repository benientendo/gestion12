# 🚀 INSTALLATION WEBSOCKET - GUIDE RAPIDE

## ✅ Ce qui a été fait

1. ✅ Packages installés (channels, channels-redis, daphne, redis)
2. ✅ `consumers.py` créé (gestion WebSocket)
3. ✅ `routing.py` créé (routes WebSocket)
4. ✅ `asgi.py` modifié (support WebSocket)
5. ✅ `settings.py` modifié (configuration Channels)
6. ✅ `websocket_utils.py` créé (fonctions utilitaires)

---

## 📋 PROCHAINES ÉTAPES

### Étape 1 : Installer et démarrer Redis

#### Windows (Recommandé : Memurai)
```powershell
# Télécharger Memurai (Redis pour Windows)
# https://www.memurai.com/get-memurai

# Ou utiliser Docker
docker run -d -p 6379:6379 redis:latest

# Ou utiliser WSL2
wsl
sudo apt update
sudo apt install redis-server
sudo service redis-server start
```

#### Vérifier que Redis fonctionne
```powershell
# Tester la connexion
python -c "import redis; r = redis.Redis(host='localhost', port=6379); print('Redis OK' if r.ping() else 'Redis KO')"
```

---

### Étape 2 : Tester le serveur WebSocket

#### Démarrer avec Daphne (serveur ASGI)
```powershell
cd c:\Users\PC\Documents\GestionMagazin

# Démarrer le serveur
daphne -b 0.0.0.0 -p 8000 gestion_magazin.asgi:application
```

Vous devriez voir :
```
2026-03-15 02:30:00 INFO     Starting server at tcp:port=8000:interface=0.0.0.0
2026-03-15 02:30:00 INFO     HTTP/2 support enabled
2026-03-15 02:30:00 INFO     Configuring endpoint tcp:port=8000:interface=0.0.0.0
2026-03-15 02:30:00 INFO     Listening on TCP address 0.0.0.0:8000
```

---

### Étape 3 : Tester la connexion WebSocket

#### Test avec navigateur (JavaScript Console)
```javascript
// Ouvrir la console du navigateur (F12)
// Remplacer 2 par l'ID de votre boutique
const ws = new WebSocket('ws://192.168.52.224:8000/ws/boutique/2/');

ws.onopen = () => {
    console.log('✅ WebSocket connecté!');
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('📥 Message reçu:', data);
};

ws.onerror = (error) => {
    console.error('❌ Erreur WebSocket:', error);
};

// Envoyer un ping
ws.send(JSON.stringify({ type: 'ping' }));
```

Si vous voyez `✅ WebSocket connecté!`, c'est bon ! 🎉

---

### Étape 4 : Intégrer dans vos vues Django

#### Exemple : Notifier quand un prix change

Modifiez votre vue de modification d'article :

```python
# Dans inventory/views_commercant.py
from inventory.websocket_utils import notify_article_updated, notify_price_updated

def modifier_article_boutique(request, boutique_id, article_id):
    # ... votre code existant ...
    
    # Après avoir sauvegardé l'article
    article.save()
    
    # ✨ NOUVEAU : Notifier tous les POS en temps réel
    notify_article_updated(boutique_id, article)
    
    # Ou notification spécifique pour le prix
    if old_price != article.prix_vente:
        notify_price_updated(boutique_id, article.id, article.prix_vente, article.devise)
    
    messages.success(request, "Article modifié et POS notifiés!")
    return redirect('...')
```

---

## 🧪 TEST COMPLET

### Scénario de test

1. **Démarrer Redis** : `redis-server` ou Memurai
2. **Démarrer serveur** : `daphne -b 0.0.0.0 -p 8000 gestion_magazin.asgi:application`
3. **Ouvrir navigateur** : Console JavaScript
4. **Connecter WebSocket** : Code JavaScript ci-dessus
5. **Modifier un article** : Dans Django admin ou votre interface
6. **Vérifier** : Console JavaScript reçoit le message

---

## 🔧 DÉPANNAGE

### Problème : "Redis connection refused"
```
Solution : Redis n'est pas démarré
→ Démarrer Redis : redis-server (Linux/Mac) ou Memurai (Windows)
```

### Problème : "Module 'channels' not found"
```
Solution : Packages non installés
→ pip install -r requirements_websocket.txt
```

### Problème : "WebSocket connection failed"
```
Solution : Vérifier que Daphne écoute sur 0.0.0.0
→ daphne -b 0.0.0.0 -p 8000 gestion_magazin.asgi:application
```

### Problème : "Terminal non autorisé"
```
Solution : Le numéro de série du terminal n'existe pas dans la base
→ Créer un terminal dans Django admin avec ce numéro de série
→ Ou envoyer le header X-Device-Serial avec un numéro valide
```

---

## 📊 MONITORING

### Voir les connexions WebSocket actives

```python
# Dans Django shell
python manage.py shell

from channels.layers import get_channel_layer
channel_layer = get_channel_layer()

# Tester l'envoi manuel
from asgiref.sync import async_to_sync
async_to_sync(channel_layer.group_send)(
    'boutique_2',
    {
        'type': 'article_updated',
        'article': {'id': 123, 'nom': 'Test', 'prix_vente': '1000'}
    }
)
```

---

## 🚀 PROCHAINE ÉTAPE : CODE MAUI

Une fois que le backend WebSocket fonctionne, je vais créer :
- `WebSocketService.cs` pour MAUI
- Gestion de la reconnexion automatique
- Mise à jour SQLite local en temps réel

**Prêt pour le code MAUI ?**
