from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0042_inventaire_ligneinventaire'),
    ]

    operations = [
        migrations.RenameField(
            model_name='inventaire',
            old_name='depot',
            new_name='boutique',
        ),
    ]
