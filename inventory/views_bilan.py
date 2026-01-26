from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Q, F, Count, Avg
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

import json
import logging

from .models import Commercant, Boutique, Vente, Article, MouvementStock, RapportCaisse
from .models_bilan import BilanGeneral, IndicateurPerformance
from .forms import BoutiqueForm, ArticleForm

# Importer les décorateurs
from .decorators import commercant_required, boutique_required

logger = logging.getLogger(__name__)

# ===== VUES PRINCIPALES DU BILAN =====

@login_required
@commercant_required
def tableau_bord_bilan(request):
    """Tableau de bord principal des bilans et indicateurs"""
    commercant = request.user.profil_commercant
    boutiques = commercant.boutiques.filter(est_active=True, est_depot=False)
    
    # Bilans récents
    bilans_recents = BilanGeneral.objects.filter(
        Q(commercant=commercant) | Q(boutique__in=boutiques)
    ).order_by('-date_generation')[:10]
    
    # Indicateurs clés en temps réel
    indicateurs = _calculer_indicateurs_temps_reel(commercant, boutiques)
    
    # Statistiques rapides
    stats_rapides = {
        'ca_jour': _get_ca_jour(commercant, boutiques),
        'ca_mois': _get_ca_mois(commercant, boutiques),
        'ventes_jour': _get_ventes_jour(commercant, boutiques),
        'marge_moyenne': _get_marge_moyenne(commercant, boutiques),
        'stock_alerte': _get_articles_stock_alerte(commercant, boutiques).count(),
    }
    
    context = {
        'commercant': commercant,
        'boutiques': boutiques,
        'bilans_recents': bilans_recents,
        'indicateurs': indicateurs,
        'stats_rapides': stats_rapides,
    }
    
    return render(request, 'inventory/bilan/tableau_bord.html', context)

@login_required
@commercant_required
def liste_bilans(request):
    """Liste de tous les bilans du commerçant"""
    commercant = request.user.profil_commercant
    
    # Filtres
    periode_filter = request.GET.get('periode', '')
    statut_filter = request.GET.get('statut', '')
    boutique_filter = request.GET.get('boutique', '')
    
    bilans_qs = BilanGeneral.objects.filter(
        Q(commercant=commercant) | Q(boutique__commercant=commercant)
    )
    
    if periode_filter:
        bilans_qs = bilans_qs.filter(periode=periode_filter)
    
    if statut_filter:
        bilans_qs = bilans_qs.filter(statut=statut_filter)
    
    if boutique_filter:
        bilans_qs = bilans_qs.filter(boutique_id=boutique_filter)
    
    bilans = bilans_qs.order_by('-date_generation')
    
    # Options pour les filtres
    boutiques = commercant.boutiques.all()
    
    context = {
        'bilans': bilans,
        'boutiques': boutiques,
        'periode_filter': periode_filter,
        'statut_filter': statut_filter,
        'boutique_filter': boutique_filter,
    }
    
    return render(request, 'inventory/bilan/liste_bilans.html', context)

@login_required
@commercant_required
def creer_bilan(request):
    """Création d'un nouveau bilan"""
    commercant = request.user.profil_commercant
    boutiques = commercant.boutiques.filter(est_active=True)
    
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            titre = request.POST.get('titre')
            description = request.POST.get('description', '')
            periode = request.POST.get('periode', 'MENSUEL')
            boutique_id = request.POST.get('boutique')
            date_debut_str = request.POST.get('date_debut')
            date_fin_str = request.POST.get('date_fin')
            
            # Validation
            if not titre or not date_debut_str or not date_fin_str:
                messages.error(request, "Veuillez remplir tous les champs obligatoires.")
                return redirect('inventory:creer_bilan')
            
            date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d')
            date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d')
            
            if date_debut >= date_fin:
                messages.error(request, "La date de début doit être antérieure à la date de fin.")
                return redirect('inventory:creer_bilan')
            
            # Créer le bilan
            bilan = BilanGeneral(
                titre=titre,
                description=description,
                periode=periode,
                date_debut=date_debut,
                date_fin=date_fin,
                commercant=commercant if not boutique_id else None,
                boutique_id=boutique_id if boutique_id else None,
            )
            
            # Générer les données du bilan
            if bilan.generer_donnees():
                bilan.save()
                messages.success(request, f"Bilan '{titre}' créé avec succès.")
                return redirect('inventory:detail_bilan', bilan.id)
            else:
                messages.error(request, "Erreur lors de la génération des données du bilan.")
                
        except Exception as e:
            logger.error(f"Erreur lors de la création du bilan: {str(e)}")
            messages.error(request, f"Une erreur est survenue: {str(e)}")
    
    context = {
        'commercant': commercant,
        'boutiques': boutiques,
        'periode_choices': BilanGeneral.PERIODE_CHOICES,
    }
    
    return render(request, 'inventory/bilan/creer_bilan.html', context)

