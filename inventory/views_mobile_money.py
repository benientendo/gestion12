"""
Vues pour la gestion des points de vente Mobile Money
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import Boutique, TransactionMobileMoney, Commercant, VenteCredit, StockCredit, ApprovisionnementCredit
from .decorators import commercant_required


@login_required
@commercant_required
def dashboard_mobile_money(request, boutique_id):
    """Dashboard principal pour un point de vente Mobile Money"""
    commercant = get_object_or_404(Commercant, user=request.user)
    boutique = get_object_or_404(Boutique, id=boutique_id, commercant=commercant, type_commerce='MOBILE_MONEY')
    
    # Statistiques du jour
    aujourd_hui = timezone.now().date()
    transactions_jour = boutique.transactions_mobile_money.filter(
        date_transaction__date=aujourd_hui,
        statut='CONFIRME'
    )
    
    stats_jour = {
        'total_transactions': transactions_jour.count(),
        'total_montant': transactions_jour.aggregate(total=Sum('montant'))['total'] or Decimal('0'),
        'total_commission': transactions_jour.aggregate(total=Sum('commission'))['total'] or Decimal('0'),
        'depots': transactions_jour.filter(type_operation='DEPOT').count(),
        'retraits': transactions_jour.filter(type_operation='RETRAIT').count(),
        'transferts': transactions_jour.filter(type_operation='TRANSFERT').count(),
    }
    
    # Statistiques par opérateur
    stats_operateurs = transactions_jour.values('operateur').annotate(
        count=Count('id'),
        total=Sum('montant'),
        commission=Sum('commission')
    )
    
    # Dernières transactions
    dernieres_transactions = boutique.transactions_mobile_money.order_by('-date_transaction')[:10]
    
    context = {
        'boutique': boutique,
        'stats_jour': stats_jour,
        'stats_operateurs': stats_operateurs,
        'dernieres_transactions': dernieres_transactions,
        'operateurs': TransactionMobileMoney.OPERATEUR_CHOICES,
        'types_operation': TransactionMobileMoney.TYPE_OPERATION_CHOICES,
    }
    return render(request, 'inventory/mobile_money/dashboard.html', context)


@login_required
@commercant_required
def nouvelle_transaction(request, boutique_id):
    """Créer une nouvelle transaction Mobile Money"""
    commercant = get_object_or_404(Commercant, user=request.user)
    boutique = get_object_or_404(Boutique, id=boutique_id, commercant=commercant, type_commerce='MOBILE_MONEY')
    
    if request.method == 'POST':
        try:
            type_operation = request.POST.get('type_operation')
            operateur = request.POST.get('operateur')
            numero_telephone = request.POST.get('numero_telephone')
            nom_client = request.POST.get('nom_client', '')
            montant = Decimal(request.POST.get('montant', '0'))
            commission = Decimal(request.POST.get('commission', '0'))
            numero_destinataire = request.POST.get('numero_destinataire', '')
            reference = request.POST.get('reference', '')
            notes = request.POST.get('notes', '')
            
            # Validation
            if not all([type_operation, operateur, numero_telephone, montant]):
                messages.error(request, "Veuillez remplir tous les champs obligatoires.")
                return redirect('inventory:mobile_money_dashboard', boutique_id=boutique_id)
            
            # Créer la transaction
            transaction = TransactionMobileMoney.objects.create(
                boutique=boutique,
                type_operation=type_operation,
                operateur=operateur,
                numero_telephone_client=numero_telephone,
                nom_client=nom_client,
                montant=montant,
                commission=commission,
                montant_net=montant - commission,
                numero_destinataire=numero_destinataire,
                reference_operateur=reference,
                notes=notes,
                statut='CONFIRME',
                effectue_par=request.user,
                date_confirmation=timezone.now()
            )
            
            messages.success(request, f"Transaction {transaction.get_type_operation_display()} de {montant} FC enregistrée avec succès.")
            
        except Exception as e:
            messages.error(request, f"Erreur lors de l'enregistrement: {str(e)}")
        
        return redirect('inventory:mobile_money_dashboard', boutique_id=boutique_id)
    
    context = {
        'boutique': boutique,
        'operateurs': TransactionMobileMoney.OPERATEUR_CHOICES,
        'types_operation': TransactionMobileMoney.TYPE_OPERATION_CHOICES,
    }
    return render(request, 'inventory/mobile_money/nouvelle_transaction.html', context)


@login_required
@commercant_required
def liste_transactions(request, boutique_id):
    """Liste des transactions Mobile Money avec filtres"""
    commercant = get_object_or_404(Commercant, user=request.user)
    boutique = get_object_or_404(Boutique, id=boutique_id, commercant=commercant, type_commerce='MOBILE_MONEY')
    
    transactions = boutique.transactions_mobile_money.all()
    
    # Filtres
    type_op = request.GET.get('type_operation')
    operateur = request.GET.get('operateur')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    statut = request.GET.get('statut')
    
    if type_op:
        transactions = transactions.filter(type_operation=type_op)
    if operateur:
        transactions = transactions.filter(operateur=operateur)
    if date_debut:
        transactions = transactions.filter(date_transaction__date__gte=date_debut)
    if date_fin:
        transactions = transactions.filter(date_transaction__date__lte=date_fin)
    if statut:
        transactions = transactions.filter(statut=statut)
    
    # Totaux
    totaux = transactions.filter(statut='CONFIRME').aggregate(
        total_montant=Sum('montant'),
        total_commission=Sum('commission'),
        count=Count('id')
    )
    
    context = {
        'boutique': boutique,
        'transactions': transactions.order_by('-date_transaction')[:100],
        'totaux': totaux,
        'operateurs': TransactionMobileMoney.OPERATEUR_CHOICES,
        'types_operation': TransactionMobileMoney.TYPE_OPERATION_CHOICES,
        'statuts': TransactionMobileMoney.STATUT_CHOICES,
        'filtres': {
            'type_operation': type_op,
            'operateur': operateur,
            'date_debut': date_debut,
            'date_fin': date_fin,
            'statut': statut,
        }
    }
    return render(request, 'inventory/mobile_money/liste_transactions.html', context)


@login_required
@commercant_required
def rapport_mobile_money(request, boutique_id):
    """Rapport des transactions Mobile Money"""
    commercant = get_object_or_404(Commercant, user=request.user)
    boutique = get_object_or_404(Boutique, id=boutique_id, commercant=commercant, type_commerce='MOBILE_MONEY')
    
    # Période (défaut: 7 derniers jours)
    date_fin = timezone.now().date()
    date_debut = date_fin - timedelta(days=6)
    
    if request.GET.get('date_debut'):
        from datetime import datetime
        date_debut = datetime.strptime(request.GET.get('date_debut'), '%Y-%m-%d').date()
    if request.GET.get('date_fin'):
        from datetime import datetime
        date_fin = datetime.strptime(request.GET.get('date_fin'), '%Y-%m-%d').date()
    
    transactions = boutique.transactions_mobile_money.filter(
        date_transaction__date__gte=date_debut,
        date_transaction__date__lte=date_fin,
        statut='CONFIRME'
    )
    
    # Statistiques par type d'opération
    stats_par_type = transactions.values('type_operation').annotate(
        count=Count('id'),
        total_montant=Sum('montant'),
        total_commission=Sum('commission')
    )
    
    # Statistiques par opérateur
    stats_par_operateur = transactions.values('operateur').annotate(
        count=Count('id'),
        total_montant=Sum('montant'),
        total_commission=Sum('commission')
    )
    
    # Totaux
    totaux = transactions.aggregate(
        total_transactions=Count('id'),
        total_montant=Sum('montant'),
        total_commission=Sum('commission')
    )
    
    context = {
        'boutique': boutique,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'stats_par_type': stats_par_type,
        'stats_par_operateur': stats_par_operateur,
        'totaux': totaux,
    }
    return render(request, 'inventory/mobile_money/rapport.html', context)


# ==================== VENTE DE CRÉDIT ====================

@login_required
@commercant_required
def dashboard_credit(request, boutique_id):
    """Dashboard pour la vente de crédit"""
    commercant = get_object_or_404(Commercant, user=request.user)
    boutique = get_object_or_404(Boutique, id=boutique_id, commercant=commercant, type_commerce='MOBILE_MONEY')
    
    aujourd_hui = timezone.now().date()
    
    # Ventes du jour
    ventes_jour = boutique.ventes_credit.filter(date_vente__date=aujourd_hui)
    
    stats_ventes = {
        'total_ventes': ventes_jour.count(),
        'unites_vendues': ventes_jour.aggregate(total=Sum('unites_vendues'))['total'] or Decimal('0'),
        'montant_recu': ventes_jour.aggregate(total=Sum('montant_recu'))['total'] or Decimal('0'),
        'benefice': ventes_jour.aggregate(total=Sum('benefice'))['total'] or Decimal('0'),
        'ventes_detail': ventes_jour.filter(type_vente='DETAIL').count(),
        'ventes_gros': ventes_jour.filter(type_vente='GROS').count(),
    }
    
    # Stock de crédit par opérateur
    stocks = boutique.stocks_credit.all()
    
    # Dernières ventes
    dernieres_ventes = boutique.ventes_credit.order_by('-date_vente')[:10]
    
    context = {
        'boutique': boutique,
        'stats_ventes': stats_ventes,
        'stocks': stocks,
        'dernieres_ventes': dernieres_ventes,
        'operateurs': VenteCredit.OPERATEUR_CHOICES,
    }
    return render(request, 'inventory/mobile_money/dashboard_credit.html', context)


@login_required
@commercant_required
def vendre_credit(request, boutique_id):
    """Enregistrer une vente de crédit"""
    commercant = get_object_or_404(Commercant, user=request.user)
    boutique = get_object_or_404(Boutique, id=boutique_id, commercant=commercant, type_commerce='MOBILE_MONEY')
    
    if request.method == 'POST':
        try:
            type_vente = request.POST.get('type_vente', 'DETAIL')
            operateur = request.POST.get('operateur')
            unites_vendues = Decimal(request.POST.get('unites_vendues', '0'))
            montant_recu = Decimal(request.POST.get('montant_recu', '0'))
            numero_client = request.POST.get('numero_client', '')
            nom_client = request.POST.get('nom_client', '')
            notes = request.POST.get('notes', '')
            
            # Vérifier le stock
            stock = StockCredit.objects.filter(boutique=boutique, operateur=operateur).first()
            if stock and stock.unites_disponibles < unites_vendues:
                messages.warning(request, f"Stock insuffisant pour {operateur}. Stock actuel: {stock.unites_disponibles} unités")
            
            # Créer la vente (le stock est déduit automatiquement dans save())
            vente = VenteCredit.objects.create(
                boutique=boutique,
                type_vente=type_vente,
                operateur=operateur,
                unites_vendues=unites_vendues,
                montant_recu=montant_recu,
                numero_telephone_client=numero_client,
                nom_client=nom_client,
                notes=notes,
                effectue_par=request.user
            )
            
            messages.success(request, f"Vente de crédit {operateur} de {unites_vendues} unités enregistrée. Bénéfice: {vente.benefice} FC")
            
        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
        
        return redirect('inventory:mobile_money_credit_dashboard', boutique_id=boutique_id)
    
    # Stocks actuels
    stocks = {s.operateur: s.unites_disponibles for s in boutique.stocks_credit.all()}
    
    context = {
        'boutique': boutique,
        'operateurs': VenteCredit.OPERATEUR_CHOICES,
        'stocks': stocks,
    }
    return render(request, 'inventory/mobile_money/vendre_credit.html', context)


@login_required
@commercant_required
def approvisionner_credit(request, boutique_id):
    """Approvisionner le stock de crédit"""
    commercant = get_object_or_404(Commercant, user=request.user)
    boutique = get_object_or_404(Boutique, id=boutique_id, commercant=commercant, type_commerce='MOBILE_MONEY')
    
    if request.method == 'POST':
        try:
            operateur = request.POST.get('operateur')
            unites = Decimal(request.POST.get('unites', '0'))
            cout_achat = Decimal(request.POST.get('cout_achat', '0'))
            fournisseur = request.POST.get('fournisseur', '')
            reference = request.POST.get('reference', '')
            notes = request.POST.get('notes', '')
            
            # Créer l'approvisionnement (le stock est mis à jour automatiquement dans le save())
            appro = ApprovisionnementCredit.objects.create(
                boutique=boutique,
                operateur=operateur,
                unites=unites,
                cout_achat=cout_achat,
                fournisseur=fournisseur,
                reference=reference,
                notes=notes,
                effectue_par=request.user
            )
            
            messages.success(request, f"Flash {operateur} de {unites} unités enregistré.")
            
        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
        
        return redirect('inventory:mobile_money_credit_dashboard', boutique_id=boutique_id)
    
    context = {
        'boutique': boutique,
        'operateurs': VenteCredit.OPERATEUR_CHOICES,
    }
    return render(request, 'inventory/mobile_money/approvisionner_credit.html', context)


@login_required
@commercant_required
def historique_credit(request, boutique_id):
    """Historique des ventes de crédit"""
    commercant = get_object_or_404(Commercant, user=request.user)
    boutique = get_object_or_404(Boutique, id=boutique_id, commercant=commercant, type_commerce='MOBILE_MONEY')
    
    ventes = boutique.ventes_credit.all()
    
    # Filtres
    type_vente = request.GET.get('type_vente')
    operateur = request.GET.get('operateur')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    
    if type_vente:
        ventes = ventes.filter(type_vente=type_vente)
    if operateur:
        ventes = ventes.filter(operateur=operateur)
    if date_debut:
        ventes = ventes.filter(date_vente__date__gte=date_debut)
    if date_fin:
        ventes = ventes.filter(date_vente__date__lte=date_fin)
    
    # Totaux
    totaux = ventes.aggregate(
        total_vente=Sum('montant_vente'),
        total_achat=Sum('montant_achat'),
        total_benefice=Sum('benefice'),
        count=Count('id')
    )
    
    context = {
        'boutique': boutique,
        'ventes': ventes.order_by('-date_vente')[:100],
        'totaux': totaux,
        'operateurs': VenteCredit.OPERATEUR_CHOICES,
        'filtres': {
            'type_vente': type_vente,
            'operateur': operateur,
            'date_debut': date_debut,
            'date_fin': date_fin,
        }
    }
    return render(request, 'inventory/mobile_money/historique_credit.html', context)
