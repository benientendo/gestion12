// ============================================================================
// GESTION DES RÉPONSES DE SYNCHRONISATION MAUI - ADAPTÉ
// ============================================================================
// Ce fichier s'intègre avec le code existant dans EXEMPLE_COMPLET_MAUI.cs
// Suit les mêmes patterns: IHttpClientFactory, ILogger, JsonPropertyName
// ============================================================================

using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.Extensions.Logging;

namespace VotreApplication.Services;

// ============================================================================
// FICHIER 1: Models/SyncVentesResponse.cs - MODÈLES DE RÉPONSE
// ============================================================================

public class SyncVentesResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }

    [JsonPropertyName("message")]
    public string Message { get; set; } = "";

    [JsonPropertyName("accepted")]
    public List<string> Accepted { get; set; } = new();

    [JsonPropertyName("rejected")]
    public List<VenteRejeteeInfo> Rejected { get; set; } = new();

    [JsonPropertyName("stock_updates")]
    public List<StockUpdateInfo> StockUpdates { get; set; } = new();

    [JsonPropertyName("statistiques")]
    public SyncStats Statistiques { get; set; } = new();

    [JsonPropertyName("ventes_creees")]
    public int VentesCreees { get; set; }

    [JsonPropertyName("ventes_erreurs")]
    public int VentesErreurs { get; set; }
}

public class VenteRejeteeInfo
{
    [JsonPropertyName("vente_uid")]
    public string VenteUid { get; set; } = "";

    [JsonPropertyName("reason")]
    public string Reason { get; set; } = "";

    [JsonPropertyName("message")]
    public string Message { get; set; } = "";

    [JsonPropertyName("action")]
    public string Action { get; set; } = "";

    [JsonPropertyName("article_id")]
    public int? ArticleId { get; set; }

    [JsonPropertyName("article_nom")]
    public string ArticleNom { get; set; } = "";

    [JsonPropertyName("stock_disponible")]
    public int? StockDisponible { get; set; }

    [JsonPropertyName("stock_demande")]
    public int? StockDemande { get; set; }
}

public class StockUpdateInfo
{
    [JsonPropertyName("article_id")]
    public int ArticleId { get; set; }

    [JsonPropertyName("code")]
    public string Code { get; set; } = "";

    [JsonPropertyName("nom")]
    public string Nom { get; set; } = "";

    [JsonPropertyName("stock_actuel")]
    public int StockActuel { get; set; }

    [JsonPropertyName("prix_actuel")]
    public string PrixActuel { get; set; } = "";
}

public class SyncStats
{
    [JsonPropertyName("total_envoyees")]
    public int TotalEnvoyees { get; set; }

    [JsonPropertyName("reussies")]
    public int Reussies { get; set; }

    [JsonPropertyName("erreurs")]
    public int Erreurs { get; set; }
}

// ============================================================================
// FICHIER 2: Services/ISyncVenteService.cs - INTERFACE
// ============================================================================

public interface ISyncVenteService
{
    Task<SyncVentesResponse> SyncVentesAsync(List<VenteSyncRequest> ventes);
}

public class VenteSyncRequest
{
    [JsonPropertyName("numero_facture")]
    public string NumeroFacture { get; set; } = "";

    [JsonPropertyName("date_vente")]
    public string DateVente { get; set; } = "";

    [JsonPropertyName("mode_paiement")]
    public string ModePaiement { get; set; } = "CASH";

    [JsonPropertyName("lignes")]
    public List<LigneSyncRequest> Lignes { get; set; } = new();
}

public class LigneSyncRequest
{
    [JsonPropertyName("article_id")]
    public int ArticleId { get; set; }

    [JsonPropertyName("quantite")]
    public int Quantite { get; set; }

    [JsonPropertyName("prix_unitaire")]
    public decimal PrixUnitaire { get; set; }
}

// ============================================================================
// FICHIER 3: Services/SyncVenteService.cs - SERVICE
// ============================================================================

