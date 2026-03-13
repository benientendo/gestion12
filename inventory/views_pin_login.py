"""
Vue pour la connexion rapide par code PIN
"""
from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from .models import Collaborateur


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
            
            # Rediriger vers le dashboard ou l'inventaire
            next_url = request.GET.get('next', 'inventory:commercant_dashboard')
            return redirect(next_url)
            
        except Collaborateur.DoesNotExist:
            return render(request, 'inventory/commercant/login_pin.html', {
                'error': 'Code PIN invalide ou compte inactif'
            })
    
    return render(request, 'inventory/commercant/login_pin.html')
