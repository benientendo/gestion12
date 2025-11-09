# 🎨 GUIDE : Indicateur Visuel de Synchronisation dans MAUI

**Date** : 4 novembre 2025  
**Pour** : Équipe MAUI  
**Objectif** : Afficher l'état de synchronisation des ventes dans l'historique

---

## 🎯 FONCTIONNALITÉ DEMANDÉE

Dans l'historique des ventes de l'application MAUI :
- 🔴 **Ligne ROUGE** : Vente créée localement (pas encore synchronisée avec le serveur)
- 🟢 **Ligne VERTE** : Vente synchronisée avec succès

---

## 📊 ARCHITECTURE RECOMMANDÉE

### 1. Base de Données Locale SQLite (MAUI)

Ajouter un champ `EstSynchronisee` à la table `Ventes` :

```sql
-- Migration SQLite
ALTER TABLE Ventes ADD COLUMN EstSynchronisee INTEGER DEFAULT 0;
-- 0 = Non synchronisée (rouge)
-- 1 = Synchronisée (vert)

ALTER TABLE Ventes ADD COLUMN DateSynchronisation TEXT;
-- Date ISO 8601 de la synchronisation
```

**Ou en C# avec Entity Framework** :

```csharp
public class Vente
{
    public int Id { get; set; }
    public string NumeroFacture { get; set; }
    public DateTime DateVente { get; set; }
    public decimal MontantTotal { get; set; }
    public string ModePaiement { get; set; }
    public bool Paye { get; set; }
    
    // ⭐ NOUVEAU : État de synchronisation
    public bool EstSynchronisee { get; set; } = false;  // Par défaut : non synchronisée
    public DateTime? DateSynchronisation { get; set; }
    
    // Relations
    public List<LigneVente> Lignes { get; set; }
}
```

---

## 🔧 IMPLÉMENTATION C# / MAUI

### 1. Modèle de Données

```csharp
// Models/Vente.cs
public class Vente
{
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    
    public string NumeroFacture { get; set; }
    public DateTime DateVente { get; set; }
    public decimal MontantTotal { get; set; }
    public string ModePaiement { get; set; }
    public bool Paye { get; set; }
    
    // ⭐ État de synchronisation
    public bool EstSynchronisee { get; set; } = false;
    public DateTime? DateSynchronisation { get; set; }
    
    // Relations
    [Ignore]
    public List<LigneVente> Lignes { get; set; } = new List<LigneVente>();
    
    // Pour l'affichage dans la liste
    [Ignore]
    public Color CouleurLigne => EstSynchronisee ? Colors.LightGreen : Colors.LightCoral;
    
    [Ignore]
    public string IconeSync => EstSynchronisee ? "✓" : "⏳";
    
    [Ignore]
    public string TexteStatut => EstSynchronisee 
        ? $"Synchronisée le {DateSynchronisation?.ToString("dd/MM/yyyy HH:mm")}"
        : "En attente de synchronisation";
}

// Models/LigneVente.cs
public class LigneVente
{
    [PrimaryKey, AutoIncrement]
    public int Id { get; set; }
    
    public int VenteId { get; set; }
    public int ArticleId { get; set; }
    public string NomArticle { get; set; }
    public int Quantite { get; set; }
    public decimal PrixUnitaire { get; set; }
    
    [Ignore]
    public decimal SousTotal => Quantite * PrixUnitaire;
}
```

---

### 2. Service de Vente

