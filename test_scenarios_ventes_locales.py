# -*- coding: utf-8 -*-
"""
Scénarios de test des ventes contre le backend LOCAL Django (boutique DADIER).
Simule exactement ce que fait l'app MAUI (headers X-Device-Serial, payloads v2 simple).

Usage : python test_scenarios_ventes_locales.py
"""
import subprocess
import sys
import time
import requests

BASE = "http://127.0.0.1:8000"
SERIAL = "MESSIENOVA"
BOUTIQUE = 12
H = {"X-Device-Serial": SERIAL, "Content-Type": "application/json"}
SUFFIXE = time.strftime("%H%M%S")

ARTICLE_SIMPLE = {"id": 121, "nom": "TOMATE", "code": "ART-1E0F9183", "pv": 7000}
PARENT_VARIANTE = {"id": 207, "nom": "TEST-VARIANT", "stock_initial": 57, "pv": 700}
VARIANTE = {"id": 12, "nom": "FIESTA1", "cb": "6009879794670"}
VARIANTE2 = {"id": 13, "nom": "FESTA2", "cb": "5449000052926"}

pass_count, fail_count = 0, 0


def check(name, ok, detail=""):
    global pass_count, fail_count
    status = "OK  " if ok else "ECHEC"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    if ok:
        pass_count += 1
    else:
        fail_count += 1


def shell(sql):
    """Exécute une commande Django et retourne la sortie."""
    r = subprocess.run(
        ["python", "manage.py", "shell", "-c", sql],
        capture_output=True, text=True, encoding="utf-8", cwd=".", timeout=60,
    )
    return (r.stdout or "") + (r.stderr or "")


def nettoyer_ventes_test():
    """Supprime toutes les ventes TEST-% NON annulees et restaure les stocks.
    Les ventes annulees sont ignorees (leur stock a deja ete restaure a l'annulation)."""
    shell(
        "from inventory.models import Vente, LigneVente, MouvementStock\n"
        "for v in Vente.objects.filter(numero_facture__startswith='TEST-').exclude(est_annulee=True):\n"
        "    for l in LigneVente.objects.filter(vente=v):\n"
        "        a = l.article\n"
        "        a.quantite_stock += l.quantite\n"
        "        a.save(update_fields=['quantite_stock'])\n"
        "    MouvementStock.objects.filter(reference_document=v.numero_facture).delete()\n"
        "    LigneVente.objects.filter(vente=v).delete()\n"
        "    v.delete()\n"
    )


def get_stock(article_id):
    r = requests.get(f"{BASE}/api/v2/simple/articles/?boutique_id={BOUTIQUE}", headers=H, timeout=15)
    r.raise_for_status()
    for a in r.json().get("articles", []):
        if a["id"] == article_id:
            return a.get("quantite_stock")
    return None


def creer_vente(lignes, numero_facture=None, attendu=201):
    payload = {"boutique_id": BOUTIQUE, "lignes": lignes}
    if numero_facture:
        payload["numero_facture"] = numero_facture
    r = requests.post(f"{BASE}/api/v2/simple/ventes/", json=payload, headers=H, timeout=15)
    if r.status_code == attendu:
        return r.json()
    print(f"      !! vente inattendue: {r.status_code} {r.text[:300]}")
    return None


print("=" * 72)
print("SCENARIOS DE VENTE — Backend local Django (boutique DADIER)")
print("=" * 72)

# ── Nettoyage des restes éventuels ──
print("\nNettoyage des ventes de test precedentes...")
nettoyer_ventes_test()

stock_simple_avant = get_stock(ARTICLE_SIMPLE["id"])
stock_variant_avant = get_stock(PARENT_VARIANTE["id"])
print(f"Stocks initiaux: {ARTICLE_SIMPLE['nom']}={stock_simple_avant} | "
      f"{PARENT_VARIANTE['nom']}(parent)={stock_variant_avant}")

# ── S1: Vente article simple (scan code-barres) ──
print("\n── S1: Vente article SIMPLE (2 x TOMATE @ 7000) ──")
f1 = f"TEST-S1-{SUFFIXE}"
v1 = creer_vente([{"article_id": ARTICLE_SIMPLE["id"], "quantite": 2,
                   "prix_unitaire": ARTICLE_SIMPLE["pv"]}], numero_facture=f1)
check("Vente simple creee (201)", v1 is not None, f"facture={f1}")
if v1:
    check("Montant total correct (14000)",
          str(v1["vente"]["montant_total"]) in ("14000", "14000.00"),
          f"montant={v1['vente']['montant_total']}")
    check("Stock decremente (116 -> 114)", get_stock(ARTICLE_SIMPLE["id"]) == stock_simple_avant - 2,
          f"stock={get_stock(ARTICLE_SIMPLE['id'])}")

# ── S2: Vente avec VARIANTE (scan code-barres variante) ──
print("\n── S2: Vente avec VARIANTE (3 x FIESTA1 @ 700) ──")
f2 = f"TEST-S2-{SUFFIXE}"
v2 = creer_vente([{"article_id": PARENT_VARIANTE["id"], "variante_id": VARIANTE["id"],
                   "quantite": 3, "prix_unitaire": PARENT_VARIANTE["pv"]}], numero_facture=f2)
check("Vente variante creee (201)", v2 is not None)
if v2:
    check("Stock PARENT decremente (57 -> 54)",
          get_stock(PARENT_VARIANTE["id"]) == stock_variant_avant - 3,
          f"stock parent={get_stock(PARENT_VARIANTE['id'])}")
    out = shell(
        "from inventory.models import LigneVente\n"
        f"print(LigneVente.objects.filter(vente__numero_facture='{f2}', variante_id={VARIANTE['id']}).exists())"
    )
    check("Variante bien liee a la ligne (base de donnees)", "True" in out, out.strip()[-30:])

