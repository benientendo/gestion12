import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.utils import timezone
from datetime import date
import pytz

from inventory.models import Boutique, Article, MouvementStock

BOUTIQUE_ID = 9
DATE_CIBLE = date.today()
KIN_TZ = pytz.timezone('Africa/Kinshasa')

print(f"=== VALEUR GLOBALE DU STOCK — BOUTIQUE ID {BOUTIQUE_ID} ===")
print(f"Date : {DATE_CIBLE}\n")

try:
    boutique = Boutique.objects.get(id=BOUTIQUE_ID)
    print(f"Boutique : {boutique.nom}\n")
except Boutique.DoesNotExist:
    print(f"ERREUR : Boutique ID {BOUTIQUE_ID} introuvable.")
    exit()

articles = Article.objects.filter(boutique=boutique, est_actif=True)

# --- Valeur ACTUELLE du stock ---
valeur_actuelle = 0
articles_avec_prix = 0
articles_sans_prix = 0

for a in articles:
    if a.prix_achat and a.prix_achat > 0:
        valeur_actuelle += a.quantite_stock * a.prix_achat
        articles_avec_prix += 1
    else:
        articles_sans_prix += 1

print(f"Articles actifs total       : {articles.count()}")
print(f"  - avec prix_achat défini  : {articles_avec_prix}")
print(f"  - sans prix_achat (=0)    : {articles_sans_prix}")
print(f"\nValeur actuelle du stock    : {valeur_actuelle:,.2f} FC")

# --- Mouvements ENTREE du jour ---
mouvements_jour = MouvementStock.objects.filter(
    article__boutique=boutique,
    date_mouvement__date=DATE_CIBLE,
    type_mouvement='ENTREE'
).order_by('date_mouvement')

print(f"\n--- Mouvements ENTREE du {DATE_CIBLE} ---")
total_gain_valeur = 0
total_unites_ajoutees = 0
details_mouvements = []

for m in mouvements_jour:
    prix = m.article.prix_achat or 0
    gain = m.quantite * prix
    total_gain_valeur += gain
    total_unites_ajoutees += m.quantite
    heure = m.date_mouvement.astimezone(KIN_TZ).strftime('%H:%M:%S')
    details_mouvements.append({
        'article': m.article.nom,
        'heure': heure,
        'quantite': m.quantite,
        'prix_achat': prix,
        'gain_valeur': gain,
        'stock_avant': m.stock_avant,
        'stock_apres': m.stock_apres,
    })
    print(f"  {heure} | {m.article.nom:<30} | +{m.quantite:>5} unités | prix_achat: {prix:>10,.2f} FC | gain valeur: +{gain:>12,.2f} FC")

print(f"\nTotal unités ajoutées       : +{total_unites_ajoutees}")
print(f"Total gain de valeur ajouts : +{total_gain_valeur:,.2f} FC")

# --- Valeur du stock AVANT les ajouts ---
valeur_avant_ajouts = valeur_actuelle - total_gain_valeur

# Note: cette estimation suppose que le stock actuel reflète exactement les ajouts
# (les ventes faites après les ajouts réduisent le stock mais pas la valeur calculée ici)
print(f"\n{'='*60}")
print(f"SYNTHESE")
print(f"{'='*60}")
print(f"Valeur stock AVANT ajouts   : {valeur_avant_ajouts:>18,.2f} FC")
print(f"Gain dû aux ajouts du jour  : {total_gain_valeur:>+18,.2f} FC")
print(f"Valeur stock ACTUELLE       : {valeur_actuelle:>18,.2f} FC")
print(f"{'='*60}")

if total_gain_valeur > 0:
    pct = (total_gain_valeur / valeur_avant_ajouts * 100) if valeur_avant_ajouts > 0 else 0
    print(f"Impact des ajouts sur stock : +{pct:.1f}%")
    print(f"\n✅ Les ajouts ont bien influencé le stock global.")
    if total_gain_valeur < (total_unites_ajoutees * 1):
        print(f"⚠️  Certains articles ajoutés n'ont pas de prix_achat (valeur = 0 FC pour eux).")
        print(f"   → Le gain réel est probablement supérieur à {total_gain_valeur:,.2f} FC.")
else:
    print(f"\n⚠️  Aucun impact sur la valeur (tous les articles ajoutés ont prix_achat = 0).")

# --- Articles ajoutés sans prix ---
print(f"\n--- Articles ajoutés SANS prix_achat (non comptabilisés) ---")
for d in details_mouvements:
    if d['prix_achat'] == 0:
        print(f"  ⚠️  {d['article']} : +{d['quantite']} unités — valeur non calculée (prix_achat = 0)")

print(f"\n=== FIN ===")
