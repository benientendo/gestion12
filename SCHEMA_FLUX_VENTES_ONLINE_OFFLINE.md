# 🔄 SCHÉMA DES FLUX - Ventes ONLINE vs OFFLINE

**Visualisation des différences entre les deux modes**

---

## 📊 MODE ONLINE (Fonctionne ✅)

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUX MODE ONLINE                              │
└─────────────────────────────────────────────────────────────────┘

1️⃣ UTILISATEUR MAUI
   └─> Scanne article
   └─> Ajoute au panier
   └─> Clique "Finaliser"

2️⃣ APPLICATION MAUI (Connexion active ✅)
   └─> Prépare la vente
       {
         "boutique_id": 2,
         "numero_facture": "VENTE-001",
         "lignes": [...]
       }
   └─> Envoie IMMÉDIATEMENT via HTTP POST
       URL: /api/v2/ventes/
       Header: Authorization: Bearer TOKEN_JWT

3️⃣ DJANGO (api_views_v2.py)
   └─> Reçoit la vente
   └─> Authentifie via JWT ✅
   └─> Trouve le terminal via request.user ✅
   └─> Vérifie le stock ✅
   └─> Crée la vente ✅
   └─> DÉCRÉMENTE LE STOCK ✅
       article.quantite_stock -= quantite
       article.save()
   └─> Crée MouvementStock ✅
   └─> Retourne succès

4️⃣ APPLICATION MAUI
   └─> Reçoit confirmation ✅
   └─> Affiche reçu ✅
   └─> Vide le panier ✅

5️⃣ RÉSULTAT
   ✅ Vente créée
   ✅ Stock mis à jour
   ✅ MouvementStock créé
   ✅ Tout fonctionne !
```

---

## 📊 MODE OFFLINE (Problème ❌)

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUX MODE OFFLINE                             │
└─────────────────────────────────────────────────────────────────┘

1️⃣ UTILISATEUR MAUI
   └─> Scanne article
   └─> Ajoute au panier
   └─> Clique "Finaliser"

2️⃣ APPLICATION MAUI (Pas de connexion ❌)
   └─> Prépare la vente
       {
         "numero_facture": "VENTE-OFFLINE-001",
         "lignes": [...]
       }
   └─> SAUVEGARDE EN LOCAL (SQLite)
       vente.EstSynchronisee = false
   └─> Affiche reçu
   └─> Vide le panier

3️⃣ ATTENTE... (Vente en attente de synchronisation)

4️⃣ CONNEXION RÉTABLIE
   └─> Utilisateur clique "Synchroniser"
       OU
   └─> Synchronisation automatique

5️⃣ APPLICATION MAUI (Synchronisation)
   └─> Récupère les ventes non synchronisées
       ventes = GetVentesNonSynchronisees()
   
   ⚠️ POINT CRITIQUE : Que se passe-t-il ici ?
   
   └─> Prépare les données
       {
         "ventes": [
           {
             "numero_facture": "VENTE-OFFLINE-001",
             "lignes": [...]
           }
         ]
       }
   
   └─> Envoie via HTTP POST
       URL: ??? (Quelle URL ?)
       Header: ??? (Quel header ?)
   
   └─> Reçoit réponse
       Status: ??? (200, 400, 500 ?)
   
   └─> Marque comme synchronisée ???
       vente.EstSynchronisee = true ???

6️⃣ DJANGO (api_views_v2_simple.py)
   └─> Reçoit les ventes ???
   └─> Trouve le terminal via header ???
   └─> Vérifie le stock ???
   └─> Crée les ventes ???
   └─> DÉCRÉMENTE LE STOCK ??? ❌
   └─> Crée MouvementStock ???
   └─> Retourne succès ???

7️⃣ RÉSULTAT
   ❌ Vente créée ? (Peut-être)
   ❌ Stock mis à jour ? (NON - Problème constaté)
   ❌ MouvementStock créé ? (Peut-être)
   ❌ Quelque chose ne fonctionne pas !
```

---

## 🔍 POINTS DE DÉFAILLANCE POSSIBLES

