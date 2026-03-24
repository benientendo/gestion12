from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from django.http import JsonResponse
from decimal import Decimal, InvalidOperation
import json

from .models import Boutique, Article, ClientAcompte, VenteAcompte, PaiementAcompte, Client
from .decorators import commercant_required


def _boutique_from_serial(request, boutique_id):
    """Authentifie un terminal MAUI via X-Device-Serial et retourne (boutique, error_response)."""
    serial = request.META.get('HTTP_X_DEVICE_SERIAL', '').strip()
    if not serial:
        return None, JsonResponse({'error': 'Header X-Device-Serial manquant'}, status=403)
    try:
        client = Client.objects.select_related('boutique').get(numero_serie=serial, est_actif=True)
    except Client.DoesNotExist:
        return None, JsonResponse({'error': 'Terminal non autorisé'}, status=403)
    if not client.boutique or client.boutique.id != boutique_id:
        return None, JsonResponse({'error': 'Boutique non autorisée pour ce terminal'}, status=403)
    return client.boutique, None


def _boutique_from_serial_for_vente(request, vente_id):
    """Authentifie un terminal MAUI et retourne (vente, boutique, error_response)."""
    serial = request.META.get('HTTP_X_DEVICE_SERIAL', '').strip()
    if not serial:
        return None, None, JsonResponse({'error': 'Header X-Device-Serial manquant'}, status=403)
    try:
        client = Client.objects.select_related('boutique').get(numero_serie=serial, est_actif=True)
    except Client.DoesNotExist:
        return None, None, JsonResponse({'error': 'Terminal non autorisé'}, status=403)
    if not client.boutique:
        return None, None, JsonResponse({'error': 'Aucune boutique associée à ce terminal'}, status=403)
    vente = get_object_or_404(VenteAcompte, id=vente_id, boutique=client.boutique)
    return vente, client.boutique, None


def _boutique_commercant(request, boutique_id):
    return get_object_or_404(Boutique, id=boutique_id, commercant=request.user.profil_commercant)


# ===== DASHBOARD LISTE =====

@login_required
@commercant_required
def liste_ventes_credit(request, boutique_id):
    boutique = _boutique_commercant(request, boutique_id)

    ventes_qs = VenteAcompte.objects.filter(boutique=boutique).select_related('client')

    # Stats globales
    nb_clients   = ClientAcompte.objects.filter(boutique=boutique).count()
    nb_en_cours  = ventes_qs.filter(statut='EN_COURS').count()
    nb_solde     = ventes_qs.filter(statut='SOLDE').count()
    agg          = ventes_qs.filter(statut='EN_COURS').aggregate(
        total_paye=Sum('montant_paye'),
        total_prix=Sum('prix_total'),
    )
    total_encaisse = agg['total_paye'] or Decimal('0')
    total_prix     = agg['total_prix'] or Decimal('0')
    total_du       = max(total_prix - total_encaisse, Decimal('0'))

    # Filtres
    statut_filter = request.GET.get('statut', '')
    search        = request.GET.get('q', '').strip()

    ventes = ventes_qs
    if statut_filter:
        ventes = ventes.filter(statut=statut_filter)
    if search:
        ventes = ventes.filter(
            Q(client__nom__icontains=search)    |
            Q(client__prenom__icontains=search) |
            Q(client__telephone__icontains=search) |
            Q(article_nom__icontains=search)    |
            Q(reference__icontains=search)
        )

    # Liste des clients pour le formulaire de création
    clients = ClientAcompte.objects.filter(boutique=boutique).order_by('nom')
    # Articles disponibles pour la saisie rapide
    articles = boutique.articles.filter(est_actif=True).order_by('nom')[:200]

    context = {
        'boutique':       boutique,
        'ventes':         ventes,
        'clients':        clients,
        'articles_dispo': articles,
        'nb_clients':     nb_clients,
        'nb_en_cours':    nb_en_cours,
        'nb_solde':       nb_solde,
        'total_du':       total_du,
        'total_encaisse': total_encaisse,
        'statut_filter':  statut_filter,
        'search':         search,
    }
    return render(request, 'inventory/credit/liste_ventes_credit.html', context)


# ===== CRÉER UNE VENTE À CRÉDIT =====

