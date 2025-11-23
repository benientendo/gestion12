from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Count
from .models import Client, Commercant, Boutique
from .forms import ClientForm, CommercantForm
import logging
import secrets
import string

logger = logging.getLogger(__name__)

def _generate_random_password(length=10):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def is_superuser(user):
    """Vérifier si l'utilisateur est un super administrateur."""
    return user.is_superuser

# ===== VUES ADMINISTRATEUR =====

@login_required
@user_passes_test(is_superuser)
def admin_dashboard(request):
    """Dashboard principal pour les super administrateurs."""
    
    # Statistiques générales
    total_commercants = Commercant.objects.count()
    commercants_actifs = Commercant.objects.filter(est_actif=True).count()
    total_boutiques = Boutique.objects.count()
    boutiques_actives = Boutique.objects.filter(est_active=True).count()
    total_clients_maui = Client.objects.count()
    clients_actifs = Client.objects.filter(est_actif=True).count()
    
    # Commerçants récents
    commercants_recents = Commercant.objects.order_by('-date_creation')[:5]
    
    # Boutiques récentes
    boutiques_recentes = Boutique.objects.select_related('commercant').order_by('-date_creation')[:5]
    
    context = {
        'total_commercants': total_commercants,
        'commercants_actifs': commercants_actifs,
        'total_boutiques': total_boutiques,
        'boutiques_actives': boutiques_actives,
        'total_clients_maui': total_clients_maui,
        'clients_actifs': clients_actifs,
        'commercants_recents': commercants_recents,
        'boutiques_recentes': boutiques_recentes,
    }
    
    return render(request, 'inventory/admin/dashboard.html', context)


@login_required
@user_passes_test(is_superuser)
def gestion_commercants(request):
    """Page de gestion des commerçants."""
    
    commercants = Commercant.objects.select_related('user').annotate(
        nombre_boutiques_count=Count('boutiques')
    ).order_by('-date_creation')
    
    # Pagination
    paginator = Paginator(commercants, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'commercants': page_obj,
        'page_obj': page_obj,
    }
    
    return render(request, 'inventory/admin/gestion_commercants.html', context)


@login_required
@user_passes_test(is_superuser)
def ajouter_commercant(request):
    """Ajouter un nouveau commerçant."""
    
    if request.method == 'POST':
        form = CommercantForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Créer l'utilisateur Django
                    user = User.objects.create_user(
                        username=form.cleaned_data['username'],
                        email=form.cleaned_data['email'],
                        password=form.cleaned_data['password'],
                        first_name=form.cleaned_data['prenom'],
                        last_name=form.cleaned_data['nom']
                    )
                    
                    # Créer le profil commerçant
                    commercant = form.save(commit=False)
                    commercant.user = user
                    commercant.save()
                    
                    messages.success(request, f'Commerçant {commercant.nom_entreprise} créé avec succès.')
                    return redirect('inventory:admin_gestion_commercants')
                    
            except Exception as e:
                logger.error(f"Erreur lors de la création du commerçant: {e}")
                messages.error(request, f'Erreur lors de la création: {str(e)}')
        else:
            # Afficher les erreurs de validation
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Erreur dans {field}: {error}')
            logger.error(f"Erreurs de validation du formulaire: {form.errors}")
    else:
        form = CommercantForm()
    
    return render(request, 'inventory/admin/ajouter_commercant.html', {'form': form})


@login_required
@user_passes_test(is_superuser)
def details_commercant(request, commercant_id):
    """Détails d'un commerçant spécifique."""
    
    commercant = get_object_or_404(Commercant, id=commercant_id)
    boutiques = commercant.boutiques.all().order_by('-date_creation')
    
    # Statistiques du commerçant
    total_boutiques = boutiques.count()
    boutiques_actives = boutiques.filter(est_active=True).count()
    
    context = {
        'commercant': commercant,
        'boutiques': boutiques,
        'total_boutiques': total_boutiques,
        'boutiques_actives': boutiques_actives,
    }
    
    return render(request, 'inventory/admin/details_commercant.html', context)


