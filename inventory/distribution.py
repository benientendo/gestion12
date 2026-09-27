# distribution.py
# Suivi de la distribution des factures d'approvisionnement vers les points de vente.
#
# Une quantité est considérée comme « distribuée » lorsqu'elle a quitté le dépôt
# par un transfert VALIDÉ (le stock n'est retiré du dépôt qu'à la validation,
# voir TransfertStock.valider_transfert) : les badges restent donc cohérents
# avec le stock réel du dépôt.
#
# Attribution des transferts aux factures : FIFO (premier entré, premier sorti)
# par article et par dépôt — les transferts validés les plus anciens sont
# imputés aux lignes reçues les plus anciennes encore non soldées. La règle
# s'applique sur TOUTES les lignes du dépôt pour ces articles (même les factures
# non affichées), afin qu'une facture affichée n'hérite jamais des transferts
# d'une facture plus ancienne.

from .models import LigneApprovisionnement, TransfertStock

STATUT_VIDE = 'VIDE'        # facture sans article
STATUT_AUCUN = 'AUCUN'      # rien n'a été distribué
STATUT_PARTIEL = 'PARTIEL'  # une partie a été distribuée
STATUT_TOUT = 'TOUT'        # tout a été distribué


def _statut(recu, distribue):
    if recu <= 0:
        return STATUT_VIDE
    if distribue <= 0:
        return STATUT_AUCUN
    if distribue < recu:
        return STATUT_PARTIEL
    return STATUT_TOUT


def etat_distribution(factures):
    """Calcule l'état de distribution des factures fournies.

    Retourne ``(par_facture, par_ligne)`` : deux dictionnaires indexés par id.
    Chaque facture reçoit en plus l'attribut ``etat`` = dict ``recu``,
    ``distribue``, ``restant``, ``statut`` — directement utilisable dans les
    templates (``{% include "_badge_distribution.html" with etat=facture.etat %}``).

    Les ``factures`` doivent avoir leurs lignes préchargées avec leurs articles
    (``prefetch_related('lignes__article')``) et leur dépôt
    (``select_related('depot')``) pour éviter les requêtes N+1.
    """
    factures = list(factures)
    par_facture = {}
    par_ligne = {}

    if not factures:
        return par_facture, par_ligne

    visible_par_id = {}      # ligne_id -> (facture, ligne)
    article_ids = set()
    depot_ids = set()

    for facture in factures:
        par_facture[facture.id] = {
            'recu': 0, 'distribue': 0, 'restant': 0, 'statut': STATUT_VIDE,
        }
        depot_ids.add(facture.depot_id)
        for ligne in facture.lignes.all():
            visible_par_id[ligne.id] = (facture, ligne)
            article_ids.add(ligne.article_id)

    if not visible_par_id:
        return par_facture, par_ligne

    # Toutes les lignes du dépôt pour ces articles (factures affichées ou non)
    contexte = LigneApprovisionnement.objects.filter(
        facture__depot_id__in=depot_ids,
        article_id__in=article_ids,
    ).values_list(
        'id', 'facture_id', 'facture__depot_id', 'article_id', 'quantite_unites',
        'date_creation', 'facture__date_facture',
    )

    lignes_par_cle = {}
    for (ligne_id, facture_id, c_depot, article_id, recu,
         date_creation, date_facture) in contexte:
        lignes_par_cle.setdefault((c_depot, article_id), []).append({
            'id': ligne_id,
            'facture_id': facture_id,
            'recu': recu or 0,
            'date_creation': date_creation,
            'date_facture': date_facture,
        })

    for entrees in lignes_par_cle.values():
        entrees.sort(key=lambda e: (e['date_facture'], e['date_creation'], e['id']))

    if not lignes_par_cle:
        return par_facture, par_ligne

    # Transferts validés (stock réellement sorti du dépôt), du plus ancien au plus récent
    transferts = TransfertStock.objects.filter(
        depot_source_id__in=depot_ids,
        article_id__in=article_ids,
        statut='VALIDE',
    ).order_by('date_transfert', 'id').values_list('depot_source_id', 'article_id', 'quantite')

    index = {cle: 0 for cle in lignes_par_cle}
    distribue_par_ligne = {}

    for depot_id, article_id, qte in transferts:
        cle = (depot_id, article_id)
        entrees = lignes_par_cle.get(cle)
        if not entrees:
            continue
        reste = qte or 0
        while reste > 0 and index[cle] < len(entrees):
            entree = entrees[index[cle]]
            deja = distribue_par_ligne.get(entree['id'], 0)
            dispo = entree['recu'] - deja
            if dispo <= 0:
                index[cle] += 1
                continue
            prendre = reste if reste < dispo else dispo
            distribue_par_ligne[entree['id']] = deja + prendre
            reste -= prendre
            if deja + prendre >= entree['recu']:
                index[cle] += 1

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
            }
            par_ligne[ligne.id] = info
            etat['recu'] += recu
            etat['distribue'] += distribue

        etat['restant'] = etat['recu'] - etat['distribue']
        etat['statut'] = _statut(etat['recu'], etat['distribue'])
        facture.etat = etat

    return par_facture, par_ligne
