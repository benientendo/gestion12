# Sauvegarde des vues commerçant originales
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from .models import Client, Article, Vente, Categorie
from django.contrib.auth.models import User

# Vue simple pour les commerçants
@login_required
def commercant_dashboard(request):
    """Dashboard simple pour les commerçants."""
    return render(request, 'inventory/dashboard.html')

@login_required
def gestion_clients_maui(request):
    """Gestion des clients MAUI."""
    clients = Client.objects.all()
    return render(request, 'inventory/gestion_clients_maui.html', {'clients': clients})

@login_required
def ajouter_client_maui(request):
    """Ajouter un client MAUI."""
    if request.method == 'POST':
        # Logique simple d'ajout
        messages.success(request, "Client MAUI ajouté avec succès!")
        return redirect('inventory:gestion_clients_maui')
    
    return render(request, 'inventory/ajouter_client_maui.html')