@login_required
@commercant_required
def creer_vente_credit(request, boutique_id):
    boutique = _boutique_commercant(request, boutique_id)

    if request.method != 'POST':
        return redirect('inventory:liste_ventes_credit', boutique_id=boutique_id)

    # Champs client
    client_id  = request.POST.get('client_id', '').strip()
    nom        = request.POST.get('nom', '').strip()
    prenom     = request.POST.get('prenom', '').strip()
    telephone  = request.POST.get('telephone', '').strip()
    adresse    = request.POST.get('adresse', '').strip()

    # Champs article
    article_nom = request.POST.get('article_nom', '').strip()
    article_id  = request.POST.get('article_id', '').strip()

    # Montants
    try:
        prix_total   = Decimal(request.POST.get('prix_total', '0') or '0')
        seuil_pct    = Decimal(request.POST.get('seuil_pct', '50') or '50')
        seuil_retrait = (prix_total * seuil_pct / 100).quantize(Decimal('1'))
    except (InvalidOperation, ValueError):
        messages.error(request, "Montants invalides.")
        return redirect('inventory:liste_ventes_credit', boutique_id=boutique_id)

    commentaire = request.POST.get('commentaire', '')

    if not article_nom or prix_total <= 0:
        messages.error(request, "L'article et le prix total sont obligatoires.")
        return redirect('inventory:liste_ventes_credit', boutique_id=boutique_id)

    if not client_id and not nom:
        messages.error(request, "Veuillez sélectionner ou créer un client.")
        return redirect('inventory:liste_ventes_credit', boutique_id=boutique_id)

    with transaction.atomic():
        # Client : existant ou nouveau
        if client_id:
            client = get_object_or_404(ClientAcompte, id=client_id, boutique=boutique)
        else:
            client = ClientAcompte.objects.create(
                boutique=boutique,
                nom=nom,
                prenom=prenom,
                telephone=telephone,
                adresse=adresse,
            )

        # Article (optionnel – lien direct)
        article = None
        if article_id:
            try:
                article = Article.objects.get(id=article_id, boutique=boutique)
                if not article_nom:
                    article_nom = article.nom
            except Article.DoesNotExist:
                pass

        vente = VenteAcompte.objects.create(
            boutique=boutique,
            client=client,
            article=article,
            article_nom=article_nom,
            prix_total=prix_total,
            seuil_retrait=seuil_retrait,
            commentaire=commentaire,
            created_by=request.user.username,
        )

    messages.success(request, f"Vente {vente.reference} créée pour {client.nom_complet}.")
    return redirect('inventory:detail_vente_credit', boutique_id=boutique_id, vente_id=vente.id)


# ===== DÉTAIL D'UNE VENTE =====

@login_required
@commercant_required
def detail_vente_credit(request, boutique_id, vente_id):
    boutique = _boutique_commercant(request, boutique_id)
    vente    = get_object_or_404(VenteAcompte, id=vente_id, boutique=boutique)
    paiements = vente.paiements.all()

    context = {
        'boutique':  boutique,
        'vente':     vente,
        'paiements': paiements,
    }
    return render(request, 'inventory/credit/detail_vente_credit.html', context)


# ===== ENREGISTRER UN PAIEMENT =====

@login_required
@commercant_required
def enregistrer_paiement(request, boutique_id, vente_id):
    boutique = _boutique_commercant(request, boutique_id)
    vente    = get_object_or_404(VenteAcompte, id=vente_id, boutique=boutique)

    if request.method != 'POST':
        return redirect('inventory:detail_vente_credit', boutique_id=boutique_id, vente_id=vente_id)

    if vente.statut != 'EN_COURS':
        messages.error(request, "Cette vente n'est plus en cours.")
        return redirect('inventory:detail_vente_credit', boutique_id=boutique_id, vente_id=vente_id)

    try:
        montant = Decimal(request.POST.get('montant', '0') or '0')
    except (InvalidOperation, ValueError):
        messages.error(request, "Montant invalide.")
        return redirect('inventory:detail_vente_credit', boutique_id=boutique_id, vente_id=vente_id)

    notes = request.POST.get('notes', '')

    if montant <= 0:
        messages.error(request, "Le montant doit être supérieur à 0.")
        return redirect('inventory:detail_vente_credit', boutique_id=boutique_id, vente_id=vente_id)

    if vente.montant_paye + montant > vente.prix_total:
        messages.error(request, f"Montant dépasse le solde restant ({vente.montant_restant:,.0f} FC).")
        return redirect('inventory:detail_vente_credit', boutique_id=boutique_id, vente_id=vente_id)

    with transaction.atomic():
        paiement = PaiementAcompte.objects.create(
            vente=vente,
            montant=montant,
            recu_par=request.user.username,
            notes=notes,
        )
        vente.montant_paye += montant
        if vente.montant_paye >= vente.prix_total:
            vente.statut = 'SOLDE'
        vente.save()

    messages.success(request, f"Paiement de {montant:,.0f} FC enregistré. Réf : {paiement.reference_recu}")
    return redirect('inventory:recu_paiement', boutique_id=boutique_id, paiement_id=paiement.id)


# ===== MARQUER L'ARTICLE COMME RÉCUPÉRÉ =====

