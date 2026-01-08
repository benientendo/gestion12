# views_commercant.py
# Vues pour l'interface commerçant multi-boutiques

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Count, Sum, Q, F
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from decimal import Decimal
from .models import Commercant, Boutique, Article, Vente, LigneVente, MouvementStock, Client, RapportCaisse, ArticleNegocie, RetourArticle, VenteRejetee, TransfertStock
from .forms import BoutiqueForm, ArticleForm
import json
import qrcode
from PIL import Image
import io
import uuid
from django.core.files.base import ContentFile

# ===== DÉCORATEURS ET UTILITAIRES =====

def generer_qr_code_article(article):
    """Génère un code QR pour un article et l'enregistre"""
    try:
        # Créer les données du QR code avec toutes les informations de l'article
        qr_data = {
            'id': article.id,
            'code': article.code,
            'nom': article.nom,
            'prix_vente': float(article.prix_vente),
            'boutique_id': article.boutique.id if article.boutique else None,
            'boutique_nom': article.boutique.nom if article.boutique else None
        }
        
        # Convertir en JSON pour le QR code
        qr_content = json.dumps(qr_data, ensure_ascii=False)
        
        # Créer le QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_content)
        qr.make(fit=True)
        
        # Créer l'image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Sauvegarder dans un buffer
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Créer le nom du fichier
        filename = f"qr_{article.code}_{article.id}.png"
        
        # Sauvegarder dans le champ qr_code de l'article
        article.qr_code.save(
            filename,
            ContentFile(buffer.read()),
            save=True
        )
        
        return True
        
    except Exception as e:
        print(f"Erreur lors de la génération du QR code pour l'article {article.id}: {str(e)}")
        return False

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

def boutique_access_required(view_func):
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

# ===== AUTHENTIFICATION =====

def login_commercant(request):
    """Page de connexion pour les commerçants"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            try:
                commercant = user.profil_commercant
                if commercant.est_actif:
                    login(request, user)
                    return redirect('inventory:commercant_dashboard')
                else:
                    messages.error(request, "Votre compte commerçant est désactivé. Veuillez contacter l'administrateur pour réactiver votre compte.")
            except Commercant.DoesNotExist:
                messages.error(request, "Vous n'avez pas de profil commerçant. Veuillez contacter l'administrateur.")
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
    
    return render(request, 'inventory/commercant/login.html')

@login_required
def logout_commercant(request):
    """Déconnexion du commerçant"""
    logout(request)
    messages.success(request, "Vous avez été déconnecté avec succès.")
    return redirect('inventory:login_commercant')

# ===== TABLEAU DE BORD COMMERÇANT =====

@login_required
@commercant_required
def dashboard_commercant(request):
    """Tableau de bord principal du commerçant"""
    commercant = request.user.profil_commercant
    
    # Statistiques générales - Debug
    boutiques_toutes = commercant.boutiques.all()
    boutiques_actives = commercant.boutiques.filter(est_active=True)
    
    # Séparer les dépôts des boutiques normales
    depots = commercant.boutiques.filter(est_depot=True)
    boutiques_normales = commercant.boutiques.filter(est_depot=False)
    
    print(f"DEBUG: Commerçant {commercant.nom_entreprise}")
    print(f"DEBUG: Total boutiques: {boutiques_toutes.count()}")
    print(f"DEBUG: Boutiques actives: {boutiques_actives.count()}")
    
    for b in boutiques_toutes:
        print(f"DEBUG: Boutique '{b.nom}' - est_active: {b.est_active}")
    
    # Utiliser les boutiques normales (sans dépôts) pour l'affichage principal
    boutiques_list = list(boutiques_normales)
    total_boutiques = len(boutiques_list)
    
    # Ajouter les statistiques pour chaque dépôt
    depots_list = list(depots)
    for depot in depots_list:
        depot.nb_articles = depot.articles.filter(est_actif=True).count()
        depot.valeur_stock = depot.articles.filter(est_actif=True).aggregate(
            total=Sum(F('quantite_stock') * F('prix_achat'))
        )['total'] or 0
        depot.nb_transferts_mois = TransfertStock.objects.filter(
            depot_source=depot,
            date_transfert__gte=timezone.now().replace(day=1)
        ).count()
    
    # Ajouter le compteur des ventes refusées du jour pour chaque boutique
    aujourd_hui = timezone.now().date()
    for boutique in boutiques_list:
        boutique.nb_ventes_refusees_jour = VenteRejetee.objects.filter(
            boutique=boutique,
            date_tentative__date=aujourd_hui
        ).count()
    
    boutiques = boutiques_list
    
    # Statistiques des 30 derniers jours
    date_debut = timezone.now() - timedelta(days=30)
    aujourd_hui = timezone.now().date()
    # Début du mois en cours (pour les dépenses mensuelles)
    debut_mois = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Calculs par boutique
    stats_boutiques = []
    total_ventes = 0
    total_ca = 0
    
    for boutique in boutiques:
        # Récupérer les ventes via les clients MAUI de la boutique (exclure les ventes annulées)
        try:
            ventes_boutique = Vente.objects.filter(
                client_maui__boutique=boutique,
                date_vente__gte=date_debut,
                paye=True,
                est_annulee=False
            )
            nb_ventes = ventes_boutique.count()
            ca_boutique = ventes_boutique.aggregate(total=Sum('montant_total'))['total'] or 0
        except (ValueError, TypeError):
            # Relations pas encore mises à jour après migration
            nb_ventes = 0
            ca_boutique = 0
        
        stats_boutiques.append({
            'boutique': boutique,
            'nb_ventes': nb_ventes,
            'chiffre_affaires': ca_boutique,
            'nb_articles': boutique.articles.count(),
            'nb_terminaux': boutique.clients.count()  # Utiliser clients au lieu de terminaux
        })
        
        total_ventes += nb_ventes
        total_ca += ca_boutique
    
    # Recette du jour (toutes boutiques, ventes payées, non annulées)
    ventes_jour = Vente.objects.filter(
        client_maui__boutique__in=boutiques,
        date_vente__date=aujourd_hui,
        paye=True,
        est_annulee=False
    )
    ca_jour = ventes_jour.aggregate(total=Sum('montant_total'))['total'] or 0

    # Valeur totale de la marchandise (stock) en CDF
    articles_commercant = Article.objects.filter(
        boutique__commercant=commercant,
        est_actif=True
    )
    valeur_marchandise = articles_commercant.aggregate(
        total=Sum(F('quantite_stock') * F('prix_achat'))
    )['total'] or 0

    # Dépenses totales de toutes les boutiques (rapports de caisse en CDF) sur le mois en cours
    depenses_qs = RapportCaisse.objects.filter(
        boutique__in=boutiques,
        devise='CDF',
        date_rapport__gte=debut_mois
    )
    depenses_totales = depenses_qs.aggregate(total=Sum('depense'))['total'] or 0

    # Articles en stock bas (tous les boutiques)
    articles_stock_bas = Article.objects.filter(
        boutique__commercant=commercant
    ).filter(
        quantite_stock__lte=5  # Seuil par défaut
    ).select_related('boutique')[:10]
    
    context = {
        'commercant': commercant,
        'boutiques': boutiques,  # Ajouter la liste des boutiques
        'depots': depots_list,  # Ajouter la liste des dépôts
        'total_boutiques': total_boutiques,
        'total_ventes': total_ventes,
        'total_ca': total_ca,
        'chiffre_affaires_30j': total_ca,  # Alias pour le template
        'recette_jour': ca_jour,
        'valeur_marchandise': valeur_marchandise,
        'depenses_totales': depenses_totales,
        'boutiques_avec_clients': boutiques_toutes.filter(clients__isnull=False).distinct().count(),
        'stats_boutiques': stats_boutiques,
        'articles_stock_bas': articles_stock_bas,
        'peut_ajouter_boutique': commercant.peut_creer_boutique()
    }
    
    return render(request, 'inventory/commercant/dashboard.html', context)

# ===== GESTION DES BOUTIQUES =====

@login_required
@commercant_required
def liste_boutiques(request):
    """Liste des boutiques du commerçant"""
    commercant = request.user.profil_commercant
    boutiques = commercant.boutiques.all().annotate(
        nb_articles=Count('articles'),
        nb_terminaux=Count('clients')
    )
    
    context = {
        'commercant': commercant,
        'boutiques': boutiques,
        'peut_ajouter_boutique': commercant.peut_creer_boutique()
    }
    
    return render(request, 'inventory/commercant/liste_boutiques.html', context)

@login_required
@commercant_required
def creer_boutique(request):
    """Créer une nouvelle boutique"""
    commercant = request.user.profil_commercant
    
    if not commercant.peut_creer_boutique():
        messages.error(request, f"Vous avez atteint la limite de {commercant.max_boutiques} boutique(s).")
        return redirect('inventory:commercant_boutiques')
    
    if request.method == 'POST':
        form = BoutiqueForm(request.POST)
        if form.is_valid():
            boutique = form.save(commit=False)
            boutique.commercant = commercant
            boutique.save()
            messages.success(request, f"Boutique '{boutique.nom}' créée avec succès!")
            return redirect('inventory:commercant_detail_boutique', boutique_id=boutique.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Erreur dans {field}: {error}")
    else:
        form = BoutiqueForm()
    
    context = {
        'commercant': commercant,
        'form': form
    }
    
    return render(request, 'inventory/commercant/ajouter_boutique.html', context)

@login_required
@commercant_required
@boutique_access_required
def detail_boutique(request, boutique_id):
    """Détail d'une boutique avec statistiques"""
    boutique = request.boutique
    
    # Statistiques des 30 derniers jours
    date_debut = timezone.now() - timedelta(days=30)
    
    # Récupérer les ventes via les clients MAUI de la boutique (exclure les ventes annulées)
    try:
        ventes_recentes = Vente.objects.filter(
            client_maui__boutique=boutique,
            date_vente__gte=date_debut,
            paye=True,
            est_annulee=False
        )
    except (ValueError, TypeError):
        # Relations pas encore mises à jour après migration
        ventes_recentes = Vente.objects.none()
    
    nb_ventes = ventes_recentes.count()
    ca_total = ventes_recentes.aggregate(total=Sum('montant_total'))['total'] or 0
    
    # Articles les plus vendus
    from django.db.models import Sum as DbSum
    articles_populaires = Article.objects.filter(
        boutique=boutique,
        lignevente__vente__date_vente__gte=date_debut,
        lignevente__vente__paye=True
    ).annotate(
        total_vendu=DbSum('lignevente__quantite')
    ).order_by('-total_vendu')[:5]
    
    # Terminaux actifs
    terminaux = boutique.clients.filter(est_actif=True)
    
    # Articles en stock bas
    articles_stock_bas = boutique.articles.filter(
        est_actif=True,
        quantite_stock__lte=boutique.alerte_stock_bas
    )[:10]
    
    # Statistiques supplémentaires pour le template
    total_articles = boutique.articles.count()
    total_categories = boutique.categories.count()
    total_ventes = nb_ventes
    chiffre_affaires = ca_total
    
    # Ventes récentes limitées pour affichage
    ventes_recentes_display = ventes_recentes[:10]
    
    # Compteur des ventes refusées du jour
    aujourd_hui = timezone.now().date()
    nb_ventes_refusees_jour = VenteRejetee.objects.filter(
        boutique=boutique,
        date_tentative__date=aujourd_hui
    ).count()
    
    context = {
        'boutique': boutique,
        'nb_ventes': nb_ventes,
        'ca_total': ca_total,
        'articles_populaires': articles_populaires,
        'terminaux': terminaux,
        'articles_stock_bas': articles_stock_bas,
        'nb_articles_total': total_articles,
        'total_articles': total_articles,
        'total_categories': total_categories,
        'total_ventes': total_ventes,
        'chiffre_affaires': chiffre_affaires,
        'ventes_recentes': ventes_recentes_display,
        'nb_ventes_refusees_jour': nb_ventes_refusees_jour
    }
    
    return render(request, 'inventory/commercant/details_boutique.html', context)

