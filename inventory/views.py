from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.http import HttpResponse, JsonResponse
from .models import Categorie, Article, Vente, LigneVente, MouvementStock, Client, SessionClientMaui, Boutique, Commercant
from django.db.models import Sum, Count, F
from datetime import datetime, timedelta
from .forms import ArticleForm, CategorieForm
from .user_forms import UserCreateForm, UserEditForm
from .utils import generate_qr_codes_pdf
from django.core.paginator import Paginator
from django.utils import timezone

# Create your views here.

@login_required
def home(request):
    """Page d'accueil - Redirection intelligente selon le type d'utilisateur."""
    
    # Vérifier si l'utilisateur est un super administrateur
    if request.user.is_superuser:
        return redirect('inventory:admin_dashboard')
    
    # Vérifier si l'utilisateur a un profil commerçant
    try:
        commercant = request.user.profil_commercant
        return redirect('inventory:commercant_dashboard')
    except:
        # Utilisateur sans profil commerçant - afficher l'ancien dashboard pour compatibilité
        pass
    
    # Ancien code pour compatibilité avec les utilisateurs existants
    # ⭐ ISOLATION: Afficher des données vides pour utilisateurs legacy
    # (ils devraient migrer vers un profil commerçant)
    categories_count = 0
    articles_count = 0
    ventes_count = 0
    
    latest_articles = Article.objects.none()
    latest_ventes = Vente.objects.none()
    
    context = {
        'categories_count': categories_count,
        'articles_count': articles_count,
        'ventes_count': ventes_count,
        'latest_articles': latest_articles,
        'latest_ventes': latest_ventes,
        'migration_needed': True,  # Indiquer qu'une migration est nécessaire
    }
    
    return render(request, 'inventory/home.html', context)

@login_required
def ajouter_article(request):
    # Déterminer si la requête vient du modal ou du formulaire complet
    is_modal_request = 'ajax' in request.GET or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # Récupérer la boutique depuis les paramètres GET
    boutique_id = request.GET.get('boutique')
    boutique = None
    
    if boutique_id:
        try:
            # Vérifier que l'utilisateur a accès à cette boutique
            if request.user.is_superuser:
                boutique = get_object_or_404(Boutique, id=boutique_id)
            else:
                commercant = request.user.profil_commercant
                boutique = get_object_or_404(Boutique, id=boutique_id, commercant=commercant)
        except:
            messages.error(request, "Boutique non trouvée ou accès non autorisé.")
            return redirect('inventory:home')
    else:
        # Si pas de boutique spécifiée, rediriger vers le dashboard approprié
        if request.user.is_superuser:
            messages.info(request, "Veuillez sélectionner une boutique pour ajouter un article.")
            return redirect('inventory:admin_dashboard')
        else:
            try:
                commercant = request.user.profil_commercant
                messages.info(request, "Veuillez sélectionner une boutique pour ajouter un article.")
                return redirect('inventory:commercant_dashboard')
            except:
                messages.error(request, "Votre compte doit être migré vers la nouvelle architecture.")
                return redirect('inventory:home')
    
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES)
        try:
            if form.is_valid():
                article = form.save(commit=False)
                article.boutique = boutique  # Associer l'article à la boutique
                article.save()
                messages.success(request, f'Article "{article.nom}" ajouté avec succès à {boutique.nom}.')
                
                # Redirection appropriée
                if is_modal_request:
                    return redirect('inventory:articles')
                else:
                    return redirect('inventory:entrer_boutique', boutique_id=boutique.id)
            else:
                # Afficher les erreurs de validation du formulaire
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"Erreur dans le champ {field}: {error}")
        except Exception as e:
            # Capturer et afficher l'exception spécifique
            import traceback
            error_message = str(e)
            error_trace = traceback.format_exc()
            print(f"ERREUR lors de l'ajout d'article: {error_message}")
            print(f"Traceback: {error_trace}")
            messages.error(request, f"Une erreur s'est produite: {error_message}")
            
        # En cas d'erreur et si c'est une requête depuis le modal, rediriger vers la liste des articles
        if is_modal_request:
            return redirect('inventory:articles')
    else:
        form = ArticleForm()
    
    # Récupérer les catégories de la boutique
    categories = Categorie.objects.filter(boutique=boutique) if boutique else Categorie.objects.none()
    
    context = {
        'form': form,
        'categories': categories,
        'boutique': boutique
    }
    
    return render(request, 'inventory/article_form.html', context)

