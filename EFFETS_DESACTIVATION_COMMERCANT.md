# 🔒 EFFETS DE LA DÉSACTIVATION D'UN COMMERÇANT

## 📋 Vue d'Ensemble

Quand un super administrateur **désactive** un commerçant, cela a des effets en cascade sur tout le système.

## 🚫 Effets Immédiats

### 1. Connexion Bloquée

**Code** : `views_commercant.py` ligne 80-82
```python
if not commercant.est_actif:
    messages.error(request, "Votre compte commerçant est désactivé.")
    return redirect('login_commercant')
```

**Résultat** :
- ❌ Le commerçant **ne peut plus se connecter**
- ❌ S'il est déjà connecté, il est **déconnecté** à la prochaine action
- ❌ Message affiché : "Votre compte commerçant est désactivé."

### 2. Accès à l'Interface Bloqué

**Décorateur** : `@commercant_required`

Toutes les pages de l'interface commerçant sont protégées :
- ❌ Dashboard commerçant
- ❌ Gestion des boutiques
- ❌ Gestion des articles
- ❌ Gestion des ventes
- ❌ Gestion des catégories
- ❌ Tous les modules

**Redirection** : Vers la page de connexion avec message d'erreur

### 3. API MAUI Bloquée

**Code** : `api_views_multi_boutiques.py` ligne 78-80
```python
terminal = TerminalMaui.objects.get(
    numero_serie=numero_serie, 
    est_actif=True,
    boutique__est_active=True,
    boutique__commercant__est_actif=True  # ← Vérification ici
)
```

**Résultat** :
- ❌ **Tous les terminaux MAUI** du commerçant sont bloqués
- ❌ Impossible de s'authentifier depuis l'app MAUI
- ❌ Impossible de scanner des articles
- ❌ Impossible de faire des ventes
- ❌ Impossible de synchroniser les données

### 4. Interface Visuelle (Dashboard Admin)

**CSS** : `gestion_commercants.html`
```css
.status-inactive {
    border-left-color: #dc3545;  /* Rouge */
    opacity: 0.7;                /* Semi-transparent */
}
```

**Résultat** :
- 🔴 Bordure gauche de la carte devient **rouge**
- 👻 Carte devient **semi-transparente** (opacity: 0.7)
- 🏷️ Badge "**Inactif**" affiché
- 🟢 Bouton devient vert "**Activer**"

## 📊 Effets en Cascade

### 1. Toutes les Boutiques Bloquées

```
Commerçant Désactivé
    ↓
Boutique 1 ─┐
Boutique 2 ─┼─→ Toutes inaccessibles
Boutique 3 ─┘
```

**Conséquences** :
- ❌ Aucune boutique accessible
- ❌ Aucun article consultable
- ❌ Aucune vente possible
- ❌ Aucun terminal MAUI fonctionnel

### 2. Tous les Terminaux MAUI Bloqués

```
Commerçant Désactivé
    ↓
Boutique 1 → Terminal MAUI 1 ─┐
Boutique 2 → Terminal MAUI 2 ─┼─→ Tous bloqués
Boutique 3 → Terminal MAUI 3 ─┘
```

**Erreur API** :
```json
{
    "success": false,
    "error": "TERMINAL_NOT_FOUND",
    "message": "Terminal non trouvé ou inactif"
}
```

### 3. Statistiques Affectées

**Dashboard Admin** :
- ✅ Le commerçant reste compté dans "Total Commerçants"
- ❌ Retiré de "Commerçants Actifs"
- ✅ Ses boutiques restent comptées
- ✅ Ses ventes historiques restent visibles

## 🔄 Comparaison Actif vs Désactivé

| Aspect | Commerçant Actif ✅ | Commerçant Désactivé ❌ |
|--------|---------------------|-------------------------|
| **Connexion Web** | Autorisée | Bloquée |
| **Dashboard** | Accessible | Inaccessible |
| **Boutiques** | Gérables | Inaccessibles |
| **Articles** | Modifiables | Inaccessibles |
| **Ventes** | Consultables | Inaccessibles |
| **Terminaux MAUI** | Fonctionnels | Bloqués |
| **API MAUI** | Active | Bloquée |
| **Scan Articles** | Possible | Impossible |
| **Nouvelles Ventes** | Possibles | Impossibles |
| **Historique** | Conservé | Conservé |
| **Données** | Intactes | Intactes |

