// ============================================================================
// EXEMPLE COMPLET - CONFIGURATION MAUI POUR ISOLATION DES VENTES
// ============================================================================
// Ce fichier contient TOUT le code nécessaire pour adapter MAUI
// Copiez-collez les sections dans vos fichiers correspondants
// ============================================================================

// ============================================================================
// FICHIER 1: MauiProgram.cs
// ============================================================================

using Microsoft.Extensions.Logging;

namespace VotreApplication;

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
                fonts.AddFont("OpenSans-Semibold.ttf", "OpenSansSemibold");
            });

        // ⭐ CONFIGURATION CRITIQUE: HttpClient avec numéro de série
        builder.Services.AddHttpClient("DjangoAPI", client =>
        {
            // URL de votre serveur Django
            client.BaseAddress = new Uri("http://10.59.88.224:8000");
            
            // ⭐ AJOUTER LE NUMÉRO DE SÉRIE DANS LES HEADERS
            #if ANDROID
            string numeroSerie = GetDeviceSerialNumber();
            client.DefaultRequestHeaders.Add("X-Device-Serial", numeroSerie);
            
            // Debug: Afficher le numéro de série
            System.Diagnostics.Debug.WriteLine($"📱 Numéro de série configuré: {numeroSerie}");
            #endif
            
            // Timeout
            client.Timeout = TimeSpan.FromSeconds(30);
        });

        // Enregistrer les services
        builder.Services.AddSingleton<IArticleService, ArticleService>();
        builder.Services.AddSingleton<IVenteService, VenteService>();
        builder.Services.AddSingleton<ICategorieService, CategorieService>();

#if DEBUG
        builder.Logging.AddDebug();
#endif

        return builder.Build();
    }

    // ⭐ MÉTHODE POUR RÉCUPÉRER LE NUMÉRO DE SÉRIE
    private static string GetDeviceSerialNumber()
    {
        #if ANDROID
        try
        {
            // Méthode 1: Build.Serial (API < 26)
            string serial = Android.OS.Build.Serial;
            
            // Méthode 2: Build.GetSerial() (API >= 26)
            if (string.IsNullOrEmpty(serial) || serial == "unknown")
            {
                if (Android.OS.Build.VERSION.SdkInt >= Android.OS.BuildVersionCodes.O)
                {
                    serial = Android.OS.Build.GetSerial();
                }
            }
            
            // Si toujours vide, générer un ID unique et le sauvegarder
            if (string.IsNullOrEmpty(serial) || serial == "unknown")
            {
                serial = Preferences.Get("device_serial", null);
                if (string.IsNullOrEmpty(serial))
                {
                    serial = $"MAUI-{Guid.NewGuid().ToString().Substring(0, 8)}";
                    Preferences.Set("device_serial", serial);
                }
            }
            
            return serial;
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"❌ Erreur récupération numéro de série: {ex.Message}");
            
            // Fallback: Utiliser un identifiant unique sauvegardé
            string serial = Preferences.Get("device_serial", null);
            if (string.IsNullOrEmpty(serial))
            {
                serial = $"MAUI-{Guid.NewGuid().ToString().Substring(0, 8)}";
                Preferences.Set("device_serial", serial);
            }
            return serial;
        }
        #else
        // Pour simulateur ou autres plateformes
        return "MAUI-SIMULATOR";
        #endif
    }
}

// ============================================================================
// FICHIER 2: Services/ArticleService.cs
// ============================================================================

using System.Text.Json;

namespace VotreApplication.Services;

public class ArticleService : IArticleService
{
    private readonly HttpClient _httpClient;

    // ⭐ INJECTER IHttpClientFactory au lieu de HttpClient
    public ArticleService(IHttpClientFactory httpClientFactory)
    {
        _httpClient = httpClientFactory.CreateClient("DjangoAPI");
    }

