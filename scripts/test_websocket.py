#!/usr/bin/env python
"""
Script de test WebSocket
Teste la connexion WebSocket et affiche les messages reçus
"""
import asyncio
import websockets
import json
import sys

async def test_websocket(server_url, boutique_id, numero_serie):
    """Tester la connexion WebSocket"""
    uri = f"{server_url}/ws/boutique/{boutique_id}/"
    
    print(f"🔌 Connexion à {uri}...")
    print(f"📱 Numéro de série: {numero_serie}")
    
    try:
        # Headers avec numéro de série
        headers = {
            'X-Device-Serial': numero_serie
        }
        
        async with websockets.connect(uri, extra_headers=headers) as websocket:
            print("✅ Connecté avec succès!")
            print("📥 En attente de messages...\n")
            
            # Envoyer un ping initial
            await websocket.send(json.dumps({'type': 'ping'}))
            
            # Écouter les messages
            while True:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    # Afficher le message avec formatage
                    message_type = data.get('type', 'unknown')
                    
                    if message_type == 'connection_established':
                        print("✅ Connexion établie par le serveur")
                        print(f"   Message: {data.get('message')}")
                        print(f"   Boutique: {data.get('boutique_id')}")
                        print(f"   Timestamp: {data.get('timestamp')}\n")
                    
                    elif message_type == 'pong':
                        print("🏓 Pong reçu (connexion active)\n")
                    
                    elif message_type == 'article_updated':
                        article = data.get('article', {})
                        print("📦 Article mis à jour:")
                        print(f"   ID: {article.get('id')}")
                        print(f"   Nom: {article.get('nom')}")
                        print(f"   Prix: {article.get('prix_vente')} {article.get('devise')}")
                        print(f"   Stock: {article.get('quantite_stock')}")
                        print(f"   Version: {article.get('version')}\n")
                    
                    elif message_type == 'article_created':
                        article = data.get('article', {})
                        print("✨ Nouvel article créé:")
                        print(f"   ID: {article.get('id')}")
                        print(f"   Nom: {article.get('nom')}")
                        print(f"   Prix: {article.get('prix_vente')} {article.get('devise')}\n")
                    
                    elif message_type == 'article_deleted':
                        print("🗑️ Article supprimé:")
                        print(f"   ID: {data.get('article_id')}\n")
                    
                    elif message_type == 'stock_updated':
                        print("📊 Stock mis à jour:")
                        print(f"   Article ID: {data.get('article_id')}")
                        print(f"   Nouveau stock: {data.get('new_stock')}\n")
                    
                    elif message_type == 'price_updated':
                        print("💰 Prix mis à jour:")
                        print(f"   Article ID: {data.get('article_id')}")
                        print(f"   Nouveau prix: {data.get('new_price')} {data.get('devise')}\n")
                    
                    elif message_type == 'category_updated':
                        category = data.get('category', {})
                        print("📁 Catégorie mise à jour:")
                        print(f"   ID: {category.get('id')}")
                        print(f"   Nom: {category.get('nom')}\n")
                    
                    elif message_type == 'sync_required':
                        print("🔄 Synchronisation requise:")
                        print(f"   Raison: {data.get('reason')}\n")
                    
                    else:
                        print(f"📥 Message reçu ({message_type}):")
                        print(f"   {json.dumps(data, indent=2)}\n")
                
                except websockets.exceptions.ConnectionClosed:
                    print("❌ Connexion fermée par le serveur")
                    break
                except KeyboardInterrupt:
                    print("\n🛑 Arrêt demandé par l'utilisateur")
                    break
                except Exception as e:
                    print(f"❌ Erreur: {e}")
                    break
    
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        return False
    
    return True

if __name__ == "__main__":
    # Configuration par défaut
    SERVER_URL = "ws://192.168.52.224:8000"
    BOUTIQUE_ID = "2"
    NUMERO_SERIE = "POS-TEST-001"
    
    # Arguments en ligne de commande
    if len(sys.argv) > 1:
        SERVER_URL = sys.argv[1]
    if len(sys.argv) > 2:
        BOUTIQUE_ID = sys.argv[2]
    if len(sys.argv) > 3:
        NUMERO_SERIE = sys.argv[3]
    
    print("=" * 60)
    print("🧪 TEST WEBSOCKET - GESTION MAGAZIN")
    print("=" * 60)
    print(f"Serveur: {SERVER_URL}")
    print(f"Boutique: {BOUTIQUE_ID}")
    print(f"Numéro série: {NUMERO_SERIE}")
    print("=" * 60)
    print("\n💡 Modifiez un article dans Django pour voir les mises à jour")
    print("💡 Appuyez sur Ctrl+C pour arrêter\n")
    
    # Lancer le test
    asyncio.run(test_websocket(SERVER_URL, BOUTIQUE_ID, NUMERO_SERIE))
