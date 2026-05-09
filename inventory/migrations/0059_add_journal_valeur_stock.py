from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0058_add_created_at_to_vente'),
    ]

    operations = [
        migrations.CreateModel(
            name='JournalValeurStock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(help_text='Date du journal (un enregistrement par jour par boutique)')),
                ('valeur_stock_precedent', models.DecimalField(decimal_places=2, default=0, help_text="Valeur du stock au début de la journée (= valeur_stock_restant de la veille)", max_digits=18)),
                ('montant_inventaire', models.DecimalField(decimal_places=2, default=0, help_text='Impact net de la régularisation d\'inventaire (positif ou négatif)', max_digits=18)),
                ('valeur_stock_ajoute', models.DecimalField(decimal_places=2, default=0, help_text='Valeur du stock ajouté par approvisionnement/facture fournisseur', max_digits=18)),
                ('valeur_transfert_entrant', models.DecimalField(decimal_places=2, default=0, help_text="Valeur du stock reçu en provenance d'un autre point de vente", max_digits=18)),
                ('impact_modification_prix', models.DecimalField(decimal_places=2, default=0, help_text="Impact de la modification des prix d'achat sur la valeur du stock existant", max_digits=18)),
                ('valeur_stock_sorti', models.DecimalField(decimal_places=2, default=0, help_text='Total de ce qu\'on a enlevé (sorties manuelles, pertes, etc.)', max_digits=18)),
                ('valeur_transfert_sortant', models.DecimalField(decimal_places=2, default=0, help_text="Valeur du stock transféré vers un autre point de vente", max_digits=18)),
                ('valeur_ventes', models.DecimalField(decimal_places=2, default=0, help_text="Valeur (au prix d'achat) des articles vendus", max_digits=18)),
                ('valeur_stock_restant', models.DecimalField(decimal_places=2, default=0, help_text='Valeur du stock à la fin de la journée', max_digits=18)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('boutique', models.ForeignKey(
                    help_text='Boutique concernée',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='journal_valeur_stock',
                    to='inventory.boutique',
                )),
            ],
            options={
                'verbose_name': 'Journal valeur stock',
                'verbose_name_plural': 'Journal valeur stock',
                'ordering': ['-date'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='journalvaleurstock',
            unique_together={('boutique', 'date')},
        ),
        migrations.AddIndex(
            model_name='journalvaleurstock',
            index=models.Index(fields=['boutique', '-date'], name='idx_journal_boutique_date'),
        ),
    ]