public class SyncVenteService : ISyncVenteService
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<SyncVenteService> _logger;

    public SyncVenteService(IHttpClientFactory httpClientFactory, ILogger<SyncVenteService> logger)
    {
        _httpClient = httpClientFactory.CreateClient("DjangoAPI");
        _logger = logger;
    }

    public async Task<SyncVentesResponse> SyncVentesAsync(List<VenteSyncRequest> ventes)
    {
        try
        {
            _logger.LogInformation($"🔄 Début synchronisation de {ventes.Count} vente(s)...");

            var requestData = new { ventes = ventes };
            var json = JsonSerializer.Serialize(requestData);
            var content = new StringContent(json, Encoding.UTF8, "application/json");

            var response = await _httpClient.PostAsync("/api/v2/simple/sync-ventes/", content);
            var responseJson = await response.Content.ReadAsStringAsync();

            if (response.IsSuccessStatusCode)
            {
                var result = JsonSerializer.Deserialize<SyncVentesResponse>(responseJson, 
                    new JsonSerializerOptions { PropertyNameCaseInsensitive = true });

                if (result != null)
                {
                    _logger.LogInformation($"✅ Sync terminée: {result.VentesCreees} créées, {result.VentesErreurs} erreurs");
                    return result;
                }
            }

            _logger.LogError($"❌ Erreur HTTP {response.StatusCode}: {responseJson}");
            return new SyncVentesResponse { Success = false, Message = responseJson };
        }
        catch (Exception ex)
        {
            _logger.LogError($"❌ Exception SyncVentesAsync: {ex.Message}");
            return new SyncVentesResponse { Success = false, Message = ex.Message };
        }
    }
}

// ============================================================================
// FICHIER 4: Helpers/SyncResultHelper.cs - HELPER POUR AFFICHER LES RÉSULTATS
// ============================================================================

public static class SyncResultHelper
{
    /// <summary>
    /// Affiche le résultat de synchronisation à l'utilisateur
    /// </summary>
    public static async Task AfficherResultatSync(SyncVentesResponse response, Page page)
    {
        // Cas 1: Toutes acceptées
        if (response.Rejected.Count == 0 && response.Accepted.Count > 0)
        {
            await page.DisplayAlert(
                "✅ Synchronisation réussie",
                $"{response.VentesCreees} vente(s) synchronisée(s) avec succès.",
                "OK");
            return;
        }

        // Cas 2: Succès partiel
        if (response.Accepted.Count > 0 && response.Rejected.Count > 0)
        {
            bool voirDetails = await page.DisplayAlert(
                "⚠️ Synchronisation partielle",
                $"✅ {response.Accepted.Count} vente(s) acceptée(s)\n" +
                $"❌ {response.Rejected.Count} vente(s) rejetée(s)",
                "Voir détails", "OK");

            if (voirDetails)
            {
                await AfficherDetailsRejets(response.Rejected, page);
            }
            return;
        }

        // Cas 3: Toutes rejetées
        if (response.Rejected.Count > 0)
        {
            await page.DisplayAlert(
                "❌ Échec de synchronisation",
                $"Aucune vente n'a pu être synchronisée.\n" +
                $"{response.Rejected.Count} vente(s) rejetée(s)",
                "Voir détails");

            await AfficherDetailsRejets(response.Rejected, page);
        }
    }

    /// <summary>
    /// Affiche les détails des ventes rejetées
    /// </summary>
    public static async Task AfficherDetailsRejets(List<VenteRejeteeInfo> rejets, Page page)
    {
        foreach (var rejet in rejets)
        {
            string titre = GetTitre(rejet.Reason);
            string message = GetMessage(rejet);
            string conseil = GetConseil(rejet.Reason);

            await page.DisplayAlert(
                titre,
                $"📋 Vente: {rejet.VenteUid}\n\n" +
                $"{message}\n\n" +
                $"💡 {conseil}",
                "Compris");
        }
    }

    private static string GetTitre(string reason) => reason switch
    {
        "INSUFFICIENT_STOCK" => "📦 Stock insuffisant",
        "ARTICLE_NOT_FOUND" => "🔍 Article introuvable",
        "PRIX_MODIFIE" => "💰 Prix modifié",
        "DUPLICATE" => "📋 Doublon",
        _ => "❌ Erreur"
    };

