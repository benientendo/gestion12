# 🔒 Guide d'Annulation de Vente - Restriction 1 Heure

## 📋 Vue d'ensemble

Le système d'annulation de vente implémente une **restriction de 1 heure** pour garantir l'intégrité des données et éviter les abus. Une vente ne peut être annulée que dans l'heure suivant sa création.

## ⏱️ Règle de Base

```
✅ ANNULABLE : Vente créée il y a moins de 1 heure
❌ NON ANNULABLE : Vente créée il y a plus de 1 heure
```

### Exemple

- **Vente créée à** : 14h00
- **Annulable jusqu'à** : 15h00
- **Après 15h00** : Annulation impossible

## 🛡️ Protection Double Couche

### 1. Validation Côté Client (MAUI)

Le bouton d'annulation est **automatiquement désactivé** après 1 heure :

```csharp
public bool PeutEtreAnnulee
{
    get
    {
        if (EstAnnulee) return false;
        
        var tempsEcoule = DateTime.Now - DateVente;
        return tempsEcoule.TotalHours <= 1.0;
    }
}
```

**Comportement UI :**
- ✅ **Moins de 1h** : Bouton rouge actif, opacité 100%
- ❌ **Plus de 1h** : Bouton gris désactivé, opacité 50%
- 📊 **Affichage** : Minutes restantes affichées en temps réel

### 2. Validation Côté Serveur (Django)

L'API vérifie le délai avant d'annuler :

```python
# Fichier: inventory/api_views_v2_simple.py
from datetime import timedelta

delai_annulation = timedelta(hours=1)
temps_ecoule = timezone.now() - vente.date_vente

if temps_ecoule > delai_annulation:
    return Response({
        'error': 'Le délai d\'annulation (1 heure) est dépassé',
        'code': 'CANCELLATION_TIMEOUT',
        'temps_ecoule_minutes': int(temps_ecoule.total_seconds() / 60),
        'delai_max_minutes': 60
    }, status=status.HTTP_400_BAD_REQUEST)
```

## 🎨 Interface Utilisateur

### Affichage du Statut

Chaque vente affiche son statut d'annulation :

```
✅ Annulable (45 min restantes)     → Vente récente
🔒 Délai d'annulation dépassé       → Plus de 1 heure
❌ Annulée le 30/12/2025 14:30      → Déjà annulée
```

### Couleurs du Bouton

