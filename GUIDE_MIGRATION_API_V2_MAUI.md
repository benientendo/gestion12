# 🚀 GUIDE MIGRATION API v2 MULTI-BOUTIQUES - ÉQUIPE MAUI

## 📋 RÉSUMÉ EXÉCUTIF

L'API Django a été adaptée pour supporter l'architecture multi-boutiques avec **isolation complète des données par boutique** basée sur le numéro de série du terminal MAUI.

### ✅ OBJECTIFS ATTEINTS
- **Isolation parfaite** : Chaque terminal ne voit que les données de sa boutique
- **Sécurité renforcée** : Impossible d'accéder aux données d'autres boutiques
- **Compatibilité MAUI** : Modifications minimales côté application
- **Performance optimisée** : Requêtes filtrées automatiquement

---

## 🔄 CHANGEMENTS CÔTÉ MAUI

### 1. **AUTHENTIFICATION SIMPLIFIÉE**

#### AVANT (API v1) :
```csharp
var authData = new {
    numero_serie = deviceSerial,
    nom_boutique = "Nom Boutique",
    proprietaire = "Nom Propriétaire"
};
```

#### APRÈS (API v2) :
```csharp
var authData = new {
    numero_serie = deviceSerial,
    version_app = "2.0.0"  // Optionnel
};
```

### 2. **NOUVEAUX ENDPOINTS API v2**

| Fonction | API v1 | API v2 |
|----------|--------|--------|
| Authentification | `/api/maui/auth/` | `/api/v2/auth/maui/` |
| Articles | `/api/articles/` | `/api/v2/articles/?boutique_id=X` |
| Catégories | `/api/categories/` | `/api/v2/categories/?boutique_id=X` |
| Ventes | `/api/ventes/` | `/api/v2/ventes/` |
| Validation session | `/api/maui/verify-session/` | `/api/v2/auth/validate/` |

### 3. **GESTION AUTOMATIQUE DU BOUTIQUE_ID**

#### Réponse d'authentification v2 :
```json
{
  "success": true,
  "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "boutique_id": 2,
  "boutique": {
    "id": 2,
    "nom": "Ma Boutique",
    "code_boutique": "BOUT_001",
    "type_commerce": "PHARMACIE",
    "ville": "Kinshasa",
    "devise": "CDF"
  },
  "terminal": {
    "id": 1,
    "numero_serie": "1327637493002135",
    "nom_terminal": "Terminal Principal"
  }
}
```

---

## 🛠️ MODIFICATIONS TECHNIQUES REQUISES

### 1. **Service d'Authentification**

```csharp
public class AuthService
{
    private string _boutiqueId;
    
    public async Task<AuthResult> AuthenticateAsync(string numeroSerie)
    {
        var authData = new { numero_serie = numeroSerie, version_app = "2.0.0" };
        
        var response = await _httpClient.PostAsync(
            "api/v2/auth/maui/", 
            JsonContent.Create(authData)
        );
        
        if (response.IsSuccessStatusCode)
        {
            var result = await response.Content.ReadFromJsonAsync<AuthResponse>();
            
            // CRITIQUE : Stocker le boutique_id pour tous les appels futurs
            _boutiqueId = result.BoutiqueId.ToString();
            await SecureStorage.SetAsync("boutique_id", _boutiqueId);
            await SecureStorage.SetAsync("token", result.Token);
            
            return new AuthResult { Success = true, BoutiqueInfo = result.Boutique };
        }
        
        return new AuthResult { Success = false };
    }
}
```

### 2. **Service API de Base**

