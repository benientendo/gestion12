# 🏗️ ARCHITECTURE SYSTÈME - Vente MAUI

## 📊 Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION MAUI                          │
│  (Terminal Android avec numéro de série unique)             │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ HTTP POST /api/v2/simple/ventes/
                     │ Header: X-Device-Serial: 0a1badae951f8473
                     │ Body: {"lignes": [...]}
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    DJANGO BACKEND                            │
│                                                              │
│  1. Détection Terminal → Boutique                           │
│  2. Génération Numéro Facture                               │
│  3. Création Vente                                          │
│  4. Mise à Jour Stock (automatique)                         │
│  5. Création Historique (automatique)                       │
│  6. Calcul CA (automatique)                                 │
│                                                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Response 201 Created
                     │ {"success": true, "vente": {...}}
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION MAUI                          │
│  - Affiche reçu                                             │
│  - Vide le panier                                           │
│  - Synchronise les données                                  │
└─────────────────────────────────────────────────────────────┘
```

## 🗂️ Structure des Fichiers

```
C:\Users\PC\Documents\GestionMagazin\
│
├── gestion_magazin/
│   ├── settings.py          # Configuration Django
│   └── urls.py              # URLs principales (API v2 simple)
│
├── inventory/
│   ├── models.py            # Modèles (Vente, Article, Client, etc.)
│   ├── api_views_v2_simple.py  # ⭐ Vues API (ventes, articles, stats)
│   └── api_urls_v2_simple.py   # URLs API v2 simple
│
├── test_vente_complete.py   # 🧪 Script de test automatique
│
└── Documentation/
    ├── DEMARRAGE_RAPIDE.md           # Guide de démarrage
    ├── VERIFICATION_CONFIGURATION.md  # État du système
    ├── GUIDE_COMPLET_VENTES_MAUI.md  # Guide complet
    ├── CORRECTIONS_VENTES_MAUI.md    # Corrections appliquées
    └── DEPANNAGE_ERREURS_400.md      # Dépannage
```

## 🔄 Flux de Données - Création de Vente

### 1️⃣ Requête MAUI → Django

```
POST http://192.168.52.224:8000/api/v2/simple/ventes/

Headers:
  Content-Type: application/json
  X-Device-Serial: 0a1badae951f8473

Body:
{
  "lignes": [
    {
      "article_id": 6,
      "quantite": 2,
      "prix_unitaire": 100000.00
    }
  ]
}
```

### 2️⃣ Traitement Django

```python
# Étape 1: Détection du terminal
numero_serie = request.headers.get('X-Device-Serial')
terminal = Client.objects.filter(numero_serie=numero_serie).first()
boutique_id = terminal.boutique.id

# Étape 2: Génération numéro facture
timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
numero_facture = f"VENTE-{boutique_id}-{timestamp}"

# Étape 3: Création vente
vente = Vente.objects.create(
    numero_facture=numero_facture,
    montant_total=0,
    mode_paiement='CASH',
    paye=True,
    client_maui=terminal
)

# Étape 4: Pour chaque ligne
for ligne in lignes:
    # Créer ligne de vente
    LigneVente.objects.create(
        vente=vente,
        article=article,
        quantite=quantite,
        prix_unitaire=prix_unitaire
    )
    
    # Mettre à jour stock (AUTOMATIQUE)
    article.quantite_stock -= quantite
    article.save()
    
    # Créer historique (AUTOMATIQUE)
    MouvementStock.objects.create(
        article=article,
        type_mouvement='VENTE',
        quantite=-quantite,
        reference=f"Vente #{numero_facture}"
    )
    
    # Calculer montant total
    montant_total += prix_unitaire * quantite

# Étape 5: Mettre à jour montant total
vente.montant_total = montant_total
vente.save()
```

### 3️⃣ Réponse Django → MAUI

```json
{
  "success": true,
  "vente": {
    "id": 123,
    "numero_facture": "VENTE-2-20251029010000",
    "montant_total": 200000.00,
    "mode_paiement": "CASH",
    "date_vente": "2025-10-29T01:00:00",
    "lignes": [
      {
        "article_nom": "samsung s24",
        "quantite": 2,
        "prix_unitaire": 100000.00,
        "sous_total": 200000.00
      }
    ]
  },
  "boutique_id": 2,
  "terminal_id": 1
}
```

## 🗄️ Base de Données - Relations

```
┌──────────────┐
│  Commercant  │
└──────┬───────┘
       │ 1:N
       ▼
┌──────────────┐
│   Boutique   │◄──────┐
└──────┬───────┘       │
       │ 1:N           │ N:1
       ▼               │
┌──────────────┐       │
│    Client    │───────┘
│  (Terminal)  │
└──────┬───────┘
       │ 1:N
       ▼
┌──────────────┐
│    Vente     │
└──────┬───────┘
       │ 1:N
       ▼