# ===== GESTION DES ARTICLES =====

@login_required
@commercant_required
@boutique_access_required
def articles_boutique(request, boutique_id):
    """Liste des articles d'une boutique"""
    boutique = request.boutique
    
    # Récupérer les filtres
    search = request.GET.get('search', '')
    categorie_id = request.GET.get('categorie', '')
    stock_filter = request.GET.get('stock', '')
    populaires_filter = request.GET.get('populaires', '')
    
    # Appliquer les filtres
    articles = boutique.articles.filter(est_actif=True)
    
    if search:
        articles = articles.filter(
            Q(nom__icontains=search) |
            Q(code__icontains=search) |
            Q(description__icontains=search)
        )
    
    if categorie_id:
        articles = articles.filter(categorie_id=categorie_id)
    
    if stock_filter == 'bas':
        articles = articles.filter(quantite_stock__lte=boutique.alerte_stock_bas)
    elif stock_filter == 'zero':
        articles = articles.filter(quantite_stock=0)
    elif stock_filter == 'normal':
        articles = articles.filter(quantite_stock__gt=boutique.alerte_stock_bas)
    
    # Filtre pour les articles populaires (ayant des ventes)
    if populaires_filter:
        from django.db.models import Count
        articles = articles.annotate(
            nb_ventes=Count('lignevente')
        ).filter(nb_ventes__gt=0).order_by('-nb_ventes')
    else:
        articles = articles.select_related('categorie').order_by('nom')
    
    # Catégories pour le filtre
    categories = boutique.categories.all()
    
    # Calculer le nombre d'articles en stock bas
    articles_stock_bas = boutique.articles.filter(
        quantite_stock__lte=boutique.alerte_stock_bas,
        est_actif=True
    ).count()
    
    context = {
        'boutique': boutique,
        'articles': articles,
        'categories': categories,
        'articles_stock_bas': articles_stock_bas,
        'search': search,
        'categorie_id': int(categorie_id) if categorie_id else None,
        'stock_filter': stock_filter,
        'populaires_filter': populaires_filter
    }
    
    return render(request, 'inventory/commercant/articles_boutique.html', context)

@login_required
@commercant_required
@boutique_access_required
def categories_boutique(request, boutique_id):
    """Liste des catégories d'une boutique"""
    boutique = request.boutique
    
    # Récupérer les catégories de la boutique
    categories = boutique.categories.all().order_by('nom')
    
    # Statistiques par catégorie
    categories_stats = []
    for categorie in categories:
        nb_articles = categorie.articles.filter(est_actif=True).count()
        categories_stats.append({
            'categorie': categorie,
            'nb_articles': nb_articles
        })
    
    context = {
        'boutique': boutique,
        'categories': categories,
        'categories_stats': categories_stats,
        'total_categories': categories.count()
    }
    
    return render(request, 'inventory/commercant/categories_boutique.html', context)

# ===== GESTION DES TERMINAUX =====

@login_required
@commercant_required
@boutique_access_required
def terminaux_boutique(request, boutique_id):
    """Gestion des terminaux MAUI d'une boutique"""
    boutique = request.boutique
    terminaux = boutique.clients.all().order_by('nom_terminal')
    
    context = {
        'boutique': boutique,
        'terminaux': terminaux
    }
    
    return render(request, 'inventory/commercant/terminaux_boutique.html', context)

@login_required
@commercant_required
@boutique_access_required
def creer_terminal(request, boutique_id):
    """Créer un nouveau terminal MAUI"""
    boutique = request.boutique
    
    if request.method == 'POST':
        nom_terminal = request.POST.get('nom_terminal')
        numero_serie = request.POST.get('numero_serie')
        nom_utilisateur = request.POST.get('nom_utilisateur', '')
        
        if nom_terminal and numero_serie:
            # Vérifier l'unicité du numéro de série
            if TerminalMaui.objects.filter(numero_serie=numero_serie).exists():
                messages.error(request, "Ce numéro de série existe déjà.")
            else:
                terminal = TerminalMaui.objects.create(
                    nom_terminal=nom_terminal,
                    boutique=boutique,
                    numero_serie=numero_serie,
                    nom_utilisateur=nom_utilisateur
                )
                
                messages.success(request, f"Terminal '{nom_terminal}' créé avec succès!")
                messages.info(request, f"Clé API générée: {terminal.cle_api}")
                return redirect('inventory:commercant_terminaux_boutique', boutique_id=boutique.id)
        else:
            messages.error(request, "Nom du terminal et numéro de série sont requis.")
    
    context = {
        'boutique': boutique
    }
    
    return render(request, 'inventory/commercant/ajouter_client_maui.html', context)

# ===== API AJAX =====

