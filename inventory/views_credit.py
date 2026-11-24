from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Q, Count, Value, F, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal, InvalidOperation
import json

from .models import Boutique, Article, ClientAcompte, VenteAcompte, LigneVenteAcompte, PaiementAcompte, Client, MouvementStock
from .decorators import commercant_required
from .websocket_utils import notify_stock_updated


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
    # Remise cumulée par facture → permet d'afficher le prix AVANT remise
    # dans le tableau (prix_total + remise = prix catalogue).
    ventes = ventes.annotate(
        remise_totale=Coalesce(Sum('lignes__remise'), Value(Decimal('0'))),
    ).annotate(
        prix_avant_remise=ExpressionWrapper(
            F('prix_total') + F('remise_totale'),
            output_field=DecimalField(max_digits=15, decimal_places=2),
        ),
    )

    # Liste des clients pour le formulaire de création et la gestion
    clients = ClientAcompte.objects.filter(boutique=boutique).annotate(
        nb_ventes_total=Count('ventes')
    ).order_by('nom')
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

    # Montants — plus de seuil : retrait autorisé uniquement si entièrement payé
    try:
        prix_total   = Decimal(request.POST.get('prix_total', '0') or '0')
    except (InvalidOperation, ValueError):
        messages.error(request, "Montants invalides.")
        return redirect('inventory:liste_ventes_credit', boutique_id=boutique_id)
    seuil_retrait = prix_total

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


# ===== SUPPRIMER UN CLIENT =====

@login_required
@commercant_required
def supprimer_client_credit(request, boutique_id, client_id):
    """Supprime un client crédit sans vente associée (protection de l'historique)."""
    boutique = _boutique_commercant(request, boutique_id)
    client   = get_object_or_404(ClientAcompte, id=client_id, boutique=boutique)

    if request.method != 'POST':
        return redirect('inventory:liste_ventes_credit', boutique_id=boutique_id)

    nom = client.nom_complet
    if client.ventes.exists():
        messages.error(
            request,
            f"Impossible de supprimer {nom} : ce client a des ventes à crédit "
            f"associées. Annulez d'abord ses ventes ou conservez son historique.")
    else:
        client.delete()
        messages.success(request, f"Client {nom} supprimé.")

    return redirect('inventory:liste_ventes_credit', boutique_id=boutique_id)


# ===== DÉTAIL D'UNE VENTE =====

