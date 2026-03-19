# 🔧 EXEMPLES D'INTÉGRATION - VUES DJANGO

Ce document montre comment intégrer WebSocket et Celery dans vos vues Django existantes.

---

## 📦 GESTION DES ARTICLES

### 1. Modifier un article (avec notification WebSocket)

```python
# Dans inventory/views_commercant.py

from inventory.websocket_utils import notify_article_updated, notify_price_updated

@login_required
@commercant_required
@boutique_access_required
def modifier_article_boutique(request, boutique_id, article_id):
    """Modifier un article et notifier tous les POS en temps réel"""
    boutique = request.boutique
    article = get_object_or_404(Article, id=article_id, boutique=boutique)
    
    if request.method == 'POST':
        # Sauvegarder les anciennes valeurs pour comparaison
        old_price = article.prix_vente
        old_stock = article.quantite_stock
        
        # Traiter le formulaire
        form = ArticleForm(request.POST, request.FILES, instance=article)
        
        if form.is_valid():
            article = form.save()
            
            # ✨ NOUVEAU : Notifier tous les POS via WebSocket
            notify_article_updated(boutique.id, article)
            
            # Notifications spécifiques si prix ou stock ont changé
            if old_price != article.prix_vente:
                notify_price_updated(boutique.id, article.id, article.prix_vente, article.devise)
                messages.success(request, f"Prix modifié et tous les POS notifiés : {article.prix_vente} {article.devise}")
            
            if old_stock != article.quantite_stock:
                notify_stock_updated(boutique.id, article.id, article.quantite_stock)
                messages.success(request, f"Stock modifié et tous les POS notifiés : {article.quantite_stock}")
            
            messages.success(request, f"Article '{article.nom}' modifié avec succès")
            return redirect('inventory:liste_articles_boutique', boutique_id=boutique.id)
    else:
        form = ArticleForm(instance=article)
    
    return render(request, 'inventory/commercant/modifier_article.html', {
        'form': form,
        'article': article,
        'boutique': boutique
    })
```

### 2. Créer un article (avec notification WebSocket)

```python
from inventory.websocket_utils import notify_article_created

@login_required
@commercant_required
@boutique_access_required
def creer_article_boutique(request, boutique_id):
    """Créer un article et notifier tous les POS"""
    boutique = request.boutique
    
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES)
        
        if form.is_valid():
            article = form.save(commit=False)
            article.boutique = boutique
            article.save()
            
            # ✨ NOUVEAU : Notifier tous les POS du nouveau produit
            notify_article_created(boutique.id, article)
            
            messages.success(request, f"Article '{article.nom}' créé et envoyé à tous les POS")
            return redirect('inventory:liste_articles_boutique', boutique_id=boutique.id)
    else:
        form = ArticleForm()
    
    return render(request, 'inventory/commercant/creer_article.html', {
        'form': form,
        'boutique': boutique
    })
```

### 3. Supprimer un article (avec notification WebSocket)

```python
from inventory.websocket_utils import notify_article_deleted

@login_required
@commercant_required
@boutique_access_required
def supprimer_article_boutique(request, boutique_id, article_id):
    """Supprimer un article et notifier tous les POS"""
    boutique = request.boutique
    article = get_object_or_404(Article, id=article_id, boutique=boutique)
    
    if request.method == 'POST':
        article_nom = article.nom
        article_id_copy = article.id
        
        # Désactiver au lieu de supprimer (soft delete)
        article.est_actif = False
        article.save()
        
        # ✨ NOUVEAU : Notifier tous les POS de la suppression
        notify_article_deleted(boutique.id, article_id_copy)
        
        messages.success(request, f"Article '{article_nom}' supprimé et retiré de tous les POS")
        return redirect('inventory:liste_articles_boutique', boutique_id=boutique.id)
    
    return render(request, 'inventory/commercant/confirmer_suppression.html', {
        'article': article,
        'boutique': boutique
    })
```

---

## 📊 GESTION DU STOCK

### 4. Approvisionnement (avec notification WebSocket)

