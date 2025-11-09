# 🔧 AMÉLIORATIONS OPTIONNELLES - Backend Django

**Date** : 4 novembre 2025  
**Priorité** : 🟡 OPTIONNEL (Le système fonctionne déjà)

---

## 📋 RÉSUMÉ

Votre backend Django est **déjà fonctionnel** pour la synchronisation offline-first. Ce document propose des améliorations **optionnelles** pour renforcer la traçabilité et la robustesse.

---

## 🎯 AMÉLIORATION 1 : Enrichir le modèle MouvementStock

### Problème actuel

Le modèle `MouvementStock` est minimal et ne stocke pas assez d'informations pour un audit complet.

### Solution proposée

Ajouter des champs pour une traçabilité complète :

```python
# inventory/models.py

class MouvementStock(models.Model):
    """Mouvements de stock avec traçabilité complète."""
    
    TYPES = [
        ('ENTREE', 'Entrée de stock'),
        ('SORTIE', 'Sortie de stock'),
        ('AJUSTEMENT', 'Ajustement'),
        ('VENTE', 'Vente'),
        ('RETOUR', 'Retour client'),  # ⭐ NOUVEAU
    ]
    
    # Champs existants
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='mouvements')
    type_mouvement = models.CharField(max_length=20, choices=TYPES)
    quantite = models.IntegerField(help_text="Négatif pour sortie, positif pour entrée")
    date_mouvement = models.DateTimeField(auto_now_add=True)
    commentaire = models.TextField(blank=True)
    
    # ⭐ NOUVEAUX CHAMPS pour meilleure traçabilité
    stock_avant = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Stock avant le mouvement"
    )
    stock_apres = models.IntegerField(
        null=True, 
        blank=True, 
        help_text="Stock après le mouvement"
    )
    reference_document = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="Numéro de facture, bon de livraison, etc."
    )
    utilisateur = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="Nom d'utilisateur ou device_serial"
    )
    
    class Meta:
        ordering = ['-date_mouvement']
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        indexes = [
            models.Index(fields=['article', 'date_mouvement'], name='mouvement_article_date_idx'),
            models.Index(fields=['type_mouvement'], name='mouvement_type_idx'),
            models.Index(fields=['reference_document'], name='mouvement_ref_idx'),
        ]
    
    def __str__(self):
        return f"{self.type_mouvement} - {self.article.nom} ({self.quantite})"
```

### Migration à créer

```python
# Créer la migration
python manage.py makemigrations

# Appliquer la migration
python manage.py migrate
```

### Modification dans api_views_v2_simple.py

```python
# Ligne 1038-1048 : Améliorer la création du MouvementStock

# AVANT (actuel)
article.quantite_stock -= quantite
article.save(update_fields=['quantite_stock'])

MouvementStock.objects.create(
    article=article,
    type_mouvement='VENTE',
    quantite=-quantite,
    commentaire=f"Vente #{vente.numero_facture} - Prix: {prix_unitaire} CDF"
)

# APRÈS (amélioré)
stock_avant = article.quantite_stock  # Capturer AVANT la modification
article.quantite_stock -= quantite
article.save(update_fields=['quantite_stock'])

MouvementStock.objects.create(
    article=article,
    type_mouvement='VENTE',
    quantite=-quantite,
    stock_avant=stock_avant,  # ⭐ NOUVEAU
    stock_apres=article.quantite_stock,  # ⭐ NOUVEAU
    reference_document=vente.numero_facture,  # ⭐ NOUVEAU
    utilisateur=terminal.nom_terminal,  # ⭐ NOUVEAU
    commentaire=f"Vente #{vente.numero_facture} - Prix: {prix_unitaire} CDF"
)
```

### Avantages

- ✅ Traçabilité complète : on sait exactement quel était le stock avant/après
- ✅ Audit facilité : lien direct avec le document source (numéro de facture)
- ✅ Identification : on sait quel terminal a fait l'opération
- ✅ Réconciliation : vérification facile des écarts de stock

---

## 🎯 AMÉLIORATION 2 : Ajouter des transactions atomiques

### Problème actuel

Si une erreur survient au milieu du traitement d'une vente, certaines lignes peuvent être créées et d'autres non, laissant la base de données dans un état incohérent.

### Solution proposée

Entourer le traitement de chaque vente d'une transaction atomique :