## 💾 Données Conservées

### ✅ Aucune Perte de Données

Même désactivé, **TOUTES** les données sont conservées :

1. **Profil Commerçant**
   - Nom entreprise
   - Informations contact
   - Type d'abonnement
   - Limites

2. **Boutiques**
   - Toutes les boutiques
   - Informations complètes
   - Configuration

3. **Articles**
   - Tous les articles
   - Stock actuel
   - Prix
   - Images et QR codes

4. **Ventes**
   - Historique complet
   - Toutes les transactions
   - Montants
   - Dates

5. **Terminaux MAUI**
   - Configuration
   - Numéros de série
   - Clés API

6. **Catégories**
   - Toutes les catégories
   - Organisation

## 🔓 Réactivation

### Processus Simple

1. **Admin clique** sur "Activer"
2. **Confirmation** de l'action
3. **Statut inversé** : `est_actif = True`
4. **Tout redevient fonctionnel** immédiatement

### Effets de la Réactivation

```
Commerçant Réactivé
    ↓
✅ Connexion possible
✅ Dashboard accessible
✅ Boutiques accessibles
✅ Terminaux MAUI fonctionnels
✅ API MAUI active
✅ Ventes possibles
```

## 🎯 Cas d'Usage

### Quand Désactiver un Commerçant ?

1. **Impayé d'Abonnement**
   - Suspension temporaire
   - Jusqu'au paiement

2. **Violation des Conditions**
   - Suspension pour enquête
   - Mesure de sécurité

3. **Demande du Commerçant**
   - Fermeture temporaire
   - Vacances prolongées

4. **Maintenance**
   - Migration de données
   - Mise à jour système

5. **Compte Inactif**
   - Pas d'utilisation depuis longtemps
   - Nettoyage administratif

### Quand NE PAS Désactiver ?

1. **Problème Technique Temporaire**
   - Mieux vaut désactiver un terminal spécifique

2. **Problème sur Une Boutique**
   - Désactiver la boutique plutôt que le commerçant

3. **Suppression Définitive**
   - Utiliser la fonction "Supprimer" à la place

## 🔍 Vérifications Système

### Points de Contrôle

**1. Connexion Web**
```python
# Ligne 80 - views_commercant.py
if not commercant.est_actif:
    messages.error(request, "Votre compte commerçant est désactivé.")
    return redirect('login_commercant')
```

**2. API MAUI - Authentification**
```python
# Ligne 78-80 - api_views_multi_boutiques.py
terminal = TerminalMaui.objects.get(
    boutique__commercant__est_actif=True  # Vérification
)
```

**3. API MAUI - Récupération Articles**
```python
# Vérifie que le commerçant est actif avant de retourner les articles
```

**4. API MAUI - Création Vente**
```python
# Vérifie que le commerçant est actif avant d'enregistrer la vente
```

## 📱 Expérience Utilisateur

### Côté Commerçant (Web)

**Tentative de Connexion** :
```
┌─────────────────────────────────────┐
│  Connexion Commerçant               │
├─────────────────────────────────────┤
│  Email: commercant@example.com      │
│  Mot de passe: ********             │
│                                     │
│  [Se connecter]                     │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│  ⚠️ Erreur                          │
│  Votre compte commerçant est        │
│  désactivé.                         │
└─────────────────────────────────────┘
```

**Déjà Connecté** :
```
Commerçant navigue → Clic sur une page
        ↓
Vérification @commercant_required
        ↓
Compte désactivé détecté
        ↓
Redirection vers login + message d'erreur
```

### Côté Terminal MAUI

**Tentative d'Authentification** :
```
Terminal MAUI → Envoi numéro de série
        ↓
API Django vérifie commercant.est_actif
        ↓
Commerçant désactivé
        ↓
Retour erreur "TERMINAL_NOT_FOUND"
        ↓
Message dans l'app : "Terminal non trouvé ou inactif"
```