```python
from inventory.websocket_utils import notify_stock_updated

@login_required
@commercant_required
@boutique_access_required
def approvisionner_article(request, boutique_id, article_id):
    """Approvisionner un article et notifier tous les POS"""
    boutique = request.boutique
    article = get_object_or_404(Article, id=article_id, boutique=boutique)
    
    if request.method == 'POST':
        quantite = int(request.POST.get('quantite', 0))
        
        if quantite > 0:
            # Mettre à jour le stock
            ancien_stock = article.quantite_stock
            article.quantite_stock += quantite
            article.save()
            
            # ✨ NOUVEAU : Notifier tous les POS du nouveau stock
            notify_stock_updated(boutique.id, article.id, article.quantite_stock)
            
            messages.success(request, 
                f"Stock de '{article.nom}' mis à jour : {ancien_stock} → {article.quantite_stock} (+{quantite})")
            
            return redirect('inventory:detail_article_boutique', 
                boutique_id=boutique.id, article_id=article.id)
    
    return render(request, 'inventory/commercant/approvisionner.html', {
        'article': article,
        'boutique': boutique
    })
```

### 5. Régularisation inventaire (avec notification WebSocket)

```python
from inventory.websocket_utils import notify_stock_updated, notify_sync_required

@login_required
@commercant_required
@boutique_access_required
def regulariser_inventaire_boutique(request, boutique_id, inventaire_id):
    """Régulariser l'inventaire et notifier tous les POS"""
    boutique = request.boutique
    inventaire = get_object_or_404(Inventaire, id=inventaire_id, boutique=boutique)
    
    if request.method == 'POST':
        # Traiter la régularisation
        lignes = inventaire.lignes.all()
        articles_modifies = []
        
        for ligne in lignes:
            if ligne.ecart != 0:
                # Mettre à jour le stock
                ligne.article.quantite_stock = ligne.quantite_physique
                ligne.article.save()
                
                articles_modifies.append(ligne.article)
                
                # ✨ NOUVEAU : Notifier chaque changement de stock
                notify_stock_updated(boutique.id, ligne.article.id, ligne.quantite_physique)
        
        # Marquer l'inventaire comme régularisé
        inventaire.statut = 'REGULARISE'
        inventaire.save()
        
        # ✨ NOUVEAU : Demander une sync complète pour être sûr
        notify_sync_required(boutique.id, f"Inventaire régularisé - {len(articles_modifies)} articles modifiés")
        
        messages.success(request, 
            f"Inventaire régularisé : {len(articles_modifies)} articles mis à jour et synchronisés")
        
        return redirect('inventory:liste_inventaires_boutique', boutique_id=boutique.id)
    
    return render(request, 'inventory/commercant/regulariser_inventaire.html', {
        'inventaire': inventaire,
        'boutique': boutique
    })
```

---

## 💰 SYNCHRONISATION DES VENTES (CELERY)

### 6. Modifier sync_ventes_simple pour utiliser Celery

