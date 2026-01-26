from django.db import models
from django.db.models import Sum, F, Count, Q, Avg
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class BilanGeneral(models.Model):
    """
    Modèle pour générer et stocker des bilans généraux complets 
    selon les bonnes pratiques de gestion.
    """
    
    PERIODE_CHOICES = [
        ('JOURNALIER', 'Journalier'),
        ('HEBDOMADAIRE', 'Hebdomadaire'),
        ('MENSUEL', 'Mensuel'),
        ('TRIMESTRIEL', 'Trimestriel'),
        ('SEMESTRIEL', 'Semestriel'),
        ('ANNUEL', 'Annuel'),
    ]
    
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('VALIDE', 'Validé'),
        ('ARCHIVE', 'Archivé'),
    ]
    
    # Informations générales
    titre = models.CharField(max_length=200, help_text="Titre du bilan")
    description = models.TextField(blank=True, help_text="Description du bilan")
    
    # Période et dates
    periode = models.CharField(max_length=20, choices=PERIODE_CHOICES, default='MENSUEL')
    date_debut = models.DateTimeField(help_text="Date de début de la période")
    date_fin = models.DateTimeField(help_text="Date de fin de la période")
    date_generation = models.DateTimeField(auto_now_add=True, help_text="Date de génération du bilan")
    
    # Association avec le commerçant et/ou la boutique
    commercant = models.ForeignKey('Commercant', on_delete=models.CASCADE, related_name='bilans_generaux',
                                 null=True, blank=True, help_text="Commerçant concerné (si bilan global)")
    boutique = models.ForeignKey('Boutique', on_delete=models.CASCADE, related_name='bilans',
                               null=True, blank=True, help_text="Boutique spécifique (si bilan par boutique)")
    
    # Statut du bilan
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    valide_par = models.CharField(max_length=100, blank=True, help_text="Utilisateur ayant validé le bilan")
    date_validation = models.DateTimeField(null=True, blank=True)
    
    # Données financières principales
    chiffre_affaires_total = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Chiffre d'affaires total CDF")
    chiffre_affaires_total_usd = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Chiffre d'affaires total USD")
    
    # Coûts et marges
    cout_achats_marchandises = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Coût total des achats de marchandises")
    marge_brute = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Marge brute (CA - Coûts)")
    taux_marge_brute = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Taux de marge brute (%)")
    
    # Dépenses opérationnelles
    depenses_operationnelles = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Dépenses opérationnelles totales")
    depenses_personnel = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Dépenses de personnel")
    depenses_loyer = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Dépenses de loyer")
    depenses_services = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Dépenses de services (électricité, eau, etc.)")
    autres_depenses = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Autres dépenses")
    
    # Résultats
    resultat_operationnel = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Résultat opérationnel")
    resultat_net = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Résultat net")
    
    # Indicateurs de performance
    nombre_ventes = models.IntegerField(default=0, help_text="Nombre total de ventes")
    panier_moyen = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Panier moyen par vente")
    taux_conversion = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Taux de conversion (%)")
    
    # Stock et inventaire
    valeur_stock_initiale = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Valeur du stock initial")
    valeur_stock_finale = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Valeur du stock final")
    variation_stock = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Variation de stock")
    
    # Données détaillées en JSON
    donnees_detaillees = models.JSONField(default=dict, blank=True, help_text="Données détaillées du bilan")
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Bilan général"
        verbose_name_plural = "Bilans généraux"
        ordering = ['-date_generation']
        indexes = [
            models.Index(fields=['commercant', 'periode', '-date_generation'], name='bilan_commercant_periode_idx'),
            models.Index(fields=['boutique', '-date_generation'], name='bilan_boutique_date_idx'),
            models.Index(fields=['statut', '-date_generation'], name='bilan_statut_date_idx'),
        ]
    
    def __str__(self):
        if self.boutique:
            return f"Bilan {self.periode} - {self.boutique.nom} ({self.date_debut.strftime('%d/%m/%Y')})"
        elif self.commercant:
            return f"Bilan {self.periode} - {self.commercant.nom_entreprise} ({self.date_debut.strftime('%d/%m/%Y')})"
        return f"Bilan {self.periode} ({self.date_debut.strftime('%d/%m/%Y')})"
    
    def generer_donnees(self):
        """Génère automatiquement les données du bilan selon les bonnes pratiques de gestion"""
        from .models import Vente, LigneVente, Article, MouvementStock, RapportCaisse
        
        logger.info(f"Génération du bilan: {self.titre}")
        
        # Déterminer le scope (commercant ou boutique)
        if self.boutique:
            ventes_qs = Vente.objects.filter(
                boutique=self.boutique,
                date_vente__gte=self.date_debut,
                date_vente__lte=self.date_fin,
                est_annulee=False
            )
            articles_qs = Article.objects.filter(boutique=self.boutique, est_actif=True)
            rapports_qs = RapportCaisse.objects.filter(
                boutique=self.boutique,
                date_rapport__gte=self.date_debut,
                date_rapport__lte=self.date_fin
            )
        elif self.commercant:
            boutiques = self.commercant.boutiques.all()
            ventes_qs = Vente.objects.filter(
                boutique__in=boutiques,
                date_vente__gte=self.date_debut,
                date_vente__lte=self.date_fin,
                est_annulee=False
            )
            articles_qs = Article.objects.filter(boutique__in=boutiques, est_actif=True)
            rapports_qs = RapportCaisse.objects.filter(
                boutique__in=boutiques,
                date_rapport__gte=self.date_debut,
                date_rapport__lte=self.date_fin
            )
        else:
            logger.error("Le bilan doit être associé à un commerçant ou une boutique")
            return False
        
        # 1. Chiffre d'affaires
        ventes_cdf = ventes_qs.filter(devise='CDF')
        ventes_usd = ventes_qs.filter(devise='USD')
        
        self.chiffre_affaires_total = ventes_cdf.aggregate(total=Sum('montant_total'))['total'] or 0
        self.chiffre_affaires_total_usd = ventes_usd.aggregate(total=Sum('montant_total_usd'))['total'] or 0
        
        # 2. Nombre de ventes et panier moyen
        self.nombre_ventes = ventes_qs.count()
        if self.nombre_ventes > 0:
            total_ventes_cdf_usd = self.chiffre_affaires_total + (self.chiffre_affaires_total_usd * self.commercant.taux_dollar if self.commercant else 2800)
            self.panier_moyen = total_ventes_cdf_usd / self.nombre_ventes
        
        # 3. Coût des achats et marges
        lignes_ventes = LigneVente.objects.filter(vente__in=ventes_qs)
        
        # Calcul du coût des marchandises vendues
        cout_total = Decimal('0')
        for ligne in lignes_ventes:
            if ligne.article.prix_achat:
                cout_total += ligne.quantite * ligne.article.prix_achat
        
        self.cout_achats_marchandises = cout_total
        
        # 4. Marges
        total_ca_cdf_usd = self.chiffre_affaires_total + (self.chiffre_affaires_total_usd * (self.commercant.taux_dollar if self.commercant else 2800))
        self.marge_brute = total_ca_cdf_usd - self.cout_achats_marchandises
        
        if total_ca_cdf_usd > 0:
            self.taux_marge_brute = (self.marge_brute / total_ca_cdf_usd) * 100
        
        # 5. Dépenses opérationnelles (depuis les rapports de caisse)
        depenses_cdf = rapports_qs.filter(devise='CDF')
        depenses_usd = rapports_qs.filter(devise='USD')
        
        total_depenses_cdf = depenses_cdf.aggregate(total=Sum('depense'))['total'] or 0
        total_depenses_usd = depenses_usd.aggregate(total=Sum('depense'))['total'] or 0
        
        # Convertir les dépenses USD en CDF
        taux_change = self.commercant.taux_dollar if self.commercant else 2800
        self.depenses_operationnelles = total_depenses_cdf + (total_depenses_usd * taux_change)
        
        # Répartition des dépenses (estimation basique - à affiner selon les besoins)
        self.depenses_personnel = self.depenses_operationnelles * Decimal('0.4')  # 40% pour le personnel
        self.depenses_loyer = self.depenses_operationnelles * Decimal('0.2')     # 20% pour le loyer
        self.depenses_services = self.depenses_operationnelles * Decimal('0.15')  # 15% pour les services
        self.autres_depenses = self.depenses_operationnelles * Decimal('0.25')    # 25% autres
        
        # 6. Résultats
        self.resultat_operationnel = self.marge_brute - self.depenses_operationnelles
        self.resultat_net = self.resultat_operationnel  # Simplifié - pas d'impôts pour le moment
        
        # 7. Valeur du stock
        # Stock initial (début de période)
        mouvements_entree_avant = MouvementStock.objects.filter(
            article__in=articles_qs,
            type_mouvement='ENTREE',
            date_mouvement__lt=self.date_debut
        )
        mouvements_sortie_avant = MouvementStock.objects.filter(
            article__in=articles_qs,
            type_mouvement='SORTIE',
            date_mouvement__lt=self.date_debut
        )
        
        total_entree_avant = mouvements_entree_avant.aggregate(total=Sum('quantite'))['total'] or 0
        total_sortie_avant = mouvements_sortie_avant.aggregate(total=Sum('quantite'))['total'] or 0
        
        # Calcul de la valeur du stock initial
        self.valeur_stock_initiale = Decimal('0')
        for article in articles_qs:
            stock_initial = article.quantite_stock - (total_entree_avant - total_sortie_avant)
            if stock_initial > 0 and article.prix_achat:
                self.valeur_stock_initiale += stock_initial * article.prix_achat
        
        # Stock final (fin de période)
        self.valeur_stock_finale = articles_qs.aggregate(
            total=Sum(F('quantite_stock') * F('prix_achat'))
        )['total'] or 0
        
        self.variation_stock = self.valeur_stock_finale - self.valeur_stock_initiale
        
        # 8. Données détaillées pour analyse
        self.donnees_detaillees = {
            'ventes_par_jour': self._get_ventes_par_jour(ventes_qs),
            'top_articles': self._get_top_articles(lignes_ventes),
            'categories_performance': self._get_categories_performance(lignes_ventes),
            'mouvements_stock': self._get_mouvements_stock_resume(articles_qs, self.date_debut, self.date_fin),
            'indicateurs_cles': {
                'marge_par_vente': float(self.marge_brute / self.nombre_ventes) if self.nombre_ventes > 0 else 0,
                'rotation_stock': self._calculer_rotation_stock(),
                'rentabilite': float((self.resultat_net / total_ca_cdf_usd) * 100) if total_ca_cdf_usd > 0 else 0,
            }
        }
        
        logger.info(f"Bilan généré avec succès: CA={self.chiffre_affaires_total}, Marge={self.marge_brute}, Résultat={self.resultat_net}")
        return True
    
    def _get_ventes_par_jour(self, ventes_qs):
        """Retourne les ventes regroupées par jour"""
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        
        ventes_par_jour = ventes_qs.annotate(
            jour=TruncDate('date_vente')
        ).values('jour').annotate(
            nb_ventes=Count('id'),
            ca_total=Sum('montant_total'),
            ca_usd_total=Sum('montant_total_usd')
        ).order('jour')
        
        return [
            {
                'date': v['jour'].strftime('%Y-%m-%d'),
                'nb_ventes': v['nb_ventes'],
                'ca_cdf': float(v['ca_total'] or 0),
                'ca_usd': float(v['ca_usd_total'] or 0)
            }
            for v in ventes_par_jour
        ]
    
    def _get_top_articles(self, lignes_ventes):
        """Retourne les articles les plus vendus"""
        top_articles = lignes_ventes.values(
            'article__nom', 'article__code'
        ).annotate(
            quantite_totale=Sum('quantite'),
            total_vente=Sum(F('quantite') * F('prix_unitaire'))
        ).order_by('-quantite_totale')[:10]
        
        return [
            {
                'nom': a['article__nom'],
                'code': a['article__code'],
                'quantite': a['quantite_totale'],
                'total': float(a['total_vente'])
            }
            for a in top_articles
        ]
    
    def _get_categories_performance(self, lignes_ventes):
        """Retourne la performance par catégorie"""
        from django.db.models import Value
        categories_perf = lignes_ventes.values(
            'article__categorie__nom'
        ).annotate(
            quantite_totale=Sum('quantite'),
            total_vente=Sum(F('quantite') * F('prix_unitaire'))
        ).order_by('-total_vente')
        
        return [
            {
                'categorie': c['article__categorie__nom'] or 'Non catégorisé',
                'quantite': c['quantite_totale'],
                'total': float(c['total_vente'])
            }
            for c in categories_perf
        ]
    
    def _get_mouvements_stock_resume(self, articles_qs, date_debut, date_fin):
        """Retourne un résumé des mouvements de stock"""
        from .models import MouvementStock
        
        mouvements = MouvementStock.objects.filter(
            article__in=articles_qs,
            date_mouvement__gte=date_debut,
            date_mouvement__lte=date_fin
        )
        
        entrees = mouvements.filter(type_mouvement='ENTREE').aggregate(total=Sum('quantite'))['total'] or 0
        sorties = mouvements.filter(type_mouvement='SORTIE').aggregate(total=Sum('quantite'))['total'] or 0
        
        return {
            'entrees': entrees,
            'sorties': abs(sorties),
            'variation': entrees - abs(sorties)
        }
    
    def _calculer_rotation_stock(self):
        """Calcule le ratio de rotation du stock"""
        if self.cout_achats_marchandises == 0:
            return 0
        
        stock_moyen = (self.valeur_stock_initiale + self.valeur_stock_finale) / 2
        if stock_moyen == 0:
            return 0
        
        return float(self.cout_achats_marchandises / stock_moyen)
    
    def valider(self, utilisateur):
        """Valide le bilan"""
        self.statut = 'VALIDE'
        self.valide_par = utilisateur
        self.date_validation = timezone.now()
        self.save()
        logger.info(f"Bilan {self.id} validé par {utilisateur}")
    
    def archiver(self):
        """Archive le bilan"""
        self.statut = 'ARCHIVE'
        self.save()
        logger.info(f"Bilan {self.id} archivé")