```csharp
// Services/VenteService.cs
public class VenteService
{
    private readonly SQLiteAsyncConnection _database;
    private readonly HttpClient _httpClient;

    public async Task<int> CreerVenteLocaleAsync(Vente vente)
    {
        // Créer la vente localement
        vente.EstSynchronisee = false;  // ⭐ Marquer comme non synchronisée
        vente.DateSynchronisation = null;
        
        await _database.InsertAsync(vente);
        
        // Insérer les lignes
        foreach (var ligne in vente.Lignes)
        {
            ligne.VenteId = vente.Id;
            await _database.InsertAsync(ligne);
        }
        
        // Tenter la synchronisation immédiate si connecté
        if (await EstConnecteAsync())
        {
            await SynchroniserVenteAsync(vente.Id);
        }
        
        return vente.Id;
    }

    public async Task<bool> SynchroniserVenteAsync(int venteId)
    {
        try
        {
            // Récupérer la vente
            var vente = await _database.Table<Vente>()
                .Where(v => v.Id == venteId)
                .FirstOrDefaultAsync();
            
            if (vente == null || vente.EstSynchronisee)
                return true;  // Déjà synchronisée
            
            // Récupérer les lignes
            var lignes = await _database.Table<LigneVente>()
                .Where(l => l.VenteId == venteId)
                .ToListAsync();
            
            // Préparer le payload
            var payload = new
            {
                numero_facture = vente.NumeroFacture,
                montant_total = vente.MontantTotal,
                mode_paiement = vente.ModePaiement,
                paye = vente.Paye,
                lignes = lignes.Select(l => new
                {
                    article_id = l.ArticleId,
                    quantite = l.Quantite,
                    prix_unitaire = l.PrixUnitaire
                }).ToList()
            };
            
            // Envoyer au serveur
            var json = JsonSerializer.Serialize(new[] { payload });
            var content = new StringContent(json, Encoding.UTF8, "application/json");
            
            var response = await _httpClient.PostAsync(
                "/api/v2/simple/ventes/sync",
                content
            );
            
            if (response.IsSuccessStatusCode)
            {
                // ⭐ Marquer comme synchronisée
                vente.EstSynchronisee = true;
                vente.DateSynchronisation = DateTime.Now;
                await _database.UpdateAsync(vente);
                
                return true;
            }
            
            return false;
        }
        catch (Exception ex)
        {
            // Log l'erreur
            Debug.WriteLine($"Erreur sync vente {venteId}: {ex.Message}");
            return false;
        }
    }

    public async Task<int> SynchroniserToutesVentesAsync()
    {
        // Récupérer toutes les ventes non synchronisées
        var ventesNonSync = await _database.Table<Vente>()
            .Where(v => v.EstSynchronisee == false)
            .ToListAsync();
        
        int compteurReussi = 0;
        
        foreach (var vente in ventesNonSync)
        {
            if (await SynchroniserVenteAsync(vente.Id))
            {
                compteurReussi++;
            }
        }
        
        return compteurReussi;
    }

    private async Task<bool> EstConnecteAsync()
    {
        var current = Connectivity.NetworkAccess;
        return current == NetworkAccess.Internet;
    }
}
```

---

### 3. Interface XAML (Historique des Ventes)