```python
# inventory/api_views_v2_simple.py

from django.db import transaction

# Ligne 947 : Modifier la boucle de traitement
for index, vente_data in enumerate(ventes_data):
    try:
        # ⭐ TRANSACTION ATOMIQUE : Tout ou rien
        with transaction.atomic():
            logger.info(f"🔄 Traitement vente {index + 1}/{len(ventes_data)}")
            
            # ... tout le code existant de traitement de la vente ...
            # (lignes 949-1079)
            
            # Si une exception est levée, TOUT est annulé automatiquement
            # Sinon, TOUT est validé à la fin du bloc with
            
    except Exception as e:
        # La transaction a déjà été rollback automatiquement
        logger.error(f"❌ Erreur création vente {index + 1}: {str(e)}")
        ventes_erreurs.append({
            'index': index + 1,
            'numero_facture': vente_data.get('numero_facture', 'N/A'),
            'erreur': str(e)
        })
```

### Avantages

- ✅ **Cohérence garantie** : Une vente est soit complètement créée, soit pas du tout
- ✅ **Pas de données orphelines** : Si erreur, aucune ligne de vente n'est créée
- ✅ **Stock cohérent** : Le stock n'est décrémenté que si la vente est complète
- ✅ **Rollback automatique** : Pas besoin de nettoyer manuellement en cas d'erreur

---

## 🎯 AMÉLIORATION 3 : Endpoint pour récupérer les mouvements de stock

### Besoin

Permettre à MAUI de consulter l'historique des mouvements de stock pour audit et réconciliation.

### Solution proposée

Créer un nouvel endpoint :

```python
# inventory/api_views_v2_simple.py

@api_view(['GET'])
def get_mouvements_stock(request):
    """
    Récupère les mouvements de stock pour une boutique.
    
    Endpoint: GET /api/v2/simple/mouvements-stock/
    
    Query params:
    - article_id: ID de l'article (optionnel)
    - type_mouvement: Type de mouvement (VENTE, ENTREE, etc.) (optionnel)
    - date_debut: Date de début ISO (optionnel)
    - date_fin: Date de fin ISO (optionnel)
    - limit: Nombre de résultats (défaut: 100, max: 500)
    
    Headers:
    - X-Device-Serial: Numéro de série du terminal (requis)
    """
    # 1. Récupérer le terminal via le header
    numero_serie = (
        request.headers.get('X-Device-Serial') or 
        request.headers.get('Device-Serial') or
        request.headers.get('Serial-Number') or
        request.META.get('HTTP_X_DEVICE_SERIAL')
    )
    
    if not numero_serie:
        return Response({
            'error': 'Header X-Device-Serial requis',
            'code': 'MISSING_SERIAL'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # 2. Trouver le terminal et sa boutique
        terminal = Client.objects.select_related('boutique').get(
            numero_serie=numero_serie,
            est_actif=True
        )
        boutique = terminal.boutique
        
        if not boutique:
            return Response({
                'error': 'Terminal non associé à une boutique',
                'code': 'NO_BOUTIQUE'
            }, status=status.HTTP_400_BAD_REQUEST)
        
    except Client.DoesNotExist:
        return Response({
            'error': 'Terminal non trouvé ou inactif',
            'code': 'TERMINAL_NOT_FOUND'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # 3. ⭐ ISOLATION : Filtrer par articles de la boutique
    mouvements = MouvementStock.objects.filter(
        article__boutique=boutique
    ).select_related('article').order_by('-date_mouvement')
    
    # 4. Filtres optionnels
    article_id = request.GET.get('article_id')
    if article_id:
        mouvements = mouvements.filter(article_id=article_id)
    
    type_mouvement = request.GET.get('type_mouvement')
    if type_mouvement:
        mouvements = mouvements.filter(type_mouvement=type_mouvement)
    
    date_debut = request.GET.get('date_debut')
    if date_debut:
        try:
            from datetime import datetime
            date_debut_obj = datetime.fromisoformat(date_debut.replace('Z', '+00:00'))
            mouvements = mouvements.filter(date_mouvement__gte=date_debut_obj)
        except ValueError:
            pass
    
    date_fin = request.GET.get('date_fin')
    if date_fin:
        try:
            from datetime import datetime
            date_fin_obj = datetime.fromisoformat(date_fin.replace('Z', '+00:00'))
            mouvements = mouvements.filter(date_mouvement__lte=date_fin_obj)
        except ValueError:
            pass
    
    # 5. Limiter les résultats
    limit = min(int(request.GET.get('limit', 100)), 500)  # Max 500
    mouvements = mouvements[:limit]
    
    # 6. Sérialiser
    data = [{
        'id': m.id,
        'article_id': m.article_id,
        'article_nom': m.article.nom,
        'article_code': m.article.code,
        'type_mouvement': m.type_mouvement,
        'quantite': m.quantite,
        'stock_avant': m.stock_avant,
        'stock_apres': m.stock_apres,
        'reference_document': m.reference_document,
        'commentaire': m.commentaire,
        'date_mouvement': m.date_mouvement.isoformat(),
        'utilisateur': m.utilisateur
    } for m in mouvements]
    
    return Response({
        'success': True,
        'boutique_id': boutique.id,
        'boutique_nom': boutique.nom,
        'count': len(data),
        'mouvements': data
    })
```

