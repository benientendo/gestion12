# 🔍 GUIDE DE DIAGNOSTIC - VENTES BACKEND DJANGO

## 🎯 Problème

**Symptôme:** MAUI dit "Synchronisation réussie" mais Django n'affiche aucune vente dans l'historique.

---

## ✅ Vérifications Préliminaires

### 1. Les ventes arrivent-elles à Django ?

```bash
cd C:\Users\PC\Documents\GestionMagazin
python verifier_ventes_backend.py
```

**Regardez la ligne:**
```
📊 Total ventes en base: X
```

- **Si X = 0** → Les ventes n'arrivent PAS à Django (voir Section A)
- **Si X > 0** → Les ventes arrivent mais ne s'affichent pas (voir Section B)

---

## 🔴 Section A: Ventes n'arrivent PAS à Django (Total = 0)

### Causes possibles:

#### 1. URL incorrecte côté MAUI
**Vérifier dans MAUI:**
```csharp
// Doit être:
POST http://192.168.X.X:8000/api/v2/simple/ventes/sync

// PAS:
POST http://192.168.X.X:8000/api/ventes/sync  // ❌ Ancienne API
```

#### 2. Header manquant
**Vérifier dans MAUI:**
```csharp
request.Headers.Add("X-Device-Serial", numeroSerie);
```

#### 3. Format JSON incorrect
**Format attendu par Django:**
```json
[
    {
        "numero_facture": "VENTE-001",
        "mode_paiement": "CASH",
        "paye": true,
        "lignes": [
            {
                "article_id": 6,
                "quantite": 1,
                "prix_unitaire": 40000
            }
        ]
    }
]
```

#### 4. Erreur HTTP non gérée
**Vérifier les logs Django:**
```bash
# Dans le terminal où Django tourne
# Chercher des erreurs 400, 404, 500
```

---

## 🟡 Section B: Ventes arrivent mais ne s'affichent pas

### Diagnostic: Ventes orphelines

**Exécuter:**
```bash
python verifier_ventes_backend.py
```

**Regarder:**
```
⚠️ VENTES ORPHELINES (sans boutique): X
```

### Si X > 0 → PROBLÈME TROUVÉ !

**Causes:**

#### 1. Terminal sans boutique associée

**Vérifier:**
```python
# Dans Django shell
python manage.py shell

from inventory.models import Client
terminal = Client.objects.get(numero_serie="VOTRE_NUMERO_SERIE")
print(terminal.boutique)  # Doit afficher une boutique, pas None
```

**Solution:**
```python
# Associer le terminal à une boutique
from inventory.models import Boutique
boutique = Boutique.objects.get(id=2)  # Remplacer 2 par l'ID correct
terminal.boutique = boutique
terminal.save()
```

#### 2. Code API ne lie pas boutique

**Vérifier dans `inventory/api_views_v2_simple.py` ligne ~1006:**
```python
vente = Vente.objects.create(
    numero_facture=numero_facture,
    montant_total=0,
    mode_paiement=vente_data.get('mode_paiement', 'CASH'),
    paye=vente_data.get('paye', True),
    boutique=boutique,  # ⚠️ CETTE LIGNE DOIT EXISTER
    client_maui=terminal,  # ⚠️ CETTE LIGNE DOIT EXISTER
    # ...
)
```

**Si ces lignes manquent:**
```python
# Les ajouter dans la fonction sync_ventes_simple()
boutique=boutique,
client_maui=terminal,
```

---

## 🔧 Correction Automatique

### Si ventes orphelines détectées:

```bash
python corriger_ventes_orphelines.py
```

**Ce script:**
1. Trouve toutes les ventes sans boutique
2. Récupère la boutique depuis le terminal associé
3. Lie automatiquement la vente à la boutique

**Après correction:**
```bash
python verifier_ventes_backend.py
```

Vérifier que `⚠️ VENTES ORPHELINES: 0`

---

## 🔍 Section C: Ventes dans la mauvaise boutique

### Symptôme
Les ventes apparaissent mais dans la mauvaise boutique.

### Diagnostic

**Exécuter:**
```bash
python verifier_ventes_backend.py
```

**Regarder la section:**
```
🔴 DERNIÈRES 10 VENTES
   🏪 Boutique: [Nom] (ID: X)
   📱 Terminal: [Nom] ([Numéro série])
```

**Vérifier que:**
- La boutique de la vente = La boutique du terminal

