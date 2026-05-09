import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from django.utils import timezone
from datetime import datetime, date
import pytz

from inventory.models import Boutique, Article, MouvementStock

BOUTIQUE_ID = 9
HEURE_CIBLE = "07:38"
DATE_CIBLE = date.today()

print(f"=== VERIFICATION STOCK — BOUTIQUE ID {BOUTIQUE_ID} ===")
print(f"Date : {DATE_CIBLE}  |  Heure cible : {HEURE_CIBLE}\n")

try:
    boutique = Boutique.objects.get(id=BOUTIQUE_ID)
    print(f"Boutique : {boutique.nom}\n")
except Boutique.DoesNotExist:
    print(f"ERREUR : Boutique ID {BOUTIQUE_ID} introuvable.")
    exit()

# Mots-clés des articles à chercher
mots_cles = ["itel", "lampe", "lamp"]

articles = Article.objects.filter(boutique=boutique, est_actif=True)
for mot in mots_cles:
    articles = articles.filter(nom__icontains=mot) | Article.objects.filter(boutique=boutique, est_actif=True, nom__icontains=mot)

# Dédupliquer
articles_itel = Article.objects.filter(
    boutique=boutique,
    est_actif=True,
    nom__icontains="itel"
)

print(f"Articles 'itel' trouvés dans la boutique : {articles_itel.count()}")
for a in articles_itel:
    print(f"  - [{a.id}] {a.nom}  |  stock actuel : {a.quantite_stock}  |  prix_achat : {a.prix_achat}  |  valeur stock : {a.quantite_stock * (a.prix_achat or 0):.2f}")

print("\n" + "="*60)
print(f"MOUVEMENTS DE STOCK DU {DATE_CIBLE} (articles itel)\n")

# Filtrer les mouvements du jour pour ces articles
mouvements = MouvementStock.objects.filter(
    article__in=articles_itel,
    date_mouvement__date=DATE_CIBLE,
    type_mouvement='ENTREE'
).order_by('date_mouvement')

if not mouvements.exists():
    print("Aucun mouvement ENTREE trouvé aujourd'hui pour les articles itel.")
else:
    for m in mouvements:
        prix_achat = m.article.prix_achat or 0
        valeur_avant = m.stock_avant * prix_achat
        valeur_apres = m.stock_apres * prix_achat
        heure_str = m.date_mouvement.astimezone(pytz.timezone('Africa/Kinshasa')).strftime('%H:%M:%S')
        print(f"  Article   : {m.article.nom}")
        print(f"  Heure     : {heure_str}")
        print(f"  Quantite  : +{m.quantite}")
        print(f"  Stock avant  : {m.stock_avant}  →  valeur avant  : {valeur_avant:.2f} FC")
        print(f"  Stock apres  : {m.stock_apres}  →  valeur apres  : {valeur_apres:.2f} FC")
        print(f"  Gain valeur  : +{valeur_apres - valeur_avant:.2f} FC")
        print(f"  Commentaire  : {m.commentaire or '-'}")
        print(f"  Ref doc      : {m.reference_document or '-'}")
        print("-" * 50)

print("\n=== FIN ===")
