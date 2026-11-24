"""
Données : reclassification du journal de valeur de stock.

Les colonnes de flux du journal étaient alimentées par des règles qui :

- classaient les retours de refus de réception (RETOUR-…) dans « Transfert IN »
  alors qu'il s'agit de marchandise qui rentre au dépôt, pas d'un transfert
  reçu entre boutiques ;
- laissaient « Transfert IN » sans les transferts dépôt→PDV confirmés par
  validation MAUI (réf. VALIDATION-…), qui atterrissaient dans « Stock ajouté » ;
- laissaient « Inventaire » à zéro après une régularisation d'inventaire
  (réf. INV-…), envoyée dans « Stock ajouté » / « Stock sorti ».

On réécrit les colonnes de flux (Inventaire, Stock ajouté, Transfert IN,
Transfert OUT, Stock sorti) directement depuis les MouvementStock avec les
règles actuelles de ``inventory.journal_valeur_stock`` — source de vérité
partagée avec l'écriture en direct, le détail cliquable de la page et la
commande ``reclasser_journal_valeur_stock``.

« Ventes », « Modif. prix » et « Réduction » ont des sources propres et ne
sont pas touchées. La chaîne valeur_stock_precedent → valeur_stock_restant est
recalculée ensuite : la somme des colonnes étant inchangée (seule leur
répartition change), le reste du journal est préservé.
"""

from django.db import migrations


def reclasser_journal_valeur_stock(apps, schema_editor):
    from inventory.journal_valeur_stock import reclasser_colonnes_depuis_mouvements

    Boutique = apps.get_model('inventory', 'Boutique')
    for boutique in Boutique.objects.all():
        reclasser_colonnes_depuis_mouvements(boutique)


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0088_ligneventeacompte_remise'),
    ]

    operations = [
        migrations.RunPython(
            reclasser_journal_valeur_stock,
            migrations.RunPython.noop,
        ),
    ]