@login_required
def liste_categories(request):
    """Page de gestion des catégories."""
    
    # Récupérer la boutique depuis les paramètres GET
    boutique_id = request.GET.get('boutique')
    boutique = None
    
    if boutique_id:
        try:
            # Vérifier que l'utilisateur a accès à cette boutique
            if request.user.is_superuser:
                boutique = get_object_or_404(Boutique, id=boutique_id)
            else:
                commercant = request.user.profil_commercant
                boutique = get_object_or_404(Boutique, id=boutique_id, commercant=commercant)
        except Boutique.DoesNotExist:
            messages.error(request, "Boutique non trouvée.")
            return redirect('inventory:commercant_dashboard')
        except AttributeError:
            messages.error(request, "Votre compte doit être migré vers la nouvelle architecture.")
            return redirect('inventory:home')
        except Exception as e:
            messages.error(request, f"Erreur d'accès à la boutique: {str(e)}")
            return redirect('inventory:commercant_dashboard')
    else:
        # Si pas de boutique spécifiée, rediriger vers le dashboard approprié
        if request.user.is_superuser:
            messages.info(request, "Veuillez sélectionner une boutique pour gérer les catégories.")
            return redirect('inventory:admin_dashboard')
        else:
            try:
                commercant = request.user.profil_commercant
                messages.info(request, "Veuillez sélectionner une boutique pour gérer les catégories.")
                return redirect('inventory:commercant_dashboard')
            except:
                messages.error(request, "Votre compte doit être migré vers la nouvelle architecture.")
                return redirect('inventory:home')
    
    # Récupérer les catégories de la boutique
    categories = Categorie.objects.filter(boutique=boutique)
    
    if request.method == 'POST':
        form = CategorieForm(request.POST)
        try:
            if form.is_valid():
                categorie = form.save(commit=False)
                categorie.boutique = boutique  # Associer la catégorie à la boutique
                categorie.save()
                messages.success(request, f'Catégorie "{categorie.nom}" ajoutée avec succès à {boutique.nom}.')
                return redirect(f'inventory:categories?boutique={boutique.id}')
            else:
                # Afficher les erreurs de validation du formulaire
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"Erreur dans le champ {field}: {error}")
        except Exception as e:
            # Capturer et afficher l'exception spécifique
            import traceback
            error_message = str(e)
            error_trace = traceback.format_exc()
            print(f"ERREUR lors de l'ajout de catégorie: {error_message}")
            print(f"Traceback: {error_trace}")
            messages.error(request, f"Une erreur s'est produite: {error_message}")
    else:
        form = CategorieForm()
    
    context = {
        'categories': categories,
        'form': form,
        'boutique': boutique
    }
    return render(request, 'inventory/categories.html', context)

