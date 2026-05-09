"""
Service JournalValeurStock
==========================
Toutes les fonctions qui écrivent dans JournalValeurStock passent par ici.
Principe : get_or_create la ligne du jour, puis F() pour les cumuls atomiques.
"""

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
            # Stock préc. = valeur_stock_reel de la veille
            # C'est la vraie valeur du stock en fin de journée précédente,
            # donc ce avec quoi on démarre la journée actuelle.
            veille = (
                JournalValeurStock.objects
                .filter(boutique=boutique, date__lt=date)
                .order_by('-date')
                .values_list('valeur_stock_reel', flat=True)
                .first()
            )
            if veille is not None:
                ligne.valeur_stock_precedent = veille
            else:
                # Première ligne : calculer la valeur actuelle du stock
                ligne.valeur_stock_precedent = _calculer_valeur_stock_reel(boutique)
            ligne.recalculer_valeur_restant()
            ligne.save(update_fields=['valeur_stock_precedent', 'valeur_stock_restant'])
    return ligne, created


def _calculer_valeur_stock_reel(boutique):
    """
    Calcule la valeur réelle du stock = SUM(quantite_stock * prix_vente)
    pour les articles actifs en CDF avec stock > 0.
    Correspond exactement à la valeur affichée sur le dashboard du point de vente.
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

    with transaction.atomic():
        ligne, _ = _get_ou_creer_ligne(boutique, date)
        # Mise à jour atomique du champ cumulatif
        JournalValeurStock.objects.filter(pk=ligne.pk).update(**{champ: F(champ) + montant})
        # Recharger et recalculer valeur_stock_restant
        ligne.refresh_from_db()
        ligne.recalculer_valeur_restant()
        # Snapshot de la valeur réelle du stock
        ligne.valeur_stock_reel = _calculer_valeur_stock_reel(boutique)
        ligne.save(update_fields=['valeur_stock_restant', 'valeur_stock_reel', 'updated_at'])


# ──────────────────────────────────────────────
# API publique appelée par les signals / views
# ──────────────────────────────────────────────

def enregistrer_vente(boutique, valeur_cout, date=None):
    """Vente : on retire la valeur au prix d'achat."""
    _incrementer(boutique, 'valeur_ventes', valeur_cout, date)


def enregistrer_approvisionnement(boutique, valeur_cout, date=None):
    """Approvisionnement / facture fournisseur : entrée de stock."""
    _incrementer(boutique, 'valeur_stock_ajoute', valeur_cout, date)


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


def enregistrer_sortie_manuelle(boutique, valeur_cout, date=None):
    """Sortie manuelle, perte, casse."""
    _incrementer(boutique, 'valeur_stock_sorti', valeur_cout, date)


def enregistrer_modification_prix(boutique, impact_valeur, date=None):
    """
    Modification du prix d'achat sur un article.
    impact_valeur = (nouveau_prix_achat - ancien_prix_achat) * quantite_stock
    """
    _incrementer(boutique, 'impact_modification_prix', impact_valeur, date)


def recalculer_tout_depuis_debut(boutique):
    """
    Recalcule toutes les lignes du journal dans l'ordre chronologique
    pour garantir la cohérence des valeurs_stock_precedent.
    Stock préc. du jour = valeur_stock_reel de la veille.
    À appeler après import massif ou correction de données.
    """
    from .models import JournalValeurStock

    lignes = JournalValeurStock.objects.filter(boutique=boutique).order_by('date')
    valeur_precedente = Decimal('0')
    first = True
    for ligne in lignes:
        if first:
            # Première ligne : garder sa valeur_stock_precedent ou utiliser 0
            if ligne.valeur_stock_reel and ligne.valeur_stock_reel > 0:
                pass  # on garde la valeur existante pour la première ligne
            first = False
        else:
            ligne.valeur_stock_precedent = valeur_precedente
        ligne.recalculer_valeur_restant()
        ligne.save(update_fields=[
            'valeur_stock_precedent', 'valeur_stock_restant', 'updated_at'
        ])
        # Le stock_reel de ce jour devient le stock_precedent du lendemain
        valeur_precedente = ligne.valeur_stock_reel if ligne.valeur_stock_reel else ligne.valeur_stock_restant
