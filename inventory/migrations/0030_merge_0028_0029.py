# -*- coding: utf-8 -*-
"""
Migration de fusion pour résoudre le conflit entre les migrations
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0028_notificationstock_quantite_mouvement_and_more'),
        ('inventory', '0029_bilan_general'),
    ]

    operations = [
        # Aucune opération nécessaire - juste fusionner les branches
    ]