@login_required
@user_passes_test(is_superuser)
def modifier_commercant(request, commercant_id):
    """Modifier un commerçant."""
    
    commercant = get_object_or_404(Commercant, id=commercant_id)
    
    if request.method == 'POST':
        form = CommercantForm(request.POST, instance=commercant)
        if form.is_valid():
            form.save()
            messages.success(request, f'Commerçant {commercant.nom_entreprise} modifié avec succès.')
            return redirect('inventory:admin_details_commercant', commercant_id=commercant.id)
    else:
        form = CommercantForm(instance=commercant)
    
    return render(request, 'inventory/admin/modifier_commercant.html', {
        'form': form,
        'commercant': commercant
    })


@login_required
@user_passes_test(is_superuser)
def reset_commercant_password(request, commercant_id):
    commercant = get_object_or_404(Commercant, id=commercant_id)

    if request.method != 'POST':
        return redirect('inventory:admin_details_commercant', commercant_id=commercant.id)

    new_password = _generate_random_password()
    commercant.user.set_password(new_password)
    commercant.user.save()

    messages.success(request, f'Nouveau mot de passe pour {commercant.nom_entreprise} : {new_password}')
    return redirect('inventory:admin_details_commercant', commercant_id=commercant.id)


@login_required
@user_passes_test(is_superuser)
def supprimer_commercant(request, commercant_id):
    """Supprimer un commerçant (avec confirmation)."""
    
    commercant = get_object_or_404(Commercant, id=commercant_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Supprimer l'utilisateur Django (cascade vers le commerçant)
                commercant.user.delete()
                messages.success(request, f'Commerçant {commercant.nom_entreprise} supprimé avec succès.')
                return redirect('inventory:admin_gestion_commercants')
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du commerçant: {e}")
            messages.error(request, f'Erreur lors de la suppression: {str(e)}')
    
    return render(request, 'inventory/admin/supprimer_commercant.html', {
        'commercant': commercant
    })


@login_required
@user_passes_test(is_superuser)
def toggle_commercant_status(request, commercant_id):
    """Activer/désactiver un commerçant via AJAX."""
    
    if request.method == 'POST':
        commercant = get_object_or_404(Commercant, id=commercant_id)
        commercant.est_actif = not commercant.est_actif
        commercant.save()
        
        return JsonResponse({
            'success': True,
            'est_actif': commercant.est_actif,
            'message': f'Commerçant {"activé" if commercant.est_actif else "désactivé"} avec succès.'
        })
    
    return JsonResponse({'success': False, 'message': 'Méthode non autorisée.'})


# ===== GESTION DES BOUTIQUES (ADMIN) =====

@login_required
@user_passes_test(is_superuser)
def gestion_boutiques_admin(request):
    """Page de gestion de toutes les boutiques (vue admin)."""
    
    boutiques = Boutique.objects.select_related('commercant').order_by('-date_creation')
    
    # Filtres
    commercant_id = request.GET.get('commercant')
    if commercant_id:
        boutiques = boutiques.filter(commercant_id=commercant_id)
    
    type_commerce = request.GET.get('type')
    if type_commerce:
        boutiques = boutiques.filter(type_commerce=type_commerce)
    
    # Pagination
    paginator = Paginator(boutiques, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Pour les filtres
    commercants = Commercant.objects.all().order_by('nom_entreprise')
    types_commerce = Boutique._meta.get_field('type_commerce').choices
    
    context = {
        'boutiques': page_obj,
        'page_obj': page_obj,
        'commercants': commercants,
        'types_commerce': types_commerce,
        'commercant_selectionne': commercant_id,
        'type_selectionne': type_commerce,
    }
    
    return render(request, 'inventory/admin/gestion_boutiques.html', context)


@login_required
@user_passes_test(is_superuser)
def diagnostic_api(request):
    """Page de diagnostic pour tester la synchronisation des catalogues d'articles."""
    
    boutiques = Boutique.objects.filter(est_active=True).select_related('commercant').order_by('nom')
    
    context = {
        'boutiques': boutiques,
    }
    
    return render(request, 'inventory/admin/diagnostic_api.html', context)