| État | Couleur | Opacité | Cliquable |
|------|---------|---------|-----------|
| Annulable | Rouge (#FF3B30) | 100% | ✅ Oui |
| Délai dépassé | Gris (#CCCCCC) | 50% | ❌ Non |
| Déjà annulée | Gris (#CCCCCC) | 50% | ❌ Non |

## 📱 Flux d'Annulation

### 1. Vérification Client

```
Utilisateur clique sur "Annuler"
    ↓
Vérification locale du délai
    ↓
Si > 1h → Message d'erreur immédiat
Si < 1h → Continuer
```

### 2. Confirmation

```
Affichage popup de confirmation
    ↓
- Numéro de facture
- Montant
- Date de vente
- Temps restant
    ↓
Utilisateur confirme ou annule
```

### 3. Saisie du Motif

```
Demande du motif d'annulation
    ↓
Validation : motif obligatoire
    ↓
Envoi à l'API
```

### 4. Validation Serveur

```
API reçoit la demande
    ↓
Vérification du délai (1h)
    ↓
Si OK : Annulation + Restauration stock
Si KO : Erreur CANCELLATION_TIMEOUT
```

## 🔧 Codes d'Erreur

| Code | Description | Action |
|------|-------------|--------|
| `CANCELLATION_TIMEOUT` | Délai de 1h dépassé | Afficher temps écoulé |
| `ALREADY_CANCELLED` | Vente déjà annulée | Afficher date d'annulation |
| `VENTE_NOT_FOUND` | Vente introuvable | Vérifier numéro facture |
| `TERMINAL_NOT_FOUND` | Terminal non autorisé | Vérifier configuration |

## 📊 Propriétés Calculées

### MinutesRestantesAnnulation

```csharp
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
```

**Exemples :**
- Vente à 14h00, maintenant 14h15 → **45 minutes restantes**
- Vente à 14h00, maintenant 14h50 → **10 minutes restantes**
- Vente à 14h00, maintenant 15h30 → **0 minutes restantes**

## 🔄 Restauration du Stock

Lors d'une annulation réussie, le stock est **automatiquement restauré** :

```python
# Pour chaque ligne de vente
article.quantite_stock += quantite
article.save()

# Création d'un mouvement de stock pour traçabilité
MouvementStock.objects.create(
    article=article,
    type_mouvement='RETOUR',
    quantite=quantite,
    reference_document=f"ANNUL-{vente.numero_facture}",
    commentaire=f"Annulation vente #{vente.numero_facture} - Motif: {motif}"
)
```

## 📝 Traçabilité

Chaque annulation enregistre :

- ✅ **Date et heure** de l'annulation
- ✅ **Motif** de l'annulation
- ✅ **Terminal** ayant effectué l'annulation
- ✅ **Mouvements de stock** générés
- ✅ **Articles** et quantités restaurées

## 🚀 Utilisation dans MAUI

### 1. Enregistrer le Service

```csharp
// Dans MauiProgram.cs
builder.Services.AddSingleton<IVenteAnnulationService, VenteAnnulationService>();
builder.Services.AddTransient<HistoriqueVentesViewModel>();
```

### 2. Charger l'Historique

```csharp
var viewModel = new HistoriqueVentesViewModel(venteService);
await viewModel.LoadVentesAsync();
```

### 3. Annuler une Vente

```csharp
// Le ViewModel gère automatiquement :
// - Vérification du délai
// - Confirmation utilisateur
// - Demande de motif
// - Appel API
// - Gestion des erreurs
await viewModel.AnnulerVenteAsync(vente);
```

## ⚠️ Cas Particuliers

### Vente Annulée Puis Re-tentative

```
❌ Une vente déjà annulée ne peut pas être annulée à nouveau
→ Message : "Cette vente a déjà été annulée"
```

### Délai Dépassé

```
❌ Impossible d'annuler après 1 heure
→ Message : "Le délai d'annulation (1 heure) est dépassé"
→ Affichage du temps écoulé
```

### Terminal Non Autorisé

```
❌ Seul le terminal de la boutique peut annuler
→ Vérification via header X-Device-Serial
```

## 🎯 Avantages de la Restriction

1. **Sécurité** : Évite les annulations abusives
2. **Intégrité** : Garantit la cohérence des données
3. **Traçabilité** : Historique complet des annulations
4. **Performance** : Limite les modifications de stock
5. **Conformité** : Respect des règles comptables

## 📞 API Endpoint

### Annuler une Vente

**URL :** `POST /api/v2/simple/ventes/annuler`

**Headers :**
```
X-Device-Serial: {numero_serie_terminal}
Content-Type: application/json
```

**Body :**
```json
{
    "numero_facture": "VENTE-001",
    "motif": "Erreur de caisse"
}
```

**Réponse Succès (200) :**
```json
{
    "success": true,
    "message": "Vente VENTE-001 annulée avec succès",
    "vente": {
        "numero_facture": "VENTE-001",
        "montant_total": "50000.00",
        "date_vente": "2025-12-30T14:00:00Z",
        "date_annulation": "2025-12-30T14:30:00Z",
        "motif": "Erreur de caisse"
    },
    "stock_restaure": [
        {
            "article_id": 1,
            "code": "ART001",
            "nom": "Article Test",
            "quantite_restauree": 2,
            "stock_avant": 10,
            "stock_apres": 12
        }
    ]
}
```

**Réponse Erreur - Délai Dépassé (400) :**
```json
{
    "error": "Le délai d'annulation (1 heure) est dépassé",
    "code": "CANCELLATION_TIMEOUT",
    "date_vente": "2025-12-30T12:00:00Z",
    "temps_ecoule_minutes": 150,
    "delai_max_minutes": 60
}
```

## ✅ Checklist d'Implémentation

- [x] Validation côté serveur (Django)
- [x] Validation côté client (MAUI)
- [x] Interface utilisateur avec statut
- [x] Bouton désactivé automatiquement
- [x] Affichage du temps restant
- [x] Messages d'erreur personnalisés
- [x] Restauration automatique du stock
- [x] Traçabilité complète
- [x] Documentation complète

## 🔍 Tests Recommandés

### Test 1 : Annulation Réussie
```
1. Créer une vente
2. Immédiatement après, tenter l'annulation
3. ✅ Vérifier : Annulation réussie, stock restauré
```

### Test 2 : Délai Dépassé
```
1. Créer une vente
2. Attendre 1h05
3. Tenter l'annulation
4. ✅ Vérifier : Erreur CANCELLATION_TIMEOUT
```

### Test 3 : Double Annulation
```
1. Créer une vente
2. Annuler la vente
3. Tenter une nouvelle annulation
4. ✅ Vérifier : Erreur ALREADY_CANCELLED
```

### Test 4 : Interface Utilisateur
```
1. Afficher l'historique
2. ✅ Vérifier : Boutons corrects selon l'état
3. ✅ Vérifier : Minutes restantes affichées
4. ✅ Vérifier : Couleurs et opacité correctes
```

---

**Date de mise en œuvre :** 30 Décembre 2025  
**Version :** 1.0  
**Statut :** ✅ Opérationnel
