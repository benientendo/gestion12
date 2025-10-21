# Guide de Migration MAUI - Architecture Multi-Boutiques

## 🎯 Objectif
Adapter le client MAUI existant pour supporter la nouvelle architecture multi-boutiques avec authentification par boutique.

## 📋 Modifications Nécessaires dans MAUI

### 1. **Modèles de Données**

#### A. Nouveau modèle Boutique.cs
```csharp
public class Boutique
{
    public int Id { get; set; }
    public string Nom { get; set; } = string.Empty;
    public string CodeBoutique { get; set; } = string.Empty;
    public string TypeCommerce { get; set; } = string.Empty;
    public string Devise { get; set; } = "CDF";
    public string Commercant { get; set; } = string.Empty;
    public bool EstActive { get; set; } = true;
}
```

#### B. Nouveau modèle Terminal.cs
```csharp
public class Terminal
{
    public int Id { get; set; }
    public string NomTerminal { get; set; } = string.Empty;
    public string NumeroSerie { get; set; } = string.Empty;
    public string NomUtilisateur { get; set; } = string.Empty;
    public string CleApi { get; set; } = string.Empty;
    public Boutique? Boutique { get; set; }
    public bool EstActif { get; set; } = true;
}
```

#### C. Modification Article.cs
```csharp
public class Article
{
    // Propriétés existantes...
    
    // Nouvelles propriétés
    public int BoutiqueId { get; set; }
    public string BoutiqueNom { get; set; } = string.Empty;
    public bool EstActif { get; set; } = true;
}
```

### 2. **Service d'Authentification**

#### Nouveau BoutiqueAuthService.cs
```csharp
public class BoutiqueAuthService
{
    private readonly HttpClient _httpClient;
    private readonly ISecureStorage _secureStorage;
    
    public async Task<AuthResult> AuthentiquerTerminalAsync(string numeroSerie, string nomTerminal, string nomUtilisateur)
    {
        var authData = new
        {
            numero_serie = numeroSerie,
            nom_terminal = nomTerminal,
            nom_utilisateur = nomUtilisateur,
            version_app = AppInfo.VersionString
        };
        
        var response = await _httpClient.PostAsJsonAsync("/api/auth/terminal/", authData);
        
        if (response.IsSuccessStatusCode)
        {
            var result = await response.Content.ReadFromJsonAsync<AuthResponse>();
            
            // Sauvegarder les informations de session
            await _secureStorage.SetAsync("token_session", result.TokenSession);
            await _secureStorage.SetAsync("terminal_id", result.TerminalId.ToString());
            await _secureStorage.SetAsync("boutique_info", JsonSerializer.Serialize(result.Boutique));
            
            return new AuthResult { Success = true, Boutique = result.Boutique };
        }
        
        return new AuthResult { Success = false, Error = "Authentification échouée" };
    }
    
    public async Task<Boutique?> GetBoutiqueActuelleAsync()
    {
        var boutiqueJson = await _secureStorage.GetAsync("boutique_info");
        if (!string.IsNullOrEmpty(boutiqueJson))
        {
            return JsonSerializer.Deserialize<Boutique>(boutiqueJson);
        }
        return null;
    }
}
```

### 3. **Modification des Services API**

#### A. ArticleApiService.cs - Modifications
```csharp
public class ArticleApiService
{
    // Ajouter l'en-tête d'authentification
    private async Task<HttpClient> GetAuthenticatedClientAsync()
    {
        var client = _httpClient;
        var token = await SecureStorage.GetAsync("token_session");
        if (!string.IsNullOrEmpty(token))
        {
            client.DefaultRequestHeaders.Add("X-MAUI-Token", token);
        }
        return client;
    }
    
    // Modifier les méthodes existantes
    public async Task<List<Article>> GetArticlesAsync()
    {
        var client = await GetAuthenticatedClientAsync();
        var response = await client.GetAsync("/api/articles/boutique/");
        
        if (response.IsSuccessStatusCode)
        {
            var result = await response.Content.ReadFromJsonAsync<ArticlesResponse>();
            return result.Articles;
        }
        
        return new List<Article>();
    }
    
    public async Task<Article?> GetArticleByCodeAsync(string code)
    {
        var client = await GetAuthenticatedClientAsync();
        var response = await client.GetAsync($"/api/articles/boutique/par_code/?code={code}");
        
        if (response.IsSuccessStatusCode)
        {
            var result = await response.Content.ReadFromJsonAsync<ArticleResponse>();
            return result.Article;
        }
        
        return null;
    }
}
```

#### B. VenteApiService.cs - Modifications
```csharp
public async Task<bool> FinaliserVenteAsync(Vente vente)
{
    var client = await GetAuthenticatedClientAsync();
    
    var venteData = new
    {
        token_session = await SecureStorage.GetAsync("token_session"),
        numero_facture = vente.NumeroFacture,
        montant_total = vente.MontantTotal,
        mode_paiement = vente.ModePaiement,
        nom_client = vente.NomClient,
        telephone_client = vente.TelephoneClient,
        lignes = vente.Lignes.Select(l => new
        {
            article_id = l.ArticleId,
            quantite = l.Quantite,
            prix_unitaire = l.PrixUnitaire
        }).ToList()
    };
    
    var response = await client.PostAsJsonAsync("/api/ventes/boutique/finaliser_vente/", venteData);
    return response.IsSuccessStatusCode;
}
```

### 4. **Interface Utilisateur**