@login_required
@commercant_required
def detail_vente_credit(request, boutique_id, vente_id):
    boutique = _boutique_commercant(request, boutique_id)
    vente    = get_object_or_404(VenteAcompte, id=vente_id, boutique=boutique)
    paiements = vente.paiements.all()
    remise    = remise_totale_vente(vente)

    context = {
        'boutique':  boutique,
        'vente':     vente,
        'paiements': paiements,
        'remise_totale': remise,
        # Prix catalogue (avant remise) : prix payé + remise accordée
        'prix_avant_remise': (vente.prix_total or Decimal('0')) + remise,
        # Correction : tant que l'article n'est pas parti et la vente pas annulée
        'peut_corriger': _motif_non_modifiable(vente) is None,
        # Suppression : rien d'encaissé, rien de remis → la saisie peut être
        # reprise de zéro sans laisser de trace financière orpheline.
        'peut_supprimer': (
            vente.article_recupere is False
            and vente.montant_paye <= 0
            and not vente.paiements.exists()
        ),
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
            messages.error(request, f"Retrait non autorisé : la facture n'est pas encore "
                                     f"entièrement payée ({vente.montant_paye:,.0f} FC sur "
                                     f"{vente.prix_total:,.0f} FC).")
        else:
            with transaction.atomic():
                vente.article_recupere = True
                vente.date_retrait = timezone.now()
                if vente.montant_paye >= vente.prix_total:
                    vente.statut = 'SOLDE'
                vente.save()
            messages.success(request, f"Article '{vente.article_nom}' récupéré par {vente.client.nom_complet}.")

    return redirect('inventory:detail_vente_credit', boutique_id=boutique_id, vente_id=vente_id)


# ===== CORRIGER UNE VENTE (articles, quantités, acomptes) =====

_NB_LIGNES_AJOUT = 5


class _CorrectionRefusee(Exception):
    """Annule la transaction de correction et reporte le message à l'utilisateur.

    Levée À L'INTÉRIEUR du ``transaction.atomic()`` : sans exception, un
    ``return`` committerait les modifications déjà appliquées.
    """


def _motif_non_modifiable(vente):
    """Raison de blocage de la correction, ou ``None`` si la vente est éditable."""
    if vente.statut == 'ANNULE':
        return f"La vente {vente.reference} est annulée : elle n'est plus modifiable."
    if vente.article_recupere:
        return (f"L'article de {vente.reference} a déjà été remis au client : "
                f"la facture n'est plus modifiable.")
    return None


def _lignes_editables(vente):
    """Lignes éditables d'une vente, avec repli sur l'ancien format mono-article.

    L'ancien format (montants portés par la vente elle-même, sans
    ``LigneVenteAcompte``) est restitué comme une ligne virtuelle
    ``id=None`` : elle est matérialisée à l'enregistrement.
    """
    lignes = [{
        'id':            ligne.id,
        'article_id':    ligne.article_id,
        'article_nom':   ligne.article_nom,
        'quantite':      ligne.quantite or 1,
        'prix_unitaire': ligne.prix_unitaire,
        'prix_total':    ligne.prix_total,
        'remise':        ligne.remise or Decimal('0'),
        'prix_avant_remise': ligne.prix_avant_remise,
    } for ligne in vente.lignes.all()]

    if lignes:
        articles = {
            a.id: a for a in Article.objects.filter(
                id__in=[l['article_id'] for l in lignes if l['article_id']])
        }
        for ligne in lignes:
            article = articles.get(ligne['article_id'])
            ligne['stock'] = article.quantite_stock if article else None
            ligne['prix_catalogue'] = article.prix_vente if article else None
        return lignes

    if vente.article_nom or vente.article_id:
        quantite  = vente.quantite or 1
        prix_total = vente.prix_total or Decimal('0')
        article = vente.article
        remise = Decimal('0')
        if article is not None and article.prix_vente:
            catalogue = article.prix_vente * quantite
            if catalogue > prix_total:
                remise = catalogue - prix_total
        return [{
            'id':            None,
            'article_id':    vente.article_id,
            'article_nom':   vente.article_nom,
            'quantite':      quantite,
            'prix_unitaire': (prix_total / quantite) if quantite else prix_total,
            'prix_total':    prix_total,
            'remise':        remise,
            'prix_avant_remise': prix_total + remise,
            'stock':         article.quantite_stock if article else None,
            'prix_catalogue': article.prix_vente if article else None,
        }]
    return []


def _appliquer_delta_stock(article, delta, reference, utilisateur, commentaire):
    """Débite (+delta) ou recrédite (−delta) le stock. Lève si insuffisant.

    Convention MouvementStock : SORTIE = quantité négative, ENTREE = positive,
    donc ``quantite = -delta`` dans les deux cas.
    """
    if delta == 0:
        return None
    stock_avant = int(article.quantite_stock or 0)
    if delta > 0 and stock_avant < delta:
        raise _CorrectionRefusee(
            f"Stock insuffisant pour {article.nom} : {stock_avant} "
            f"disponible(s), {delta} requis.")
    stock_restant = stock_avant - delta
    article.quantite_stock = stock_restant
    article.save(update_fields=['quantite_stock'])
    MouvementStock.objects.create(
        article=article,
        type_mouvement='VENTE' if delta > 0 else 'RETOUR',
        quantite=-delta,
        stock_avant=stock_avant,
        stock_apres=stock_restant,
        reference_document=reference if delta > 0 else f"CORR-CREDIT-{reference}",
        utilisateur=utilisateur,
        commentaire=commentaire,
    )
    return stock_restant


@login_required
@commercant_required
def modifier_vente_credit(request, boutique_id, vente_id):
    """Corrige une vente à crédit saisie en erreur (articles ou acomptes)."""
    boutique = _boutique_commercant(request, boutique_id)
    vente    = get_object_or_404(VenteAcompte, id=vente_id, boutique=boutique)

    if request.method == 'GET':
        remise = remise_totale_vente(vente)
        return render(request, 'inventory/credit/modifier_vente_credit.html', {
            'boutique':      boutique,
            'vente':         vente,
            'lignes':        _lignes_editables(vente),
            'paiements':     list(vente.paiements.all()),
            'articles_dispo': boutique.articles.filter(est_actif=True).order_by('nom'),
            'nb_ajout':      _NB_LIGNES_AJOUT,
            'remise_totale': remise,
            'prix_avant_remise': (vente.prix_total or Decimal('0')) + remise,
            'modifiable':    _motif_non_modifiable(vente),
        })

    motif = _motif_non_modifiable(vente)
    if motif:
        messages.error(request, motif)
        return redirect('inventory:detail_vente_credit',
                        boutique_id=boutique_id, vente_id=vente_id)

    # ── 1. Lecture et validation de la saisie (aucune écriture) ─────────
    lignes_actuelles = _lignes_editables(vente)

    form_quantites = {}   # clé de formulaire -> quantité demandée
    form_suppr     = set()  # clés à supprimer
    for ligne in lignes_actuelles:
        cle = str(ligne['id']) if ligne['id'] else 'legacy'
        if request.POST.get(f'suppr_{cle}') == '1':
            form_suppr.add(cle)
            continue
        brut = (request.POST.get(f'qte_{cle}') or '').strip()
        try:
            qte = int(brut)
        except (TypeError, ValueError):
            messages.error(
                request,
                f"Quantité invalide pour « {ligne['article_nom']} ».")
            return redirect('inventory:detail_vente_credit',
                            boutique_id=boutique_id, vente_id=vente_id)
        if qte < 1:
            messages.error(
                request,
                f"La quantité de « {ligne['article_nom']} » doit être au "
                f"moins 1 (pour retirer un article, cochez « retirer »).")
            return redirect('inventory:detail_vente_credit',
                            boutique_id=boutique_id, vente_id=vente_id)
        form_quantites[cle] = qte

    articles_dispo = {
        a.id: a for a in boutique.articles.filter(est_actif=True)
    }
    ajouts = []
    for article_brut, qte_brut in zip(
            request.POST.getlist('add_article'),
            request.POST.getlist('add_qte')):
        article_brut = (article_brut or '').strip()
        qte_brut     = (qte_brut or '').strip()
        if not article_brut and not qte_brut:
            continue
        if not article_brut or not qte_brut:
            messages.error(request, "Chaque ligne d'ajout doit avoir un article "
                                    "ET une quantité.")
            return redirect('inventory:detail_vente_credit',
                            boutique_id=boutique_id, vente_id=vente_id)
        try:
            article_id = int(article_brut)
            qte        = int(qte_brut)
        except (TypeError, ValueError):
            messages.error(request, "Ajout invalide : article ou quantité.")
            return redirect('inventory:detail_vente_credit',
                            boutique_id=boutique_id, vente_id=vente_id)
        if qte < 1:
            messages.error(request, "La quantité ajoutée doit être au moins 1.")
            return redirect('inventory:detail_vente_credit',
                            boutique_id=boutique_id, vente_id=vente_id)
        article = articles_dispo.get(article_id)
        if article is None:
            messages.error(request, "Article introuvable dans cette boutique.")
            return redirect('inventory:detail_vente_credit',
                            boutique_id=boutique_id, vente_id=vente_id)
        ajouts.append((article, qte))

    maj_paiements = {}   # id paiement -> montant (None = supprimer)
    for paiement in vente.paiements.all():
        if request.POST.get(f'pay_suppr_{paiement.id}') == '1':
            maj_paiements[paiement.id] = None
            continue
        brut = (request.POST.get(f'pay_{paiement.id}') or '').strip()
        if not brut:
            continue
        try:
            montant = Decimal(brut)
        except InvalidOperation:
            messages.error(request, f"Montant invalide pour {paiement.reference_recu}.")
            return redirect('inventory:detail_vente_credit',
                            boutique_id=boutique_id, vente_id=vente_id)
        if montant <= 0:
            messages.error(request, f"Le montant de {paiement.reference_recu} "
                                    f"doit être supérieur à 0.")
            return redirect('inventory:detail_vente_credit',
                            boutique_id=boutique_id, vente_id=vente_id)
        maj_paiements[paiement.id] = montant

    # ── 2. État final visé ──────────────────────────────────────────────
    final = []          # ligne existante (ou None si création), article, qté…
    articles_impliques = set()

    for ligne in lignes_actuelles:
        cle = str(ligne['id']) if ligne['id'] else 'legacy'
        if cle in form_suppr:
            if ligne['article_id']:
                articles_impliques.add(ligne['article_id'])
            continue

        qte        = form_quantites[cle]
        ancienne_q = ligne['quantite']
        # Le prix unitaire NET vendu est la base : changer de quantité ne
        # change pas le prix convenu à l'unité, la remise suit proportionnellement.
        prix_unitaire = ligne['prix_unitaire']
        if qte == ancienne_q:
            prix_total = ligne['prix_total']
            remise     = ligne['remise']
        else:
            prix_total = prix_unitaire * qte
            remise     = (
                (ligne['remise'] * qte / ancienne_q).quantize(Decimal('0.01'))
                if ancienne_q else Decimal('0')
            )
        if ligne['article_id']:
            articles_impliques.add(ligne['article_id'])
        final.append({
            'ligne':        ligne['id'],
            'virtuelle':    ligne['id'] is None,
            'article_id':   ligne['article_id'],
            'article_nom':  ligne['article_nom'],
            'quantite':     qte,
            'ancienne_q':   ancienne_q,
            'prix_unitaire': prix_unitaire,
            'prix_total':   prix_total,
            'remise':       remise,
        })

    for article, qte in ajouts:
        articles_impliques.add(article.id)
        prix_unitaire = article.prix_vente or Decimal('0')
        final.append({
            'ligne':        None,
            'virtuelle':    False,
            'article_id':   article.id,
            'article_nom':  article.nom,
            'quantite':     qte,
            'ancienne_q':   0,
            'prix_unitaire': prix_unitaire,
            'prix_total':   prix_unitaire * qte,
            'remise':       Decimal('0'),
        })

    nouveau_total    = sum((f['prix_total'] for f in final), Decimal('0'))
    nouvelle_qte_tot = sum(f['quantite'] for f in final)

    if not final:
        messages.error(
            request,
            "La vente doit conserver au moins un article : utilisez "
            "« Annuler » pour la supprimer entièrement.")
        return redirect('inventory:detail_vente_credit',
                        boutique_id=boutique_id, vente_id=vente_id)
    if nouveau_total <= 0:
        messages.error(request, "Le nouveau prix total doit être supérieur à 0.")
        return redirect('inventory:detail_vente_credit',
                        boutique_id=boutique_id, vente_id=vente_id)

    # ── 3. Application atomique ─────────────────────────────────────────
    retours_stock = []      # (article_id, nom, stock_restant) à notifier
    reference = vente.reference
    utilisateur = request.user.get_full_name() or request.user.username

    try:
        with transaction.atomic():
            vente = VenteAcompte.objects.select_for_update().get(
                id=vente_id, boutique=boutique)
            blocage = _motif_non_modifiable(vente)
            if blocage:
                raise _CorrectionRefusee(blocage)

            # Verrous articles par id croissant : même ordre partout ailleurs
            # → pas de deadlock avec les autres vues de stock.
            verrous = {
                a.id: a for a in Article.objects.select_for_update()
                .filter(id__in=articles_impliques).order_by('id')
            }

            # Ligne virtuelle (ancien format sans LigneVenteAcompte) :
            # matérialisée pour uniformiser le reste du traitement.
            virtuelle = next((f for f in final if f['virtuelle']), None)
            if virtuelle is not None:
                mat = LigneVenteAcompte.objects.create(
                    vente=vente,
                    article_id=virtuelle['article_id'],
                    article_nom=virtuelle['article_nom'],
                    quantite=virtuelle['quantite'],
                    prix_unitaire=virtuelle['prix_unitaire'],
                    prix_total=virtuelle['prix_total'],
                    remise=virtuelle['remise'],
                )
                virtuelle['ligne'] = mat.id

            # a) Ajustements de quantité + suppressions de lignes
            for f in final:
                if f['ligne'] is None:
                    continue
                delta = f['quantite'] - f['ancienne_q']
                if delta == 0:
                    continue
                article = verrous.get(f['article_id'])
                if article is None:
                    continue
                reste = _appliquer_delta_stock(
                    article, delta, reference, utilisateur,
                    commentaire=(f"Correction vente à crédit {reference} — "
                                 f"{article.nom} : {f['ancienne_q']} → "
                                 f"{f['quantite']} unité(s)"),
                )
                if reste is not None:
                    retours_stock.append((article.id, article.nom, reste))

            # b) Nouvelles lignes (ajouts)
            for f in final:
                if f['ligne'] is not None:
                    continue
                article = verrous.get(f['article_id'])
                if article is None:
                    continue
                reste = _appliquer_delta_stock(
                    article, f['quantite'], reference, utilisateur,
                    commentaire=(f"Correction vente à crédit {reference} — "
                                 f"ajout de {f['quantite']} × {article.nom}"),
                )
                if reste is not None:
                    retours_stock.append((article.id, article.nom, reste))

            # c) Écriture des lignes
            existantes = {l.id: l for l in vente.lignes.all()}
            for f in final:
                if f['ligne'] is None:
                    LigneVenteAcompte.objects.create(
                        vente=vente,
                        article_id=f['article_id'],
                        article_nom=f['article_nom'],
                        quantite=f['quantite'],
                        prix_unitaire=f['prix_unitaire'],
                        prix_total=f['prix_total'],
                        remise=f['remise'],
                    )
                else:
                    ligne = existantes.get(f['ligne'])
                    if ligne is None:
                        continue
                    ligne.quantite     = f['quantite']
                    ligne.prix_total   = f['prix_total']
                    ligne.remise       = f['remise']
                    ligne.prix_unitaire = f['prix_unitaire']
                    ligne.save(update_fields=[
                        'quantite', 'prix_total', 'remise', 'prix_unitaire',
                    ])

            # d) Lignes retirées
            ids_retenus = {f['ligne'] for f in final if f['ligne'] is not None}
            for ligne_id, ligne in existantes.items():
                if ligne_id in ids_retenus:
                    continue
                if ligne.article_id:
                    article = verrous.get(ligne.article_id)
                    if article is not None:
                        reste = _appliquer_delta_stock(
                            article, -(ligne.quantite or 1), reference,
                            utilisateur,
                            commentaire=(f"Correction vente à crédit {reference} — "
                                         f"retrait de {ligne.article_nom}"),
                        )
                        if reste is not None:
                            retours_stock.append((article.id, article.nom, reste))
                ligne.delete()

            # e) Acomptes
            for paiement in vente.paiements.all():
                if paiement.id not in maj_paiements:
                    continue
                montant = maj_paiements[paiement.id]
                if montant is None:
                    paiement.delete()
                else:
                    paiement.montant = montant
                    paiement.save(update_fields=['montant'])

            # f) Recalcul de l'en-tête de facture
            lignes_fin = list(vente.lignes.all())
            total      = sum((l.prix_total for l in lignes_fin), Decimal('0'))
            quantite   = sum(int(l.quantite or 0) for l in lignes_fin)
            paye       = sum((p.montant for p in vente.paiements.all()),
                             Decimal('0'))

            if paye > total:
                raise _CorrectionRefusee(
                    f"Le nouveau total ({total:,.0f} FC) est inférieur aux "
                    f"acomptes déjà encaissés ({paye:,.0f} FC). Corrigez "
                    f"d’abord les acomptes."
                )

            if len(lignes_fin) == 1:
                vente.article     = lignes_fin[0].article
                vente.article_nom = lignes_fin[0].article_nom[:200]
            else:
                vente.article     = None
                vente.article_nom = ', '.join(
                    l.article_nom for l in lignes_fin)[:200]

            vente.prix_total     = total
            vente.seuil_retrait  = total
            vente.quantite       = quantite
            vente.montant_paye   = paye
            if paye >= total:
                vente.statut = 'SOLDE'
            else:
                vente.statut = 'EN_COURS'
            vente.save()

    except _CorrectionRefusee as exc:
        messages.error(request, str(exc))
        return redirect('inventory:detail_vente_credit',
                        boutique_id=boutique_id, vente_id=vente_id)

    for article_id, article_nom, stock_restant in retours_stock:
        notify_stock_updated(boutique.id, article_id, stock_restant,
                             article_nom=article_nom)

    messages.success(
        request,
        f"Vente {reference} corrigée : {nouvelle_qte_tot} article(s) pour "
        f"{nouveau_total:,.0f} FC.")
    return redirect('inventory:detail_vente_credit',
                    boutique_id=boutique_id, vente_id=vente_id)


# ===== RETOUR DE STOCK D'UNE VENTE (partagé : annulation / suppression) =====

def _retourner_stock_vente(vente, utilisateur, motif, reference_doc=None):
    """Remet en stock les articles d'une vente à crédit.

    Utilisé par l'annulation ET la suppression : les deux doivent rendre
    exactement ce qui avait été débité à la création. Renvoie la liste des
    ``(article_id, article_nom, stock_restant)`` à pousser en WebSocket.
    """
    reference_doc = reference_doc or f"ANNUL-CREDIT-{vente.reference}"

    lignes = list(vente.lignes.all())
    if lignes:
        cibles = [
            (ligne.article_id, int(ligne.quantite or 1))
            for ligne in lignes if ligne.article_id
        ]
    elif vente.article_id:
        # Anciennes ventes mono-article (créées avant les lignes)
        cibles = [(vente.article_id, int(vente.quantite or 1))]
    else:
        cibles = []

    retours = []
    for article_id, quantite in cibles:
        article = Article.objects.select_for_update().filter(id=article_id).first()
        if article is None:
            continue
        stock_avant = int(article.quantite_stock or 0)
        stock_restant = stock_avant + quantite
        article.quantite_stock = stock_restant
        article.save(update_fields=['quantite_stock'])
        MouvementStock.objects.create(
            article=article,
            type_mouvement='RETOUR',
            quantite=quantite,
            stock_avant=stock_avant,
            stock_apres=stock_restant,
            reference_document=reference_doc,
            utilisateur=utilisateur,
            commentaire=motif,
        )
        retours.append((article.id, article.nom, stock_restant))
    return retours


# ===== ANNULER UNE VENTE =====

@login_required
@commercant_required
def annuler_vente_credit(request, boutique_id, vente_id):
    boutique = _boutique_commercant(request, boutique_id)
    vente    = get_object_or_404(VenteAcompte, id=vente_id, boutique=boutique)

    if request.method == 'POST' and vente.statut == 'EN_COURS':
        with transaction.atomic():
            retours = _retourner_stock_vente(
                vente,
                utilisateur=request.user.get_full_name() or request.user.username,
                motif=(f"Annulation vente à crédit {vente.reference} — "
                       f"retour des articles en stock"),
            )
            vente.statut = 'ANNULE'
            vente.save()

        for article_id, article_nom, stock_restant in retours:
            notify_stock_updated(boutique.id, article_id, stock_restant,
                                 article_nom=article_nom)
        if retours:
            messages.warning(
                request,
                f"Vente {vente.reference} annulée — stock remis à jour pour "
                f"{len(retours)} article(s).")
        else:
            messages.warning(request, f"Vente {vente.reference} annulée.")

    return redirect('inventory:detail_vente_credit', boutique_id=boutique_id, vente_id=vente_id)


# ===== SUPPRIMER UNE VENTE (erreur de saisie côté MAUI) =====

@login_required
@commercant_required
def supprimer_vente_credit(request, boutique_id, vente_id):
    """Supprime définitivement une vente à crédit.

    Réservé aux ventes sans encaissement et sans remise d'article : c'est la
    voie de sortie pour une saisie erronée côté MAUI (mauvais article, mauvais
    montant) quand rien n'a encore été payé. Le stock débité est rendu.
    """
    boutique = _boutique_commercant(request, boutique_id)
    vente    = get_object_or_404(VenteAcompte, id=vente_id, boutique=boutique)

    if request.method != 'POST':
        return redirect('inventory:detail_vente_credit', boutique_id=boutique_id, vente_id=vente_id)

    if vente.article_recupere:
        messages.error(
            request,
            f"Suppression impossible : l'article de {vente.reference} a déjà "
            f"été remis au client. Annulez la vente pour tracer le retour.")
        return redirect('inventory:detail_vente_credit', boutique_id=boutique_id, vente_id=vente_id)

    if vente.montant_paye > 0 or vente.paiements.exists():
        messages.error(
            request,
            f"Suppression impossible : {vente.reference} porte des encaissements "
            f"({vente.montant_paye:,.0f} FC). Corrigez d'abord les acomptes "
            f"ou annulez la vente pour conserver la trace financière.")
        return redirect('inventory:detail_vente_credit', boutique_id=boutique_id, vente_id=vente_id)

    reference = vente.reference
    client_nom = vente.client.nom_complet
    deja_annulee = vente.statut == 'ANNULE'

    retours = []
    with transaction.atomic():
        # Une vente déjà annulée a DÉJÀ rendu son stock : ne pas le rendre 2×.
        if not deja_annulee:
            retours = _retourner_stock_vente(
                vente,
                utilisateur=request.user.get_full_name() or request.user.username,
                motif=(f"Suppression vente à crédit {reference} — "
                       f"retour des articles en stock"),
            )
        vente.delete()

    for article_id, article_nom, stock_restant in retours:
        notify_stock_updated(boutique.id, article_id, stock_restant,
                             article_nom=article_nom)

    if retours:
        messages.success(
            request,
            f"Vente {reference} supprimée — {len(retours)} article(s) remis "
            f"en stock pour {client_nom}.")
    else:
        messages.success(request, f"Vente {reference} supprimée ({client_nom}).")

    return redirect('inventory:liste_ventes_credit', boutique_id=boutique_id)


# ===== REÇU DE PAIEMENT (imprimable) =====

@login_required
@commercant_required
def recu_paiement(request, boutique_id, paiement_id):
    boutique  = _boutique_commercant(request, boutique_id)
    paiement  = get_object_or_404(PaiementAcompte, id=paiement_id, vente__boutique=boutique)
    vente     = paiement.vente
    remise    = remise_totale_vente(vente)

    context = {
        'boutique': boutique,
        'paiement': paiement,
        'vente':    vente,
        'client':   vente.client,
        'remise_totale': remise,
        'prix_avant_remise': (vente.prix_total or Decimal('0')) + remise,
    }
    return render(request, 'inventory/credit/recu_paiement.html', context)


# ===== API ANDROID / MAUI =====

@csrf_exempt
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
    # Un client déjà enregistré doit être réutilisé : sa nouvelle dette
    # s'ajoute ainsi à son compte au lieu de créer un doublon.
    client_id = body.get('client_id')
    if client_id:
        client = get_object_or_404(ClientAcompte, id=client_id, boutique=boutique)
    else:
        nom       = (body.get('nom') or '').strip()
        prenom    = (body.get('prenom') or '').strip()
        telephone = (body.get('telephone') or '').strip()
        adresse   = (body.get('adresse') or '').strip()
        if not nom:
            return JsonResponse({'error': 'Le nom du client est obligatoire'}, status=400)

        client = None
        if telephone:
            client = ClientAcompte.objects.filter(
                boutique=boutique, telephone=telephone).first()
        if client is None:
            candidats = ClientAcompte.objects.filter(
                boutique=boutique, nom__iexact=nom, prenom__iexact=prenom)
            if candidats.count() == 1:
                client = candidats.first()
        if client is None:
            client = ClientAcompte.objects.create(
                boutique=boutique,
                nom=nom,
                prenom=prenom,
                telephone=telephone,
                adresse=adresse,
            )

    # ── Lignes d'articles ───────────────────────────────────────────────
    lignes_brutes = body.get('articles') or body.get('lignes')
    if not lignes_brutes:
        # Compatibilité avec l'ancien format mono-article
        lignes_brutes = [{
            'article_id':  body.get('article_id'),
            'article_nom': body.get('article_nom'),
            'quantite':    body.get('quantite', 1),
            'prix_total':  body.get('prix_total', 0),
        }]
    if not isinstance(lignes_brutes, list) or not lignes_brutes:
        return JsonResponse({'error': "Au moins un article est obligatoire"}, status=400)

    lignes_normalisees = {}
    ordre = []
    for brute in lignes_brutes:
        if not isinstance(brute, dict):
            return JsonResponse({'error': 'Article invalide'}, status=400)

        article_nom = (brute.get('article_nom') or '').strip()
        article_id = brute.get('article_id')
        try:
            quantite = int(brute.get('quantite', 1) or 1)
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Quantité invalide'}, status=400)
        if quantite < 1:
            return JsonResponse({'error': 'La quantité doit être au moins 1'}, status=400)

        # Article du catalogue (optionnel) : prix plafonné au catalogue,
        # une remise est possible mais jamais de surcharge (voir plus bas)
        article = None
        if article_id:
            try:
                article = Article.objects.get(
                    id=article_id, boutique=boutique,
                    est_actif=True, est_valide_client=True, date_suppression__isnull=True,
                )
            except Article.DoesNotExist:
                return JsonResponse(
                    {'error': f"Article du catalogue introuvable (id {article_id})"},
                    status=404)
            article_nom = article.nom
        elif not article_nom:
            return JsonResponse(
                {'error': "Le nom de l'article est obligatoire"}, status=400)

        try:
            prix_total_ligne = Decimal(str(brute.get('prix_total', 0) or 0))
        except (InvalidOperation, TypeError, ValueError):
            return JsonResponse({'error': 'Montants invalides'}, status=400)

        # Fusionne les doublons du même article
        cle = f"id:{article.id}" if article is not None else f"nom:{article_nom.lower()}"
        if cle in lignes_normalisees:
            lignes_normalisees[cle]['quantite'] += quantite
            lignes_normalisees[cle]['prix_total'] += prix_total_ligne
            continue

        lignes_normalisees[cle] = {
            'article': article,
            'article_nom': article_nom,
            'quantite': quantite,
            'prix_total': prix_total_ligne,
        }
        ordre.append(cle)

    # Prix catalogue : le prix vendu ne peut jamais DÉPASSER le catalogue
    # (surcharge interdite), mais il peut être inférieur → c'est une remise.
    for cle in ordre:
        ligne = lignes_normalisees[cle]
        article = ligne['article']
        if article is not None:
            prix_unitaire = article.prix_vente or Decimal('0')
            prix_catalogue = prix_unitaire * ligne['quantite']
            if ligne['prix_total'] <= 0:
                return JsonResponse(
                    {'error': f"Le prix total de {article.nom} doit être positif"},
                    status=400)
            # ecart > 0 : le prix vendu est INFÉRIEUR au catalogue → remise.
            # ecart < 0 : surcharge → refusée. |ecart| <= 0,5 : simple écart
            # d'arrondi, on force le prix catalogue exact (ancien comportement).
            ecart = prix_catalogue - ligne['prix_total']
            if ecart < Decimal('-0.5'):
                return JsonResponse(
                    {'error': f"Prix total incorrect pour {article.nom} : le prix "
                               f"catalogue est de {prix_catalogue:.0f} pour "
                               f"{ligne['quantite']} × {article.nom} "
                               f"(remise possible, surcharge interdite)."},
                    status=400)
            if ecart <= Decimal('0.5'):
                ligne['prix_total'] = prix_catalogue
                ligne['remise'] = Decimal('0')
                ligne['prix_unitaire'] = prix_unitaire
            else:
                ligne['remise'] = ecart
                ligne['prix_unitaire'] = ligne['prix_total'] / ligne['quantite']
        else:
            if ligne['prix_total'] <= 0:
                return JsonResponse(
                    {'error': f"Le prix total de {ligne['article_nom']} doit être positif"},
                    status=400)
            ligne['remise'] = Decimal('0')
            ligne['prix_unitaire'] = ligne['prix_total'] / ligne['quantite']

    prix_total = sum(
        (ligne['prix_total'] for ligne in lignes_normalisees.values()),
        Decimal('0'),
    )
    if prix_total <= 0:
        return JsonResponse({'error': 'Le prix total doit être positif'}, status=400)

    try:
        acompte = Decimal(str(body.get('acompte_initial', 0) or 0))
    except (InvalidOperation, TypeError, ValueError):
        return JsonResponse({'error': 'Montants invalides'}, status=400)

    # Plus de seuil de retrait : le retrait est autorisé uniquement quand la
    # facture est entièrement payée (seuil = prix total, champ historique).
    seuil_retrait = prix_total

    if acompte < 0 or acompte > prix_total:
        return JsonResponse({'error': 'Acompte initial invalide'}, status=400)

    article_nom_resume = ', '.join(
        ligne['article_nom'] for ligne in lignes_normalisees.values()
    )[:200]
    quantite_totale = sum(
        ligne['quantite'] for ligne in lignes_normalisees.values()
    )
    premier_article = next(
        (ligne['article'] for ligne in lignes_normalisees.values()
         if ligne['article'] is not None),
        None,
    )

    lignes_reponse = []
    articles_a_notifier = []

    commentaire = (body.get('commentaire') or '').strip()

    with transaction.atomic():
        # ── Compte crédit du client ─────────────────────────────────────
        # Une seule facture ouverte par client : si elle existe, les
        # nouveaux articles et l'acompte s'y ajoutent (la dette augmente).
        vente = (
            VenteAcompte.objects.select_for_update()
            .filter(boutique=boutique, client=client, statut='EN_COURS')
            .order_by('-date_creation')
            .first()
        )
        fusionnee = vente is not None
        avait_lignes = fusionnee and vente.lignes.exists()

        # ── Stock : contrôle + décrément immédiat à la création ─────────
        articles_verrouilles = {}
        for ligne in lignes_normalisees.values():
            article = ligne['article']
            if article is None:
                continue
            if article.id not in articles_verrouilles:
                article = Article.objects.select_for_update().get(id=article.id)
                articles_verrouilles[article.id] = {
                    'article': article,
                    'stock_avant': int(article.quantite_stock or 0),
                    'quantite_demandee': 0,
                }
            info = articles_verrouilles[article.id]
            info['quantite_demandee'] += ligne['quantite']
            if info['stock_avant'] < info['quantite_demandee']:
                return JsonResponse(
                    {'error': f"Stock insuffisant pour {article.nom} : "
                              f"{info['stock_avant']} disponible(s), "
                              f"{info['quantite_demandee']} demandé(s)."},
                    status=400)

        if vente is None:
            vente = VenteAcompte.objects.create(
                boutique=boutique,
                client=client,
                article=premier_article if len(lignes_normalisees) == 1 else None,
                article_nom=article_nom_resume,
                quantite=quantite_totale,
                prix_total=prix_total,
                seuil_retrait=seuil_retrait,
                montant_paye=Decimal('0'),
                commentaire=commentaire,
            )
        else:
            vente.prix_total += prix_total
            vente.seuil_retrait = vente.prix_total
            vente.quantite = (vente.quantite or 0) + quantite_totale
            noms = [n for n in (vente.article_nom, article_nom_resume) if n]
            vente.article_nom = ', '.join(noms)[:200]
            if commentaire:
                vente.commentaire = (
                    f"{vente.commentaire}\n{commentaire}".strip()
                    if vente.commentaire else commentaire
                )
            vente.article_recupere = False
            vente.save()

        for cle in ordre:
            ligne = lignes_normalisees[cle]
            existante = None
            if avait_lignes:
                if ligne['article'] is not None:
                    existante = vente.lignes.filter(article=ligne['article']).first()
                else:
                    existante = vente.lignes.filter(
                        article__isnull=True,
                        article_nom=ligne['article_nom'],
                    ).first()

            if existante is not None:
                existante.quantite += ligne['quantite']
                existante.prix_total += ligne['prix_total']
                existante.remise += ligne.get('remise') or Decimal('0')
                existante.prix_unitaire = (
                    existante.prix_total / existante.quantite
                    if existante.quantite else ligne['prix_unitaire']
                )
                existante.save(update_fields=[
                    'quantite', 'prix_total', 'prix_unitaire', 'remise',
                ])
            else:
                LigneVenteAcompte.objects.create(
                    vente=vente,
                    article=ligne['article'],
                    article_nom=ligne['article_nom'],
                    quantite=ligne['quantite'],
                    prix_unitaire=ligne['prix_unitaire'],
                    prix_total=ligne['prix_total'],
                    remise=ligne.get('remise') or Decimal('0'),
                )

        if fusionnee and avait_lignes:
            toutes_lignes = list(vente.lignes.order_by('id'))
            if len(toutes_lignes) == 1:
                vente.article = toutes_lignes[0].article
                vente.article_nom = toutes_lignes[0].article_nom[:200]
            else:
                vente.article = None
                vente.article_nom = ', '.join(
                    ligne.article_nom for ligne in toutes_lignes
                )[:200]
            vente.save(update_fields=['article', 'article_nom'])
        elif fusionnee:
            # Ancienne facture mono-article sans lignes : on conserve
            # l'article d'origine et on ajoute le nom des nouveaux.
            vente.article = None
            vente.save(update_fields=['article'])

        if acompte > 0:
            PaiementAcompte.objects.create(
                vente=vente, montant=acompte,
                recu_par=request.META.get('HTTP_X_DEVICE_SERIAL', 'MAUI'),
                notes=commentaire,
            )
            vente.montant_paye += acompte
            if vente.montant_paye >= vente.prix_total:
                vente.statut = 'SOLDE'
            vente.save()

        for cle in ordre:
            ligne = lignes_normalisees[cle]
            article = ligne['article']
            if article is None:
                lignes_reponse.append({
                    'article_id':    None,
                    'article_nom':   ligne['article_nom'],
                    'quantite':      ligne['quantite'],
                    'prix_unitaire': float(ligne['prix_unitaire']),
                    'prix_total':    float(ligne['prix_total']),
                    'stock_avant':   None,
                    'stock_restant': None,
                })
                continue

            info = articles_verrouilles[article.id]
            article_obj = info['article']
            stock_avant = info['stock_avant']
            stock_restant = stock_avant - ligne['quantite']
            article_obj.quantite_stock = stock_restant
            article_obj.save(update_fields=['quantite_stock'])
            MouvementStock.objects.create(
                article=article_obj,
                type_mouvement='VENTE',
                quantite=-ligne['quantite'],
                stock_avant=stock_avant,
                stock_apres=stock_restant,
                reference_document=vente.reference,
                utilisateur=request.META.get('HTTP_X_DEVICE_SERIAL', 'MAUI'),
                commentaire=(f"Vente à crédit {vente.reference} — "
                             f"{ligne['quantite']} × {article_obj.nom}"),
            )
            articles_a_notifier.append(
                (article_obj.id, article_obj.nom, stock_restant)
            )
            lignes_reponse.append({
                'article_id':    article_obj.id,
                'article_nom':   article_obj.nom,
                'quantite':      ligne['quantite'],
                'prix_unitaire': float(ligne['prix_unitaire']),
                'prix_total':    float(ligne['prix_total']),
                'stock_avant':   stock_avant,
                'stock_restant': stock_restant,
            })

    # Après commit : pousser le nouveau stock à tous les terminaux (WebSocket)
    for article_id, article_nom, stock_restant in articles_a_notifier:
        notify_stock_updated(boutique.id, article_id, stock_restant,
                             article_nom=article_nom)

    premiere = lignes_reponse[0] if lignes_reponse else {}
    return JsonResponse({
        'success':          True,
        'fusionnee':        fusionnee,
        'vente_id':         vente.id,
        'reference':        vente.reference,
        'client_id':        client.id,
        'client_nom':       client.nom_complet,
        'statut':           vente.statut,
        'quantite':         vente.quantite,
        'prix_total':       float(vente.prix_total),
        'montant_paye':     float(vente.montant_paye),
        'montant_restant':  float(vente.montant_restant),
        'lignes':           lignes_reponse,
        'stock_avant':      premiere.get('stock_avant'),
        'stock_restant':    premiere.get('stock_restant'),
    }, status=201)


def _lignes_vente_credit_json(vente):
    """Lignes d'une vente à crédit, avec repli sur l'ancien format mono-article."""
    lignes = list(vente.lignes.all())
    if lignes:
        return [{
            'id':            ligne.id,
            'article_id':    ligne.article_id,
            'article_nom':   ligne.article_nom,
            'quantite':      ligne.quantite,
            'prix_unitaire': float(ligne.prix_unitaire),
            'prix_total':    float(ligne.prix_total),
            'remise':        float(ligne.remise or 0),
        } for ligne in lignes]

    quantite = vente.quantite or 1
    prix_total = vente.prix_total or Decimal('0')
    prix_unitaire = (prix_total / quantite) if quantite else prix_total
    return [{
        'id':            None,
        'article_id':    vente.article_id,
        'article_nom':   vente.article_nom,
        'quantite':      quantite,
        'prix_unitaire': float(prix_unitaire),
        'prix_total':    float(prix_total),
        'remise':        0,
    }]


def remise_totale_vente(vente):
    """Remise totale accordée sur une vente (somme des remises de lignes)."""
    return sum(
        (ligne.remise or Decimal('0') for ligne in vente.lignes.all()),
        Decimal('0'),
    )


def api_credit_ventes(request, boutique_id):
    """GET : liste des ventes crédit pour l'app Android."""
    boutique, err = _boutique_from_serial(request, boutique_id)
    if err:
        return err
    statut   = request.GET.get('statut', '')

    ventes = VenteAcompte.objects.filter(
        boutique=boutique
    ).select_related('client').prefetch_related('lignes')
    if statut:
        ventes = ventes.filter(statut=statut)

    data = [{
        'id':               v.id,
        'reference':        v.reference,
        'client_id':        v.client.id,
        'client_nom':       v.client.nom_complet,
        'client_telephone': v.client.telephone,
        'article_nom':      v.article_nom,
        'quantite':         v.quantite,
        'prix_total':       float(v.prix_total),
        'seuil_retrait':    float(v.seuil_retrait),
        'montant_paye':     float(v.montant_paye),
        'montant_restant':  float(v.montant_restant),
        'statut':           v.statut,
        'article_recupere': v.article_recupere,
        'peut_recuperer':   v.peut_recuperer,
        'pourcentage_paye': v.pourcentage_paye,
        'date_creation':    v.date_creation.isoformat(),
        'remise':           float(remise_totale_vente(v)),
        'lignes':           _lignes_vente_credit_json(v),
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
        'quantite':         vente.quantite,
        'prix_total':       float(vente.prix_total),
        'seuil_retrait':    float(vente.seuil_retrait),
        'montant_paye':     float(vente.montant_paye),
        'montant_restant':  float(vente.montant_restant),
        'statut':           vente.statut,
        'article_recupere': vente.article_recupere,
        'peut_recuperer':   vente.peut_recuperer,
        'pourcentage_paye': vente.pourcentage_paye,
        'remise':           float(remise_totale_vente(vente)),
        'paiements':        paiements,
        'lignes':           _lignes_vente_credit_json(vente),
    })


@csrf_exempt
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


# ===== RÉDUCTION DE PRIX SUR UN ARTICLE D'UNE VENTE À CRÉDIT =====

@csrf_exempt
def api_credit_reduire_ligne(request, vente_id, ligne_id):
    """POST : accorde une réduction sur un article d'une vente à crédit.

    Payload (l'un des trois) :
        {"montant": 5000}     → remise totale de 5 000 FC sur la ligne
        {"pourcentage": 10}   → remise totale de 10 % du prix catalogue
        {"reset": true}       → remise effacée (prix catalogue plein)

    La valeur saisie est la remise TOTALE visée (et non un cumul) : saisir
    10 % deux fois donne toujours 10 %, ce qui évite les remises
    « qui s'empilent » sans que le commerçant s'en rende compte.
    Jamais de surcharge : le prix final reste ≤ prix catalogue, et il ne
    peut pas descendre sous les acomptes déjà encaissés.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    vente, _, err = _boutique_from_serial_for_vente(request, vente_id)
    if err:
        return err

    ligne = get_object_or_404(LigneVenteAcompte, id=ligne_id, vente=vente)

    if vente.statut != 'EN_COURS':
        return JsonResponse(
            {'error': 'Vente non active : la réduction n\'est plus possible.'},
            status=400)
    if vente.article_recupere:
        return JsonResponse(
            {'error': 'Article déjà remis au client : facture non modifiable.'},
            status=400)

    try:
        body = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Corps JSON invalide'}, status=400)

    # ── Prix catalogue de la ligne (le plafond) ─────────────────────────
    quantite = int(ligne.quantite or 1)
    article  = ligne.article
    if article is not None and article.prix_vente:
        prix_catalogue = article.prix_vente * quantite
    else:
        # Ligne sans article au catalogue (ancien format) : le plafond est
        # le prix déjà vendu, on ne peut donc que réduire.
        prix_catalogue = (ligne.prix_total or Decimal('0')) + (ligne.remise or Decimal('0'))

    # ── Remise demandée ─────────────────────────────────────────────────
    if body.get('reset') is True:
        remise = Decimal('0')
    elif body.get('pourcentage') is not None:
        try:
            pourcentage = Decimal(str(body['pourcentage']))
        except (InvalidOperation, ValueError, TypeError):
            return JsonResponse({'error': 'Pourcentage invalide.'}, status=400)
        if not (Decimal('0') <= pourcentage < Decimal('100')):
            return JsonResponse(
                {'error': 'Le pourcentage doit être compris entre 0 et 100 (exclus).'},
                status=400)
        remise = (prix_catalogue * pourcentage / Decimal('100')).quantize(Decimal('0.01'))
    elif body.get('montant') is not None:
        try:
            remise = Decimal(str(body['montant']))
        except (InvalidOperation, ValueError, TypeError):
            return JsonResponse({'error': 'Montant invalide.'}, status=400)
        if remise < 0:
            return JsonResponse(
                {'error': 'La remise ne peut pas être négative.'}, status=400)
    else:
        return JsonResponse(
            {'error': 'Indiquez « montant » (FC) ou « pourcentage » (%).'},
            status=400)

    if remise > prix_catalogue:
        return JsonResponse(
            {'error': f"Remise trop élevée : le prix catalogue de cet article "
                      f"est de {prix_catalogue:.0f} FC pour {quantite} × "
                      f"{ligne.article_nom}."},
            status=400)

    nouveau_prix = prix_catalogue - remise
    if nouveau_prix <= 0:
        return JsonResponse(
            {'error': 'Le prix après réduction doit être supérieur à 0.'},
            status=400)
    if nouveau_prix < vente.montant_paye:
        return JsonResponse(
            {'error': f"Prix après réduction ({nouveau_prix:.0f} FC) inférieur "
                      f"aux acomptes déjà versés ({vente.montant_paye:.0f} FC)."},
            status=400)

    # ── Application atomique ────────────────────────────────────────────
    with transaction.atomic():
        ligne = LigneVenteAcompte.objects.select_for_update().get(id=ligne_id)
        ligne.prix_total   = nouveau_prix
        ligne.remise       = remise
        ligne.prix_unitaire = nouveau_prix / quantite
        ligne.save(update_fields=['prix_total', 'remise', 'prix_unitaire'])

        total = sum(
            (l.prix_total for l in vente.lignes.all()), Decimal('0'))
        vente.prix_total    = total
        vente.seuil_retrait = total
        if vente.montant_paye >= total:
            vente.statut = 'SOLDE'
        vente.save()

    return JsonResponse({
        'success':          True,
        'ligne':            {
            'id':            ligne.id,
            'article_nom':   ligne.article_nom,
            'quantite':      ligne.quantite,
            'prix_unitaire': float(ligne.prix_unitaire),
            'prix_total':    float(ligne.prix_total),
            'remise':        float(ligne.remise),
        },
        'remise':           float(remise_totale_vente(vente)),
        'prix_total':       float(vente.prix_total),
        'seuil_retrait':    float(vente.seuil_retrait),
        'montant_paye':     float(vente.montant_paye),
        'montant_restant':  float(vente.montant_restant),
        'statut':           vente.statut,
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


def api_credit_paiements_jour(request, boutique_id):
    """GET : paiements crédit encaissés aujourd'hui pour le dashboard MAUI."""
    boutique, err = _boutique_from_serial(request, boutique_id)
    if err:
        return err

    today = timezone.localdate()
    paiements = PaiementAcompte.objects.filter(
        date_paiement__date=today,
        vente__boutique=boutique,
    ).select_related('vente', 'vente__client')

    data = [{
        'id':            p.id,
        'reference':     p.reference_recu,
        'montant':       float(p.montant),
        'date_paiement': p.date_paiement.isoformat(),
        'vente_id':      p.vente_id,
        'vente_ref':     p.vente.reference,
        'client_nom':    p.vente.client.nom_complet,
    } for p in paiements]

    total = sum(p['montant'] for p in data)
    return JsonResponse({'paiements': data, 'total': total, 'count': len(data)})