```xml
<!-- Views/HistoriqueVentesPage.xaml -->
<ContentPage xmlns="http://schemas.microsoft.com/dotnet/2021/maui"
             xmlns:x="http://schemas.microsoft.com/winfx/2009/xaml"
             x:Class="VotreApp.Views.HistoriqueVentesPage"
             Title="Historique des Ventes">
    
    <Grid RowDefinitions="Auto,*,Auto">
        
        <!-- En-tête avec bouton sync -->
        <HorizontalStackLayout Grid.Row="0" Padding="10" Spacing="10">
            <Label Text="Historique des Ventes" 
                   FontSize="20" 
                   FontAttributes="Bold"
                   VerticalOptions="Center"/>
            
            <Button Text="🔄 Synchroniser Tout"
                    Command="{Binding SynchroniserToutCommand}"
                    BackgroundColor="{StaticResource Primary}"
                    TextColor="White"/>
            
            <Label Text="{Binding NombreNonSynchronisees, StringFormat='{0} en attente'}"
                   TextColor="Red"
                   VerticalOptions="Center"
                   IsVisible="{Binding ADesVentesNonSync}"/>
        </HorizontalStackLayout>
        
        <!-- Liste des ventes -->
        <CollectionView Grid.Row="1" 
                        ItemsSource="{Binding Ventes}"
                        Margin="10">
            <CollectionView.ItemTemplate>
                <DataTemplate>
                    <!-- ⭐ Ligne colorée selon l'état de synchronisation -->
                    <Frame Padding="10" 
                           Margin="0,5"
                           BackgroundColor="{Binding CouleurLigne}"
                           BorderColor="{Binding CouleurLigne}"
                           CornerRadius="8"
                           HasShadow="True">
                        
                        <Grid ColumnDefinitions="Auto,*,Auto" RowDefinitions="Auto,Auto,Auto">
                            
                            <!-- Icône de statut -->
                            <Label Grid.Column="0" Grid.RowSpan="3"
                                   Text="{Binding IconeSync}"
                                   FontSize="30"
                                   VerticalOptions="Center"
                                   Margin="0,0,10,0"/>
                            
                            <!-- Informations vente -->
                            <Label Grid.Column="1" Grid.Row="0"
                                   Text="{Binding NumeroFacture}"
                                   FontSize="16"
                                   FontAttributes="Bold"/>
                            
                            <Label Grid.Column="1" Grid.Row="1"
                                   Text="{Binding DateVente, StringFormat='Le {0:dd/MM/yyyy à HH:mm}'}"
                                   FontSize="12"
                                   TextColor="Gray"/>
                            
                            <Label Grid.Column="1" Grid.Row="2"
                                   Text="{Binding TexteStatut}"
                                   FontSize="11"
                                   TextColor="DarkGray"
                                   FontAttributes="Italic"/>
                            
                            <!-- Montant -->
                            <Label Grid.Column="2" Grid.RowSpan="3"
                                   Text="{Binding MontantTotal, StringFormat='{0:N0} CDF'}"
                                   FontSize="18"
                                   FontAttributes="Bold"
                                   VerticalOptions="Center"
                                   HorizontalOptions="End"/>
                        </Grid>
                        
                        <!-- Geste pour réessayer la sync -->
                        <Frame.GestureRecognizers>
                            <TapGestureRecognizer 
                                Command="{Binding Source={RelativeSource AncestorType={x:Type ContentPage}}, Path=BindingContext.SynchroniserVenteCommand}"
                                CommandParameter="{Binding .}"/>
                        </Frame.GestureRecognizers>
                    </Frame>
                </DataTemplate>
            </CollectionView.ItemTemplate>
        </CollectionView>
        
        <!-- Barre d'information -->
        <Frame Grid.Row="2" 
               BackgroundColor="LightYellow"
               Padding="10"
               IsVisible="{Binding ADesVentesNonSync}">
            <Label Text="💡 Appuyez sur une vente rouge pour réessayer la synchronisation"
                   FontSize="12"
                   TextColor="DarkOrange"
                   HorizontalTextAlignment="Center"/>
        </Frame>
    </Grid>
</ContentPage>
```

---

### 4. ViewModel

