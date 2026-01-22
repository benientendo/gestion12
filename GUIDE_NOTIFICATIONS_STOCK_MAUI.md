# Guide d'Implémentation - Notifications de Stock pour MAUI

## 📋 Vue d'ensemble

Ce système permet de **notifier automatiquement les clients MAUI** lorsque du stock est ajouté à leur point de vente. Les notifications sont créées automatiquement côté backend Django et peuvent être consultées via l'API REST.

## 🎯 Fonctionnalités

### Côté Backend (Django)

✅ **Création automatique de notifications** via Django Signals lorsque :
- Du stock est ajouté (mouvement de type `ENTREE`)
- Un ajustement de stock positif est effectué (mouvement de type `AJUSTEMENT`)

✅ **Modèle NotificationStock** avec :
- Titre et message personnalisés
- Informations sur l'article (nom, code, quantité ajoutée, stock actuel)
- Statut de lecture (lue/non lue)
- Données supplémentaires (prix, devise, catégorie, etc.)
- Lien vers le mouvement de stock et l'article

✅ **API REST complète** pour gérer les notifications depuis MAUI

## 🔌 Endpoints API Disponibles

### Base URL
```
http://votre-serveur/api/v2/notifications/
```

### 1. Liste des notifications
**GET** `/api/v2/notifications/`

**Headers requis :**
```
X-Device-Serial: <numero_serie_du_terminal>
```

**Query Parameters (optionnel) :**
- `lue=true|false` : Filtrer par statut de lecture

**Réponse :**
```json
{
  "count": 15,
  "non_lues": 5,
  "results": [
    {
      "id": 1,
      "client_nom": "Terminal Principal",
      "boutique_nom": "Ma Boutique",
      "type_notification": "STOCK_AJOUT",
      "type_notification_display": "Ajout de stock",
      "titre": "Nouveau stock disponible: Coca-Cola",
      "message": "L'article 'Coca-Cola' (COCA-001) a été ajouté au stock.\nQuantité ajoutée: 50\nStock actuel: 150\n",
      "article_nom": "Coca-Cola",
      "article_code": "COCA-001",
      "quantite_ajoutee": 50,
      "stock_actuel": 150,
      "lue": false,
      "date_lecture": null,
      "date_creation": "2026-01-21T03:30:00Z",
      "donnees_supplementaires": {
        "article_id": 123,
        "prix_vente": "1500.00",
        "devise": "CDF",
        "categorie": "Boissons"
      }
    }
  ]
}
```

---

### 2. Notifications non lues uniquement
**GET** `/api/v2/notifications/unread/`

**Headers requis :**
```
X-Device-Serial: <numero_serie_du_terminal>
```

**Réponse :**
```json
{
  "count": 5,
  "results": [...]
}
```

---

### 3. Nombre de notifications non lues
**GET** `/api/v2/notifications/count_unread/`

**Headers requis :**
```
X-Device-Serial: <numero_serie_du_terminal>
```

**Réponse :**
```json
{
  "count": 5
}
```

---

### 4. Détail d'une notification
**GET** `/api/v2/notifications/{id}/`

**Headers requis :**
```
X-Device-Serial: <numero_serie_du_terminal>
```

**Comportement :** La notification est automatiquement marquée comme lue lors de la consultation.

**Réponse :**
```json
{
  "id": 1,
  "client_info": {
    "id": 1,
    "nom_terminal": "Terminal Principal",
    "numero_serie": "MAUI-001"
  },
  "boutique_info": {
    "id": 1,
    "nom": "Ma Boutique",
    "code_boutique": "BOUT_001"
  },
  "type_notification": "STOCK_AJOUT",
  "type_notification_display": "Ajout de stock",
  "titre": "Nouveau stock disponible: Coca-Cola",
  "message": "L'article 'Coca-Cola' (COCA-001) a été ajouté au stock.\nQuantité ajoutée: 50\nStock actuel: 150\n",
  "article_info": {
    "id": 123,
    "code": "COCA-001",
    "nom": "Coca-Cola",
    "description": "Boisson gazeuse",
    "prix_vente": "1500.00",
    "devise": "CDF",
    "quantite_stock": 150,
    "categorie": "Boissons"
  },
  "mouvement_info": {
    "id": 456,
    "type_mouvement": "ENTREE",
    "quantite": 50,
    "date_mouvement": "2026-01-21T03:30:00Z",
    "commentaire": "Réapprovisionnement",
    "reference_document": "BON-2026-001",
    "utilisateur": "admin"
  },
  "quantite_ajoutee": 50,
  "stock_actuel": 150,
  "lue": true,
  "date_lecture": "2026-01-21T03:35:00Z",
  "date_creation": "2026-01-21T03:30:00Z",
  "donnees_supplementaires": {...}
}
```

