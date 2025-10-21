# 🚀 Guide de Déploiement - Architecture Multi-Commerçants

## 📋 Vue d'ensemble

Ce guide vous accompagne dans la migration de votre application Django mono-utilisateur vers une architecture multi-commerçants avec gestion de boutiques multiples.

## 🏗️ Architecture Finale

```
Super Admin (Django Admin)
    ↓
Commerçant (Entreprise/Personne)
    ↓
Boutique (Pharmacie, Bar, Alimentation, etc.)
    ↓
Terminal MAUI (Application mobile)
```

## 📂 Fichiers Créés

### Nouveaux Modèles
- `inventory/models_multi_commercants.py` - Nouveaux modèles (Commercant, Boutique, TerminalMaui)
- `inventory/models_modifications.py` - Modèles existants modifiés

### Interface et API
- `inventory/admin_multi_commercants.py` - Administration Django
- `inventory/views_commercant.py` - Vues pour l'interface commerçant
- `inventory/api_views_multi_boutiques.py` - API adaptée multi-boutiques

### Migration et Documentation
- `migration_multi_commercants.py` - Script de migration
- `guide_migration_maui.md` - Guide pour adapter MAUI

## 🔧 Étapes de Déploiement

### Phase 1: Préparation Django

#### 1.1 Sauvegarde
```bash
# Sauvegarder la base de données
cp db.sqlite3 db_backup_$(date +%Y%m%d).sqlite3

# Sauvegarder les fichiers
python migration_multi_commercants.py
```

#### 1.2 Intégration des nouveaux modèles
```bash
# Remplacer le fichier models.py existant
cp inventory/models_multi_commercants.py inventory/models.py

# Ou intégrer manuellement les nouveaux modèles
```

#### 1.3 Migrations Django
```bash
python manage.py makemigrations inventory
python manage.py migrate
```

### Phase 2: Configuration Initiale

#### 2.1 Créer un Super Admin
```bash
python manage.py createsuperuser
```

#### 2.2 Créer un Commerçant de Test
```python
# Dans le shell Django (python manage.py shell)
from django.contrib.auth.models import User
from inventory.models import Commercant, Boutique, TerminalMaui

# Créer un utilisateur commerçant
user = User.objects.create_user(
    username='commercant_test',
    email='test@exemple.com',
    password='motdepasse123'
)

# Créer le profil commerçant
commercant = Commercant.objects.create(
    nom_entreprise='Pharmacie Test',
    nom_responsable='Jean Dupont',
    email='test@exemple.com',
    telephone='+243123456789',
    utilisateur=user,
    type_abonnement='STANDARD',
    limite_boutiques=3
)

# Créer une boutique
boutique = Boutique.objects.create(
    nom='Pharmacie Centrale',
    commercant=commercant,
    type_commerce='PHARMACIE',
    adresse='123 Avenue de la Paix, Kinshasa'
)

# Créer un terminal MAUI
terminal = TerminalMaui.objects.create(
    nom_terminal='Caisse Principale',
    boutique=boutique,
    numero_serie='PHAR001',
    nom_utilisateur='Caissier 1'
)

print(f"Boutique créée: {boutique.code_boutique}")
print(f"Terminal créé: {terminal.numero_serie}")
print(f"Clé API: {terminal.cle_api}")
```

### Phase 3: Migration des Données Existantes

#### 3.1 Script de Migration des Articles
```python
# migration_articles.py
from inventory.models import Article, Boutique

def migrer_articles_vers_boutique():
    """Migre les articles existants vers la première boutique"""
    
    boutique = Boutique.objects.first()
    if not boutique:
        print("Aucune boutique trouvée. Créez d'abord une boutique.")
        return
    
    articles_sans_boutique = Article.objects.filter(boutique__isnull=True)
    count = 0
    
    for article in articles_sans_boutique:
        article.boutique = boutique
        article.save()
        count += 1
    
    print(f"{count} articles migrés vers la boutique '{boutique.nom}'")

if __name__ == "__main__":
    migrer_articles_vers_boutique()
```

#### 3.2 Script de Migration des Ventes
```python
# migration_ventes.py
from inventory.models import Vente, TerminalMaui

def migrer_ventes_vers_terminal():
    """Migre les ventes existantes vers le premier terminal"""
    
    terminal = TerminalMaui.objects.first()
    if not terminal:
        print("Aucun terminal trouvé. Créez d'abord un terminal.")
        return
    
    ventes_sans_terminal = Vente.objects.filter(terminal_maui__isnull=True)
    count = 0
    
    for vente in ventes_sans_terminal:
        vente.terminal_maui = terminal
        vente.boutique = terminal.boutique
        vente.save()
        count += 1
    
    print(f"{count} ventes migrées vers le terminal '{terminal.nom_terminal}'")

if __name__ == "__main__":
    migrer_ventes_vers_terminal()
```

### Phase 4: Configuration de l'Interface

#### 4.1 URLs Django
```python
# gestion_magazin/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('inventory.api_urls')),
    path('commercant/', include('inventory.urls_commercant')),  # Nouvelle interface
    path('', include('inventory.urls')),  # Interface existante
]
```