@login_required
@commercant_required
def api_stats_boutique(request, boutique_id):
    """API pour récupérer les statistiques d'une boutique en temps réel"""
    try:
        commercant = request.user.profil_commercant
        boutique = get_object_or_404(Boutique, id=boutique_id, commercant=commercant)
        
        # Statistiques d'aujourd'hui
        aujourd_hui = timezone.now().date()
        try:
            ventes_aujourd_hui = Vente.objects.filter(
                boutique=boutique,
                date_vente__date=aujourd_hui,
                paye=True
            )
        except (ValueError, TypeError):
            # Relations pas encore mises à jour après migration
            ventes_aujourd_hui = Vente.objects.none()
        
        nb_ventes = ventes_aujourd_hui.count()
        ca_aujourd_hui_brut = ventes_aujourd_hui.aggregate(total=Sum('montant_total'))['total'] or 0

        depenses_appliquees_aujourd_hui = RapportCaisse.objects.filter(
            boutique=boutique,
            date_rapport__date=aujourd_hui,
            depense_appliquee=True
        ).aggregate(total=Sum('depense'))['total'] or 0

        ca_aujourd_hui_net = ca_aujourd_hui_brut - depenses_appliquees_aujourd_hui
        
        # Terminaux connectés
        terminaux_actifs = boutique.clients.filter(
            est_actif=True,
            sessions__est_active=True
        ).distinct().count()
        
        return JsonResponse({
            'success': True,
            'stats': {
                'ventes_aujourd_hui': nb_ventes,
                'ca_aujourd_hui': float(ca_aujourd_hui_net),
                'ca_aujourd_hui_brut': float(ca_aujourd_hui_brut),
                'depenses_appliquees_aujourd_hui': float(depenses_appliquees_aujourd_hui),
                'terminaux_connectes': terminaux_actifs
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# ===== GESTION AVANCÉE DES BOUTIQUES =====

@login_required
@commercant_required
@boutique_access_required
def modifier_boutique(request, boutique_id):
    """Modifier une boutique"""
    boutique = request.boutique
    
    if request.method == 'POST':
        form = BoutiqueForm(request.POST, instance=boutique)
        if form.is_valid():
            form.save()
            messages.success(request, f"Boutique '{boutique.nom}' modifiée avec succès!")
            return redirect('inventory:commercant_detail_boutique', boutique_id=boutique.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Erreur dans {field}: {error}")
    else:
        form = BoutiqueForm(instance=boutique)
    
    context = {
        'boutique': boutique,
        'form': form
    }
    
    return render(request, 'inventory/commercant/modifier_boutique.html', context)

@login_required
@commercant_required
@boutique_access_required
def supprimer_boutique(request, boutique_id):
    """Supprimer une boutique"""
    boutique = request.boutique
    
    if request.method == 'POST':
        nom_boutique = boutique.nom
        boutique.delete()
        messages.success(request, f"Boutique '{nom_boutique}' supprimée avec succès!")
        return redirect('inventory:commercant_boutiques')
    
    context = {
        'boutique': boutique
    }
    
    return render(request, 'inventory/commercant/supprimer_boutique.html', context)

@login_required
@commercant_required
@boutique_access_required
def toggle_boutique_pos(request, boutique_id):
    boutique = request.boutique
    boutique.pos_autorise = not boutique.pos_autorise
    boutique.save(update_fields=['pos_autorise'])
    if boutique.pos_autorise:
        messages.success(request, f"POS MAUI autorisé pour la boutique '{boutique.nom}'.")
    else:
        messages.warning(request, f"POS MAUI désactivé pour la boutique '{boutique.nom}'. Aucun terminal ne pourra enregistrer de ventes.")
    return redirect('inventory:commercant_dashboard')

@login_required
@commercant_required
@boutique_access_required
def entrer_boutique(request, boutique_id):
    """Entrer dans une boutique (dashboard boutique)"""
    boutique = request.boutique
    
    # Statistiques de base
    nb_articles = boutique.articles.count()
    nb_terminaux = boutique.clients.count()
    
    # Ventes d'aujourd'hui (exclure les ventes annulées)
    date_aujourd_hui = timezone.now().date()
    try:
        ventes_aujourd_hui = Vente.objects.filter(
            boutique=boutique,
            date_vente__date=date_aujourd_hui,
            paye=True,
            est_annulee=False
        )
        nb_ventes_aujourd_hui = ventes_aujourd_hui.count()
        ca_aujourd_hui_brut = ventes_aujourd_hui.aggregate(total=Sum('montant_total'))['total'] or 0
    except (ValueError, TypeError):
        nb_ventes_aujourd_hui = 0
        ca_aujourd_hui_brut = 0

    depenses_appliquees_ca_jour = RapportCaisse.objects.filter(
        boutique=boutique,
        date_rapport__date=date_aujourd_hui,
        depense_appliquee=True
    ).aggregate(total=Sum('depense'))['total'] or 0

    ca_aujourd_hui = ca_aujourd_hui_brut - depenses_appliquees_ca_jour
    
    # Ventes du mois en cours (exclure les ventes annulées)
    try:
        premier_jour_mois = timezone.now().date().replace(day=1)
        ventes_mois = Vente.objects.filter(
            boutique=boutique,
            date_vente__date__gte=premier_jour_mois,
            paye=True,
            est_annulee=False
        )
        nb_ventes_mois = ventes_mois.count()
        ca_mois_brut = ventes_mois.aggregate(total=Sum('montant_total'))['total'] or 0
    except (ValueError, TypeError):
        nb_ventes_mois = 0
        ca_mois_brut = 0

    depenses_appliquees_ca_mois = RapportCaisse.objects.filter(
        boutique=boutique,
        date_rapport__date__gte=premier_jour_mois,
        date_rapport__date__lte=date_aujourd_hui,
        depense_appliquee=True
    ).aggregate(total=Sum('depense'))['total'] or 0

    ca_mois = ca_mois_brut - depenses_appliquees_ca_mois
    
    # Variables supplémentaires pour le template dashboard.html
    total_articles = nb_articles
    total_categories = boutique.categories.count()
    ca_jour = ca_aujourd_hui
    
    # Valeur totale du stock disponible (prix de vente x quantité)
    try:
        valeur_stock_disponible = boutique.articles.filter(
            est_actif=True,
            quantite_stock__gt=0
        ).aggregate(
            total=Sum(F('prix_vente') * F('quantite_stock'))
        )['total'] or 0
    except Exception:
        valeur_stock_disponible = 0
    
    # Articles en stock faible
    try:
        articles_stock_faible = boutique.articles.filter(
            est_actif=True,
            quantite_stock__lte=boutique.alerte_stock_bas
        )
    except:
        articles_stock_faible = boutique.articles.none()
    
    # Mouvements de stock des 7 derniers jours
    try:
        date_7_jours = timezone.now() - timezone.timedelta(days=7)
        mouvements_recents = MouvementStock.objects.filter(
            article__boutique=boutique,
            date_mouvement__gte=date_7_jours
        ).count()
    except:
        mouvements_recents = 0
    
    # Ventes récentes (exclure les ventes annulées)
    try:
        ventes_recentes = Vente.objects.filter(
            client_maui__boutique=boutique,
            est_annulee=False
        ).order_by('-date_vente')[:10]
    except:
        ventes_recentes = Vente.objects.none()
    
    # Données pour graphiques (simplifiées)
    labels_jours = []
    ca_quotidien = []
    
    context = {
        'boutique': boutique,
        'nb_articles': nb_articles,
        'nb_terminaux': nb_terminaux,
        'nb_ventes_aujourd_hui': nb_ventes_aujourd_hui,
        'ca_aujourd_hui': ca_aujourd_hui,
        'ca_aujourd_hui_brut': ca_aujourd_hui_brut,
        'depenses_appliquees_ca_jour': depenses_appliquees_ca_jour,
        'total_articles': total_articles,
        'total_categories': total_categories,
        'ca_mois': ca_mois,
        'ca_mois_brut': ca_mois_brut,
        'depenses_appliquees_ca_mois': depenses_appliquees_ca_mois,
        'ca_jour': ca_jour,
        'valeur_stock_disponible': valeur_stock_disponible,
        'articles_stock_faible': articles_stock_faible,
        'mouvements_recents': mouvements_recents,
        'ventes_recentes': ventes_recentes,
        'labels_jours': labels_jours,
        'ca_quotidien': ca_quotidien
    }
    
    return render(request, 'inventory/boutique/dashboard.html', context)

@login_required
@commercant_required
@boutique_access_required
def ajouter_client_maui_boutique(request, boutique_id):
    """Ajouter un client MAUI à une boutique spécifique"""
    boutique = request.boutique
    
    if request.method == 'POST':
        nom_terminal = request.POST.get('nom_terminal')
        numero_serie = request.POST.get('numero_serie')
        description = request.POST.get('description', '')
        
        if nom_terminal and numero_serie:
            # Vérifier l'unicité du numéro de série
            if Client.objects.filter(numero_serie=numero_serie).exists():
                messages.error(request, "Ce numéro de série existe déjà.")
            else:
                client = Client.objects.create(
                    nom_terminal=nom_terminal,
                    boutique=boutique,
                    compte_proprietaire=boutique.commercant.user,
                    numero_serie=numero_serie,
                    description=description
                )
                
                messages.success(request, f"Terminal '{nom_terminal}' créé avec succès!")
                messages.info(request, f"Clé API générée: {client.cle_api}")
                return redirect('inventory:commercant_detail_boutique', boutique_id=boutique.id)
        else:
            messages.error(request, "Nom du terminal et numéro de série sont requis.")
    
    context = {
        'boutique': boutique
    }
    
    return render(request, 'inventory/commercant/ajouter_client_maui.html', context)

@login_required
@commercant_required
@boutique_access_required
def rapport_ca_quotidien(request, boutique_id):
    """Afficher le rapport du chiffre d'affaires pour une journée donnée (par défaut aujourd'hui)"""
    boutique = request.boutique

    # Récupérer la date ciblée (par défaut aujourd'hui)
    date_str = request.GET.get('date')
    if date_str:
        try:
            date_cible = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            date_cible = timezone.now().date()
    else:
        date_cible = timezone.now().date()

    ventes = Vente.objects.filter(
        boutique=boutique,
        date_vente__date=date_cible,
        paye=True,
        est_annulee=False
    ).select_related('client_maui').prefetch_related('lignes__article')

    total_ventes = ventes.count()
    total_ca = ventes.aggregate(total=Sum('montant_total'))['total'] or 0

    depenses_appliquees_qs = RapportCaisse.objects.filter(
        boutique=boutique,
        date_rapport__date=date_cible,
        depense_appliquee=True
    )
    total_depenses_appliquees = depenses_appliquees_qs.aggregate(total=Sum('depense'))['total'] or 0

    total_ca_brut = total_ca
    total_ca_net = total_ca_brut - total_depenses_appliquees

    ventes_par_mode = ventes.values('mode_paiement').annotate(
        count=Count('id'),
        total=Sum('montant_total')
    )
    
    # ===== CALCUL DES BÉNÉFICES =====
    # Calculer le coût d'achat total et le bénéfice brut
    total_cout_achat = Decimal('0')
    total_benefice_brut = Decimal('0')
    articles_sans_prix_achat = []  # Articles avec prix_achat = 0
    
    for vente in ventes:
        for ligne in vente.lignes.all():
            if ligne.article:
                prix_achat = ligne.article.prix_achat or Decimal('0')
                cout_achat_ligne = prix_achat * ligne.quantite
                prix_vente_ligne = ligne.prix_unitaire * ligne.quantite
                total_cout_achat += cout_achat_ligne
                total_benefice_brut += (prix_vente_ligne - cout_achat_ligne)
                
                # Détecter les articles sans prix d'achat
                if prix_achat <= 0 and ligne.article.nom not in articles_sans_prix_achat:
                    articles_sans_prix_achat.append(ligne.article.nom)
    
    # Bénéfice net = Bénéfice brut - Dépenses appliquées
    total_benefice_net = total_benefice_brut - total_depenses_appliquees
    
    # Marge bénéficiaire en pourcentage
    marge_beneficiaire = 0
    if total_ca_brut > 0:
        marge_beneficiaire = (total_benefice_brut / total_ca_brut) * 100
    
    # Avertissement si calcul incomplet
    benefice_incomplet = len(articles_sans_prix_achat) > 0

    context = {
        'boutique': boutique,
        'ventes': ventes,
        'date_cible': date_cible,
        'total_ventes': total_ventes,
        'total_ca': total_ca_net,
        'total_ca_brut': total_ca_brut,
        'total_depenses_appliquees': total_depenses_appliquees,
        'ventes_par_mode': ventes_par_mode,
        # Données de bénéfices
        'total_cout_achat': total_cout_achat,
        'total_benefice_brut': total_benefice_brut,
        'total_benefice_net': total_benefice_net,
        'marge_beneficiaire': marge_beneficiaire,
        'benefice_incomplet': benefice_incomplet,
        'articles_sans_prix_achat': articles_sans_prix_achat,
    }

    return render(request, 'inventory/commercant/rapport_ca_quotidien.html', context)

@login_required
@commercant_required
@boutique_access_required
def rapport_ca_mensuel(request, boutique_id):
    """Afficher le rapport du chiffre d'affaires mensuel"""
    boutique = request.boutique
    
    # Récupérer le mois et l'année depuis les paramètres GET (optionnel)
    try:
        annee = int(request.GET.get('annee', timezone.now().year))
        mois = int(request.GET.get('mois', timezone.now().month))
    except (ValueError, TypeError):
        annee = timezone.now().year
        mois = timezone.now().month
    
    # Noms des mois en français
    mois_noms = {
        1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril',
        5: 'Mai', 6: 'Juin', 7: 'Juillet', 8: 'Août',
        9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
    }
    nom_mois = mois_noms.get(mois, 'Mois')
    
    # Calculer le premier et dernier jour du mois
    from calendar import monthrange
    premier_jour = datetime(annee, mois, 1).date()
    dernier_jour_num = monthrange(annee, mois)[1]
    dernier_jour = datetime(annee, mois, dernier_jour_num).date()
    
    rapports_jours = []
    current_date = premier_jour
    total_ca = 0
    total_ventes = 0
    total_ca_brut = 0
    total_depenses_appliquees = 0
    
    # Parcourir tous les jours du mois
    while current_date <= dernier_jour:
        ventes_jour = Vente.objects.filter(
            boutique=boutique,
            date_vente__date=current_date,
            paye=True,
            est_annulee=False
        )
        nb_ventes = ventes_jour.count()
        ca_jour_brut = ventes_jour.aggregate(total=Sum('montant_total'))['total'] or 0

        depenses_jour = RapportCaisse.objects.filter(
            boutique=boutique,
            date_rapport__date=current_date,
            depense_appliquee=True
        ).aggregate(total=Sum('depense'))['total'] or 0

        ca_jour = ca_jour_brut - depenses_jour
        
        rapports_jours.append({
            'date': current_date,
            'nb_ventes': nb_ventes,
            'ca': ca_jour,
            'ca_brut': ca_jour_brut,
            'depenses_appliquees': depenses_jour
        })
        
        total_ventes += nb_ventes
        total_ca += ca_jour
        total_ca_brut += ca_jour_brut
        total_depenses_appliquees += depenses_jour
        current_date += timedelta(days=1)
    
    # Inverser pour avoir les dates les plus récentes en premier
    rapports_jours.reverse()
    
    # Calculer mois précédent et suivant pour navigation
    if mois == 1:
        mois_precedent = 12
        annee_precedente = annee - 1
    else:
        mois_precedent = mois - 1
        annee_precedente = annee
    
    if mois == 12:
        mois_suivant = 1
        annee_suivante = annee + 1
    else:
        mois_suivant = mois + 1
        annee_suivante = annee
    
    context = {
        'boutique': boutique,
        'rapports_jours': rapports_jours,
        'total_ventes': total_ventes,
        'total_ca': total_ca,
        'total_ca_brut': total_ca_brut,
        'total_depenses_appliquees': total_depenses_appliquees,
        'mois': mois,
        'annee': annee,
        'nom_mois': nom_mois,
        'mois_precedent': mois_precedent,
        'annee_precedente': annee_precedente,
        'mois_suivant': mois_suivant,
        'annee_suivante': annee_suivante,
    }
    
    return render(request, 'inventory/commercant/rapport_ca_mensuel.html', context)

@login_required
@commercant_required
@boutique_access_required
def rapports_caisse_boutique(request, boutique_id):
    """Liste des rapports de caisse envoyés depuis les terminaux MAUI pour une boutique."""
    boutique = request.boutique

    rapports = RapportCaisse.objects.filter(
        boutique=boutique
    ).select_related('terminal').order_by('-date_rapport', '-created_at')

    # Filtres optionnels
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    terminal_id = request.GET.get('terminal_id')

    if date_debut:
        try:
            d = datetime.strptime(date_debut, '%Y-%m-%d').date()
            rapports = rapports.filter(date_rapport__date__gte=d)
        except ValueError:
            pass

    if date_fin:
        try:
            d = datetime.strptime(date_fin, '%Y-%m-%d').date()
            rapports = rapports.filter(date_rapport__date__lte=d)
        except ValueError:
            pass

    terminal_selected = 'TOUS'
    if terminal_id:
        if terminal_id != 'TOUS':
            try:
                terminal_id_int = int(terminal_id)
                rapports = rapports.filter(terminal_id=terminal_id_int)
                terminal_selected = terminal_id_int
            except (TypeError, ValueError):
                terminal_selected = 'TOUS'

    terminaux = boutique.clients.all().order_by('nom_terminal')

    # Statistiques simples
    stats = rapports.aggregate(total_depense=Sum('depense'))
    total_depense = stats['total_depense'] or 0

    # Notifications de rapports non lus (style "Facebook")
    now = timezone.now()
    boutique.derniere_lecture_rapports_caisse = now
    boutique.save(update_fields=['derniere_lecture_rapports_caisse'])

    # Sur cette page, tous les rapports de caisse sont considérés comme lus
    unread_rapports_count = 0

    # Articles négociés non lus
    if boutique.derniere_lecture_articles_negocies:
        unread_articles_negocies_count = ArticleNegocie.objects.filter(
            boutique=boutique,
            created_at__gt=boutique.derniere_lecture_articles_negocies
        ).count()
    else:
        unread_articles_negocies_count = ArticleNegocie.objects.filter(
            boutique=boutique
        ).count()

    # Retours d'articles non lus
    if boutique.derniere_lecture_retours_articles:
        unread_retours_count = RetourArticle.objects.filter(
            boutique=boutique,
            created_at__gt=boutique.derniere_lecture_retours_articles
        ).count()
    else:
        unread_retours_count = RetourArticle.objects.filter(
            boutique=boutique
        ).count()

    context = {
        'boutique': boutique,
        'rapports': rapports,
        'terminaux': terminaux,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'terminal_selected': terminal_selected,
        'total_depense': total_depense,
        'unread_rapports_count': unread_rapports_count,
        'unread_articles_negocies_count': unread_articles_negocies_count,
        'unread_retours_count': unread_retours_count,
    }

    return render(request, 'inventory/commercant/rapports_caisse_boutique.html', context)


@login_required
@commercant_required
@boutique_access_required
def articles_negocies_boutique(request, boutique_id):
    boutique = request.boutique

    articles = ArticleNegocie.objects.filter(
        boutique=boutique
    ).select_related('terminal', 'article').order_by('-date_operation', '-created_at')

    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    terminal_id = request.GET.get('terminal_id')

    if date_debut:
        try:
            d = datetime.strptime(date_debut, '%Y-%m-%d').date()
            articles = articles.filter(date_operation__date__gte=d)
        except ValueError:
            pass

    if date_fin:
        try:
            d = datetime.strptime(date_fin, '%Y-%m-%d').date()
            articles = articles.filter(date_operation__date__lte=d)
        except ValueError:
            pass

    terminal_selected = 'TOUS'
    if terminal_id:
        if terminal_id != 'TOUS':
            try:
                terminal_id_int = int(terminal_id)
                articles = articles.filter(terminal_id=terminal_id_int)
                terminal_selected = terminal_id_int
            except (TypeError, ValueError):
                terminal_selected = 'TOUS'

    terminaux = boutique.clients.all().order_by('nom_terminal')

    stats = articles.aggregate(total_montant=Sum('montant_negocie'))
    total_montant = stats['total_montant'] or 0

    # Notifications de rapports non lus (style "Facebook")
    now = timezone.now()
    boutique.derniere_lecture_articles_negocies = now
    boutique.save(update_fields=['derniere_lecture_articles_negocies'])

    # Sur cette page, tous les articles négociés sont considérés comme lus
    unread_articles_negocies_count = 0

    # Rapports de caisse non lus
    if boutique.derniere_lecture_rapports_caisse:
        unread_rapports_count = RapportCaisse.objects.filter(
            boutique=boutique,
            created_at__gt=boutique.derniere_lecture_rapports_caisse
        ).count()
    else:
        unread_rapports_count = RapportCaisse.objects.filter(
            boutique=boutique
        ).count()

    # Retours d'articles non lus
    if boutique.derniere_lecture_retours_articles:
        unread_retours_count = RetourArticle.objects.filter(
            boutique=boutique,
            created_at__gt=boutique.derniere_lecture_retours_articles
        ).count()
    else:
        unread_retours_count = RetourArticle.objects.filter(
            boutique=boutique
        ).count()

    # Statut d'application des négociations (vente déjà créée ou non)
    article_ids = list(articles.values_list('id', flat=True))
    applied_negociations_ids = []
    if article_ids:
        numero_map = {f"NEG-{boutique.id}-{nid}": nid for nid in article_ids}
        existing_num = Vente.objects.filter(
            boutique=boutique,
            numero_facture__in=numero_map.keys()
        ).values_list('numero_facture', flat=True)
        applied_negociations_ids = [
            numero_map[nf]
            for nf in existing_num
            if nf in numero_map
        ]

    context = {
        'boutique': boutique,
        'articles_negocies': articles,
        'terminaux': terminaux,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'terminal_selected': terminal_selected,
        'total_montant': total_montant,
        'unread_rapports_count': unread_rapports_count,
        'unread_articles_negocies_count': unread_articles_negocies_count,
        'unread_retours_count': unread_retours_count,
        'applied_negociations_ids': applied_negociations_ids,
    }

    return render(request, 'inventory/commercant/articles_negocies_boutique.html', context)


@login_required
@commercant_required
@boutique_access_required
def retours_articles_boutique(request, boutique_id):
    boutique = request.boutique

    retours = RetourArticle.objects.filter(
        boutique=boutique
    ).select_related('terminal', 'article').order_by('-date_operation', '-created_at')

    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    terminal_id = request.GET.get('terminal_id')

    if date_debut:
        try:
            d = datetime.strptime(date_debut, '%Y-%m-%d').date()
            retours = retours.filter(date_operation__date__gte=d)
        except ValueError:
            pass

    if date_fin:
        try:
            d = datetime.strptime(date_fin, '%Y-%m-%d').date()
            retours = retours.filter(date_operation__date__lte=d)
        except ValueError:
            pass

    terminal_selected = 'TOUS'
    if terminal_id:
        if terminal_id != 'TOUS':
            try:
                terminal_id_int = int(terminal_id)
                retours = retours.filter(terminal_id=terminal_id_int)
                terminal_selected = terminal_id_int
            except (TypeError, ValueError):
                terminal_selected = 'TOUS'

    terminaux = boutique.clients.all().order_by('nom_terminal')

    stats = retours.aggregate(total_montant=Sum('montant_retourne'))
    total_montant = stats['total_montant'] or 0

    # Notifications de rapports non lus (style "Facebook")
    now = timezone.now()
    boutique.derniere_lecture_retours_articles = now
    boutique.save(update_fields=['derniere_lecture_retours_articles'])

    # Sur cette page, tous les retours d'articles sont considérés comme lus
    unread_retours_count = 0

    # Rapports de caisse non lus
    if boutique.derniere_lecture_rapports_caisse:
        unread_rapports_count = RapportCaisse.objects.filter(
            boutique=boutique,
            created_at__gt=boutique.derniere_lecture_rapports_caisse
        ).count()
    else:
        unread_rapports_count = RapportCaisse.objects.filter(
            boutique=boutique
        ).count()

    # Articles négociés non lus
    if boutique.derniere_lecture_articles_negocies:
        unread_articles_negocies_count = ArticleNegocie.objects.filter(
            boutique=boutique,
            created_at__gt=boutique.derniere_lecture_articles_negocies
        ).count()
    else:
        unread_articles_negocies_count = ArticleNegocie.objects.filter(
            boutique=boutique
        ).count()

    context = {
        'boutique': boutique,
        'retours_articles': retours,
        'terminaux': terminaux,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'terminal_selected': terminal_selected,
        'total_montant': total_montant,
        'unread_rapports_count': unread_rapports_count,
        'unread_articles_negocies_count': unread_articles_negocies_count,
        'unread_retours_count': unread_retours_count,
    }

    return render(request, 'inventory/commercant/retours_articles_boutique.html', context)


@login_required
@commercant_required
@boutique_access_required
def appliquer_article_negocie(request, boutique_id, negociation_id):
    boutique = request.boutique
    negociation = get_object_or_404(ArticleNegocie, id=negociation_id, boutique=boutique)

    if request.method != 'POST':
        return HttpResponseForbidden("Méthode non autorisée")

    # Idempotence simple : numéro de facture déterministe basé sur la boutique et l'ID de la négociation
    numero_facture = f"NEG-{boutique.id}-{negociation.id}"
    if Vente.objects.filter(numero_facture=numero_facture).exists():
        messages.warning(request, "Cette négociation a déjà été appliquée à la recette.")
        return redirect('inventory:commercant_articles_negocies_boutique', boutique_id=boutique.id)

    if not negociation.article:
        messages.error(request, "Impossible d'appliquer cette négociation car l'article lié est introuvable.")
        return redirect('inventory:commercant_articles_negocies_boutique', boutique_id=boutique.id)

    article = negociation.article
    if article.boutique_id != boutique.id:
        messages.error(request, "Cet article n'appartient plus à cette boutique.")
        return redirect('inventory:commercant_articles_negocies_boutique', boutique_id=boutique.id)

    quantite = negociation.quantite or 0
    if quantite <= 0:
        messages.error(request, "Quantité invalide pour cette négociation.")
        return redirect('inventory:commercant_articles_negocies_boutique', boutique_id=boutique.id)

    montant_unitaire = negociation.montant_negocie or Decimal('0')
    montant_total = montant_unitaire * quantite
    if montant_total <= 0:
        messages.error(request, "Montant négocié invalide pour cette négociation.")
        return redirect('inventory:commercant_articles_negocies_boutique', boutique_id=boutique.id)

    # Vérifier le stock disponible avant de lancer la transaction
    if article.quantite_stock < quantite:
        messages.error(
            request,
            f"Stock insuffisant pour l'article {article.code}. Stock disponible : {article.quantite_stock}, quantité demandée : {quantite}."
        )
        return redirect('inventory:commercant_articles_negocies_boutique', boutique_id=boutique.id)

    terminal = negociation.terminal

    try:
        with transaction.atomic():
            # Créer la vente comme si elle venait de MAUI
            vente = Vente.objects.create(
                numero_facture=numero_facture,
                date_vente=timezone.now(),
                montant_total=montant_total,
                mode_paiement='CASH',
                paye=True,
                boutique=boutique,
                client_maui=terminal,
                adresse_ip_client=request.META.get('REMOTE_ADDR'),
                version_app_maui=terminal.version_app_maui if terminal else ''
            )

            # Créer la ligne de vente
            LigneVente.objects.create(
                vente=vente,
                article=article,
                quantite=quantite,
                prix_unitaire=montant_unitaire,
            )

            # Mettre à jour le stock de l'article et journaliser le mouvement
            stock_avant = article.quantite_stock
            article.quantite_stock = stock_avant - quantite
            article.save(update_fields=['quantite_stock'])

            MouvementStock.objects.create(
                article=article,
                type_mouvement='VENTE',
                quantite=-quantite,
                stock_avant=stock_avant,
                stock_apres=article.quantite_stock,
                reference_document=vente.numero_facture,
                utilisateur=request.user.username,
                commentaire=(
                    f"Négociation appliquée depuis l'interface commerçant "
                    f"(Article négocié ID {negociation.id}, motif: {negociation.motif})"
                )
            )

        messages.success(
            request,
            f"La négociation sur l'article {article.code} a été appliquée avec succès "
            f"({quantite} × {montant_unitaire} {negociation.devise} ajoutés au CA du jour)."
        )
    except Exception as e:
        messages.error(request, f"Erreur lors de l'application de la négociation : {e}")

    return redirect('inventory:commercant_articles_negocies_boutique', boutique_id=boutique.id)


@login_required
@commercant_required
@boutique_access_required
def appliquer_depense_rapport_caisse(request, boutique_id, rapport_id):
    boutique = request.boutique
    rapport = get_object_or_404(RapportCaisse, id=rapport_id, boutique=boutique)

    if request.method != 'POST':
        return HttpResponseForbidden("Méthode non autorisée")

    if not rapport.depense_appliquee:
        rapport.depense_appliquee = True
        rapport.date_application_depense = timezone.now()
        rapport.save(update_fields=['depense_appliquee', 'date_application_depense'])
        messages.success(
            request,
            f"La dépense de {rapport.depense} {rapport.devise} du {rapport.date_rapport.date()} a été appliquée à la recette du jour."
        )
    else:
        messages.info(request, "Cette dépense est déjà appliquée à la recette du jour.")

    return redirect('inventory:commercant_rapports_caisse_boutique', boutique_id=boutique.id)

@login_required
@commercant_required
@boutique_access_required
def exporter_ca_quotidien_pdf(request, boutique_id):
    """Exporter le chiffre d'affaires quotidien en PDF"""
    from django.http import HttpResponse
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from datetime import datetime, timedelta
    import io
    
    boutique = request.boutique
    
    # Créer le buffer pour le PDF
    buffer = io.BytesIO()
    
    # Créer le document PDF
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Titre
    title = Paragraph(f"Rapport CA Quotidien - {boutique.nom}", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 20))
    
    # Informations boutique
    info_text = f"""
    <b>Boutique:</b> {boutique.nom}<br/>
    <b>Type:</b> {boutique.get_type_commerce_display()}<br/>
    <b>Adresse:</b> {boutique.adresse}, {boutique.ville}<br/>
    <b>Date d'export:</b> {datetime.now().strftime('%d/%m/%Y à %H:%M')}<br/>
    """
    info = Paragraph(info_text, styles['Normal'])
    story.append(info)
    story.append(Spacer(1, 20))
    
    # Données des 30 derniers jours
    date_fin = timezone.now().date()
    date_debut = date_fin - timedelta(days=30)
    
    # Créer les données du tableau
    data = [['Date', 'Nb Ventes', 'Chiffre d\'Affaires (CDF)']]
    
    current_date = date_debut
    total_ca = 0
    total_ventes = 0
    
    while current_date <= date_fin:
        try:
            ventes_jour = Vente.objects.filter(
                boutique=boutique,
                date_vente__date=current_date,
                paye=True
            )
            nb_ventes = ventes_jour.count()
            ca_jour = ventes_jour.aggregate(total=Sum('montant_total'))['total'] or 0
        except (ValueError, TypeError):
            nb_ventes = 0
            ca_jour = 0
        
        data.append([
            current_date.strftime('%d/%m/%Y'),
            str(nb_ventes),
            f"{ca_jour:,.0f}"
        ])
        
        total_ventes += nb_ventes
        total_ca += ca_jour
        current_date += timedelta(days=1)
    
    # Ajouter ligne de total
    data.append(['TOTAL', str(total_ventes), f"{total_ca:,.0f}"])
    
    # Créer le tableau
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(table)
    
    # Construire le PDF
    doc.build(story)
    
    # Préparer la réponse
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="CA_quotidien_{boutique.nom}_{date_fin.strftime("%Y%m%d")}.pdf"'
    
    return response

@login_required
@commercant_required
@boutique_access_required
def exporter_ca_mensuel_pdf(request, boutique_id):
    """Exporter le chiffre d'affaires mensuel en PDF"""
    from django.http import HttpResponse
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from datetime import datetime
    from calendar import monthrange
    import io
    import locale
    
    boutique = request.boutique
    
    # Récupérer le mois et l'année depuis les paramètres GET (optionnel)
    try:
        annee = int(request.GET.get('annee', timezone.now().year))
        mois = int(request.GET.get('mois', timezone.now().month))
    except (ValueError, TypeError):
        annee = timezone.now().year
        mois = timezone.now().month
    
    # Créer le buffer pour le PDF
    buffer = io.BytesIO()
    
    # Créer le document PDF
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Noms des mois en français
    mois_noms = {
        1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril',
        5: 'Mai', 6: 'Juin', 7: 'Juillet', 8: 'Août',
        9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
    }
    nom_mois = mois_noms.get(mois, 'Mois')
    
    # Titre avec le nom du mois
    title = Paragraph(
        f"Rapport CA Mensuel - {nom_mois} {annee}<br/>{boutique.nom}", 
        styles['Title']
    )
    story.append(title)
    story.append(Spacer(1, 20))
    
    # Informations boutique
    info_text = f"""
    <b>Boutique:</b> {boutique.nom}<br/>
    <b>Type:</b> {boutique.get_type_commerce_display()}<br/>
    <b>Adresse:</b> {boutique.adresse}, {boutique.ville}<br/>
    <b>Période:</b> {nom_mois} {annee}<br/>
    <b>Date d'export:</b> {datetime.now().strftime('%d/%m/%Y à %H:%M')}<br/>
    """
    info = Paragraph(info_text, styles['Normal'])
    story.append(info)
    story.append(Spacer(1, 20))
    
    # Calculer le premier et dernier jour du mois
    premier_jour = datetime(annee, mois, 1).date()
    dernier_jour_num = monthrange(annee, mois)[1]
    dernier_jour = datetime(annee, mois, dernier_jour_num).date()
    
    # Créer les données du tableau
    data = [['Date', 'Nb Ventes', 'Chiffre d\'Affaires (CDF)']]
    
    current_date = premier_jour
    total_ca = 0
    total_ventes = 0
    
    # Parcourir tous les jours du mois
    while current_date <= dernier_jour:
        try:
            ventes_jour = Vente.objects.filter(
                boutique=boutique,
                date_vente__date=current_date,
                paye=True
            )
            nb_ventes = ventes_jour.count()
            ca_jour = ventes_jour.aggregate(total=Sum('montant_total'))['total'] or 0
        except (ValueError, TypeError):
            nb_ventes = 0
            ca_jour = 0
        
        data.append([
            current_date.strftime('%d/%m/%Y'),
            str(nb_ventes),
            f"{ca_jour:,.0f}"
        ])
        
        total_ventes += nb_ventes
        total_ca += ca_jour
        current_date += timedelta(days=1)
    
    # Ajouter ligne de total
    data.append(['TOTAL', str(total_ventes), f"{total_ca:,.0f}"])
    
    # Créer le tableau
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(table)
    
    # Construire le PDF
    doc.build(story)
    
    # Préparer la réponse
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="CA_Mensuel_{nom_mois}_{annee}_{boutique.nom}.pdf"'
    
    return response

@login_required
@commercant_required
@boutique_access_required
def ajouter_article_boutique(request, boutique_id):
    """Ajouter un article à une boutique spécifique (interface commerçant)"""
    from django.http import JsonResponse
    from inventory.models import Article, Categorie
    
    boutique = request.boutique
    
    if request.method == 'POST':
        # Vérifier si c'est une requête AJAX (ajout rapide)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                # Créer l'article avec les données minimales
                nom = request.POST.get('nom', '').strip()
                prix_vente = request.POST.get('prix_vente', '')
                quantite_stock = request.POST.get('quantite_stock', 0)
                categorie_id = request.POST.get('categorie', '')
                
                # Validations
                errors = {}
                if not nom:
                    errors['nom'] = ['Le nom est requis']
                if not prix_vente:
                    errors['prix_vente'] = ['Le prix de vente est requis']
                    
                # Si un code est fourni (cas évolutif), vérifier qu'il n'existe pas déjà
                code = request.POST.get('code', '').strip()
                if code and Article.objects.filter(code=code).exists():
                    errors['code'] = ['Ce code-barres existe déjà']
                
                if errors:
                    return JsonResponse({'success': False, 'errors': errors})
                
                # Générer un code-barres automatique si aucun n'est fourni
                if not code:
                    base_code = f"{boutique.id}-{uuid.uuid4().hex[:8].upper()}"
                    # S'assurer que le code est unique
                    while Article.objects.filter(code=base_code).exists():
                        base_code = f"{boutique.id}-{uuid.uuid4().hex[:8].upper()}"
                    code = base_code
                
                # Créer l'article
                stock_initial = int(quantite_stock) if quantite_stock else 0
                article = Article.objects.create(
                    boutique=boutique,
                    nom=nom,
                    code=code,
                    prix_vente=float(prix_vente),
                    prix_achat=0,  # Prix d'achat non calculé
                    quantite_stock=stock_initial,
                    est_actif=True
                )
                
                # ⭐ Créer un mouvement de stock pour le stock initial si > 0
                if stock_initial > 0:
                    MouvementStock.objects.create(
                        article=article,
                        type_mouvement='ENTREE',
                        quantite=stock_initial,
                        stock_avant=0,
                        stock_apres=stock_initial,
                        reference_document=f"INIT-{boutique.code_boutique}-{article.id}",
                        utilisateur=request.user.username,
                        commentaire=f"Stock initial à la création de l'article"
                    )
                
                # Ajouter la catégorie si fournie
                if categorie_id:
                    try:
                        categorie = Categorie.objects.get(id=categorie_id, boutique=boutique)
                        article.categorie = categorie
                        article.save()
                    except Categorie.DoesNotExist:
                        pass
                
                # Générer le code QR automatiquement
                try:
                    generer_qr_code_article(article)
                except Exception as e:
                    print(f"Erreur génération QR: {e}")
                
                return JsonResponse({
                    'success': True, 
                    'message': f'Article "{article.nom}" ajouté avec succès',
                    'article_id': article.id,
                    'article_nom': article.nom
                })
                
            except Exception as e:
                return JsonResponse({
                    'success': False, 
                    'message': f'Erreur lors de l\'ajout: {str(e)}'
                })
        
        # Si ce n'est pas AJAX, utiliser le formulaire normal
        form = ArticleForm(request.POST, request.FILES)
        if form.is_valid():
            article = form.save(commit=False)
            article.boutique = boutique
            stock_initial = article.quantite_stock
            article.save()
            
            # ⭐ Créer un mouvement de stock pour le stock initial si > 0
            if stock_initial > 0:
                MouvementStock.objects.create(
                    article=article,
                    type_mouvement='ENTREE',
                    quantite=stock_initial,
                    stock_avant=0,
                    stock_apres=stock_initial,
                    reference_document=f"INIT-{boutique.code_boutique}-{article.id}",
                    utilisateur=request.user.username,
                    commentaire=f"Stock initial à la création de l'article"
                )
            
            # Générer le code QR automatiquement
            try:
                generer_qr_code_article(article)
                messages.success(request, f'Article "{article.nom}" ajouté avec succès à {boutique.nom}. Code QR généré automatiquement.')
            except Exception as e:
                messages.warning(request, f'Article "{article.nom}" ajouté, mais erreur lors de la génération du code QR: {str(e)}')
            
            return redirect('inventory:entrer_boutique', boutique_id=boutique.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Erreur dans {field}: {error}")
    else:
        form = ArticleForm()
    
    # Récupérer les catégories de la boutique
    categories = boutique.categories.all()
    
    context = {
        'form': form,
        'boutique': boutique,
        'categories': categories
    }
    
    return render(request, 'inventory/commercant/ajouter_article.html', context)

@login_required
@commercant_required
@boutique_access_required
def modifier_article_boutique(request, boutique_id, article_id):
    """Modifier un article d'une boutique spécifique"""
    boutique = request.boutique
    
    try:
        article = Article.objects.get(id=article_id, boutique=boutique)
    except Article.DoesNotExist:
        messages.error(request, "Article introuvable.")
        return redirect('inventory:commercant_articles_boutique', boutique_id=boutique.id)
    
    if request.method == 'POST':
        # Conserver le code-barres existant (on ne souhaite plus le modifier via ce formulaire)
        ancien_code = article.code
        form = ArticleForm(request.POST, request.FILES, instance=article)
        if form.is_valid():
            article = form.save(commit=False)
            article.boutique = boutique
            # Réappliquer le code d'origine pour éviter de le vider ou de le dupliquer
            article.code = ancien_code
            article.save()
            
            # Régénérer le code QR si le code a changé
            try:
                generer_qr_code_article(article)
                messages.success(request, f'Article "{article.nom}" modifié avec succès.')
            except Exception as e:
                messages.warning(request, f'Article modifié, mais erreur lors de la génération du code QR: {str(e)}')
            
            return redirect('inventory:commercant_articles_boutique', boutique_id=boutique.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Erreur dans {field}: {error}")
    else:
        form = ArticleForm(instance=article)
    
    # Récupérer les catégories de la boutique
    categories = boutique.categories.all()
    
    context = {
        'form': form,
        'boutique': boutique,
        'categories': categories,
        'article': article,
        'mode_edition': True
    }
    
    return render(request, 'inventory/commercant/modifier_article.html', context)

@login_required
@commercant_required
@boutique_access_required
def supprimer_article_boutique(request, boutique_id, article_id):
    """Supprimer un article d'une boutique spécifique (interface commerçant)"""
    boutique = request.boutique
    
    try:
        article = Article.objects.get(id=article_id, boutique=boutique)
    except Article.DoesNotExist:
        messages.error(request, "Article introuvable.")
        return redirect('inventory:commercant_articles_boutique', boutique_id=boutique.id)
    
    if request.method == 'POST':
        nom_article = article.nom
        try:
            article.delete()
            messages.success(request, f"Article '{nom_article}' supprimé avec succès!")
        except Exception as e:
            messages.error(request, f"Impossible de supprimer l'article : {str(e)}")
    
    return redirect('inventory:commercant_articles_boutique', boutique_id=boutique.id)

@login_required
@commercant_required
@boutique_access_required
def ajuster_stock_article(request, boutique_id, article_id):
    """Ajuster rapidement le stock d'un article avec traçabilité complète"""
    from django.http import JsonResponse
    
    boutique = request.boutique
    
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            article = Article.objects.get(id=article_id, boutique=boutique)
            
            type_ajustement = request.POST.get('type_ajustement')
            quantite = int(request.POST.get('quantite', 0))
            commentaire = request.POST.get('commentaire', '')
            
            # Capturer le stock avant modification
            stock_avant = article.quantite_stock
            
            # Calculer la différence et le type de mouvement
            if type_ajustement == 'ajouter':
                article.quantite_stock += quantite
                type_mouvement = 'ENTREE'
                quantite_mouvement = quantite
            elif type_ajustement == 'retirer':
                article.quantite_stock = max(0, article.quantite_stock - quantite)
                type_mouvement = 'SORTIE'
                quantite_mouvement = -(stock_avant - article.quantite_stock)  # Négatif pour sortie
            elif type_ajustement == 'definir':
                article.quantite_stock = quantite
                difference = quantite - stock_avant
                type_mouvement = 'AJUSTEMENT'
                quantite_mouvement = difference
            else:
                return JsonResponse({'success': False, 'message': 'Type d\'ajustement invalide'})
            
            article.save(update_fields=['quantite_stock'])
            
            # ⭐ Créer le mouvement de stock pour traçabilité
            MouvementStock.objects.create(
                article=article,
                type_mouvement=type_mouvement,
                quantite=quantite_mouvement,
                stock_avant=stock_avant,
                stock_apres=article.quantite_stock,
                reference_document=f"AJUST-{boutique.code_boutique}-{article.id}",
                utilisateur=request.user.username,
                commentaire=commentaire or f"Ajustement {type_ajustement}: {stock_avant} → {article.quantite_stock}"
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Stock ajusté: {stock_avant} → {article.quantite_stock}',
                'ancien_stock': stock_avant,
                'nouveau_stock': article.quantite_stock
            })
            
        except Article.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Article introuvable'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Méthode non autorisée'})

@login_required
@commercant_required
@boutique_access_required
def modifier_prix_article(request, boutique_id, article_id):
    """Modifier rapidement le prix d'un article"""
    from django.http import JsonResponse
    
    boutique = request.boutique
    
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            article = Article.objects.get(id=article_id, boutique=boutique)
            
            nouveau_prix = float(request.POST.get('prix_vente', 0))
            commentaire = request.POST.get('commentaire', '')
            
            if nouveau_prix < 0:
                return JsonResponse({'success': False, 'message': 'Le prix ne peut pas être négatif'})
            
            ancien_prix = article.prix_vente
            article.prix_vente = nouveau_prix
            article.save()
            
            # Régénérer le QR code avec le nouveau prix
            try:
                generer_qr_code_article(article)
            except Exception:
                pass  # Ne pas bloquer si le QR code échoue
            
            return JsonResponse({
                'success': True,
                'message': f'Prix modifié: {ancien_prix} → {nouveau_prix} CDF',
                'ancien_prix': float(ancien_prix),
                'nouveau_prix': float(nouveau_prix)
            })
            
        except Article.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Article introuvable'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Méthode non autorisée'})

