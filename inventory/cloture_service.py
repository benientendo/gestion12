"""Calcul unique de la recette et de la clôture de journée.

Toutes les vues affichant une recette (dashboard commerçant, dashboard
boutique, API statistiques MAUI, rapport CA quotidien, page de clôture)
doivent passer par ce module afin de garantir des montants identiques.

Règles métier :
- Une vente USD est comptabilisée avec ``montant_total_usd`` (repli sur
  ``montant_total`` pour les anciennes ventes).
- Une vente CDF est comptabilisée avec ``montant_total``.
- Les remboursements sont imputés au jour d'annulation (pas au jour de la
  vente d'origine).
- Les dépenses (RapportCaisse appliqués) sont déduites dans leur devise.
- Les paiements d'acomptes (crédit) sont ajoutés à la recette du jour.
"""

from decimal import Decimal

from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from .ca_remboursements import paiements_credit
from .models import Article, JournalValeurStock, LigneVente, RapportCaisse, Vente

DEVISE_CHOICES = ('CDF', 'USD')
MONEY_FIELD = DecimalField(max_digits=18, decimal_places=2)


def _montant_vente_expr(devise):
    if devise == 'USD':
        return Coalesce(F('montant_total_usd'), F('montant_total'))
    return F('montant_total')


def _montant_ligne_expr(devise):
    if devise == 'USD':
        return Coalesce(F('prix_unitaire_usd'), F('prix_unitaire'))
    return F('prix_unitaire')


def _somme_ventes(ventes_qs, devise):
    total = ventes_qs.aggregate(
        total=Sum(ExpressionWrapper(_montant_vente_expr(devise), output_field=MONEY_FIELD))
    )['total']
    return total or Decimal('0')


def _somme_lignes(lignes_qs, devise):
    total = lignes_qs.aggregate(
        total=Sum(ExpressionWrapper(
            F('quantite') * _montant_ligne_expr(devise),
            output_field=MONEY_FIELD,
        ))
    )['total']
    return total or Decimal('0')


def perimetre_ventes(boutique, devise=None):
    """Toutes les ventes payées de la boutique, sans filtre de date.

    Le périmètre sans date sert à imputer un remboursement au jour de
    l'annulation, même si la vente d'origine est d'un autre jour.
    """
    qs = Vente.objects.filter(
        Q(boutique=boutique) | Q(client_maui__boutique=boutique),
        paye=True,
    ).distinct()
    if devise:
        qs = qs.filter(devise=devise)
    return qs


def ventes_periode(boutique, debut, fin, devise=None):
    qs = perimetre_ventes(boutique, devise).filter(
        date_vente__date__gte=debut,
        date_vente__date__lte=fin,
    )
    return qs


def encaisse_origine(ventes_qs, devise):
    """Montant encaissé à l'origine (avant annulations) pour ces ventes."""
    total = _somme_ventes(ventes_qs, devise)

    # Vente encore active (annulation partielle) : les lignes annulées ont
    # réduit montant_total, on les ré-ajoute pour retrouver l'origine.
    total += _somme_lignes(
        LigneVente.objects.filter(
            est_annulee=True,
            devise=devise,
            vente__in=ventes_qs.filter(est_annulee=False),
        ),
        devise,
    )

    # Vente totalement annulée : montant_total n'a pas bougé ; seules les
    # annulations partielles antérieures à l'annulation totale l'ont réduit.
    total += _somme_lignes(
        LigneVente.objects.filter(
            est_annulee=True,
            devise=devise,
            vente__in=ventes_qs.filter(est_annulee=True),
            date_annulation__lt=F('vente__date_annulation'),
        ),
        devise,
    )
    return total


def remboursements_periode(scope_qs, debut, fin, devise):
    """Montant remboursé dans la période, imputé au jour d'annulation."""
    return _somme_lignes(
        LigneVente.objects.filter(
            est_annulee=True,
            date_annulation__isnull=False,
            date_annulation__date__gte=debut,
            date_annulation__date__lte=fin,
            devise=devise,
            vente__in=scope_qs,
        ),
        devise,
    )


def depenses_periode(boutique, debut, fin, devise):
    total = RapportCaisse.objects.filter(
        boutique=boutique,
        date_rapport__date__gte=debut,
        date_rapport__date__lte=fin,
        depense_appliquee=True,
        devise=devise,
    ).aggregate(total=Sum('depense'))['total']
    return total or Decimal('0')


