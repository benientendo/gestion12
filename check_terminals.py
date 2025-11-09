#!/usr/bin/env python3
"""
Script pour vérifier les terminaux MAUI disponibles
"""

import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Client, Boutique

def check_terminals():
    """Vérifier les terminaux MAUI disponibles"""
    print("🔍 TERMINAUX MAUI DISPONIBLES")
    print("=" * 50)
    
    terminals = Client.objects.select_related('boutique').all()
    
    if not terminals.exists():
        print("❌ Aucun terminal MAUI trouvé dans la base de données")
        return
    
    for terminal in terminals:
        boutique_info = terminal.boutique.nom if terminal.boutique else "❌ Aucune boutique"
        status = "✅ Actif" if terminal.est_actif else "❌ Inactif"
        
        print(f"📱 Terminal: {terminal.nom_terminal}")
        print(f"   Numéro de série: {terminal.numero_serie}")
        print(f"   Boutique: {boutique_info}")
        print(f"   Statut: {status}")
        print(f"   Propriétaire: {terminal.compte_proprietaire.username if terminal.compte_proprietaire else 'Aucun'}")
        print("-" * 30)
    
    print(f"\n📊 Total: {terminals.count()} terminal(s)")
    
    # Vérifier les boutiques
    print("\n🏪 BOUTIQUES DISPONIBLES")
    print("=" * 50)
    
    boutiques = Boutique.objects.all()
    for boutique in boutiques:
        terminals_count = boutique.clients.count()
        print(f"🏪 {boutique.nom} (ID: {boutique.id})")
        print(f"   Type: {boutique.type_commerce}")
        print(f"   Terminaux: {terminals_count}")
        print(f"   Statut: {'✅ Active' if boutique.est_active else '❌ Inactive'}")
        print("-" * 30)

if __name__ == "__main__":
    check_terminals()
