# Migration de données : activation de la validation des saisies d'inventaire
# pour le commerçant « KMC » uniquement.
#
# Le code est générique (flag par commerçant) mais seuls les comptes KMC sont
# activés ici : tous les autres commerçants gardent le comportement historique
# (saisie directe du collaborateur, sans validation).
#
# Idempotente : relancer la migration ne change rien.
from django.db import migrations


def activer_pour_kmc(apps, schema_editor):
    Commercant = apps.get_model('inventory', 'Commercant')
    Commercant.objects.filter(
        nom_entreprise__icontains='KMC'
    ).update(validation_inventaire_requise=True)


def desactiver_pour_kmc(apps, schema_editor):
    Commercant = apps.get_model('inventory', 'Commercant')
    Commercant.objects.filter(
        nom_entreprise__icontains='KMC'
    ).update(validation_inventaire_requise=False)


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0084_commercant_validation_inventaire_requise_and_more'),
    ]

    operations = [
        migrations.RunPython(activer_pour_kmc, desactiver_pour_kmc),
    ]
