"""Génère un aperçu HTML du procès-verbal d'inventaire (base de test éphémère).

Usage :
    python scripts/apercu_pv_inventaire.py
    → écrit _apercu_pv.html à la racine du projet
"""
import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..")))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gestion_magazin.settings")

import django  # noqa: E402
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import setup_test_environment  # noqa: E402
from django.urls import reverse  # noqa: E402

from django.db import connection  # noqa: E402

from inventory.models import (  # noqa: E402
    Article, Boutique, Commercant, Inventaire, LigneInventaire,
)

setup_test_environment()
old_config = connection.creation.create_test_db(verbosity=0)

try:
    User = get_user_model()
    user = User.objects.create_user(
        username="pv_apercu", password="x", email="pv_apercu@test.cd")
    commercant = Commercant.objects.create(
        nom_entreprise="PV SARL", nom_responsable="Gérant Propriétaire",
        email="pv_apercu@test.cd", user=user)
    boutique = Boutique.objects.create(
        nom="Boutique Aperçu", commercant=commercant, code_boutique="BT-APERCU-001")
    inventaire = Inventaire.objects.create(
        boutique=boutique, reference="INV-APERCU-001",
        date_inventaire=date.today(), statut="TERMINE", cree_par=user)

    donnees = [
        ("AP-A", "Savon parfumé 250g", "100", "200", 10, 12),
        ("AP-B", "Eponge ménagère", "50", "80", 8, 5),
        ("AP-C", "Balai sol", "20", "30", 4, None),
        ("AP-D", "Huile de palme 5L bidon", "4500", "5200", 20, 20),
        ("AP-E", "Riz local 25kg sac", "28000", "32000", 6, 4),
        ("AP-F", "Sucre en poudre 1kg", "1800", "2200", 15, 14),
        ("AP-G", "Farine de maïs 5kg", "6500", "7500", 9, 9),
        ("AP-H", "Lait concentré boîte", "1200", "1500", 30, 27),
    ]
    # Inventaire volumineux : N articles via argument (ex. 40)
    nb = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    noms = ["Savon", "Eponge", "Balai", "Huile", "Riz", "Sucre", "Farine",
            "Lait", "Café", "Thé", "Sel", "Poudre", "Jus", "Biscuit", "Riz",
            "Maïs", "Haricot", "Huile", "Sucre", "Lait"]
    for i in range(nb):
        donnees.append((
            "AP-%03d" % i,
            "%s n°%d conditionnement standard" % (noms[i % len(noms)], i),
            str(100 + i * 37), str(250 + i * 53),
            5 + (i % 17), None if i % 13 == 0 else 5 + (i % 17) - (i % 3),
        ))
    for code, nom, pa, pv, th, ph in donnees:
        art = Article.objects.create(
            boutique=boutique, code=code, nom=nom,
            prix_achat=Decimal(pa), prix_vente=Decimal(pv), quantite_stock=th)
        LigneInventaire.objects.create(
            inventaire=inventaire, article=art,
            stock_theorique=th, stock_physique=ph, prix_unitaire=Decimal(pa))

    inventaire.calculer_statistiques()
    inventaire.refresh_from_db()

    client = Client()
    client.force_login(user)
    url = reverse("inventory:imprimer_inventaire_boutique",
                  args=[boutique.id, inventaire.id])
    resp = client.get(url)
    assert resp.status_code == 200, resp.status_code

    out = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "_apercu_pv.html"))
    with open(out, "w", encoding="utf-8") as f:
        f.write(resp.content.decode("utf-8"))
    print("OK", out)
finally:
    connection.creation.destroy_test_db(old_config, verbosity=0)
