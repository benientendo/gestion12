"""
Service JournalValeurStock
==========================
Toutes les fonctions qui écrivent dans JournalValeurStock passent par ici.
Principe : get_or_create la ligne du jour, puis F() pour les cumuls atomiques.
"""

from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone


def _aujourd_hui(boutique):
    """Retourne la date locale de la boutique (ou date serveur par défaut)."""
    return timezone.localdate()


def _get_ou_creer_ligne(boutique, date=None):
    """
    Récupère ou crée la ligne du journal pour (boutique, date).
    Si c'est une nouvelle ligne, copie valeur_stock_restant de la veille.
    Retourne (journal, created).
    """
    from .models import JournalValeurStock

    if date is None:
        date = _aujourd_hui(boutique)

    with transaction.atomic():
        ligne, created = JournalValeurStock.objects.select_for_update().get_or_create(
            boutique=boutique,
            date=date,
            defaults={'valeur_stock_precedent': Decimal('0')}
        )
        if created:
            # Stock préc. = stock RESTANT de la veille (formule du journal).
            # On ne prend pas un instantané temps réel : il inclurait les
            # mouvements déjà survenus aujourd'hui (surtout lors d'une sync
            # retardée d'une vente de la veille).
            veille = (
                JournalValeurStock.objects
                .filter(boutique=boutique, date__lt=date)
                .order_by('-date')
                .values('valeur_stock_restant', 'valeur_stock_reel')
                .first()
            )
            if veille is not None:
                ligne.valeur_stock_precedent = (
                    veille['valeur_stock_restant']
                    if veille['valeur_stock_restant'] is not None
                    else veille['valeur_stock_reel']
                ) or Decimal('0')
            else:
                # Première ligne : ancrer sur la valeur actuelle du stock.
                ligne.valeur_stock_precedent = _calculer_valeur_stock_reel(boutique)
            ligne.recalculer_valeur_restant()
            ligne.save(update_fields=['valeur_stock_precedent', 'valeur_stock_restant'])
    return ligne, created


def _calculer_valeur_stock_reel(boutique):
    """
    Calcule la valeur réelle du stock = SUM(quantite_stock * prix_vente)
    pour les articles actifs en CDF avec stock > 0.
    ⚠️ PRIX DE VENTE: valeur commerciale confiée au gérant
    (ex: 100 u × PV 100 = 10 000 FC — pas le coût d'achat).
    """
    from .models import Article

    articles = Article.objects.filter(
        boutique=boutique, est_actif=True,
        quantite_stock__gt=0, devise='CDF'
    )
    total = Decimal('0')
    for art in articles.values_list('quantite_stock', 'prix_vente'):
        total += Decimal(str(art[0])) * Decimal(str(art[1]))
    return total


def _incrementer(boutique, champ, montant, date=None):
    """
    Incrémente atomiquement le champ `champ` de `montant` pour (boutique, date).
    Recalcule ensuite valeur_stock_restant et valeur_stock_reel.
    """
    from .models import JournalValeurStock

    if montant == 0:
        return

    if date is None:
        date = _aujourd_hui(boutique)

    montant = Decimal(str(montant))
    aujourd_hui = timezone.localdate()

    with transaction.atomic():
        ligne, _ = _get_ou_creer_ligne(boutique, date)
        # Mise à jour atomique du champ cumulatif
        JournalValeurStock.objects.filter(pk=ligne.pk).update(**{champ: F(champ) + montant})
        # Recharger et recalculer valeur_stock_restant
        ligne.refresh_from_db()
        ligne.recalculer_valeur_restant()
        # Snapshot de la valeur réelle : uniquement pour aujourd'hui.
        # Écrire la valeur live sur un jour passé la polluerait avec les
        # mouvements des jours suivants (sync retardée d'une vente, etc.).
        if date >= aujourd_hui:
            ligne.valeur_stock_reel = _calculer_valeur_stock_reel(boutique)
        elif not ligne.valeur_stock_reel:
            ligne.valeur_stock_reel = ligne.valeur_stock_restant
        ligne.save(update_fields=['valeur_stock_restant', 'valeur_stock_reel', 'updated_at'])

        # Un mouvement antidaté change le restant de ce jour : il faut
        # propager le nouveau stock précédent aux jours suivants.
        if date < aujourd_hui:
            recalculer_chaines_depuis(boutique, date + timedelta(days=1))


