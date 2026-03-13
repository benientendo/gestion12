"""
Vue pour l'assignation automatique des articles d'inventaire aux collaborateurs
"""
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST

from .models import Inventaire, LigneInventaire, Collaborateur
from .decorators import commercant_required


@login_required
@commercant_required
@require_POST
def auto_assigner_inventaire(request, boutique_id, inventaire_id):
    """Assigne automatiquement les articles aux collaborateurs actifs."""
    commercant = request.user.profil_commercant
    inventaire = get_object_or_404(
        Inventaire, 
        id=inventaire_id, 
        boutique_id=boutique_id,
        boutique__commercant=commercant
    )
    
    # Récupérer les collaborateurs actifs
    collaborateurs = list(Collaborateur.objects.filter(
        commercant=commercant,
        est_actif=True
    ).values_list('nom_complet', flat=True))
    
    if not collaborateurs:
        messages.warning(
            request, 
            "Aucun collaborateur actif trouvé. Créez d'abord des collaborateurs."
        )
        return redirect('inventory:saisir_inventaire_boutique', boutique_id, inventaire_id)
    
    # Récupérer les lignes non assignées
    lignes_non_assignees = LigneInventaire.objects.filter(
        inventaire=inventaire,
        assigne_a__isnull=True
    ) | LigneInventaire.objects.filter(
        inventaire=inventaire,
        assigne_a=''
    )
    
    nb_lignes = lignes_non_assignees.count()
    
    if nb_lignes == 0:
        messages.info(request, "Tous les articles sont déjà assignés.")
        return redirect('inventory:saisir_inventaire_boutique', boutique_id, inventaire_id)
    
    # Répartition équitable
    nb_collaborateurs = len(collaborateurs)
    lignes_par_collab = nb_lignes // nb_collaborateurs
    reste = nb_lignes % nb_collaborateurs
    
    # Assigner les articles
    index = 0
    for i, collaborateur in enumerate(collaborateurs):
        # Nombre d'articles pour ce collaborateur
        nb_articles = lignes_par_collab + (1 if i < reste else 0)
        
        # Assigner
        lignes_a_assigner = list(lignes_non_assignees[index:index + nb_articles])
        for ligne in lignes_a_assigner:
            ligne.assigne_a = collaborateur
            ligne.save(update_fields=['assigne_a'])
        
        index += nb_articles
    
    messages.success(
        request,
        f"✅ {nb_lignes} articles assignés automatiquement à {nb_collaborateurs} collaborateurs "
        f"({lignes_par_collab}-{lignes_par_collab + 1} articles par personne)"
    )
    
    return redirect('inventory:saisir_inventaire_boutique', boutique_id, inventaire_id)
