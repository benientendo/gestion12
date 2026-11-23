from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0086_propositioninventaire_quantite_appliquee'),
    ]

    operations = [
        migrations.AddField(
            model_name='transfertstock',
            name='date_refus',
            field=models.DateTimeField(
                blank=True,
                help_text="Refus de réception par la destination : la quantité est revenue à la source",
                null=True,
            ),
        ),
    ]