    public async Task<List<Article>> GetArticlesAsync()
    {
        try
        {
            // ⭐ PAS DE boutique_id dans l'URL !
            // Le header X-Device-Serial est automatiquement envoyé
            var response = await _httpClient.GetAsync("/api/v2/simple/articles/");
            
            if (response.IsSuccessStatusCode)
            {
                var content = await response.Content.ReadAsStringAsync();
                var result = JsonSerializer.Deserialize<ArticlesResponse>(content);
                return result?.Articles ?? new List<Article>();
            }
            else
            {
                var error = await response.Content.ReadAsStringAsync();
                System.Diagnostics.Debug.WriteLine($"❌ Erreur API: {error}");
                return new List<Article>();
            }
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"❌ Exception GetArticles: {ex.Message}");
            return new List<Article>();
        }
    }
}

// ============================================================================
// FICHIER 3: Services/VenteService.cs
// ============================================================================

using System.Text;
using System.Text.Json;

namespace VotreApplication.Services;

public class VenteService : IVenteService
{
    private readonly HttpClient _httpClient;

    public VenteService(IHttpClientFactory httpClientFactory)
    {
        _httpClient = httpClientFactory.CreateClient("DjangoAPI");
    }

    public async Task<VenteResponse> CreerVenteAsync(List<LigneVenteRequest> lignes)
    {
        try
        {
            // ⭐ FORMAT MINIMAL - Django gère tout automatiquement
            var vente = new { lignes = lignes };
            
            var json = JsonSerializer.Serialize(vente);
            var content = new StringContent(json, Encoding.UTF8, "application/json");
            
            // ⭐ PAS DE boutique_id, PAS DE numero_facture !
            var response = await _httpClient.PostAsync("/api/v2/simple/ventes/", content);
            
            if (response.IsSuccessStatusCode)
            {
                var result = await response.Content.ReadAsStringAsync();
                return JsonSerializer.Deserialize<VenteResponse>(result);
            }
            else
            {
                var error = await response.Content.ReadAsStringAsync();
                System.Diagnostics.Debug.WriteLine($"❌ Erreur création vente: {error}");
                
                // Tenter de désérialiser l'erreur
                try
                {
                    var errorResponse = JsonSerializer.Deserialize<VenteResponse>(error);
                    return errorResponse;
                }
                catch
                {
                    return new VenteResponse { Success = false, Error = error };
                }
            }
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"❌ Exception création vente: {ex.Message}");
            return new VenteResponse { Success = false, Error = ex.Message };
        }
    }

    public async Task<List<Vente>> GetHistoriqueVentesAsync(int limit = 50)
    {
        try
        {
            // ⭐ PAS DE boutique_id !
            var response = await _httpClient.GetAsync($"/api/v2/simple/ventes/historique/?limit={limit}");
            
            if (response.IsSuccessStatusCode)
            {
                var content = await response.Content.ReadAsStringAsync();
                var result = JsonSerializer.Deserialize<HistoriqueResponse>(content);
                return result?.Ventes ?? new List<Vente>();
            }
            
            return new List<Vente>();
        }
        catch (Exception ex)
        {
            System.Diagnostics.Debug.WriteLine($"❌ Exception historique: {ex.Message}");
            return new List<Vente>();
        }
    }
}

// ============================================================================
// FICHIER 4: Models/LigneVenteRequest.cs
// ============================================================================

using System.Text.Json.Serialization;

namespace VotreApplication.Models;

public class LigneVenteRequest
{
    [JsonPropertyName("article_id")]
    public int ArticleId { get; set; }
    
    [JsonPropertyName("quantite")]
    public int Quantite { get; set; }
    
    [JsonPropertyName("prix_unitaire")]
    public decimal PrixUnitaire { get; set; }
}

// ============================================================================
// FICHIER 5: Models/VenteResponse.cs
// ============================================================================

using System.Text.Json.Serialization;

namespace VotreApplication.Models;

public class VenteResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }
    
    [JsonPropertyName("vente")]
    public VenteDetail Vente { get; set; }
    
    [JsonPropertyName("error")]
    public string Error { get; set; }
    
    [JsonPropertyName("code")]
    public string Code { get; set; }
}

public class VenteDetail
{
    [JsonPropertyName("id")]
    public int Id { get; set; }
    
    [JsonPropertyName("numero_facture")]
    public string NumeroFacture { get; set; }
    
    [JsonPropertyName("montant_total")]
    public decimal MontantTotal { get; set; }
    
    [JsonPropertyName("date_vente")]
    public DateTime DateVente { get; set; }
    
