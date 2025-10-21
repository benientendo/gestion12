#!/usr/bin/env python
import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import *

def analyze_database():
    print("=== ANALYSE DE LA BASE DE DONNÉES ===")
    print()
    
    # Compteurs généraux
    print("📊 COMPTEURS GÉNÉRAUX:")
    print(f"   Commerçants: {Commercant.objects.count()}")
    print(f"   Boutiques: {Boutique.objects.count()}")
    print(f"   Clients MAUI: {Client.objects.count()}")
    print(f"   Articles: {Article.objects.count()}")
    print(f"   Catégories: {Categorie.objects.count()}")
    print(f"   Ventes: {Vente.objects.count()}")
    print()
    
    # Analyse des commerçants
    print("👤 COMMERÇANTS:")
    for commercant in Commercant.objects.all():
        print(f"   - {commercant.nom_entreprise} ({commercant.nom_responsable})")
        print(f"     Email: {commercant.email}")
        print(f"     Boutiques: {commercant.boutiques.count()}")
        print(f"     Actif: {commercant.est_actif}")
        print()
    
    # Analyse des boutiques
    print("🏪 BOUTIQUES:")
    for boutique in Boutique.objects.all():
        print(f"   - {boutique.nom} ({boutique.commercant.nom_entreprise})")
        print(f"     Type: {boutique.type_commerce}")
        print(f"     Ville: {boutique.ville}")
        print(f"     Articles: {boutique.articles.count()}")
        print(f"     Catégories: {boutique.categories.count()}")
        print(f"     Terminaux MAUI: {boutique.clients.count()}")
        print(f"     Active: {boutique.est_active}")
        print()
    
    # Analyse des clients MAUI
    print("📱 TERMINAUX MAUI:")
    for client in Client.objects.all():
        print(f"   - {client.nom_terminal} ({client.numero_serie})")
        print(f"     Boutique: {client.boutique.nom if client.boutique else 'Non assigné'}")
        print(f"     Propriétaire: {client.compte_proprietaire.username}")
        print(f"     Actif: {client.est_actif}")
        print(f"     Ventes: {client.ventes.count()}")
        print()
    
    # Analyse des relations
    print("🔗 ANALYSE DES RELATIONS:")
    
    # Articles sans boutique
    articles_sans_boutique = Article.objects.filter(boutique__isnull=True).count()
    print(f"   Articles sans boutique: {articles_sans_boutique}")
    
    # Catégories sans boutique
    categories_sans_boutique = Categorie.objects.filter(boutique__isnull=True).count()
    print(f"   Catégories sans boutique: {categories_sans_boutique}")
    
    # Clients sans boutique
    clients_sans_boutique = Client.objects.filter(boutique__isnull=True).count()
    print(f"   Terminaux sans boutique: {clients_sans_boutique}")
    
    print()
    print("=== ARCHITECTURE MULTI-BOUTIQUES ===")
    
    # Vérifier si l'architecture est prête
    architecture_ok = True
    
    if articles_sans_boutique > 0:
        print("❌ Des articles ne sont pas associés à une boutique")
        architecture_ok = False
    else:
        print("✅ Tous les articles sont associés à une boutique")
    
    if categories_sans_boutique > 0:
        print("❌ Des catégories ne sont pas associées à une boutique")
        architecture_ok = False
    else:
        print("✅ Toutes les catégories sont associées à une boutique")
    
    if clients_sans_boutique > 0:
        print("❌ Des terminaux ne sont pas associés à une boutique")
        architecture_ok = False
    else:
        print("✅ Tous les terminaux sont associés à une boutique")
    
    print()
    if architecture_ok:
        print("🎉 L'ARCHITECTURE MULTI-BOUTIQUES EST DÉJÀ EN PLACE !")
        print("   Votre Django supporte déjà l'isolation par boutique.")
    else:
        print("⚠️  L'ARCHITECTURE NÉCESSITE DES AJUSTEMENTS")
        print("   Certaines données doivent être migrées.")

if __name__ == "__main__":
    analyze_database()
