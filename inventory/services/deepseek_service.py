import requests
import json
from django.conf import settings
from django.core.cache import cache
from inventory.models import Article, Categorie, Boutique

class DeepSeekService:
    """Service pour interagir avec l'API DeepSeek"""
    
    @staticmethod
    def _call_deepseek(prompt, use_json=True):
        """Appel générique à l'API DeepSeek"""
        try:
            payload = {
                "model": settings.DEEPSEEK_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1000,
                "temperature": 0.3,
            }
            
            if use_json:
                payload["response_format"] = {"type": "json_object"}
            
            response = requests.post(
                settings.DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"DeepSeek API Error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"DeepSeek Service Error: {e}")
            return None
    
    @staticmethod
    def suggest_article_data(article_name, boutique_id=None):
        """Suggérer des données pour un article"""
        # Cache pour éviter les appels répétés
        cache_key = f"deepseek_suggest_{article_name}_{boutique_id}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Récupérer le contexte
        try:
            boutique = Boutique.objects.get(id=boutique_id) if boutique_id else None
            articles_similaires = Article.objects.filter(
                nom__icontains=article_name[:10]
            ).values('nom', 'prix_vente', 'prix_achat', 'categorie__nom')[:5]
            
            categories = list(Categorie.objects.values_list('nom', flat=True))
            
            context_articles = "\n".join([
                f"- {a['nom']} | Vente: {a['prix_vente']} FC | Achat: {a['prix_achat']} FC | Cat: {a['categorie__nom']}"
                for a in articles_similaires
            ])
            
            context_categories = ", ".join(categories[:10])
            
        except:
            context_articles = "Non disponible"
            context_categories = "Alimentation, Boisson, Hygiène, Entretien"
        
        prompt = f"""
        Tu es un expert en gestion de magasin en RD Congo.
        
        Article demandé: "{article_name}"
        Boutique: {boutique.nom if boutique else "Non spécifiée"}
        
        Articles similaires existants:
        {context_articles}
        
        Catégories disponibles: {context_categories}
        
        Analyse et suggère:
        1. description_complete: Description détaillée de l'article
        2. prix_vente_suggere: Prix de vente raisonnable en FC
        3. prixAchatEstime: Prix d'achat estimé en FC  
        4. categorie_suggeree: Catégorie la plus appropriée
        5. marge_estimee: Pourcentage de marge estimée
        6. alertes: Alerte si prix semble anormal ou suggestions
        
        Réponds UNIQUEMENT en JSON avec ce format exact:
        {{
            "description_complete": "...",
            "prix_vente_suggere": 0000,
            "prixAchatEstime": 0000,
            "categorie_suggeree": "...",
            "marge_estimee": 00,
            "alertes": "...",
            "articles_similaires_trouves": [...]
        }}
        
        Sois réaliste pour le marché congolais. Les prix doivent être en Francs Congolais (FC).
        """
        
        result = DeepSeekService._call_deepseek(prompt, use_json=True)
        
        if result and 'choices' in result:
            try:
                content = json.loads(result['choices'][0]['message']['content'])
                # Cache pour 30 minutes
                cache.set(cache_key, content, 1800)
                return content
            except json.JSONDecodeError:
                return None
        
        return None
    
    @staticmethod
    def analyze_price_anomaly(article_name, prix_vente, boutique_id=None):
        """Analyser si un prix semble anormal"""
        try:
            articles_similaires = Article.objects.filter(
                nom__icontains=article_name[:10]
            ).values_list('prix_vente', flat=True)
            
            if len(articles_similaires) < 3:
                return None
            
            prix_moyen = sum(articles_similaires) / len(articles_similaires)
            prix_min = min(articles_similaires)
            prix_max = max(articles_similaires)
            
            # Calcul si le prix est anormal (>50% d'écart)
            ecart_pourcentage = abs(prix_vente - prix_moyen) / prix_moyen * 100
            
            if ecart_pourcentage > 50:
                return {
                    "anomalie": True,
                    "prix_moyen": prix_moyen,
                    "prix_min": prix_min,
                    "prix_max": prix_max,
                    "ecart_pourcentage": round(ecart_pourcentage, 1),
                    "message": f"Prix inhabituel ! La moyenne est de {prix_moyen} FC"
                }
            
            return {"anomalie": False}
            
        except:
            return None
    
    @staticmethod
    def get_category_suggestions(article_name):
        """Suggérer une catégorie basée sur le nom de l'article"""
        cache_key = f"deepseek_category_{article_name}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        prompt = f"""
        Article: "{article_name}"
        
        Catégories communes en magasin: Alimentation, Boisson, Hygiène, Entretien, Electronique, Vêtements, Cosmétique, Bureau, Auto, Maison
        
        Quelle est la meilleure catégorie pour cet article ? Réponds avec juste le nom de la catégorie.
        """
        
        result = DeepSeekService._call_deepseek(prompt, use_json=False)
        
        if result and 'choices' in result:
            category = result['choices'][0]['message']['content'].strip()
            cache.set(cache_key, category, 3600)  # 1 heure
            return category
        
        return "Alimentation"  # Par défaut