# ──────────────────────────────────────────────
# API publique appelée par les signals / views
# ──────────────────────────────────────────────

def enregistrer_vente(boutique, valeur, date=None):
    """Vente : on retire la valeur au prix de vente (valeur commerciale)."""
    _incrementer(boutique, 'valeur_ventes', valeur, date)


def enregistrer_approvisionnement(boutique, valeur, date=None):
    """Approvisionnement / facture fournisseur : entrée de stock (valeur commerciale au prix de vente)."""
    _incrementer(boutique, 'valeur_stock_ajoute', valeur, date)


def enregistrer_transfert_entrant(boutique, valeur_cout, date=None):
    """Transfert reçu depuis un autre point de vente."""
    _incrementer(boutique, 'valeur_transfert_entrant', valeur_cout, date)


def enregistrer_transfert_sortant(boutique, valeur_cout, date=None):
    """Transfert envoyé vers un autre point de vente."""
    _incrementer(boutique, 'valeur_transfert_sortant', valeur_cout, date)


def enregistrer_inventaire(boutique, impact_valeur, date=None):
    """
    Régularisation inventaire.
    impact_valeur peut être négatif (excédent de comptage → sortie de valeur)
    ou positif (manque → entrée de valeur).
    """
    _incrementer(boutique, 'montant_inventaire', impact_valeur, date)


def enregistrer_sortie_manuelle(boutique, valeur, date=None):
    """Sortie manuelle, perte, casse (valeur au prix de vente)."""
    _incrementer(boutique, 'valeur_stock_sorti', valeur, date)


def compenser_annulation_defectueuse(boutique, valeur, date=None):
    """
    Annulation d'un article pour motif « Article défectueux ».
    L'article n'est PAS remis en stock : sa valeur est RECLASSÉE de la
    colonne « Ventes » vers « Stock sorti » (le mouvement SORTIE est créé
    par l'annulation, il alimente valeur_stock_sorti). On retire donc ici
    la même valeur de valeur_ventes pour que la formule de cohérence
    (restant = ... - sorti - ventes) reste inchangée.
    """
    _incrementer(boutique, 'valeur_ventes', -Decimal(str(valeur)), date)


def enregistrer_modification_prix(boutique, impact_valeur, date=None, details=None):
    """
    Modification du prix de vente d'un article.
    impact_valeur = (nouveau_prix_vente - ancien_prix_vente) * quantite_stock

    `details` (dict optionnel) trace l'article modifié pour le détail cliquable
    de la colonne « Modif. prix » du back-office :
        article, article_nom, article_code, devise,
        ancien_prix, nouveau_prix, quantite_stock, utilisateur
    """
    _incrementer(boutique, 'impact_modification_prix', impact_valeur, date)
    if details is not None:
        _enregistrer_detail_modification_prix(boutique, impact_valeur, details, date)


def _enregistrer_detail_modification_prix(boutique, impact_valeur, details, date=None):
    """Écrit la ligne de détail article d'une modification de prix."""
    from .models import DetailModificationPrix

    if date is None:
        date = _aujourd_hui(boutique)

    ligne, creee = _get_ou_creer_ligne(boutique, date)
    if creee:
        # Jamais de ligne journal « vierge » (impact nul, ex. stock à 0) :
        # on fige la valeur réelle du stock comme le ferait _incrementer.
        # Un jour passé garde une valeur historique (pas le stock live).
        if date >= timezone.localdate():
            ligne.valeur_stock_reel = _calculer_valeur_stock_reel(boutique)
        else:
            ligne.valeur_stock_reel = ligne.valeur_stock_restant
        ligne.save(update_fields=['valeur_stock_reel', 'updated_at'])

    DetailModificationPrix.objects.create(
        journal=ligne,
        article=details.get('article'),
        article_nom=details.get('article_nom') or '',
        article_code=details.get('article_code') or '',
        devise=details.get('devise') or 'CDF',
        ancien_prix=details.get('ancien_prix') or 0,
        nouveau_prix=details.get('nouveau_prix') or 0,
        quantite_stock=int(details.get('quantite_stock') or 0),
        impact=impact_valeur,
        utilisateur=details.get('utilisateur') or '',
    )


