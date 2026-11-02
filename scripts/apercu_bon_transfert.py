"""Génère un aperçu HTML du bon de transfert (base de test éphémère).

Usage :
    python scripts/apercu_bon_transfert.py        # 8 articles
    python scripts/apercu_bon_transfert.py 40     # 40 articles (test pagination)
    → écrit _apercu_bon.html à la racine du projet
"""
import os
import sys
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
    Article, Boutique, Commercant, TransfertStock,
)

setup_test_environment()
old_config = connection.creation.create_test_db(verbosity=0)

try:
    User = get_user_model()
    user = User.objects.create_user(
        username="bon_apercu", password="x", email="bon_apercu@test.cd")
    commercant = Commercant.objects.create(
        nom_entreprise="Transfert SARL", nom_responsable="Gérant Propriétaire",
        email="bon_apercu@test.cd", user=user)
    depot = Boutique.objects.create(
        nom="Dépôt Central", commercant=commercant, est_depot=True,
        code_boutique="DP-APERCU-001", adresse="12 av. du Commerce",
        ville="Kinshasa")
    boutique = Boutique.objects.create(
        nom="Boutique Nord", commercant=commercant,
        code_boutique="BT-APERCU-001", adresse="45 blvd du Marché",
        ville="Kinshasa")

    nb = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    noms = ["Savon", "Eponge", "Balai", "Huile", "Riz", "Sucre", "Farine",
            "Lait", "Café", "Thé", "Sel", "Poudre", "Jus", "Biscuit",
            "Maïs", "Haricot"]
    ref = "LOT-APERCU-001"
    for i in range(nb):
        art = Article.objects.create(
            boutique=depot,
            code="TR-%03d" % i,
            nom="%s n°%d conditionnement standard" % (noms[i % len(noms)], i),
            prix_achat=Decimal(100 + i * 37),
            prix_vente=Decimal(250 + i * 53),
            quantite_stock=50,
        )
        TransfertStock.objects.create(
            article=art, depot_source=depot, boutique_destination=boutique,
            quantite=1 + (i % 9), effectue_par="Agent Dépôt",
            valide_par="Gérant Propriétaire", statut="VALIDE",
            reference_lot=ref,
            commentaire=("Livraison complète, colis vérifiés à réception."
                         if i == 0 else ""))

    client = Client()
    client.force_login(user)
    url = reverse("inventory:bon_transfert", args=[depot.id, ref])
    resp = client.get(url)
    assert resp.status_code == 200, resp.status_code

    out = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "_apercu_bon.html"))
    with open(out, "w", encoding="utf-8") as f:
        f.write(resp.content.decode("utf-8"))
    print("OK", out)
finally:
    connection.creation.destroy_test_db(old_config, verbosity=0)