    [JsonPropertyName("lignes")]
    public List<LigneVenteDetail> Lignes { get; set; }
}

public class LigneVenteDetail
{
    [JsonPropertyName("article")]
    public ArticleDetail Article { get; set; }
    
    [JsonPropertyName("quantite")]
    public int Quantite { get; set; }
    
    [JsonPropertyName("prix_unitaire")]
    public decimal PrixUnitaire { get; set; }
    
    [JsonPropertyName("sous_total")]
    public decimal SousTotal { get; set; }
}

public class ArticleDetail
{
    [JsonPropertyName("id")]
    public int Id { get; set; }
    
    [JsonPropertyName("nom")]
    public string Nom { get; set; }
    
    [JsonPropertyName("code")]
    public string Code { get; set; }
}

// ============================================================================
// FICHIER 6: Pages/DebugPage.xaml.cs (PAGE DE TEST)
// ============================================================================

namespace VotreApplication.Pages;

public partial class DebugPage : ContentPage
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly IArticleService _articleService;
    private readonly IVenteService _venteService;
    
    public DebugPage(
        IHttpClientFactory httpClientFactory,
        IArticleService articleService,
        IVenteService venteService)
    {
        InitializeComponent();
        _httpClientFactory = httpClientFactory;
        _articleService = articleService;
        _venteService = venteService;
    }
    
    private async void OnTestNumeroSerieClicked(object sender, EventArgs e)
    {
        var httpClient = _httpClientFactory.CreateClient("DjangoAPI");
        var serialHeader = httpClient.DefaultRequestHeaders
            .FirstOrDefault(h => h.Key == "X-Device-Serial");
        
        if (serialHeader.Value != null)
        {
            var numeroSerie = serialHeader.Value.FirstOrDefault();
            await DisplayAlert("✅ Succès", 
                $"Numéro de série configuré:\n{numeroSerie}", "OK");
        }
        else
        {
            await DisplayAlert("❌ Erreur", 
                "Header X-Device-Serial manquant!\n\n" +
                "Vérifiez la configuration dans MauiProgram.cs", "OK");
        }
    }
    
    private async void OnTestArticlesClicked(object sender, EventArgs e)
    {
        try
        {
            var articles = await _articleService.GetArticlesAsync();
            
            if (articles.Count > 0)
            {
                var message = $"{articles.Count} articles récupérés:\n\n";
                foreach (var article in articles.Take(5))
                {
                    message += $"• {article.Nom} - {article.PrixVente} CDF\n";
                }
                
                await DisplayAlert("✅ Succès", message, "OK");
            }
            else
            {
                await DisplayAlert("⚠️ Attention", 
                    "Aucun article trouvé pour cette boutique.\n\n" +
                    "Vérifiez dans Django Admin que:\n" +
                    "1. Le terminal existe\n" +
                    "2. Le terminal est lié à une boutique\n" +
                    "3. La boutique a des articles actifs", "OK");
            }
        }
        catch (Exception ex)
        {
            await DisplayAlert("❌ Erreur", 
                $"Exception: {ex.Message}\n\n" +
                $"Vérifiez que le serveur Django est accessible.", "OK");
        }
    }
    
    private async void OnTestVenteClicked(object sender, EventArgs e)
    {
        try
        {
            // Récupérer les articles
            var articles = await _articleService.GetArticlesAsync();
            if (articles.Count == 0)
            {
                await DisplayAlert("❌ Erreur", 
                    "Aucun article disponible pour créer une vente de test.", "OK");
                return;
            }
            
            // Prendre le premier article
            var article = articles[0];
            
            // Créer une ligne de vente
            var lignes = new List<LigneVenteRequest>
            {
                new LigneVenteRequest
                {
                    ArticleId = article.Id,
                    Quantite = 1,
                    PrixUnitaire = article.PrixVente
                }
            };
            
            // Créer la vente
            var result = await _venteService.CreerVenteAsync(lignes);
            
            if (result?.Success == true)
            {
                await DisplayAlert("✅ Succès", 
                    $"Vente créée avec succès!\n\n" +
                    $"Numéro: {result.Vente.NumeroFacture}\n" +
                    $"Montant: {result.Vente.MontantTotal} CDF\n" +
                    $"Date: {result.Vente.DateVente:dd/MM/yyyy HH:mm}\n\n" +
                    $"Vérifiez dans le backend Django que cette vente\n" +
                    $"est visible UNIQUEMENT pour votre boutique.", "OK");
            }
            else
            {
                await DisplayAlert("❌ Erreur", 
                    $"Erreur lors de la création:\n\n" +
                    $"{result?.Error ?? "Erreur inconnue"}\n\n" +
                    $"Code: {result?.Code ?? "N/A"}", "OK");
            }
        }
        catch (Exception ex)
        {
            await DisplayAlert("❌ Exception", 
                $"Exception: {ex.Message}", "OK");
        }
    }
}

