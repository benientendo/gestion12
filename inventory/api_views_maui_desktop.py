"""
API pour le client MAUI Windows (Desktop)
==========================================
Endpoints pour:
- Authentification du commerçant
- Liste des boutiques
- Réception des factures d'approvisionnement depuis MAUI
"""

import json
import logging
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import authenticate
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import (
    Commercant, Boutique, Article, Categorie, Fournisseur,
    FactureApprovisionnement, LigneApprovisionnement, MouvementStock,
)

logger = logging.getLogger(__name__)


# ===== AUTHENTIFICATION =====

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@parser_classes([JSONParser])
def auth_commercant(request):
    """
    Authentifier un commerçant depuis MAUI Windows.
    
    Body JSON:
    {
        "username": "horizon",
        "mot_de_passe": "password123"
    }
    
    Retourne:
    {
        "success": true,
        "token": "xxx",
        "commercant": { "id": 1, "nom": "...", "email": "..." },
        "boutiques": [ { "id": 1, "nom": "...", "code": "...", "type": "..." } ]
    }
    """
    data = request.data
    if not data:
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            data = {}

    username = data.get('username', '').strip()
    mot_de_passe = data.get('mot_de_passe', '')

    if not username or not mot_de_passe:
        return Response({
            'success': False,
            'error': 'Nom d\'utilisateur et mot de passe requis'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Authentifier via Django User
    user = authenticate(username=username, password=mot_de_passe)
    if user is None:
        return Response({
            'success': False,
            'error': 'Email ou mot de passe incorrect'
        }, status=status.HTTP_401_UNAUTHORIZED)

    # Vérifier que c'est un commerçant
    try:
        commercant = Commercant.objects.get(user=user, est_actif=True)
    except Commercant.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Ce compte n\'est pas associé à un commerçant'
        }, status=status.HTTP_403_FORBIDDEN)

    # Générer un token simple (UUID du commerçant)
    token = str(commercant.user.id)

    # Lister les boutiques actives
    boutiques = Boutique.objects.filter(
        commercant=commercant,
        est_active=True
    ).values('id', 'nom', 'code_boutique', 'type_commerce', 'devise', 'est_depot')

    return Response({
        'success': True,
        'token': token,
        'commercant': {
            'id': commercant.id,
            'nom_entreprise': commercant.nom_entreprise,
            'nom_responsable': commercant.nom_responsable,
            'email': commercant.email,
            'taux_dollar': float(commercant.taux_dollar),
        },
        'boutiques': list(boutiques),
    })


# ===== BOUTIQUES =====

@csrf_exempt
@api_view(['GET'])
@permission_classes([AllowAny])
def boutiques_commercant(request):
    """
    Lister les boutiques du commerçant connecté.
    
    Header: Authorization: <user_id>
    """
    user_id = _get_user_id(request)
    if user_id is None:
        return Response({'error': 'Authentification requise'}, status=401)

    try:
        commercant = Commercant.objects.get(user_id=user_id, est_actif=True)
    except Commercant.DoesNotExist:
        return Response({'error': 'Commerçant non trouvé'}, status=404)

    boutiques = Boutique.objects.filter(
        commercant=commercant,
        est_active=True
    ).values('id', 'nom', 'code_boutique', 'type_commerce', 'devise', 'est_depot', 'adresse', 'ville')

    return Response({
        'success': True,
        'boutiques': list(boutiques),
    })


# ===== CATÉGORIES =====

@csrf_exempt
@api_view(['GET'])
@permission_classes([AllowAny])
def categories_boutique(request):
    """
    Lister les catégories d'une boutique.
    
    Query: boutique_id=1
    """
    boutique_id = request.query_params.get('boutique_id')
    if not boutique_id:
        return Response({'error': 'boutique_id requis'}, status=400)

    categories = Categorie.objects.filter(boutique_id=boutique_id).values('id', 'nom')
    return Response({'success': True, 'categories': list(categories)})


