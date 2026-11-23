# distribution.py
# Suivi de la distribution des factures d'approvisionnement vers les points de vente.
#
# RÈGLE UNIQUE D'ATTRIBUTION
# --------------------------
# Une quantité est considérée comme « distribuée » lorsqu'elle a quitté le
# dépôt par un transfert VALIDÉ (le stock n'est retiré du dépôt qu'à la
# validation, voir TransfertStock.valider_transfert) : les badges restent
# donc cohérents avec le stock réel du dépôt.
#
# Chaque transfert validé est imputé aux lignes de facture du MÊME dépôt et
# du MÊME article dans l'ordre FIFO — date de facture, puis date
# d'enregistrement, puis id : les factures les plus anciennes reçoivent
# d'abord la marchandise. La règle s'applique sur TOUTES les lignes du
# dépôt pour ces articles (même les factures non affichées), afin qu'une
# facture affichée n'hérite jamais des transferts d'une facture plus ancienne.
#
# L'imputation est calculée TRANSFERT PAR TRANSFERT : on mémorise les
# segments (« la ligne X a pris N unités de CE transfert ») que chaque
# transfert a remplis. C'est cette mémoire qui rend les RETOURS exacts :
# renvoyer une quantité annule les segments du transfert d'où la marchandise
# est réellement partie, et non les lignes les plus anciennes. Un même
# article présent dans deux factures différentes est ainsi recrédité sur la
# BONNE facture, sans devinette.
#
# Retours (MouvementStock, référence RETOUR-…) :
#   - RETOUR-<transfert_id> : on annule les segments DE CE transfert, du
#     dernier rempli au premier (LIFO) — ce sont les dernières unités
#     chargées qui repartent ;
#   - RETOUR-<uuid> (retour lancé depuis la page articles, sans transfert
#     précisé) : on annule les imputations les plus récentes en premier
#     (LIFO entre les transferts, puis LIFO dans chacun).
# Ce qui ne correspond à aucune imputation (stock non issu d'une facture,
# facture supprimée…) n'est PAS recrédité : la vue le signale explicitement
# (« quantite_sans_source ») au lieu de le faire passer silencieusement.
#
# Refus de réception (terminal MAUI qui refuse un transfert reçu) : mêmes
# références RETOUR-<transfert_id> — la quantité revient à la source, les
# segments du lot sont annulés (LIFO) et ``deja_credite`` interdit tout
# double recrédit, que le crédit vienne d'un refus ou d'un retour d'excédent.
#
# Les colonnes « distribué / restant » dérivent des MÊMES segments :
# affichage et retour ne peuvent donc pas diverger.

from django.db.models import Sum

from .models import (
    Article, LigneApprovisionnement, MouvementStock, TransfertStock,
    trouver_article_destination,
)

STATUT_VIDE = 'VIDE'        # facture sans article
STATUT_AUCUN = 'AUCUN'      # rien n'a été distribué
STATUT_PARTIEL = 'PARTIEL'  # une partie a été distribuée
STATUT_TOUT = 'TOUT'        # tout a été distribué

PREFIXE_RETOUR = 'RETOUR-'
# Les références RETOUR-<uuid> font exactement 8 caractères : en dessous,
# un suffixe numérique est forcément un id de transfert.
LONGUEUR_UUID = 8


def _statut(recu, distribue):
    if recu <= 0:
        return STATUT_VIDE
    if distribue <= 0:
        return STATUT_AUCUN
    if distribue < recu:
        return STATUT_PARTIEL
    return STATUT_TOUT


# --------------------------------------------------------------------------
# Imputation des transferts sur les lignes de facture
# --------------------------------------------------------------------------

