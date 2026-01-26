"""
URL configuration for gestion_magazin project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.authtoken.views import obtain_auth_token
from inventory.test_timezone import test_timezone

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('inventory.urls')),
    path('api/', include('inventory.api_urls')),
    path('api/v2/', include('inventory.api_urls_v2')),  # API v2 multi-boutiques avec isolation par boutique
    path('api/v2/simple/', include('inventory.api_urls_v2_simple')),  # API v2 simplifiée sans authentification
    path('api/bilan/', include('inventory.api_urls_bilan')),  # API pour les bilans et indicateurs
    path('api-token-auth/', obtain_auth_token, name='api_token_auth'),
    path('test-timezone/', test_timezone),  # Endpoint de test pour les timezone
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