@login_required
@commercant_required
def detail_bilan(request, bilan_id):
    """Détail d'un bilan spécifique"""
    commercant = request.user.profil_commercant
    bilan = get_object_or_404(BilanGeneral, id=bilan_id)
    
    # Vérifier les autorisations
    if bilan.commercant != commercant and (not bilan.boutique or bilan.boutique.commercant != commercant):
        messages.error(request, "Accès non autorisé à ce bilan.")
        return redirect('inventory:liste_bilans')
    
    # Données détaillées du bilan
    donnees_detaillees = bilan.donnees_detaillees or {}
    
    # Préparer les données pour les graphiques
    ventes_par_jour = donnees_detaillees.get('ventes_par_jour', [])
    top_articles = donnees_detaillees.get('top_articles', [])
    categories_perf = donnees_detaillees.get('categories_performance', [])
    indicateurs_cles = donnees_detaillees.get('indicateurs_cles', {})
    
    context = {
        'bilan': bilan,
        'ventes_par_jour': ventes_par_jour,
        'top_articles': top_articles,
        'categories_perf': categories_perf,
        'indicateurs_cles': indicateurs_cles,
    }
    
    return render(request, 'inventory/bilan/detail_bilan.html', context)

@login_required
@commercant_required
def valider_bilan(request, bilan_id):
    """Validation d'un bilan"""
    commercant = request.user.profil_commercant
    bilan = get_object_or_404(BilanGeneral, id=bilan_id)
    
    # Vérifier les autorisations
    if bilan.commercant != commercant and (not bilan.boutique or bilan.boutique.commercant != commercant):
        messages.error(request, "Accès non autorisé à ce bilan.")
        return redirect('inventory:liste_bilans')
    
    if bilan.statut != 'BROUILLON':
        messages.warning(request, "Ce bilan ne peut plus être validé.")
        return redirect('inventory:detail_bilan', bilan.id)
    
    if request.method == 'POST':
        try:
            bilan.valider(request.user.username)
            messages.success(request, "Bilan validé avec succès.")
        except Exception as e:
            logger.error(f"Erreur lors de la validation du bilan: {str(e)}")
            messages.error(request, f"Erreur lors de la validation: {str(e)}")
    
    return redirect('inventory:detail_bilan', bilan.id)

@login_required
@commercant_required
def exporter_bilan(request, bilan_id):
    """Export d'un bilan en format PDF ou Excel"""
    commercant = request.user.profil_commercant
    bilan = get_object_or_404(BilanGeneral, id=bilan_id)
    
    # Vérifier les autorisations
    if bilan.commercant != commercant and (not bilan.boutique or bilan.boutique.commercant != commercant):
        messages.error(request, "Accès non autorisé à ce bilan.")
        return redirect('inventory:liste_bilans')
    
    format_export = request.GET.get('format', 'pdf')
    
    if format_export == 'pdf':
        return _exporter_bilan_pdf(bilan)
    elif format_export == 'excel':
        return _exporter_bilan_excel(bilan)
    else:
        messages.error(request, "Format d'export non supporté.")
        return redirect('inventory:detail_bilan', bilan.id)

# ===== VUES DES INDICATEURS =====

@login_required
@commercant_required
def tableau_indicateurs(request):
    """Tableau de bord des indicateurs de performance"""
    commercant = request.user.profil_commercant
    boutiques = commercant.boutiques.filter(est_active=True)
    
    # Récupérer ou créer les indicateurs par défaut
    indicateurs = _get_or_create_indicateurs_defaut(commercant)
    
    # Mettre à jour les valeurs des indicateurs
    for indicateur in indicateurs:
        _mettre_a_jour_indicateur(indicateur, boutiques)
        indicateur.calculer_variation()
    
    # Indicateurs en alerte
    indicateurs_alerte = [ind for ind in indicateurs if ind.est_en_alerte()]
    
    # Grouper les indicateurs par catégorie
    indicateurs_par_categorie = {}
    for indicateur in indicateurs:
        categorie = indicateur.categorie
        if categorie not in indicateurs_par_categorie:
            indicateurs_par_categorie[categorie] = []
        indicateurs_par_categorie[categorie].append(indicateur)
    
    context = {
        'indicateurs': indicateurs,
        'indicateurs_alerte': indicateurs_alerte,
        'indicateurs_par_categorie': indicateurs_par_categorie,
        'categories': IndicateurPerformance.CATEGORIE_CHOICES,
    }
    
    return render(request, 'inventory/bilan/tableau_indicateurs.html', context)