def lignes_fifo(depot_ids, article_ids):
    """Lignes de facture du dépôt pour ces articles, triées FIFO.

    Retourne {(depot_id, article_id): [ligne, …]} ; chaque ligne porte
    ``id``, ``facture_id``, ``recu``, ``date_creation``, ``date_facture``.
    """
    contexte = LigneApprovisionnement.objects.filter(
        facture__depot_id__in=depot_ids,
        article_id__in=article_ids,
    ).values_list(
        'id', 'facture_id', 'facture__depot_id', 'article_id',
        'quantite_unites', 'date_creation', 'facture__date_facture',
    )

    par_cle = {}
    for (ligne_id, facture_id, c_depot, article_id, recu,
         date_creation, date_facture) in contexte:
        par_cle.setdefault((c_depot, article_id), []).append({
            'id': ligne_id,
            'facture_id': facture_id,
            'recu': recu or 0,
            'date_creation': date_creation,
            'date_facture': date_facture,
        })

    for entrees in par_cle.values():
        entrees.sort(key=lambda e: (e['date_facture'], e['date_creation'], e['id']))
    return par_cle


def imputer_transferts(lignes, depot_ids, article_ids):
    """Impute chaque transfert validé aux lignes FIFO.

    Retourne ``(segments, ordre)`` :
      - ``segments`` : {transfert_id: [[ligne_id, quantité], …]} — ce que le
        transfert a rempli, dans l'ordre de remplissage (mémorisé pour que
        un retour annule exactement ces lignes) ;
      - ``ordre`` : {(depot_id, article_id): [transfert_id, …]} du plus
        ancien au plus récent (ordre d'annulation d'un retour sans transfert).
    """
    segments = {}
    ordre = {}
    deja = {}          # ligne_id -> quantité déjà imputée (hors retours)

    transferts = TransfertStock.objects.filter(
        depot_source_id__in=depot_ids,
        article_id__in=article_ids,
        statut='VALIDE',
    ).order_by('date_transfert', 'id').values_list(
        'id', 'depot_source_id', 'article_id', 'quantite',
    )

    for transfert_id, depot_id, article_id, quantite in transferts:
        entrees = lignes.get((depot_id, article_id))
        if not entrees:
            continue
        reste = quantite or 0
        remplissage = []
        for entree in entrees:
            if reste <= 0:
                break
            ligne_id = entree['id']
            dispo = entree['recu'] - deja.get(ligne_id, 0)
            if dispo <= 0:
                continue
            prendre = reste if reste < dispo else dispo
            remplissage.append([ligne_id, prendre])
            deja[ligne_id] = deja.get(ligne_id, 0) + prendre
            reste -= prendre
        if remplissage:
            segments[transfert_id] = remplissage
            ordre.setdefault((depot_id, article_id), []).append(transfert_id)

    return segments, ordre


def mouvements_retour(depot_ids, article_ids):
    """Entrées du dépôt portant une référence RETOUR-… (les plus anciens d'abord)."""
    return list(
        MouvementStock.objects.filter(
            article__boutique_id__in=depot_ids,
            article_id__in=article_ids,
            type_mouvement='ENTREE',
            reference_document__startswith=PREFIXE_RETOUR,
        ).order_by('date_mouvement', 'id').values_list(
            'reference_document', 'article__boutique_id', 'article_id', 'quantite',
        )
    )


def _transferts_cibles(segments, ordre, reference, depot_id, article_id):
    """Transferts à annuler pour un retour, du plus prioritaire au moins.

    - ``RETOUR-<transfert_id>`` : ce transfert-là (et lui seul) ;
    - ``RETOUR-<uuid>`` : les imputations les plus récentes d'abord.
    """
    suffixe = ''
    if reference and reference.startswith(PREFIXE_RETOUR):
        suffixe = reference[len(PREFIXE_RETOUR):]

    if suffixe.isdigit():
        transfert_id = int(suffixe)
        if transfert_id in segments:
            return [transfert_id]
        if len(suffixe) < LONGUEUR_UUID:
            # Id réel de transfert mais aucune imputation connue (facture
            # supprimée, article jamais facturé…) : rien à recréditer —
            # on ne devine JAMAIS une autre facture à sa place.
            return []
        # Suffixe chiffré de 8 caractères = un uuid, pas un id de transfert.

    return list(reversed(ordre.get((depot_id, article_id), [])))


