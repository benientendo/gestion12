// ═══════════════════════════════════════════════════════════════════════
// CODE C# MAUI - ANNULATION DE VENTE AVEC RESTRICTION 1 HEURE
// ═══════════════════════════════════════════════════════════════════════

using System;
using System.Collections.ObjectModel;
using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading.Tasks;
using Microsoft.Maui.Controls;

// ═══════════════════════════════════════════════════════════════════════
// MODÈLES DE DONNÉES
// ═══════════════════════════════════════════════════════════════════════

public class VenteHistorique
{
    [JsonPropertyName("numero_facture")]
    public string NumeroFacture { get; set; }
    
    [JsonPropertyName("date_vente")]
    public DateTime DateVente { get; set; }
    
    [JsonPropertyName("montant_total")]
    public string MontantTotal { get; set; }
    
    [JsonPropertyName("mode_paiement")]
    public string ModePaiement { get; set; }
    
    [JsonPropertyName("est_annulee")]
    public bool EstAnnulee { get; set; }
    
    [JsonPropertyName("date_annulation")]
    public DateTime? DateAnnulation { get; set; }
    
    [JsonPropertyName("motif_annulation")]
    public string MotifAnnulation { get; set; }
    
    [JsonPropertyName("lignes")]
    public List<LigneVenteInfo> Lignes { get; set; }
    
    // ⭐ PROPRIÉTÉS CALCULÉES POUR L'UI
    
    /// <summary>
    /// Vérifie si la vente peut être annulée (moins de 1 heure depuis la création)
    /// </summary>
    [JsonIgnore]
    public bool PeutEtreAnnulee
    {
        get
        {
            if (EstAnnulee) return false;
            
            var tempsEcoule = DateTime.Now - DateVente;
            return tempsEcoule.TotalHours <= 1.0;
        }
    }
    
    /// <summary>
    /// Temps restant pour annuler la vente (en minutes)
    /// </summary>
    [JsonIgnore]
    public int MinutesRestantesAnnulation
    {
        get
        {
            if (EstAnnulee) return 0;
            
            var tempsEcoule = DateTime.Now - DateVente;
            var minutesRestantes = 60 - (int)tempsEcoule.TotalMinutes;
            return Math.Max(0, minutesRestantes);
        }
    }
    
    /// <summary>
    /// Texte d'état pour l'UI
    /// </summary>
    [JsonIgnore]
    public string StatutAnnulation
    {
        get
        {
            if (EstAnnulee)
                return $"❌ Annulée le {DateAnnulation?.ToString("dd/MM/yyyy HH:mm")}";
            
            if (PeutEtreAnnulee)
                return $"✅ Annulable ({MinutesRestantesAnnulation} min restantes)";
            
            return "🔒 Délai d'annulation dépassé";
        }
    }
    
    /// <summary>
    /// Couleur du bouton d'annulation
    /// </summary>
    [JsonIgnore]
    public Color CouleurBoutonAnnulation
    {
        get
        {
            if (EstAnnulee)
                return Color.FromArgb("#CCCCCC"); // Gris
            
            if (PeutEtreAnnulee)
                return Color.FromArgb("#FF3B30"); // Rouge
            
            return Color.FromArgb("#CCCCCC"); // Gris désactivé
        }
    }
    
    /// <summary>
    /// Opacité du bouton d'annulation
    /// </summary>
    [JsonIgnore]
    public double OpaciteBoutonAnnulation => PeutEtreAnnulee ? 1.0 : 0.5;
}

public class LigneVenteInfo
{
    [JsonPropertyName("article_nom")]
    public string ArticleNom { get; set; }
    
    [JsonPropertyName("quantite")]
    public int Quantite { get; set; }
    
    [JsonPropertyName("prix_unitaire")]
    public string PrixUnitaire { get; set; }
    
    [JsonPropertyName("total_ligne")]
    public string TotalLigne { get; set; }
}

