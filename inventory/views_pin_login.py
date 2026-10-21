"""
Vue pour la connexion rapide par code PIN
"""
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from .models import Collaborateur, Inventaire


def accueil_collaborateur(request):
    """Point d'arrivée d'un collaborateur connecté par code PIN.

    Un collaborateur n'a PAS de profil commerçant : lire `profil_commercant`
    (dashboard, liste d'inventaires…) lève RelatedObjectDoesNotExist → erreur
    500. On le mène donc vers l'inventaire en cours, sinon vers la page PIN
    avec un message explicite.
    """
    collaborateur = Collaborateur.objects.filter(
        user=request.user, est_actif=True
    ).select_related('commercant').first()

    if collaborateur is None:
        messages.error(request, "Vous n'avez pas de profil commerçant ou collaborateur.")
        return redirect('inventory:login_commercant')

    inventaire = Inventaire.objects.filter(
        boutique__commercant=collaborateur.commercant,
        statut='EN_COURS',
    ).select_related('boutique').first()

    if inventaire:
        return redirect(
            'inventory:saisir_inventaire_boutique',
            boutique_id=inventaire.boutique.id,
            inventaire_id=inventaire.id,
        )

    return render(request, 'inventory/commercant/login_pin.html', {
        'notice': (
            "Aucun inventaire en cours pour le moment. "
            "Reconnectez-vous avec votre PIN dès qu'un inventaire sera démarré."
        ),
    })


@require_http_methods(["GET", "POST"])
def login_pin(request):
    """Connexion rapide par code PIN pour les collaborateurs."""
    
    if request.method == 'POST':
        pin = request.POST.get('pin', '').strip()
        
        if not pin or len(pin) < 4:
            return render(request, 'inventory/commercant/login_pin.html', {
                'error': 'Le code PIN doit contenir au moins 4 chiffres'
            })
        
        try:
            # Chercher le collaborateur avec ce PIN
            collaborateur = Collaborateur.objects.select_related('user').get(
                code_pin=pin,
                est_actif=True
            )
            
            # Connecter l'utilisateur
            login(request, collaborateur.user)
            
            # Mettre à jour la dernière connexion
            from django.utils import timezone
            collaborateur.date_derniere_connexion = timezone.now()
            collaborateur.save(update_fields=['date_derniere_connexion'])
            
            messages.success(
                request, 
                f"Bienvenue {collaborateur.nom_complet} ! Connexion rapide réussie."
            )
            
            # Inventaire en cours → saisie ; sinon accueil collaborateur
            # (et surtout PAS le dashboard commerçant : erreur 500).
            return accueil_collaborateur(request)
            
        except Collaborateur.DoesNotExist:
            return render(request, 'inventory/commercant/login_pin.html', {
                'error': 'Code PIN invalide ou compte inactif'
            })
    
    return render(request, 'inventory/commercant/login_pin.html')