---

### 5. Marquer une notification comme lue
**POST** `/api/v2/notifications/{id}/mark_as_read/`

**Headers requis :**
```
X-Device-Serial: <numero_serie_du_terminal>
```

**Réponse :**
```json
{
  "status": "success",
  "message": "Notification marquée comme lue.",
  "notification": {...}
}
```

---

### 6. Marquer toutes les notifications comme lues
**POST** `/api/v2/notifications/mark_all_as_read/`

**Headers requis :**
```
X-Device-Serial: <numero_serie_du_terminal>
```

**Réponse :**
```json
{
  "status": "success",
  "message": "5 notification(s) marquée(s) comme lue(s).",
  "count": 5
}
```

---

### 7. Notifications récentes (dernières 24h)
**GET** `/api/v2/notifications/recent/`

**Headers requis :**
```
X-Device-Serial: <numero_serie_du_terminal>
```

**Réponse :**
```json
{
  "count": 3,
  "non_lues": 2,
  "results": [...]
}
```

---

## 💻 Exemple d'Implémentation MAUI (.NET MAUI)

### 1. Modèle de données

```csharp
public class NotificationStock
{
    public int Id { get; set; }
    public string ClientNom { get; set; }
    public string BoutiqueNom { get; set; }
    public string TypeNotification { get; set; }
    public string TypeNotificationDisplay { get; set; }
    public string Titre { get; set; }
    public string Message { get; set; }
    public string ArticleNom { get; set; }
    public string ArticleCode { get; set; }
    public int QuantiteAjoutee { get; set; }
    public int StockActuel { get; set; }
    public bool Lue { get; set; }
    public DateTime? DateLecture { get; set; }
    public DateTime DateCreation { get; set; }
    public Dictionary<string, object> DonneesSupplementaires { get; set; }
}

public class NotificationsResponse
{
    public int Count { get; set; }
    public int NonLues { get; set; }
    public List<NotificationStock> Results { get; set; }
}
```

### 2. Service de notification

```csharp
public class NotificationService
{
    private readonly HttpClient _httpClient;
    private readonly string _baseUrl = "http://votre-serveur/api/v2/notifications/";
    private readonly string _deviceSerial;

    public NotificationService(HttpClient httpClient, string deviceSerial)
    {
        _httpClient = httpClient;
        _deviceSerial = deviceSerial;
        _httpClient.DefaultRequestHeaders.Add("X-Device-Serial", _deviceSerial);
    }

    // Récupérer toutes les notifications
    public async Task<NotificationsResponse> GetNotificationsAsync()
    {
        var response = await _httpClient.GetAsync(_baseUrl);
        response.EnsureSuccessStatusCode();
        var json = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<NotificationsResponse>(json);
    }

    // Récupérer uniquement les non lues
    public async Task<NotificationsResponse> GetUnreadNotificationsAsync()
    {
        var response = await _httpClient.GetAsync($"{_baseUrl}unread/");
        response.EnsureSuccessStatusCode();
        var json = await response.Content.ReadAsStringAsync();
        return JsonSerializer.Deserialize<NotificationsResponse>(json);
    }

    // Compter les non lues
    public async Task<int> GetUnreadCountAsync()
    {
        var response = await _httpClient.GetAsync($"{_baseUrl}count_unread/");
        response.EnsureSuccessStatusCode();
        var json = await response.Content.ReadAsStringAsync();
        var data = JsonSerializer.Deserialize<Dictionary<string, int>>(json);
        return data["count"];
    }

    // Marquer comme lue
    public async Task<bool> MarkAsReadAsync(int notificationId)
    {
        var response = await _httpClient.PostAsync(
            $"{_baseUrl}{notificationId}/mark_as_read/", 
            null
        );
        return response.IsSuccessStatusCode;
    }

    // Marquer toutes comme lues
    public async Task<int> MarkAllAsReadAsync()
    {
        var response = await _httpClient.PostAsync(
            $"{_baseUrl}mark_all_as_read/", 
            null
        );
        response.EnsureSuccessStatusCode();
        var json = await response.Content.ReadAsStringAsync();
        var data = JsonSerializer.Deserialize<Dictionary<string, object>>(json);
        return Convert.ToInt32(data["count"]);
    }
}
```

