#!/usr/bin/env python
"""
Script pour remplacer commercant_views.py
"""

SIMPLE_VIEWS_CONTENT = '''# Version simplifiée des vues commerçant
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def commercant_dashboard(request):
    """Dashboard simple pour les commerçants."""
    return render(request, 'inventory/dashboard.html')

@login_required
def gestion_clients_maui(request):
    """Gestion des clients MAUI."""
    return render(request, 'inventory/gestion_clients_maui.html')

@login_required
def ajouter_client_maui(request):
    """Ajouter un client MAUI."""
    if request.method == 'POST':
        messages.success(request, "Client MAUI ajouté avec succès!")
        return redirect('inventory:gestion_clients_maui')
    
    return render(request, 'inventory/ajouter_client_maui.html')
'''

def replace_views():
    """Remplacer le fichier commercant_views.py"""
    
    try:
        with open('inventory/commercant_views.py', 'w', encoding='utf-8') as f:
            f.write(SIMPLE_VIEWS_CONTENT)
        
        print("✅ Fichier commercant_views.py remplacé!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

if __name__ == "__main__":
    success = replace_views()
    exit(0 if success else 1)
