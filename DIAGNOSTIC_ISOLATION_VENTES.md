# 🔍 DIAGNOSTIC COMPLET - Isolation des Ventes

## ✅ VÉRIFICATIONS EFFECTUÉES

### 1. Modèle Django ✅
```python
class Vente(models.Model):
    boutique = models.ForeignKey('Boutique', ...)  # ✅ Champ ajouté
    client_maui = models.ForeignKey(Client, ...)
```

### 2. Migration Django ✅
```bash
✅ Migration 0006_vente_boutique créée et appliquée
✅ 14 ventes migrées avec succès
```

### 3. Endpoint Historique Django ✅
```python
# api_views_v2_simple.py - Ligne 622-624
ventes = Vente.objects.filter(
    boutique=boutique  # ✅ FILTRAGE DIRECT PAR BOUTIQUE
).select_related('client_maui', 'boutique')
```

### 4. Endpoint Création Vente Django ✅
```python
# api_views_v2_simple.py - Ligne 471
vente = Vente.objects.create(
    boutique=boutique,  # ✅ BOUTIQUE ASSIGNÉE
    client_maui=terminal,
    ...
)
```

### 5. Endpoint Synchronisation Django ✅
```python
# api_views_v2_simple.py - Ligne 996
vente = Vente.objects.create(
    boutique=boutique,  # ✅ BOUTIQUE ASSIGNÉE
    client_maui=terminal,
    ...
)
```

---

## 🎯 PROBLÈME IDENTIFIÉ

**Tout le code Django est correct !** Le problème peut venir de :

### Hypothèse 1 : Ventes Anciennes Sans Boutique
Les ventes créées **AVANT** la migration n'ont pas de `boutique` assignée.

**Vérification :**
```sql
SELECT COUNT(*) FROM inventory_vente WHERE boutique_id IS NULL;
```

**Solution :**
```bash
python migrer_ventes_boutiques.py
```

### Hypothèse 2 : MAUI Appelle le Mauvais Endpoint
MAUI pourrait appeler un ancien endpoint qui ne filtre pas.

**Endpoints disponibles :**
- ✅ `/api/v2/simple/ventes/historique/` - Filtre par boutique
- ❌ `/api/ventes/` - Ancien endpoint sans filtrage

**Vérification MAUI :**
Chercher dans `VenteApiService.cs` ou similaire :
```csharp
// ✅ BON
var response = await _httpClient.GetAsync("/api/v2/simple/ventes/historique/");

// ❌ MAUVAIS
var response = await _httpClient.GetAsync("/api/ventes/");
```

### Hypothèse 3 : Cache ou Données Locales MAUI
MAUI affiche peut-être des données en cache de la base SQLite locale.

**Vérification SQLite MAUI :**
```sql
SELECT Id, Reference, BoutiqueId, CodeBoutique 
FROM Vente 
ORDER BY Date DESC;
```

Si `BoutiqueId = 0` ou `NULL` → Les ventes locales n'ont pas de boutique

---

## 🧪 TESTS À EFFECTUER

### Test 1 : Vérifier Django Shell
```python
python manage.py shell

from inventory.models import Client, Vente

# Récupérer le terminal
terminal = Client.objects.get(numero_serie='0a1badae951f8473')
print(f"Terminal: {terminal.nom_terminal}")
print(f"Boutique: {terminal.boutique.nom} (ID: {terminal.boutique.id})")

# Vérifier les ventes de cette boutique
ventes_boutique = Vente.objects.filter(boutique=terminal.boutique)
print(f"\n✅ Ventes boutique {terminal.boutique.nom}: {ventes_boutique.count()}")

# Vérifier les ventes sans boutique
ventes_sans_boutique = Vente.objects.filter(boutique__isnull=True)
print(f"⚠️ Ventes sans boutique: {ventes_sans_boutique.count()}")

# Afficher quelques ventes
for v in ventes_boutique[:5]:
    print(f"  - {v.numero_facture}: Boutique {v.boutique.id if v.boutique else 'NULL'}")
```

