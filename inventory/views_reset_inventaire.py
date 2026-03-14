"""
Vue pour réinitialiser les articles d'inventaire saisis par l'utilisateur
"""
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST

from .models import Inventaire, LigneInventaire
from .views_commercant import commercant_required, boutique_access_required


@login_required
@commercant_required
@boutique_access_required
@require_POST
def reinitialiser_mes_articles(request, boutique_id, inventaire_id):
    """Réinitialise uniquement les articles saisis par l'utilisateur actuel."""
    boutique = request.boutique
    inventaire = get_object_or_404(
        Inventaire, 
        id=inventaire_id, 
        boutique=boutique,
        statut='EN_COURS'
    )
    
    # Récupérer les lignes saisies par cet utilisateur
    lignes_utilisateur = LigneInventaire.objects.filter(
        inventaire=inventaire,
        saisi_par=request.user
    )
    
    nb_lignes = lignes_utilisateur.count()
    
    if nb_lignes == 0:
        messages.info(request, "Vous n'avez encore saisi aucun article dans cet inventaire.")
        return redirect('inventory:saisir_inventaire_boutique', boutique_id, inventaire_id)
    
    # Réinitialiser les champs
    for ligne in lignes_utilisateur:
        ligne.stock_physique = None
        ligne.commentaire = ''
        ligne.saisi_par = None
        ligne.date_modification = None
        ligne.save(update_fields=['stock_physique', 'commentaire', 'saisi_par', 'date_modification'])
    
    messages.success(
        request,
        f"✅ {nb_lignes} article(s) réinitialisé(s) avec succès. Vous pouvez recommencer votre comptage."
    )
    
    return redirect('inventory:saisir_inventaire_boutique', boutique_id, inventaire_id)
