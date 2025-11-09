# 🚀 DÉMARRAGE RAPIDE - Système de Vente MAUI

## ✅ Tout est Prêt !

Le système Django est **100% configuré et fonctionnel**. Voici comment démarrer :

## 📍 Étape 1 : Démarrer le Serveur Django

```bash
cd C:\Users\PC\Documents\GestionMagazin
python manage.py runserver 192.168.52.224:8000
```

**Vous devriez voir :**
```
Starting development server at http://192.168.52.224:8000/
Quit the server with CTRL-BREAK.
```

## 🧪 Étape 2 : Tester le Système

### Option A : Test Automatique Complet
```bash
# Dans un nouveau terminal (pendant que le serveur tourne)
cd C:\Users\PC\Documents\GestionMagazin
python test_vente_complete.py
```

**Ce test va :**
- ✅ Vérifier le statut de l'API
- ✅ Récupérer les infos du terminal
- ✅ Lister les articles disponibles
- ✅ Créer une vente de test
- ✅ Vérifier la mise à jour du stock
- ✅ Récupérer l'historique
- ✅ Afficher les statistiques

### Option B : Test Manuel Rapide
```bash
# Test 1: Vérifier l'API
curl http://192.168.52.224:8000/api/v2/simple/status/

# Test 2: Récupérer les articles
curl -H "X-Device-Serial: 0a1badae951f8473" http://192.168.52.224:8000/api/v2/simple/articles/

# Test 3: Créer une vente (remplacer article_id et prix)
curl -X POST http://192.168.52.224:8000/api/v2/simple/ventes/ \
  -H "Content-Type: application/json" \
  -H "X-Device-Serial: 0a1badae951f8473" \
  -d "{\"lignes\":[{\"article_id\":6,\"quantite\":1,\"prix_unitaire\":100000.00}]}"
```

## 📊 Étape 3 : Vérifier les Logs

Dans la console où le serveur Django tourne, vous verrez :

**Succès :**
```
🔍 Création vente - Headers: {'X-Device-Serial': '0a1badae951f8473', ...}
🔍 Création vente - Body: {'lignes': [...]}
✅ Boutique détectée automatiquement: 2
📝 Numéro de facture généré automatiquement: VENTE-2-20251029010000
[29/Oct/2025 01:00:00] "POST /api/v2/simple/ventes/ HTTP/1.1" 201 789
```

**Erreur :**
```
❌ Erreur lors de la création de la vente: [détails]
❌ Traceback complet: [...]
❌ Données reçues: {...}
```

## 🔧 Étape 4 : Configuration MAUI

### Code C# à Ajouter dans MauiProgram.cs

```csharp
public static MauiApp CreateMauiApp()
{
    var builder = MauiApp.CreateBuilder();
    
    // Récupérer le numéro de série
    string numeroSerie = GetDeviceSerialNumber();
    
    // Configurer HttpClient GLOBALEMENT
    builder.Services.AddHttpClient("DjangoAPI", client =>
    {
        client.BaseAddress = new Uri("http://192.168.52.224:8000");
        
        // ⭐ IMPORTANT : Ajouter le header ICI
        client.DefaultRequestHeaders.Add("X-Device-Serial", numeroSerie);
        client.DefaultRequestHeaders.Add("Accept", "application/json");
        client.Timeout = TimeSpan.FromSeconds(30);
    });
    
    // Enregistrer les services
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
        return "0a1badae951f8473"; // Fallback
    }
    #else
    return "0a1badae951f8473"; // Pour tests Windows
    #endif
}
```

### Service de Vente MAUI

```csharp
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
            // Format MINIMAL
            var vente = new { lignes = lignes };
            
            var json = JsonSerializer.Serialize(vente);
            var content = new StringContent(json, Encoding.UTF8, "application/json");
            
            // Le header X-Device-Serial est automatiquement ajouté !
            var response = await _httpClient.PostAsync("/api/v2/simple/ventes/", content);
            
            if (response.IsSuccessStatusCode)
            {
                var result = await response.Content.ReadAsStringAsync();
                return JsonSerializer.Deserialize<VenteResponse>(result);
            }
            
            var error = await response.Content.ReadAsStringAsync();
            Console.WriteLine($"❌ Erreur: {error}");
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

## 📋 Checklist Finale

### Django (Backend) ✅
- [x] Serveur démarre sans erreur
- [x] API v2 simple configurée
- [x] Génération automatique numéro facture
- [x] Détection automatique boutique
- [x] Mise à jour stock automatique
- [x] Logs détaillés activés

### MAUI (Client) ⏳
- [ ] HttpClient configuré avec header `X-Device-Serial`
- [ ] URL correcte : `/api/v2/simple/ventes/`
- [ ] Body JSON avec `lignes` uniquement
- [ ] Gestion des réponses 201/400/500

## 🎯 Résultat Attendu

Après configuration MAUI, chaque vente devrait :

1. **MAUI** : Envoie `lignes` avec header `X-Device-Serial`
2. **Django** : Génère `numero_facture` automatiquement
3. **Django** : Détecte la boutique via le numéro de série
4. **Django** : Crée la vente
5. **Django** : Décrémente le stock automatiquement
6. **Django** : Crée l'historique (MouvementStock)
7. **Django** : Calcule le CA automatiquement
8. **Django** : Retourne la confirmation
9. **MAUI** : Affiche le reçu
10. **MAUI** : Vide le panier

## 📚 Documentation Complète

- **VERIFICATION_CONFIGURATION.md** - État actuel du système
- **GUIDE_COMPLET_VENTES_MAUI.md** - Guide complet
- **CORRECTIONS_VENTES_MAUI.md** - Corrections appliquées
- **DEPANNAGE_ERREURS_400.md** - Dépannage erreurs

## 🆘 Besoin d'Aide ?

### Problème : Erreur 400
➡️ Lire `DEPANNAGE_ERREURS_400.md`

### Problème : Erreur 500
➡️ Vérifier les logs Django (traceback complet affiché)

### Problème : Stock non mis à jour
➡️ Vérifier que la vente a bien été créée (code 201)

### Problème : Numéro de série non détecté
➡️ Vérifier que le header `X-Device-Serial` est bien envoyé

## 🎉 C'est Parti !

```bash
# 1. Démarrer Django
python manage.py runserver 192.168.52.224:8000

# 2. Tester (dans un autre terminal)
python test_vente_complete.py

# 3. Si tout fonctionne, configurer MAUI !
```

**Le système est prêt à l'emploi !** 🚀