### 3. Interface utilisateur suggérée

```xml
<!-- NotificationsPage.xaml -->
<ContentPage xmlns="http://schemas.microsoft.com/dotnet/2021/maui"
             Title="Notifications">
    <StackLayout>
        <!-- Badge de notifications non lues -->
        <Frame BackgroundColor="Red" Padding="5" CornerRadius="10">
            <Label Text="{Binding UnreadCount}" 
                   TextColor="White" 
                   FontSize="12" 
                   HorizontalOptions="Center"/>
        </Frame>

        <!-- Liste des notifications -->
        <CollectionView ItemsSource="{Binding Notifications}">
            <CollectionView.ItemTemplate>
                <DataTemplate>
                    <Frame Padding="10" Margin="5" 
                           BackgroundColor="{Binding Lue, Converter={StaticResource BoolToColorConverter}}">
                        <StackLayout>
                            <Label Text="{Binding Titre}" 
                                   FontSize="16" 
                                   FontAttributes="Bold"/>
                            <Label Text="{Binding Message}" 
                                   FontSize="14"/>
                            <Label Text="{Binding ArticleNom}" 
                                   FontSize="12" 
                                   TextColor="Gray"/>
                            <Label Text="{Binding DateCreation, StringFormat='Le {0:dd/MM/yyyy à HH:mm}'}" 
                                   FontSize="10" 
                                   TextColor="Gray"/>
                            
                            <!-- Bouton pour voir les détails -->
                            <Button Text="Voir les détails" 
                                    Command="{Binding Source={RelativeSource AncestorType={x:Type local:NotificationsViewModel}}, Path=ViewDetailsCommand}"
                                    CommandParameter="{Binding .}"/>
                        </StackLayout>
                    </Frame>
                </DataTemplate>
            </CollectionView.ItemTemplate>
        </CollectionView>

        <!-- Bouton pour marquer toutes comme lues -->
        <Button Text="Marquer toutes comme lues" 
                Command="{Binding MarkAllAsReadCommand}"/>
    </StackLayout>
</ContentPage>
```

### 4. ViewModel

```csharp
public class NotificationsViewModel : INotifyPropertyChanged
{
    private readonly NotificationService _notificationService;
    private ObservableCollection<NotificationStock> _notifications;
    private int _unreadCount;

    public ObservableCollection<NotificationStock> Notifications
    {
        get => _notifications;
        set
        {
            _notifications = value;
            OnPropertyChanged();
        }
    }

    public int UnreadCount
    {
        get => _unreadCount;
        set
        {
            _unreadCount = value;
            OnPropertyChanged();
        }
    }

    public ICommand RefreshCommand { get; }
    public ICommand ViewDetailsCommand { get; }
    public ICommand MarkAllAsReadCommand { get; }

    public NotificationsViewModel(NotificationService notificationService)
    {
        _notificationService = notificationService;
        RefreshCommand = new Command(async () => await LoadNotificationsAsync());
        ViewDetailsCommand = new Command<NotificationStock>(async (notif) => await ViewDetailsAsync(notif));
        MarkAllAsReadCommand = new Command(async () => await MarkAllAsReadAsync());
        
        LoadNotificationsAsync();
    }

    private async Task LoadNotificationsAsync()
    {
        try
        {
            var response = await _notificationService.GetNotificationsAsync();
            Notifications = new ObservableCollection<NotificationStock>(response.Results);
            UnreadCount = response.NonLues;
        }
        catch (Exception ex)
        {
            await Application.Current.MainPage.DisplayAlert("Erreur", 
                $"Impossible de charger les notifications: {ex.Message}", "OK");
        }
    }

    private async Task ViewDetailsAsync(NotificationStock notification)
    {
        // Navigation vers la page de détails
        await Shell.Current.GoToAsync($"notificationdetail?id={notification.Id}");
        
        // Marquer comme lue
        if (!notification.Lue)
        {
            await _notificationService.MarkAsReadAsync(notification.Id);
            notification.Lue = true;
            UnreadCount--;
        }
    }

    private async Task MarkAllAsReadAsync()
    {
        try
        {
            var count = await _notificationService.MarkAllAsReadAsync();
            await Application.Current.MainPage.DisplayAlert("Succès", 
                $"{count} notification(s) marquée(s) comme lue(s)", "OK");
            await LoadNotificationsAsync();
        }
        catch (Exception ex)
        {
            await Application.Current.MainPage.DisplayAlert("Erreur", 
                $"Impossible de marquer les notifications: {ex.Message}", "OK");
        }
    }

    public event PropertyChangedEventHandler PropertyChanged;
    protected void OnPropertyChanged([CallerMemberName] string propertyName = null)
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
    }
}
```