#### A. Page de Configuration Initiale
```xml
<!-- ConfigurationPage.xaml -->
<ContentPage x:Class="VenteMagazin.Views.ConfigurationPage"
             Title="Configuration Terminal">
    <ScrollView>
        <StackLayout Padding="20">
            <Label Text="Configuration du Terminal MAUI" 
                   FontSize="24" FontAttributes="Bold" 
                   HorizontalOptions="Center" Margin="0,0,0,30"/>
            
            <Frame BackgroundColor="LightBlue" Padding="15" Margin="0,0,0,20">
                <StackLayout>
                    <Label Text="Informations du Terminal" FontAttributes="Bold"/>
                    
                    <Label Text="Numéro de Série:"/>
                    <Entry x:Name="EntryNumeroSerie" Placeholder="Ex: TERM001"/>
                    
                    <Label Text="Nom du Terminal:"/>
                    <Entry x:Name="EntryNomTerminal" Placeholder="Ex: Caisse 1"/>
                    
                    <Label Text="Nom de l'Utilisateur:"/>
                    <Entry x:Name="EntryNomUtilisateur" Placeholder="Ex: Jean Dupont"/>
                </StackLayout>
            </Frame>
            
            <Button Text="Se Connecter à la Boutique" 
                    Clicked="OnConnecterClicked"
                    BackgroundColor="Green" TextColor="White"/>
                    
            <Label x:Name="LabelStatut" Text="" 
                   HorizontalOptions="Center" Margin="0,20,0,0"/>
        </StackLayout>
    </ScrollView>
</ContentPage>
```

#### B. Affichage des Informations Boutique
```xml
<!-- Ajouter dans MainPage.xaml -->
<Frame BackgroundColor="LightGray" Padding="10" Margin="5">
    <StackLayout Orientation="Horizontal">
        <Label Text="🏪" FontSize="20"/>
        <StackLayout>
            <Label Text="{Binding BoutiqueNom}" FontAttributes="Bold"/>
            <Label Text="{Binding TypeCommerce}" FontSize="12"/>
        </StackLayout>
    </StackLayout>
</Frame>
```

### 5. **ViewModel Modifications**

#### A. Nouveau BoutiqueViewModel.cs
```csharp
public class BoutiqueViewModel : BaseViewModel
{
    private Boutique? _boutiqueActuelle;
    private Terminal? _terminalActuel;
    
    public Boutique? BoutiqueActuelle
    {
        get => _boutiqueActuelle;
        set => SetProperty(ref _boutiqueActuelle, value);
    }
    
    public string BoutiqueNom => BoutiqueActuelle?.Nom ?? "Non connecté";
    public string TypeCommerce => BoutiqueActuelle?.TypeCommerce ?? "";
    
    public async Task ChargerInformationsBoutiqueAsync()
    {
        var authService = DependencyService.Get<BoutiqueAuthService>();
        BoutiqueActuelle = await authService.GetBoutiqueActuelleAsync();
    }
}
```

#### B. Modification VenteViewModel.cs
```csharp
public class VenteViewModel : BaseViewModel
{
    private BoutiqueViewModel _boutiqueViewModel;
    
    public VenteViewModel(BoutiqueViewModel boutiqueViewModel)
    {
        _boutiqueViewModel = boutiqueViewModel;
    }
    
    public async Task FinaliserVenteAsync()
    {
        // Vérifier que nous sommes connectés à une boutique
        if (_boutiqueViewModel.BoutiqueActuelle == null)
        {
            await Application.Current.MainPage.DisplayAlert("Erreur", 
                "Vous devez être connecté à une boutique pour finaliser une vente.", "OK");
            return;
        }
        
        // Logique de finalisation existante...
    }
}
```

### 6. **Configuration et Injection de Dépendances**

#### MauiProgram.cs - Ajouts
```csharp
public static class MauiProgram
{
    public static MauiApp CreateMauiApp()
    {
        var builder = MauiApp.CreateBuilder();
        builder
            .UseMauiApp<App>()
            .ConfigureFonts(fonts =>
            {
                fonts.AddFont("OpenSans-Regular.ttf", "OpenSansRegular");
            });
        
        // Services existants...
        
        // Nouveaux services
        builder.Services.AddSingleton<BoutiqueAuthService>();
        builder.Services.AddSingleton<BoutiqueViewModel>();
        
        // Modifier les services existants pour inclure BoutiqueViewModel
        builder.Services.AddTransient<VenteViewModel>();
        
        return builder.Build();
    }
}
```

## 🔄 Plan de Migration

### Phase 1: Préparation
1. Sauvegarder l'application MAUI actuelle
2. Créer une branche de développement
3. Ajouter les nouveaux modèles

### Phase 2: Services
1. Implémenter BoutiqueAuthService
2. Modifier ArticleApiService et VenteApiService
3. Tester l'authentification

### Phase 3: Interface
1. Créer ConfigurationPage
2. Modifier MainPage pour afficher les infos boutique
3. Adapter les ViewModels

### Phase 4: Tests
1. Tester avec une boutique de démonstration
2. Vérifier la synchronisation des données
3. Valider les ventes multi-boutiques

## 🚀 Déploiement

1. **Configuration Django**: Appliquer les migrations
2. **Création des données**: Créer commerçant, boutique et terminal de test
3. **Test MAUI**: Configurer l'application avec le nouveau terminal
4. **Validation**: Effectuer des ventes de test
5. **Formation**: Former les utilisateurs à la nouvelle interface