@login_required
@commercant_required
def marquer_retrait(request, boutique_id, vente_id):
    boutique = _boutique_commercant(request, boutique_id)
    vente    = get_object_or_404(VenteAcompte, id=vente_id, boutique=boutique)

    if request.method == 'POST':
        if not vente.peut_recuperer:
            messages.error(request, f"Conditions de retrait non remplies. Minimum requis : {vente.seuil_retrait:,.0f} FC.")
        else:
            with transaction.atomic():
                vente.article_recupere = True
                vente.date_retrait = timezone.now()
                if vente.montant_paye >= vente.prix_total:
                    vente.statut = 'SOLDE'
                vente.save()
            messages.success(request, f"Article '{vente.article_nom}' récupéré par {vente.client.nom_complet}.")

    return redirect('inventory:detail_vente_credit', boutique_id=boutique_id, vente_id=vente_id)


# ===== ANNULER UNE VENTE =====

@login_required
@commercant_required
def annuler_vente_credit(request, boutique_id, vente_id):
    boutique = _boutique_commercant(request, boutique_id)
    vente    = get_object_or_404(VenteAcompte, id=vente_id, boutique=boutique)

    if request.method == 'POST' and vente.statut == 'EN_COURS':
        vente.statut = 'ANNULE'
        vente.save()
        messages.warning(request, f"Vente {vente.reference} annulée.")

    return redirect('inventory:detail_vente_credit', boutique_id=boutique_id, vente_id=vente_id)


# ===== REÇU DE PAIEMENT (imprimable) =====

@login_required
@commercant_required
def recu_paiement(request, boutique_id, paiement_id):
    boutique  = _boutique_commercant(request, boutique_id)
    paiement  = get_object_or_404(PaiementAcompte, id=paiement_id, vente__boutique=boutique)
    vente     = paiement.vente

    context = {
        'boutique': boutique,
        'paiement': paiement,
        'vente':    vente,
        'client':   vente.client,
    }
    return render(request, 'inventory/credit/recu_paiement.html', context)


# ===== API ANDROID / MAUI =====

def api_credit_creer_vente(request, boutique_id):
    """POST : créer une vente à crédit depuis l'app Android."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    boutique, err = _boutique_from_serial(request, boutique_id)
    if err:
        return err

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Corps JSON invalide'}, status=400)

    # ── Client ──────────────────────────────────────────────────────────
    client_id = body.get('client_id')
    if client_id:
        client = get_object_or_404(ClientAcompte, id=client_id, boutique=boutique)
    else:
        nom = (body.get('nom') or '').strip()
        if not nom:
            return JsonResponse({'error': 'Le nom du client est obligatoire'}, status=400)
        client = ClientAcompte.objects.create(
            boutique=boutique,
            nom=nom,
            prenom=(body.get('prenom') or '').strip(),
            telephone=(body.get('telephone') or '').strip(),
            adresse=(body.get('adresse') or '').strip(),
        )

    # ── Article + montants ───────────────────────────────────────────────
    article_nom = (body.get('article_nom') or '').strip()
    if not article_nom:
        return JsonResponse({'error': "Le nom de l'article est obligatoire"}, status=400)

    try:
        prix_total    = Decimal(str(body.get('prix_total', 0)))
        seuil_retrait = Decimal(str(body.get('seuil_retrait', 0)))
        acompte       = Decimal(str(body.get('acompte_initial', 0) or 0))
    except (InvalidOperation, TypeError, ValueError):
        return JsonResponse({'error': 'Montants invalides'}, status=400)

    if prix_total <= 0:
        return JsonResponse({'error': 'Le prix total doit être positif'}, status=400)
    if seuil_retrait <= 0 or seuil_retrait > prix_total:
        return JsonResponse({'error': 'Seuil de retrait invalide'}, status=400)
    if acompte < 0 or acompte > prix_total:
        return JsonResponse({'error': 'Acompte initial invalide'}, status=400)

    with transaction.atomic():
        vente = VenteAcompte.objects.create(
            boutique=boutique,
            client=client,
            article_nom=article_nom,
            prix_total=prix_total,
            seuil_retrait=seuil_retrait,
            montant_paye=Decimal('0'),
        )
        if acompte > 0:
            PaiementAcompte.objects.create(
                vente=vente, montant=acompte,
                recu_par=request.META.get('HTTP_X_DEVICE_SERIAL', 'MAUI'),
                notes=(body.get('commentaire') or '').strip(),
            )
            vente.montant_paye = acompte
            if vente.montant_paye >= vente.prix_total:
                vente.statut = 'SOLDE'
            vente.save()

    return JsonResponse({
        'success':    True,
        'vente_id':   vente.id,
        'reference':  vente.reference,
        'client_nom': client.nom_complet,
        'statut':     vente.statut,
    }, status=201)


def api_credit_ventes(request, boutique_id):
    """GET : liste des ventes crédit pour l'app Android."""
    boutique, err = _boutique_from_serial(request, boutique_id)
    if err:
        return err
    statut   = request.GET.get('statut', '')

    ventes = VenteAcompte.objects.filter(boutique=boutique).select_related('client')
    if statut:
        ventes = ventes.filter(statut=statut)

    data = [{
        'id':               v.id,
        'reference':        v.reference,
        'client_id':        v.client.id,
        'client_nom':       v.client.nom_complet,
        'client_telephone': v.client.telephone,
        'article_nom':      v.article_nom,
        'prix_total':       float(v.prix_total),
        'seuil_retrait':    float(v.seuil_retrait),
        'montant_paye':     float(v.montant_paye),
        'montant_restant':  float(v.montant_restant),
        'statut':           v.statut,
        'article_recupere': v.article_recupere,
        'peut_recuperer':   v.peut_recuperer,
        'pourcentage_paye': v.pourcentage_paye,
        'date_creation':    v.date_creation.isoformat(),
    } for v in ventes]

    return JsonResponse({'ventes': data, 'count': len(data)})