```csharp
// ViewModels/HistoriqueVentesViewModel.cs
public class HistoriqueVentesViewModel : BaseViewModel
{
    private readonly VenteService _venteService;
    private ObservableCollection<Vente> _ventes;
    private int _nombreNonSynchronisees;

    public ObservableCollection<Vente> Ventes
    {
        get => _ventes;
        set => SetProperty(ref _ventes, value);
    }

    public int NombreNonSynchronisees
    {
        get => _nombreNonSynchronisees;
        set
        {
            SetProperty(ref _nombreNonSynchronisees, value);
            OnPropertyChanged(nameof(ADesVentesNonSync));
        }
    }

    public bool ADesVentesNonSync => NombreNonSynchronisees > 0;

    public ICommand SynchroniserToutCommand { get; }
    public ICommand SynchroniserVenteCommand { get; }
    public ICommand ActualiserCommand { get; }

    public HistoriqueVentesViewModel(VenteService venteService)
    {
        _venteService = venteService;
        
        SynchroniserToutCommand = new Command(async () => await SynchroniserTout());
        SynchroniserVenteCommand = new Command<Vente>(async (vente) => await SynchroniserVente(vente));
        ActualiserCommand = new Command(async () => await ChargerVentes());
        
        _ = ChargerVentes();
    }

    private async Task ChargerVentes()
    {
        IsBusy = true;
        
        try
        {
            var ventes = await _venteService.ObtenirToutesVentesAsync();
            Ventes = new ObservableCollection<Vente>(ventes);
            
            NombreNonSynchronisees = ventes.Count(v => !v.EstSynchronisee);
        }
        catch (Exception ex)
        {
            await Application.Current.MainPage.DisplayAlert(
                "Erreur",
                $"Impossible de charger les ventes: {ex.Message}",
                "OK"
            );
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task SynchroniserTout()
    {
        if (NombreNonSynchronisees == 0)
        {
            await Application.Current.MainPage.DisplayAlert(
                "Info",
                "Toutes les ventes sont déjà synchronisées",
                "OK"
            );
            return;
        }

        IsBusy = true;
        
        try
        {
            int reussi = await _venteService.SynchroniserToutesVentesAsync();
            
            await Application.Current.MainPage.DisplayAlert(
                "Synchronisation",
                $"{reussi} vente(s) synchronisée(s) avec succès",
                "OK"
            );
            
            // Recharger la liste
            await ChargerVentes();
        }
        catch (Exception ex)
        {
            await Application.Current.MainPage.DisplayAlert(
                "Erreur",
                $"Erreur de synchronisation: {ex.Message}",
                "OK"
            );
        }
        finally
        {
            IsBusy = false;
        }
    }

    private async Task SynchroniserVente(Vente vente)
    {
        if (vente.EstSynchronisee)
            return;

        IsBusy = true;
        
        try
        {
            bool reussi = await _venteService.SynchroniserVenteAsync(vente.Id);
            
            if (reussi)
            {
                await Application.Current.MainPage.DisplayAlert(
                    "Succès",
                    $"Vente {vente.NumeroFacture} synchronisée",
                    "OK"
                );
                
                // Recharger la liste
                await ChargerVentes();
            }
            else
            {
                await Application.Current.MainPage.DisplayAlert(
                    "Erreur",
                    "Impossible de synchroniser cette vente. Vérifiez votre connexion.",
                    "OK"
                );
            }
        }
        catch (Exception ex)
        {
            await Application.Current.MainPage.DisplayAlert(
                "Erreur",
                $"Erreur: {ex.Message}",
                "OK"
            );
        }
        finally
        {
            IsBusy = false;
        }
    }
}
```

---

## 🎨 STYLES RECOMMANDÉS

### Couleurs dans Resources/Styles/Colors.xaml

```xml
<!-- Couleurs pour l'état de synchronisation -->
<Color x:Key="SyncSuccess">#90EE90</Color>      <!-- Vert clair -->
<Color x:Key="SyncPending">#FFB6C1</Color>      <!-- Rouge clair -->
<Color x:Key="SyncSuccessText">#006400</Color>  <!-- Vert foncé -->
<Color x:Key="SyncPendingText">#8B0000</Color>  <!-- Rouge foncé -->
```

---

## 🔄 FLUX DE SYNCHRONISATION

### 1. Création de Vente Locale

```
Utilisateur finalise vente
    ↓
Vente enregistrée en local avec EstSynchronisee = false
    ↓
Affichage dans l'historique avec LIGNE ROUGE 🔴
    ↓
Si connexion disponible → Tentative sync automatique
    ↓
Si succès → Ligne devient VERTE 🟢
Si échec → Reste ROUGE 🔴
```