@login_required
def liste_articles(request):
    """Page de gestion des articles."""
    
    # Récupérer la boutique depuis les paramètres GET
    boutique_id = request.GET.get('boutique')
    boutique = None
    
    if boutique_id:
        try:
            # Vérifier que l'utilisateur a accès à cette boutique
            if request.user.is_superuser:
                boutique = get_object_or_404(Boutique, id=boutique_id)
            else:
                commercant = request.user.profil_commercant
                boutique = get_object_or_404(Boutique, id=boutique_id, commercant=commercant)
        except:
            messages.error(request, "Boutique non trouvée ou accès non autorisé.")
            return redirect('inventory:home')
    else:
        # Si pas de boutique spécifiée, rediriger vers le dashboard approprié
        if request.user.is_superuser:
            messages.info(request, "Veuillez sélectionner une boutique pour voir les articles.")
            return redirect('inventory:admin_dashboard')
        else:
            try:
                commercant = request.user.profil_commercant
                messages.info(request, "Veuillez sélectionner une boutique pour voir les articles.")
                return redirect('inventory:commercant_dashboard')
            except:
                messages.error(request, "Votre compte doit être migré vers la nouvelle architecture.")
                return redirect('inventory:home')
    
    # Récupérer les articles et catégories de la boutique
    articles = Article.objects.filter(boutique=boutique)
    categories = Categorie.objects.filter(boutique=boutique)
    
    context = {
        'articles': articles,
        'categories': categories,
        'boutique': boutique
    }
    return render(request, 'inventory/articles.html', context)

@login_required
def liste_ventes(request):
    """Page de gestion des ventes."""
    # ⭐ ISOLATION: Filtrer les ventes selon le contexte utilisateur
    if request.user.is_superuser:
        # Super admin voit toutes les ventes
        ventes = Vente.objects.all().order_by('-date_vente')
        articles = Article.objects.filter(quantite_stock__gt=0)
    else:
        try:
            # Commerçant voit uniquement les ventes de ses boutiques
            commercant = request.user.profil_commercant
            ventes = Vente.objects.filter(
                boutique__commercant=commercant
            ).select_related('boutique', 'client_maui').order_by('-date_vente')
            articles = Article.objects.filter(
                boutique__commercant=commercant,
                quantite_stock__gt=0
            )
        except Commercant.DoesNotExist:
            # Utilisateur legacy sans profil commerçant - pas de ventes
            ventes = Vente.objects.none()
            articles = Article.objects.none()
    
    context = {
        'ventes': ventes,
        'articles': articles
    }
    return render(request, 'inventory/ventes.html', context)

@login_required
def supprimer_categorie(request, categorie_id):
    """Supprimer une catégorie."""
    categorie = get_object_or_404(Categorie, id=categorie_id)
    
    if request.method == 'POST':
        try:
            categorie.delete()
            messages.success(request, f'Catégorie "{categorie.nom}" supprimée avec succès.')
        except Exception as e:
            messages.error(request, f'Impossible de supprimer la catégorie : {str(e)}')
    
    return redirect('inventory:categories')

@login_required
def supprimer_article(request, article_id):
    """Supprimer un article."""
    article = get_object_or_404(Article, id=article_id)
    
    if request.method == 'POST':
        try:
            article.delete()
            messages.success(request, f'Article "{article.nom}" supprimé avec succès.')
        except Exception as e:
            messages.error(request, f'Impossible de supprimer l\'article : {str(e)}')
    
    return redirect('inventory:articles')


@login_required
def editer_categorie(request, categorie_id):
    categorie = get_object_or_404(Categorie, id=categorie_id)
    if request.method == 'POST':
        form = CategorieForm(request.POST, instance=categorie)
        if form.is_valid():
            form.save()
            return redirect('liste_categories')  # Redirige vers la liste après modification
    else:
        form = CategorieForm(instance=categorie)
    
    return render(request, 'inventory/editer_categorie.html', {
        'form': form,
        'categorie': categorie
    })


@login_required
def ajouter_categorie(request):
    """Ajouter une nouvelle catégorie."""
    if request.method == 'POST':
        form = CategorieForm(request.POST)
        if form.is_valid():
            categorie = form.save(commit=False)
            # Associer à la boutique si fournie dans les paramètres
            boutique_id = request.POST.get('boutique')
            if boutique_id:
                try:
                    boutique = Boutique.objects.get(id=boutique_id)
                    categorie.boutique = boutique
                except Boutique.DoesNotExist:
                    pass
            categorie.save()
            messages.success(request, 'Catégorie ajoutée avec succès!')
            
            # Redirection selon le contexte
            if boutique_id:
                return redirect('inventory:commercant_categories_boutique', boutique_id=boutique_id)
            else:
                return redirect('inventory:categories')
        else:
            messages.error(request, 'Erreur lors de l\'ajout de la catégorie.')
    else:
        form = CategorieForm()
    
    context = {
        'form': form,
        'boutique_id': request.GET.get('boutique') or request.POST.get('boutique')
    }
    return render(request, 'inventory/ajouter_categorie.html', context)