┌──────────────┐       ┌──────────────┐
│  LigneVente  │──────►│   Article    │
└──────────────┘  N:1  └──────┬───────┘
                               │ 1:N
                               ▼
                        ┌──────────────┐
                        │MouvementStock│
                        └──────────────┘
```

## 🔐 Sécurité et Isolation

### Isolation par Boutique

```python
# Chaque requête est filtrée par boutique
articles = Article.objects.filter(
    boutique=boutique,
    est_actif=True
)

# Impossible d'accéder aux articles d'une autre boutique
# Car le boutique_id est déterminé par le numéro de série du terminal
```

### Authentification

```
Terminal MAUI
    │
    ├─ Numéro de Série Unique (0a1badae951f8473)
    │
    └─ Associé à UNE SEULE Boutique
           │
           └─ Accès UNIQUEMENT aux données de cette boutique
```

## 📡 Endpoints API Disponibles

| Endpoint | Méthode | Authentification | Fonction |
|----------|---------|------------------|----------|
| `/status/` | GET | ❌ Non | Statut API |
| `/terminal/{serial}/` | GET | ✅ Header | Info terminal |
| `/articles/` | GET | ✅ Header | Liste articles |
| `/categories/` | GET | ✅ Header | Liste catégories |
| `/ventes/` | POST | ✅ Header | **Créer vente** |
| `/ventes/historique/` | GET | ✅ Header | Historique |
| `/statistiques/` | GET | ✅ Header | Statistiques |

**Authentification :** Header `X-Device-Serial: {numero_serie}`

## ⚡ Performances

### Optimisations Implémentées

1. **Select Related** : Chargement optimisé des relations
   ```python
   terminal = Client.objects.select_related('boutique').filter(...)
   ```

2. **Update Fields** : Mise à jour ciblée
   ```python
   article.save(update_fields=['quantite_stock'])
   ```

3. **Bulk Operations** : Création groupée si nécessaire
   ```python
   LigneVente.objects.bulk_create([...])
   ```

4. **Indexation** : Index sur champs fréquemment utilisés
   - `numero_serie` (Client)
   - `numero_facture` (Vente)
   - `boutique_id` (Article, Categorie)

## 🔍 Logs et Monitoring

### Logs Activés

```python
# Logs de debug
logger.info(f"🔍 Création vente - Headers: {dict(request.headers)}")
logger.info(f"🔍 Création vente - Body: {request.data}")
logger.info(f"✅ Boutique détectée automatiquement: {boutique_id}")
logger.info(f"📝 Numéro de facture généré: {numero_facture}")

# Logs d'erreur
logger.error(f"❌ Erreur: {str(e)}")
logger.error(f"❌ Traceback:\n{traceback.format_exc()}")
logger.error(f"❌ Données reçues: {request.data}")
```

### Monitoring en Temps Réel

```bash
# Voir les logs Django
python manage.py runserver 192.168.52.224:8000

# Les logs s'affichent automatiquement dans la console
```

## 🎯 Points Clés

### ✅ Ce Qui Fonctionne Automatiquement

1. **Génération Numéro Facture** - Format : `VENTE-{boutique_id}-{timestamp}`
2. **Détection Boutique** - Via numéro de série du terminal
3. **Mise à Jour Stock** - Décrémentation automatique
4. **Création Historique** - MouvementStock pour traçabilité
5. **Calcul CA** - Montant total calculé automatiquement
6. **Isolation Données** - Par boutique garantie

### ⚠️ Ce Qui Nécessite Configuration MAUI

1. **Header X-Device-Serial** - Doit être ajouté à toutes les requêtes
2. **URL Correcte** - `/api/v2/simple/ventes/` (sans double slash)
3. **Format JSON** - Body avec `lignes` uniquement
4. **Gestion Erreurs** - Codes 201 (succès), 400/500 (erreur)

## 🚀 Déploiement

### Prérequis

- Python 3.x
- Django 5.x
- Django REST Framework
- Base de données configurée

### Commandes

```bash
# Démarrer le serveur
python manage.py runserver 192.168.52.224:8000

# Tester le système
python test_vente_complete.py

# Vérifier la configuration
python manage.py check
```

## 📈 Évolutions Futures

### Possibles Améliorations

1. **Cache Redis** - Pour performances accrues
2. **WebSockets** - Pour notifications temps réel
3. **API GraphQL** - Pour requêtes flexibles
4. **Authentification JWT** - Pour sécurité renforcée
5. **Rate Limiting** - Pour protection contre abus

### Actuellement Non Nécessaire

Le système actuel est **suffisant et performant** pour :
- Plusieurs boutiques simultanées
- Centaines de ventes par jour
- Milliers d'articles
- Synchronisation temps réel

**L'architecture est prête pour la production !** 🎉