```python
# Dans inventory/api_views_v2_simple.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from inventory.tasks import process_vente_async
from celery.result import AsyncResult
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([AllowAny])
def sync_ventes_simple(request):
    """
    Synchroniser les ventes - VERSION ASYNCHRONE avec Celery
    
    Les ventes sont mises en queue Redis et traitées en arrière-plan.
    Le POS reçoit une réponse immédiate et peut continuer à fonctionner.
    """
    ventes_data = request.data
    
    if not isinstance(ventes_data, list):
        ventes_data = [ventes_data]
    
    # Récupérer boutique_id et terminal_id
    boutique_id = request.GET.get('boutique_id')
    terminal_id = request.GET.get('terminal_id')
    numero_serie = request.headers.get('X-Device-Serial')
    
    # Validation
    if not boutique_id:
        return Response({
            'success': False,
            'error': 'boutique_id requis'
        }, status=400)
    
    try:
        boutique = Boutique.objects.get(id=boutique_id, est_active=True)
    except Boutique.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Boutique introuvable ou inactive'
        }, status=404)
    
    # Récupérer le terminal
    terminal = None
    if terminal_id:
        try:
            terminal = Client.objects.get(id=terminal_id, est_actif=True)
        except Client.DoesNotExist:
            pass
    
    if not terminal and numero_serie:
        try:
            terminal = Client.objects.get(numero_serie=numero_serie, est_actif=True)
        except Client.DoesNotExist:
            pass
    
    if not terminal:
        return Response({
            'success': False,
            'error': 'Terminal introuvable'
        }, status=404)
    
    logger.info(f"📥 Réception de {len(ventes_data)} ventes - Boutique {boutique.id} - Terminal {terminal.id}")
    
    # ✨ NOUVEAU : Traitement asynchrone avec Celery
    accepted = []
    rejected = []
    
    for vente_data in ventes_data:
        vente_uid = vente_data.get('numero_facture') or vente_data.get('NumeroFacture')
        
        try:
            # Vérification rapide des doublons (avant de mettre en queue)
            if Vente.objects.filter(numero_facture=vente_uid, boutique=boutique).exists():
                rejected.append({
                    'vente_uid': vente_uid,
                    'error': 'Vente déjà enregistrée (doublon)',
                    'error_type': 'duplicate'
                })
                logger.warning(f"⚠️ Doublon détecté : {vente_uid}")
                continue
            
            # ✨ Lancer la tâche asynchrone Celery
            task = process_vente_async.delay(
                vente_data, 
                boutique.id, 
                terminal.id
            )
            
            accepted.append({
                'vente_uid': vente_uid,
                'task_id': task.id,
                'status': 'queued',
                'message': 'Vente en cours de traitement'
            })
            
            logger.info(f"✅ Vente {vente_uid} mise en queue - Task {task.id}")
            
        except Exception as e:
            rejected.append({
                'vente_uid': vente_uid,
                'error': str(e),
                'error_type': 'queue_error'
            })
            logger.error(f"❌ Erreur mise en queue vente {vente_uid}: {e}")
    
    # Réponse immédiate au POS
    response_data = {
        'success': True,
        'message': f'{len(accepted)} ventes en cours de traitement, {len(rejected)} rejetées',
        'accepted': accepted,
        'rejected': rejected,
        'processing_mode': 'async',
        'total_received': len(ventes_data),
        'server_time': timezone.now().isoformat()
    }
    
    logger.info(f"📤 Réponse envoyée : {len(accepted)} acceptées, {len(rejected)} rejetées")
    
    return Response(response_data)


@api_view(['GET'])
@permission_classes([AllowAny])
def check_vente_task_status(request, task_id):
    """
    Vérifier le statut d'une tâche de vente Celery
    
    Usage: GET /api/v2/simple/ventes/task/{task_id}/
    """
    task = AsyncResult(task_id)
    
    response_data = {
        'task_id': task_id,
        'status': task.status,  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
        'ready': task.ready(),
    }
    
    if task.ready():
        if task.successful():
            response_data['result'] = task.result
            response_data['success'] = task.result.get('success', False)
        else:
            response_data['error'] = str(task.info)
            response_data['success'] = False
    else:
        response_data['message'] = 'Traitement en cours...'
    
    return Response(response_data)
```

### 7. Ajouter la route pour vérifier le statut des tâches

```python
# Dans inventory/api_urls_v2_simple.py

from django.urls import path
from inventory import api_views_v2_simple

urlpatterns = [
    # ... vos routes existantes ...
    
    # ✨ NOUVEAU : Route pour vérifier le statut des tâches
    path('ventes/task/<str:task_id>/', 
         api_views_v2_simple.check_vente_task_status, 
         name='check_vente_task_status'),
]
```

---

## 📁 GESTION DES CATÉGORIES

### 8. Modifier une catégorie (avec notification WebSocket)

```python
from inventory.websocket_utils import notify_category_updated

@login_required
@commercant_required
@boutique_access_required
def modifier_categorie_boutique(request, boutique_id, categorie_id):
    """Modifier une catégorie et notifier tous les POS"""
    boutique = request.boutique
    categorie = get_object_or_404(Categorie, id=categorie_id, boutique=boutique)
    
    if request.method == 'POST':
        form = CategorieForm(request.POST, instance=categorie)
        
        if form.is_valid():
            categorie = form.save()
            
            # ✨ NOUVEAU : Notifier tous les POS
            notify_category_updated(boutique.id, categorie)
            
            messages.success(request, f"Catégorie '{categorie.nom}' modifiée et synchronisée")
            return redirect('inventory:liste_categories_boutique', boutique_id=boutique.id)
    else:
        form = CategorieForm(instance=categorie)
    
    return render(request, 'inventory/commercant/modifier_categorie.html', {
        'form': form,
        'categorie': categorie,
        'boutique': boutique
    })
```