def _ligne_devise(boutique, debut, fin, devise):
    ventes = ventes_periode(boutique, debut, fin, devise)
    ventes_actives = ventes.filter(est_annulee=False)
    scope = perimetre_ventes(boutique, devise)

    brut = encaisse_origine(ventes, devise)
    remboursements = remboursements_periode(scope, debut, fin, devise)
    depenses = depenses_periode(boutique, debut, fin, devise)
    credit = (
        paiements_credit(boutique, debut, fin)
        if devise == 'CDF' else Decimal('0')
    )
    net = brut - remboursements - depenses + credit

    return {
        'devise': devise,
        'ventes_brutes': brut,
        'remboursements': remboursements,
        'depenses': depenses,
        'credit': credit,
        'recette_nette': net,
        'nb_ventes': ventes_actives.count(),
        'nb_ventes_annulees': ventes.filter(est_annulee=True).count(),
    }


def resume_periode(boutique, debut, fin):
    """Recette complète (CDF + USD) d'une période pour une boutique."""
    return {devise.lower(): _ligne_devise(boutique, debut, fin, devise)
            for devise in DEVISE_CHOICES}


def valeur_stock_live(boutique, devise='CDF'):
    total = Article.objects.filter(
        boutique=boutique, est_actif=True,
        quantite_stock__gt=0, devise=devise,
    ).aggregate(
        total=Sum(ExpressionWrapper(
            F('quantite_stock') * F('prix_vente'),
            output_field=MONEY_FIELD,
        ))
    )['total']
    return total or Decimal('0')


def valeurs_stock(boutique, date=None):
    """Stock précédent / restant / réel d'une journée.

    ``precedent`` suit la formule du journal : c'est le stock restant de la
    veille (et non un instantané temps réel qui inclurait la journée en cours).
    """
    date = date or timezone.localdate()
    ligne = JournalValeurStock.objects.filter(boutique=boutique, date=date).first()

    if ligne is not None:
        precedent = ligne.valeur_stock_precedent
        restant = ligne.valeur_stock_restant
        reel = ligne.valeur_stock_reel
    else:
        veille = (
            JournalValeurStock.objects
            .filter(boutique=boutique, date__lt=date)
            .order_by('-date')
            .first()
        )
        if veille is not None:
            precedent = veille.valeur_stock_restant
            if precedent is None:
                precedent = veille.valeur_stock_reel
        else:
            precedent = Decimal('0')
        restant = precedent
        reel = valeur_stock_live(boutique)

    # Aujourd'hui : la valeur réelle est recalculée en direct (comme le
    # dashboard), les jours passés gardent leur instantané historique.
    if date == timezone.localdate():
        reel = valeur_stock_live(boutique)

    precedent = precedent or Decimal('0')
    restant = restant or Decimal('0')
    reel = reel or Decimal('0')

    return {
        'precedent': precedent,
        'restant': restant,
        'reel': reel,
        'ecart': reel - restant,
        'reel_usd': valeur_stock_live(boutique, 'USD'),
    }


def _arrondi(value):
    return float(Decimal(value).quantize(Decimal('0.01')))


def _serialiser_ligne(ligne):
    return {
        'devise': ligne['devise'],
        'ventes_brutes': _arrondi(ligne['ventes_brutes']),
        'remboursements': _arrondi(ligne['remboursements']),
        'depenses': _arrondi(ligne['depenses']),
        'credit': _arrondi(ligne['credit']),
        'recette_nette': _arrondi(ligne['recette_nette']),
        'nb_ventes': ligne['nb_ventes'],
        'nb_ventes_annulees': ligne['nb_ventes_annulees'],
    }


def resume_journee(boutique, date=None):
    """Résumé prêt pour l'API / la page de clôture (montants numériques)."""
    date = date or timezone.localdate()
    recettes = resume_periode(boutique, date, date)
    stock = valeurs_stock(boutique, date)
    return {
        'date': date.isoformat(),
        'recette': {devise: _serialiser_ligne(ligne)
                    for devise, ligne in recettes.items()},
        'stock': {
            'precedent_cdf': _arrondi(stock['precedent']),
            'restant_cdf': _arrondi(stock['restant']),
            'reel_cdf': _arrondi(stock['reel']),
            'ecart_cdf': _arrondi(stock['ecart']),
            'reel_usd': _arrondi(stock['reel_usd']),
        },
    }