@login_required
@commercant_required
def rafraichir_indicateurs(request):
    """Rafraîchit tous les indicateurs (AJAX)"""
    commercant = request.user.profil_commercant
    boutiques = commercant.boutiques.filter(est_active=True)
    
    indicateurs = IndicateurPerformance.objects.filter(
        Q(commercant=commercant) | Q(boutique__in=boutiques)
    )
    
    resultats = []
    for indicateur in indicateurs:
        ancienne_valeur = indicateur.valeur_actuelle
        _mettre_a_jour_indicateur(indicateur, boutiques)
        indicateur.calculer_variation()
        
        resultats.append({
            'id': indicateur.id,
            'nom': indicateur.nom,
            'valeur_actuelle': float(indicateur.valeur_actuelle),
            'valeur_precedente': float(indicateur.valeur_precedente),
            'variation_pourcentage': float(indicateur.variation_pourcentage),
            'en_alerte': indicateur.est_en_alerte(),
        })
    
    return JsonResponse({'success': True, 'indicateurs': resultats})

# ===== FONCTIONS UTILITAIRES =====

def _calculer_indicateurs_temps_reel(commercant, boutiques):
    """Calcule les indicateurs clés en temps réel"""
    aujourd_hui = timezone.now().date()
    debut_mois = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Ventes du jour
    ventes_jour = Vente.objects.filter(
        boutique__in=boutiques,
        date_vente__date=aujourd_hui,
        est_annulee=False
    )
    
    # Ventes du mois
    ventes_mois = Vente.objects.filter(
        boutique__in=boutiques,
        date_vente__gte=debut_mois,
        est_annulee=False
    )
    
    # Chiffre d'affaires
    ca_jour = ventes_jour.aggregate(total=Sum('montant_total'))['total'] or 0
    ca_mois = ventes_mois.aggregate(total=Sum('montant_total'))['total'] or 0
    
    # Nombre de ventes
    nb_ventes_jour = ventes_jour.count()
    nb_ventes_mois = ventes_mois.count()
    
    # Articles en stock
    total_articles = Article.objects.filter(boutique__in=boutiques, est_actif=True).count()
    articles_stock_bas = Article.objects.filter(
        boutique__in=boutiques,
        est_actif=True,
        quantite_stock__lte=F('boutique__alerte_stock_bas')
    ).count()
    
    return {
        'ca_jour': ca_jour,
        'ca_mois': ca_mois,
        'nb_ventes_jour': nb_ventes_jour,
        'nb_ventes_mois': nb_ventes_mois,
        'total_articles': total_articles,
        'articles_stock_bas': articles_stock_bas,
        'panier_moyen_jour': ca_jour / nb_ventes_jour if nb_ventes_jour > 0 else 0,
        'panier_moyen_mois': ca_mois / nb_ventes_mois if nb_ventes_mois > 0 else 0,
    }

def _get_ca_jour(commercant, boutiques):
    """Retourne le chiffre d'affaires du jour"""
    aujourd_hui = timezone.now().date()
    return Vente.objects.filter(
        boutique__in=boutiques,
        date_vente__date=aujourd_hui,
        est_annulee=False
    ).aggregate(total=Sum('montant_total'))['total'] or 0

def _get_ca_mois(commercant, boutiques):
    """Retourne le chiffre d'affaires du mois"""
    debut_mois = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return Vente.objects.filter(
        boutique__in=boutiques,
        date_vente__gte=debut_mois,
        est_annulee=False
    ).aggregate(total=Sum('montant_total'))['total'] or 0

def _get_ventes_jour(commercant, boutiques):
    """Retourne le nombre de ventes du jour"""
    aujourd_hui = timezone.now().date()
    return Vente.objects.filter(
        boutique__in=boutiques,
        date_vente__date=aujourd_hui,
        est_annulee=False
    ).count()

def _get_marge_moyenne(commercant, boutiques):
    """Calcule la marge moyenne"""
    from django.db.models import Avg
    
    lignes_ventes = Vente.objects.filter(
        boutique__in=boutiques,
        est_annulee=False
    ).aggregate(
        ca_total=Sum('montant_total'),
        cout_total=Sum(F('lignes__quantite') * F('lignes__article__prix_achat'))
    )
    
    ca_total = lignes_ventes['ca_total'] or 0
    cout_total = lignes_ventes['cout_total'] or 0
    
    if ca_total > 0:
        return ((ca_total - cout_total) / ca_total) * 100
    return 0

