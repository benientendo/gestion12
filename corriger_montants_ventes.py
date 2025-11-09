"""
Script de Correction - Recalculer les Montants des Ventes
=========================================================

Ce script recalcule le montant_total de toutes les ventes
en se basant sur leurs lignes de vente.
"""

import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Vente, LigneVente
from decimal import Decimal

def corriger_montants_ventes():
    """Recalculer les montants de toutes les ventes"""
    
    print("="*60)
    print("  CORRECTION DES MONTANTS DE VENTES")
    print("="*60)
    
    # Récupérer toutes les ventes
    ventes = Vente.objects.all().prefetch_related('lignes')
    total_ventes = ventes.count()
    
    print(f"\n📊 Total ventes à vérifier: {total_ventes}")
    
    ventes_corrigees = 0
    ventes_ok = 0
    
    for vente in ventes:
        # Calculer le montant total à partir des lignes
        montant_calcule = Decimal('0.00')
        
        for ligne in vente.lignes.all():
            sous_total = ligne.prix_unitaire * ligne.quantite
            montant_calcule += sous_total
        
        # Comparer avec le montant actuel
        if vente.montant_total != montant_calcule:
            ancien_montant = vente.montant_total
            vente.montant_total = montant_calcule
            vente.save(update_fields=['montant_total'])
            
            print(f"\n✅ Vente #{vente.numero_facture} corrigée:")
            print(f"   Ancien montant: {ancien_montant} CDF")
            print(f"   Nouveau montant: {montant_calcule} CDF")
            print(f"   Lignes: {vente.lignes.count()}")
            
            ventes_corrigees += 1
        else:
            ventes_ok += 1
    
    print("\n" + "="*60)
    print("  RÉSUMÉ")
    print("="*60)
    print(f"✅ Ventes correctes: {ventes_ok}")
    print(f"🔧 Ventes corrigées: {ventes_corrigees}")
    print(f"📊 Total traité: {total_ventes}")
    print("\n✨ Correction terminée avec succès!")
    print("="*60)

if __name__ == "__main__":
    try:
        corriger_montants_ventes()
    except Exception as e:
        print(f"\n❌ Erreur: {str(e)}")
        import traceback
        traceback.print_exc()