### Cause
Terminal associé à la mauvaise boutique.

### Solution

```python
# Django shell
python manage.py shell

from inventory.models import Client, Boutique

# Trouver le terminal
terminal = Client.objects.get(numero_serie="NUMERO_SERIE")

# Vérifier sa boutique actuelle
print(f"Boutique actuelle: {terminal.boutique}")

# Changer si nécessaire
bonne_boutique = Boutique.objects.get(id=CORRECT_ID)
terminal.boutique = bonne_boutique
terminal.save()

print(f"✅ Terminal associé à: {terminal.boutique.nom}")
```

---

## 📊 Vérification Finale

### Checklist complète:

```bash
# 1. Vérifier les ventes
python verifier_ventes_backend.py
```

**Résultats attendus:**
- ✅ Total ventes > 0
- ✅ Ventes orphelines = 0
- ✅ Ventes sans terminal = 0
- ✅ Chaque vente a une boutique
- ✅ Chaque vente a un terminal
- ✅ Boutique vente = Boutique terminal

### 2. Vérifier l'interface Django

**Accéder à:**
```
http://localhost:8000/commercant/dashboard/
```

**Vérifier:**
- Les ventes apparaissent dans l'historique
- Le chiffre d'affaires est correct
- Les ventes sont dans la bonne boutique

---

## 🐛 Problèmes Persistants

### Si après toutes les corrections, les ventes ne s'affichent toujours pas:

#### 1. Vérifier les filtres dans la vue Django

**Fichier:** `inventory/views_commercant.py`

**Chercher la fonction qui affiche l'historique:**
```python
def historique_ventes(request, boutique_id):
    boutique = request.boutique
    
    # ⚠️ VÉRIFIER CE FILTRE
    ventes = Vente.objects.filter(boutique=boutique)
    
    # Doit retourner les ventes de la boutique
    print(f"DEBUG: Ventes trouvées: {ventes.count()}")
```

#### 2. Vérifier les permissions

**Dans le template:**
```html
<!-- Vérifier que l'utilisateur a accès à la boutique -->
{% if request.user.is_authenticated %}
    <!-- Afficher les ventes -->
{% endif %}
```

#### 3. Activer le mode DEBUG

**Dans `gestion_magazin/settings.py`:**
```python
DEBUG = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}
```

**Relancer Django et observer les logs:**
```bash
python manage.py runserver
```

---

## 📞 Support

### Informations à fournir si problème persiste:

1. **Résultat complet de:**
   ```bash
   python verifier_ventes_backend.py
   ```

2. **Logs Django** (dernières 50 lignes du terminal)

3. **Réponse MAUI** lors de la synchronisation

4. **Version Django:**
   ```bash
   python manage.py --version
   ```

5. **Structure de la base de données:**
   ```bash
   python manage.py showmigrations inventory
   ```

---

## ✅ Résolution Typique

**Dans 90% des cas, le problème est:**

1. **Terminal sans boutique** → Associer le terminal à une boutique
2. **Ventes orphelines** → Exécuter `corriger_ventes_orphelines.py`
3. **Mauvaise URL API** → Utiliser `/api/v2/simple/ventes/sync`

**Temps de résolution:** 5-10 minutes

---

## 🎯 Prévention Future

### Configuration recommandée:

#### 1. Validation au démarrage MAUI
```csharp
// Vérifier que le terminal a une boutique
var response = await _httpClient.GetAsync("/api/v2/simple/status/");
var status = await response.Content.ReadFromJsonAsync<StatusResponse>();

if (status.Boutique == null)
{
    await DisplayAlert("Erreur", "Terminal non associé à une boutique", "OK");
    // Empêcher l'utilisation de l'app
}
```

#### 2. Logs détaillés MAUI
```csharp
// Logger toutes les synchronisations
Debug.WriteLine($"Sync ventes: {ventes.Count} ventes");
Debug.WriteLine($"URL: {url}");
Debug.WriteLine($"Header X-Device-Serial: {numeroSerie}");
Debug.WriteLine($"Response: {response.StatusCode}");
```

#### 3. Tests automatiques Django
```python
# tests/test_sync_ventes.py
def test_vente_a_boutique():
    """Vérifier que chaque vente créée a une boutique"""
    vente = Vente.objects.latest('id')
    assert vente.boutique is not None
    assert vente.client_maui is not None
```

---

**Dernière mise à jour:** 5 novembre 2024  
**Version:** 1.0