# ===== RÉCEPTION FACTURE APPROVISIONNEMENT =====

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@parser_classes([JSONParser])
def recevoir_facture(request):
    """
    Recevoir une facture d'approvisionnement depuis MAUI Windows.
    
    Crée:
    - FactureApprovisionnement
    - LigneApprovisionnement pour chaque article
    - Article (si nouveau) ou met à jour le stock
    - MouvementStock pour traçabilité
    
    Body JSON:
    {
        "boutique_id": 1,
        "numero_facture": "FACT-20260920-1234",
        "fournisseur_nom": "Kibali Supplies",
        "date_facture": "2026-09-20",
        "devise": "CDF",
        "taux_dollar": 2800,
        "notes": "...",
        "lignes": [
            {
                "nom": "Riz 5kg",
                "categorie": "Alimentaire",
                "nb_cartons": 10,
                "pcs_carton": 20,
                "pcs_sup": 5,
                "qte_unites": 205,
                "prix_achat_carton": 50000,
                "prix_achat_unitaire": 2500,
                "prix_vente": 3500
            }
        ]
    }
    """
    user_id = _get_user_id(request)
    if user_id is None:
        return Response({'error': 'Authentification requise'}, status=401)

    try:
        commercant = Commercant.objects.get(user_id=user_id, est_actif=True)
    except Commercant.DoesNotExist:
        return Response({'error': 'Commerçant non trouvé'}, status=404)

    data = request.data
    if not data:
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            data = {}
    boutique_id = data.get('boutique_id')
    numero_facture = data.get('numero_facture', '').strip()
    fournisseur_nom = data.get('fournisseur_nom', '').strip()
    date_facture = data.get('date_facture')
    devise = data.get('devise', 'CDF')
    taux_dollar = data.get('taux_dollar', 2800)
    notes = data.get('notes', '')
    lignes = data.get('lignes', [])

    # Validations
    if not boutique_id:
        return Response({'error': 'boutique_id requis'}, status=400)
    if not numero_facture:
        return Response({'error': 'numero_facture requis'}, status=400)
    if not date_facture:
        return Response({'error': 'date_facture requis'}, status=400)
    if not lignes:
        return Response({'error': 'Au moins une ligne requise'}, status=400)

    # Vérifier que la boutique appartient au commerçant
    try:
        boutique = Boutique.objects.get(id=boutique_id, commercant=commercant, est_active=True)
    except Boutique.DoesNotExist:
        return Response({'error': 'Boutique non trouvée'}, status=404)

    # Vérifier doublon
    doublon = FactureApprovisionnement.objects.filter(numero_facture=numero_facture, depot=boutique).first()
    if doublon:
        return Response({
            'success': True,
            'message': f'La facture {numero_facture} existe déjà (envoyée précédemment)',
            'doublon': True,
            'facture': {
                'id': doublon.id,
                'numero': doublon.numero_facture,
                'montant_total': float(doublon.montant_total),
                'lignes': 0,
            },
            'articles_crees': 0,
            'articles_mis_a_jour': 0,
        })

    # Créer ou récupérer le fournisseur
    fournisseur = None
    if fournisseur_nom:
        fournisseur, _ = Fournisseur.objects.get_or_create(
            nom=fournisseur_nom,
            commercant=commercant,
            defaults={'est_actif': True}
        )

    try:
        with transaction.atomic():
            # Créer la facture
            facture = FactureApprovisionnement.objects.create(
                numero_facture=numero_facture,
                fournisseur=fournisseur,
                fournisseur_nom=fournisseur_nom,
                depot=boutique,
                date_facture=date_facture,
                devise=devise,
                notes=notes,
                created_by=f"MAUI-Windows ({commercant.nom_entreprise})",
            )

            articles_crees = 0
            articles_mis_a_jour = 0
            total_lignes = 0

            for ligne_data in lignes:
                nom = ligne_data.get('nom', '').strip()
                if not nom:
                    continue

                categorie_nom = ligne_data.get('categorie', '').strip()
                qte_unites = int(ligne_data.get('qte_unites', 0))
                prix_achat_carton = Decimal(str(ligne_data.get('prix_achat_carton', 0)))
                prix_achat_unitaire = Decimal(str(ligne_data.get('prix_achat_unitaire', 0)))
                prix_vente = Decimal(str(ligne_data.get('prix_vente', 0)))
                nb_cartons = int(ligne_data.get('nb_cartons', 0))
                pcs_carton = int(ligne_data.get('pcs_carton', 1))

                if qte_unites <= 0:
                    continue

                # Calculer prix_achat_total
                prix_achat_total = Decimal(str(qte_unites)) * prix_achat_unitaire

                # Trouver ou créer la catégorie
                categorie = None
                if categorie_nom:
                    categorie, _ = Categorie.objects.get_or_create(
                        nom=categorie_nom,
                        boutique=boutique,
                        defaults={'description': f'Créée depuis MAUI Windows'}
                    )

                # Générer un code article unique
                code_article = nom[:50].upper().replace(' ', '_')

                # Chercher ou créer l'article dans la boutique
                article, created = Article.objects.get_or_create(
                    code=code_article,
                    boutique=boutique,
                    defaults={
                        'nom': nom,
                        'devise': devise,
                        'prix_vente': prix_vente,
                        'prix_achat': prix_achat_unitaire,
                        'categorie': categorie,
                        'quantite_stock': qte_unites,
                        'est_actif': True,
                    }
                )

                if created:
                    articles_crees += 1
                else:
                    # Mettre à jour le stock existant
                    ancien_stock = article.quantite_stock
                    article.quantite_stock += qte_unites
                    if prix_vente > 0:
                        article.prix_vente = prix_vente
                    if prix_achat_unitaire > 0:
                        article.prix_achat = prix_achat_unitaire
                    if categorie:
                        article.categorie = categorie
                    article.save()
                    articles_mis_a_jour += 1

                    # Mouvement de stock
                    MouvementStock.objects.create(
                        article=article,
                        type_mouvement='ENTREE',
                        quantite=qte_unites,
                        stock_avant=ancien_stock,
                        stock_apres=article.quantite_stock,
                        reference_document=numero_facture,
                        utilisateur="MAUI-Windows",
                        commentaire=f"Approvisionnement facture {numero_facture}"
                    )

                # Créer la ligne d'approvisionnement
                LigneApprovisionnement.objects.create(
                    facture=facture,
                    article=article,
                    categorie=categorie,
                    type_quantite='CARTON' if nb_cartons > 0 else 'UNITE',
                    nombre_cartons=nb_cartons,
                    pieces_par_carton=pcs_carton,
                    quantite_unites=qte_unites,
                    prix_achat_carton=prix_achat_carton,
                    prix_achat_unitaire=prix_achat_unitaire,
                    prix_achat_total=prix_achat_total,
                    prix_vente_unitaire=prix_vente,
                )
                total_lignes += 1

            # Calculer le montant total
            facture.calculer_montant_total()

        return Response({
            'success': True,
            'message': f'Facture {numero_facture} enregistrée avec succès',
            'facture': {
                'id': facture.id,
                'numero': facture.numero_facture,
                'montant_total': float(facture.montant_total),
                'lignes': total_lignes,
            },
            'articles_crees': articles_crees,
            'articles_mis_a_jour': articles_mis_a_jour,
        })

    except Exception as e:
        logger.error(f"Erreur réception facture: {str(e)}", exc_info=True)
        return Response({
            'error': f'Erreur serveur: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== RÉCEPTION ARTICLES (sans facture) =====

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@parser_classes([JSONParser])
def recevoir_articles(request):
    """
    Recevoir des articles depuis MAUI Windows SANS créer de facture.

    Crée/met à jour uniquement:
    - Article (stock, prix_achat, prix_vente)
    - MouvementStock (traçabilité)

    Body JSON:
    {
        "boutique_id": 1,
        "date": "2026-09-05",
        "source": "inventaire",
        "articles": [
            {
                "nom": "Riz 5kg",
                "categorie": "Alimentaire",
                "qte": 205,
                "prix_achat": 2500,
                "prix_vente": 3500
            }
        ]
    }
    """
    user_id = _get_user_id(request)
    if user_id is None:
        return Response({'error': 'Authentification requise'}, status=401)

    try:
        commercant = Commercant.objects.get(user_id=user_id, est_actif=True)
    except Commercant.DoesNotExist:
        return Response({'error': 'Commerçant non trouvé'}, status=404)

    data = request.data
    if not data:
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            data = {}

    boutique_id = data.get('boutique_id')
    articles = data.get('articles', [])
    source = data.get('source', 'MAUI')
    date_ref = data.get('date', '')

    if not boutique_id:
        return Response({'error': 'boutique_id requis'}, status=400)
    if not articles:
        return Response({'error': 'Au moins un article requis'}, status=400)

    try:
        boutique = Boutique.objects.get(id=boutique_id, commercant=commercant, est_active=True)
    except Boutique.DoesNotExist:
        return Response({'error': 'Boutique non trouvée'}, status=404)

    try:
        with transaction.atomic():
            articles_crees = 0
            articles_mis_a_jour = 0

            for art_data in articles:
                nom = art_data.get('nom', '').strip()
                if not nom:
                    continue

                qte = int(art_data.get('qte', 0))
                prix_achat = Decimal(str(art_data.get('prix_achat', 0)))
                prix_vente = Decimal(str(art_data.get('prix_vente', 0)))
                categorie_nom = art_data.get('categorie', '').strip()

                if qte <= 0:
                    continue

                # Catégorie
                categorie = None
                if categorie_nom:
                    categorie, _ = Categorie.objects.get_or_create(
                        nom=categorie_nom,
                        boutique=boutique,
                        defaults={'description': f'Créée depuis {source}'}
                    )

                code_article = nom[:50].upper().replace(' ', '_')

                article, created = Article.objects.get_or_create(
                    code=code_article,
                    boutique=boutique,
                    defaults={
                        'nom': nom,
                        'devise': 'CDF',
                        'prix_vente': prix_vente,
                        'prix_achat': prix_achat,
                        'categorie': categorie,
                        'quantite_stock': qte,
                        'est_actif': True,
                    }
                )

                if created:
                    articles_crees += 1
                else:
                    ancien_stock = article.quantite_stock
                    article.quantite_stock += qte
                    if prix_vente > 0:
                        article.prix_vente = prix_vente
                    if prix_achat > 0:
                        article.prix_achat = prix_achat
                    if categorie:
                        article.categorie = categorie
                    article.save()
                    articles_mis_a_jour += 1

                    MouvementStock.objects.create(
                        article=article,
                        type_mouvement='ENTREE',
                        quantite=qte,
                        stock_avant=ancien_stock,
                        stock_apres=article.quantite_stock,
                        reference_document=source,
                        utilisateur="MAUI-Windows",
                        commentaire=f"{source} {date_ref}".strip()
                    )

            return Response({
                'success': True,
                'message': f'{articles_crees} article(s) créé(s), {articles_mis_a_jour} mis à jour',
                'articles_crees': articles_crees,
                'articles_mis_a_jour': articles_mis_a_jour,
            })

    except Exception as e:
        logger.error(f"Erreur réception articles: {str(e)}", exc_info=True)
        return Response({
            'error': f'Erreur serveur: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===== UTILITAIRES =====

def _get_user_id(request):
    """Extraire le user_id du header Authorization."""
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        auth = auth[7:]
    if auth.isdigit():
        return int(auth)
    return None