def api_credit_detail_vente(request, vente_id):
    """GET : détail d'une vente + historique paiements."""
    vente, _, err = _boutique_from_serial_for_vente(request, vente_id)
    if err:
        return err
    paiements = [{
        'id':              p.id,
        'reference_recu':  p.reference_recu,
        'montant':         float(p.montant),
        'date_paiement':   p.date_paiement.isoformat(),
        'recu_par':        p.recu_par,
        'notes':           p.notes,
    } for p in vente.paiements.all()]

    return JsonResponse({
        'id':               vente.id,
        'reference':        vente.reference,
        'client_nom':       vente.client.nom_complet,
        'client_telephone': vente.client.telephone,
        'article_nom':      vente.article_nom,
        'prix_total':       float(vente.prix_total),
        'seuil_retrait':    float(vente.seuil_retrait),
        'montant_paye':     float(vente.montant_paye),
        'montant_restant':  float(vente.montant_restant),
        'statut':           vente.statut,
        'article_recupere': vente.article_recupere,
        'peut_recuperer':   vente.peut_recuperer,
        'pourcentage_paye': vente.pourcentage_paye,
        'paiements':        paiements,
    })


def api_credit_enregistrer_paiement(request, vente_id):
    """POST : enregistrer un acompte depuis Android."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    vente, _, err = _boutique_from_serial_for_vente(request, vente_id)
    if err:
        return err

    try:
        body    = json.loads(request.body)
        montant = Decimal(str(body.get('montant', 0)))
        notes   = body.get('notes', '')
    except (json.JSONDecodeError, InvalidOperation, ValueError):
        return JsonResponse({'error': 'Données invalides'}, status=400)

    if vente.statut != 'EN_COURS':
        return JsonResponse({'error': 'Vente non active'}, status=400)
    if montant <= 0:
        return JsonResponse({'error': 'Montant invalide'}, status=400)
    if vente.montant_paye + montant > vente.prix_total:
        return JsonResponse({'error': f'Dépasse le restant ({float(vente.montant_restant)} FC)'}, status=400)

    with transaction.atomic():
        paiement = PaiementAcompte.objects.create(
            vente=vente, montant=montant,
            recu_par=request.META.get('HTTP_X_DEVICE_SERIAL', 'MAUI'), notes=notes,
        )
        vente.montant_paye += montant
        if vente.montant_paye >= vente.prix_total:
            vente.statut = 'SOLDE'
        vente.save()

    return JsonResponse({
        'success':         True,
        'reference_recu':  paiement.reference_recu,
        'montant_paye':    float(vente.montant_paye),
        'montant_restant': float(vente.montant_restant),
        'statut':          vente.statut,
        'peut_recuperer':  vente.peut_recuperer,
        'pourcentage_paye': vente.pourcentage_paye,
    })


def api_credit_clients(request, boutique_id):
    """GET : liste des clients crédit pour l'app Android."""
    boutique, err = _boutique_from_serial(request, boutique_id)
    if err:
        return err
    clients  = ClientAcompte.objects.filter(boutique=boutique)

    data = [{
        'id':        c.id,
        'nom':       c.nom,
        'prenom':    c.prenom,
        'nom_complet': c.nom_complet,
        'telephone': c.telephone,
        'adresse':   c.adresse,
        'nb_ventes': c.ventes.count(),
        'montant_du': float(sum(v.montant_restant for v in c.ventes.filter(statut='EN_COURS'))),
    } for c in clients]

    return JsonResponse({'clients': data, 'count': len(data)})
