from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0077_lignevente_motif_annulation_code_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='venteacompte',
            name='quantite',
            field=models.IntegerField(default=1, help_text="Quantité commandée (prix catalogue × quantité)"),
        ),
    ]