def annuler_retour(segments, ordre, reference, depot_id, article_id, quantite):
    """Annule ``quantite`` sur les segments concernés (LIFO).

    Mutue ``segments`` en place et renvoie les segments annulés sous la
    forme ``[[ligne_id, quantité], …]``.
    """
    reste = quantite or 0
    annule = []

    for transfert_id in _transferts_cibles(segments, ordre, reference, depot_id, article_id):
        for paire in reversed(segments.get(transfert_id) or []):
            if reste <= 0:
                break
            ligne_id, dispo = paire
            if dispo <= 0:
                continue
            prendre = reste if reste < dispo else dispo
            paire[1] = dispo - prendre
            reste -= prendre
            annule.append([ligne_id, prendre])
        if reste <= 0:
            break

    return annule


def _repartition(depot_ids, article_ids):
    """Imputation courante, nette des retours déjà enregistrés.

    Retourne ``(segments, ordre)``.
    """
    lignes = lignes_fifo(depot_ids, article_ids)
    if not lignes:
        return {}, {}

    segments, ordre = imputer_transferts(lignes, depot_ids, article_ids)
    if not segments:
        return segments, ordre

    for reference, r_depot, r_article, quantite in mouvements_retour(depot_ids, article_ids):
        annuler_retour(segments, ordre, reference, r_depot, r_article, quantite)

    return segments, ordre


def deja_credite(transfert_ids):
    """{transfert_id: quantité déjà recréditée à la source (référence RETOUR-…)}.

    Sert à ne JAMAIS recréditer deux fois un même transfert, que le
    recrédit vienne d'un refus de réception ou d'un retour d'excédent.
    """
    if not transfert_ids:
        return {}
    references = [f'{PREFIXE_RETOUR}{tid}' for tid in transfert_ids]
    lignes = (
        MouvementStock.objects.filter(
            type_mouvement='ENTREE',
            reference_document__in=references,
        ).values('reference_document').annotate(total=Sum('quantite'))
    )
    return {
        int(ligne['reference_document'][len(PREFIXE_RETOUR):]): ligne['total'] or 0
        for ligne in lignes
    }


def _meme_article(source, destination):
    """Pré-filtre : ``source`` peut-il se résoudre en ``destination`` ?

    Reprend les deux règles de ``trouver_article_destination`` (le code,
    puis le nom insensible à la casse) dans l'autre sens, sans requête.
    Ce n'est qu'un filtre : la décision définitive est prise par
    ``trouver_article_destination`` lui-même, pour ne JAMAIS imputer un lot
    qui finirait par résoudre un autre article de la boutique.
    """
    if destination is None or source is None:
        return False
    if destination.code and source.code == destination.code:
        return True
    nom_destination = (destination.nom or '').strip().casefold()
    return bool(nom_destination) and (
        (source.nom or '').strip().casefold() == nom_destination
    )


