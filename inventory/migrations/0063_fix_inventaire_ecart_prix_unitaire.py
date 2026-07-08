# Generated migration to fix inventory ecart values

from django.db import migrations


def fix_inventaire_prix_unitaire(apps, schema_editor):
    """
    Corrige les lignes d'inventaire avec prix_unitaire=0 en utilisant le prix_vente.
    Recalcule les valeur_ecart pour ces lignes.
    """
    LigneInventaire = apps.get_model('inventory', 'LigneInventaire')
    
    # Récupérer les lignes avec prix_unitaire=0 mais prix_vente>0
    lignes_a_corriger = LigneInventaire.objects.filter(
        prix_unitaire=0
    ).exclude(
        article__prix_vente=0
    )
    
    count = lignes_a_corriger.count()
    if count > 0:
        for ligne in lignes_a_corriger:
            ligne.prix_unitaire = ligne.article.prix_vente
            # Recalculer la valeur de l'écart si stock physique est saisi
            if ligne.stock_physique is not None:
                ligne.ecart = ligne.stock_physique - ligne.stock_theorique
                ligne.valeur_ecart = ligne.ecart * ligne.prix_unitaire
            ligne.save()


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0062_telechargement_rapport_mensuel'),
    ]

    operations = [
        migrations.RunPython(fix_inventaire_prix_unitaire),
    ]