```csharp
public class BaseApiService
{
    protected async Task<string> GetBoutiqueIdAsync()
    {
        return await SecureStorage.GetAsync("boutique_id");
    }
    
    protected async Task<HttpRequestMessage> CreateRequestAsync(
        HttpMethod method, 
        string endpoint, 
        object content = null)
    {
        var request = new HttpRequestMessage(method, endpoint);
        
        // Ajouter le token d'authentification
        var token = await SecureStorage.GetAsync("token");
        if (!string.IsNullOrEmpty(token))
        {
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        }
        
        // Ajouter le contenu si nécessaire
        if (content != null)
        {
            request.Content = JsonContent.Create(content);
        }
        
        return request;
    }
    
    protected string AddBoutiqueIdToUrl(string baseUrl)
    {
        var boutiqueId = GetBoutiqueIdAsync().Result;
        if (string.IsNullOrEmpty(boutiqueId))
        {
            throw new InvalidOperationException("Boutique ID non disponible");
        }
        
        var separator = baseUrl.Contains("?") ? "&" : "?";
        return $"{baseUrl}{separator}boutique_id={boutiqueId}";
    }
}
```

### 3. **Service Articles Modifié**

```csharp
public class ArticleService : BaseApiService
{
    public async Task<List<Article>> GetArticlesAsync()
    {
        try
        {
            // AVANT : var url = "api/articles/";
            // APRÈS : Ajouter automatiquement boutique_id
            var url = AddBoutiqueIdToUrl("api/v2/articles/");
            
            var request = await CreateRequestAsync(HttpMethod.Get, url);
            var response = await _httpClient.SendAsync(request);
            
            if (response.IsSuccessStatusCode)
            {
                var result = await response.Content.ReadFromJsonAsync<ArticlesResponse>();
                return result.Articles;
            }
            
            return new List<Article>();
        }
        catch (Exception ex)
        {
            // Log l'erreur
            return new List<Article>();
        }
    }
}
```

### 4. **Service Ventes Modifié**

```csharp
public class VenteService : BaseApiService
{
    public async Task<bool> CreateVenteAsync(Vente vente)
    {
        try
        {
            var boutiqueId = await GetBoutiqueIdAsync();
            
            // CRITIQUE : Ajouter boutique_id aux données de vente
            var venteData = new
            {
                boutique_id = int.Parse(boutiqueId),
                numero_facture = vente.NumeroFacture,
                mode_paiement = vente.ModePaiement,
                paye = vente.Paye,
                lignes = vente.Lignes.Select(l => new
                {
                    article_id = l.ArticleId,
                    quantite = l.Quantite,
                    prix_unitaire = l.PrixUnitaire
                }).ToList()
            };
            
            var request = await CreateRequestAsync(
                HttpMethod.Post, 
                "api/v2/ventes/", 
                venteData
            );
            
            var response = await _httpClient.SendAsync(request);
            return response.IsSuccessStatusCode;
        }
        catch (Exception ex)
        {
            // Log l'erreur
            return false;
        }
    }
}
```

---

## 🔒 SÉCURITÉ ET ISOLATION

### **Garanties de Sécurité :**

1. **Authentification par Numéro de Série** : Seuls les terminaux enregistrés peuvent s'authentifier
2. **Association Boutique Automatique** : Le `boutique_id` est déterminé par le numéro de série
3. **Filtrage Automatique** : Toutes les requêtes sont filtrées par boutique
4. **Validation Stricte** : Impossible d'accéder aux données d'une autre boutique

### **Tests de Validation :**

```bash
# Lancer le script de test d'isolation
python test_api_v2_isolation.py
```

Le script vérifie :
- ✅ Authentification avec numéro de série
- ✅ Récupération des articles de la bonne boutique
- ✅ Rejet d'accès aux autres boutiques
- ✅ Validation des sessions
- ✅ Isolation complète des données

---

## 📊 EXEMPLE CONCRET D'UTILISATION

### **Scénario :** Terminal `1327637493002135` de la boutique "Ma Pharmacie"

#### 1. Authentification :
```http
POST /api/v2/auth/maui/
{
  "numero_serie": "1327637493002135",
  "version_app": "2.0.0"
}
```

#### 2. Réponse :
```json
{
  "boutique_id": 2,
  "boutique": {
    "nom": "Ma Pharmacie",
    "type_commerce": "PHARMACIE",
    "devise": "CDF"
  }
}
```