def transferts_en_attente(boutique_destination, article_destination, quantite):
    """Transferts VALIDÉS qui ont fourni la quantité encore en attente au
    point de vente (``quantite_envoyee``), **du plus récent au plus ancien**.

    La validation de réception vide TOUTE la quantité en attente d'un
    article : ce qui reste en attente est donc toujours un suffixe continu
    des transferts les plus récents. Le LIFO restitue exactement les
    transferts concernés — jamais un lot déjà reçu et revendu.

    Retourne ``[(transfert, quantité), …]`` totalisant au plus ``quantite``
    (les lots déjà recrédités par un refus ou un retour sont exclus).

    Les lots qui ne correspondent pas à ``article_destination`` (l'article
    du point de vente a pu être apparié à un autre article source) sont
    écartés par la vérification exacte, jamais devinés.
    """
    reste = quantite or 0
    if reste <= 0 or article_destination is None or boutique_destination is None:
        return []

    lignes = list(
        TransfertStock.objects.filter(
            boutique_destination_id=boutique_destination.id,
            statut='VALIDE',
        ).order_by('-date_transfert', '-id').values_list(
            'id', 'article_id', 'quantite',
        )
    )
    if not lignes:
        return []

    articles = {
        article.id: article
        for article in Article.objects.filter(
            id__in={article_id for _, article_id, _ in lignes}
        )
    }

    candidats = []
    for transfert_id, article_id, quantite_lot in lignes:
        source = articles.get(article_id)
        if _meme_article(source, article_destination):
            candidats.append((transfert_id, source, quantite_lot or 0))
    if not candidats:
        return []

    credites = deja_credite([candidat[0] for candidat in candidats])

    retenus = []
    for transfert_id, source, quantite_lot in candidats:
        if reste <= 0:
            break
        dispo = quantite_lot - credites.get(transfert_id, 0)
        if dispo <= 0:
            continue
        # Vérification exacte (1 à 2 requêtes) uniquement sur les lots
        # qu'on s'apprête à retenir.
        resolu, _ = trouver_article_destination(
            source, boutique_destination, creer_si_absent=False,
        )
        if resolu is None or resolu.id != article_destination.id:
            continue
        prendre = dispo if dispo < reste else reste
        retenus.append((transfert_id, prendre))
        reste -= prendre

    if not retenus:
        return []

    quantites = dict(retenus)
    return [
        (transfert, quantites[transfert.id])
        for transfert in (
            TransfertStock.objects.filter(id__in=quantites)
            .select_related('article', 'depot_source')
            .order_by('-date_transfert', '-id')
        )
    ]


def cumul_par_ligne(segments):
    """{ligne_id: quantité distribuée} à partir des segments restants."""
    cumul = {}
    for remplissage in segments.values():
        for ligne_id, quantite in remplissage:
            if quantite > 0:
                cumul[ligne_id] = cumul.get(ligne_id, 0) + quantite
    return cumul


# --------------------------------------------------------------------------
# Renseignements « quelle facture source ? » (affichage)
# --------------------------------------------------------------------------

def _info_lignes(ligne_ids):
    """{ligne_id: {'facture_id', 'numero_facture', 'date_facture'}}"""
    if not ligne_ids:
        return {}
    return {
        ligne_id: {
            'facture_id': facture_id,
            'numero_facture': numero,
            'date_facture': date_facture,
        }
        for ligne_id, facture_id, numero, date_facture in (
            LigneApprovisionnement.objects.filter(id__in=set(ligne_ids)).values_list(
                'id', 'facture_id', 'facture__numero_facture', 'facture__date_facture',
            )
        )
    }


def _regrouper_par_facture(quantites_par_ligne):
    """{ligne_id: quantité} → liste de factures source, FIFO d'abord."""
    infos = _info_lignes(quantites_par_ligne)
    par_facture = {}
    for ligne_id, quantite in quantites_par_ligne.items():
        if quantite <= 0:
            continue
        info = infos.get(ligne_id)
        if info is None:
            continue
        entree = par_facture.setdefault(info['facture_id'], {
            'facture_id': info['facture_id'],
            'numero_facture': info['numero_facture'],
            'date_facture': info['date_facture'],
            'quantite': 0,
        })
        entree['quantite'] += quantite

    return sorted(
        par_facture.values(),
        key=lambda e: (e['date_facture'], e['facture_id']),
    )


