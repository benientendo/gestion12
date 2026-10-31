from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Q
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


# ===== ANNULER UNE VENTE =====

@login_required
@commercant_required
def annuler_vente_credit(request, boutique_id, vente_id):
    boutique = _boutique_commercant(request, boutique_id)
    vente    = get_object_or_404(VenteAcompte, id=vente_id, boutique=boutique)

    if request.method == 'POST' and vente.statut == 'EN_COURS':
        retours = []
        with transaction.atomic():
            # Retour du stock décrémenté à la création de la vente
            lignes = list(vente.lignes.all())
            if lignes:
                for ligne in lignes:
                    if not ligne.article_id:
                        continue
                    article = Article.objects.select_for_update().filter(
                        id=ligne.article_id).first()
                    if article is None:
                        continue
                    stock_avant = int(article.quantite_stock or 0)
                    quantite = int(ligne.quantite or 1)
                    stock_restant = stock_avant + quantite
                    article.quantite_stock = stock_restant
                    article.save(update_fields=['quantite_stock'])
                    MouvementStock.objects.create(
                        article=article,
                        type_mouvement='RETOUR',
                        quantite=quantite,
                        stock_avant=stock_avant,
                        stock_apres=stock_restant,
                        reference_document=f"ANNUL-CREDIT-{vente.reference}",
                        utilisateur=request.user.get_full_name() or request.user.username,
                        commentaire=f"Annulation vente à crédit {vente.reference} — "
                                    f"retour {quantite} × {article.nom} en stock",
                    )
                    retours.append((article.id, article.nom, stock_restant))
            elif vente.article_id:
                # Anciennes ventes mono-article (créées avant les lignes)
                article = Article.objects.select_for_update().filter(
                    id=vente.article_id).first()
                if article is not None:
                    stock_avant = int(article.quantite_stock or 0)
                    quantite = int(vente.quantite or 1)
                    stock_restant = stock_avant + quantite
                    article.quantite_stock = stock_restant
                    article.save(update_fields=['quantite_stock'])
                    MouvementStock.objects.create(
                        article=article,
                        type_mouvement='RETOUR',
                        quantite=quantite,
                        stock_avant=stock_avant,
                        stock_apres=stock_restant,
                        reference_document=f"ANNUL-CREDIT-{vente.reference}",
                        utilisateur=request.user.get_full_name() or request.user.username,
                        commentaire=f"Annulation vente à crédit {vente.reference} — "
                                    f"retour {quantite} × {article.nom} en stock",
                    )
                    retours.append((article.id, article.nom, stock_restant))
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

        # Article du catalogue (optionnel) : le prix est toujours celui du catalogue
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

    # Prix catalogue verrouillé : prix_vente × quantité (aucun prix saisi à la main)
    for cle in ordre:
        ligne = lignes_normalisees[cle]
        article = ligne['article']
        if article is not None:
            prix_unitaire = article.prix_vente or Decimal('0')
            prix_catalogue = prix_unitaire * ligne['quantite']
            if abs(ligne['prix_total'] - prix_catalogue) > Decimal('0.5'):
                return JsonResponse(
                    {'error': f"Prix total incorrect pour {article.nom} : le prix "
                               f"catalogue est de {prix_catalogue:.0f} pour "
                               f"{ligne['quantite']} × {article.nom}."},
                    status=400)
            ligne['prix_total'] = prix_catalogue
            ligne['prix_unitaire'] = prix_unitaire
        else:
            if ligne['prix_total'] <= 0:
                return JsonResponse(
                    {'error': f"Le prix total de {ligne['article_nom']} doit être positif"},
                    status=400)
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
                existante.prix_unitaire = (
                    existante.prix_total / existante.quantite
                    if existante.quantite else ligne['prix_unitaire']
                )
                existante.save(update_fields=['quantite', 'prix_total', 'prix_unitaire'])
            else:
                LigneVenteAcompte.objects.create(
                    vente=vente,
                    article=ligne['article'],
                    article_nom=ligne['article_nom'],
                    quantite=ligne['quantite'],
                    prix_unitaire=ligne['prix_unitaire'],
                    prix_total=ligne['prix_total'],
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
    }]


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