### 5. Polling périodique (optionnel)

```csharp
public class NotificationPollingService
{
    private readonly NotificationService _notificationService;
    private Timer _pollingTimer;

    public event EventHandler<int> UnreadCountChanged;

    public NotificationPollingService(NotificationService notificationService)
    {
        _notificationService = notificationService;
    }

    public void StartPolling(int intervalSeconds = 60)
    {
        _pollingTimer = new Timer(async _ =>
        {
            try
            {
                var count = await _notificationService.GetUnreadCountAsync();
                UnreadCountChanged?.Invoke(this, count);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Erreur polling notifications: {ex.Message}");
            }
        }, null, TimeSpan.Zero, TimeSpan.FromSeconds(intervalSeconds));
    }

    public void StopPolling()
    {
        _pollingTimer?.Dispose();
    }
}
```

## 🎨 Recommandations UX

1. **Badge de notification** : Afficher le nombre de notifications non lues sur l'icône de notification
2. **Indicateur visuel** : Différencier visuellement les notifications lues/non lues (couleur, gras)
3. **Marquage automatique** : Marquer automatiquement comme lue quand l'utilisateur consulte les détails
4. **Rafraîchissement** : Implémenter un pull-to-refresh pour actualiser la liste
5. **Notification push (future)** : Considérer l'ajout de notifications push pour une expérience temps réel

## 🔧 Configuration Backend

Le système est déjà configuré et actif :

✅ Signal Django actif qui crée automatiquement les notifications
✅## 📡 Endpoints API Disponibles

Tous les endpoints sont sous `/api/v2/simple/notifications/` :
✅ Interface d'administration Django pour gérer les notifications manuellement
✅ Index de base de données pour des requêtes optimisées

## 📊 Types de notifications

- `STOCK_AJOUT` : Ajout de stock normal
- `STOCK_TRANSFERT` : Transfert de stock depuis un dépôt
- `STOCK_AJUSTEMENT` : Ajustement manuel de stock

## 🔒 Sécurité

- Authentification par `X-Device-Serial` header
- Chaque client ne voit que ses propres notifications
- Isolation par boutique respectée

## 📝 Notes importantes

1. Les notifications sont créées **automatiquement** à chaque ajout de stock
2. Tous les clients actifs de la boutique reçoivent la notification
3. Les notifications sont **persistées** en base de données
4. Le signal ne crée des notifications que pour les mouvements positifs (`ENTREE`, `AJUSTEMENT`)

## 🚀 Prochaines étapes

Pour l'équipe MAUI :
1. Implémenter le service de notification
2. Créer l'interface utilisateur
3. Ajouter le badge de notification sur l'écran principal
4. Tester avec des données réelles
5. (Optionnel) Implémenter le polling périodique

---

**Date de création :** 21 janvier 2026  
**Version backend :** Django API v2  
**Compatibilité :** .NET MAUI 7.0+
