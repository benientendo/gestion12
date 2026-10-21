"""
Vue pour la connexion rapide par code PIN
"""
import logging

from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Collaborateur, Inventaire

logger = logging.getLogger(__name__)


def _page_pin(request, error=None, notice=None):
    """Rend la page PIN (jamais une erreur 500 pour un terrain mobile)."""
    return render(request, 'inventory/commercant/login_pin.html', {
        'error': error,
        'notice': notice,
    })


def accueil_collaborateur(request):
    """Point d'arrivée d'un collaborateur connecté par code PIN.

    Un collaborateur n'a PAS de profil commerçant : lire `profil_commercant`
    (dashboard, liste d'inventaires…) lève RelatedObjectDoesNotExist → erreur
    500. On le mène donc vers l'inventaire en cours, sinon vers la page PIN
    avec un message explicite.
    """
    collaborateur = Collaborateur.objects.filter(
        user=request.user, est_actif=True
    ).select_related('commercant').first()

    if collaborateur is None:
        messages.error(request, "Vous n'avez pas de profil commerçant ou collaborateur.")
        return redirect('inventory:login_commercant')

    inventaire = Inventaire.objects.filter(
        boutique__commercant=collaborateur.commercant,
        statut='EN_COURS',
    ).select_related('boutique').first()

    if inventaire:
        return redirect(
            'inventory:saisir_inventaire_boutique',
            boutique_id=inventaire.boutique.id,
            inventaire_id=inventaire.id,
        )

    return _page_pin(
        request,
        notice=(
            "Aucun inventaire en cours pour le moment. "
            "Reconnectez-vous avec votre PIN dès qu'un inventaire sera démarré."
        ),
    )


@require_http_methods(["GET", "POST"])
def login_pin(request):
    """Connexion rapide par code PIN pour les collaborateurs.

    Aucune exception ne doit s'échapper : elle devient un message affiché sur
    la page PIN (le terrain ne doit jamais voir une page 500).
    """
    if request.method == 'POST':
        pin = request.POST.get('pin', '').strip()

        if not pin or len(pin) < 4:
            return _page_pin(request, error='Le code PIN doit contenir au moins 4 chiffres')

        # `.get()` levait MultipleObjectsReturned si deux collaborateurs
        # partagent le même PIN (aucune contrainte unique sur le champ) → 500.
        candidats = list(
            Collaborateur.objects.select_related('user', 'commercant')
            .filter(code_pin=pin, est_actif=True)
            .order_by('id')[:2]
        )

        if not candidats:
            return _page_pin(request, error='Code PIN invalide ou compte inactif')

        if len(candidats) > 1:
            logger.warning(
                "Code PIN %s partagé par les collaborateurs %s",
                pin, [c.id for c in candidats],
            )
            return _page_pin(
                request,
                error=(
                    "Ce code PIN est utilisé par plusieurs collaborateurs. "
                    "Contactez votre commerçant pour qu'il vous en attribue un autre."
                ),
            )

        collaborateur = candidats[0]

        try:
            login(request, collaborateur.user)
        except PermissionDenied:
            return _page_pin(request, error='Ce compte est désactivé')
        except Exception as e:
            logger.exception("Echec de connexion PIN pour le collaborateur %s", collaborateur.id)
            return _page_pin(request, error=f"Connexion impossible : {e}")

        try:
            collaborateur.date_derniere_connexion = timezone.now()
            collaborateur.save(update_fields=['date_derniere_connexion'])

            messages.success(
                request,
                f"Bienvenue {collaborateur.nom_complet} ! Connexion rapide réussie."
            )

            # Inventaire en cours → saisie ; sinon accueil collaborateur
            # (et surtout PAS le dashboard commerçant : erreur 500).
            return accueil_collaborateur(request)
        except Exception as e:
            logger.exception(
                "Erreur post-connexion PIN pour le collaborateur %s", collaborateur.id
            )
            return _page_pin(request, error=f"Erreur technique : {e}")

    return _page_pin(request)
