from rest_framework import serializers
from django.db import transaction
import decimal
from .models import Article, Categorie, Vente, LigneVente, Client, SessionClientMaui, RapportCaisse, ArticleNegocie, RetourArticle, NotificationStock, VarianteArticle

class CategorieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categorie
        fields = '__all__'

class ArticleSerializer(serializers.ModelSerializer):
    categorie_id = serializers.PrimaryKeyRelatedField(
        queryset=Categorie.objects.all(),
        source='categorie',
        write_only=True
    )
    categorie_nom = serializers.CharField(source='categorie.nom', read_only=True)
    qr_code_url = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    full_details = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            'id', 'code', 'nom', 'description', 'devise', 'prix_vente', 'prix_achat',
            'prix_vente_usd', 'prix_achat_usd',
            'categorie_id', 'categorie_nom', 'quantite_stock', 'qr_code_url', 'image_url',
            'full_details'
        ]
    
    def get_full_details(self, obj):
        import logging
        logger = logging.getLogger(__name__)
        details = {
            'nom_complet': f"{obj.nom} ({obj.code})",
            'prix_vente_formate': f"{obj.prix_vente:.2f} €",
            'stock_disponible': obj.quantite_stock,
            'categorie': obj.categorie.nom if obj.categorie else 'Non catégorisé'
        }
        logger.debug(f'Détails complets de l\'article : {details}')
        return details

    def get_qr_code_url(self, obj):
        request = self.context.get('request')
        if obj.qr_code and request:
            return request.build_absolute_uri(obj.qr_code.url)
        return None

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and hasattr(obj.image, 'url') and request:
            return request.build_absolute_uri(obj.image.url)
        return None


class VarianteArticleSerializer(serializers.ModelSerializer):
    """Serializer pour les variantes d'articles avec code-barres."""
    
    article_parent_id = serializers.PrimaryKeyRelatedField(
        queryset=Article.objects.all(),
        source='article_parent',
        write_only=True
    )
    article_parent_nom = serializers.CharField(source='article_parent.nom', read_only=True)
    prix_vente = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    prix_achat = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    devise = serializers.CharField(read_only=True)
    nom_complet = serializers.CharField(read_only=True)
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = VarianteArticle
        fields = [
            'id', 'article_parent_id', 'article_parent_nom',
            'code_barre', 'nom_variante', 'type_attribut',
            'quantite_stock', 'est_actif',
            'prix_vente', 'prix_achat', 'devise', 'nom_complet',
            'image_url', 'date_creation', 'date_mise_a_jour'
        ]
        read_only_fields = ['date_creation', 'date_mise_a_jour']
    
    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and hasattr(obj.image, 'url') and request:
            return request.build_absolute_uri(obj.image.url)
        # Fallback to parent article image
        if obj.article_parent.image and hasattr(obj.article_parent.image, 'url') and request:
            return request.build_absolute_uri(obj.article_parent.image.url)
        return None


class ArticleAvecVariantesSerializer(serializers.ModelSerializer):
    """Serializer d'article incluant ses variantes."""
    
    variantes = VarianteArticleSerializer(many=True, read_only=True)
    categorie_nom = serializers.CharField(source='categorie.nom', read_only=True)
    has_variantes = serializers.SerializerMethodField()
    stock_total_variantes = serializers.SerializerMethodField()
    
    class Meta:
        model = Article
        fields = [
            'id', 'code', 'nom', 'description', 'devise', 
            'prix_vente', 'prix_achat', 'categorie_nom',
            'quantite_stock', 'est_actif', 'has_variantes',
            'stock_total_variantes', 'variantes'
        ]
    
    def get_has_variantes(self, obj):
        return obj.variantes.filter(est_actif=True).exists()
    
    def get_stock_total_variantes(self, obj):
        return sum(v.quantite_stock for v in obj.variantes.filter(est_actif=True))


class LigneVenteSerializer(serializers.ModelSerializer):
    article = ArticleSerializer(read_only=True)
    article_id = serializers.PrimaryKeyRelatedField(
        queryset=Article.objects.all(),
        source='article',
        write_only=True
    )

    class Meta:
        model = LigneVente
        fields = '__all__'

class VenteSerializer(serializers.ModelSerializer):
    lignes = LigneVenteSerializer(many=True, read_only=True)
    lignes_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False
    )
    
    # Remplacer € par CDF dans le formatage du prix
    def get_full_details(self, obj):
        return {
            'numero_facture': obj.numero_facture,
            'date': obj.date_vente.strftime('%d/%m/%Y %H:%M'),
            'montant_total': f"{obj.montant_total:.2f} CDF",
            'mode_paiement': obj.get_mode_paiement_display(),
            'status': "Payé" if obj.paye else "En attente"
        }

    class Meta:
        model = Vente
        fields = '__all__'
        
    def to_internal_value(self, data):
        # data is the raw input from the request body (e.g., from MAUI client)
        internal_data = {}

        # 1. Map top-level fields from MAUI input to serializer field names
        if 'reference' in data:
            internal_data['numero_facture'] = data['reference']
        
        if 'total' in data:
            try:
                montant_str = str(data['total']).replace(',', '.')
                internal_data['montant_total'] = decimal.Decimal(montant_str)
                if internal_data['montant_total'] <= 0:
                    # This validation can also be in a specific field validator or .validate_montant_total
                    raise serializers.ValidationError({'montant_total': "Le montant total doit être positif."})
            except (ValueError, TypeError, InvalidOperation) as e:
                raise serializers.ValidationError({'montant_total': f"Montant total '{data['total']}' invalide. Erreur: {e}"})
        
        if 'mode_paiement' in data:
            internal_data['mode_paiement'] = data['mode_paiement']

        if 'date_vente' in data:
            internal_data['date_vente'] = data['date_vente']
        elif 'date' in data: # Assuming MAUI sends 'date' in ISO format
            internal_data['date_vente'] = data['date'] # DRF will parse this for DateTimeField

        # Handle 'paye' field, defaulting to True as observed in logs
        internal_data['paye'] = data.get('paye', True)

        # 2. Process line items: MAUI 'lignes' list to serializer 'lignes_data' list
        if 'lignes' in data and isinstance(data['lignes'], list):
            processed_lignes_data = []
            for index, maui_ligne in enumerate(data['lignes']):
                ligne_item = {}
                
                if 'article_id' not in maui_ligne:
                    raise serializers.ValidationError({f'lignes[{index}].article_id': "Champ article_id manquant."})
                try:
                    ligne_item['article_id'] = int(maui_ligne['article_id'])
                except (ValueError, TypeError):
                    raise serializers.ValidationError({f'lignes[{index}].article_id': f"article_id '{maui_ligne.get('article_id')}' invalide."})

                if 'quantite' not in maui_ligne:
                    raise serializers.ValidationError({f'lignes[{index}].quantite': "Champ quantite manquant."})
                try:
                    quantite_str = str(maui_ligne['quantite']).replace(',', '.')
                    ligne_item['quantite'] = int(float(quantite_str)) # float for "2.0", then int
                    if ligne_item['quantite'] <= 0:
                        raise ValueError("La quantité doit être positive.")
                except (ValueError, TypeError):
                    raise serializers.ValidationError({f'lignes[{index}].quantite': f"Quantité '{maui_ligne.get('quantite')}' invalide."})

                if 'prix_unitaire' not in maui_ligne:
                    raise serializers.ValidationError({f'lignes[{index}].prix_unitaire': "Champ prix_unitaire manquant."})
                try:
                    prix_str = str(maui_ligne['prix_unitaire']).replace(',', '.')
                    ligne_item['prix_unitaire'] = decimal.Decimal(prix_str)
                    if ligne_item['prix_unitaire'] <= 0:
                        raise ValueError("Le prix unitaire doit être positif.")
                except (ValueError, TypeError, InvalidOperation) as e:
                    raise serializers.ValidationError({f'lignes[{index}].prix_unitaire': f"Prix unitaire '{maui_ligne.get('prix_unitaire')}' invalide. Erreur: {e}"})

                # Calculate 'montant_ligne' based on processed quantite and prix_unitaire
                ligne_item['montant_ligne'] = ligne_item['quantite'] * ligne_item['prix_unitaire']
                
                processed_lignes_data.append(ligne_item)
            
            internal_data['lignes_data'] = processed_lignes_data
        elif self.fields['lignes_data'].required: # Check if field is required if not provided
             raise serializers.ValidationError({'lignes': "Le champ lignes est requis et doit contenir au moins un article."}) # Or 'lignes_data'

        # Pass the fully prepared internal_data to the parent class's to_internal_value
        return super().to_internal_value(internal_data)

    def validate(self, data):
        # Validation personnalisée pour les champs critiques
        if 'lignes_data' not in data or not data['lignes_data']:
            raise serializers.ValidationError({
                'lignes_data': 'Au moins une ligne de vente est requise'
            })
            
        # Vérifier chaque ligne pour des données valides
        for index, ligne in enumerate(data['lignes_data']):
            if 'article_id' not in ligne:
                raise serializers.ValidationError({
                    f'lignes_data[{index}]': 'Champ article_id manquant'
                })
            if 'quantite' not in ligne:
                raise serializers.ValidationError({
                    f'lignes_data[{index}]': 'Champ quantite manquant'
                })
            if 'prix_unitaire' not in ligne:
                raise serializers.ValidationError({
                    f'lignes_data[{index}]': 'Champ prix_unitaire manquant'
                })
        
        return data

    @transaction.atomic
    def create(self, validated_data):
        import logging
        import json
        from django.db import transaction
        
        # Configuration d'un logger spécifique pour voir les erreurs en détail
        logger = logging.getLogger(__name__)
        
        # Afficher les données exactes reçues pour le débogage
        logger.error(f"=========== DONNÉES DE VENTE REÇUES ===========")
        logger.error(f"Type: {type(validated_data)}")
        
        try:
            # Afficher le contenu exact pour le débogage
            logger.error(json.dumps(validated_data, default=str, indent=2))
        except Exception as e:
            logger.error(f"Erreur lors de la sérialisation des données: {e}")
            for key, value in validated_data.items():
                logger.error(f"{key}: {type(value)} = {value}")
        
        logger.error(f"=================================================")
        
        # Extraction des lignes pour traitement séparé
        lignes_data = validated_data.pop('lignes_data', [])
        
        # Si aucune ligne n'est fournie, on peut lever une erreur
        # Cette vérification est déjà faite dans validate(), mais on la garde par sécurité
        if not lignes_data:
            logger.warning("Aucune ligne de vente fournie")
            raise serializers.ValidationError({
                'lignes_data': 'Au moins une ligne de vente est requise'
            })
        
        # Vérification préalable de la disponibilité des articles et des stocks
        articles_insuffisants = []
        articles_a_traiter = []
        
        for ligne_data in lignes_data:
            try:
                # Récupération de l'article
                article_id = ligne_data.get('article_id')
                article_code = ligne_data.get('code_barres')
                prix_unitaire_ligne = ligne_data.get('prix_unitaire')
                
                # Log pour débogage
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Recherche d'article avec: ID={article_id}, Code={article_code}, Prix={prix_unitaire_ligne}")
                
                article = None
                
                # Stratégie 1: Essayer de trouver par ID si différent de 0
                if article_id and article_id != 0:
                    try:
                        article = Article.objects.get(id=article_id)
                        logger.info(f"Article trouvé par ID: {article.nom}")
                    except Article.DoesNotExist:
                        logger.warning(f"Article avec ID {article_id} non trouvé, essai par code ou prix")
                
                # Stratégie 2: Si ID non valide ou article non trouvé, essayer par code-barres
                if article is None and article_code:
                    try:
                        article = Article.objects.filter(code=article_code).first()
                        if article:
                            logger.info(f"Article trouvé par code: {article.nom}")
                    except Exception as e:
                        logger.warning(f"Erreur lors de la recherche par code: {e}")
                
                # Stratégie 3: Si toujours pas trouvé, essayer par prix
                if article is None and prix_unitaire_ligne:
                    try:
                        # Conversion en decimal pour comparaison précise
                        prix_decimal = decimal.Decimal(str(prix_unitaire_ligne))
                        
                        # Recherche des articles avec ce prix (avec une marge d'erreur minime)
                        articles_par_prix = Article.objects.filter(prix_vente__range=[prix_decimal*0.99, prix_decimal*1.01])
                        
                        if articles_par_prix.count() == 1:
                            article = articles_par_prix.first()
                            logger.info(f"Article trouvé par prix exact: {article.nom}")
                        elif articles_par_prix.count() > 1:
                            # Si plusieurs articles ont le même prix, prendre celui avec le plus de stock
                            article = articles_par_prix.order_by('-quantite_stock').first()
                            logger.info(f"Plusieurs articles trouvés par prix, sélection de: {article.nom}")
                    except Exception as e:
                        logger.warning(f"Erreur lors de la recherche par prix: {e}")
                
                # Si aucun article n'a été trouvé, lever une erreur
                if article is None:
                    raise serializers.ValidationError(f"Impossible de trouver l'article avec ID={article_id}, Code={article_code}, Prix={prix_unitaire_ligne}")
                
                # Conversion explicite des valeurs numériques
                try:
                    quantite = int(ligne_data['quantite'])
                    if quantite <= 0:
                        raise serializers.ValidationError(f"La quantité doit être positive pour l'article {article.nom}")
                except (ValueError, TypeError):
                    raise serializers.ValidationError(f"Quantité invalide pour l'article {article.nom}")
                
                # Vérification du stock disponible
                if article.quantite_stock < quantite:
                    articles_insuffisants.append({
                        'id': article.id,
                        'nom': article.nom,
                        'stock_disponible': article.quantite_stock,
                        'quantite_demandee': quantite
                    })
                else:
                    # Conversion du prix unitaire
                    try:
                        prix_unitaire = decimal.Decimal(str(ligne_data['prix_unitaire']))
                    except (ValueError, TypeError, InvalidOperation):
                        raise serializers.ValidationError(f"Prix unitaire invalide pour l'article {article.nom}")
                    
                    # Calcul ou récupération du montant de la ligne
                    montant_ligne = ligne_data.get('montant_ligne')
                    if montant_ligne is None:
                        montant_ligne = quantite * prix_unitaire
                    else:
                        try:
                            montant_ligne = decimal.Decimal(str(montant_ligne))
                        except (ValueError, TypeError, InvalidOperation):
                            montant_ligne = quantite * prix_unitaire
                    
                    # Stockage des données validées pour traitement ultérieur
                    articles_a_traiter.append({
                        'article': article,
                        'quantite': quantite,
                        'prix_unitaire': prix_unitaire,
                        'montant_ligne': montant_ligne
                    })
                    
            except serializers.ValidationError as ve:
                # Propager l'erreur de validation
                logger.error(f"Erreur de validation: {str(ve)}")
                raise
            except Exception as e:
                # Journaliser et propager les autres erreurs
                logger.error(f"Erreur inattendue: {str(e)}")
                raise serializers.ValidationError(f"Erreur lors de la validation: {str(e)}")
        
        # Si des articles ont un stock insuffisant, lever une erreur
        if articles_insuffisants:
            logger.warning(f"Stock insuffisant pour les articles: {articles_insuffisants}")
            raise serializers.ValidationError({
                'stock_insuffisant': articles_insuffisants
            })
        
        # Tout est validé, procéder à la création de la vente
        try:
            # Création de la vente
            vente = Vente.objects.create(**validated_data)
            logger.info(f"Vente créée: {vente.numero_facture}")
            
            # Traitement de chaque ligne de vente
            for article_info in articles_a_traiter:
                article = article_info['article']
                quantite = article_info['quantite']
                prix_unitaire = article_info['prix_unitaire']
                montant_ligne = article_info['montant_ligne']
                
                # S'assurer que la quantité est un entier positif
                try:
                    # Convertir explicitement en entier
                    quantite_int = int(quantite)
                    if quantite_int <= 0:
                        logger.warning(f"Quantité négative ou nulle reçue: {quantite} pour {article.nom}, utilisation de 1 par défaut")
                        quantite_int = 1
                except (ValueError, TypeError) as e:
                    logger.error(f"Erreur de conversion de quantité '{quantite}' pour {article.nom}: {str(e)}")
                    quantite_int = 1
                
                # Création de la ligne de vente avec la quantité validée
                LigneVente.objects.create(
                    vente=vente,
                    article=article,
                    quantite=quantite_int,
                    prix_unitaire=prix_unitaire,
                    montant_ligne=montant_ligne
                )
                logger.info(f"Ligne de vente créée pour {article.nom}, qté: {quantite_int}")
                
                # Utiliser la nouvelle fonction efficace de mise à jour du stock
                from .utils import update_stock_by_article_id
                
                # Récupérer l'utilisateur courant (si disponible)
                utilisateur = None
                if self.context.get('request') and hasattr(self.context['request'], 'user') and self.context['request'].user.is_authenticated:
                    utilisateur = self.context['request'].user.username
                
                # Préparer les détails pour l'historique
                details = {
                    'vente_numero': vente.numero_facture,
                    'prix_unitaire': prix_unitaire,
                    'montant_ligne': montant_ligne
                }
                
                # Mise à jour du stock avec détails améliorés
                success, message, mouvement = update_stock_by_article_id(
                    article_id=article.id,
                    quantite=quantite_int,
                    type_mouvement="VENTE",
                    reference=vente.numero_facture,
                    utilisateur=utilisateur or "API",
                    details=details,
                    is_sale=True
                )
                
                # Si la mise à jour a échoué, journaliser l'erreur
                if not success:
                    logger.warning(f"Échec de mise à jour du stock: {message}")
                    # Continuer malgré tout, la transaction se poursuit
                else:
                    # Récupérer les détails du mouvement pour le log (si disponible)
                    if mouvement:
                        logger.info(f"Stock mis à jour pour {article.nom}: {mouvement.stock_avant} -> {mouvement.stock_apres}")
                    else:
                        # Rafraîchir l'article depuis la base de données
                        article.refresh_from_db()
                        logger.info(f"Stock mis à jour pour {article.nom}. Nouveau stock: {article.quantite_stock}")
            
            return vente
            
        except Exception as e:
            # En cas d'erreur, la transaction sera automatiquement annulée
            logger.error(f"Erreur lors de la création de la vente: {str(e)}")
            # Le @transaction.atomic s'occupera du rollback
            raise serializers.ValidationError({
                'error': f"Erreur lors de l'enregistrement de la vente: {str(e)}"
            })


class ClientSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les clients MAUI."""
    
    compte_proprietaire_nom = serializers.CharField(source='compte_proprietaire.username', read_only=True)
    sessions_actives_count = serializers.SerializerMethodField()
    ventes_count = serializers.SerializerMethodField()
    derniere_vente = serializers.SerializerMethodField()
    
    class Meta:
        model = Client
        fields = [
            'id', 'nom_boutique', 'proprietaire', 'adresse', 'telephone', 'email',
            'numero_serie', 'est_actif', 'derniere_connexion', 'derniere_activite',
            'date_creation', 'type_commerce', 'notes', 'compte_proprietaire_nom',
            'sessions_actives_count', 'ventes_count', 'derniere_vente'
        ]
        read_only_fields = ['id', 'date_creation', 'cle_api']
    
    def get_sessions_actives_count(self, obj):
        """Retourne le nombre de sessions actives pour ce client."""
        return obj.sessions.filter(est_active=True).count()
    
    def get_ventes_count(self, obj):
        """Retourne le nombre total de ventes pour ce client."""
        return obj.ventes.count()
    
    def get_derniere_vente(self, obj):
        """Retourne les informations de la dernière vente."""
        derniere_vente = obj.ventes.order_by('-date_vente').first()
        if derniere_vente:
            return {
                'numero_facture': derniere_vente.numero_facture,
                'date_vente': derniere_vente.date_vente,
                'montant_total': derniere_vente.montant_total
            }
        return None


class SessionClientMauiSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les sessions des clients MAUI."""
    
    client_nom = serializers.CharField(source='client.nom_boutique', read_only=True)
    duree_session = serializers.SerializerMethodField()
    
    class Meta:
        model = SessionClientMaui
        fields = [
            'id', 'client', 'client_nom', 'token_session', 'date_debut', 'date_fin',
            'est_active', 'adresse_ip', 'user_agent', 'version_app', 'duree_session'
        ]
        read_only_fields = ['id', 'date_debut', 'token_session']
    
    def get_duree_session(self, obj):
        """Calcule la durée de la session."""
        if obj.date_fin:
            duree = obj.date_fin - obj.date_debut
            return str(duree)
        elif obj.est_active:
            from django.utils import timezone
            duree = timezone.now() - obj.date_debut
            return f"{str(duree)} (en cours)"
        return None


class RapportCaisseSerializer(serializers.ModelSerializer):
    boutique_id = serializers.IntegerField(source='boutique.id', read_only=True)
    boutique_nom = serializers.CharField(source='boutique.nom', read_only=True)
    terminal_id = serializers.IntegerField(source='terminal.id', read_only=True)
    terminal_nom = serializers.CharField(source='terminal.nom_terminal', read_only=True)
    terminal_serial = serializers.CharField(source='terminal.numero_serie', read_only=True)

    class Meta:
        model = RapportCaisse
        fields = [
            'id',
            'boutique_id', 'boutique_nom',
            'terminal_id', 'terminal_nom', 'terminal_serial',
            'date_rapport', 'detail', 'depense', 'devise',
            'est_synchronise', 'id_backend',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id',
            'boutique_id', 'boutique_nom',
            'terminal_id', 'terminal_nom', 'terminal_serial',
            'est_synchronise', 'id_backend',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'date_rapport': {'required': False},
        }


class ArticleNegocieSerializer(serializers.ModelSerializer):
    boutique_id = serializers.IntegerField(source='boutique.id', read_only=True)
    boutique_nom = serializers.CharField(source='boutique.nom', read_only=True)
    terminal_id = serializers.IntegerField(source='terminal.id', read_only=True)
    terminal_nom = serializers.CharField(source='terminal.nom_terminal', read_only=True)
    terminal_serial = serializers.CharField(source='terminal.numero_serie', read_only=True)
    article_id = serializers.IntegerField(source='article.id', read_only=True)
    article_nom = serializers.CharField(source='article.nom', read_only=True)

    class Meta:
        model = ArticleNegocie
        fields = [
            'id',
            'boutique_id', 'boutique_nom',
            'terminal_id', 'terminal_nom', 'terminal_serial',
            'article_id', 'article_nom',
            'code_article', 'quantite', 'montant_negocie', 'devise', 'date_operation',
            'motif', 'reference_vente',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class RetourArticleSerializer(serializers.ModelSerializer):
    boutique_id = serializers.IntegerField(source='boutique.id', read_only=True)
    boutique_nom = serializers.CharField(source='boutique.nom', read_only=True)
    terminal_id = serializers.IntegerField(source='terminal.id', read_only=True)
    terminal_nom = serializers.CharField(source='terminal.nom_terminal', read_only=True)
    terminal_serial = serializers.CharField(source='terminal.numero_serie', read_only=True)
    article_id = serializers.IntegerField(source='article.id', read_only=True)
    article_nom = serializers.CharField(source='article.nom', read_only=True)

    class Meta:
        model = RetourArticle
        fields = [
            'id',
            'boutique_id', 'boutique_nom',
            'terminal_id', 'terminal_nom', 'terminal_serial',
            'article_id', 'article_nom',
            'code_article', 'quantite', 'montant_retourne', 'devise', 'date_operation',
            'motif', 'reference_vente',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class NotificationStockSerializer(serializers.ModelSerializer):
    """Serializer pour les notifications de stock avec détails enrichis."""
    
    client_nom = serializers.CharField(source='client.nom_terminal', read_only=True)
    boutique_nom = serializers.CharField(source='boutique.nom', read_only=True)
    article_nom = serializers.CharField(source='article.nom', read_only=True, allow_null=True)
    article_code = serializers.CharField(source='article.code', read_only=True, allow_null=True)
    type_notification_display = serializers.CharField(source='get_type_notification_display', read_only=True)
    date_creation_formatee = serializers.SerializerMethodField()
    date_lecture_formatee = serializers.SerializerMethodField()
    
    def get_date_creation_formatee(self, obj):
        """Retourne la date de création au format lisible français."""
        if obj.date_creation:
            return obj.date_creation.strftime('%d/%m/%Y à %H:%M')
        return None
    
    def get_date_lecture_formatee(self, obj):
        """Retourne la date de lecture au format lisible français."""
        if obj.date_lecture:
            return obj.date_lecture.strftime('%d/%m/%Y à %H:%M')
        return None
    
    class Meta:
        model = NotificationStock
        fields = [
            'id',
            'client_nom',
            'boutique_nom',
            'type_notification',
            'type_notification_display',
            'titre',
            'message',
            'article_nom',
            'article_code',
            'quantite_mouvement',
            'stock_avant',
            'stock_actuel',
            'quantite_ajoutee',
            'lue',
            'date_lecture',
            'date_lecture_formatee',
            'date_creation',
            'date_creation_formatee',
            'donnees_supplementaires',
        ]
        read_only_fields = [
            'id', 'client_nom', 'boutique_nom', 'type_notification',
            'type_notification_display', 'titre', 'message', 'article_nom',
            'article_code', 'quantite_mouvement', 'stock_avant', 'stock_actuel', 
            'quantite_ajoutee', 'date_lecture', 'date_lecture_formatee', 
            'date_creation', 'date_creation_formatee'
        ]


class NotificationStockDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour une notification de stock avec toutes les informations."""
    
    client_info = serializers.SerializerMethodField()
    boutique_info = serializers.SerializerMethodField()
    article_info = serializers.SerializerMethodField()
    mouvement_info = serializers.SerializerMethodField()
    type_notification_display = serializers.CharField(source='get_type_notification_display', read_only=True)
    date_creation_formatee = serializers.SerializerMethodField()
    date_lecture_formatee = serializers.SerializerMethodField()
    
    def get_date_creation_formatee(self, obj):
        """Retourne la date de création au format lisible français."""
        if obj.date_creation:
            return obj.date_creation.strftime('%d/%m/%Y à %H:%M')
        return None
    
    def get_date_lecture_formatee(self, obj):
        """Retourne la date de lecture au format lisible français."""
        if obj.date_lecture:
            return obj.date_lecture.strftime('%d/%m/%Y à %H:%M')
        return None
    
    class Meta:
        model = NotificationStock
        fields = [
            'id',
            'client_info',
            'boutique_info',
            'type_notification',
            'type_notification_display',
            'titre',
            'message',
            'article_info',
            'mouvement_info',
            'quantite_mouvement',
            'stock_avant',
            'stock_actuel',
            'quantite_ajoutee',
            'lue',
            'date_lecture',
            'date_lecture_formatee',
            'date_creation',
            'date_creation_formatee',
            'donnees_supplementaires',
        ]
    
    def get_client_info(self, obj):
        """Retourne les informations du client MAUI."""
        return {
            'id': obj.client.id,
            'nom_terminal': obj.client.nom_terminal,
            'numero_serie': obj.client.numero_serie,
        }
    
    def get_boutique_info(self, obj):
        """Retourne les informations de la boutique."""
        return {
            'id': obj.boutique.id,
            'nom': obj.boutique.nom,
            'code_boutique': obj.boutique.code_boutique,
        }
    
    def get_article_info(self, obj):
        """Retourne les informations détaillées de l'article."""
        if not obj.article:
            return None
        
        return {
            'id': obj.article.id,
            'code': obj.article.code,
            'nom': obj.article.nom,
            'description': obj.article.description,
            'prix_vente': str(obj.article.prix_vente),
            'devise': obj.article.devise,
            'quantite_stock': obj.article.quantite_stock,
            'categorie': obj.article.categorie.nom if obj.article.categorie else None,
        }
    
    def get_mouvement_info(self, obj):
        """Retourne les informations du mouvement de stock."""
        if not obj.mouvement_stock:
            return None
        
        mouvement = obj.mouvement_stock
        date_formatee = mouvement.date_mouvement.strftime('%d/%m/%Y à %H:%M') if mouvement.date_mouvement else None
        
        return {
            'id': mouvement.id,
            'type_mouvement': mouvement.type_mouvement,
            'quantite': mouvement.quantite,
            'stock_avant': mouvement.stock_avant,
            'stock_apres': mouvement.stock_apres,
            'date_mouvement': mouvement.date_mouvement,
            'date_mouvement_formatee': date_formatee,
            'commentaire': mouvement.commentaire,
            'reference_document': mouvement.reference_document,
            'utilisateur': mouvement.utilisateur,
        }