@login_required
@commercant_required
@boutique_access_required
def generer_pdf_qr_codes(request, boutique_id):
    """Générer un PDF avec tous les codes QR des articles d'une boutique"""
    from django.http import HttpResponse
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as ReportLabImage
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    import os
    
    boutique = request.boutique
    
    # Récupérer tous les articles actifs de la boutique avec QR code
    articles = boutique.articles.filter(est_actif=True, qr_code__isnull=False).exclude(qr_code='')
    
    if not articles.exists():
        messages.warning(request, "Aucun article avec code QR trouvé dans cette boutique.")
        return redirect('inventory:entrer_boutique', boutique_id=boutique.id)
    
    # Créer le buffer pour le PDF
    buffer = io.BytesIO()
    
    # Créer le document PDF
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []
    
    # Titre
    title = Paragraph(f"Codes QR - {boutique.nom}", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 20))
    
    # Informations boutique
    info_text = f"""
    <b>Boutique:</b> {boutique.nom}<br/>
    <b>Type:</b> {boutique.get_type_commerce_display()}<br/>
    <b>Adresse:</b> {boutique.adresse}, {boutique.ville}<br/>
    <b>Date de génération:</b> {datetime.now().strftime('%d/%m/%Y à %H:%M')}<br/>
    <b>Nombre d'articles:</b> {articles.count()}<br/>
    """
    info = Paragraph(info_text, styles['Normal'])
    story.append(info)
    story.append(Spacer(1, 30))
    
    # Créer une grille de QR codes (3 colonnes)
    qr_data = []
    current_row = []
    
    for i, article in enumerate(articles):
        try:
            # Vérifier que le fichier QR code existe
            if article.qr_code and os.path.exists(article.qr_code.path):
                # Créer une cellule avec QR code + informations
                cell_content = [
                    ReportLabImage(article.qr_code.path, width=4*cm, height=4*cm),
                    Paragraph(f"<b>{article.nom}</b>", styles['Normal']),
                    Paragraph(f"Code: {article.code}", styles['Normal']),
                    Paragraph(f"Prix: {article.prix_vente} CDF", styles['Normal'])
                ]
                current_row.append(cell_content)
            else:
                # Si pas de QR code, générer un nouveau
                if generer_qr_code_article(article):
                    cell_content = [
                        ReportLabImage(article.qr_code.path, width=4*cm, height=4*cm),
                        Paragraph(f"<b>{article.nom}</b>", styles['Normal']),
                        Paragraph(f"Code: {article.code}", styles['Normal']),
                        Paragraph(f"Prix: {article.prix_vente} CDF", styles['Normal'])
                    ]
                    current_row.append(cell_content)
                else:
                    # QR code manquant
                    cell_content = [
                        Paragraph("QR Code<br/>non disponible", styles['Normal']),
                        Paragraph(f"<b>{article.nom}</b>", styles['Normal']),
                        Paragraph(f"Code: {article.code}", styles['Normal']),
                        Paragraph(f"Prix: {article.prix_vente} CDF", styles['Normal'])
                    ]
                    current_row.append(cell_content)
            
            # Ajouter la ligne quand on a 3 colonnes ou à la fin
            if len(current_row) == 3 or i == len(articles) - 1:
                # Compléter la ligne si nécessaire
                while len(current_row) < 3:
                    empty_cell = [
                        Paragraph("", styles['Normal']),
                        Paragraph("", styles['Normal']),
                        Paragraph("", styles['Normal']),
                        Paragraph("", styles['Normal'])
                    ]
                    current_row.append(empty_cell)
                qr_data.append(current_row)
                current_row = []
                
        except Exception as e:
            print(f"Erreur avec l'article {article.id}: {str(e)}")
            continue
    
    # Créer le tableau avec les QR codes
    if qr_data:
        table = Table(qr_data, colWidths=[6*cm, 6*cm, 6*cm])
        table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(table)
    
    # Construire le PDF
    doc.build(story)
    
    # Préparer la réponse
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="QR_Codes_{boutique.nom}_{datetime.now().strftime("%Y%m%d")}.pdf"'
    
    return response