@login_required
def modifier_categorie(request, categorie_id):
    """Modifier une catégorie existante."""
    categorie = get_object_or_404(Categorie, id=categorie_id)
    
    if request.method == 'POST':
        form = CategorieForm(request.POST, instance=categorie)
        if form.is_valid():
            form.save()
            messages.success(request, 'Catégorie modifiée avec succès!')
            
            # Redirection selon le contexte
            boutique_id = request.POST.get('boutique')
            if boutique_id:
                return redirect('inventory:commercant_categories_boutique', boutique_id=boutique_id)
            else:
                return redirect('inventory:categories')
        else:
            messages.error(request, 'Erreur lors de la modification de la catégorie.')
    else:
        form = CategorieForm(instance=categorie)
    
    context = {
        'form': form,
        'categorie': categorie,
        'boutique_id': request.GET.get('boutique') or request.POST.get('boutique')
    }
    return render(request, 'inventory/modifier_categorie.html', context)


def user_login(request):
    """Vue pour la page de connexion."""
    if request.user.is_authenticated:
        return redirect('inventory:home')
        
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            next_url = request.POST.get('next', 'inventory:home')
            messages.success(request, f'Bienvenue, {user.username}!')
            return redirect(next_url)
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
            return render(request, 'inventory/login.html', {'error_message': "Nom d'utilisateur ou mot de passe incorrect."})
    
    return render(request, 'inventory/login.html')


def user_logout(request):
    """Vue pour la déconnexion."""
    logout(request)
    messages.success(request, "Vous avez été déconnecté avec succès.")
    return redirect('inventory:login')


@login_required
def change_password(request):
    """Vue pour permettre à l'utilisateur de modifier son mot de passe."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Mettre à jour la session pour éviter que l'utilisateur ne soit déconnecté
            update_session_auth_hash(request, user)
            messages.success(request, "Votre mot de passe a été modifié avec succès!")
            return redirect('inventory:home')
        else:
            messages.error(request, "Erreur lors de la modification du mot de passe. Veuillez corriger les erreurs ci-dessous.")
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'inventory/change_password.html', {
        'form': form
    })


@login_required
def generate_qr_pdf(request):
    """Vue pour générer un PDF contenant tous les codes QR des articles avec leur nom."""
    # Récupérer tous les articles
    articles = Article.objects.all().order_by('nom')
    
    # Générer le PDF
    pdf = generate_qr_codes_pdf(articles)
    
    # Créer la réponse HTTP avec le contenu PDF
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="catalogue_codes_qr.pdf"'
    
    return response


@login_required
def historique_ventes(request):
    """Page d'historique détaillé des ventes."""
    # ⭐ ISOLATION: Filtrer les ventes selon le contexte utilisateur
    if request.user.is_superuser:
        # Super admin voit toutes les ventes
        ventes = Vente.objects.all().order_by('-date_vente')
    else:
        try:
            # Commerçant voit uniquement les ventes de ses boutiques
            commercant = request.user.profil_commercant
            ventes = Vente.objects.filter(
                boutique__commercant=commercant
            ).select_related('boutique', 'client_maui').order_by('-date_vente')
        except Commercant.DoesNotExist:
            # Utilisateur legacy sans profil commerçant - pas de ventes
            ventes = Vente.objects.none()
    
    # Filtres de dates
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    mode_paiement = request.GET.get('mode_paiement')
    
    # Appliquer les filtres si nécessaire
    if date_debut:
        try:
            date_debut = datetime.strptime(date_debut, '%Y-%m-%d')
            ventes = ventes.filter(date_vente__gte=date_debut)
        except ValueError:
            pass
    
    if date_fin:
        try:
            date_fin = datetime.strptime(date_fin, '%Y-%m-%d')
            # Ajouter un jour pour inclure toute la journée de fin
            date_fin = date_fin + timedelta(days=1)
            ventes = ventes.filter(date_vente__lt=date_fin)
        except ValueError:
            pass
    
    if mode_paiement and mode_paiement != 'TOUS':
        ventes = ventes.filter(mode_paiement=mode_paiement)
    
    # Pagination
    paginator = Paginator(ventes, 15)  # 15 ventes par page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistiques
    stats = {
        'total_ventes': ventes.count(),
        'montant_total': ventes.aggregate(Sum('montant_total'))['montant_total__sum'] or 0,
        'ventes_par_mode': ventes.values('mode_paiement').annotate(
            count=Count('id'),
            total=Sum('montant_total')
        )
    }
    
    # Contexte pour le template
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'modes_paiement': dict(Vente._meta.get_field('mode_paiement').choices),
        'date_debut': date_debut.strftime('%Y-%m-%d') if isinstance(date_debut, datetime) else '',
        'date_fin': (date_fin - timedelta(days=1)).strftime('%Y-%m-%d') if isinstance(date_fin, datetime) else '',
        'mode_paiement_selected': mode_paiement or 'TOUS'
    }
    
    return render(request, 'inventory/historique_ventes.html', context)