```
┌─────────────────────────────────────────────────────────────────┐
│              OÙ PEUT SE SITUER LE PROBLÈME ?                     │
└─────────────────────────────────────────────────────────────────┘

❌ HYPOTHÈSE 1 : Ventes non récupérées
   └─> GetVentesNonSynchronisees() retourne 0 vente
   └─> Rien n'est envoyé à Django
   └─> Stock ne change pas (normal)

❌ HYPOTHÈSE 2 : Mauvaise URL
   └─> MAUI envoie vers /api/v2/ventes/ (mode ONLINE)
   └─> Au lieu de /api/v2/simple/ventes/sync (mode OFFLINE)
   └─> Django reçoit mais avec mauvais endpoint
   └─> Stock peut ne pas être mis à jour

❌ HYPOTHÈSE 3 : Header manquant
   └─> MAUI n'envoie pas X-Device-Serial
   └─> Django ne trouve pas le terminal
   └─> Erreur 400 retournée
   └─> Vente non créée, stock non mis à jour

❌ HYPOTHÈSE 4 : Erreur HTTP non gérée
   └─> Django retourne erreur (400, 403, 500)
   └─> MAUI ignore l'erreur
   └─> Marque la vente comme synchronisée
   └─> Vente non créée dans Django, stock non mis à jour

❌ HYPOTHÈSE 5 : Format JSON incorrect
   └─> MAUI envoie mauvais format
   └─> Django ne peut pas parser
   └─> Erreur 400 retournée
   └─> Vente non créée, stock non mis à jour
```

---

## ✅ FLUX CORRECT ATTENDU (Mode OFFLINE)

```
┌─────────────────────────────────────────────────────────────────┐
│              FLUX CORRECT MODE OFFLINE                           │
└─────────────────────────────────────────────────────────────────┘

1️⃣ UTILISATEUR MAUI
   └─> Fait une vente OFFLINE
   └─> Vente sauvegardée en local

2️⃣ SYNCHRONISATION
   └─> Connexion rétablie
   └─> Clic "Synchroniser"

3️⃣ APPLICATION MAUI
   ✅ Récupère ventes non synchronisées
      ventes = GetVentesNonSynchronisees()
      → Doit retourner les ventes OFFLINE
   
   ✅ Prépare les données
      {
        "ventes": [
          {
            "numero_facture": "VENTE-OFFLINE-001",
            "mode_paiement": "CASH",
            "paye": true,
            "lignes": [
              {
                "article_id": 6,
                "quantite": 2,
                "prix_unitaire": 100000.00
              }
            ]
          }
        ]
      }
   
   ✅ Envoie via HTTP POST
      URL: /api/v2/simple/ventes/sync
      Header: X-Device-Serial: 0a1badae951f8473
      Body: JSON ci-dessus
   
   ✅ Vérifie la réponse
      if (response.StatusCode != 200)
      {
          // NE PAS marquer comme synchronisée
          return false;
      }
   
   ✅ Parse la réponse
      var result = JsonSerializer.Deserialize<SyncResponse>(content);
      
      if (!result.Success)
      {
          // NE PAS marquer comme synchronisée
          return false;
      }
   
   ✅ Marque comme synchronisée UNIQUEMENT si succès
      foreach (var vente in ventes)
      {
          vente.EstSynchronisee = true;
          vente.DateSynchronisation = DateTime.Now;
      }

4️⃣ DJANGO (api_views_v2_simple.py)
   ✅ Reçoit les ventes
   ✅ Lit le header X-Device-Serial
   ✅ Trouve le terminal
   ✅ Trouve la boutique via terminal.boutique
   ✅ Pour chaque vente:
      ✅ Vérifie le stock disponible
      ✅ Crée la vente
      ✅ DÉCRÉMENTE LE STOCK
         article.quantite_stock -= quantite
         article.save(update_fields=['quantite_stock'])
      ✅ Crée MouvementStock
         MouvementStock.objects.create(
             article=article,
             type_mouvement='VENTE',
             quantite=-quantite,
             commentaire=f"Vente #{numero_facture}"
         )
   ✅ Retourne succès
      {
        "success": true,
        "ventes_creees": 1,
        "ventes_erreurs": 0
      }

5️⃣ RÉSULTAT
   ✅ Vente créée dans Django
   ✅ Stock décrémenté correctement
   ✅ MouvementStock créé pour traçabilité
   ✅ Vente marquée comme synchronisée dans MAUI
   ✅ Tout fonctionne !
```