---

## 🚨 ALERTES STOCK

### 9. Créer une alerte stock (avec notification WebSocket)

```python
from inventory.websocket_utils import notify_stock_alert

def check_and_create_stock_alert(article, quantite_demandee, vente_uid=None):
    """
    Vérifier le stock et créer une alerte si nécessaire
    Appelé automatiquement lors des ventes
    """
    seuil_alerte = 10  # Configurable
    
    if article.quantite_stock < seuil_alerte:
        # Créer l'alerte en base
        alerte = AlerteStock.objects.create(
            article=article,
            boutique=article.boutique,
            quantite_actuelle=article.quantite_stock,
            quantite_demandee=quantite_demandee,
            vente_uid=vente_uid
        )
        
        # ✨ NOUVEAU : Notifier tous les POS via WebSocket
        notify_stock_alert(
            article.boutique.id,
            article.id,
            article.nom,
            article.quantite_stock,
            seuil_alerte
        )
        
        logger.warning(f"⚠️ Alerte stock créée : {article.nom} ({article.quantite_stock} restants)")
        
        return alerte
    
    return None
```

---

## 🔄 SYNCHRONISATION COMPLÈTE

### 10. Forcer une synchronisation complète

```python
from inventory.websocket_utils import notify_sync_required

@login_required
@commercant_required
@boutique_access_required
def forcer_sync_complete(request, boutique_id):
    """
    Forcer tous les POS à faire une synchronisation complète
    Utile après des changements majeurs
    """
    boutique = request.boutique
    
    if request.method == 'POST':
        raison = request.POST.get('raison', 'Synchronisation manuelle demandée')
        
        # ✨ Envoyer l'événement WebSocket à tous les POS
        notify_sync_required(boutique.id, raison)
        
        messages.success(request, 
            f"Synchronisation complète demandée à tous les POS de '{boutique.nom}'")
        
        return redirect('inventory:dashboard_boutique', boutique_id=boutique.id)
    
    return render(request, 'inventory/commercant/forcer_sync.html', {
        'boutique': boutique
    })
```

---

## 📝 RÉSUMÉ DES IMPORTS NÉCESSAIRES

```python
# En haut de vos fichiers views

# Pour WebSocket
from inventory.websocket_utils import (
    notify_article_updated,
    notify_article_created,
    notify_article_deleted,
    notify_stock_updated,
    notify_price_updated,
    notify_category_updated,
    notify_sync_required,
    notify_stock_alert,
    notify_vente_rejected
)

# Pour Celery
from inventory.tasks import (
    process_vente_async,
    process_multiple_ventes
)
from celery.result import AsyncResult

# Django standard
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)
```

---

## ✅ CHECKLIST D'INTÉGRATION

- [ ] Ajouter `notify_article_updated()` dans toutes les vues de modification d'articles
- [ ] Ajouter `notify_article_created()` dans les vues de création d'articles
- [ ] Ajouter `notify_article_deleted()` dans les vues de suppression
- [ ] Ajouter `notify_stock_updated()` dans les vues d'approvisionnement et régularisation
- [ ] Modifier `sync_ventes_simple()` pour utiliser `process_vente_async.delay()`
- [ ] Ajouter la route `check_vente_task_status` dans `api_urls_v2_simple.py`
- [ ] Tester chaque modification avec un POS connecté en WebSocket

---

## 🧪 TESTS RECOMMANDÉS

1. **Test WebSocket** : Modifier un prix dans Django admin → Vérifier mise à jour instantanée sur POS
2. **Test Celery** : Envoyer 10 ventes simultanément → Vérifier traitement parallèle
3. **Test charge** : Envoyer 100 ventes → Vérifier que le POS reçoit une réponse rapide
4. **Test reconnexion** : Couper Redis → Redémarrer → Vérifier reconnexion automatique
5. **Test erreur** : Vendre un article avec stock insuffisant → Vérifier alerte WebSocket

Bon courage pour l'intégration ! 🚀