def maj_reductions_journal(boutique, date_debut, date_fin):
    """
    Recalcule montant_reductions du journal pour une période.
    Réduction = (prix_original − prix_unitaire) × quantité sur les lignes négociées CDF
    des ventes non annulées de la boutique.
    """
    from decimal import Decimal
    from django.db.models import Q, Sum, F, ExpressionWrapper, DecimalField
    from .models import JournalValeurStock, LigneVente

    reductions = (
        LigneVente.objects.filter(
            Q(vente__boutique=boutique) | Q(vente__client_maui__boutique=boutique),
            vente__date_vente__date__gte=date_debut,
            vente__date_vente__date__lte=date_fin,
            vente__est_annulee=False,
            prix_original__isnull=False,
            devise='CDF',
        )
        .annotate(jour=F('vente__date_vente__date'))
        .values('jour')
        .annotate(total=Sum(ExpressionWrapper(
            (F('prix_original') - F('prix_unitaire')) * F('quantite'),
            output_field=DecimalField(max_digits=18, decimal_places=2),
        )))
        .filter(total__gt=0)
    )
    par_jour = {r['jour']: r['total'] or Decimal('0') for r in reductions}

    lignes = JournalValeurStock.objects.filter(
        boutique=boutique,
        date__gte=date_debut,
        date__lte=date_fin,
    )
    for ligne in lignes:
        nouveau = par_jour.get(ligne.date, Decimal('0'))
        if ligne.montant_reductions != nouveau:
            ligne.montant_reductions = nouveau
            ligne.save(update_fields=['montant_reductions', 'updated_at'])
    return par_jour


def recalculer_chaines_depuis(boutique, date):
    """
    Propage le stock restant à partir de ``date`` (incluse) vers les jours
    suivants : le stock précédent d'un jour = stock restant de la veille.

    Utilisé après une synchronisation retardée (mouvement antidaté) pour que
    la page de clôture et le journal restent cohérents.
    """
    from .models import JournalValeurStock

    veille = (
        JournalValeurStock.objects
        .filter(boutique=boutique, date__lt=date)
        .order_by('-date')
        .first()
    )
    valeur_precedente = None
    if veille is not None:
        valeur_precedente = veille.valeur_stock_restant
        if valeur_precedente is None:
            valeur_precedente = veille.valeur_stock_reel

    lignes = (
        JournalValeurStock.objects
        .filter(boutique=boutique, date__gte=date)
        .order_by('date')
    )
    for ligne in lignes:
        if valeur_precedente is not None:
            ligne.valeur_stock_precedent = valeur_precedente
        ligne.recalculer_valeur_restant()
        ligne.save(update_fields=[
            'valeur_stock_precedent', 'valeur_stock_restant', 'updated_at'
        ])
        valeur_precedente = ligne.valeur_stock_restant


def recalculer_tout_depuis_debut(boutique):
    """
    Recalcule toutes les lignes du journal dans l'ordre chronologique
    pour garantir la cohérence des valeurs_stock_precedent.
    Stock préc. du jour = stock restant de la veille.
    À appeler après import massif ou correction de données.
    """
    from .models import JournalValeurStock

    lignes = JournalValeurStock.objects.filter(boutique=boutique).order_by('date')
    valeur_precedente = None
    for ligne in lignes:
        if valeur_precedente is not None:
            ligne.valeur_stock_precedent = valeur_precedente
        ligne.recalculer_valeur_restant()
        ligne.save(update_fields=[
            'valeur_stock_precedent', 'valeur_stock_restant', 'updated_at'
        ])
        # Le stock restant de ce jour devient le stock précédent du lendemain
        valeur_precedente = ligne.valeur_stock_restant