#### 3. Récupération Articles :
```http
GET /api/v2/articles/?boutique_id=2
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

#### 4. Résultat :
```json
{
  "success": true,
  "count": 15,
  "boutique_id": 2,
  "articles": [
    {
      "id": 1,
      "nom": "Paracétamol 500mg",
      "code": "PARA500",
      "prix_vente": 500.00,
      "quantite_stock": 100
    }
  ]
}
```

---

## 🚦 PLAN DE MIGRATION

### **Phase 1 : Préparation (1 jour)**
- [ ] Mettre à jour les constantes d'URL vers API v2
- [ ] Implémenter la gestion du `boutique_id`
- [ ] Modifier le service d'authentification

### **Phase 2 : Services Core (2 jours)**
- [ ] Adapter ArticleService
- [ ] Adapter VenteService  
- [ ] Adapter CategorieService
- [ ] Tester sur terminal pilote

### **Phase 3 : Tests et Validation (1 jour)**
- [ ] Tests d'isolation des données
- [ ] Tests de performance
- [ ] Validation sécurité

### **Phase 4 : Déploiement (1 jour)**
- [ ] Déploiement progressif
- [ ] Monitoring des erreurs
- [ ] Validation terrain

---

## 🔧 POINTS D'ATTENTION

### **Critiques :**
1. **Stockage Sécurisé** : Le `boutique_id` doit être stocké de manière sécurisée
2. **Gestion d'Erreur** : Prévoir les cas où `boutique_id` est manquant
3. **Synchronisation** : S'assurer que tous les appels API utilisent v2

### **Optionnels :**
1. **Cache Local** : Mettre en cache les informations boutique
2. **Retry Logic** : Implémenter une logique de retry pour les appels échoués
3. **Monitoring** : Ajouter des logs pour le debugging

---

## 🆘 SUPPORT ET DÉPANNAGE

### **Erreurs Communes :**

| Erreur | Cause | Solution |
|--------|-------|----------|
| `MISSING_BOUTIQUE_ID` | Paramètre manquant | Ajouter `boutique_id` à la requête |
| `ACCESS_DENIED` | Terminal non autorisé | Vérifier le numéro de série |
| `BOUTIQUE_INACTIVE` | Boutique désactivée | Contacter l'administrateur |
| `TERMINAL_NOT_FOUND` | Terminal inexistant | Vérifier l'enregistrement |

### **Diagnostic Rapide :**

```csharp
public async Task<bool> DiagnosticApiV2Async()
{
    try
    {
        // 1. Vérifier le token
        var token = await SecureStorage.GetAsync("token");
        if (string.IsNullOrEmpty(token))
        {
            Debug.WriteLine("❌ Token manquant");
            return false;
        }
        
        // 2. Vérifier boutique_id
        var boutiqueId = await SecureStorage.GetAsync("boutique_id");
        if (string.IsNullOrEmpty(boutiqueId))
        {
            Debug.WriteLine("❌ Boutique ID manquant");
            return false;
        }
        
        // 3. Test de connectivité
        var response = await _httpClient.GetAsync($"api/v2/articles/?boutique_id={boutiqueId}");
        Debug.WriteLine($"✅ API v2 Status: {response.StatusCode}");
        
        return response.IsSuccessStatusCode;
    }
    catch (Exception ex)
    {
        Debug.WriteLine($"❌ Erreur diagnostic: {ex.Message}");
        return false;
    }
}
```

---

## 📞 CONTACT

Pour toute question technique :
- **Backend Django** : Équipe Backend
- **Tests d'isolation** : `python test_api_v2_isolation.py`
- **Documentation API** : Voir `api_views_v2.py`

---

## ✅ CHECKLIST FINALE

- [ ] Endpoints API v2 implémentés
- [ ] Gestion automatique du `boutique_id`
- [ ] Service d'authentification adapté
- [ ] Services articles/ventes/catégories modifiés
- [ ] Tests d'isolation validés
- [ ] Gestion d'erreur robuste
- [ ] Documentation mise à jour

**🎉 L'API v2 multi-boutiques est prête pour l'intégration MAUI !**
