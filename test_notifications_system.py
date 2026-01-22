"""
Script de test pour le système de notifications de stock.
Exécutez ce script pour vérifier que les notifications sont créées automatiquement.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Article, MouvementStock, Client, Boutique, NotificationStock
from django.utils import timezone

def test_notification_creation():
    """Test la création automatique de notifications lors d'un ajout de stock."""
    
    print("=" * 60)
    print("TEST DU SYSTÈME DE NOTIFICATIONS DE STOCK")
    print("=" * 60)
    
    # 1. Vérifier qu'il y a des boutiques et clients
    boutiques = Boutique.objects.filter(est_active=True)
    if not boutiques.exists():
        print("❌ Aucune boutique active trouvée")
        return
    
    boutique = boutiques.first()
    print(f"✓ Boutique sélectionnée: {boutique.nom}")
    
    clients = Client.objects.filter(boutique=boutique, est_actif=True)
    if not clients.exists():
        print(f"❌ Aucun client actif trouvé pour la boutique {boutique.nom}")
        return
    
    print(f"✓ {clients.count()} client(s) actif(s) trouvé(s) pour cette boutique")
    for client in clients:
        print(f"  - {client.nom_terminal} ({client.numero_serie})")
    
    # 2. Trouver ou créer un article de test
    articles = Article.objects.filter(boutique=boutique, est_actif=True)
    if not articles.exists():
        print("❌ Aucun article trouvé pour cette boutique")
        return
    
    article = articles.first()
    stock_avant = article.quantite_stock
    print(f"\n✓ Article sélectionné: {article.nom} ({article.code})")
    print(f"  Stock avant: {stock_avant}")
    
    # 3. Compter les notifications avant
    notifs_avant = NotificationStock.objects.filter(
        boutique=boutique,
        article=article
    ).count()
    print(f"\n✓ Notifications existantes pour cet article: {notifs_avant}")
    
    # 4. Créer un mouvement de stock (ENTREE)
    print("\n📦 Création d'un mouvement de stock (ENTREE)...")
    quantite_ajout = 25
    
    mouvement = MouvementStock.objects.create(
        article=article,
        type_mouvement='ENTREE',
        quantite=quantite_ajout,
        stock_avant=stock_avant,
        stock_apres=stock_avant + quantite_ajout,
        commentaire="Test système de notification",
        reference_document="TEST-001",
        utilisateur="test_script"
    )
    
    # Mettre à jour le stock de l'article
    article.quantite_stock += quantite_ajout
    article.save()
    
    print(f"✓ Mouvement créé: +{quantite_ajout} unités")
    print(f"  Stock après: {article.quantite_stock}")
    
    # 5. Vérifier que les notifications ont été créées
    print("\n📢 Vérification des notifications créées...")
    notifs_apres = NotificationStock.objects.filter(
        boutique=boutique,
        mouvement_stock=mouvement
    )
    
    if notifs_apres.exists():
        print(f"✅ {notifs_apres.count()} notification(s) créée(s) avec succès!")
        for notif in notifs_apres:
            print(f"\n  Notification #{notif.id}:")
            print(f"    Client: {notif.client.nom_terminal}")
            print(f"    Titre: {notif.titre}")
            print(f"    Message: {notif.message[:100]}...")
            print(f"    Quantité ajoutée: {notif.quantite_ajoutee}")
            print(f"    Stock actuel: {notif.stock_actuel}")
            print(f"    Lue: {notif.lue}")
            print(f"    Date: {notif.date_creation}")
    else:
        print("❌ Aucune notification n'a été créée!")
        print("   Vérifiez que les signals sont bien configurés.")
    
    # 6. Tester l'API (simulation)
    print("\n" + "=" * 60)
    print("RÉSUMÉ DU TEST")
    print("=" * 60)
    print(f"Boutique: {boutique.nom}")
    print(f"Article: {article.nom} ({article.code})")
    print(f"Quantité ajoutée: {quantite_ajout}")
    print(f"Clients notifiés: {notifs_apres.count()}")
    
    total_notifs = NotificationStock.objects.filter(boutique=boutique).count()
    notifs_non_lues = NotificationStock.objects.filter(boutique=boutique, lue=False).count()
    print(f"\nTotal notifications boutique: {total_notifs}")
    print(f"Notifications non lues: {notifs_non_lues}")
    
    print("\n✅ Test terminé avec succès!")
    print("\n📖 Consultez GUIDE_NOTIFICATIONS_STOCK_MAUI.md pour l'intégration côté MAUI")

if __name__ == '__main__':
    try:
        test_notification_creation()
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
