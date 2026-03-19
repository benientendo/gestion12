"""
Test WebSocket - vérifie que Daphne + Channels fonctionne sur Scalingo
Usage: python test_websocket.py
"""
import asyncio
import websockets
import json

BASE_URL = "wss://gestionnumerique.osc-fr1.scalingo.io"
BOUTIQUE_ID = 44

# Numéro de série d'un terminal existant (changer si nécessaire)
# Laisser vide pour tester le NotificationConsumer (sans auth)
NUMERO_SERIE = "MESSIENOVA"


async def test_notification_consumer():
    """Test NotificationConsumer — pas d'authentification requise"""
    url = f"{BASE_URL}/ws/notifications/{BOUTIQUE_ID}/"
    print(f"\n📡 Test NotificationConsumer: {url}")
    try:
        async with websockets.connect(url, ping_interval=None) as ws:
            print("✅ Connexion WebSocket établie (NotificationConsumer)")
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                print(f"📩 Message reçu: {json.dumps(data, indent=2)}")
            except asyncio.TimeoutError:
                print("⏱️  Aucun message reçu (normal - en attente d'événements)")
            print("✅ NotificationConsumer OK\n")
            return True
    except Exception as e:
        print(f"❌ Erreur NotificationConsumer: {e}\n")
        return False


async def test_boutique_consumer(numero_serie):
    """Test BoutiqueConsumer — nécessite un X-Device-Serial valide"""
    url = f"{BASE_URL}/ws/boutique/{BOUTIQUE_ID}/"
    headers = {"X-Device-Serial": numero_serie}
    print(f"📡 Test BoutiqueConsumer: {url}")
    print(f"   Terminal: {numero_serie}")
    try:
        async with websockets.connect(url, additional_headers=headers, ping_interval=None) as ws:
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            if data.get("type") == "connection_established":
                print(f"✅ BoutiqueConsumer connecté: {data['message']}")
                # Test ping/pong
                await ws.send(json.dumps({"type": "ping"}))
                pong = await asyncio.wait_for(ws.recv(), timeout=3)
                pong_data = json.loads(pong)
                if pong_data.get("type") == "pong":
                    print("✅ Ping/Pong OK")
                return True
            else:
                print(f"⚠️  Réponse inattendue: {data}")
                return False
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"❌ Connexion refusée (terminal non autorisé?): {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur BoutiqueConsumer: {e}")
        return False


async def main():
    print("=" * 50)
    print("  TEST WEBSOCKET — gestionnumerique Scalingo")
    print("=" * 50)

    # Test 1: NotificationConsumer (sans auth)
    ok1 = await test_notification_consumer()

    # Test 2: BoutiqueConsumer (avec numéro de série)
    if NUMERO_SERIE:
        ok2 = await test_boutique_consumer(NUMERO_SERIE)
    else:
        print("ℹ️  BoutiqueConsumer non testé (NUMERO_SERIE vide)")
        print("   → Mets le numéro de série d'un terminal dans NUMERO_SERIE\n")
        ok2 = None

    print("=" * 50)
    print("RÉSULTATS:")
    print(f"  NotificationConsumer : {'✅ OK' if ok1 else '❌ FAILED'}")
    if ok2 is not None:
        print(f"  BoutiqueConsumer     : {'✅ OK' if ok2 else '❌ FAILED'}")
    else:
        print(f"  BoutiqueConsumer     : ⏭️  non testé")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
