"""
Script pour corriger l'isolation des ventes existantes
Assigne automatiquement le champ 'boutique' aux ventes qui n'en ont pas
Exécuter avec: python manage.py shell < corriger_isolation_ventes.py
"""

import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Vente, Boutique, Client

print("\n" + "="*80)
print("CORRECTION DE L'ISOLATION DES VENTES")
print("="*80 + "\n")

# 1. Identifier les ventes sans boutique
ventes_sans_boutique = Vente.objects.filter(boutique__isnull=True)
total_a_corriger = ventes_sans_boutique.count()

print(f"📊 Ventes à corriger: {total_a_corriger}\n")

if total_a_corriger == 0:
    print("✅ Aucune vente à corriger. L'isolation est déjà parfaite!")
    print("\n" + "="*80)
    print("SCRIPT TERMINÉ")
    print("="*80 + "\n")
    exit()

# 2. Corriger chaque vente
ventes_corrigees = 0
ventes_non_corrigees = 0
details_corrections = []

print("🔧 Correction en cours...\n")

for vente in ventes_sans_boutique:
    print(f"Vente #{vente.numero_facture} (ID: {vente.id})")
    
    # Essayer de récupérer la boutique via le client_maui
    if vente.client_maui:
        if vente.client_maui.boutique:
            boutique = vente.client_maui.boutique
            vente.boutique = boutique
            vente.save(update_fields=['boutique'])
            
            print(f"   ✅ Assignée à: {boutique.nom} (ID: {boutique.id})")
            ventes_corrigees += 1
            details_corrections.append({
                'vente_id': vente.id,
                'numero_facture': vente.numero_facture,
                'boutique_id': boutique.id,
                'boutique_nom': boutique.nom,
                'status': 'corrigée'
            })
        else:
            print(f"   ⚠️  Client MAUI sans boutique: {vente.client_maui.nom_terminal}")
            ventes_non_corrigees += 1
            details_corrections.append({
                'vente_id': vente.id,
                'numero_facture': vente.numero_facture,
                'client_maui': vente.client_maui.nom_terminal,
                'status': 'client_sans_boutique'
            })
    else:
        print(f"   ⚠️  Pas de client MAUI associé")
        ventes_non_corrigees += 1
        details_corrections.append({
            'vente_id': vente.id,
            'numero_facture': vente.numero_facture,
            'status': 'pas_de_client'
        })
    print()

# 3. Résumé
print("="*80)
print("RÉSUMÉ DE LA CORRECTION")
print("="*80 + "\n")

print(f"📊 Statistiques:")
print(f"   - Ventes à corriger: {total_a_corriger}")
print(f"   - Ventes corrigées: {ventes_corrigees}")
print(f"   - Ventes non corrigées: {ventes_non_corrigees}")
print(f"   - Taux de réussite: {(ventes_corrigees/total_a_corriger*100):.1f}%\n")

# 4. Vérification finale
print("="*80)
print("VÉRIFICATION FINALE")
print("="*80 + "\n")

ventes_restantes = Vente.objects.filter(boutique__isnull=True).count()
print(f"Ventes sans boutique restantes: {ventes_restantes}\n")

if ventes_restantes == 0:
    print("✅ SUCCÈS TOTAL!")
    print("   Toutes les ventes ont maintenant une boutique assignée.")
    print("   L'isolation entre boutiques est maintenant garantie.")
else:
    print(f"⚠️  {ventes_restantes} vente(s) n'ont pas pu être corrigées.")
    print("\n   Ventes non corrigées:")
    for detail in details_corrections:
        if detail['status'] != 'corrigée':
            print(f"   - Vente #{detail['numero_facture']} (ID: {detail['vente_id']})")
            if detail['status'] == 'client_sans_boutique':
                print(f"     Raison: Client MAUI '{detail['client_maui']}' sans boutique")
            elif detail['status'] == 'pas_de_client':
                print(f"     Raison: Pas de client MAUI associé")
    
    print("\n   ACTIONS MANUELLES REQUISES:")
    print("   1. Vérifier les clients MAUI sans boutique:")
    print("      Client.objects.filter(boutique__isnull=True)")
    print("\n   2. Assigner manuellement les boutiques aux clients:")
    print("      client = Client.objects.get(id=X)")
    print("      client.boutique = Boutique.objects.get(id=Y)")
    print("      client.save()")
    print("\n   3. Relancer ce script pour corriger les ventes restantes")

# 5. Test d'isolation
print("\n" + "="*80)
print("TEST D'ISOLATION PAR BOUTIQUE")
print("="*80 + "\n")

boutiques = Boutique.objects.all()
for boutique in boutiques:
    ventes_boutique = Vente.objects.filter(boutique=boutique).count()
    print(f"🏪 {boutique.nom}: {ventes_boutique} ventes")

print("\n" + "="*80)
print("SCRIPT TERMINÉ")
print("="*80 + "\n")

print("💡 PROCHAINES ÉTAPES:")
print("   1. Tester l'interface backend pour vérifier l'isolation")
print("   2. Vérifier que chaque commerçant ne voit que ses ventes")
print("   3. Tester avec différents comptes utilisateurs")
print("   4. Vérifier les logs Django lors de la création de nouvelles ventes\n")