### Test 2 : Tester l'API avec curl
```bash
# Test avec X-Device-Serial
curl -X GET "http://10.59.88.224:8000/api/v2/simple/ventes/historique/" \
  -H "X-Device-Serial: 0a1badae951f8473"

# Test avec boutique_id
curl -X GET "http://10.59.88.224:8000/api/v2/simple/ventes/historique/?boutique_id=2"
```

**Vérifier dans la réponse :**
- `boutique_id` doit être présent
- Toutes les ventes doivent avoir le même `boutique_id`

### Test 3 : Vérifier les Logs Django
```bash
# Redémarrer Django avec logs visibles
python manage.py runserver 10.59.88.224:8000

# Chercher ces messages :
🔍 Filtrage ventes par boutique ID: 2
✅ Boutique détectée pour historique: 2
```

### Test 4 : Créer une Nouvelle Vente et Vérifier
```bash
# 1. Créer une vente depuis MAUI
# 2. Synchroniser
# 3. Vérifier dans Django Shell :

from inventory.models import Vente
derniere_vente = Vente.objects.latest('date_vente')
print(f"Dernière vente: {derniere_vente.numero_facture}")
print(f"Boutique: {derniere_vente.boutique.nom if derniere_vente.boutique else 'NULL'}")
print(f"Boutique ID: {derniere_vente.boutique.id if derniere_vente.boutique else 'NULL'}")
```

---

## 🔧 SOLUTIONS SELON LE PROBLÈME

### Si : Ventes sans boutique dans la DB
```bash
cd C:\Users\PC\Documents\GestionMagazin
python migrer_ventes_boutiques.py
```

### Si : MAUI appelle le mauvais endpoint
**Modifier dans MAUI :**
```csharp
// Chercher et remplacer
"/api/ventes/" → "/api/v2/simple/ventes/historique/"
```

### Si : Cache SQLite MAUI
**Dans MAUI :**
1. Supprimer la base SQLite locale
2. Relancer l'app
3. Re-synchroniser

### Si : Ventes d'autres boutiques visibles
**Vérifier que le terminal est bien lié à UNE SEULE boutique :**
```python
python manage.py shell

from inventory.models import Client
terminal = Client.objects.get(numero_serie='0a1badae951f8473')
print(f"Boutique du terminal: {terminal.boutique.id}")
```

---

## 📋 CHECKLIST DE VALIDATION

- [ ] Django Shell : Ventes filtrées par boutique ✅
- [ ] curl : API retourne uniquement ventes de la boutique ✅
- [ ] Logs Django : Messages de filtrage visibles ✅
- [ ] Nouvelle vente : Créée avec `boutique` assignée ✅
- [ ] MAUI : Appelle le bon endpoint `/api/v2/simple/ventes/historique/`
- [ ] SQLite MAUI : Ventes ont `BoutiqueId` valide
- [ ] Pas de ventes sans boutique dans Django

---

## 🎯 PROCHAINE ÉTAPE

**Exécutez Test 1 (Django Shell)** pour voir exactement ce qui se passe dans la base de données :

```bash
cd C:\Users\PC\Documents\GestionMagazin
python manage.py shell
```

Puis copiez-collez ce code :
```python
from inventory.models import Client, Vente

terminal = Client.objects.get(numero_serie='0a1badae951f8473')
print(f"Terminal: {terminal.nom_terminal}, Boutique: {terminal.boutique.nom} (ID: {terminal.boutique.id})")

ventes_boutique = Vente.objects.filter(boutique=terminal.boutique)
ventes_sans_boutique = Vente.objects.filter(boutique__isnull=True)

print(f"\n✅ Ventes avec boutique {terminal.boutique.id}: {ventes_boutique.count()}")
print(f"⚠️ Ventes sans boutique: {ventes_sans_boutique.count()}")

print("\n📊 Dernières ventes :")
for v in Vente.objects.all().order_by('-date_vente')[:10]:
    boutique_info = f"Boutique {v.boutique.id}" if v.boutique else "SANS BOUTIQUE"
    print(f"  - {v.numero_facture}: {boutique_info}")
```

**Partagez-moi le résultat !** 🔍
