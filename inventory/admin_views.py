from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction, connection
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from .models import Client, Commercant, Boutique, Article, Vente, LigneVente, VenteRejetee
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
    
    # Demandes de réinitialisation PDV en attente
    try:
        from .models import DemandeResetPdv
        nb_demandes_reset_en_attente = DemandeResetPdv.objects.filter(
            statut='EN_ATTENTE'
        ).count()
    except Exception:
        nb_demandes_reset_en_attente = 0

    # Bannières
    from .models import Banner
    nb_bannieres_total = Banner.objects.count()
    nb_bannieres_actives = Banner.objects.filter(est_active=True).count()

    # Messages
    from .models import MerchantMessage
    nb_messages_non_lus = MerchantMessage.objects.filter(est_lu=False).count()

    context = {
        'total_commercants': total_commercants,
        'commercants_actifs': commercants_actifs,
        'total_boutiques': total_boutiques,
        'boutiques_actives': boutiques_actives,
        'total_clients_maui': total_clients_maui,
        'clients_actifs': clients_actifs,
        'commercants_recents': commercants_recents,
        'boutiques_recentes': boutiques_recentes,
        'nb_demandes_reset_en_attente': nb_demandes_reset_en_attente,
        'nb_bannieres_total': nb_bannieres_total,
        'nb_bannieres_actives': nb_bannieres_actives,
        'nb_messages_non_lus': nb_messages_non_lus,
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


# ===== GESTION DES ERREURS DE TRANSACTION =====

@login_required
@user_passes_test(is_superuser)
def liste_erreurs_transactions(request):
    """Liste des erreurs de transaction pour le débogage."""
    from .models import ErreurTransaction
    from django.utils import timezone
    from datetime import timedelta
    
    # Filtres
    type_erreur = request.GET.get('type', '')
    gravite = request.GET.get('gravite', '')
    boutique_id = request.GET.get('boutique', '')
    commercant_id = request.GET.get('commercant', '')
    resolu = request.GET.get('resolu', '')
    periode = request.GET.get('periode', '7')  # 7 jours par défaut
    
    erreurs = ErreurTransaction.objects.select_related('boutique', 'commercant', 'utilisateur', 'client_maui').all()
    
    # Appliquer les filtres
    if type_erreur:
        erreurs = erreurs.filter(type_erreur=type_erreur)
    if gravite:
        erreurs = erreurs.filter(gravite=gravite)
    if boutique_id:
        erreurs = erreurs.filter(boutique_id=boutique_id)
    if commercant_id:
        erreurs = erreurs.filter(commercant_id=commercant_id)
    if resolu == '1':
        erreurs = erreurs.filter(est_resolu=True)
    elif resolu == '0':
        erreurs = erreurs.filter(est_resolu=False)
    
    # Filtre période
    if periode and periode != 'all':
        jours = int(periode)
        date_limite = timezone.now() - timedelta(days=jours)
        erreurs = erreurs.filter(date_creation__gte=date_limite)
    
    # Statistiques
    stats = {
        'total': erreurs.count(),
        'non_resolues': erreurs.filter(est_resolu=False).count(),
        'critiques': erreurs.filter(gravite='CRITICAL', est_resolu=False).count(),
        'aujourd_hui': erreurs.filter(date_creation__date=timezone.localdate()).count(),
    }
    
    # Pagination
    paginator = Paginator(erreurs, 25)
    page = request.GET.get('page', 1)
    erreurs_page = paginator.get_page(page)
    
    # Listes pour les filtres
    boutiques = Boutique.objects.all().order_by('nom')
    commercants = Commercant.objects.all().order_by('nom_entreprise')
    
    context = {
        'erreurs': erreurs_page,
        'stats': stats,
        'boutiques': boutiques,
        'commercants': commercants,
        'types_erreur': ErreurTransaction.TYPE_ERREUR_CHOICES,
        'gravites': ErreurTransaction.GRAVITE_CHOICES,
        'filtres': {
            'type': type_erreur,
            'gravite': gravite,
            'boutique': boutique_id,
            'commercant': commercant_id,
            'resolu': resolu,
            'periode': periode,
        }
    }
    
    return render(request, 'inventory/admin/liste_erreurs_transactions.html', context)


@login_required
@user_passes_test(is_superuser)
def detail_erreur_transaction(request, erreur_id):
    """Détail d'une erreur de transaction."""
    from .models import ErreurTransaction
    from django.utils import timezone
    
    erreur = get_object_or_404(ErreurTransaction, id=erreur_id)
    
    # Marquer comme résolu
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'resoudre':
            erreur.est_resolu = True
            erreur.note_resolution = request.POST.get('note_resolution', '')
            erreur.resolu_par = request.user
            erreur.date_resolution = timezone.now()
            erreur.save()
            messages.success(request, "Erreur marquée comme résolue.")
        elif action == 'rouvrir':
            erreur.est_resolu = False
            erreur.note_resolution = ''
            erreur.resolu_par = None
            erreur.date_resolution = None
            erreur.save()
            messages.info(request, "Erreur rouverte.")
        return redirect('inventory:admin_detail_erreur_transaction', erreur_id=erreur.id)
    
    # Erreurs similaires (même boutique, même type)
    erreurs_similaires = ErreurTransaction.objects.filter(
        boutique=erreur.boutique,
        type_erreur=erreur.type_erreur
    ).exclude(id=erreur.id).order_by('-date_creation')[:5]
    
    context = {
        'erreur': erreur,
        'erreurs_similaires': erreurs_similaires,
    }
    
    return render(request, 'inventory/admin/detail_erreur_transaction.html', context)


# ===== VENTES REJETÉES (ADMIN) =====

@login_required
@user_passes_test(is_superuser)
def admin_ventes_rejetees(request):
    """Affiche toutes les ventes rejetées de tous les points de vente pour l'administrateur."""
    from django.utils import timezone
    from decimal import Decimal
    
    # Filtres
    boutique_filter = request.GET.get('boutique', '')
    raison_filter = request.GET.get('raison', '')
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    traitee_filter = request.GET.get('traitee', '')
    
    # Requête de base
    ventes_rejetees = VenteRejetee.objects.select_related('boutique', 'terminal').order_by('-date_tentative')
    
    # Appliquer les filtres
    if boutique_filter:
        ventes_rejetees = ventes_rejetees.filter(boutique_id=boutique_filter)
    if raison_filter:
        ventes_rejetees = ventes_rejetees.filter(raison_rejet=raison_filter)
    if date_debut:
        ventes_rejetees = ventes_rejetees.filter(date_tentative__date__gte=date_debut)
    if date_fin:
        ventes_rejetees = ventes_rejetees.filter(date_tentative__date__lte=date_fin)
    if traitee_filter == '1':
        ventes_rejetees = ventes_rejetees.filter(traitee=True)
    elif traitee_filter == '0':
        ventes_rejetees = ventes_rejetees.filter(traitee=False)
    
    # Statistiques globales
    total_rejetees = ventes_rejetees.count()
    non_traitees = ventes_rejetees.filter(traitee=False).count()
    
    # Stats par raison
    stats_par_raison = ventes_rejetees.values('raison_rejet').annotate(
        count=Count('id')
    ).order_by('-count')
    
    raisons_display = dict(VenteRejetee.RAISONS_REJET)
    for stat in stats_par_raison:
        stat['raison_display'] = raisons_display.get(stat['raison_rejet'], stat['raison_rejet'])
    
    # Stats par boutique
    stats_par_boutique = ventes_rejetees.values('boutique__nom').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Préparer les détails
    ventes_details = []
    for vente in ventes_rejetees[:100]:  # Limiter à 100
        try:
            donnees = vente.donnees_vente
            montant = Decimal('0')
            nb_lignes = 0
            lignes = []
            
            if isinstance(donnees, dict):
                montant = Decimal(str(donnees.get('montant_total', 0)))
                lignes_data = donnees.get('lignes', [])
                nb_lignes = len(lignes_data)
                for ligne in lignes_data[:5]:  # Max 5 lignes par vente
                    lignes.append({
                        'article': ligne.get('article_nom', ligne.get('article', 'N/A')),
                        'quantite': ligne.get('quantite', 0),
                        'prix': ligne.get('prix_unitaire', 0),
                    })
            
            ventes_details.append({
                'id': vente.id,
                'vente_uid': vente.vente_uid,
                'boutique': vente.boutique.nom,
                'terminal': vente.terminal.nom_terminal if vente.terminal else 'N/A',
                'date_tentative': vente.date_tentative,
                'date_vente_originale': vente.date_vente_originale,
                'raison': vente.get_raison_rejet_display(),
                'raison_code': vente.raison_rejet,
                'message_erreur': vente.message_erreur,
                'article_concerne': vente.article_concerne_nom or '-',
                'stock_demande': vente.stock_demande,
                'stock_disponible': vente.stock_disponible,
                'montant': montant,
                'nb_lignes': nb_lignes,
                'lignes': lignes,
                'traitee': vente.traitee,
                'action_requise': vente.get_action_requise_display(),
                'notes_traitement': vente.notes_traitement,
            })
        except Exception as e:
            logger.error(f"Erreur parsing vente rejetée {vente.id}: {e}")
    
    # Liste des boutiques pour le filtre
    boutiques = Boutique.objects.filter(est_active=True).order_by('nom')
    
    context = {
        'ventes_details': ventes_details,
        'total_rejetees': total_rejetees,
        'non_traitees': non_traitees,
        'stats_par_raison': stats_par_raison,
        'stats_par_boutique': stats_par_boutique,
        'boutiques': boutiques,
        'raisons': VenteRejetee.RAISONS_REJET,
        'boutique_filter': boutique_filter,
        'raison_filter': raison_filter,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'traitee_filter': traitee_filter,
    }
    
    return render(request, 'inventory/admin/ventes_rejetees.html', context)


@login_required
@user_passes_test(is_superuser)
def admin_traiter_vente_rejetee(request, vente_id):
    """Marquer une vente rejetée comme traitée."""
    from django.utils import timezone
    
    vente = get_object_or_404(VenteRejetee, id=vente_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'traiter':
            vente.traitee = True
            vente.date_traitement = timezone.now()
            vente.traite_par = request.user.username
            vente.notes_traitement = request.POST.get('notes', '')
            vente.save()
            messages.success(request, f"Vente {vente.vente_uid} marquée comme traitée.")
        elif action == 'rouvrir':
            vente.traitee = False
            vente.date_traitement = None
            vente.traite_par = ''
            vente.notes_traitement = ''
            vente.save()
            messages.info(request, f"Vente {vente.vente_uid} rouverte.")
    
    return redirect('inventory:admin_ventes_rejetees')


# ===== GESTION DES BANNIÈRES PUBLICITAIRES (ADMIN) =====

@login_required
@user_passes_test(is_superuser)
def admin_gestion_bannieres(request):
    """Liste des bannières publicitaires."""
    from .models import Banner
    from django.utils import timezone

    bannières = Banner.objects.select_related('boutique').all()

    # Filtres
    boutique_id = request.GET.get('boutique')
    est_active = request.GET.get('actif')
    if boutique_id:
        bannières = bannières.filter(boutique_id=boutique_id)
    if est_active == '1':
        bannières = bannières.filter(est_active=True)
    elif est_active == '0':
        bannières = bannières.filter(est_active=False)

    stats = {
        'total': Banner.objects.count(),
        'actives': Banner.objects.filter(est_active=True).count(),
        'inactives': Banner.objects.filter(est_active=False).count(),
    }

    boutiques = Boutique.objects.all().order_by('nom')

    context = {
        'bannières': bannières,
        'stats': stats,
        'boutiques': boutiques,
        'filtre_boutique': boutique_id or '',
        'filtre_actif': est_active or '',
    }
    return render(request, 'inventory/admin/gestion_bannieres.html', context)


@login_required
@user_passes_test(is_superuser)
def admin_ajouter_banniere(request):
    """Créer une nouvelle bannière."""
    from .models import Banner

    if request.method == 'POST':
        try:
            titre = request.POST.get('titre', '').strip()
            if not titre:
                messages.error(request, 'Le titre est obligatoire.')
                return render(request, 'inventory/admin/ajouter_banniere.html', {'boutiques': Boutique.objects.all().order_by('nom')})

            boutique_id = request.POST.get('boutique')
            boutique = None
            if boutique_id:
                boutique = get_object_or_404(Boutique, id=boutique_id)

            banniere = Banner.objects.create(
                titre=titre,
                sous_titre=request.POST.get('sous_titre', '').strip(),
                couleur_fond=request.POST.get('couleur_fond', '#1565C0'),
                texte_bouton=request.POST.get('texte_bouton', '').strip(),
                action_type=request.POST.get('action_type', 'NONE'),
                action_cible=request.POST.get('action_cible', '').strip(),
                est_active=request.POST.get('est_active') == 'on',
                priorite=int(request.POST.get('priorite', 0)),
                boutique=boutique,
            )

            image = request.FILES.get('image')
            if image:
                banniere.image = image
                banniere.save()

            try:
                from .websocket_utils import notify_banner_created
                notify_banner_created(
                    boutique_id=boutique.id if boutique else None,
                    banner_id=banniere.id,
                    banner_titre=banniere.titre,
                )
            except Exception as e:
                logger.warning(f"Erreur notification bannière: {e}")

            messages.success(request, f'Bannière "{banniere.titre}" créée avec succès.')
            return redirect('inventory:admin_gestion_bannieres')
        except Exception as e:
            logger.error(f"Erreur création bannière: {e}")
            messages.error(request, f'Erreur: {str(e)}')

    boutiques = Boutique.objects.all().order_by('nom')
    return render(request, 'inventory/admin/ajouter_banniere.html', {'boutiques': boutiques})


@login_required
@user_passes_test(is_superuser)
def admin_modifier_banniere(request, banniere_id):
    """Modifier une bannière."""
    from .models import Banner

    banniere = get_object_or_404(Banner, id=banniere_id)

    if request.method == 'POST':
        try:
            banniere.titre = request.POST.get('titre', banniere.titre).strip()
            banniere.sous_titre = request.POST.get('sous_titre', '').strip()
            banniere.couleur_fond = request.POST.get('couleur_fond', banniere.couleur_fond)
            banniere.texte_bouton = request.POST.get('texte_bouton', '').strip()
            banniere.action_type = request.POST.get('action_type', banniere.action_type)
            banniere.action_cible = request.POST.get('action_cible', '').strip()
            banniere.est_active = request.POST.get('est_active') == 'on'
            banniere.priorite = int(request.POST.get('priorite', banniere.priorite))

            boutique_id = request.POST.get('boutique')
            if boutique_id:
                banniere.boutique = get_object_or_404(Boutique, id=boutique_id)
            else:
                banniere.boutique = None

            image = request.FILES.get('image')
            if image:
                banniere.image = image

            banniere.save()

            try:
                from .websocket_utils import notify_banner_created
                notify_banner_created(
                    boutique_id=banniere.boutique.id if banniere.boutique else None,
                    banner_id=banniere.id,
                    banner_titre=banniere.titre,
                )
            except Exception as e:
                logger.warning(f"Erreur notification bannière: {e}")

            messages.success(request, f'Bannière "{banniere.titre}" modifiée.')
            return redirect('inventory:admin_gestion_bannieres')
        except Exception as e:
            logger.error(f"Erreur modification bannière {banniere_id}: {e}")
            messages.error(request, f'Erreur: {str(e)}')

    boutiques = Boutique.objects.all().order_by('nom')
    return render(request, 'inventory/admin/modifier_banniere.html', {
        'banniere': banniere,
        'boutiques': boutiques,
    })


@login_required
@user_passes_test(is_superuser)
def admin_supprimer_banniere(request, banniere_id):
    """Supprimer une bannière."""
    from .models import Banner

    banniere = get_object_or_404(Banner, id=banniere_id)

    if request.method == 'POST':
        try:
            titre = banniere.titre
            banniere.delete()
            messages.success(request, f'Bannière "{titre}" supprimée.')
        except Exception as e:
            logger.error(f"Erreur suppression bannière {banniere_id}: {e}")
            messages.error(request, f'Erreur: {str(e)}')
        return redirect('inventory:admin_gestion_bannieres')

    return render(request, 'inventory/admin/supprimer_banniere.html', {'banniere': banniere})


@login_required
@user_passes_test(is_superuser)
def admin_toggle_banniere(request, banniere_id):
    """Activer/désactiver une bannière (AJAX)."""
    from .models import Banner

    if request.method == 'POST':
        banniere = get_object_or_404(Banner, id=banniere_id)
        banniere.est_active = not banniere.est_active
        banniere.save(update_fields=['est_active'])
        return JsonResponse({
            'success': True,
            'est_active': banniere.est_active,
            'message': f'Bannière {"activée" if banniere.est_active else "désactivée"}.'
        })

    return JsonResponse({'success': False, 'message': 'Méthode non autorisée.'})


# ===== GESTION DES MESSAGES COMMERCANT (ADMIN) =====

@login_required
@user_passes_test(is_superuser)
def admin_gestion_messages(request):
    """Liste des messages envoyés aux commerçants."""
    from .models import MerchantMessage

    msgs = MerchantMessage.objects.select_related('commercant').all()

    # Filtres
    type_msg = request.GET.get('type')
    if type_msg:
        msgs = msgs.filter(type_message=type_msg)

    stats = {
        'total': MerchantMessage.objects.count(),
        'non_lus': MerchantMessage.objects.filter(est_lu=False).count(),
        'paiements': MerchantMessage.objects.filter(type_message='PAIEMENT').count(),
    }

    commercants = Commercant.objects.all().order_by('nom_entreprise')

    context = {
        'messages_list': msgs,
        'stats': stats,
        'commercants': commercants,
        'filtre_type': type_msg or '',
    }
    return render(request, 'inventory/admin/gestion_messages.html', context)


@login_required
@user_passes_test(is_superuser)
def admin_ajouter_message(request):
    """Envoyer un message à un ou plusieurs commerçants."""
    from .models import MerchantMessage

    if request.method == 'POST':
        try:
            titre = request.POST.get('titre', '').strip()
            contenu = request.POST.get('contenu', '').strip()
            type_message = request.POST.get('type_message', 'INFO')
            commercant_id = request.POST.get('commercant')

            if not titre or not contenu:
                messages.error(request, 'Le titre et le contenu sont obligatoires.')
                return render(request, 'inventory/admin/ajouter_message.html', {
                    'commercants': Commercant.objects.all().order_by('nom_entreprise'),
                })

            commercant = None
            if commercant_id:
                commercant = get_object_or_404(Commercant, id=commercant_id)

            msg = MerchantMessage.objects.create(
                titre=titre,
                contenu=contenu,
                type_message=type_message,
                commercant=commercant,
            )

            # Notifier via WebSocket si commerçant spécifique
            if commercant:
                try:
                    from .websocket_utils import notify_merchant_message
                    notify_merchant_message(commercant.id, msg.id, msg.titre, msg.type_message)
                except Exception:
                    pass

            messages.success(request, f'Message "{titre}" envoyé avec succès.')
            return redirect('inventory:admin_gestion_messages')

        except Exception as e:
            logger.error(f"Erreur création message: {e}")
            messages.error(request, f'Erreur: {str(e)}')

    commercants = Commercant.objects.all().order_by('nom_entreprise')
    return render(request, 'inventory/admin/ajouter_message.html', {
        'commercants': commercants,
    })


@login_required
@user_passes_test(is_superuser)
def admin_supprimer_message(request, message_id):
    """Supprimer un message."""
    from .models import MerchantMessage

    msg = get_object_or_404(MerchantMessage, id=message_id)

    if request.method == 'POST':
        try:
            titre = msg.titre
            msg.delete()
            messages.success(request, f'Message "{titre}" supprimé.')
        except Exception as e:
            logger.error(f"Erreur suppression message: {e}")
            messages.error(request, f'Erreur: {str(e)}')
        return redirect('inventory:admin_gestion_messages')

    return render(request, 'inventory/admin/supprimer_message.html', {'message_obj': msg})


@login_required
@user_passes_test(is_superuser)
def admin_marquer_lu_message(request, message_id):
    """Marquer un message comme lu (GET ou POST)."""
    from .models import MerchantMessage
    from django.utils import timezone

    if request.method in ('GET', 'POST'):
        msg = get_object_or_404(MerchantMessage, id=message_id)
        msg.est_lu = True
        msg.date_lecture = timezone.now()
        msg.save(update_fields=['est_lu', 'date_lecture'])
        messages.success(request, f'Message "{msg.titre}" marqué comme lu.')

    # Retourner à la page précédente
    referer = request.META.get('HTTP_REFERER')
    if referer:
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(referer)
    if request.user.is_superuser:
        return redirect('inventory:admin_dashboard')
    return redirect('inventory:home')