public class HistoriqueResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }
    
    [JsonPropertyName("count")]
    public int Count { get; set; }
    
    [JsonPropertyName("ventes")]
    public List<VenteHistorique> Ventes { get; set; } = new List<VenteHistorique>();
}

public class AnnulationRequest
{
    [JsonPropertyName("numero_facture")]
    public string NumeroFacture { get; set; }
    
    [JsonPropertyName("motif")]
    public string Motif { get; set; }
}

public class AnnulationResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }
    
    [JsonPropertyName("message")]
    public string Message { get; set; }
    
    [JsonPropertyName("error")]
    public string Error { get; set; }
    
    [JsonPropertyName("code")]
    public string Code { get; set; }
    
    [JsonPropertyName("temps_ecoule_minutes")]
    public int? TempsEcouleMinutes { get; set; }
    
    [JsonPropertyName("delai_max_minutes")]
    public int? DelaiMaxMinutes { get; set; }
}

// ═══════════════════════════════════════════════════════════════════════
// SERVICE D'ANNULATION DE VENTE
// ═══════════════════════════════════════════════════════════════════════

public interface IVenteAnnulationService
{
    Task<HistoriqueResponse> GetHistoriqueAsync(int limit = 50);
    Task<AnnulationResponse> AnnulerVenteAsync(string numeroFacture, string motif);
}

