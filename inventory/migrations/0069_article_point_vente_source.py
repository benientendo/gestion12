from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0068_merchantmessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='point_vente_source',
            field=models.CharField(
                blank=True,
                default='',
                help_text="Point de vente d'origine (ex: KIYAMBU 04 MPOLO, KIYAMBU DUBAI 04 MPOLO)",
                max_length=200,
            ),
        ),
    ]