### Ajouter l'URL

```python
# inventory/api_urls_v2_simple.py

urlpatterns = [
    # ... URLs existantes ...
    
    # ⭐ NOUVEAU : Endpoint mouvements de stock
    path('mouvements-stock/', api_views_v2_simple.get_mouvements_stock, name='mouvements_stock'),
]
```

### Exemple d'utilisation

```bash
# Récupérer tous les mouvements récents
curl -X GET "http://192.168.155.224:8000/api/v2/simple/mouvements-stock/" \
  -H "X-Device-Serial: 0a1badae951f8473"

# Récupérer les mouvements d'un article spécifique
curl -X GET "http://192.168.155.224:8000/api/v2/simple/mouvements-stock/?article_id=15" \
  -H "X-Device-Serial: 0a1badae951f8473"

# Récupérer uniquement les ventes
curl -X GET "http://192.168.155.224:8000/api/v2/simple/mouvements-stock/?type_mouvement=VENTE" \
  -H "X-Device-Serial: 0a1badae951f8473"

# Récupérer les mouvements d'une période
curl -X GET "http://192.168.155.224:8000/api/v2/simple/mouvements-stock/?date_debut=2024-11-01T00:00:00Z&date_fin=2024-11-04T23:59:59Z" \
  -H "X-Device-Serial: 0a1badae951f8473"
```

### Réponse

```json
{
  "success": true,
  "boutique_id": 9,
  "boutique_nom": "Ma Boutique",
  "count": 15,
  "mouvements": [
    {
      "id": 123,
      "article_id": 15,
      "article_nom": "Article Test",
      "article_code": "ART-001",
      "type_mouvement": "VENTE",
      "quantite": -2,
      "stock_avant": 10,
      "stock_apres": 8,
      "reference_document": "FAC-20241104-001",
      "commentaire": "Vente #FAC-20241104-001 - Prix: 25000.00 CDF",
      "date_mouvement": "2024-11-04T10:30:00Z",
      "utilisateur": "Terminal MAUI"
    },
    ...
  ]
}
```

### Avantages

- ✅ **Audit complet** : MAUI peut consulter tout l'historique
- ✅ **Réconciliation** : Vérifier que le stock local correspond au serveur
- ✅ **Traçabilité** : Voir qui a fait quoi et quand
- ✅ **Isolation** : Chaque boutique ne voit que ses propres mouvements

---

## 🎯 AMÉLIORATION 4 : Ajouter des statistiques dans la réponse de sync

### Problème actuel

La réponse de synchronisation ne donne pas assez d'informations sur l'état du stock après la synchronisation.

### Solution proposée

Enrichir la réponse avec des statistiques :

```python
# inventory/api_views_v2_simple.py

# Ligne 1088-1117 : Améliorer la réponse

# Calculer des statistiques après la synchronisation
articles_stock_bas = Article.objects.filter(
    boutique=boutique,
    quantite_stock__lte=models.F('seuil_alerte'),
    est_actif=True
).count()

articles_stock_zero = Article.objects.filter(
    boutique=boutique,
    quantite_stock=0,
    est_actif=True
).count()

return Response({
    'success': True,
    'message': f'{len(ventes_creees)} vente(s) synchronisée(s) avec succès',
    'ventes_creees': len(ventes_creees),
    'ventes_erreurs': len(ventes_erreurs),
    'details': {
        'creees': ventes_creees,
        'erreurs': ventes_erreurs if ventes_erreurs else []
    },
    'boutique': {
        'id': boutique.id,
        'nom': boutique.nom,
        'code': boutique.code_boutique if hasattr(boutique, 'code_boutique') else None
    },
    'terminal': {
        'id': terminal.id,
        'nom': terminal.nom_terminal,
        'numero_serie': numero_serie
    },
    'statistiques': {
        'total_envoyees': len(ventes_data),
        'reussies': len(ventes_creees),
        'erreurs': len(ventes_erreurs),
        # ⭐ NOUVELLES STATISTIQUES
        'articles_stock_bas': articles_stock_bas,
        'articles_stock_zero': articles_stock_zero,
        'alerte_stock': articles_stock_bas > 0 or articles_stock_zero > 0
    }
}, status=status.HTTP_201_CREATED)
```