# ──────────────────────────────────────────────────────────────
# Classification d'un MouvementStock → colonne du journal
# ──────────────────────────────────────────────────────────────
#
# SOURCE DE VÉRITÉ unique : le signal d'écriture, le détail cliquable de la
# page du journal et la reconstruction historique passent tous par les deux
# fonctions ci-dessous. Règles :
#
#   « Inventaire »   = comptages : régularisation d'un inventaire (INV-…) et
#                      instantanés envoyés par MAUI Windows (source
#                      « inventaire » / « stock »). Impact NET signé valorisé
#                      au prix de vente : (compté − théorique) × prix de vente.
#   « Transfert IN » = UNIQUEMENT des flux entre boutiques : TRANSFERT-…,
#                      TRANSFERT-BTQ-… et les transferts dépôt→PDV confirmés
#                      par validation MAUI (réécrits TRANSFERT-… grâce au
#                      marqueur Article.date_envoi posé par valider_transfert).
#   « Stock ajouté » = tout le reste en entrée : régulations du back-office
#                      (REGUL-, AJUST-…), factures, retours clients et retours
#                      de refus de réception (RETOUR-…).
#
# Les références INIT-/REGL- sont des régularisations d'historique : pas de flux.

# Références d'inventaire (régularisation d'un modèle Inventaire).
PREFIXES_INVENTAIRE = ('INV-',)
# Sources MAUI Windows comptées comme instantané de stock.
SOURCES_INVENTAIRE_MAUI = ('inventaire', 'stock')
# Régularisations d'historique : bookkeeping, pas de vrais flux de valeur.
PREFIXES_HORS_JOURNAL = ('INIT-', 'REGL-')
# Flux entre boutiques.
PREFIXES_TRANSFERT = ('TRANSFERT-',)

# Colonnes alimentées par les MouvementStock. Les autres (Ventes, Modif. prix,
# Réduction) ont des sources propres et ne sont jamais réécrites par ici.
COLONNES_MOUVEMENTS = (
    'montant_inventaire',
    'valeur_stock_ajoute',
    'valeur_transfert_entrant',
    'valeur_transfert_sortant',
    'valeur_stock_sorti',
)


def ecart_ajustement(mouvement):
    """Écart SIGNÉ d'un AJUSTEMENT : stock_apres − stock_avant.

    Repli sur ``quantite`` quand les stocks n'ont pas été renseignés. On préfère
    les stocks parce que certaines origines (MAUI Windows) enregistrent la
    quantité en valeur absolue, ce qui fausserait le signe de la colonne.
    """
    avant = mouvement.stock_avant or 0
    apres = mouvement.stock_apres or 0
    if avant or apres:
        return apres - avant
    return mouvement.quantite or 0


def est_inventaire(mouvement):
    """True si ce mouvement est un comptage (colonne « Inventaire »)."""
    ref = mouvement.reference_document or ''
    if ref.startswith(PREFIXES_INVENTAIRE):
        return True
    return (
        mouvement.type_mouvement == 'AJUSTEMENT'
        and ref in SOURCES_INVENTAIRE_MAUI
    )


def colonne_mouvement(mouvement):
    """Colonne du journal de valeur alimentée par ``mouvement`` (ou None)."""
    ref = mouvement.reference_document or ''
    if ref.startswith(PREFIXES_HORS_JOURNAL):
        return None
    if mouvement.type_mouvement == 'VENTE':
        return 'valeur_ventes'
    if mouvement.type_mouvement == 'RETOUR':
        # Retour client : réentrée de stock, pas un transfert entre boutiques.
        return 'valeur_stock_ajoute'
    if est_inventaire(mouvement):
        return 'montant_inventaire'
    if mouvement.type_mouvement == 'AJUSTEMENT':
        # Régulation saisie dans le back-office : un ajout est un ajout,
        # une diminution est une sortie — jamais l'inverse.
        return (
            'valeur_stock_ajoute' if ecart_ajustement(mouvement) >= 0
            else 'valeur_stock_sorti'
        )
    if mouvement.type_mouvement == 'ENTREE':
        return (
            'valeur_transfert_entrant'
            if ref.startswith(PREFIXES_TRANSFERT) else 'valeur_stock_ajoute'
        )
    if mouvement.type_mouvement == 'SORTIE':
        return (
            'valeur_transfert_sortant'
            if ref.startswith(PREFIXES_TRANSFERT) else 'valeur_stock_sorti'
        )
    return None