def is_superuser(user):
    """Vérifie si l'utilisateur est un super-utilisateur."""
    return user.is_superuser


@login_required
@user_passes_test(is_superuser)
def gestion_utilisateurs(request):
    """Page de gestion des utilisateurs, réservée aux super-utilisateurs."""
    users = User.objects.all().order_by('-is_superuser', '-is_staff', 'username')
    
    context = {
        'users': users
    }
    return render(request, 'inventory/gestion_utilisateurs.html', context)


@login_required
@user_passes_test(is_superuser)
def creer_utilisateur(request):
    """Page pour créer un nouvel utilisateur, réservée aux super-utilisateurs."""
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Utilisateur "{user.username}" créé avec succès.')
            return redirect('inventory:gestion_utilisateurs')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Erreur dans le champ {field}: {error}")
    else:
        form = UserCreateForm()
    
    context = {
        'form': form
    }
    return render(request, 'inventory/creer_utilisateur.html', context)


@login_required
@user_passes_test(is_superuser)
def editer_utilisateur(request, user_id):
    """Page pour éditer un utilisateur existant, réservée aux super-utilisateurs."""
    user_to_edit = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user_to_edit)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Utilisateur "{user.username}" modifié avec succès.')
            return redirect('inventory:gestion_utilisateurs')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Erreur dans le champ {field}: {error}")
    else:
        form = UserEditForm(instance=user_to_edit)
    
    context = {
        'form': form,
        'user_to_edit': user_to_edit
    }
    return render(request, 'inventory/editer_utilisateur.html', context)


@login_required
@user_passes_test(is_superuser)
def supprimer_utilisateur(request, user_id):
    """Supprimer un utilisateur, réservé aux super-utilisateurs."""
    user_to_delete = get_object_or_404(User, id=user_id)
    
    # Ne pas permettre de supprimer son propre compte
    if user_to_delete == request.user:
        messages.error(request, 'Vous ne pouvez pas supprimer votre propre compte.')
        return redirect('inventory:gestion_utilisateurs')
    
    if request.method == 'POST':
        try:
            username = user_to_delete.username
            user_to_delete.delete()
            messages.success(request, f'Utilisateur "{username}" supprimé avec succès.')
        except Exception as e:
            messages.error(request, f'Impossible de supprimer l\'utilisateur : {str(e)}')
    
    return redirect('inventory:gestion_utilisateurs')


# ===== GESTION DES CLIENTS MAUI =====

