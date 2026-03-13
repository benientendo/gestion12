"""
Vues pour la gestion des collaborateurs (employés)
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db import transaction

from .models import Collaborateur, Boutique, Commercant
from .decorators import commercant_required


@login_required
@commercant_required
def gestion_collaborateurs(request):
    """Page de gestion des collaborateurs pour un commerçant."""
    commercant = request.user.profil_commercant
    
    collaborateurs = Collaborateur.objects.filter(
        commercant=commercant
    ).select_related('user').prefetch_related('boutiques_autorisees')
    
    boutiques = Boutique.objects.filter(commercant=commercant)
    
    collaborateurs_inventaire = collaborateurs.filter(role='INVENTAIRE').count()
    
    context = {
        'collaborateurs': collaborateurs,
        'boutiques': boutiques,
        'collaborateurs_inventaire': collaborateurs_inventaire,
    }
    
    return render(request, 'inventory/commercant/gestion_collaborateurs.html', context)


@login_required
@commercant_required
@require_POST
def ajouter_collaborateur(request):
    """Créer un nouveau collaborateur."""
    commercant = request.user.profil_commercant
    
    try:
        with transaction.atomic():
            # Créer le compte utilisateur Django
            username = request.POST.get('username')
            password = request.POST.get('password')
            
            if User.objects.filter(username=username).exists():
                messages.error(request, f"Le nom d'utilisateur '{username}' existe déjà.")
                return redirect('inventory:gestion_collaborateurs')
            
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=request.POST.get('nom_complet', '').split()[0] if request.POST.get('nom_complet') else '',
                last_name=' '.join(request.POST.get('nom_complet', '').split()[1:]) if len(request.POST.get('nom_complet', '').split()) > 1 else ''
            )
            
            # Créer le profil collaborateur
            collaborateur = Collaborateur.objects.create(
                user=user,
                commercant=commercant,
                nom_complet=request.POST.get('nom_complet'),
                telephone=request.POST.get('telephone', ''),
                role=request.POST.get('role', 'INVENTAIRE'),
                code_pin=request.POST.get('code_pin', ''),
                est_actif=True
            )
            
            # Assigner les boutiques autorisées
            boutiques_ids = request.POST.getlist('boutiques')
            if boutiques_ids:
                boutiques = Boutique.objects.filter(
                    id__in=boutiques_ids,
                    commercant=commercant
                )
                collaborateur.boutiques_autorisees.set(boutiques)
            
            messages.success(
                request, 
                f"✅ Collaborateur '{collaborateur.nom_complet}' créé avec succès ! "
                f"Identifiants : {username} / {password}"
            )
            
    except Exception as e:
        messages.error(request, f"Erreur lors de la création : {str(e)}")
    
    return redirect('inventory:gestion_collaborateurs')


@login_required
@commercant_required
@require_POST
def supprimer_collaborateur(request, collaborateur_id):
    """Supprimer un collaborateur."""
    commercant = request.user.profil_commercant
    
    try:
        collaborateur = get_object_or_404(
            Collaborateur, 
            id=collaborateur_id, 
            commercant=commercant
        )
        
        nom = collaborateur.nom_complet
        user = collaborateur.user
        
        # Supprimer le collaborateur (cascade supprimera aussi le user)
        collaborateur.delete()
        user.delete()
        
        return JsonResponse({'success': True, 'message': f'Collaborateur {nom} supprimé'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@commercant_required
def toggle_collaborateur_statut(request, collaborateur_id):
    """Activer/désactiver un collaborateur."""
    commercant = request.user.profil_commercant
    
    collaborateur = get_object_or_404(
        Collaborateur, 
        id=collaborateur_id, 
        commercant=commercant
    )
    
    collaborateur.est_actif = not collaborateur.est_actif
    collaborateur.save()
    
    statut = "activé" if collaborateur.est_actif else "désactivé"
    messages.success(request, f"Collaborateur {collaborateur.nom_complet} {statut}")
    
    return redirect('inventory:gestion_collaborateurs')


def collaborateur_required(view_func):
    """Décorateur pour vérifier qu'un utilisateur est un collaborateur actif."""
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'profil_collaborateur'):
            messages.error(request, "Accès réservé aux collaborateurs")
            return redirect('inventory:login')
        
        if not request.user.profil_collaborateur.est_actif:
            messages.error(request, "Votre compte collaborateur est désactivé")
            return redirect('inventory:login')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper
