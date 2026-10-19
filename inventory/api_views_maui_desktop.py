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
import uuid
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import (
    Commercant, Boutique, Article, Categorie, Fournisseur,
    FactureApprovisionnement, LigneApprovisionnement, MouvementStock,
    Client, TransfertStock,
)

logger = logging.getLogger(__name__)


def _normaliser_pv_source(pv: str) -> str:
    """
    Normaliser le nom du point de vente source.
    Ex: 'KIYAMBU 04 MPOLO' → 'MPOLO 04'
        'KIYAMBU DUBAI 04 MPOLO' → 'DUBAI 04 MPOLO'
    """
    pv = (pv or '').strip()
    if not pv:
        return ''
    parts = pv.upper().replace('KIYAMBU', ' ').split()
    if not parts:
        return ''
    # '04 MPOLO' → 'MPOLO 04' ; 'DUBAI 04 MPOLO' → 'DUBAI 04 MPOLO'
    if len(parts) == 2 and parts[0].isdigit() and parts[1] == 'MPOLO':
        return f'{parts[1]} {parts[0]}'
    return ' '.join(parts)


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

                # Ne jamais copier PV en PA : si non renseigné ou égal au PV, on laisse 0
                if prix_achat <= 0 or prix_achat == prix_vente:
                    prix_achat = Decimal('0')

                if qte < 0:
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
                pv_source = _normaliser_pv_source(art_data.get('point_vente') or '')

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
                        'point_vente_source': pv_source,
                    }
                )

                if pv_source or article.point_vente_source:
                    sources = []
                    for s in (article.point_vente_source or '').split(','):
                        ns = _normaliser_pv_source(s)
                        if ns and ns not in sources:
                            sources.append(ns)
                    if pv_source and pv_source not in sources:
                        sources.append(pv_source)
                    new_val = ', '.join(sources)
                    if new_val != article.point_vente_source:
                        article.point_vente_source = new_val
                        pv_changed = True
                    else:
                        pv_changed = False
                else:
                    pv_changed = False

                if created:
                    articles_crees += 1
                    if pv_changed:
                        article.save(update_fields=['point_vente_source'])
                else:
                    ancien_stock = article.quantite_stock
                    # Inventaire/stock = instantané : on remet le stock à la valeur reçue
                    # (permet de recommencer l'envoi sans doubler)
                    # Facture = entrée de marchandise : on additionne
                    if source in ('inventaire', 'stock'):
                        article.quantite_stock = qte
                    else:
                        article.quantite_stock += qte

                    if prix_vente > 0:
                        article.prix_vente = prix_vente
                    if prix_achat > 0:
                        article.prix_achat = prix_achat
                    if categorie:
                        article.categorie = categorie
                    article.save()
                    articles_mis_a_jour += 1

                    if article.quantite_stock != ancien_stock:
                        MouvementStock.objects.create(
                            article=article,
                            type_mouvement='AJUSTEMENT' if source in ('inventaire', 'stock') else 'ENTREE',
                            quantite=abs(article.quantite_stock - ancien_stock),
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
    """Extraire le user_id du header Authorization (user_id numérique ou token JWT Bearer)."""
    auth = request.headers.get('Authorization', '') or ''
    if auth.startswith('Bearer '):
        auth = auth[7:]
    auth = auth.strip()
    if not auth:
        return None
    if auth.isdigit():
        return int(auth)
    # Token JWT (simplejwt) : décoder pour récupérer le user_id
    try:
        from rest_framework_simplejwt.tokens import AccessToken
        return int(AccessToken(auth)['user_id'])
    except Exception:
        return None


# ===== TRANSFERTS ENTRE BOUTIQUES =====

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@parser_classes([JSONParser])
@transaction.atomic
def transfert_entre_boutiques(request):
    """
    Transfert d'un article d'une boutique source vers une boutique destination
    (même commerçant, boutiques différentes). Terminal identifié par X-Device-Serial.
    """
    try:
        # 1. Authentification terminal
        numero_serie = request.headers.get('X-Device-Serial', '')
        if not numero_serie:
            return Response(
                {'success': False, 'error': 'Header X-Device-Serial manquant.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        client = Client.objects.select_related('boutique__commercant').filter(
            numero_serie=numero_serie, est_actif=True
        ).first()
        if not client:
            return Response(
                {'success': False, 'error': 'Terminal non reconnu ou inactif.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        boutique_source = client.boutique
        if not boutique_source:
            return Response(
                {'success': False, 'error': 'Ce terminal n\'est associé à aucune boutique.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        commerçant = boutique_source.commercant

        # 2. Lecture du payload (multi-lignes 'lignes' ou mono-article rétro-compatible)
        data = request.data

        try:
            boutique_destination_id = int(data.get('boutique_destination_id'))
        except (TypeError, ValueError):
            return Response(
                {'success': False, 'error': 'boutique_destination_id invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3. Destination : même commerçant, boutique différente
        try:
            boutique_destination = Boutique.objects.get(pk=boutique_destination_id)
        except Boutique.DoesNotExist:
            return Response(
                {'success': False, 'error': 'Boutique destination introuvable.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if boutique_destination.commercant_id != commerçant.id:
            return Response(
                {'success': False, 'error': 'La boutique destination doit appartenir au même commerçant.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if boutique_destination.id == boutique_source.id:
            return Response(
                {'success': False, 'error': 'La boutique source et destination doivent être différentes.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Normalisation des lignes demandées
        lignes_entree = data.get('lignes')
        if lignes_entree is None:
            # Rétro-compatibilité : un seul article
            lignes_entree = [{
                'article_id': data.get('article_id'),
                'article_code': data.get('article_code'),
                'quantite': data.get('quantite'),
            }]
        if not isinstance(lignes_entree, list) or not lignes_entree:
            return Response(
                {'success': False, 'error': 'Aucune ligne à transférer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 5. Résolution des articles + agrégation par article (évite les doublons)
        articles_demandes = {}  # article_id -> {'article': Article, 'quantite': int}
        for index, ligne in enumerate(lignes_entree, start=1):
            if not isinstance(ligne, dict):
                return Response(
                    {'success': False, 'error': f'Ligne {index} invalide.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                qte_ligne = int(ligne.get('quantite'))
            except (TypeError, ValueError):
                return Response(
                    {'success': False, 'error': f'Ligne {index} : quantité invalide.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if qte_ligne < 1:
                return Response(
                    {'success': False, 'error': f'Ligne {index} : quantité doit être ≥ 1.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            article_ligne = None
            article_id = ligne.get('article_id')
            article_code = ligne.get('article_code')
            if article_id is not None:
                try:
                    article_ligne = Article.objects.get(pk=int(article_id), boutique=boutique_source)
                except (Article.DoesNotExist, TypeError, ValueError):
                    article_ligne = None
            elif article_code:
                article_ligne = Article.objects.filter(
                    code=str(article_code).strip(), boutique=boutique_source
                ).first()
            if not article_ligne:
                return Response(
                    {'success': False, 'error': f'Ligne {index} : article introuvable dans cette boutique.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if article_ligne.id in articles_demandes:
                articles_demandes[article_ligne.id]['quantite'] += qte_ligne
            else:
                articles_demandes[article_ligne.id] = {'article': article_ligne, 'quantite': qte_ligne}

        # 6. Stock suffisant pour chaque article
        for demande in articles_demandes.values():
            article_demande = demande['article']
            if article_demande.quantite_stock < demande['quantite']:
                return Response(
                    {'success': False, 'error': f"Stock insuffisant pour {article_demande.nom} "
                                                f"(disponible: {article_demande.quantite_stock}, "
                                                f"demandé: {demande['quantite']})."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 7. Commentaire + référence de lot (regroupe toutes les lignes)
        commentaire = str(data.get('commentaire', '')).strip()
        if not commentaire:
            commentaire = f"Transfert terminal {client.numero_serie} → {boutique_destination.nom}"

        reference_lot = f"LOT-{timezone.localtime().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        effectue_par = f"Terminal {client.numero_serie}"

        # 8. Créer et valider chaque ligne (transaction globale : tout ou rien)
        transferts = []
        quantite_totale = 0
        for demande in articles_demandes.values():
            article = demande['article']
            quantite = demande['quantite']

            transfert = TransfertStock.objects.create(
                article=article,
                depot_source=boutique_source,
                boutique_destination=boutique_destination,
                quantite=quantite,
                effectue_par=effectue_par,
                statut='EN_ATTENTE',
                reference_lot=reference_lot,
                commentaire=commentaire,
            )

            # valider_transfert décrémente la source, crée le mouvement SORTIE
            # et place le stock de destination EN ATTENTE de validation côté terminal
            # (quantite_envoyee += quantite, est_valide_client=False).
            # On ne crédite PAS quantite_stock ici : le terminal de la boutique
            # destination validera la réception (comme un transfert validé depuis le
            # back-office). Créditer directement doublerait le stock à la validation.
            article_dest = transfert.valider_transfert(valide_par_user=effectue_par)

            quantite_totale += quantite
            transferts.append({
                'transfert_id': transfert.id,
                'article_id': article.id,
                'article_destination_id': article_dest.id,
                'article_nom': article.nom,
                'quantite': quantite,
            })

        # Prévenir la boutique destination : stock reçu en attente de validation client
        try:
            from .websocket_utils import notify_sync_required
            notify_sync_required(
                boutique_destination.id,
                f"{quantite_totale} unité(s) reçue(s) - en attente de validation côté client"
            )
        except Exception as e:
            logger.warning(f"Notification destination échouée: {e}")

        premier = transferts[0]
        return Response({
            'success': True,
            'reference_lot': reference_lot,
            'boutique_destination': boutique_destination.nom,
            'nb_articles': len(transferts),
            'quantite_totale': quantite_totale,
            'transferts': transferts,
            # Rétro-compatibilité mono-article
            'transfert_id': premier['transfert_id'] if len(transferts) == 1 else None,
            'article_destination_id': premier['article_destination_id'] if len(transferts) == 1 else None,
            'quantite_transferee': quantite_totale,
        })

    except ValidationError as e:
        logger.warning(f"Transfert refusé: {e}")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except ParseError as e:
        return Response(
            {'success': False, 'error': f'JSON invalide: {e}'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        logger.error(f"Erreur transfert entre boutiques: {str(e)}", exc_info=True)
        return Response(
            {'success': False, 'error': f'Erreur serveur: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