    private static string GetMessage(VenteRejeteeInfo rejet) => rejet.Reason switch
    {
        "INSUFFICIENT_STOCK" => 
            $"Article: {rejet.ArticleNom}\n" +
            $"Demandé: {rejet.StockDemande}\n" +
            $"Disponible: {rejet.StockDisponible}",
        
        "ARTICLE_NOT_FOUND" => 
            "L'article n'existe plus ou a été désactivé.",
        
        "DUPLICATE" => 
            "Cette vente a déjà été enregistrée sur le serveur.",
        
        _ => rejet.Message
    };

    private static string GetConseil(string reason) => reason switch
    {
        "INSUFFICIENT_STOCK" => "Actualisez les stocks et recréez la vente.",
        "ARTICLE_NOT_FOUND" => "Actualisez votre catalogue d'articles.",
        "DUPLICATE" => "Aucune action requise.",
        _ => "Contactez le responsable."
    };
}

// ============================================================================
// FICHIER 5: MauiProgram.cs - ENREGISTREMENT DU SERVICE (À AJOUTER)
// ============================================================================
/*
    // Dans MauiProgram.cs, ajouter:
    builder.Services.AddSingleton<ISyncVenteService, SyncVenteService>();
*/

// ============================================================================
// FICHIER 6: EXEMPLE D'UTILISATION DANS UNE PAGE
// ============================================================================
/*
namespace VotreApplication.Pages;

public partial class VentesPage : ContentPage
{
    private readonly ISyncVenteService _syncService;
    
    public VentesPage(ISyncVenteService syncService)
    {
        InitializeComponent();
        _syncService = syncService;
    }
    
    // ⭐ Bouton synchroniser les ventes en attente
    private async void OnSyncButtonClicked(object sender, EventArgs e)
    {
        try
        {
            // Afficher loading
            SyncButton.IsEnabled = false;
            LoadingIndicator.IsVisible = true;
            
            // Récupérer les ventes locales non synchronisées
            var ventesLocales = await GetVentesNonSynchronisees();
            
            if (ventesLocales.Count == 0)
            {
                await DisplayAlert("Info", "Aucune vente à synchroniser.", "OK");
                return;
            }
            
            // Convertir en format API
            var ventesSync = ventesLocales.Select(v => new VenteSyncRequest
            {
                NumeroFacture = v.NumeroFacture,
                DateVente = v.DateVente.ToString("o"),
                ModePaiement = v.ModePaiement,
                Lignes = v.Lignes.Select(l => new LigneSyncRequest
                {
                    ArticleId = l.ArticleId,
                    Quantite = l.Quantite,
                    PrixUnitaire = l.PrixUnitaire
                }).ToList()
            }).ToList();
            
            // ⭐ Appeler le service de sync
            var response = await _syncService.SyncVentesAsync(ventesSync);
            
            // ⭐ Afficher le résultat à l'utilisateur
            await SyncResultHelper.AfficherResultatSync(response, this);
            
            // Marquer les ventes acceptées comme synchronisées
            foreach (var venteUid in response.Accepted)
            {
                await MarquerVenteSynchronisee(venteUid);
            }
            
            // Mettre à jour les stocks locaux
            foreach (var stock in response.StockUpdates)
            {
                await MettreAJourStockLocal(stock.ArticleId, stock.StockActuel);
            }
        }
        catch (Exception ex)
        {
            await DisplayAlert("Erreur", 
                $"Impossible de synchroniser:\n{ex.Message}", "OK");
        }
        finally
        {
            SyncButton.IsEnabled = true;
            LoadingIndicator.IsVisible = false;
        }
    }
    
    // Méthodes à implémenter selon votre stockage local (SQLite, Preferences, etc.)
    private Task<List<VenteLocale>> GetVentesNonSynchronisees() => Task.FromResult(new List<VenteLocale>());
    private Task MarquerVenteSynchronisee(string venteUid) => Task.CompletedTask;
    private Task MettreAJourStockLocal(int articleId, int stock) => Task.CompletedTask;
}

// Modèle local simple
public class VenteLocale
{
    public string NumeroFacture { get; set; } = "";
    public DateTime DateVente { get; set; }
    public string ModePaiement { get; set; } = "CASH";
    public List<LigneLocale> Lignes { get; set; } = new();
}

public class LigneLocale
{
    public int ArticleId { get; set; }
    public int Quantite { get; set; }
    public decimal PrixUnitaire { get; set; }
}
*/