---

## 🎯 COMPARAISON VISUELLE

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODE ONLINE vs OFFLINE                        │
└─────────────────────────────────────────────────────────────────┘

CARACTÉRISTIQUE          │ ONLINE ✅        │ OFFLINE ❌
─────────────────────────┼──────────────────┼─────────────────
Connexion requise        │ OUI              │ NON (puis OUI)
Envoi immédiat           │ OUI              │ NON (différé)
Sauvegarde locale        │ NON              │ OUI
URL utilisée             │ /api/v2/ventes/  │ /api/v2/simple/ventes/sync
Authentification         │ JWT Token        │ X-Device-Serial
Format données           │ 1 vente          │ N ventes (batch)
Endpoint Django          │ create_vente_v2  │ sync_ventes_simple
Décrémente stock         │ ✅ OUI           │ ✅ OUI (théoriquement)
Fonctionne actuellement  │ ✅ OUI           │ ❌ NON (problème)
```

---

## 🔧 POINTS DE VÉRIFICATION

```
┌─────────────────────────────────────────────────────────────────┐
│              CHECKLIST DE VÉRIFICATION MAUI                      │
└─────────────────────────────────────────────────────────────────┘

[ ] 1. Les ventes OFFLINE sont bien sauvegardées en local
        └─> Vérifier SQLite après une vente OFFLINE

[ ] 2. GetVentesNonSynchronisees() retourne bien les ventes
        └─> Ajouter log: Console.WriteLine($"Ventes: {ventes.Count}")

[ ] 3. L'URL de synchronisation est correcte
        └─> Doit être: /api/v2/simple/ventes/sync
        └─> Ajouter log: Console.WriteLine($"URL: {url}")

[ ] 4. Le header X-Device-Serial est envoyé
        └─> Ajouter log: Console.WriteLine($"Serial: {numeroSerie}")

[ ] 5. Le format JSON est correct
        └─> Doit avoir: { "ventes": [...] }
        └─> Ajouter log: Console.WriteLine($"JSON: {json}")

[ ] 6. La réponse HTTP est vérifiée
        └─> Vérifier: response.StatusCode == 200
        └─> Ajouter log: Console.WriteLine($"Status: {response.StatusCode}")

[ ] 7. Les erreurs sont gérées correctement
        └─> Si erreur: NE PAS marquer comme synchronisée
        └─> Ajouter log: Console.WriteLine($"Erreur: {error}")

[ ] 8. Les ventes sont marquées synchronisées UNIQUEMENT si succès
        └─> Après vérification du status code ET du JSON
```

---

## 🎯 TEST DE VALIDATION

```
┌─────────────────────────────────────────────────────────────────┐
│                    TEST COMPLET                                  │
└─────────────────────────────────────────────────────────────────┘

ÉTAPE 1 : Préparation
   └─> Vérifier stock initial dans Django
       Article 6 = 10 unités

ÉTAPE 2 : Vente OFFLINE
   └─> Désactiver la connexion
   └─> Faire une vente de 2 unités de l'article 6
   └─> Vérifier que la vente est sauvegardée en local
       EstSynchronisee = false

ÉTAPE 3 : Synchronisation
   └─> Réactiver la connexion
   └─> Cliquer "Synchroniser"
   └─> Regarder les logs MAUI

ÉTAPE 4 : Vérification
   └─> Vérifier stock dans Django
       Article 6 = 8 unités ✅
   
   └─> Vérifier MouvementStock dans Django
       Type: VENTE, Quantité: -2 ✅
   
   └─> Vérifier dans MAUI
       EstSynchronisee = true ✅

RÉSULTAT ATTENDU : Stock = 8 unités
RÉSULTAT ACTUEL : Stock = 10 unités ❌
```

---

**Document créé pour visualiser les flux et identifier le problème** 🔍  
**Utilisez ce schéma pour comprendre où se situe la défaillance** 🎯
