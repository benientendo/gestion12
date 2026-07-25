using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading.Tasks;

namespace Gestion_et_ventes.Services
{
    /// <summary>
    /// Service de réconciliation des stocks avec le serveur Django
    /// </summary>
    public class ReconciliationStocksService
    {
        private readonly HttpClient _httpClient;
        private readonly string _baseUrl;

        public ReconciliationStocksService(HttpClient httpClient, string baseUrl)
        {
            _httpClient = httpClient;
            _baseUrl = baseUrl;
        }

        /// <summary>
        /// Envoie l'état des stocks du client au serveur pour réconciliation
        /// </summary>
        public async Task<ReconciliationResponse> ReconcilierStocksAsync(
            int boutiqueId,
            string numeroSerie,
            List<StockClientInfo> stocksClient)
        {
            try
            {
                var request = new ReconciliationRequest
                {
                    boutique_id = boutiqueId,
                    numero_serie = numeroSerie,
                    stocks_client = stocksClient
                };

                var response = await _httpClient.PostAsJsonAsync(
                    $"{_baseUrl}/api/v2/reconciliation/stocks/",
                    request
                );

                response.EnsureSuccessStatusCode();

                var result = await response.Content.ReadFromJsonAsync<ReconciliationResponse>();
                return result;
            }
            catch (HttpRequestException ex)
            {
                Console.WriteLine($"Erreur HTTP lors de la réconciliation: {ex.Message}");
                return new ReconciliationResponse
                {
                    success = false,
                    message = $"Erreur de connexion: {ex.Message}"
                };
            }
            catch (JsonException ex)
            {
                Console.WriteLine($"Erreur JSON lors de la réconciliation: {ex.Message}");
                return new ReconciliationResponse
                {
                    success = false,
                    message = $"Erreur de parsing JSON: {ex.Message}"
                };
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Erreur inattendue lors de la réconciliation: {ex.Message}");
                return new ReconciliationResponse
                {
                    success = false,
                    message = $"Erreur inattendue: {ex.Message}"
                };
            }
        }

        /// <summary>
        /// Collecte l'état des stocks depuis la base locale
        /// </summary>
        public List<StockClientInfo> CollecterStocksLocaux(List<ArticleLocal> articles)
        {
            var stocks = new List<StockClientInfo>();

            foreach (var article in articles)
            {
                stocks.Add(new StockClientInfo
                {
                    article_id = article.Id,
                    stock_client = article.Stock
                });
            }

            return stocks;
        }

        /// <summary>
        /// Lance la réconciliation automatique (périodique)
        /// </summary>
        public async Task<bool> ReconciliationAutomatiqueAsync(
            int boutiqueId,
            string numeroSerie,
            List<ArticleLocal> articles)
        {
            try
            {
                var stocksClient = CollecterStocksLocaux(articles);
                var result = await ReconcilierStocksAsync(boutiqueId, numeroSerie, stocksClient);

                if (result.success)
                {
                    Console.WriteLine($"✅ Réconciliation réussie: {result.message}");
                    Console.WriteLine($"Corrections: {result.corrections?.Count ?? 0}");
                    
                    // Afficher les détails des corrections
                    if (result.corrections != null && result.corrections.Count > 0)
                    {
                        foreach (var correction in result.corrections)
                        {
                            Console.WriteLine(
                                $"  - {correction.article_nom}: " +
                                $"Django={correction.stock_django} → " +
                                $"Client={correction.stock_client} " +
                                $"(diff={correction.difference})"
                            );
                        }
                    }
                    
                    return true;
                }
                else
                {
                    Console.WriteLine($"❌ Réconciliation échouée: {result.message}");
                    return false;
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"❌ Erreur réconciliation automatique: {ex.Message}");
                return false;
            }
        }
    }

    // ===== MODELES DE DONNÉES =====

    public class ReconciliationRequest
    {
        [JsonPropertyName("boutique_id")]
        public int boutique_id { get; set; }

        [JsonPropertyName("numero_serie")]
        public string numero_serie { get; set; }

        [JsonPropertyName("stocks_client")]
        public List<StockClientInfo> stocks_client { get; set; }
    }

    public class StockClientInfo
    {
        [JsonPropertyName("article_id")]
        public int article_id { get; set; }

        [JsonPropertyName("stock_client")]
        public int stock_client { get; set; }
    }

    public class ReconciliationResponse
    {
        [JsonPropertyName("success")]
        public bool success { get; set; }

        [JsonPropertyName("message")]
        public string message { get; set; }

        [JsonPropertyName("corrections")]
        public List<CorrectionInfo> corrections { get; set; }

        [JsonPropertyName("boutique")]
        public string boutique { get; set; }

        [JsonPropertyName("terminal")]
        public string terminal { get; set; }

        [JsonPropertyName("error")]
        public string error { get; set; }

        [JsonPropertyName("code")]
        public string code { get; set; }
    }

    public class CorrectionInfo
    {
        [JsonPropertyName("article_id")]
        public int article_id { get; set; }

        [JsonPropertyName("article_nom")]
        public string article_nom { get; set; }

        [JsonPropertyName("stock_django")]
        public int stock_django { get; set; }

        [JsonPropertyName("stock_client")]
        public int stock_client { get; set; }

        [JsonPropertyName("difference")]
        public int difference { get; set; }
    }

    // ===== MODELE LOCAL (à adapter selon votre structure) =====

    public class ArticleLocal
    {
        public int Id { get; set; }
        public string Nom { get; set; }
        public int Stock { get; set; }
        // ... autres propriétés
    }
}

// ===== EXEMPLE D'UTILISATION =====

/*
namespace Gestion_et_ventes.ViewModels
{
    public class MainViewModel
    {
        private readonly ReconciliationStocksService _reconciliationService;
        private readonly int _boutiqueId;
        private readonly string _numeroSerie;

        public MainViewModel()
        {
            var httpClient = new HttpClient();
            _reconciliationService = new ReconciliationStocksService(
                httpClient,
                "https://votre-serveur.com"
            );
            _boutiqueId = Preferences.Get("boutique_id", 0);
            _numeroSerie = Preferences.Get("numero_serie", "");
        }

        // Réconciliation manuelle (bouton)
        public async Task ReconcilierStocksCommand()
        {
            var articles = await ObtenirArticlesLocauxAsync();
            await _reconciliationService.ReconciliationAutomatiqueAsync(
                _boutiqueId,
                _numeroSerie,
                articles
            );
        }

        // Réconciliation automatique périodique
        public void DemarrerReconciliationPeriodique()
        {
            Device.StartTimer(TimeSpan.FromMinutes(30), async () =>
            {
                var articles = await ObtenirArticlesLocauxAsync();
                await _reconciliationService.ReconciliationAutomatiqueAsync(
                    _boutiqueId,
                    _numeroSerie,
                    articles
                );
                return true; // Continue le timer
            });
        }

        private async Task<List<ArticleLocal>> ObtenirArticlesLocauxAsync()
        {
            // Implémenter selon votre base locale (SQLite, etc.)
            return new List<ArticleLocal>();
        }
    }
}
*/
