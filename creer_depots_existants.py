"""
Script pour créer des dépôts pour les commerçants existants qui n'en ont pas.
À exécuter en production après la migration 0020.

Usage:
    python manage.py shell < creer_depots_existants.py
    
    OU
    
    python manage.py shell
    >>> exec(open('creer_depots_existants.py').read())
"""

import os
import django

# Setup Django si exécuté directement
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
    django.setup()

from inventory.models import Commercant, Boutique


def creer_depots_manquants():
    """Crée un dépôt pour chaque commerçant qui n'en a pas."""
    
    print("=" * 60)
    print("🔍 Recherche des commerçants sans dépôt...")
    print("=" * 60)
    
    # Tous les commerçants
    commercants = Commercant.objects.all()
    print(f"📊 Total commerçants: {commercants.count()}")
    
    depots_crees = 0
    depots_existants = 0
    
    for commercant in commercants:
        # Vérifier si le commerçant a déjà un dépôt
        depot_existant = commercant.boutiques.filter(est_depot=True).first()
        
        if depot_existant:
            print(f"✅ {commercant.nom_entreprise} - Dépôt existant: {depot_existant.nom}")
            depots_existants += 1
        else:
            # Créer un dépôt pour ce commerçant
            depot = Boutique.objects.create(
                nom=f"Dépôt Central - {commercant.nom_entreprise}",
                description=f"Dépôt central de stockage pour {commercant.nom_entreprise}",
                commercant=commercant,
                type_commerce='DEPOT',
                est_depot=True,
                est_active=True,
                ville=commercant.adresse.split(',')[0] if commercant.adresse else '',
            )
            print(f"🆕 {commercant.nom_entreprise} - Dépôt créé: {depot.nom} (ID: {depot.id})")
            depots_crees += 1
    
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ")
    print("=" * 60)
    print(f"✅ Dépôts existants: {depots_existants}")
    print(f"🆕 Dépôts créés: {depots_crees}")
    print(f"📊 Total commerçants traités: {commercants.count()}")
    print("=" * 60)
    
    return depots_crees


if __name__ == '__main__':
    creer_depots_manquants()
else:
    # Exécuté depuis Django shell
    creer_depots_manquants()
