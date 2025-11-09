# 🚀 Guide de Déploiement sur Scalingo - GestionMagazin

Ce guide vous accompagne étape par étape pour déployer votre application Django sur Scalingo.

---

## 📋 Prérequis

### 1. Compte Scalingo
- ✅ Créer un compte sur [https://scalingo.com](https://scalingo.com)
- ✅ Vérifier votre email
- ✅ Installer le CLI Scalingo (optionnel mais recommandé)

### 2. Installer le CLI Scalingo (Windows)
```powershell
# Télécharger depuis : https://cli.scalingo.com/
# Ou utiliser Chocolatey
choco install scalingo
```

### 3. Vérifier Git
```bash
git --version
# Si pas installé : https://git-scm.com/download/win
```

---

## 📦 Fichiers Préparés (Déjà Créés)

✅ **Procfile** - Configuration du serveur web  
✅ **runtime.txt** - Version Python  
✅ **requirements.txt** - Dépendances Python complètes  
✅ **scalingo.json** - Configuration Scalingo  
✅ **.scalingoignore** - Fichiers à ignorer  
✅ **settings.py** - Adapté pour production  
✅ **.env.example** - Exemple de variables d'environnement  

---

## 🔧 Étape 1 : Initialiser Git (si pas déjà fait)

```bash
# Dans le dossier GestionMagazin
cd C:\Users\PC\Documents\GestionMagazin

# Initialiser Git
git init

# Créer .gitignore
echo "*.pyc
__pycache__/
*.sqlite3
db.sqlite3
*.log
.env
env/
venv/
media/qr_codes/
staticfiles/" > .gitignore

# Premier commit
git add .
git commit -m "Préparation déploiement Scalingo"
```

---

## 🌐 Étape 2 : Créer l'Application sur Scalingo

### Option A : Via l'interface Web

1. **Connexion** : [https://dashboard.scalingo.com](https://dashboard.scalingo.com)
2. **Créer une App** : Cliquer sur "Create an app"
3. **Nom** : Choisir un nom (ex: `gestion-magazin-prod`)
4. **Région** : Choisir "osc-fr1" (Paris, France)

### Option B : Via le CLI

```bash
# Se connecter
scalingo login

# Créer l'application
scalingo create gestion-magazin-prod --region osc-fr1
```

---

## 🗄️ Étape 3 : Ajouter PostgreSQL

### Via l'interface Web

1. **Dashboard** → Votre app → **Addons**
2. **Ajouter PostgreSQL** : Starter 512MB (gratuit pour commencer)
3. **Confirmer** : L'addon est créé automatiquement

### Via le CLI

```bash
scalingo --app gestion-magazin-prod addons-add postgresql postgresql-starter-512
```

> ℹ️ La variable `DATABASE_URL` est automatiquement créée

---

## 🔑 Étape 4 : Configurer les Variables d'Environnement

### Via l'interface Web

1. **Dashboard** → Votre app → **Environment**
2. **Ajouter les variables** :

```
SECRET_KEY=votre-nouvelle-cle-secrete-tres-longue-et-aleatoire-minimum-50-caracteres
DEBUG=False
ALLOWED_HOSTS=.scalingo.io,gestion-magazin-prod.osc-fr1.scalingo.io
```

### Via le CLI

```bash
# Générer une SECRET_KEY sécurisée
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Configurer les variables
scalingo --app gestion-magazin-prod env-set SECRET_KEY="votre-cle-generee"
scalingo --app gestion-magazin-prod env-set DEBUG="False"
scalingo --app gestion-magazin-prod env-set ALLOWED_HOSTS=".scalingo.io,gestion-magazin-prod.osc-fr1.scalingo.io"
```

> ⚠️ **Important** : Remplacez `gestion-magazin-prod` par le nom réel de votre app

---

## 🚀 Étape 5 : Déployer l'Application

### Ajouter le remote Git Scalingo

```bash
# Vérifier le nom de votre app
scalingo apps

# Ajouter le remote (remplacer VOTRE_APP par le nom réel)
git remote add scalingo git@ssh.osc-fr1.scalingo.com:VOTRE_APP.git

# Ou via CLI
scalingo --app gestion-magazin-prod git-setup
```

### Déployer

```bash
# Pousser sur Scalingo
git push scalingo master

# Ou si votre branche est "main"
git push scalingo main:master
```

### Suivre le déploiement

```bash
# Via CLI
scalingo --app gestion-magazin-prod logs --follow

# Ou dans le Dashboard Web → Logs
```

---

## 🛠️ Étape 6 : Migrations et Superuser

### Exécuter les migrations

```bash
# Via CLI
scalingo --app gestion-magazin-prod run python manage.py migrate

# Créer un superutilisateur
scalingo --app gestion-magazin-prod run python manage.py createsuperuser
```

### Collecter les fichiers statiques

```bash
# Normalement fait automatiquement par le Procfile
# Mais si besoin :
scalingo --app gestion-magazin-prod run python manage.py collectstatic --noinput
```

---

## ✅ Étape 7 : Vérifier le Déploiement

### Accéder à l'application

```
https://VOTRE_APP.osc-fr1.scalingo.io
```

### Vérifier les logs

```bash
# Temps réel
scalingo --app gestion-magazin-prod logs --follow

# Derniers logs
scalingo --app gestion-magazin-prod logs -n 100
```

### Tests à effectuer

- ✅ Page d'accueil charge correctement
- ✅ Connexion admin : `/admin/`
- ✅ API fonctionne : `/api/v2/`
- ✅ Fichiers statiques (CSS/JS) chargent
- ✅ Création d'une boutique
- ✅ Ajout d'articles

---

## 📱 Étape 8 : Configurer l'Application MAUI

### Mettre à jour l'URL de l'API MAUI

```csharp
// Dans votre projet MAUI
builder.Services.AddHttpClient("DjangoAPI", client =>
{
    // AVANT (développement)
    // client.BaseAddress = new Uri("http://192.168.52.224:8000");
    
    // APRÈS (production Scalingo)
    client.BaseAddress = new Uri("https://VOTRE_APP.osc-fr1.scalingo.io");
    
    // Headers
    #if ANDROID
    string numeroSerie = Android.OS.Build.Serial ?? Android.OS.Build.GetSerial();
    client.DefaultRequestHeaders.Add("X-Device-Serial", numeroSerie);
    #endif
});
```

### Tester la connexion

```csharp
// Test d'authentification
var response = await _httpClient.PostAsync("/api/v2/auth/maui/", content);
```

---

## 🔧 Commandes Utiles

### Logs et Debug

```bash
# Voir les logs en temps réel
scalingo --app gestion-magazin-prod logs --follow

# Accéder au shell Django
scalingo --app gestion-magazin-prod run python manage.py shell

# Lancer dbshell PostgreSQL
scalingo --app gestion-magazin-prod run python manage.py dbshell
```

### Gestion de l'application

```bash
# Redémarrer l'application
scalingo --app gestion-magazin-prod restart

# Mettre à l'échelle
scalingo --app gestion-magazin-prod scale web:1:M

# État de l'application
scalingo --app gestion-magazin-prod ps
```

### Base de données

```bash
# Créer un backup manuel
scalingo --app gestion-magazin-prod backups-create

# Lister les backups
scalingo --app gestion-magazin-prod backups

# Télécharger un backup
scalingo --app gestion-magazin-prod backups-download
```

---

## 🔄 Déploiement de Mises à Jour

```bash
# Après modifications du code
git add .
git commit -m "Description des changements"
git push scalingo master

# Les migrations sont exécutées automatiquement (voir Procfile)
```

---

## ⚠️ Dépannage

### Problème : Erreur 500 après déploiement

**Solution** :
```bash
# Vérifier les logs
scalingo --app gestion-magazin-prod logs -n 100

# Vérifier les variables d'environnement
scalingo --app gestion-magazin-prod env

# Vérifier que DEBUG=False et SECRET_KEY est définie
```

### Problème : Fichiers statiques ne chargent pas

**Solution** :
```bash
# Collecter à nouveau les fichiers statiques
scalingo --app gestion-magazin-prod run python manage.py collectstatic --noinput

# Vérifier STATIC_ROOT et STATICFILES_STORAGE dans settings.py
```

### Problème : Migrations échouent

**Solution** :
```bash
# Lancer les migrations manuellement
scalingo --app gestion-magazin-prod run python manage.py migrate --verbosity 2

# Vérifier l'état des migrations
scalingo --app gestion-magazin-prod run python manage.py showmigrations
```

### Problème : "DisallowedHost" erreur

**Solution** :
```bash
# Ajouter l'hôte dans ALLOWED_HOSTS
scalingo --app gestion-magazin-prod env-set ALLOWED_HOSTS=".scalingo.io,VOTRE_APP.osc-fr1.scalingo.io"
```

---

## 📊 Surveillance et Performance

### Metrics Dashboard

- **Accès** : Dashboard Scalingo → Votre app → Metrics
- **Métriques** : CPU, RAM, Requêtes HTTP, Temps de réponse

### Activer les Notifications

- **Dashboard** → Settings → Notifications
- **Configurer** : Email, Slack pour alertes

### Upgrade du Plan (si nécessaire)

```bash
# Passer à un plan supérieur
scalingo --app gestion-magazin-prod addons-upgrade postgresql postgresql-starter-1024
scalingo --app gestion-magazin-prod scale web:1:M
```

---

## 🔒 Sécurité en Production

### Checklist Sécurité

- ✅ `DEBUG=False` en production
- ✅ `SECRET_KEY` unique et sécurisée (50+ caractères)
- ✅ `ALLOWED_HOSTS` correctement configuré
- ✅ HTTPS activé (automatique sur Scalingo)
- ✅ Variables sensibles dans variables d'environnement (pas dans le code)
- ✅ Backups automatiques PostgreSQL activés
- ✅ Logs surveillés régulièrement

### Backups Automatiques

```bash
# Activer les backups quotidiens (inclus dans les plans payants)
# Via Dashboard → Addons → PostgreSQL → Backups
```

---

## 📞 Support

### Ressources Scalingo

- **Documentation** : [https://doc.scalingo.com](https://doc.scalingo.com)
- **Support** : [https://scalingo.com/support](https://scalingo.com/support)
- **Status** : [https://scalingostatus.com](https://scalingostatus.com)

### Commandes d'Aide

```bash
# Aide générale
scalingo help

# Aide sur une commande spécifique
scalingo help logs
scalingo help env-set
```

---

## 🎉 Félicitations !

Votre application **GestionMagazin** est maintenant déployée en production sur Scalingo !

### URLs Importantes

- **Application** : `https://VOTRE_APP.osc-fr1.scalingo.io`
- **Admin Django** : `https://VOTRE_APP.osc-fr1.scalingo.io/admin/`
- **API v2** : `https://VOTRE_APP.osc-fr1.scalingo.io/api/v2/`
- **Dashboard Scalingo** : [https://dashboard.scalingo.com](https://dashboard.scalingo.com)

### Prochaines Étapes

1. ✅ Configurer un nom de domaine personnalisé (optionnel)
2. ✅ Configurer les backups automatiques
3. ✅ Surveiller les métriques et logs
4. ✅ Tester avec l'application MAUI
5. ✅ Former les utilisateurs

---

**Dernière mise à jour** : Novembre 2024  
**Support** : Contactez votre équipe technique pour toute question
