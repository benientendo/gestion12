"""Recalculer stock_precedent pour toutes les boutiques (utiliser valeur_stock_reel de la veille)."""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_magazin.settings')

import django
django.setup()

from inventory.models import Boutique
from inventory.journal_valeur_stock import recalculer_tout_depuis_debut

for b in Boutique.objects.all():
    print(f"Recalcul {b.nom} (id={b.id})...")
    recalculer_tout_depuis_debut(b)

print("Terminé !")