@login_required
def gestion_clients_maui(request):
    """Page de gestion des clients MAUI - Redirection vers la nouvelle interface."""
    
    # Vérifier si l'utilisateur est un super administrateur
    if request.user.is_superuser:
        return redirect('inventory:admin_dashboard')
    
    # Vérifier si l'utilisateur a un profil commerçant
    try:
        commercant = request.user.profil_commercant
        return redirect('inventory:gestion_clients_maui_commercant')
    except:
        # Utilisateur legacy - afficher un message d'information
        messages.info(request, "Votre compte doit être migré vers la nouvelle architecture. Contactez l'administrateur.")
        return redirect('inventory:home')
    
    # Code legacy pour compatibilité (ne devrait plus être atteint)
    from django.db.models import Exists, OuterRef
    
    # Récupérer tous les clients associés aux boutiques du commerçant
    try:
        commercant = request.user.profil_commercant
        clients = Client.objects.filter(boutique__commercant=commercant).annotate(
            has_active_session=Exists(
                SessionClientMaui.objects.filter(
                    client=OuterRef('pk'),
                    est_active=True
                )
            )
        ).order_by('-derniere_activite')
    except:
        clients = Client.objects.none()
    
    # Statistiques
    clients_actifs = clients.filter(est_actif=True)
    clients_connectes = clients.filter(
        sessions__est_active=True,
        sessions__date_debut__gte=timezone.now() - timedelta(hours=24)
    ).distinct()
    
    # Sessions actives
    try:
        commercant = request.user.profil_commercant
        sessions_actives = SessionClientMaui.objects.filter(
            client__boutique__commercant=commercant,
            est_active=True
        ).select_related('client').order_by('-date_debut')
        
        # Ventes récentes par client
        ventes_recentes = Vente.objects.filter(
            boutique__commercant=commercant
        ).select_related('client_maui', 'boutique').order_by('-date_vente')[:10]
    except:
        sessions_actives = SessionClientMaui.objects.none()
        ventes_recentes = Vente.objects.none()
    
    context = {
        'clients': clients,
        'clients_actifs_count': clients_actifs.count(),
        'clients_connectes_count': clients_connectes.count(),
        'sessions_actives': sessions_actives,
        'ventes_recentes': ventes_recentes,
        'total_clients': clients.count(),
    }
    
    return render(request, 'inventory/gestion_clients_maui.html', context)