def imputation_transfert(transfert):
    """Factures source d'un transfert validé, nettes des retours déjà faits.

    Retourne une liste de
    ``{'facture_id', 'numero_facture', 'date_facture', 'quantite}``
    (quantité de CE transfert encore imputée à chaque facture).
    """
    if transfert.statut != 'VALIDE':
        return []

    depot_ids = [transfert.depot_source_id]
    article_ids = [transfert.article_id]
    segments, _ = _repartition(depot_ids, article_ids)
    remplissage = segments.get(transfert.id) or []
    return _regrouper_par_facture({ligne_id: qte for ligne_id, qte in remplissage})


def simuler_retour(depot_id, article_id, reference, quantite):
    """Factures qu'un retour créditerait — sans rien écrire en base.

    Retourne ``{'factures_source': [...], 'quantite_sans_source': int}``
    où ``quantite_sans_source`` est la part du retour qui ne correspond à
    aucune facture (à signaler explicitement à l'utilisateur).
    """
    quantite = quantite or 0

    segments, ordre = _repartition([depot_id], [article_id])
    if not segments:
        return {'factures_source': [], 'quantite_sans_source': max(quantite, 0)}

    # Les retours déjà enregistrés sont neutralisés dans _repartition :
    # il ne reste qu'à appliquer celui qu'on prépare.
    annule = annuler_retour(segments, ordre, reference, depot_id, article_id, quantite)

    par_ligne = {}
    for ligne_id, qte in annule:
        par_ligne[ligne_id] = par_ligne.get(ligne_id, 0) + qte

    factures_source = _regrouper_par_facture(par_ligne)
    total_credite = sum(c['quantite'] for c in factures_source)
    return {
        'factures_source': factures_source,
        'quantite_sans_source': max(quantite - total_credite, 0),
    }


# --------------------------------------------------------------------------
# État de distribution (badges des factures)
# --------------------------------------------------------------------------

def etat_distribution(factures):
    """Calcule l'état de distribution des factures fournies.

    Retourne ``(par_facture, par_ligne)`` : deux dictionnaires indexés par id.
    Chaque facture reçoit en plus l'attribut ``etat`` = dict ``recu``,
    ``distribue``, ``restant``, ``statut`` — directement utilisable dans les
    templates (``{% include "_badge_distribution.html" with etat=facture.etat %}``).

    Les ``factures`` doivent avoir leurs lignes préchargées avec leurs articles
    (``prefetch_related('lignes__article')``) et leur dépôt
    (``select_related('depot')``) pour éviter les requêtes N+1.

    L'affichage et les retours partagent la même imputation (cf. en-tête du
    module) : une quantité revenue au dépôt est retirée de la facture d'où
    elle est réellement partie, jamais d'une facture devinée.
    """
    factures = list(factures)
    par_facture = {}
    par_ligne = {}

    if not factures:
        return par_facture, par_ligne

    article_ids = set()
    depot_ids = set()
    visible = False

    for facture in factures:
        par_facture[facture.id] = {
            'recu': 0, 'distribue': 0, 'restant': 0, 'statut': STATUT_VIDE,
        }
        depot_ids.add(facture.depot_id)
        for ligne in facture.lignes.all():
            visible = True
            article_ids.add(ligne.article_id)

    if not visible:
        return par_facture, par_ligne

    segments, _ = _repartition(depot_ids, article_ids)
    distribue_par_ligne = cumul_par_ligne(segments)

    # Reporting : uniquement les factures demandées
    for facture in factures:
        etat = par_facture[facture.id]
        for ligne in facture.lignes.all():
            recu = ligne.quantite_unites or 0
            distribue = distribue_par_ligne.get(ligne.id, 0)
            if distribue > recu:
                distribue = recu
            info = {
                'recu': recu,
                'distribue': distribue,
                'restant': recu - distribue,
                'statut': _statut(recu, distribue),
            }
            par_ligne[ligne.id] = info
            etat['recu'] += recu
            etat['distribue'] += distribue

        etat['restant'] = etat['recu'] - etat['distribue']
        etat['statut'] = _statut(etat['recu'], etat['distribue'])
        facture.etat = etat

    return par_facture, par_ligne
