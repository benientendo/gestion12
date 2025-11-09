# 🔧 DÉPANNAGE - Erreurs 400 API MAUI

## 🚨 Problème Identifié

Vous obtenez des erreurs **400 Bad Request** sur :
- `POST /api/v2/simple/ventes/`
- `GET /api/v2/simple/articles/`
- `GET /api/v2/simple/categories/`

## 🔍 Cause Principale

Le header `X-Device-Serial` n'est **PAS envoyé** avec toutes les requêtes.

### Vérification dans les Logs Django

Quand vous voyez :
```
Bad Request: /api/v2/simple/ventes/
[29/Oct/2025 00:31:17] "POST /api/v2/simple/ventes/ HTTP/1.1" 400 188
```

Cela signifie que le numéro de série est manquant.

## ✅ Solution : Configuration HttpClient Globale

### ❌ MAUVAISE Configuration (Ne Fonctionne Pas)

```csharp
// Configuration locale - Le header n'est pas persisté
public async Task<List<Article>> GetArticlesAsync()
{
    var client = new HttpClient();
    client.DefaultRequestHeaders.Add("X-Device-Serial", "0a1badae951f8473");
    var response = await client.GetAsync("http://192.168.52.224:8000/api/v2/simple/articles/");
}
```

**Problème :** Le header est ajouté localement mais perdu entre les requêtes.

### ✅ BONNE Configuration (Fonctionne)

```csharp
// Dans MauiProgram.cs
public static MauiApp CreateMauiApp()
{
    var builder = MauiApp.CreateBuilder();
    
    // Récupérer le numéro de série UNE SEULE FOIS
    string numeroSerie = GetDeviceSerialNumber();
    
    // Configurer HttpClient GLOBALEMENT avec IHttpClientFactory
    builder.Services.AddHttpClient("DjangoAPI", client =>
    {
        client.BaseAddress = new Uri("http://192.168.52.224:8000");
        
        // ⭐ IMPORTANT : Ajouter le header ICI
        client.DefaultRequestHeaders.Add("X-Device-Serial", numeroSerie);
        
        // Headers supplémentaires recommandés
        client.DefaultRequestHeaders.Add("Accept", "application/json");
        client.Timeout = TimeSpan.FromSeconds(30);
    });
    
    // Enregistrer les services
    builder.Services.AddSingleton<IArticleService, ArticleService>();
    builder.Services.AddSingleton<IVenteService, VenteService>();
    
    return builder.Build();
}

private static string GetDeviceSerialNumber()
{
    #if ANDROID
    try
    {
        return Android.OS.Build.Serial ?? Android.OS.Build.GetSerial();
    }
    catch
    {
        return "0a1badae951f8473"; // Fallback pour tests
    }
    #else
    return "0a1badae951f8473"; // Pour tests Windows/iOS
    #endif
}
```

### ✅ Utilisation dans les Services

```csharp
public class ArticleService : IArticleService
{
    private readonly HttpClient _httpClient;

    // ⭐ IMPORTANT : Injecter IHttpClientFactory
    public ArticleService(IHttpClientFactory httpClientFactory)
    {
        // Récupérer le client configuré
        _httpClient = httpClientFactory.CreateClient("DjangoAPI");
    }

    public async Task<List<Article>> GetArticlesAsync()
    {
        // Le header X-Device-Serial est AUTOMATIQUEMENT ajouté !
        var response = await _httpClient.GetAsync("/api/v2/simple/articles/");
        
        if (response.IsSuccessStatusCode)
        {
            var content = await response.Content.ReadAsStringAsync();
            var result = JsonSerializer.Deserialize<ArticlesResponse>(content);
            return result.Articles;
        }
        
        return new List<Article>();
    }
}

public class VenteService : IVenteService
{
    private readonly HttpClient _httpClient;

    public VenteService(IHttpClientFactory httpClientFactory)
    {
        _httpClient = httpClientFactory.CreateClient("DjangoAPI");
    }

    public async Task<VenteResponse> CreerVenteAsync(VenteRequest vente)
    {
        var json = JsonSerializer.Serialize(vente);
        var content = new StringContent(json, Encoding.UTF8, "application/json");
        
        // Le header X-Device-Serial est AUTOMATIQUEMENT ajouté !
        var response = await _httpClient.PostAsync("/api/v2/simple/ventes/", content);
        
        if (response.IsSuccessStatusCode)
        {
            var result = await response.Content.ReadAsStringAsync();
            return JsonSerializer.Deserialize<VenteResponse>(result);
        }
        
        // Afficher l'erreur pour debug
        var error = await response.Content.ReadAsStringAsync();
        Console.WriteLine($"❌ Erreur vente: {error}");
        
        return null;
    }
}
```