@login_required
@commercant_required
@boutique_access_required
def modifier_terminal(request, boutique_id, terminal_id):
    """Modifier un terminal MAUI"""
    boutique = request.boutique
    terminal = get_object_or_404(Client, id=terminal_id, boutique=boutique)
    
    if request.method == 'POST':
        terminal.nom_terminal = request.POST.get('nom_terminal', terminal.nom_terminal)
        terminal.description = request.POST.get('description', '')
        terminal.notes = request.POST.get('notes', '')
        terminal.save()
        
        messages.success(request, f"Terminal '{terminal.nom_terminal}' modifié avec succès!")
        return redirect('inventory:commercant_terminaux_boutique', boutique_id=boutique.id)
    
    context = {
        'boutique': boutique,
        'terminal': terminal
    }
    
    return render(request, 'inventory/commercant/modifier_terminal.html', context)

@login_required
@commercant_required
@boutique_access_required
def toggle_terminal(request, boutique_id, terminal_id):
    """Activer/Désactiver un terminal MAUI"""
    boutique = request.boutique
    terminal = get_object_or_404(Client, id=terminal_id, boutique=boutique)
    
    terminal.est_actif = not terminal.est_actif
    terminal.save()
    
    statut = "activé" if terminal.est_actif else "désactivé"
    messages.success(request, f"Terminal '{terminal.nom_terminal}' {statut} avec succès!")
    
    return redirect('inventory:commercant_terminaux_boutique', boutique_id=boutique.id)

