from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .api_views import (
    ArticleViewSet, 
    CategorieViewSet, 
    VenteViewSet, 
    update_stock_efficient,
    sync_ventes_batch,
    authentifier_client_maui,
    verifier_session_maui,
    deconnecter_client_maui
)

# Création du router pour les ViewSets
router = DefaultRouter()
router.register(r'articles', ArticleViewSet)
router.register(r'categories', CategorieViewSet)
router.register(r'ventes', VenteViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('stock/update/', update_stock_efficient, name='update_stock_efficient'),
    path('sync/ventes', sync_ventes_batch, name='sync_ventes_batch'),
    
    # Authentification clients MAUI
    path('maui/auth/', authentifier_client_maui, name='authentifier_client_maui'),
    path('maui/verify-session/', verifier_session_maui, name='verifier_session_maui'),
    path('maui/logout/', deconnecter_client_maui, name='deconnecter_client_maui'),
]

urlpatterns += [
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
