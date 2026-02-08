from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction, connection
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from .models import Client, Commercant, Boutique, Article, Vente, LigneVente
from .forms import ClientForm, CommercantForm
import logging
import secrets
import string
import os

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
def toggle_boutique_pos_admin(request, boutique_id):
    boutique = get_object_or_404(Boutique, id=boutique_id)
    boutique.pos_autorise = not boutique.pos_autorise
    boutique.save(update_fields=['pos_autorise'])
    if boutique.pos_autorise:
        messages.success(request, f"POS MAUI autorisé pour la boutique '{boutique.nom}'.")
    else:
        messages.warning(request, f"POS MAUI désactivé pour la boutique '{boutique.nom}'. Aucun terminal ne pourra enregistrer de ventes.")
    return redirect('inventory:admin_gestion_boutiques')


@login_required
@user_passes_test(is_superuser)
def diagnostic_api(request):
    """Page de diagnostic pour tester la synchronisation des catalogues d'articles."""
    
    boutiques = Boutique.objects.filter(est_active=True).select_related('commercant').order_by('nom')
    
    context = {
        'boutiques': boutiques,
    }
    
    return render(request, 'inventory/admin/diagnostic_api.html', context)


@login_required
@user_passes_test(is_superuser)
def statistiques_systeme(request):
    """Statistiques système détaillées - Base de données, RAM, Performance."""
    
    # ===== STATISTIQUES BASE DE DONNÉES =====
    stats_db = {}
    
    # Compter les enregistrements par table principale
    stats_db['articles'] = Article.objects.count()
    stats_db['ventes'] = Vente.objects.count()
    stats_db['lignes_vente'] = LigneVente.objects.count()
    stats_db['boutiques'] = Boutique.objects.count()
    stats_db['commercants'] = Commercant.objects.count()
    stats_db['clients_maui'] = Client.objects.count()
    
    # Total des enregistrements
    stats_db['total_enregistrements'] = sum(stats_db.values())
    
    # Taille estimée de la base (PostgreSQL)
    taille_db = None
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_database_size(current_database());")
            taille_bytes = cursor.fetchone()[0]
            taille_db = {
                'bytes': taille_bytes,
                'mb': round(taille_bytes / (1024 * 1024), 2),
                'gb': round(taille_bytes / (1024 * 1024 * 1024), 3),
            }
    except Exception as e:
        logger.warning(f"Impossible de récupérer la taille DB: {e}")
    
    # Statistiques des tables (taille)
    tables_stats = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    relname as table_name,
                    n_live_tup as row_count,
                    pg_total_relation_size(relid) as total_size
                FROM pg_stat_user_tables
                ORDER BY pg_total_relation_size(relid) DESC
                LIMIT 10;
            """)
            for row in cursor.fetchall():
                tables_stats.append({
                    'nom': row[0],
                    'lignes': row[1],
                    'taille_bytes': row[2],
                    'taille_mb': round(row[2] / (1024 * 1024), 2),
                })
    except Exception as e:
        logger.warning(f"Impossible de récupérer les stats des tables: {e}")
    
    # ===== CONFIGURATION SCALINGO =====
    config_scalingo = {
        'redis_url': bool(os.environ.get('REDIS_URL')),
        'database_url': bool(os.environ.get('DATABASE_URL')),
        'debug': os.environ.get('DEBUG', 'False'),
        'scalingo_app': os.environ.get('SCALINGO_APP', 'Non défini'),
    }
    
    # ===== LIMITES ET RECOMMANDATIONS =====
    # Plan postgresql-starter-512 : 512 MB RAM, 2 GB stockage
    limites = {
        'db_stockage_max_gb': 2.0,
        'db_ram_mb': 512,
        'app_ram_mb': 512,
        'redis_ram_mb': 256,
    }
    
    # Calcul des pourcentages d'utilisation
    utilisation = {}
    if taille_db:
        utilisation['db_stockage_pct'] = round((taille_db['gb'] / limites['db_stockage_max_gb']) * 100, 1)
        utilisation['db_stockage_status'] = 'success' if utilisation['db_stockage_pct'] < 70 else ('warning' if utilisation['db_stockage_pct'] < 85 else 'danger')
    
    # Estimations de capacité
    capacite = {
        'articles_max_estime': 50000,
        'ventes_max_estime': 100000,
        'articles_pct': round((stats_db['articles'] / 50000) * 100, 1) if stats_db['articles'] else 0,
        'ventes_pct': round((stats_db['ventes'] / 100000) * 100, 1) if stats_db['ventes'] else 0,
    }
    
    # ===== ALERTES =====
    alertes = []
    if taille_db and taille_db['gb'] > 1.5:
        alertes.append({
            'type': 'warning',
            'titre': 'Stockage base de données',
            'message': f"La base utilise {taille_db['gb']} GB sur 2 GB disponibles. Envisagez un upgrade."
        })
    if stats_db['articles'] > 30000:
        alertes.append({
            'type': 'warning',
            'titre': 'Nombre d\'articles élevé',
            'message': f"{stats_db['articles']} articles. Les performances peuvent être impactées."
        })
    if stats_db['ventes'] > 70000:
        alertes.append({
            'type': 'warning',
            'titre': 'Nombre de ventes élevé',
            'message': f"{stats_db['ventes']} ventes. Envisagez l'archivage des anciennes données."
        })
    
    context = {
        'stats_db': stats_db,
        'taille_db': taille_db,
        'tables_stats': tables_stats,
        'config_scalingo': config_scalingo,
        'limites': limites,
        'utilisation': utilisation,
        'capacite': capacite,
        'alertes': alertes,
    }
    
    return render(request, 'inventory/admin/statistiques_systeme.html', context)
