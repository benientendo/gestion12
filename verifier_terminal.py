"""
Script pour verifier et corriger le terminal MAUI
Commande: python verifier_terminal.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Client, Boutique, Commercant
from django.contrib.auth.models import User

print("=" * 60)
print("VERIFICATION TERMINAL MAUI")
print("=" * 60)

# Numero de serie du terminal
NUMERO_SERIE = "575c50cf32d00948"

print(f"\nRecherche du terminal: {NUMERO_SERIE}")

# Verifier si le terminal existe
try:
    terminal = Client.objects.select_related('boutique', 'compte_proprietaire').get(
        numero_serie=NUMERO_SERIE
    )
    
    print(f"\n✅ TERMINAL TROUVE")
    print(f"   ID: {terminal.id}")
    print(f"   Nom: {terminal.nom_terminal}")
    print(f"   Numero serie: {terminal.numero_serie}")
    print(f"   Actif: {terminal.est_actif}")
    print(f"   Proprietaire: {terminal.compte_proprietaire.username if terminal.compte_proprietaire else 'AUCUN'}")
    
    # Verifier la boutique
    if terminal.boutique:
        print(f"\n✅ BOUTIQUE ASSOCIEE")
        print(f"   ID: {terminal.boutique.id}")
        print(f"   Nom: {terminal.boutique.nom}")
        print(f"   Code: {terminal.boutique.code_boutique}")
        print(f"   Active: {terminal.boutique.est_active}")
        print(f"   Commercant: {terminal.boutique.commercant.nom_entreprise}")
    else:
        print(f"\n❌ AUCUNE BOUTIQUE ASSOCIEE")
        print(f"\nBoutiques disponibles:")
        for b in Boutique.objects.all():
            print(f"   - ID {b.id}: {b.nom} ({b.code_boutique})")
        
        # Proposer d'associer
        print(f"\nPour associer le terminal a une boutique:")
        print(f"   terminal.boutique = Boutique.objects.get(id=XX)")
        print(f"   terminal.save()")
    
    # Verifier si actif
    if not terminal.est_actif:
        print(f"\n⚠️ TERMINAL INACTIF")
        print(f"Pour activer:")
        print(f"   terminal.est_actif = True")
        print(f"   terminal.save()")
    
except Client.DoesNotExist:
    print(f"\n❌ TERMINAL NON TROUVE")
    print(f"\nTerminaux existants:")
    for t in Client.objects.all():
        print(f"   - {t.numero_serie}: {t.nom_terminal} (Boutique: {t.boutique.nom if t.boutique else 'AUCUNE'})")
    
    print(f"\nPour creer le terminal:")
    print(f"   1. Trouver le user proprietaire")
    print(f"   2. Trouver la boutique")
    print(f"   3. Creer le terminal")
    print(f"\nCode:")
    print(f"   user = User.objects.get(username='VOTRE_USER')")
    print(f"   boutique = Boutique.objects.get(id=XX)")
    print(f"   terminal = Client.objects.create(")
    print(f"       numero_serie='{NUMERO_SERIE}',")
    print(f"       nom_terminal='Terminal TABORA1',")
    print(f"       compte_proprietaire=user,")
    print(f"       boutique=boutique,")
    print(f"       est_actif=True")
    print(f"   )")

print("\n" + "=" * 60)
print("VERIFICATION TERMINEE")
print("=" * 60)
