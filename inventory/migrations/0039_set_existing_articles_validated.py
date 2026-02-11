# Generated manually - Set all existing articles as validated
from django.db import migrations


def set_existing_articles_validated(apps, schema_editor):
    """
    Marquer tous les articles existants comme validés par le client.
    Cela évite que les articles existants disparaissent de l'app MAUI.
    """
    Article = apps.get_model('inventory', 'Article')
    # Mettre à jour tous les articles actifs pour les marquer comme validés
    Article.objects.filter(est_actif=True).update(est_valide_client=True)


def reverse_validation(apps, schema_editor):
    """Reverse: remettre tous les articles comme non validés."""
    Article = apps.get_model('inventory', 'Article')
    Article.objects.all().update(est_valide_client=False)


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0038_add_article_validation_fields'),
    ]

    operations = [
        migrations.RunPython(set_existing_articles_validated, reverse_validation),
    ]
