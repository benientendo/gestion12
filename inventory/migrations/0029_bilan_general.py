# -*- coding: utf-8 -*-
"""
Migration pour ajouter les modèles de bilan général
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0013_boutique_derniere_lecture_articles_negocies_and_more'),
    ]

    operations = [
        # Création du modèle BilanGeneral
        migrations.CreateModel(
            name='BilanGeneral',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titre', models.CharField(help_text='Titre du bilan', max_length=200)),
                ('description', models.TextField(blank=True, help_text='Description du bilan')),
                ('periode', models.CharField(choices=[('JOURNALIER', 'Journalier'), ('HEBDOMADAIRE', 'Hebdomadaire'), ('MENSUEL', 'Mensuel'), ('TRIMESTRIEL', 'Trimestriel'), ('SEMESTRIEL', 'Semestriel'), ('ANNUEL', 'Annuel')], default='MENSUEL', max_length=20)),
                ('date_debut', models.DateTimeField(help_text='Date de début de la période')),
                ('date_fin', models.DateTimeField(help_text='Date de fin de la période')),
                ('date_generation', models.DateTimeField(auto_now_add=True, help_text='Date de génération du bilan')),
                ('statut', models.CharField(choices=[('BROUILLON', 'Brouillon'), ('VALIDE', 'Validé'), ('ARCHIVE', 'Archivé')], default='BROUILLON', max_length=20)),
                ('valide_par', models.CharField(blank=True, max_length=100, help_text='Utilisateur ayant validé le bilan')),
                ('date_validation', models.DateTimeField(blank=True, null=True)),
                ('chiffre_affaires_total', models.DecimalField(decimal_places=2, default=0, help_text='Chiffre d\'affaires total CDF', max_digits=15)),
                ('chiffre_affaires_total_usd', models.DecimalField(decimal_places=2, default=0, help_text='Chiffre d\'affaires total USD', max_digits=15)),
                ('cout_achats_marchandises', models.DecimalField(decimal_places=2, default=0, help_text='Coût total des achats de marchandises', max_digits=15)),
                ('marge_brute', models.DecimalField(decimal_places=2, default=0, help_text='Marge brute (CA - Coûts)', max_digits=15)),
                ('taux_marge_brute', models.DecimalField(decimal_places=2, default=0, help_text='Taux de marge brute (%)', max_digits=5)),
                ('depenses_operationnelles', models.DecimalField(decimal_places=2, default=0, help_text='Dépenses opérationnelles totales', max_digits=15)),
                ('depenses_personnel', models.DecimalField(decimal_places=2, default=0, help_text='Dépenses de personnel', max_digits=15)),
                ('depenses_loyer', models.DecimalField(decimal_places=2, default=0, help_text='Dépenses de loyer', max_digits=15)),
                ('depenses_services', models.DecimalField(decimal_places=2, default=0, help_text='Dépenses de services (électricité, eau, etc.)', max_digits=15)),
                ('autres_depenses', models.DecimalField(decimal_places=2, default=0, help_text='Autres dépenses', max_digits=15)),
                ('resultat_operationnel', models.DecimalField(decimal_places=2, default=0, help_text='Résultat opérationnel', max_digits=15)),
                ('resultat_net', models.DecimalField(decimal_places=2, default=0, help_text='Résultat net', max_digits=15)),
                ('nombre_ventes', models.IntegerField(default=0, help_text='Nombre total de ventes')),
                ('panier_moyen', models.DecimalField(decimal_places=2, default=0, help_text='Panier moyen par vente', max_digits=10)),
                ('taux_conversion', models.DecimalField(decimal_places=2, default=0, help_text='Taux de conversion (%)', max_digits=5)),
                ('valeur_stock_initiale', models.DecimalField(decimal_places=2, default=0, help_text='Valeur du stock initial', max_digits=15)),
                ('valeur_stock_finale', models.DecimalField(decimal_places=2, default=0, help_text='Valeur du stock final', max_digits=15)),
                ('variation_stock', models.DecimalField(decimal_places=2, default=0, help_text='Variation de stock', max_digits=15)),
                ('donnees_detaillees', models.JSONField(blank=True, default=dict, help_text='Données détaillées du bilan')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('boutique', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='bilans', to='inventory.boutique')),
                ('commercant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='bilans_generaux', to='inventory.commercant')),
            ],
            options={
                'verbose_name': 'Bilan général',
                'verbose_name_plural': 'Bilans généraux',
                'ordering': ['-date_generation'],
            },
        ),

        # Création du modèle IndicateurPerformance
        migrations.CreateModel(
            name='IndicateurPerformance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(help_text='Nom de l\'indicateur', max_length=100)),
                ('description', models.TextField(blank=True, help_text='Description de l\'indicateur')),
                ('categorie', models.CharField(choices=[('VENTES', 'Ventes'), ('STOCK', 'Stock'), ('FINANCIER', 'Financier'), ('OPERATIONNEL', 'Opérationnel'), ('CLIENT', 'Client')], max_length=20)),
                ('periodicite', models.CharField(choices=[('REEL', 'En temps réel'), ('QUOTIDIEN', 'Quotidien'), ('HEBDOMADAIRE', 'Hebdomadaire'), ('MENSUEL', 'Mensuel')], default='REEL', max_length=20)),
                ('formule', models.JSONField(help_text='Formule de calcul de l\'indicateur')),
                ('valeur_actuelle', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('valeur_precedente', models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ('variation_pourcentage', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('objectif', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ('seuil_alerte', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ('date_derniere_maj', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('boutique', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='indicateurs', to='inventory.boutique')),
                ('commercant', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='indicateurs', to='inventory.commercant')),
            ],
            options={
                'verbose_name': 'Indicateur de performance',
                'verbose_name_plural': 'Indicateurs de performance',
                'ordering': ['categorie', 'nom'],
            },
        ),

        # Ajout des index pour optimiser les performances
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS bilan_commercant_periode_idx ON inventory_bilangeneral (commercant_id, periode, date_generation);",
            reverse_sql="DROP INDEX IF EXISTS bilan_commercant_periode_idx;"
        ),

        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS bilan_boutique_date_idx ON inventory_bilangeneral (boutique_id, date_generation);",
            reverse_sql="DROP INDEX IF EXISTS bilan_boutique_date_idx;"
        ),

        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS bilan_statut_date_idx ON inventory_bilangeneral (statut, date_generation);",
            reverse_sql="DROP INDEX IF EXISTS bilan_statut_date_idx;"
        ),

        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS indicateur_client_lue_date_idx ON inventory_indicateurperformance (commercant_id, categorie, nom);",
            reverse_sql="DROP INDEX IF EXISTS indicateur_client_lue_date_idx;"
        ),
    ]
