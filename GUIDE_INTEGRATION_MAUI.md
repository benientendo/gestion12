# 🚀 GUIDE D'INTÉGRATION MAUI - Synchronisation Articles

## 📋 Checklist d'Implémentation

### ✅ Étape 1 : Modifier MauiProgram.cs

```csharp
public static MauiApp CreateMauiApp()
{
    var builder = MauiApp.CreateBuilder();
    
    // Récupérer le numéro de série
    string numeroSerie = GetDeviceSerialNumber();
    
    // Configurer HttpClient avec le header
    builder.Services.AddHttpClient("DjangoAPI", client =>
    {
        client.BaseAddress = new Uri("http://192.168.52.224:8000");
        client.DefaultRequestHeaders.Add("X-Device-Serial", numeroSerie);
    });
    
    // Enregistrer les services
    builder.Services.AddSingleton<IArticleService, ArticleService>();
    
    return builder.Build();
}

private static string GetDeviceSerialNumber()
{
    #if ANDROID
    return Android.OS.Build.Serial ?? Android.OS.Build.GetSerial();
    #else
    return "0a1badae951f8473"; // Pour les tests
    #endif
}
```

### ✅ Étape 2 : Créer/Modifier ArticleService

```csharp
public class ArticleService : IArticleService
{
    private readonly HttpClient _httpClient;

    public ArticleService(IHttpClientFactory httpClientFactory)
    {
        _httpClient = httpClientFactory.CreateClient("DjangoAPI");
    }

    public async Task<List<Article>> LoadArticlesAsync()
    {
        try
        {
            // URL simple - le header est automatiquement ajouté
            var response = await _httpClient.GetAsync("/api/v2/simple/articles/");
            
            if (response.IsSuccessStatusCode)
            {
                var content = await response.Content.ReadAsStringAsync();
                var result = JsonSerializer.Deserialize<ArticlesResponse>(content);
                
                if (result?.Success == true)
                {
                    Console.WriteLine($"✅ {result.Count} articles récupérés");
                    return result.Articles;
                }
            }
            
            return new List<Article>();
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ Erreur: {ex.Message}");
            return new List<Article>();
        }
    }
}
```

### ✅ Étape 3 : Modèles de Données

```csharp
public class ArticlesResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }
    
    [JsonPropertyName("count")]
    public int Count { get; set; }
    
    [JsonPropertyName("boutique_nom")]
    public string BoutiqueNom { get; set; }
    
    [JsonPropertyName("articles")]
    public List<Article> Articles { get; set; }
}

public class Article
{
    [JsonPropertyName("id")]
    public int Id { get; set; }
    
    [JsonPropertyName("code")]
    public string Code { get; set; }
    
    [JsonPropertyName("nom")]
    public string Nom { get; set; }
    
    [JsonPropertyName("prix_vente")]
    public string PrixVente { get; set; }
    
    [JsonPropertyName("quantite_stock")]
    public int QuantiteStock { get; set; }
}
```

## 🧪 Test avec Votre Boutique

**Boutique :** messie vanza  
**Terminal :** 0a1badae951f8473  
**Articles attendus :** 2

1. battery iphone - 40 000 CDF
2. samsung s24 - 100 000 CDF

## 🔍 Vérification

### Dans les logs MAUI, vous devriez voir :
```
📱 Numéro de série : 0a1badae951f8473
✅ HttpClient configuré
🔄 Chargement articles...
✅ 2 articles récupérés pour messie vanza
```

### Dans les logs Django, vous devriez voir :
```
🔍 Tentative de récupération articles via numéro de série: 0a1badae951f8473
✅ Terminal trouvé: Terminal messie vanza → Boutique ID: 2
```

## ⚠️ Points Importants

1. **Le header X-Device-Serial est OBLIGATOIRE**
2. **Ne pas envoyer boutique_id** - Il est détecté automatiquement
3. **Vérifier le numéro de série** - Doit correspondre à celui dans Django
4. **Isolation garantie** - Chaque terminal ne voit que ses articles

## 🆘 Dépannage

### Problème : Toujours 0 articles
✅ Vérifier que le header X-Device-Serial est bien envoyé  
✅ Vérifier le numéro de série dans les logs  
✅ Vérifier que le terminal existe dans Django  
✅ Vérifier que le terminal est associé à une boutique  

### Problème : Erreur 400
✅ Le header n'est pas envoyé correctement  
✅ Vérifier le nom exact : `X-Device-Serial`  

### Problème : Erreur 404
✅ Terminal non trouvé dans la base Django  
✅ Créer le terminal dans l'interface Django  

## 📞 Support

Si problème, fournir :
1. Le numéro de série du terminal
2. Les logs MAUI (console)
3. Les logs Django (serveur)

## ✅ Résultat Final

Après implémentation :
- ✅ Articles synchronisés automatiquement
- ✅ Pas de gestion manuelle de boutique_id
- ✅ Isolation par boutique garantie
- ✅ Simple et sécurisé