@login_required
@commercant_required
@boutique_access_required
def supprimer_terminal(request, boutique_id, terminal_id):
    """Supprimer un terminal MAUI"""
    boutique = request.boutique
    terminal = get_object_or_404(Client, id=terminal_id, boutique=boutique)
    
    if request.method == 'POST':
        nom_terminal = terminal.nom_terminal
        terminal.delete()
        messages.success(request, f"Terminal '{nom_terminal}' supprimé avec succès!")
        return redirect('inventory:commercant_terminaux_boutique', boutique_id=boutique.id)
    
    context = {
        'boutique': boutique,
        'terminal': terminal
    }
    
    return render(request, 'inventory/commercant/supprimer_terminal.html', context)

@login_required
@commercant_required
@boutique_access_required
def ventes_boutique(request, boutique_id):
    """Afficher les ventes d'une boutique spécifique"""
    boutique = request.boutique
    
    # ⭐ ISOLATION: Récupérer UNIQUEMENT les ventes de CETTE boutique
    ventes = Vente.objects.filter(
        boutique=boutique  # Filtrage direct par boutique
    ).select_related('client_maui', 'boutique').prefetch_related('lignes__article').order_by('-date_vente')
    terminaux = boutique.clients.all().order_by('nom_terminal')
    
    # Filtres optionnels
    periode = request.GET.get('periode') or 'CUSTOM'
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    terminal_id = request.GET.get('terminal_id')

    # Calculer les dates selon la période sélectionnée
    today = timezone.now().date()
    if periode == 'TODAY':
        date_debut = today.isoformat()
        date_fin = today.isoformat()
    elif periode == 'YESTERDAY':
        jour = today - timedelta(days=1)
        date_debut = jour.isoformat()
        date_fin = jour.isoformat()
    elif periode == 'THIS_MONTH':
        premier_jour = today.replace(day=1)
        date_debut = premier_jour.isoformat()
        date_fin = today.isoformat()

    # Appliquer les filtres de dates
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

    # Filtre par terminal (client MAUI)
    if terminal_id:
        if terminal_id != 'TOUS':
            try:
                terminal_id_int = int(terminal_id)
                ventes = ventes.filter(client_maui_id=terminal_id_int)
                terminal_selected = terminal_id_int
            except (TypeError, ValueError):
                terminal_selected = 'TOUS'
        else:
            terminal_selected = 'TOUS'
    else:
        terminal_selected = 'TOUS'
    
    # Statistiques
    from django.db.models import Sum, Count
    stats = ventes.aggregate(
        total_ventes=Count('id'),
        chiffre_affaires=Sum('montant_total')
    )
    
    # Regrouper les ventes par période
    from collections import OrderedDict
    maintenant = datetime.now()
    aujourd_hui = maintenant.date()
    
    ventes_groupees = OrderedDict()
    periodes_ordre = [
        "Aujourd'hui",
        "Hier",
        "Cette semaine",
        "Ce mois",
        "Mois précédent"
    ]
    
    for vente in ventes:
        # Déterminer la période
        date_vente = vente.date_vente.date()
        
        if date_vente == aujourd_hui:
            periode = "Aujourd'hui"
        elif date_vente == aujourd_hui - timedelta(days=1):
            periode = "Hier"
        elif date_vente > aujourd_hui - timedelta(days=7):
            periode = "Cette semaine"
        elif vente.date_vente.year == aujourd_hui.year and vente.date_vente.month == aujourd_hui.month:
            periode = "Ce mois"
        else:
            mois_precedent = aujourd_hui.replace(day=1) - timedelta(days=1)
            if vente.date_vente.year == mois_precedent.year and vente.date_vente.month == mois_precedent.month:
                periode = "Mois précédent"
            else:
                mois_fr = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 
                          'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
                periode = f"{mois_fr[vente.date_vente.month - 1]} {vente.date_vente.year}"
        
        if periode not in ventes_groupees:
            ventes_groupees[periode] = []
        ventes_groupees[periode].append(vente)
    
    # Trier les périodes dans l'ordre souhaité
    ventes_groupees_triees = OrderedDict()
    for periode in periodes_ordre:
        if periode in ventes_groupees:
            ventes_groupees_triees[periode] = ventes_groupees[periode]
    # Ajouter les autres périodes (mois passés)
    for periode, ventes_list in ventes_groupees.items():
        if periode not in ventes_groupees_triees:
            ventes_groupees_triees[periode] = ventes_list
    
    context = {
        'boutique': boutique,
        'ventes': ventes,
        'ventes_groupees': ventes_groupees_triees,
        'total_ventes': stats['total_ventes'] or 0,
        'chiffre_affaires': stats['chiffre_affaires'] or 0,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'terminaux': terminaux,
        'terminal_selected': terminal_selected,
        'periode_selected': periode,
    }
    
    return render(request, 'inventory/commercant/ventes_boutique.html', context)