def valeur_mouvement(mouvement):
    """Valeur au prix de vente portée par la colonne de ``mouvement``.

    Positive pour les colonnes d'entrée/sortie ; SIGNÉE pour
    « montant_inventaire » (un manque ajoute de la valeur, un excédent retire).
    """
    article = mouvement.article
    prix_vente = Decimal(str(article.prix_vente or 0)) if article else Decimal('0')
    colonne = colonne_mouvement(mouvement)
    if colonne is None:
        return Decimal('0')

    quantite = Decimal(str(abs(mouvement.quantite or 0)))

    if colonne == 'montant_inventaire':
        if mouvement.type_mouvement == 'AJUSTEMENT':
            return prix_vente * Decimal(str(ecart_ajustement(mouvement)))
        # Régularisation d'inventaire : ENTREE = écart positif, SORTIE = négatif.
        signe = Decimal('1') if mouvement.type_mouvement == 'ENTREE' else Decimal('-1')
        return prix_vente * quantite * signe

    return prix_vente * quantite


# Colonnes qui RETIRENT de la valeur (négatives dans la formule de cohérence).
COLONNES_SORTANTES = (
    'valeur_stock_sorti',
    'valeur_transfert_sortant',
    'valeur_ventes',
)


def impact_valeur_mouvement(mouvement):
    """Impact SIGNÉ sur la valeur du stock (colonne du journal).

    Positif pour « Inventaire », « Stock ajouté » et « Transfert IN » ;
    négatif pour « Stock sorti », « Transfert OUT » et « Ventes ».
    """
    colonne = colonne_mouvement(mouvement)
    if colonne is None:
        return Decimal('0')
    valeur = valeur_mouvement(mouvement)
    return -valeur if colonne in COLONNES_SORTANTES else valeur


def enregistrer_mouvement(boutique, mouvement, date=None):
    """Incrémente la colonne du journal correspondant à ``mouvement``.

    Retourne la colonne écrite, ou None si le mouvement est hors journal
    (régularisation d'historique INIT-/REGL-, type inconnu).
    """
    colonne = colonne_mouvement(mouvement)
    if colonne is None:
        return None
    if date is None:
        try:
            date = mouvement.date_mouvement.date()
        except Exception:
            date = None
    _incrementer(boutique, colonne, valeur_mouvement(mouvement), date)
    return colonne


def reclasser_colonnes_depuis_mouvements(boutique, date_debut=None, date_fin=None):
    """Réécrit les colonnes de flux du journal de ``boutique`` depuis les
    MouvementStock, avec les règles ci-dessus.

    Seules les colonnes de ``COLONNES_MOUVEMENTS`` sont réécrites : « Ventes »
    (dont les annulations « article défectueux » retraitées hors CA), « Modif.
    prix » et « Réduction » ont des sources propres. Recalcule ensuite la chaîne
    valeur_stock_precedent → valeur_stock_restant. Retourne le nombre de lignes
    réécrites.
    """
    from collections import defaultdict
    from .models import JournalValeurStock, MouvementStock

    mouvements = MouvementStock.objects.filter(
        article__boutique=boutique,
    ).select_related('article')
    if date_debut:
        mouvements = mouvements.filter(date_mouvement__date__gte=date_debut)
    if date_fin:
        mouvements = mouvements.filter(date_mouvement__date__lte=date_fin)

    cumuls = defaultdict(
        lambda: {colonne: Decimal('0') for colonne in COLONNES_MOUVEMENTS}
    )
    for mouvement in mouvements.order_by('date_mouvement'):
        colonne = colonne_mouvement(mouvement)
        if colonne in COLONNES_MOUVEMENTS:
            cumuls[mouvement.date_mouvement.date()][colonne] += valeur_mouvement(mouvement)

    lignes = JournalValeurStock.objects.filter(boutique=boutique)
    if date_debut:
        lignes = lignes.filter(date__gte=date_debut)
    if date_fin:
        lignes = lignes.filter(date__lte=date_fin)

    reecrites = 0
    with transaction.atomic():
        for ligne in lignes.order_by('date'):
            # Journée sans mouvement : ces colonnes sont forcément à zéro.
            data = cumuls.get(
                ligne.date,
                {colonne: Decimal('0') for colonne in COLONNES_MOUVEMENTS},
            )
            for colonne in COLONNES_MOUVEMENTS:
                setattr(ligne, colonne, data[colonne])
            ligne.save()
            reecrites += 1
        recalculer_tout_depuis_debut(boutique)

    return reecrites
