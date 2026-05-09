import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from datetime import date
import pytz
from inventory.models import Boutique, Article, MouvementStock

BOUTIQUE_ID = 9
DATE_CIBLE = date.today()
KIN_TZ = pytz.timezone('Africa/Kinshasa')

print(f"=== VALEUR STOCK (prix_vente × quantite) — BOUTIQUE ID {BOUTIQUE_ID} ===")
print(f"Date : {DATE_CIBLE}\n")

boutique = Boutique.objects.get(id=BOUTIQUE_ID)
print(f"Boutique : {boutique.nom}\n")

articles = Article.objects.filter(boutique=boutique, est_actif=True)

# Mouvements ENTREE du jour : on récupère les quantités ajoutées par article
mouvements_jour = MouvementStock.objects.filter(
    article__boutique=boutique,
    date_mouvement__date=DATE_CIBLE,
    type_mouvement='ENTREE'
).order_by('date_mouvement')

# Construire un dict : article_id -> quantite totale ajoutée aujourd'hui
ajouts_du_jour = {}
for m in mouvements_jour:
    ajouts_du_jour[m.article_id] = ajouts_du_jour.get(m.article_id, 0) + m.quantite

# Calcul valeur ACTUELLE et valeur AVANT ajouts (prix_vente × stock)
valeur_actuelle_total = 0
valeur_avant_total = 0
nb_avec_prix = 0
nb_sans_prix = 0

for a in articles:
    pv = a.prix_vente or 0
    stock_actuel = a.quantite_stock
    ajout = ajouts_du_jour.get(a.id, 0)
    stock_avant = stock_actuel - ajout  # stock reconstruit avant ajout du jour

    valeur_actuelle = stock_actuel * pv
    valeur_avant = stock_avant * pv

    valeur_actuelle_total += valeur_actuelle
    valeur_avant_total += valeur_avant

    if pv > 0:
        nb_avec_prix += 1
    else:
        nb_sans_prix += 1

# Calcul du gain
gain_total = valeur_actuelle_total - valeur_avant_total

print(f"Articles actifs              : {articles.count()}")
print(f"  - avec prix_vente défini   : {nb_avec_prix}")
print(f"  - sans prix_vente (=0)     : {nb_sans_prix}")

print(f"\n{'='*60}")
print(f"  SYNTHESE VALEUR STOCK (base : prix_vente)")
print(f"{'='*60}")
print(f"  Valeur stock AVANT ajouts  : {valeur_avant_total:>20,.2f} FC")
print(f"  Gain dû aux ajouts du jour : {gain_total:>+20,.2f} FC")
print(f"  Valeur stock ACTUELLE      : {valeur_actuelle_total:>20,.2f} FC")
print(f"{'='*60}")

if valeur_avant_total > 0:
    pct = gain_total / valeur_avant_total * 100
    print(f"  Impact des ajouts          : {pct:>+19.2f}%")

# Détail des articles ajoutés ce matin
print(f"\n--- Détail des articles ajoutés le {DATE_CIBLE} ---")
for m in mouvements_jour:
    pv = m.article.prix_vente or 0
    heure = m.date_mouvement.astimezone(KIN_TZ).strftime('%H:%M:%S')
    val_avant = m.stock_avant * pv
    val_apres = m.stock_apres * pv
    gain = val_apres - val_avant
    status = "✅" if pv > 0 else "⚠️  prix_vente=0"
    print(f"  {heure} | {m.article.nom:<28} | +{m.quantite:>4}u "
          f"| pv={pv:>8,.0f} FC "
          f"| avant={val_avant:>12,.0f} FC → après={val_apres:>12,.0f} FC "
          f"| gain={gain:>+12,.0f} FC {status}")

print(f"\n=== FIN ===")