# ===== VENTES REFUSÉES =====

@login_required
@commercant_required
@boutique_access_required
def ventes_refusees_boutique(request, boutique_id):
    """Affiche les ventes refusées de la boutique avec statistiques"""
    boutique = request.boutique
    aujourd_hui = timezone.now().date()
    
    # Récupérer les ventes refusées de la boutique
    ventes_refusees = VenteRejetee.objects.filter(
        boutique=boutique
    ).select_related('terminal').order_by('-date_tentative')
    
    # Filtrer par date si demandé
    date_filter = request.GET.get('date', '')
    if date_filter:
        try:
            date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
            ventes_refusees = ventes_refusees.filter(date_tentative__date=date_obj)
        except ValueError:
            pass
    
    # Ventes refusées du jour
    ventes_refusees_jour = VenteRejetee.objects.filter(
        boutique=boutique,
        date_tentative__date=aujourd_hui
    )
    
    # Calculer la somme des articles refusés du jour (extraire du JSON)
    total_refusees_jour = Decimal('0')
    for vente in ventes_refusees_jour:
        try:
            donnees = vente.donnees_vente
            if isinstance(donnees, dict):
                montant = donnees.get('montant_total', 0)
                total_refusees_jour += Decimal(str(montant))
        except (TypeError, ValueError, KeyError):
            pass
    
    # Recette normale du jour (ventes payées)
    recette_jour = Vente.objects.filter(
        client_maui__boutique=boutique,
        date_vente__date=aujourd_hui,
        paye=True
    ).aggregate(total=Sum('montant_total'))['total'] or Decimal('0')
    
    # Total combiné (recette + ventes refusées)
    total_combine = recette_jour + total_refusees_jour
    
    # Statistiques par raison de rejet
    stats_par_raison = ventes_refusees.values('raison_rejet').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Mapping des raisons pour l'affichage
    raisons_display = dict(VenteRejetee.RAISONS_REJET)
    for stat in stats_par_raison:
        stat['raison_display'] = raisons_display.get(stat['raison_rejet'], stat['raison_rejet'])
    
    # Préparer les données détaillées des ventes refusées
    ventes_details = []
    for vente in ventes_refusees[:50]:  # Limiter à 50 pour la performance
        try:
            donnees = vente.donnees_vente
            montant = Decimal('0')
            articles_info = []
            
            if isinstance(donnees, dict):
                montant = Decimal(str(donnees.get('montant_total', 0)))
                lignes = donnees.get('lignes', donnees.get('articles', []))
                for ligne in lignes:
                    if isinstance(ligne, dict):
                        articles_info.append({
                            'nom': ligne.get('nom', ligne.get('article_nom', 'N/A')),
                            'quantite': ligne.get('quantite', 1),
                            'prix': ligne.get('prix_unitaire', ligne.get('prix', 0))
                        })
            
            ventes_details.append({
                'vente': vente,
                'montant': montant,
                'articles': articles_info,
                'raison_display': raisons_display.get(vente.raison_rejet, vente.raison_rejet)
            })
        except (TypeError, ValueError, KeyError):
            ventes_details.append({
                'vente': vente,
                'montant': Decimal('0'),
                'articles': [],
                'raison_display': raisons_display.get(vente.raison_rejet, vente.raison_rejet)
            })
    
    context = {
        'boutique': boutique,
        'ventes_refusees': ventes_refusees,
        'ventes_details': ventes_details,
        'total_refusees_jour': total_refusees_jour,
        'recette_jour': recette_jour,
        'total_combine': total_combine,
        'nb_refusees_jour': ventes_refusees_jour.count(),
        'nb_refusees_total': ventes_refusees.count(),
        'stats_par_raison': stats_par_raison,
        'date_filter': date_filter,
        'aujourd_hui': aujourd_hui.strftime('%Y-%m-%d'),
    }
    
    return render(request, 'inventory/commercant/ventes_refusees_boutique.html', context)

@login_required
@commercant_required
def api_vente_details(request, vente_id):
    """API pour récupérer les détails d'une vente avec ses articles"""
    try:
        vente = get_object_or_404(Vente, id=vente_id)
        
        # Vérifier que le commerçant a accès à cette vente
        commercant = request.user.profil_commercant
        if vente.boutique.commercant != commercant:
            return JsonResponse({'error': 'Accès non autorisé'}, status=403)
        
        # Récupérer les lignes de vente avec les articles
        lignes = vente.lignes.select_related('article').all()
        
        # Construire les lignes avec gestion des articles supprimés
        lignes_data = []
        for ligne in lignes:
            try:
                lignes_data.append({
                    'article_nom': ligne.article.nom if ligne.article else 'Article supprimé',
                    'article_code': getattr(ligne.article, 'code', '') or '-' if ligne.article else '-',
                    'quantite': ligne.quantite,
                    'prix_unitaire': f"{ligne.prix_unitaire:,.0f}",
                    'total_ligne': f"{ligne.total_ligne:,.0f}"
                })
            except Exception:
                lignes_data.append({
                    'article_nom': 'Article inconnu',
                    'article_code': '-',
                    'quantite': ligne.quantite,
                    'prix_unitaire': f"{ligne.prix_unitaire:,.0f}",
                    'total_ligne': f"{ligne.total_ligne:,.0f}"
                })
        
        # Construire la réponse JSON
        data = {
            'id': vente.id,
            'numero_facture': vente.numero_facture,
            'date_vente': vente.date_vente.strftime('%d/%m/%Y %H:%M'),
            'mode_paiement': vente.get_mode_paiement_display(),
            'terminal': vente.client_maui.nom_terminal if vente.client_maui else None,
            'montant_total': f"{vente.montant_total:,.0f}",
            'lignes': lignes_data
        }
        
        return JsonResponse(data)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# ===== GESTION DU DÉPÔT CENTRAL =====

@login_required
@commercant_required
def liste_depots(request):
    """Liste des dépôts du commerçant"""
    commercant = request.user.profil_commercant
    depots = commercant.boutiques.filter(est_depot=True)
    
    # Statistiques pour chaque dépôt
    for depot in depots:
        depot.nb_articles = depot.articles.filter(est_actif=True).count()
        depot.valeur_stock = depot.articles.filter(est_actif=True).aggregate(
            total=Sum(F('quantite_stock') * F('prix_achat'))
        )['total'] or 0
        depot.nb_transferts_mois = TransfertStock.objects.filter(
            depot_source=depot,
            date_transfert__gte=timezone.now().replace(day=1)
        ).count()
    
    context = {
        'commercant': commercant,
        'depots': depots,
    }
    
    return render(request, 'inventory/commercant/liste_depots.html', context)

@login_required
@commercant_required
def detail_depot(request, depot_id):
    """Détail d'un dépôt avec ses articles et statistiques"""
    commercant = request.user.profil_commercant
    depot = get_object_or_404(Boutique, id=depot_id, commercant=commercant, est_depot=True)
    
    # Articles du dépôt
    articles = depot.articles.filter(est_actif=True).select_related('categorie').order_by('nom')
    
    # Statistiques
    total_articles = articles.count()
    valeur_stock = articles.aggregate(total=Sum(F('quantite_stock') * F('prix_achat')))['total'] or 0
    articles_stock_bas = articles.filter(quantite_stock__lte=depot.alerte_stock_bas).count()
    
    # Transferts récents
    transferts_recents = TransfertStock.objects.filter(
        depot_source=depot
    ).select_related('article', 'boutique_destination').order_by('-date_transfert')[:20]
    
    # Boutiques de destination disponibles (non-dépôts)
    boutiques_destination = commercant.boutiques.filter(est_depot=False, est_active=True)
    
    context = {
        'depot': depot,
        'articles': articles,
        'total_articles': total_articles,
        'valeur_stock': valeur_stock,
        'articles_stock_bas': articles_stock_bas,
        'transferts_recents': transferts_recents,
        'boutiques_destination': boutiques_destination,
    }
    
    return render(request, 'inventory/commercant/detail_depot.html', context)

@login_required
@commercant_required
def creer_transfert_stock(request, depot_id):
    """Créer un transfert de stock du dépôt vers une boutique"""
    commercant = request.user.profil_commercant
    depot = get_object_or_404(Boutique, id=depot_id, commercant=commercant, est_depot=True)
    
    if request.method == 'POST':
        try:
            article_id = request.POST.get('article_id')
            boutique_dest_id = request.POST.get('boutique_destination')
            quantite = int(request.POST.get('quantite', 0))
            commentaire = request.POST.get('commentaire', '')
            
            article = get_object_or_404(Article, id=article_id, boutique=depot)
            boutique_dest = get_object_or_404(Boutique, id=boutique_dest_id, commercant=commercant, est_depot=False)
            
            if quantite <= 0:
                messages.error(request, "La quantité doit être supérieure à 0")
                return redirect('inventory:detail_depot', depot_id=depot.id)
            
            if article.quantite_stock < quantite:
                messages.error(request, f"Stock insuffisant. Disponible: {article.quantite_stock}")
                return redirect('inventory:detail_depot', depot_id=depot.id)
            
            # Créer le transfert
            transfert = TransfertStock.objects.create(
                article=article,
                depot_source=depot,
                boutique_destination=boutique_dest,
                quantite=quantite,
                effectue_par=request.user.username,
                commentaire=commentaire,
                statut='EN_ATTENTE'
            )
            
            messages.success(request, f"Transfert créé: {quantite} x {article.nom} vers {boutique_dest.nom}")
            return redirect('inventory:detail_transfert', transfert_id=transfert.id)
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la création du transfert: {str(e)}")
            return redirect('inventory:detail_depot', depot_id=depot.id)
    
    return redirect('inventory:detail_depot', depot_id=depot.id)

@login_required
@commercant_required
def detail_transfert(request, transfert_id):
    """Détail d'un transfert de stock"""
    commercant = request.user.profil_commercant
    transfert = get_object_or_404(TransfertStock, id=transfert_id)
    
    # Vérifier l'accès
    if transfert.depot_source.commercant != commercant:
        messages.error(request, "Accès non autorisé")
        return redirect('inventory:commercant_dashboard')
    
    context = {
        'transfert': transfert,
    }
    
    return render(request, 'inventory/commercant/detail_transfert.html', context)

@login_required
@commercant_required
def valider_transfert(request, transfert_id):
    """Valider un transfert de stock"""
    commercant = request.user.profil_commercant
    transfert = get_object_or_404(TransfertStock, id=transfert_id)
    
    # Vérifier l'accès
    if transfert.depot_source.commercant != commercant:
        messages.error(request, "Accès non autorisé")
        return redirect('inventory:commercant_dashboard')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                transfert.valider_transfert(request.user.username)
            
            messages.success(request, f"Transfert validé avec succès! {transfert.quantite} x {transfert.article.nom} transféré vers {transfert.boutique_destination.nom}")
            return redirect('inventory:detail_depot', depot_id=transfert.depot_source.id)
            
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"Erreur lors de la validation: {str(e)}")
    
    return redirect('inventory:detail_transfert', transfert_id=transfert.id)