#### 4.2 URLs Commerçant
```python
# inventory/urls_commercant.py
from django.urls import path
from . import views_commercant

urlpatterns = [
    path('login/', views_commercant.login_commercant, name='login_commercant'),
    path('logout/', views_commercant.logout_commercant, name='logout_commercant'),
    path('dashboard/', views_commercant.dashboard_commercant, name='dashboard_commercant'),
    path('boutiques/', views_commercant.liste_boutiques, name='liste_boutiques'),
    path('boutiques/creer/', views_commercant.creer_boutique, name='creer_boutique'),
    path('boutiques/<int:boutique_id>/', views_commercant.detail_boutique, name='detail_boutique'),
    path('boutiques/<int:boutique_id>/articles/', views_commercant.articles_boutique, name='articles_boutique'),
    path('boutiques/<int:boutique_id>/terminaux/', views_commercant.terminaux_boutique, name='terminaux_boutique'),
]
```

### Phase 5: Adaptation MAUI

#### 5.1 Nouveaux Modèles MAUI
Suivre le guide dans `guide_migration_maui.md` pour :
- Ajouter les modèles Boutique et Terminal
- Modifier le service d'authentification
- Adapter l'interface utilisateur

#### 5.2 Configuration MAUI
```csharp
// Dans ApiSettings.cs
public static class ApiSettings
{
    public const string BaseUrl = "http://votre-serveur:8000";
    public const string AuthEndpoint = "/api/auth/terminal/";
    public const string ArticlesEndpoint = "/api/articles/boutique/";
    public const string VentesEndpoint = "/api/ventes/boutique/finaliser_vente/";
}
```

## 🧪 Tests de Validation

### Test 1: Authentification Terminal
```bash
curl -X POST http://localhost:8000/api/auth/terminal/ \
  -H "Content-Type: application/json" \
  -d '{
    "numero_serie": "PHAR001",
    "nom_terminal": "Caisse Principale",
    "nom_utilisateur": "Caissier 1",
    "version_app": "1.0.0"
  }'
```

### Test 2: Récupération Articles par Boutique
```bash
curl -X GET http://localhost:8000/api/articles/boutique/ \
  -H "X-MAUI-Token: TOKEN_SESSION_ICI"
```

### Test 3: Finalisation Vente
```bash
curl -X POST http://localhost:8000/api/ventes/boutique/finaliser_vente/ \
  -H "Content-Type: application/json" \
  -H "X-MAUI-Token: TOKEN_SESSION_ICI" \
  -d '{
    "numero_facture": "FAC001",
    "montant_total": 15000,
    "mode_paiement": "CASH",
    "lignes": [
      {"article_id": 1, "quantite": 2, "prix_unitaire": 7500}
    ]
  }'
```

## 🔒 Sécurité et Permissions

### Isolation des Données
- Chaque commerçant ne voit que ses boutiques
- Chaque terminal ne peut accéder qu'aux données de sa boutique
- Les articles et ventes sont isolés par boutique

### Authentification
- Commerçants : Authentification Django standard
- Terminaux MAUI : Authentification par numéro de série + token de session

## 📊 Monitoring et Maintenance

### Logs à Surveiller
```python
# Dans settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'multi_commercants.log',
        },
    },
    'loggers': {
        'inventory.api_views_multi_boutiques': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

### Métriques Importantes
- Nombre de connexions par terminal
- Ventes par boutique
- Erreurs d'authentification
- Performance des API

## 🚨 Dépannage

### Problèmes Courants

#### 1. Erreur de Migration
```bash
# Réinitialiser les migrations si nécessaire
python manage.py migrate inventory zero
python manage.py makemigrations inventory
python manage.py migrate
```

#### 2. Authentification MAUI Échoue
- Vérifier que le numéro de série existe
- Vérifier que la boutique est active
- Vérifier que le commerçant est actif

#### 3. Articles Non Visibles
- Vérifier que les articles sont liés à la bonne boutique
- Vérifier que les articles sont actifs

## ✅ Checklist de Déploiement

- [ ] Sauvegarde effectuée
- [ ] Nouveaux modèles intégrés
- [ ] Migrations appliquées
- [ ] Commerçant de test créé
- [ ] Boutique de test créée
- [ ] Terminal de test créé
- [ ] Articles migrés
- [ ] Ventes migrées
- [ ] Interface commerçant accessible
- [ ] API multi-boutiques fonctionnelle
- [ ] MAUI adapté et testé
- [ ] Tests de validation passés

## 🎯 Résultat Final

Après déploiement, vous aurez :

1. **Interface Super Admin** : Gestion globale des commerçants
2. **Interface Commerçant** : Gestion de ses boutiques et terminaux
3. **API Multi-Boutiques** : Isolation des données par boutique
4. **MAUI Adapté** : Authentification par boutique et terminal

Chaque commerçant peut gérer ses boutiques indépendamment, avec une isolation complète des données et une facturation séparée possible.