## 🧪 Test de Vérification

### 1. Vérifier que le Header est Envoyé

```csharp
public async Task TestHeaderAsync()
{
    var response = await _httpClient.GetAsync("/api/v2/simple/articles/");
    
    Console.WriteLine($"Status: {response.StatusCode}");
    Console.WriteLine($"Headers envoyés:");
    
    foreach (var header in _httpClient.DefaultRequestHeaders)
    {
        Console.WriteLine($"  {header.Key}: {string.Join(", ", header.Value)}");
    }
}
```

**Résultat Attendu :**
```
Status: 200
Headers envoyés:
  X-Device-Serial: 0a1badae951f8473
  Accept: application/json
```

### 2. Vérifier les Logs Django

Après avoir configuré correctement, vous devriez voir dans les logs Django :

```
✅ Terminal trouvé: Terminal messie vanza → Boutique ID: 2
[29/Oct/2025 00:30:46] "GET /api/v2/simple/articles/ HTTP/1.1" 200 1129
```

Au lieu de :
```
Bad Request: /api/v2/simple/articles/
[29/Oct/2025 00:30:45] "GET /api/v2/simple/articles/ HTTP/1.1" 400 228
```

## 📋 Checklist de Vérification

- [ ] `MauiProgram.cs` contient `AddHttpClient("DjangoAPI", ...)`
- [ ] Le header `X-Device-Serial` est ajouté dans la configuration
- [ ] Les services utilisent `IHttpClientFactory`
- [ ] Les services appellent `CreateClient("DjangoAPI")`
- [ ] Le numéro de série est récupéré correctement
- [ ] Les requêtes utilisent `_httpClient` injecté (pas `new HttpClient()`)

## 🔍 Debug Avancé

### Afficher Tous les Headers Envoyés

```csharp
public class LoggingHandler : DelegatingHandler
{
    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request, 
        CancellationToken cancellationToken)
    {
        Console.WriteLine($"🔍 Request: {request.Method} {request.RequestUri}");
        Console.WriteLine($"🔍 Headers:");
        
        foreach (var header in request.Headers)
        {
            Console.WriteLine($"  {header.Key}: {string.Join(", ", header.Value)}");
        }
        
        var response = await base.SendAsync(request, cancellationToken);
        
        Console.WriteLine($"✅ Response: {response.StatusCode}");
        
        return response;
    }
}

// Dans MauiProgram.cs
builder.Services.AddHttpClient("DjangoAPI", client =>
{
    client.BaseAddress = new Uri("http://192.168.52.224:8000");
    client.DefaultRequestHeaders.Add("X-Device-Serial", numeroSerie);
})
.AddHttpMessageHandler<LoggingHandler>();

builder.Services.AddTransient<LoggingHandler>();
```

## 🎯 Résultat Final

Après correction, **TOUTES** vos requêtes doivent retourner **200 OK** :

```
[29/Oct/2025 00:30:46] "GET /api/v2/simple/articles/ HTTP/1.1" 200 1129
[29/Oct/2025 00:30:46] "GET /api/v2/simple/categories/ HTTP/1.1" 200 456
[29/Oct/2025 00:31:17] "POST /api/v2/simple/ventes/ HTTP/1.1" 201 789
```

## 📞 Support

Si le problème persiste après avoir appliqué ces corrections :

1. Vérifier les logs MAUI (console)
2. Vérifier les logs Django (serveur)
3. Partager les deux logs pour diagnostic

**Le header `X-Device-Serial` DOIT être présent dans TOUTES les requêtes !**