@login_required
def details_client_maui(request, client_id):
    """Page de détails d'un client MAUI spécifique."""
    # Vérifier si l'utilisateur a accès à ce client via ses boutiques
    try:
        commercant = request.user.profil_commercant
        client = get_object_or_404(Client, id=client_id, boutique__commercant=commercant)
    except:
        # Utilisateur legacy ou sans accès
        messages.error(request, "Accès non autorisé à ce client.")
        return redirect('inventory:home')
    
    # Ventes du client avec pagination
    ventes = Vente.objects.filter(client_maui=client).order_by('-date_vente')
    
    # Filtres de dates
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    
    if date_debut:
        try:
            date_debut_obj = datetime.strptime(date_debut, '%Y-%m-%d')
            ventes = ventes.filter(date_vente__gte=date_debut_obj)
        except ValueError:
            pass
    
    if date_fin:
        try:
            date_fin_obj = datetime.strptime(date_fin, '%Y-%m-%d') + timedelta(days=1)
            ventes = ventes.filter(date_vente__lt=date_fin_obj)
        except ValueError:
            pass
    
    # Pagination
    paginator = Paginator(ventes, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistiques du client
    stats = {
        'total_ventes': ventes.count(),
        'montant_total': ventes.aggregate(Sum('montant_total'))['montant_total__sum'] or 0,
        'ventes_aujourd_hui': ventes.filter(date_vente__date=timezone.now().date()).count(),
        'montant_aujourd_hui': ventes.filter(date_vente__date=timezone.now().date()).aggregate(Sum('montant_total'))['montant_total__sum'] or 0,
    }
    
    # Sessions récentes
    sessions_recentes = SessionClientMaui.objects.filter(client=client).order_by('-date_debut')[:10]
    
    context = {
        'client': client,
        'page_obj': page_obj,
        'stats': stats,
        'sessions_recentes': sessions_recentes,
        'date_debut': date_debut or '',
        'date_fin': date_fin or '',
    }
    
    return render(request, 'inventory/details_client_maui.html', context)


@login_required
def ajouter_client_maui(request):
    """Ajouter un nouveau client MAUI - Redirection vers la nouvelle interface."""
    
    # Vérifier si l'utilisateur est un super administrateur
    if request.user.is_superuser:
        messages.info(request, "Utilisez l'interface d'administration pour gérer les commerçants et leurs boutiques.")
        return redirect('inventory:admin_dashboard')
    
    # Vérifier si l'utilisateur a un profil commerçant
    try:
        commercant = request.user.profil_commercant
        # Rediriger vers l'ajout de boutique ou la gestion des clients
        if commercant.peut_ajouter_boutique:
            messages.info(request, "Créez d'abord une boutique, puis ajoutez-y un client MAUI.")
            return redirect('inventory:ajouter_boutique')
        else:
            return redirect('inventory:gestion_clients_maui_commercant')
    except:
        # Utilisateur legacy
        messages.warning(request, "Votre compte doit être migré vers la nouvelle architecture. Contactez l'administrateur.")
        return redirect('inventory:home')
    
    # Code legacy (ne devrait plus être utilisé)
    return render(request, 'inventory/ajouter_client_maui.html')


@login_required
def dashboard_clients_maui(request):
    """Dashboard avec vue d'ensemble des clients MAUI - Redirection vers la nouvelle interface."""
    
    # Vérifier si l'utilisateur est un super administrateur
    if request.user.is_superuser:
        return redirect('inventory:admin_dashboard')
    
    # Vérifier si l'utilisateur a un profil commerçant
    try:
        commercant = request.user.profil_commercant
        return redirect('inventory:commercant_dashboard')
    except:
        # Utilisateur legacy
        messages.info(request, "Votre compte doit être migré vers la nouvelle architecture. Contactez l'administrateur.")
        return redirect('inventory:home')
    
    # Code legacy pour compatibilité (ne devrait plus être atteint)
    try:
        commercant = request.user.profil_commercant
        # Statistiques générales
        total_clients = Client.objects.filter(boutique__commercant=commercant).count()
        clients_actifs = Client.objects.filter(boutique__commercant=commercant, est_actif=True).count()
        
        # Clients connectés dans les dernières 24h
        clients_connectes_24h = Client.objects.filter(
            boutique__commercant=commercant,
            sessions__est_active=True,
            sessions__date_debut__gte=timezone.now() - timedelta(hours=24)
        ).distinct().count()
        
        # Ventes du jour par client
        aujourd_hui = timezone.now().date()
        ventes_aujourd_hui = Vente.objects.filter(
            boutique__commercant=commercant,
            date_vente__date=aujourd_hui
        ).values('boutique__nom').annotate(
            total_ventes=Count('id'),
            montant_total=Sum('montant_total')
        ).order_by('-total_ventes')
        
        # Activité récente
        activite_recente = SessionClientMaui.objects.filter(
            client__boutique__commercant=commercant
        ).select_related('client').order_by('-date_debut')[:10]
    except:
        total_clients = 0
        clients_actifs = 0
        clients_connectes_24h = 0
        ventes_aujourd_hui = []
        activite_recente = []
    
    context = {
        'total_clients': total_clients,
        'clients_actifs': clients_actifs,
        'clients_connectes_24h': clients_connectes_24h,
        'ventes_aujourd_hui': ventes_aujourd_hui,
        'activite_recente': activite_recente,
    }
    
    return render(request, 'inventory/dashboard_clients_maui.html', context)

# ===== FIN GESTION DES CLIENTS MAUI =====