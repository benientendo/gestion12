# Problème de Synchronisation des Catalogues d'Articles MAUI

## 🔴 Problème Identifié

Les catalogues d'articles ne se synchronisent pas correctement entre le serveur Django et l'application MAUI.

## 🔍 Causes Possibles

### 1. **Paramètre `boutique_id` Manquant**
L'application MAUI n'envoie pas le paramètre `boutique_id` lors de la requête API pour récupérer les articles.

**URL Incorrecte:**
```
GET /api/v2/simple/articles/
```

**URL Correcte:**
```
GET /api/v2/simple/articles/?boutique_id=2
```

### 2. **Mauvaise URL API Utilisée**
L'application MAUI utilise peut-être l'ancienne API au lieu de l'API v2 multi-boutiques.

**Anciennes URLs (à ne plus utiliser):**
- `/api/articles/`
- `/api/categories/`

**Nouvelles URLs (à utiliser):**
- `/api/v2/simple/articles/?boutique_id=X`
- `/api/v2/simple/categories/?boutique_id=X`

### 3. **Problème d'Authentification**
Le terminal MAUI n'est pas correctement authentifié ou n'a pas récupéré son `boutique_id` lors de la connexion.

### 4. **Cache MAUI Non Vidé**
Les données sont en cache dans l'application MAUI et ne sont pas mises à jour.

## ✅ Solution - Outil de Diagnostic Créé

### Page de Diagnostic Disponible

**URL:** `/superadmin/diagnostic-api/`

**Accès:** Dashboard Super Admin → Section "Outils de Diagnostic" → Bouton "Lancer le Diagnostic"

### Fonctionnalités de l'Outil

1. **Test Status API** - Vérifier que l'API v2 est accessible
2. **Liste des Boutiques** - Récupérer toutes les boutiques disponibles
3. **Articles par Boutique** - Tester la récupération des articles d'une boutique spécifique
4. **Catégories par Boutique** - Tester la récupération des catégories

### Comment Utiliser l'Outil

1. **Accéder à la page de diagnostic**
   - Se connecter en tant que super admin
   - Aller sur `/superadmin/diagnostic-api/`

2. **Sélectionner une boutique**
   - Choisir une boutique dans la liste déroulante
   - Les informations de la boutique s'affichent

3. **Lancer les tests**
   - Cliquer sur "Tester" pour chaque endpoint
   - Vérifier les réponses JSON affichées

4. **Analyser les résultats**
   - Vérifier que les articles s'affichent correctement
   - Noter le nombre d'articles retournés
   - Comparer avec les données en base

## 🔧 Configuration MAUI Requise

### 1. Authentification MAUI

L'application MAUI doit d'abord s'authentifier pour récupérer son `boutique_id`:

```csharp
// Endpoint d'authentification
POST /api/v2/auth/maui/

// Corps de la requête
{
    "numero_serie": "MAUI-XXX",
    "version_app": "1.0.0"
}

// Réponse
{
    "success": true,
    "token": "...",
    "boutique_id": 2,
    "boutique": {
        "id": 2,
        "nom": "Ma Boutique",
        "code_boutique": "BTQ-002",
        "type_commerce": "PHARMACIE",
        "ville": "Kinshasa",
        "devise": "CDF"
    }
}
```

### 2. Récupération des Articles

Une fois authentifié, utiliser le `boutique_id` pour toutes les requêtes:

```csharp
// Récupérer les articles
GET /api/v2/simple/articles/?boutique_id={boutiqueId}

// Récupérer les catégories
GET /api/v2/simple/categories/?boutique_id={boutiqueId}
```

### 3. Code C# Exemple

```csharp
public class ArticleService : BaseApiService
{
    private int _boutiqueId;

    public async Task InitializeAsync(string numeroSerie)
    {
        // 1. Authentification
        var authResponse = await AuthenticateAsync(numeroSerie);
        _boutiqueId = authResponse.BoutiqueId;
    }

    public async Task<List<Article>> GetArticlesAsync()
    {
        // 2. Récupération des articles avec boutique_id
        var url = $"/api/v2/simple/articles/?boutique_id={_boutiqueId}";
        var response = await _httpClient.GetAsync(url);
        
        if (response.IsSuccessStatusCode)
        {
            var content = await response.Content.ReadAsStringAsync();
            var result = JsonSerializer.Deserialize<ArticlesResponse>(content);
            return result.Articles;
        }
        
        return new List<Article>();
    }
}
```

## 📋 Checklist de Vérification

### Côté Serveur Django

- [x] API v2 créée et fonctionnelle
- [x] Endpoints avec isolation par boutique
- [x] Template de diagnostic créé
- [x] URL de diagnostic ajoutée
- [x] Lien dans dashboard admin

### Côté Application MAUI

- [ ] Authentification MAUI implémentée
- [ ] Récupération du `boutique_id` lors de la connexion
- [ ] Utilisation de l'API v2 au lieu de l'ancienne API
- [ ] Paramètre `boutique_id` ajouté à toutes les requêtes
- [ ] Gestion du cache et rafraîchissement des données

## 🚀 Prochaines Étapes

### 1. Tester avec l'Outil de Diagnostic

1. Accéder à `/superadmin/diagnostic-api/`
2. Sélectionner une boutique de test
3. Lancer tous les tests
4. Noter les résultats

### 2. Vérifier les Logs Django

```bash
# Activer les logs détaillés
python manage.py runserver

# Observer les requêtes reçues
# Vérifier que boutique_id est présent dans les requêtes
```

### 3. Mettre à Jour MAUI

1. Implémenter l'authentification v2
2. Stocker le `boutique_id` après authentification
3. Ajouter `boutique_id` à toutes les requêtes API
4. Tester la synchronisation

### 4. Valider la Synchronisation

1. Ajouter un article via l'interface web
2. Lancer la synchronisation dans MAUI
3. Vérifier que l'article apparaît
4. Tester avec plusieurs boutiques

## 📞 Support

Si le problème persiste après avoir suivi ce guide:

1. **Vérifier les logs Django** pour voir les requêtes reçues
2. **Utiliser l'outil de diagnostic** pour identifier le problème exact
3. **Vérifier la configuration MAUI** (URL du serveur, numéro de série)
4. **Tester manuellement les endpoints** avec Postman ou curl

## 🔗 Ressources

- **Documentation API v2:** `/GUIDE_MIGRATION_API_V2_MAUI.md`
- **Architecture API:** `/ARCHITECTURE_API_V2_MULTI_BOUTIQUES.md`
- **Page de diagnostic:** `/superadmin/diagnostic-api/`
- **Endpoints API:**
  - Status: `/api/v2/simple/status/`
  - Boutiques: `/api/v2/simple/boutiques/`
  - Articles: `/api/v2/simple/articles/?boutique_id=X`
  - Catégories: `/api/v2/simple/categories/?boutique_id=X`

---

**Date de création:** 28 octobre 2025  
**Dernière mise à jour:** 28 octobre 2025  
**Version:** 1.0
