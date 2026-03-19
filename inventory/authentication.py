"""
Authentification personnalisée pour l'API v2 simplifiée.
Permet aux vues AllowAny de fonctionner même quand un token JWT expiré/invalide est envoyé.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class OptionalJWTAuthentication(JWTAuthentication):
    """
    Variante de JWTAuthentication qui ne lève pas d'exception si le token est
    invalide ou expiré. Retourne None (utilisateur anonyme) dans ce cas.

    Comportement:
    - Token valide  → authentifie l'utilisateur normalement
    - Token absent  → retourne None (anonyme) — comportement standard JWTAuthentication
    - Token invalide/expiré → retourne None (anonyme) au lieu de 401
    """

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except (InvalidToken, TokenError):
            return None
