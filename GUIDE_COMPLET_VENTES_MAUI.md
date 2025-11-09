# 🛒 GUIDE COMPLET - Système de Vente MAUI

## 🎯 Fonctionnalités Automatiques Backend

Quand MAUI envoie une vente, le backend Django fait **AUTOMATIQUEMENT** :

### ✅ 1. Mise à Jour du Stock
- Décrémente `quantite_stock` de chaque article vendu
- Vérifie le stock disponible avant validation
- Retourne erreur si stock insuffisant

### ✅ 2. Création Historique
- Crée un `MouvementStock` pour chaque article
- Type : `VENTE`
- Référence : Numéro de facture
- Traçabilité complète

### ✅ 3. Calcul du CA
- Calcule automatiquement `montant_total` de la vente
- Somme de tous les sous-totaux (prix × quantité)
- Disponible dans les statistiques

### ✅ 4. Association Terminal
- Lie la vente au terminal MAUI
- Enregistre l'IP et la version de l'app
- Permet le suivi par boutique

## 📡 API Endpoints Disponibles

### Base URL
```
http://192.168.52.224:8000/api/v2/simple/
```

### 1️⃣ Créer une Vente
```
POST /ventes/
Header: X-Device-Serial: 0a1badae951f8473
```

**Body JSON :**
```json
{
    "numero_facture": "VENTE-001",
    "mode_paiement": "CASH",
    "paye": true,
    "lignes": [
        {
            "article_id": 6,
            "quantite": 2,
            "prix_unitaire": 100000.00
        },
        {
            "article_id": 7,
            "quantite": 1,
            "prix_unitaire": 40000.00
        }
    ]
}
```

**Réponse Succès :**
```json
{
    "success": true,
    "vente": {
        "id": 123,
        "numero_facture": "VENTE-001",
        "montant_total": 240000.00,
        "mode_paiement": "CASH",
        "date_vente": "2025-10-28T03:00:00",
        "lignes": [
            {
                "article_nom": "samsung s24",
                "quantite": 2,
                "prix_unitaire": 100000.00,
                "sous_total": 200000.00
            },
            {
                "article_nom": "battery iphone",
                "quantite": 1,
                "prix_unitaire": 40000.00,
                "sous_total": 40000.00
            }
        ]
    },
    "boutique_id": 2,
    "terminal_id": 1
}
```

**Erreurs Possibles :**
- `INSUFFICIENT_STOCK` : Stock insuffisant
- `ARTICLE_NOT_FOUND` : Article inexistant
- `TERMINAL_NOT_FOUND` : Terminal non trouvé

### 2️⃣ Historique des Ventes
```
GET /ventes/historique/
Header: X-Device-Serial: 0a1badae951f8473
```

**Paramètres Optionnels :**
- `limit` : Nombre de ventes (défaut: 50)
- `date_debut` : Date ISO (ex: 2025-10-01T00:00:00)
- `date_fin` : Date ISO

**Réponse :**
```json
{
    "success": true,
    "boutique_id": 2,
    "boutique_nom": "messie vanza",
    "statistiques": {
        "total_ventes": 15,
        "chiffre_affaires": "1500000.00"
    },
    "ventes": [
        {
            "id": 123,
            "numero_facture": "VENTE-001",
            "date_vente": "2025-10-28T03:00:00",
            "montant_total": "240000.00",
            "mode_paiement": "CASH",
            "paye": true,
            "terminal": "Terminal messie vanza",
            "lignes": [...]
        }
    ],
    "count": 15
}
```

### 3️⃣ Statistiques Boutique
```
GET /statistiques/
Header: X-Device-Serial: 0a1badae951f8473
```

**Réponse :**
```json
{
    "success": true,
    "boutique": {
        "id": 2,
        "nom": "messie vanza",
        "type": "Boutique générale",
        "ville": "Mbanza-Ngungu"
    },
    "statistiques": {
        "articles": {
            "total": 2,
            "stock_bas": 0
        },
        "categories": {
            "total": 1
        },
        "ventes_jour": {
            "nombre": 3,
            "chiffre_affaires": "450000.00"
        },
        "ventes_mois": {
            "nombre": 15,
            "chiffre_affaires": "1500000.00"
        }
    }
}
```

## 💻 Code C# pour MAUI

### 1. Service de Vente

```csharp
public interface IVenteService
{
    Task<VenteResponse> CreerVenteAsync(VenteRequest vente);
    Task<HistoriqueResponse> GetHistoriqueAsync(int limit = 50);
    Task<StatistiquesResponse> GetStatistiquesAsync();
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
        try
        {
            var json = JsonSerializer.Serialize(vente);
            var content = new StringContent(json, Encoding.UTF8, "application/json");
            
            var response = await _httpClient.PostAsync("/api/v2/simple/ventes/", content);
            
            if (response.IsSuccessStatusCode)
            {
                var result = await response.Content.ReadAsStringAsync();
                return JsonSerializer.Deserialize<VenteResponse>(result);
            }
            
            var error = await response.Content.ReadAsStringAsync();
            Console.WriteLine($"❌ Erreur vente: {error}");
            return null;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ Exception: {ex.Message}");
            return null;
        }
    }

    public async Task<HistoriqueResponse> GetHistoriqueAsync(int limit = 50)
    {
        try
        {
            var response = await _httpClient.GetAsync($"/api/v2/simple/ventes/historique/?limit={limit}");
            
            if (response.IsSuccessStatusCode)
            {
                var content = await response.Content.ReadAsStringAsync();
                return JsonSerializer.Deserialize<HistoriqueResponse>(content);
            }
            
            return null;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ Exception: {ex.Message}");
            return null;
        }
    }

    public async Task<StatistiquesResponse> GetStatistiquesAsync()
    {
        try
        {
            var response = await _httpClient.GetAsync("/api/v2/simple/statistiques/");
            
            if (response.IsSuccessStatusCode)
            {
                var content = await response.Content.ReadAsStringAsync();
                return JsonSerializer.Deserialize<StatistiquesResponse>(content);
            }
            
            return null;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ Exception: {ex.Message}");
            return null;
        }
    }
}
```

