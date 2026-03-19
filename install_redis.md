# 📥 INSTALLER REDIS POUR WINDOWS - SOLUTION SIMPLE

## Option 1 : Redis portable (Recommandé - 2 minutes)

1. **Télécharger** : https://github.com/tporadowski/redis/releases
   - Téléchargez `Redis-x64-5.0.14.1.zip`

2. **Extraire** dans `C:\Redis`

3. **Démarrer Redis** :
   ```powershell
   cd C:\Redis
   .\redis-server.exe
   ```

4. **Vérifier** (dans un autre terminal) :
   ```powershell
   cd c:\Users\PC\Documents\GestionMagazin
   python -c "import redis; r = redis.Redis(); print('OK' if r.ping() else 'KO')"
   ```

## Option 2 : Tester sans Redis (Mode développement)

Modifiez temporairement `settings.py` pour utiliser InMemoryChannelLayer :

```python
# Dans settings.py, remplacez CHANNEL_LAYERS par :
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
    }
}
```

⚠️ **Limitation** : Fonctionne seulement avec 1 serveur (pas de scaling)
✅ **Avantage** : Pas besoin de Redis pour tester