def _get_articles_stock_alerte(commercant, boutiques):
    """Retourne les articles avec stock bas"""
    return Article.objects.filter(
        boutique__in=boutiques,
        est_actif=True,
        quantite_stock__lte=F('boutique__alerte_stock_bas')
    )

def _get_or_create_indicateurs_defaut(commercant):
    """Crée les indicateurs par défaut si ils n'existent pas"""
    indicateurs_defaut = [
        {
            'nom': 'Chiffre d\'affaires journalier',
            'description': 'CA réalisé chaque jour',
            'categorie': 'VENTES',
            'periodicite': 'QUOTIDIEN',
            'formule': {'type': 'somme', 'champ': 'montant_total', 'filtre': 'jour'},
            'objectif': 1000000,  # 1M CDF
            'seuil_alerte': 500000,  # 500K CDF
        },
        {
            'nom': 'Nombre de ventes journalier',
            'description': 'Nombre de ventes réalisées chaque jour',
            'categorie': 'VENTES',
            'periodicite': 'QUOTIDIEN',
            'formule': {'type': 'compte', 'filtre': 'jour'},
            'objectif': 50,
            'seuil_alerte': 20,
        },
        {
            'nom': 'Taux de marge moyenne',
            'description': 'Pourcentage de marge moyen',
            'categorie': 'FINANCIER',
            'periodicite': 'HEBDOMADAIRE',
            'formule': {'type': 'marge', 'periode': 'semaine'},
            'objectif': 30,
            'seuil_alerte': 15,
        },
        {
            'nom': 'Rotation du stock',
            'description': 'Nombre de rotations de stock par période',
            'categorie': 'STOCK',
            'periodicite': 'MENSUEL',
            'formule': {'type': 'rotation_stock'},
            'objectif': 4,
            'seuil_alerte': 2,
        },
        {
            'nom': 'Articles en alerte de stock',
            'description': 'Nombre d\'articles avec stock bas',
            'categorie': 'STOCK',
            'periodicite': 'REEL',
            'formule': {'type': 'compte_stock_alerte'},
            'objectif': 0,
            'seuil_alerte': 5,
        },
    ]
    
    indicateurs = []
    for indic_def in indicateurs_defaut:
        indicateur, created = IndicateurPerformance.objects.get_or_create(
            nom=indic_def['nom'],
            commercant=commercant,
            defaults={
                'description': indic_def['description'],
                'categorie': indic_def['categorie'],
                'periodicite': indic_def['periodicite'],
                'formule': indic_def['formule'],
                'objectif': indic_def['objectif'],
                'seuil_alerte': indic_def['seuil_alerte'],
            }
        )
        indicateurs.append(indicateur)
    
    return indicateurs