### Avantages

- ✅ **Alertes proactives** : MAUI sait immédiatement s'il y a des problèmes de stock
- ✅ **Informations utiles** : Pas besoin de faire une requête supplémentaire
- ✅ **UX améliorée** : Afficher une notification si stock bas

---

## 📊 RÉCAPITULATIF DES AMÉLIORATIONS

| Amélioration | Priorité | Effort | Impact | Recommandation |
|--------------|----------|--------|--------|----------------|
| 1. Enrichir MouvementStock | 🟡 Moyenne | 🔧 Faible | ⭐⭐⭐ Élevé | ✅ **RECOMMANDÉ** |
| 2. Transactions atomiques | 🟢 Basse | 🔧 Très faible | ⭐⭐ Moyen | ✅ **RECOMMANDÉ** |
| 3. Endpoint mouvements | 🟡 Moyenne | 🔧 Moyen | ⭐⭐ Moyen | 🟡 **OPTIONNEL** |
| 4. Statistiques dans réponse | 🟢 Basse | 🔧 Très faible | ⭐ Faible | 🟡 **OPTIONNEL** |

---

## 🚀 PLAN D'IMPLÉMENTATION RECOMMANDÉ

### Phase 1 : Améliorations critiques (1-2 heures)

1. ✅ **Ajouter les transactions atomiques** (15 min)
   - Modifier `sync_ventes_simple()` ligne 947
   - Tester avec Postman

2. ✅ **Enrichir le modèle MouvementStock** (30 min)
   - Modifier `models.py`
   - Créer et appliquer la migration
   - Modifier `api_views_v2_simple.py` ligne 1038-1048

3. ✅ **Tester les modifications** (30 min)
   - Synchroniser des ventes
   - Vérifier les MouvementStock dans l'admin Django
   - Vérifier que les transactions rollback en cas d'erreur

### Phase 2 : Améliorations optionnelles (2-3 heures)

4. 🟡 **Créer l'endpoint mouvements de stock** (1h)
   - Ajouter la fonction dans `api_views_v2_simple.py`
   - Ajouter l'URL dans `api_urls_v2_simple.py`
   - Tester avec Postman

5. 🟡 **Ajouter les statistiques dans la réponse** (30 min)
   - Modifier la réponse de `sync_ventes_simple()`
   - Tester avec Postman

---

## ✅ CHECKLIST D'IMPLÉMENTATION

### Amélioration 1 : MouvementStock enrichi

- [ ] Modifier le modèle `MouvementStock` dans `models.py`
- [ ] Exécuter `python manage.py makemigrations`
- [ ] Exécuter `python manage.py migrate`
- [ ] Modifier `api_views_v2_simple.py` ligne 1038-1048
- [ ] Tester la création d'une vente
- [ ] Vérifier dans l'admin Django que les nouveaux champs sont remplis

### Amélioration 2 : Transactions atomiques

- [ ] Ajouter `from django.db import transaction` en haut du fichier
- [ ] Entourer le traitement de chaque vente avec `with transaction.atomic():`
- [ ] Tester avec une vente valide (doit réussir)
- [ ] Tester avec une vente invalide (doit rollback)
- [ ] Vérifier qu'aucune donnée orpheline n'est créée en cas d'erreur

### Amélioration 3 : Endpoint mouvements

- [ ] Créer la fonction `get_mouvements_stock()` dans `api_views_v2_simple.py`
- [ ] Ajouter l'URL dans `api_urls_v2_simple.py`
- [ ] Tester avec Postman sans filtres
- [ ] Tester avec filtres (article_id, type_mouvement, dates)
- [ ] Vérifier l'isolation (chaque boutique ne voit que ses mouvements)

### Amélioration 4 : Statistiques enrichies

- [ ] Modifier la réponse de `sync_ventes_simple()`
- [ ] Ajouter les calculs de statistiques
- [ ] Tester avec Postman
- [ ] Vérifier que les statistiques sont correctes

---

**Document créé le** : 4 novembre 2025  
**Statut** : 🟡 Améliorations optionnelles - Le système fonctionne déjà  
**Recommandation** : Implémenter les améliorations 1 et 2 pour plus de robustesse