### 2. Synchronisation Manuelle

```
Utilisateur clique "Synchroniser Tout"
    ↓
Récupération de toutes les ventes non synchronisées
    ↓
Envoi batch au serveur Django
    ↓
Pour chaque vente réussie:
    - EstSynchronisee = true
    - DateSynchronisation = DateTime.Now
    - Ligne devient VERTE 🟢
```

### 3. Synchronisation au Démarrage

```csharp
// App.xaml.cs
protected override async void OnStart()
{
    base.OnStart();
    
    // Synchroniser automatiquement au démarrage si connecté
    if (Connectivity.NetworkAccess == NetworkAccess.Internet)
    {
        var venteService = ServiceProvider.GetService<VenteService>();
        await venteService.SynchroniserToutesVentesAsync();
    }
}
```

---

## 📱 EXEMPLE VISUEL

### Historique avec Ventes Mixtes

```
┌─────────────────────────────────────────────┐
│  Historique des Ventes    🔄 Synchroniser   │
│                           3 en attente       │
├─────────────────────────────────────────────┤
│                                             │
│  🟢 FAC-20241104-001      50,000 CDF       │
│     Le 04/11/2024 à 10:30                  │
│     Synchronisée le 04/11/2024 10:31       │
│                                             │
│  🔴 FAC-20241104-002      75,000 CDF       │
│     Le 04/11/2024 à 11:15                  │
│     En attente de synchronisation          │
│                                             │
│  🟢 FAC-20241104-003     100,000 CDF       │
│     Le 04/11/2024 à 12:00                  │
│     Synchronisée le 04/11/2024 12:01       │
│                                             │
│  🔴 FAC-20241104-004      45,000 CDF       │
│     Le 04/11/2024 à 13:30                  │
│     En attente de synchronisation          │
│                                             │
├─────────────────────────────────────────────┤
│  💡 Appuyez sur une vente rouge pour       │
│     réessayer la synchronisation           │
└─────────────────────────────────────────────┘
```

---

## ✅ CHECKLIST D'IMPLÉMENTATION

### Phase 1 : Base de Données
- [ ] Ajouter champ `EstSynchronisee` au modèle `Vente`
- [ ] Ajouter champ `DateSynchronisation` au modèle `Vente`
- [ ] Créer migration SQLite
- [ ] Tester la migration

### Phase 2 : Service
- [ ] Modifier `CreerVenteLocaleAsync()` pour marquer `EstSynchronisee = false`
- [ ] Créer `SynchroniserVenteAsync(int venteId)`
- [ ] Créer `SynchroniserToutesVentesAsync()`
- [ ] Ajouter gestion des erreurs

### Phase 3 : Interface
- [ ] Créer propriétés `CouleurLigne`, `IconeSync`, `TexteStatut`
- [ ] Modifier le template XAML pour utiliser les couleurs
- [ ] Ajouter bouton "Synchroniser Tout"
- [ ] Ajouter compteur ventes non synchronisées

### Phase 4 : Tests
- [ ] Tester création vente hors ligne → Ligne rouge
- [ ] Tester synchronisation → Ligne devient verte
- [ ] Tester "Synchroniser Tout"
- [ ] Tester tap sur ligne rouge pour réessayer

---

## 🎯 RÉSULTAT FINAL

✅ **Ventes locales** : Ligne rouge avec icône ⏳  
✅ **Ventes synchronisées** : Ligne verte avec icône ✓  
✅ **Synchronisation manuelle** : Bouton "Synchroniser Tout"  
✅ **Synchronisation individuelle** : Tap sur ligne rouge  
✅ **Compteur** : Nombre de ventes en attente  
✅ **Feedback visuel** : Couleurs et icônes claires  

---

**Document créé le** : 4 novembre 2025 à 13:50  
**Pour** : Équipe MAUI  
**Backend Django** : Prêt et opérationnel ✅