// ============================================================================
// FICHIER 7: Pages/DebugPage.xaml
// ============================================================================

/*
<?xml version="1.0" encoding="utf-8" ?>
<ContentPage xmlns="http://schemas.microsoft.com/dotnet/2021/maui"
             xmlns:x="http://schemas.microsoft.com/winfx/2009/xaml"
             x:Class="VotreApplication.Pages.DebugPage"
             Title="Tests API Django">
    
    <ScrollView>
        <VerticalStackLayout Padding="20" Spacing="20">
            
            <!-- En-tête -->
            <Frame BackgroundColor="#007AFF" CornerRadius="10" Padding="15">
                <VerticalStackLayout Spacing="5">
                    <Label Text="🧪 Tests d'Intégration API" 
                           FontSize="24" 
                           FontAttributes="Bold"
                           TextColor="White"
                           HorizontalOptions="Center"/>
                    <Label Text="Vérifiez que l'isolation fonctionne" 
                           FontSize="14"
                           TextColor="White"
                           HorizontalOptions="Center"/>
                </VerticalStackLayout>
            </Frame>
            
            <!-- Instructions -->
            <Frame BackgroundColor="#F0F0F0" CornerRadius="10" Padding="15">
                <VerticalStackLayout Spacing="10">
                    <Label Text="📋 Instructions" 
                           FontSize="18" 
                           FontAttributes="Bold"/>
                    <Label Text="1. Testez le numéro de série" FontSize="14"/>
                    <Label Text="2. Récupérez les articles" FontSize="14"/>
                    <Label Text="3. Créez une vente de test" FontSize="14"/>
                    <Label Text="4. Vérifiez dans Django que la vente est isolée" FontSize="14"/>
                </VerticalStackLayout>
            </Frame>
            
            <!-- Boutons de test -->
            <Button Text="Test 1: Vérifier Numéro de Série"
                    Clicked="OnTestNumeroSerieClicked"
                    BackgroundColor="#007AFF"
                    TextColor="White"
                    HeightRequest="50"
                    FontSize="16"
                    FontAttributes="Bold"/>
            
            <Button Text="Test 2: Récupérer Articles"
                    Clicked="OnTestArticlesClicked"
                    BackgroundColor="#34C759"
                    TextColor="White"
                    HeightRequest="50"
                    FontSize="16"
                    FontAttributes="Bold"/>
            
            <Button Text="Test 3: Créer Vente de Test"
                    Clicked="OnTestVenteClicked"
                    BackgroundColor="#FF9500"
                    TextColor="White"
                    HeightRequest="50"
                    FontSize="16"
                    FontAttributes="Bold"/>
            
            <!-- Informations -->
            <Frame BackgroundColor="#FFF3CD" BorderColor="#FFC107" CornerRadius="10" Padding="15">
                <VerticalStackLayout Spacing="5">
                    <Label Text="💡 Important" 
                           FontSize="16" 
                           FontAttributes="Bold"
                           TextColor="#856404"/>
                    <Label Text="Après le Test 3, connectez-vous au backend Django et vérifiez que la vente est visible UNIQUEMENT pour votre boutique." 
                           FontSize="14"
                           TextColor="#856404"/>
                </VerticalStackLayout>
            </Frame>
            
        </VerticalStackLayout>
    </ScrollView>
</ContentPage>
*/

// ============================================================================
// FIN DU FICHIER
// ============================================================================
