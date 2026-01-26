"""
Décorateurs pour les vues de bilan et gestion
"""
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from .models import Commercant, Boutique

def commercant_required(view_func):
    """Décorateur pour vérifier que l'utilisateur est un commerçant"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('inventory:login_commercant')
        
        try:
            commercant = request.user.profil_commercant
            if not commercant.est_actif:
                messages.error(request, "Votre compte commerçant est désactivé.")
                return redirect('inventory:login_commercant')
        except Commercant.DoesNotExist:
            messages.error(request, "Vous n'avez pas de profil commerçant.")
            return redirect('inventory:login_commercant')
        
        return view_func(request, *args, **kwargs)
    return wrapper

def boutique_required(view_func):
    """Décorateur pour vérifier l'accès à une boutique spécifique"""
    def wrapper(request, boutique_id, *args, **kwargs):
        try:
            commercant = request.user.profil_commercant
            boutique = get_object_or_404(Boutique, id=boutique_id, commercant=commercant)
            request.boutique = boutique  # Ajouter la boutique à la requête
            return view_func(request, boutique_id, *args, **kwargs)
        except Commercant.DoesNotExist:
            return HttpResponseForbidden("Accès non autorisé")
    return wrapper