@login_required
@commercant_required
def annuler_transfert(request, transfert_id):
    """Annuler un transfert de stock en attente"""
    commercant = request.user.profil_commercant
    transfert = get_object_or_404(TransfertStock, id=transfert_id)
    
    # Vérifier l'accès
    if transfert.depot_source.commercant != commercant:
        messages.error(request, "Accès non autorisé")
        return redirect('inventory:commercant_dashboard')
    
    if request.method == 'POST':
        if transfert.statut == 'EN_ATTENTE':
            transfert.statut = 'ANNULE'
            transfert.save()
            messages.success(request, "Transfert annulé")
        else:
            messages.error(request, "Ce transfert ne peut plus être annulé")
    
    return redirect('inventory:detail_depot', depot_id=transfert.depot_source.id)

@login_required
@commercant_required
def approvisionner_depot(request, depot_id):
    """Approvisionner le dépôt avec de nouveaux articles ou ajouter du stock"""
    commercant = request.user.profil_commercant
    depot = get_object_or_404(Boutique, id=depot_id, commercant=commercant, est_depot=True)
    
    if request.method == 'POST':
        type_appro = request.POST.get('type_appro', 'nouveau')
        
        try:
            if type_appro == 'nouveau':
                # Créer un nouvel article
                code = request.POST.get('code', '').strip()
                nom = request.POST.get('nom', '').strip()
                prix_achat = Decimal(request.POST.get('prix_achat', '0'))
                prix_vente = Decimal(request.POST.get('prix_vente', '0'))
                quantite = int(request.POST.get('quantite_initiale', '1'))
                description = request.POST.get('description', '')
                
                if not code or not nom:
                    messages.error(request, "Le code et le nom de l'article sont obligatoires")
                    return redirect('inventory:detail_depot', depot_id=depot.id)
                
                # Vérifier si l'article existe déjà dans ce dépôt
                if Article.objects.filter(code=code, boutique=depot).exists():
                    messages.error(request, f"Un article avec le code '{code}' existe déjà dans ce dépôt")
                    return redirect('inventory:detail_depot', depot_id=depot.id)
                
                # Créer l'article
                article = Article.objects.create(
                    code=code,
                    nom=nom,
                    description=description,
                    prix_achat=prix_achat,
                    prix_vente=prix_vente,
                    quantite_stock=quantite,
                    boutique=depot,
                    est_actif=True
                )
                
                # Enregistrer le mouvement de stock
                MouvementStock.objects.create(
                    article=article,
                    type_mouvement='ENTREE',
                    quantite=quantite,
                    stock_avant=0,
                    stock_apres=quantite,
                    commentaire=f"Approvisionnement initial du dépôt",
                    reference_document=f"APPRO-{depot.id}-{article.id}",
                    utilisateur=request.user.username
                )
                
                messages.success(request, f"Article '{nom}' créé avec {quantite} unités en stock")
                
            else:
                # Ajouter du stock à un article existant
                article_id = request.POST.get('article_existant')
                quantite_ajout = int(request.POST.get('quantite_ajout', '1'))
                
                if not article_id:
                    messages.error(request, "Veuillez sélectionner un article")
                    return redirect('inventory:detail_depot', depot_id=depot.id)
                
                article = get_object_or_404(Article, id=article_id, boutique=depot)
                stock_avant = article.quantite_stock
                article.quantite_stock += quantite_ajout
                article.save()
                
                # Enregistrer le mouvement de stock
                MouvementStock.objects.create(
                    article=article,
                    type_mouvement='ENTREE',
                    quantite=quantite_ajout,
                    stock_avant=stock_avant,
                    stock_apres=article.quantite_stock,
                    commentaire=f"Approvisionnement du dépôt",
                    reference_document=f"APPRO-{depot.id}-{article.id}",
                    utilisateur=request.user.username
                )
                
                messages.success(request, f"{quantite_ajout} unités ajoutées à '{article.nom}' (nouveau stock: {article.quantite_stock})")
                
        except Exception as e:
            messages.error(request, f"Erreur lors de l'approvisionnement: {str(e)}")
    
    return redirect('inventory:detail_depot', depot_id=depot.id)

@login_required
@commercant_required
def historique_transferts(request, depot_id):
    """Historique des transferts d'un dépôt"""
    commercant = request.user.profil_commercant
    depot = get_object_or_404(Boutique, id=depot_id, commercant=commercant, est_depot=True)
    
    # Filtres
    statut = request.GET.get('statut', '')
    boutique_dest = request.GET.get('boutique', '')
    
    transferts = TransfertStock.objects.filter(depot_source=depot).select_related(
        'article', 'boutique_destination'
    ).order_by('-date_transfert')
    
    if statut:
        transferts = transferts.filter(statut=statut)
    if boutique_dest:
        transferts = transferts.filter(boutique_destination_id=boutique_dest)
    
    # Statistiques
    stats = {
        'total': transferts.count(),
        'en_attente': transferts.filter(statut='EN_ATTENTE').count(),
        'valides': transferts.filter(statut='VALIDE').count(),
        'annules': transferts.filter(statut='ANNULE').count(),
    }
    
    boutiques = commercant.boutiques.filter(est_depot=False, est_active=True)
    
    context = {
        'depot': depot,
        'transferts': transferts[:100],
        'stats': stats,
        'boutiques': boutiques,
        'statut_filter': statut,
        'boutique_filter': boutique_dest,
    }
    
    return render(request, 'inventory/commercant/historique_transferts.html', context)


# ===== TRANSFERT MULTIPLE =====

@login_required
@commercant_required
def transfert_multiple(request, depot_id):
    """Page de transfert multiple d'articles du dépôt vers une boutique"""
    commercant = request.user.profil_commercant
    depot = get_object_or_404(Boutique, id=depot_id, commercant=commercant, est_depot=True)
    
    # Articles disponibles dans le dépôt (avec stock > 0)
    articles = depot.articles.filter(
        est_actif=True,
        quantite_stock__gt=0
    ).select_related('categorie').order_by('nom')
    
    # Boutiques de destination
    boutiques_destination = commercant.boutiques.filter(est_depot=False, est_active=True)
    
    if request.method == 'POST':
        boutique_dest_id = request.POST.get('boutique_destination')
        commentaire_global = request.POST.get('commentaire', '')
        
        if not boutique_dest_id:
            messages.error(request, "Veuillez sélectionner une boutique de destination")
            return redirect('inventory:transfert_multiple', depot_id=depot.id)
        
        boutique_dest = get_object_or_404(Boutique, id=boutique_dest_id, commercant=commercant, est_depot=False)
        
        # Récupérer les articles sélectionnés avec leurs quantités
        articles_selectionnes = request.POST.getlist('articles_selectionnes')
        
        if not articles_selectionnes:
            messages.error(request, "Veuillez sélectionner au moins un article à transférer")
            return redirect('inventory:transfert_multiple', depot_id=depot.id)
        
        transferts_crees = []
        erreurs = []
        
        try:
            with transaction.atomic():
                for article_id in articles_selectionnes:
                    quantite_key = f'quantite_{article_id}'
                    quantite = int(request.POST.get(quantite_key, 0))
                    
                    if quantite <= 0:
                        continue
                    
                    try:
                        article = Article.objects.get(id=article_id, boutique=depot)
                        
                        if article.quantite_stock < quantite:
                            erreurs.append(f"{article.nom}: stock insuffisant (dispo: {article.quantite_stock}, demandé: {quantite})")
                            continue
                        
                        # Créer le transfert
                        transfert = TransfertStock.objects.create(
                            article=article,
                            depot_source=depot,
                            boutique_destination=boutique_dest,
                            quantite=quantite,
                            effectue_par=request.user.username,
                            commentaire=commentaire_global,
                            statut='EN_ATTENTE'
                        )
                        transferts_crees.append(transfert)
                        
                    except Article.DoesNotExist:
                        erreurs.append(f"Article ID {article_id} introuvable")
                
                if not transferts_crees and erreurs:
                    raise Exception("Aucun transfert créé")
        
        except Exception as e:
            for erreur in erreurs:
                messages.error(request, erreur)
            return redirect('inventory:transfert_multiple', depot_id=depot.id)
        
        # Messages de résultat
        if transferts_crees:
            messages.success(request, f"{len(transferts_crees)} transfert(s) créé(s) vers {boutique_dest.nom}")
        
        for erreur in erreurs:
            messages.warning(request, erreur)
        
        return redirect('inventory:detail_depot', depot_id=depot.id)
    
    context = {
        'depot': depot,
        'articles': articles,
        'boutiques_destination': boutiques_destination,
    }
    
    return render(request, 'inventory/commercant/transfert_multiple.html', context)


@login_required
@commercant_required
def valider_transferts_multiples(request, depot_id):
    """Valider plusieurs transferts en attente en une seule fois"""
    commercant = request.user.profil_commercant
    depot = get_object_or_404(Boutique, id=depot_id, commercant=commercant, est_depot=True)
    
    if request.method == 'POST':
        transferts_ids = request.POST.getlist('transferts_selectionnes')
        
        if not transferts_ids:
            messages.error(request, "Veuillez sélectionner au moins un transfert à valider")
            return redirect('inventory:historique_transferts', depot_id=depot.id)
        
        valides = 0
        erreurs = []
        
        for transfert_id in transferts_ids:
            try:
                transfert = TransfertStock.objects.get(id=transfert_id, depot_source=depot, statut='EN_ATTENTE')
                with transaction.atomic():
                    transfert.valider_transfert(request.user.username)
                valides += 1
            except TransfertStock.DoesNotExist:
                erreurs.append(f"Transfert {transfert_id} introuvable ou déjà traité")
            except Exception as e:
                erreurs.append(f"Erreur transfert {transfert_id}: {str(e)}")
        
        if valides:
            messages.success(request, f"{valides} transfert(s) validé(s) avec succès")
        for erreur in erreurs:
            messages.warning(request, erreur)
    
    return redirect('inventory:historique_transferts', depot_id=depot.id)


# ===== HISTORIQUE DES MOUVEMENTS DE STOCK =====

@login_required
@commercant_required
@boutique_access_required
def historique_mouvements_stock(request, boutique_id):
    """Historique des mouvements de stock d'une boutique"""
    boutique = request.boutique
    
    # Filtres
    type_mouvement = request.GET.get('type', '')
    article_id = request.GET.get('article', '')
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    
    # Récupérer les mouvements de stock pour les articles de cette boutique
    mouvements = MouvementStock.objects.filter(
        article__boutique=boutique
    ).select_related('article', 'article__categorie').order_by('-date_mouvement')
    
    # Appliquer les filtres
    if type_mouvement:
        mouvements = mouvements.filter(type_mouvement=type_mouvement)
    
    if article_id:
        mouvements = mouvements.filter(article_id=article_id)
    
    if date_debut:
        try:
            date_debut_parsed = datetime.strptime(date_debut, '%Y-%m-%d')
            mouvements = mouvements.filter(date_mouvement__date__gte=date_debut_parsed)
        except ValueError:
            pass
    
    if date_fin:
        try:
            date_fin_parsed = datetime.strptime(date_fin, '%Y-%m-%d')
            mouvements = mouvements.filter(date_mouvement__date__lte=date_fin_parsed)
        except ValueError:
            pass
    
    # Statistiques
    stats = {
        'total_mouvements': mouvements.count(),
        'entrees': mouvements.filter(type_mouvement='ENTREE').count(),
        'sorties': mouvements.filter(type_mouvement='SORTIE').count(),
        'ventes': mouvements.filter(type_mouvement='VENTE').count(),
        'ajustements': mouvements.filter(type_mouvement='AJUSTEMENT').count(),
        'retours': mouvements.filter(type_mouvement='RETOUR').count(),
    }
    
    # Liste des articles pour le filtre
    articles = boutique.articles.filter(est_actif=True).order_by('nom')
    
    # Types de mouvement pour le filtre
    types_mouvement = MouvementStock.TYPES
    
    context = {
        'boutique': boutique,
        'mouvements': mouvements[:200],  # Limiter à 200 pour performance
        'stats': stats,
        'articles': articles,
        'types_mouvement': types_mouvement,
        'type_filter': type_mouvement,
        'article_filter': int(article_id) if article_id else None,
        'date_debut': date_debut,
        'date_fin': date_fin,
    }
    
    return render(request, 'inventory/commercant/historique_mouvements_stock.html', context)