# ── S3: Sync batch offline-first (PascalCase, comme MAUI) ──
print("\n── S3: Sync batch offline (1 simple + 1 variante, payload MAUI) ──")
f3a, f3b = f"TEST-S3A-{SUFFIXE}", f"TEST-S3B-{SUFFIXE}"
batch = {
    "PosId": SERIAL,
    "Ventes": [
        {
            "VenteUid": f3a, "Date": time.strftime("%Y-%m-%dT%H:%M:%S+01:00"),
            "Total": 7000, "Devise": "CDF", "ModePaiement": "CASH",
            "Items": [{"ArticleId": ARTICLE_SIMPLE["id"], "Quantite": 1,
                       "PrixUnitaire": ARTICLE_SIMPLE["pv"]}],
        },
        {
            "VenteUid": f3b, "Date": time.strftime("%Y-%m-%dT%H:%M:%S+01:00"),
            "Total": 1400, "Devise": "CDF", "ModePaiement": "CASH",
            "Items": [{"ArticleId": PARENT_VARIANTE["id"], "VarianteId": VARIANTE2["id"],
                       "Quantite": 2, "PrixUnitaire": PARENT_VARIANTE["pv"]}],
        },
    ],
}
r3 = requests.post(f"{BASE}/api/v2/simple/ventes/sync/", json=batch, headers=H, timeout=30)
j3 = r3.json() if r3.status_code in (200, 201) else {}
check("Sync batch accepte (200/201)", r3.status_code in (200, 201),
      f"accepted={j3.get('accepted')} rejected={j3.get('rejected')}")
if r3.status_code in (200, 201):
    check("2 ventes acceptees", len(j3.get("accepted", [])) == 2,
          f"accepted={j3.get('accepted')}")
    check("Stock TOMATE decremente (114 -> 113)", get_stock(ARTICLE_SIMPLE["id"]) == stock_simple_avant - 3,
          f"stock={get_stock(ARTICLE_SIMPLE['id'])}")
    check("Stock parent decremente (54 -> 52)", get_stock(PARENT_VARIANTE["id"]) == stock_variant_avant - 5,
          f"stock={get_stock(PARENT_VARIANTE['id'])}")

# ── S4: Prix negatif rejete (securite) ──
print("\n── S4: Prix negatif refuse par le serveur ──")
r4 = requests.post(f"{BASE}/api/v2/simple/ventes/", headers=H, timeout=15, json={
    "boutique_id": BOUTIQUE,
    "lignes": [{"article_id": ARTICLE_SIMPLE["id"], "quantite": 1, "prix_unitaire": -500}],
})
check("Prix negatif rejete (400)", r4.status_code == 400,
      f"code={r4.json().get('code') if r4.status_code == 400 else r4.status_code}")

# ── S5: Annulation vente + restauration stock ──
print("\n── S5: Annulation de la vente S1 ──")
if v1:
    r5 = requests.post(f"{BASE}/api/v2/simple/ventes/annuler/", headers=H, timeout=15,
                       json={"numero_facture": f1, "motif": "Test annulation"})
    check("Annulation acceptee", r5.status_code in (200, 201), str(r5.text)[:120])
    # S3A (1 TOMATE) est encore active a ce stade -> stock attendu = initial - 1
    check("Stock restaure (114 -> 115)", get_stock(ARTICLE_SIMPLE["id"]) == stock_simple_avant - 1,
          f"stock={get_stock(ARTICLE_SIMPLE['id'])} (attendu {stock_simple_avant - 1})")

# ── S6: Coherence du journal valeur stock (jour) ──
print("\n── S6: Coherence du journal de valeur de stock (jour) ──")
r6 = requests.get(f"{BASE}/api/v2/simple/journal-valeur-stock/?boutique_id={BOUTIQUE}",
                  headers=H, timeout=15)
j6 = r6.json() if r6.status_code == 200 else {}
lignes = j6.get("journal", []) or j6.get("lignes", []) or []
if lignes:
    ligne = lignes[0]
    def dec(v):
        return float(str(v or 0))
    calc = (dec(ligne["valeur_stock_precedent"]) + dec(ligne["montant_inventaire"])
            + dec(ligne["valeur_stock_ajoute"]) + dec(ligne["valeur_transfert_entrant"])
            + dec(ligne["impact_modification_prix"]) - dec(ligne["valeur_stock_sorti"])
            - dec(ligne["valeur_transfert_sortant"]) - dec(ligne["valeur_ventes"]))
    check("Formule du journal coherente", abs(calc - dec(ligne["valeur_stock_restant"])) < 0.01,
          f"restant={ligne['valeur_stock_restant']} calcule={round(calc, 2)}")
else:
    check("Journal disponible (API)", False, str(r6.text)[:150])

# ── Nettoyage final ──
print("\n── Nettoyage final (suppression ventes de test, stocks restaures) ──")
nettoyer_ventes_test()
fin1, fin2 = get_stock(ARTICLE_SIMPLE["id"]), get_stock(PARENT_VARIANTE["id"])
check("Stocks restaures apres nettoyage",
      fin1 == stock_simple_avant and fin2 == stock_variant_avant,
      f"TOMATE={fin1} (attendu {stock_simple_avant}) | VARIANT={fin2} (attendu {stock_variant_avant})")

print("\n" + "=" * 72)
print(f"RESULTAT: {pass_count} OK / {fail_count} ECHEC")
print("=" * 72)
sys.exit(1 if fail_count else 0)
