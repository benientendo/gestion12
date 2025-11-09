"""
Script de migration : Assigner les boutiques aux ventes existantes
Date: 30 Octobre 2025
"""

import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Vente, Client

def migrer_ventes_vers_boutiques():
    """Assigner la boutique à toutes les ventes existantes basées sur le client_maui."""
    
    print("=" * 60)
    print("MIGRATION DES VENTES VERS BOUTIQUES")
    print("=" * 60)
    print()
    
    # Récupérer toutes les ventes sans boutique
    ventes_sans_boutique = Vente.objects.filter(boutique__isnull=True)
    total_ventes = ventes_sans_boutique.count()
    
    print(f"📊 Ventes sans boutique: {total_ventes}")
    print()
    
    if total_ventes == 0:
        print("✅ Toutes les ventes ont déjà une boutique assignée!")
        return
    
    ventes_migrees = 0
    ventes_sans_client = 0
    ventes_client_sans_boutique = 0
    
    for vente in ventes_sans_boutique:
        # Vérifier si la vente a un client_maui
        if not vente.client_maui:
            print(f"⚠️  Vente {vente.numero_facture}: Pas de client_maui")
            ventes_sans_client += 1
            continue
        
        # Vérifier si le client a une boutique
        if not vente.client_maui.boutique:
            print(f"⚠️  Vente {vente.numero_facture}: Client {vente.client_maui.nom_terminal} sans boutique")
            ventes_client_sans_boutique += 1
            continue
        
        # Assigner la boutique
        boutique = vente.client_maui.boutique
        vente.boutique = boutique
        vente.save(update_fields=['boutique'])
        
        ventes_migrees += 1
        print(f"✅ Vente {vente.numero_facture} → Boutique {boutique.nom} (ID: {boutique.id})")
    
    print()
    print("=" * 60)
    print("RÉSUMÉ DE LA MIGRATION")
    print("=" * 60)
    print(f"✅ Ventes migrées: {ventes_migrees}")
    print(f"⚠️  Ventes sans client: {ventes_sans_client}")
    print(f"⚠️  Ventes avec client sans boutique: {ventes_client_sans_boutique}")
    print(f"📊 Total traité: {total_ventes}")
    print()
    
    # Vérification finale
    ventes_restantes = Vente.objects.filter(boutique__isnull=True).count()
    print(f"🔍 Ventes encore sans boutique: {ventes_restantes}")
    
    if ventes_restantes == 0:
        print()
        print("🎉 MIGRATION TERMINÉE AVEC SUCCÈS!")
    else:
        print()
        print("⚠️  Certaines ventes n'ont pas pu être migrées.")
        print("   Vérifiez que tous les clients ont une boutique assignée.")

if __name__ == '__main__':
    migrer_ventes_vers_boutiques()