**Tentative de Vente** :
```
Terminal MAUI → Scan article
        ↓
API Django vérifie commercant.est_actif
        ↓
Commerçant désactivé
        ↓
Erreur : Impossible de récupérer les articles
```

## 🛡️ Sécurité

### Protection Multi-Niveaux

1. **Niveau Web**
   - Décorateur `@commercant_required`
   - Vérification à chaque requête

2. **Niveau API**
   - Vérification dans les requêtes ORM
   - Filtrage automatique

3. **Niveau Base de Données**
   - Champ `est_actif` dans le modèle
   - Intégrité des données

### Logs et Traçabilité

**Action Enregistrée** :
```python
# Lors du toggle
commercant.est_actif = not commercant.est_actif
commercant.save()  # Date de mise à jour automatique
```

**Informations Conservées** :
- Date de désactivation (via `date_mise_a_jour`)
- Qui a désactivé (super admin connecté)
- Historique des changements

## 📊 Impact sur les Statistiques

### Dashboard Super Admin

**Avant Désactivation** :
```
Total Commerçants: 10
Commerçants Actifs: 10
```

**Après Désactivation** :
```
Total Commerçants: 10      ← Inchangé
Commerçants Actifs: 9      ← Diminué de 1
```

### Rapports et Exports

- ✅ Le commerçant apparaît dans les rapports
- ✅ Ses ventes sont comptées dans les statistiques globales
- ✅ Son CA est inclus dans les totaux
- 🏷️ Marqué comme "Inactif" dans les exports

## 🔄 Workflow Complet

### Désactivation

```
1. Super Admin → Dashboard Admin
2. Gestion des Commerçants
3. Clic sur "Désactiver" pour un commerçant
4. Confirmation : "Êtes-vous sûr ?"
5. Requête AJAX → Backend
6. commercant.est_actif = False
7. Sauvegarde en base
8. Retour JSON success
9. Page rechargée
10. Carte devient semi-transparente
11. Badge "Inactif" affiché
12. Bouton devient "Activer" (vert)
```

### Tentative d'Accès Commerçant

```
1. Commerçant → Page de connexion
2. Saisie identifiants
3. Authentification Django réussie
4. Redirection vers dashboard
5. Décorateur @commercant_required activé
6. Vérification commercant.est_actif
7. Résultat : False
8. Message d'erreur affiché
9. Redirection vers login
10. Commerçant bloqué
```

### Tentative d'Accès Terminal MAUI

```
1. Terminal MAUI → Envoi numéro de série
2. API recherche terminal
3. Filtre : est_actif=True
4. Filtre : boutique__est_active=True
5. Filtre : boutique__commercant__est_actif=True ← Échoue ici
6. Aucun terminal trouvé
7. Retour erreur "TERMINAL_NOT_FOUND"
8. App MAUI affiche message d'erreur
9. Impossible de continuer
```

## ✅ Résumé des Effets

### Effets Immédiats
- ❌ Connexion web bloquée
- ❌ Accès interface bloqué
- ❌ API MAUI bloquée
- ❌ Tous les terminaux bloqués
- 🔴 Interface admin : carte rouge et semi-transparente

### Effets en Cascade
- ❌ Toutes les boutiques inaccessibles
- ❌ Tous les articles inaccessibles
- ❌ Toutes les ventes impossibles
- ❌ Tous les terminaux MAUI non fonctionnels

### Données Conservées
- ✅ Profil commerçant intact
- ✅ Boutiques intactes
- ✅ Articles intacts
- ✅ Ventes historiques intactes
- ✅ Terminaux MAUI intacts
- ✅ Toutes les données préservées

### Réactivation
- ✅ Un clic pour réactiver
- ✅ Tout redevient fonctionnel immédiatement
- ✅ Aucune perte de données
- ✅ Aucune reconfiguration nécessaire

---

**En résumé** : Désactiver un commerçant = **Suspension temporaire complète** sans perte de données. Tout peut être réactivé en un clic ! 🔄
