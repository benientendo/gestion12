"""
Vue pour modifier une vente existante
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from decimal import Decimal

from .models import Vente, LigneVente, Article, Boutique, MouvementStock
from .decorators import commercant_required
from .views_commercant import boutique_access_required


@login_required
@commercant_required
@boutique_access_required
@require_http_methods(["GET", "POST"])
def modifier_vente(request, boutique_id, vente_id):
    """Modifier une vente existante."""
    boutique = request.boutique
    vente = get_object_or_404(Vente, id=vente_id, boutique=boutique)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Récupérer les données du formulaire
                lignes_data = []
                i = 0
                while f'article_id_{i}' in request.POST:
                    article_id = request.POST.get(f'article_id_{i}')
                    quantite = request.POST.get(f'quantite_{i}')
                    prix_unitaire = request.POST.get(f'prix_unitaire_{i}')
                    
                    if article_id and quantite and prix_unitaire:
                        lignes_data.append({
                            'article_id': int(article_id),
                            'quantite': int(quantite),
                            'prix_unitaire': Decimal(prix_unitaire)
                        })
                    i += 1
                
                if not lignes_data:
                    messages.error(request, "La vente doit contenir au moins un article.")
                    return redirect('inventory:modifier_vente', boutique_id, vente_id)
                
                # Restaurer le stock des anciennes lignes
                for ligne in vente.lignes.all():
                    article = ligne.article
                    article.stock += ligne.quantite
                    article.save(update_fields=['stock'])
                    
                    # Créer mouvement de stock (annulation)
                    MouvementStock.objects.create(
                        article=article,
                        boutique=boutique,
                        type_mouvement='AJUSTEMENT',
                        quantite=ligne.quantite,
                        stock_avant=article.stock - ligne.quantite,
                        stock_apres=article.stock,
                        reference=f"Modification vente #{vente.id}",
                        utilisateur=request.user
                    )
                
                # Supprimer les anciennes lignes
                vente.lignes.all().delete()
                
                # Créer les nouvelles lignes
                montant_total = Decimal('0')
                for ligne_data in lignes_data:
                    article = Article.objects.get(id=ligne_data['article_id'], boutique=boutique)
                    quantite = ligne_data['quantite']
                    prix_unitaire = ligne_data['prix_unitaire']
                    
                    # Vérifier le stock
                    if article.stock < quantite:
                        raise ValueError(f"Stock insuffisant pour {article.nom} (disponible: {article.stock})")
                    
                    # Créer la ligne de vente
                    LigneVente.objects.create(
                        vente=vente,
                        article=article,
                        quantite=quantite,
                        prix_unitaire=prix_unitaire,
                        total=quantite * prix_unitaire
                    )
                    
                    # Déduire du stock
                    article.stock -= quantite
                    article.save(update_fields=['stock'])
                    
                    # Créer mouvement de stock
                    MouvementStock.objects.create(
                        article=article,
                        boutique=boutique,
                        type_mouvement='VENTE',
                        quantite=-quantite,
                        stock_avant=article.stock + quantite,
                        stock_apres=article.stock,
                        reference=f"Vente #{vente.id} (modifiée)",
                        utilisateur=request.user
                    )
                    
                    montant_total += quantite * prix_unitaire
                
                # Mettre à jour le montant total de la vente
                vente.montant_total = montant_total
                vente.save(update_fields=['montant_total'])
                
                messages.success(request, f"✅ Vente #{vente.id} modifiée avec succès !")
                return redirect('inventory:commercant_ventes_boutique', boutique_id)
                
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"Erreur lors de la modification : {str(e)}")
    
    # GET - Afficher le formulaire
    articles = Article.objects.filter(boutique=boutique, est_actif=True).order_by('nom')
    
    context = {
        'boutique': boutique,
        'vente': vente,
        'articles': articles,
    }
    
    return render(request, 'inventory/commercant/modifier_vente.html', context)
