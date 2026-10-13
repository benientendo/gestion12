"""
Utilisateur courant, hors de la requête
=======================================
Les signals Django n'ont pas accès à `request` : ce module transporte le nom
du collaborateur (ou le numéro de série du terminal) en cours de requête via
un ContextVar, posé par `CurrentUserMiddleware`. C'est ce qui permet de tracer
QUI a modifié un prix — colonne « Utilisateur » du détail « Modif. prix ».

Tout est défensif : une erreur ici ne doit jamais casser une requête.
"""

from contextvars import ContextVar

_utilisateur_courant = ContextVar('utilisateur_courant', default='')


def utilisateur_courant():
    """Nom de l'utilisateur courant, ou '' si inconnu."""
    try:
        return _utilisateur_courant.get() or ''
    except Exception:
        return ''


def nom_utilisateur(user):
    """Affichage du collaborateur : profil collaborateur, sinon nom, sinon login."""
    try:
        if user is None or not user.is_authenticated:
            return ''
        if hasattr(user, 'profil_collaborateur'):
            return user.profil_collaborateur.nom_complet or ''
        return user.get_full_name() or user.username or ''
    except Exception:
        return ''


class CurrentUserMiddleware:
    """
    Mémorise l'utilisateur courant pour les signals (traçabilité des
    modifications de prix, ...). À placer APRÈS AuthenticationMiddleware.
    Sur l'API terminal il n'y a pas de compte web : on retient le numéro de série.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            if request.path.startswith('/api/'):
                nom = (
                    request.headers.get('X-Device-Serial')
                    or request.headers.get('Device-Serial')
                    or ''
                )
            else:
                nom = nom_utilisateur(request.user)
        except Exception:
            nom = ''

        token = _utilisateur_courant.set(nom)
        try:
            return self.get_response(request)
        finally:
            try:
                _utilisateur_courant.reset(token)
            except Exception:
                pass