def _mettre_a_jour_indicateur(indicateur, boutiques):
    """Met à jour la valeur d'un indicateur"""
    formule = indicateur.formule
    type_formule = formule.get('type')
    
    # Sauvegarder l'ancienne valeur
    indicateur.valeur_precedente = indicateur.valeur_actuelle
    
    if type_formule == 'somme':
        champ = formule.get('champ')
        filtre = formule.get('filtre')
        
        queryset = Vente.objects.filter(boutique__in=boutiques, est_annulee=False)
        
        if filtre == 'jour':
            queryset = queryset.filter(date_vente__date=timezone.now().date())
        elif filtre == 'semaine':
            debut_semaine = timezone.now() - timedelta(days=timezone.now().weekday())
            queryset = queryset.filter(date_vente__gte=debut_semaine)
        elif filtre == 'mois':
            debut_mois = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            queryset = queryset.filter(date_vente__gte=debut_mois)
        
        indicateur.valeur_actuelle = queryset.aggregate(total=Sum(champ))['total'] or 0
        
    elif type_formule == 'compte':
        filtre = formule.get('filtre')
        
        queryset = Vente.objects.filter(boutique__in=boutiques, est_annulee=False)
        
        if filtre == 'jour':
            queryset = queryset.filter(date_vente__date=timezone.now().date())
        
        indicateur.valeur_actuelle = queryset.count()
        
    elif type_formule == 'marge':
        periode = formule.get('periode', 'semaine')
        
        queryset = Vente.objects.filter(boutique__in=boutiques, est_annulee=False)
        
        if periode == 'semaine':
            debut_semaine = timezone.now() - timedelta(days=timezone.now().weekday())
            queryset = queryset.filter(date_vente__gte=debut_semaine)
        elif periode == 'mois':
            debut_mois = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            queryset = queryset.filter(date_vente__gte=debut_mois)
        
        # Calculer la marge
        lignes_ventes = queryset.aggregate(
            ca_total=Sum('montant_total'),
            cout_total=Sum(F('lignes__quantite') * F('lignes__article__prix_achat'))
        )
        
        ca_total = lignes_ventes['ca_total'] or 0
        cout_total = lignes_ventes['cout_total'] or 0
        
        if ca_total > 0:
            indicateur.valeur_actuelle = ((ca_total - cout_total) / ca_total) * 100
        else:
            indicateur.valeur_actuelle = 0
            
    elif type_formule == 'rotation_stock':
        # Calcul de la rotation du stock (coût des ventes / stock moyen)
        debut_mois = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        ventes_mois = Vente.objects.filter(
            boutique__in=boutiques,
            date_vente__gte=debut_mois,
            est_annulee=False
        )
        
        cout_ventes = ventes_mois.aggregate(
            cout_total=Sum(F('lignes__quantite') * F('lignes__article__prix_achat'))
        )['cout_total'] or 0
        
        # Stock moyen
        stock_moyen = Article.objects.filter(
            boutique__in=boutiques,
            est_actif=True
        ).aggregate(
            total=Sum(F('quantite_stock') * F('prix_achat'))
        )['total'] or 0
        
        if stock_moyen > 0:
            indicateur.valeur_actuelle = cout_ventes / stock_moyen
        else:
            indicateur.valeur_actuelle = 0
            
    elif type_formule == 'compte_stock_alerte':
        indicateur.valeur_actuelle = Article.objects.filter(
            boutique__in=boutiques,
            est_actif=True,
            quantite_stock__lte=F('boutique__alerte_stock_bas')
        ).count()
    
    indicateur.save()

def _exporter_bilan_pdf(bilan):
    """Exporte un bilan en format PDF"""
    # Implémentation à faire avec ReportLab ou similar
    from django.http import HttpResponse
    import io
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="bilan_{bilan.id}.pdf"'
    
    # Pour l'instant, retourner un simple texte
    buffer = io.StringIO()
    buffer.write(f"BILAN GÉNÉRAL\n")
    buffer.write(f"{'='*50}\n")
    buffer.write(f"Titre: {bilan.titre}\n")
    buffer.write(f"Période: {bilan.periode}\n")
    buffer.write(f"Du: {bilan.date_debut.strftime('%d/%m/%Y')} au {bilan.date_fin.strftime('%d/%m/%Y')}\n")
    buffer.write(f"\nCHIFFRE D'AFFAIRES\n")
    buffer.write(f"CA CDF: {bilan.chiffre_affaires_total:,.2f} CDF\n")
    buffer.write(f"CA USD: {bilan.chiffre_affaires_total_usd:,.2f} USD\n")
    buffer.write(f"\nMARGE\n")
    buffer.write(f"Marge brute: {bilan.marge_brute:,.2f} CDF\n")
    buffer.write(f"Taux de marge: {bilan.taux_marge_brute:.2f}%\n")
    
    response.write(buffer.getvalue().encode('latin-1'))
    return response

def _exporter_bilan_excel(bilan):
    """Exporte un bilan en format Excel"""
    # Implémentation à faire avec openpyxl ou pandas
    from django.http import HttpResponse
    import io
    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="bilan_{bilan.id}.xlsx"'
    
    # Pour l'instant, retourner un CSV simple
    response['Content-Type'] = 'text/csv'
    response['Content-Disposition'] = f'attachment; filename="bilan_{bilan.id}.csv"'
    
    buffer = io.StringIO()
    buffer.write("Indicateur,Valeur\n")
    buffer.write(f"Chiffre d'affaires CDF,{bilan.chiffre_affaires_total}\n")
    buffer.write(f"Chiffre d'affaires USD,{bilan.chiffre_affaires_total_usd}\n")
    buffer.write(f"Marge brute,{bilan.marge_brute}\n")
    buffer.write(f"Taux de marge,{bilan.taux_marge_brute}\n")
    buffer.write(f"Nombre de ventes,{bilan.nombre_ventes}\n")
    buffer.write(f"Panier moyen,{bilan.panier_moyen}\n")
    
    response.write(buffer.getvalue())
    return response