public class VenteAnnulationService : IVenteAnnulationService
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<VenteAnnulationService> _logger;

    public VenteAnnulationService(IHttpClientFactory httpClientFactory, ILogger<VenteAnnulationService> logger)
    {
        _httpClient = httpClientFactory.CreateClient("DjangoAPI");
        _logger = logger;
    }

    /// <summary>
    /// Récupère l'historique des ventes
    /// </summary>
    public async Task<HistoriqueResponse> GetHistoriqueAsync(int limit = 50)
    {
        try
        {
            _logger.LogInformation("🔄 Récupération historique des ventes...");
            
            var url = $"/api/v2/simple/ventes/historique/?limit={limit}";
            var response = await _httpClient.GetAsync(url);
            
            if (response.IsSuccessStatusCode)
            {
                var content = await response.Content.ReadAsStringAsync();
                var result = JsonSerializer.Deserialize<HistoriqueResponse>(content, new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true
                });
                
                if (result != null && result.Success)
                {
                    _logger.LogInformation($"✅ {result.Count} ventes récupérées");
                    return result;
                }
            }
            
            var error = await response.Content.ReadAsStringAsync();
            _logger.LogError($"❌ Erreur récupération historique: {error}");
            return new HistoriqueResponse { Success = false };
        }
        catch (Exception ex)
        {
            _logger.LogError($"❌ Exception GetHistoriqueAsync: {ex.Message}");
            return new HistoriqueResponse { Success = false };
        }
    }

    /// <summary>
    /// Annule une vente (uniquement si moins de 1 heure)
    /// </summary>
    public async Task<AnnulationResponse> AnnulerVenteAsync(string numeroFacture, string motif)
    {
        try
        {
            _logger.LogInformation($"🔄 Annulation vente {numeroFacture}...");
            
            var request = new AnnulationRequest
            {
                NumeroFacture = numeroFacture,
                Motif = motif
            };
            
            var json = JsonSerializer.Serialize(request);
            var content = new StringContent(json, Encoding.UTF8, "application/json");
            
            var response = await _httpClient.PostAsync("/api/v2/simple/ventes/annuler", content);
            var responseContent = await response.Content.ReadAsStringAsync();
            
            var result = JsonSerializer.Deserialize<AnnulationResponse>(responseContent, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true
            });
            
            if (response.IsSuccessStatusCode && result.Success)
            {
                _logger.LogInformation($"✅ Vente {numeroFacture} annulée avec succès");
                return result;
            }
            else
            {
                _logger.LogWarning($"⚠️ Échec annulation: {result.Error} (Code: {result.Code})");
                return result;
            }
        }
        catch (Exception ex)
        {
            _logger.LogError($"❌ Exception AnnulerVenteAsync: {ex.Message}");
            return new AnnulationResponse
            {
                Success = false,
                Error = $"Erreur technique: {ex.Message}",
                Code = "EXCEPTION"
            };
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════
// VIEWMODEL POUR L'HISTORIQUE DES VENTES
// ═══════════════════════════════════════════════════════════════════════

public class HistoriqueVentesViewModel : BaseViewModel
{
    private readonly IVenteAnnulationService _venteService;
    private ObservableCollection<VenteHistorique> _ventes;
    private bool _isLoading;
    private bool _isRefreshing;

    public ObservableCollection<VenteHistorique> Ventes
    {
        get => _ventes;
        set => SetProperty(ref _ventes, value);
    }

    public bool IsLoading
    {
        get => _isLoading;
        set => SetProperty(ref _isLoading, value);
    }

    public bool IsRefreshing
    {
        get => _isRefreshing;
        set => SetProperty(ref _isRefreshing, value);
    }

    public Command LoadVentesCommand { get; }
    public Command<VenteHistorique> AnnulerVenteCommand { get; }
    public Command RefreshCommand { get; }

    public HistoriqueVentesViewModel(IVenteAnnulationService venteService)
    {
        _venteService = venteService;
        Ventes = new ObservableCollection<VenteHistorique>();
        
        LoadVentesCommand = new Command(async () => await LoadVentesAsync());
        AnnulerVenteCommand = new Command<VenteHistorique>(async (vente) => await AnnulerVenteAsync(vente));
        RefreshCommand = new Command(async () => await RefreshAsync());
    }

    public async Task LoadVentesAsync()
    {
        try
        {
            IsLoading = true;
            
            var response = await _venteService.GetHistoriqueAsync(50);
            
            if (response.Success)
            {
                Ventes.Clear();
                foreach (var vente in response.Ventes)
                {
                    Ventes.Add(vente);
                }
                
                Console.WriteLine($"✅ {Ventes.Count} ventes chargées");
            }
            else
            {
                await Application.Current.MainPage.DisplayAlert(
                    "Erreur",
                    "Impossible de charger l'historique des ventes",
                    "OK"
                );
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ Erreur LoadVentesAsync: {ex.Message}");
            await Application.Current.MainPage.DisplayAlert(
                "Erreur",
                $"Erreur technique: {ex.Message}",
                "OK"
            );
        }
        finally
        {
            IsLoading = false;
        }
    }

    public async Task RefreshAsync()
    {
        try
        {
            IsRefreshing = true;
            await LoadVentesAsync();
        }
        finally
        {
            IsRefreshing = false;
        }
    }

    public async Task AnnulerVenteAsync(VenteHistorique vente)
    {
        if (vente == null) return;

        // ⭐ VALIDATION CÔTÉ CLIENT : Vérifier le délai de 1 heure
        if (!vente.PeutEtreAnnulee)
        {
            string message;
            if (vente.EstAnnulee)
            {
                message = "Cette vente a déjà été annulée.";
            }
            else
            {
                message = $"Le délai d'annulation (1 heure) est dépassé.\n\n" +
                         $"Cette vente a été effectuée il y a plus d'une heure et ne peut plus être annulée.";
            }
            
            await Application.Current.MainPage.DisplayAlert(
                "Annulation impossible",
                message,
                "OK"
            );
            return;
        }

        // Demander confirmation
        var confirmer = await Application.Current.MainPage.DisplayAlert(
            "Confirmer l'annulation",
            $"Voulez-vous vraiment annuler la vente {vente.NumeroFacture} ?\n\n" +
            $"Montant: {vente.MontantTotal} CDF\n" +
            $"Date: {vente.DateVente:dd/MM/yyyy HH:mm}\n\n" +
            $"⏱️ Temps restant: {vente.MinutesRestantesAnnulation} minutes",
            "Annuler la vente",
            "Retour"
        );

        if (!confirmer) return;

        // Demander le motif
        var motif = await Application.Current.MainPage.DisplayPromptAsync(
            "Motif d'annulation",
            "Veuillez indiquer la raison de l'annulation:",
            placeholder: "Ex: Erreur de caisse, client insatisfait...",
            maxLength: 200
        );

        if (string.IsNullOrWhiteSpace(motif))
        {
            await Application.Current.MainPage.DisplayAlert(
                "Annulation",
                "Un motif est requis pour annuler une vente.",
                "OK"
            );
            return;
        }

        try
        {
            IsLoading = true;

            var response = await _venteService.AnnulerVenteAsync(vente.NumeroFacture, motif);

            if (response.Success)
            {
                await Application.Current.MainPage.DisplayAlert(
                    "✅ Succès",
                    $"La vente {vente.NumeroFacture} a été annulée avec succès.\n\n" +
                    $"Le stock a été restauré.",
                    "OK"
                );

                // Recharger l'historique
                await LoadVentesAsync();
            }
            else
            {
                string errorMessage = response.Error;
                
                // Message personnalisé selon le code d'erreur
                if (response.Code == "CANCELLATION_TIMEOUT")
                {
                    errorMessage = $"Le délai d'annulation (1 heure) est dépassé.\n\n" +
                                 $"Temps écoulé: {response.TempsEcouleMinutes} minutes\n" +
                                 $"Délai maximum: {response.DelaiMaxMinutes} minutes";
                }
                else if (response.Code == "ALREADY_CANCELLED")
                {
                    errorMessage = "Cette vente a déjà été annulée.";
                }
                
                await Application.Current.MainPage.DisplayAlert(
                    "❌ Échec de l'annulation",
                    errorMessage,
                    "OK"
                );
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ Erreur AnnulerVenteAsync: {ex.Message}");
            await Application.Current.MainPage.DisplayAlert(
                "Erreur",
                $"Erreur technique lors de l'annulation: {ex.Message}",
                "OK"
            );
        }
        finally
        {
            IsLoading = false;
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════
// CONFIGURATION DANS MauiProgram.cs
// ═══════════════════════════════════════════════════════════════════════

/*
// Ajouter dans MauiProgram.cs:

builder.Services.AddSingleton<IVenteAnnulationService, VenteAnnulationService>();
builder.Services.AddTransient<HistoriqueVentesViewModel>();
*/

// ═══════════════════════════════════════════════════════════════════════
// XAML - PAGE HISTORIQUE DES VENTES
// ═══════════════════════════════════════════════════════════════════════

/*
<?xml version="1.0" encoding="utf-8" ?>
<ContentPage xmlns="http://schemas.microsoft.com/dotnet/2021/maui"
             xmlns:x="http://schemas.microsoft.com/winfx/2009/xaml"
             x:Class="VotreApplication.Pages.HistoriqueVentesPage"
             Title="Historique des Ventes">
    
    <RefreshView IsRefreshing="{Binding IsRefreshing}"
                 Command="{Binding RefreshCommand}">
        
        <CollectionView ItemsSource="{Binding Ventes}"
                        SelectionMode="None">
            
            <CollectionView.EmptyView>
                <StackLayout Padding="40" VerticalOptions="Center">
                    <Label Text="📋 Aucune vente enregistrée"
                           FontSize="18"
                           HorizontalOptions="Center"
                           TextColor="#999999"/>
                </StackLayout>
            </CollectionView.EmptyView>
            
            <CollectionView.ItemTemplate>
                <DataTemplate>
                    <Frame Margin="15,10" 
                           Padding="15" 
                           CornerRadius="12"
                           HasShadow="True"
                           BorderColor="#E0E0E0"
                           BackgroundColor="White">
                        
                        <Grid RowDefinitions="Auto,Auto,Auto,Auto,Auto" 
                              ColumnDefinitions="*,Auto"
                              RowSpacing="8">
                            
                            <!-- Numéro de facture -->
                            <Label Grid.Row="0" Grid.Column="0"
                                   Text="{Binding NumeroFacture}"
                                   FontSize="18"
                                   FontAttributes="Bold"
                                   TextColor="#333333"/>
                            
                            <!-- Montant -->
                            <Label Grid.Row="0" Grid.Column="1"
                                   Text="{Binding MontantTotal, StringFormat='{0} CDF'}"
                                   FontSize="18"
                                   FontAttributes="Bold"
                                   TextColor="#007AFF"
                                   HorizontalOptions="End"/>
                            
                            <!-- Date -->
                            <Label Grid.Row="1" Grid.Column="0" Grid.ColumnSpan="2"
                                   Text="{Binding DateVente, StringFormat='📅 {0:dd/MM/yyyy HH:mm}'}"
                                   FontSize="14"
                                   TextColor="#666666"/>
                            
                            <!-- Mode de paiement -->
                            <Label Grid.Row="2" Grid.Column="0"
                                   Text="{Binding ModePaiement, StringFormat='💳 {0}'}"
                                   FontSize="14"
                                   TextColor="#666666"/>
                            
                            <!-- Statut d'annulation -->
                            <Label Grid.Row="3" Grid.Column="0" Grid.ColumnSpan="2"
                                   Text="{Binding StatutAnnulation}"
                                   FontSize="13"
                                   FontAttributes="Italic"
                                   TextColor="#888888"/>
                            
                            <!-- Bouton d'annulation -->
                            <Button Grid.Row="4" Grid.Column="0" Grid.ColumnSpan="2"
                                    Text="🗑️ Annuler cette vente"
                                    Command="{Binding Source={RelativeSource AncestorType={x:Type local:HistoriqueVentesViewModel}}, Path=AnnulerVenteCommand}"
                                    CommandParameter="{Binding .}"
                                    IsEnabled="{Binding PeutEtreAnnulee}"
                                    BackgroundColor="{Binding CouleurBoutonAnnulation}"
                                    TextColor="White"
                                    Opacity="{Binding OpaciteBoutonAnnulation}"
                                    CornerRadius="8"
                                    Padding="12,8"
                                    Margin="0,8,0,0"/>
                            
                        </Grid>
                    </Frame>
                </DataTemplate>
            </CollectionView.ItemTemplate>
            
        </CollectionView>
    </RefreshView>
    
    <!-- Indicateur de chargement -->
    <ActivityIndicator IsRunning="{Binding IsLoading}"
                       IsVisible="{Binding IsLoading}"
                       Color="#007AFF"
                       VerticalOptions="Center"
                       HorizontalOptions="Center"/>
    
</ContentPage>
*/

// ═══════════════════════════════════════════════════════════════════════
// EXEMPLE D'UTILISATION
// ═══════════════════════════════════════════════════════════════════════

/*
// Dans le code-behind de la page (HistoriqueVentesPage.xaml.cs):

public partial class HistoriqueVentesPage : ContentPage
{
    private readonly HistoriqueVentesViewModel _viewModel;

    public HistoriqueVentesPage(HistoriqueVentesViewModel viewModel)
    {
        InitializeComponent();
        _viewModel = viewModel;
        BindingContext = _viewModel;
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        await _viewModel.LoadVentesAsync();
    }
}
*/

// ═══════════════════════════════════════════════════════════════════════
// FONCTIONNALITÉS IMPLÉMENTÉES
// ═══════════════════════════════════════════════════════════════════════

/*
✅ Validation côté client : Bouton désactivé si > 1 heure
✅ Validation côté serveur : API rejette si > 1 heure
✅ Affichage du temps restant : Minutes restantes affichées
✅ Statut visuel : Couleur et opacité du bouton selon l'état
✅ Messages d'erreur personnalisés : Selon le code d'erreur
✅ Confirmation avant annulation : Double vérification
✅ Demande de motif : Obligatoire pour traçabilité
✅ Rafraîchissement automatique : Pull-to-refresh
✅ Gestion des erreurs : Try-catch avec messages clairs
✅ Restauration du stock : Automatique côté serveur
*/
