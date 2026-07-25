#!/usr/bin/env python
"""Script de réconciliation automatique des stocks"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')
django.setup()

from django.db import transaction
from django.db.models import Sum
from inventory.models import Article, MouvementStock, AlerteStock
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def recalculer_stock(article):
    stock_calcule = MouvementStock.objects.filter(article=article).aggregate(total=Sum('quantite'))['total'] or 0
    return stock_calcule, article.quantite_stock, stock_calcule != article.quantite_stock

def identifier_negatifs():
    return list(Article.objects.filter(quantite_stock__lt=0, est_actif=True).select_related('boutique'))

def identifier_incoherences():
    incoherences = []
    for article in Article.objects.filter(est_actif=True):
        calc, actuel, diverge = recalculer_stock(article)
        if diverge:
            incoherences.append({'article': article, 'actuel': actuel, 'calc': calc})
    return incoherences

def corriger(article, stock_correct):
    article.quantite_stock = stock_correct
    article.save(update_fields=['quantite_stock'])
    AlerteStock.objects.filter(article=article, type_alerte='STOCK_NEGATIF', est_resolue=False).update(est_resolue=True)
    logger.info(f"✅ {article.code}: {article.quantite_stock} → {stock_correct}")

def reconcilier(corriger=True):
    logger.info("🔍 Réconciliation des stocks...")
    
    # Stocks négatifs
    negatifs = identifier_negatifs()
    logger.info(f"⚠️ Stocks négatifs: {len(negatifs)}")
    
    # Incohérences
    incoherences = identifier_incoherences()
    logger.info(f"⚠️ Incohérences: {len(incoherences)}")
    
    if not corriger:
        return
    
    # Corriger
    with transaction.atomic():
        for item in incoherences:
            corriger(item['article'], item['calc'])
        
        for article in negatifs:
            calc, _, _ = recalculer_stock(article)
            if calc >= 0:
                corriger(article, calc)
    
    logger.info("✅ Réconciliation terminée")

if __name__ == '__main__':
    reconcilier(corriger=True)