class IndicateurPerformance(models.Model):
    """
    Modèle pour stocker des indicateurs de performance clés (KPIs)
    """
    
    CATEGORIE_CHOICES = [
        ('VENTES', 'Ventes'),
        ('STOCK', 'Stock'),
        ('FINANCIER', 'Financier'),
        ('OPERATIONNEL', 'Opérationnel'),
        ('CLIENT', 'Client'),
    ]
    
    PERIODICITE_CHOICES = [
        ('REEL', 'En temps réel'),
        ('QUOTIDIEN', 'Quotidien'),
        ('HEBDOMADAIRE', 'Hebdomadaire'),
        ('MENSUEL', 'Mensuel'),
    ]
    
    nom = models.CharField(max_length=100, help_text="Nom de l'indicateur")
    description = models.TextField(blank=True, help_text="Description de l'indicateur")
    categorie = models.CharField(max_length=20, choices=CATEGORIE_CHOICES)
    periodicite = models.CharField(max_length=20, choices=PERIODICITE_CHOICES, default='REEL')
    
    # Formule de calcul (stockée en JSON pour flexibilité)
    formule = models.JSONField(help_text="Formule de calcul de l'indicateur")
    
    # Valeurs actuelles
    valeur_actuelle = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    valeur_precedente = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    variation_pourcentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Objectifs
    objectif = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    seuil_alerte = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    
    # Associations
    boutique = models.ForeignKey('Boutique', on_delete=models.CASCADE, related_name='indicateurs',
                               null=True, blank=True)
    commercant = models.ForeignKey('Commercant', on_delete=models.CASCADE, related_name='indicateurs',
                                 null=True, blank=True)
    
    # Métadonnées
    date_derniere_maj = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Indicateur de performance"
        verbose_name_plural = "Indicateurs de performance"
        ordering = ['categorie', 'nom']
        unique_together = ['nom', 'boutique', 'commercant']
    
    def __str__(self):
        return f"{self.nom} - {self.get_categorie_display()}"
    
    def calculer_variation(self):
        """Calcule la variation en pourcentage par rapport à la période précédente"""
        if self.valeur_precedente != 0:
            self.variation_pourcentage = ((self.valeur_actuelle - self.valeur_precedente) / self.valeur_precedente) * 100
        else:
            self.variation_pourcentage = 0
        self.save()
    
    def est_en_alerte(self):
        """Vérifie si l'indicateur est en alerte"""
        if self.seuil_alerte is not None:
            if self.categorie in ['VENTES', 'FINANCIER']:
                return self.valeur_actuelle < self.seuil_alerte
            else:
                return self.valeur_actuelle > self.seuil_alerte
        return False