### 2. Modèles de Données

```csharp
public class VenteRequest
{
    [JsonPropertyName("numero_facture")]
    public string NumeroFacture { get; set; }
    
    [JsonPropertyName("mode_paiement")]
    public string ModePaiement { get; set; } = "CASH";
    
    [JsonPropertyName("paye")]
    public bool Paye { get; set; } = true;
    
    [JsonPropertyName("lignes")]
    public List<LigneVenteRequest> Lignes { get; set; } = new();
}

public class LigneVenteRequest
{
    [JsonPropertyName("article_id")]
    public int ArticleId { get; set; }
    
    [JsonPropertyName("quantite")]
    public int Quantite { get; set; }
    
    [JsonPropertyName("prix_unitaire")]
    public decimal PrixUnitaire { get; set; }
}

public class VenteResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }
    
    [JsonPropertyName("vente")]
    public VenteInfo Vente { get; set; }
    
    [JsonPropertyName("boutique_id")]
    public int BoutiqueId { get; set; }
}

public class VenteInfo
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
    public List<LigneVenteInfo> Lignes { get; set; }
}

public class StatistiquesResponse
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }
    
    [JsonPropertyName("boutique")]
    public BoutiqueInfo Boutique { get; set; }
    
    [JsonPropertyName("statistiques")]
    public Statistiques Stats { get; set; }
}

public class Statistiques
{
    [JsonPropertyName("ventes_jour")]
    public VentesStats VentesJour { get; set; }
    
    [JsonPropertyName("ventes_mois")]
    public VentesStats VentesMois { get; set; }
    
    [JsonPropertyName("articles")]
    public ArticlesStats Articles { get; set; }
}

public class VentesStats
{
    [JsonPropertyName("nombre")]
    public int Nombre { get; set; }
    
    [JsonPropertyName("chiffre_affaires")]
    public string ChiffreAffaires { get; set; }
}
```

### 3. Exemple d'Utilisation

```csharp
public class VenteViewModel
{
    private readonly IVenteService _venteService;
    private ObservableCollection<Article> _panier;

    public async Task FinaliserVenteAsync()
    {
        try
        {
            // Générer numéro de facture
            var numeroFacture = $"VENTE-{DateTime.Now:yyyyMMddHHmmss}";
            
            // Créer la requête
            var venteRequest = new VenteRequest
            {
                NumeroFacture = numeroFacture,
                ModePaiement = "CASH",
                Paye = true,
                Lignes = _panier.Select(article => new LigneVenteRequest
                {
                    ArticleId = article.Id,
                    Quantite = article.QuantiteVendue,
                    PrixUnitaire = decimal.Parse(article.PrixVente)
                }).ToList()
            };
            
            // Envoyer la vente
            var response = await _venteService.CreerVenteAsync(venteRequest);
            
            if (response?.Success == true)
            {
                Console.WriteLine($"✅ Vente créée: {response.Vente.NumeroFacture}");
                Console.WriteLine($"💰 Montant: {response.Vente.MontantTotal} CDF");
                
                // Vider le panier
                _panier.Clear();
                
                // Afficher confirmation
                await Application.Current.MainPage.DisplayAlert(
                    "Succès",
                    $"Vente enregistrée\nMontant: {response.Vente.MontantTotal} CDF",
                    "OK"
                );
            }
            else
            {
                await Application.Current.MainPage.DisplayAlert(
                    "Erreur",
                    "Impossible d'enregistrer la vente",
                    "OK"
                );
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"❌ Erreur: {ex.Message}");
        }
    }
}
```

## 🔄 Flux Complet d'une Vente

```
1. MAUI : Utilisateur scanne articles → Panier
2. MAUI : Clic "Finaliser" → POST /ventes/
3. Django : Vérifie stock disponible
4. Django : Crée la vente
5. Django : Décrémente stock automatiquement
6. Django : Crée MouvementStock
7. Django : Calcule montant_total
8. Django : Retourne confirmation
9. MAUI : Affiche reçu
10. MAUI : Vide le panier
```

## ✅ Ce Qui Est Géré Automatiquement

### Côté Django (Backend)
- ✅ Validation du stock
- ✅ Mise à jour du stock
- ✅ Création historique (MouvementStock)
- ✅ Calcul du CA
- ✅ Association au terminal
- ✅ Enregistrement IP et version app
- ✅ Isolation par boutique

### Côté MAUI (Client)
- ✅ Gestion du panier
- ✅ Scan QR codes
- ✅ Affichage articles
- ✅ Envoi de la vente
- ✅ Affichage confirmation

## 🎯 Résultat Final

Après chaque vente :
- ✅ Stock mis à jour en temps réel
- ✅ Historique complet disponible
- ✅ CA calculé automatiquement
- ✅ Statistiques à jour
- ✅ Traçabilité complète
- ✅ Isolation par boutique garantie

**Tout est automatique, rien à gérer manuellement !** 🚀
