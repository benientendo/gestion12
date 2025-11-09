"""
Script de Vérification - État des Ventes
========================================

Ce script affiche l'état actuel de toutes les ventes
avec leurs montants et lignes.
"""

import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Vente, LigneVente, Boutique
from decimal import Decimal

def verifier_ventes():
    """Afficher l'état de toutes les ventes"""
    
    print("="*80)
    print("  VÉRIFICATION DES VENTES")
    print("="*80)
    
    # Récupérer toutes les ventes
    ventes = Vente.objects.all().select_related('client_maui__boutique').prefetch_related('lignes__article')
    
    if not ventes:
        print("\n⚠️  Aucune vente trouvée dans la base de données")
        return
    
    print(f"\n📊 Total ventes: {ventes.count()}\n")
    
    ventes_probleme = []
    
    for vente in ventes:
        boutique_nom = vente.client_maui.boutique.nom if vente.client_maui and vente.client_maui.boutique else "N/A"
        terminal_nom = vente.client_maui.nom_terminal if vente.client_maui else "N/A"
        
        print("-"*80)
        print(f"🧾 Vente: {vente.numero_facture}")
        print(f"   Date: {vente.date_vente.strftime('%d/%m/%Y %H:%M')}")
        print(f"   Boutique: {boutique_nom}")
        print(f"   Terminal: {terminal_nom}")
        print(f"   Mode paiement: {vente.mode_paiement}")
        print(f"   Payé: {'Oui' if vente.paye else 'Non'}")
        print(f"   Montant enregistré: {vente.montant_total} CDF")
        
        # Calculer le montant à partir des lignes
        montant_calcule = Decimal('0.00')
        nb_lignes = vente.lignes.count()
        
        print(f"\n   📦 Lignes de vente ({nb_lignes}):")
        
        for ligne in vente.lignes.all():
            sous_total = ligne.prix_unitaire * ligne.quantite
            montant_calcule += sous_total
            
            print(f"      - {ligne.article.nom}")
            print(f"        Quantité: {ligne.quantite}")
            print(f"        Prix unitaire: {ligne.prix_unitaire} CDF")
            print(f"        Sous-total: {sous_total} CDF")
        
        print(f"\n   💰 Montant calculé: {montant_calcule} CDF")
        
        # Vérifier la cohérence
        if vente.montant_total != montant_calcule:
            print(f"   ⚠️  PROBLÈME: Le montant enregistré ({vente.montant_total}) ne correspond pas au montant calculé ({montant_calcule})")
            ventes_probleme.append(vente)
        else:
            print(f"   ✅ Montant correct")
        
        print()
    
    # Résumé
    print("="*80)
    print("  RÉSUMÉ")
    print("="*80)
    print(f"Total ventes: {ventes.count()}")
    print(f"Ventes avec problème: {len(ventes_probleme)}")
    print(f"Ventes correctes: {ventes.count() - len(ventes_probleme)}")
    
    if ventes_probleme:
        print(f"\n⚠️  {len(ventes_probleme)} vente(s) nécessite(nt) une correction")
        print(f"   Exécutez: python corriger_montants_ventes.py")
    else:
        print(f"\n✅ Toutes les ventes sont correctes!")
    
    print("="*80)

if __name__ == "__main__":
    try:
        verifier_ventes()
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
