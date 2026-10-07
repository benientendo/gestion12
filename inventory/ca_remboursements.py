"""CA net : encaisse d'origine des ventes moins les remboursements imputes
au jour d'annulation.

Regles (annulation immediate ou differee apres cloture) :
- L'annulation TOTALE d'une vente ne modifie pas ``montant_total``.
- L'annulation PARTIELLE d'une ligne retranche son montant de ``montant_total``.
- Un remboursement est impute au CA du JOUR d'annulation : la recette du jour
  de la vente d'origine reste inchangee, meme si sa journee est cloturee.

Donc pour une periode : CA net = encaisse d'origine - remboursements de la periode.
"""
from decimal import Decimal

from django.db.models import F, Sum

from .models import LigneVente


def _montant_lignes(lignes_qs):
    """Montant (quantite x prix unitaire) de ces lignes de vente."""
    total = lignes_qs.aggregate(total=Sum(F('quantite') * F('prix_unitaire')))['total']
    return total or Decimal('0')


def encaisse_total(ventes_qs):
    """Montant encaisse a l'origine (avant annulations) pour ces ventes.

    Repartit de ``montant_total`` (reduit par les annulations partielles) et
    ajoute le montant des lignes annulees pour retrouver le montant d'origine.
    """
    total = ventes_qs.aggregate(total=Sum('montant_total'))['total'] or Decimal('0')

    # Vente encore active (annulation partielle uniquement) : toutes ses
    # lignes annulees ont reduit montant_total -> tout est ajoute.
    total += _montant_lignes(LigneVente.objects.filter(
        est_annulee=True,
        vente__in=ventes_qs.filter(est_annulee=False),
    ))

    # Vente deja annulee : montant_total n'a pas bouge lors de l'annulation
    # totale, seules les annulations partielles anterieures l'ont reduit.
    total += _montant_lignes(LigneVente.objects.filter(
        est_annulee=True,
        vente__in=ventes_qs.filter(est_annulee=True),
        date_annulation__lt=F('vente__date_annulation'),
    ))

    return total


def remboursements(ventes_scope_qs, date_debut, date_fin=None):
    """Montant rembourse dans la periode pour ce perimetre de ventes.

    ``ventes_scope_qs`` = meme perimetre de ventes SANS filtre de date ni
    d'annulation (une facture annulee reste dans le perimetre : son
    remboursement est impute au jour d'annulation).
    """
    lignes = LigneVente.objects.filter(
        est_annulee=True,
        date_annulation__isnull=False,
        date_annulation__date__gte=date_debut,
        vente__in=ventes_scope_qs,
    )
    if date_fin is not None:
        lignes = lignes.filter(date_annulation__date__lte=date_fin)
    return _montant_lignes(lignes)


def ca_net(ventes_qs, ventes_scope_qs, date_debut, date_fin=None):
    """CA net de la periode : encaisse d'origine - remboursements de la periode."""
    return encaisse_total(ventes_qs) - remboursements(ventes_scope_qs, date_debut, date_fin)
