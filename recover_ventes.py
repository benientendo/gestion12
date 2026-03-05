import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from inventory.models import Vente, VenteRejetee, Boutique, Article, LigneVente, AlerteStock, VarianteArticle
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import json

print("=== RECUPERATION VENTES REJETEES KMC KIMPESE 01 - CE MATIN ===")
boutique = Boutique.objects.filter(nom='KMC KIMPESE 01').first()

if not boutique:
    print("Boutique KMC KIMPESE 01 non trouvee")
    exit()

print(f"Boutique: {boutique.nom} (ID: {boutique.id})")

# Recuperer les ventes rejetees d'aujourd'hui non traitees
today = timezone.now().date()
rejets = VenteRejetee.objects.filter(
    boutique=boutique,
    date_tentative__date=today,
    traitee=False
).order_by('date_tentative')

print(f"Ventes rejetees a recuperer: {rejets.count()}")

recovered = 0
for r in rejets:
    print(f"\n--- Traitement {r.vente_uid} ---")
    
    print(f"  donnees_vente type: {type(r.donnees_vente)}")
    print(f"  article_concerne_nom: {r.article_concerne_nom}")
    print(f"  stock_disponible: {r.stock_disponible}, stock_demande: {r.stock_demande}")
    
    # donnees_vente peut etre un dict (JSONField) ou une string
    if isinstance(r.donnees_vente, dict):
        data = r.donnees_vente
    elif isinstance(r.donnees_vente, str):
        try:
            data = json.loads(r.donnees_vente)
        except:
            data = {}
    else:
        data = {}
    
    print(f"  data keys: {data.keys() if data else 'VIDE'}")
    
    # Verifier si la vente existe deja
    if Vente.objects.filter(numero_facture=r.vente_uid).exists():
        print(f"  SKIP: Vente {r.vente_uid} existe deja")
        r.traitee = True
        r.notes_traitement = "Vente deja existante"
        r.save()
        continue
    
    with transaction.atomic():
        # Creer la vente
        vente = Vente.objects.create(
            numero_facture=r.vente_uid,
            boutique=boutique,
            client_maui=r.terminal,
            montant_total=Decimal(str(data.get('montant_total', 0))),
            date_vente=r.date_tentative,
            paye=data.get('paye', True),
            est_annulee=False
        )
        print(f"  Vente creee: {vente.numero_facture} - {vente.montant_total} CDF")
        
        # Creer les lignes de vente
        lignes = data.get('lignes', [])
        for ligne_data in lignes:
            article_id = ligne_data.get('article_id') or ligne_data.get('article')
            variante_id = ligne_data.get('variante_id') or ligne_data.get('variante')
            quantite = int(ligne_data.get('quantite', 1))
            prix_unitaire = Decimal(str(ligne_data.get('prix_unitaire', 0)))
            
            article = None
            variante = None
            
            if article_id:
                article = Article.objects.filter(id=article_id).first()
            if variante_id:
                variante = VarianteArticle.objects.filter(id=variante_id).first()
                if variante and not article:
                    article = variante.article
            
            if not article:
                print(f"    WARN: Article {article_id} non trouve, ligne ignoree")
                continue
            
            # Creer la ligne de vente
            LigneVente.objects.create(
                vente=vente,
                article=article,
                variante=variante,
                quantite=quantite,
                prix_unitaire=prix_unitaire
            )
            
            # Determiner le stock actuel
            if variante:
                stock_avant = variante.quantite_stock
                nom_complet = f"{article.nom} - {variante.nom_variante}"
            else:
                stock_avant = article.quantite_stock
                nom_complet = article.nom
            
            # Ne pas modifier le stock - juste creer une alerte si necessaire
            if stock_avant < quantite:
                AlerteStock.objects.create(
                    boutique=boutique,
                    vente=vente,
                    terminal=r.terminal,
                    article=article,
                    variante=variante,
                    quantite_vendue=quantite,
                    stock_serveur_avant=stock_avant,
                    stock_serveur_apres=max(0, stock_avant - quantite),
                    ecart=quantite - stock_avant,
                    statut='EN_ATTENTE'
                )
                print(f"    AlerteStock: {nom_complet} (ecart: {quantite - stock_avant})")
            
            print(f"    Ligne: {nom_complet} x{quantite} @ {prix_unitaire}")
        
        # Marquer le rejet comme traite
        r.traitee = True
        r.date_traitement = timezone.now()
        r.notes_traitement = f"Converti en vente {vente.id} avec AlerteStock"
        r.save()
        
        recovered += 1
        print(f"  OK: Vente recuperee!")

print(f"\n=== RESULTAT ===")
print(f"Ventes recuperees: {recovered}/{rejets.count()}")
