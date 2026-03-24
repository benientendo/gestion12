"""
Recalcule montant_total depuis les LigneVente pour une ou plusieurs ventes.
Usage:
    python manage.py recalculer_total_ventes --factures QRU50NU-20260325022946724-ee5a273d QRU50NU-20260325023914134-756657b1
    python manage.py recalculer_total_ventes --all   # toutes les ventes
"""
from django.core.management.base import BaseCommand
from django.db.models import Sum, F
from inventory.models import Vente


class Command(BaseCommand):
    help = "Recalcule montant_total depuis les lignes de vente"

    def add_arguments(self, parser):
        parser.add_argument('--factures', nargs='+', type=str, help='Numéros de facture à corriger')
        parser.add_argument('--all', action='store_true', help='Recalculer toutes les ventes')

    def handle(self, *args, **options):
        if options['all']:
            ventes = Vente.objects.all()
        elif options['factures']:
            ventes = Vente.objects.filter(numero_facture__in=options['factures'])
            if not ventes.exists():
                self.stderr.write(f"Aucune vente trouvée pour: {options['factures']}")
                return
        else:
            self.stderr.write("Utilisez --factures ou --all")
            return

        nb_corrigees = 0
        for vente in ventes:
            total_depuis_lignes = (
                vente.lignes.filter(devise='CDF')
                .aggregate(total=Sum(F('prix_unitaire') * F('quantite')))['total'] or 0
            )
            ancien = vente.montant_total
            if abs(float(ancien) - float(total_depuis_lignes)) > 0.01:
                vente.montant_total = total_depuis_lignes
                vente.save(update_fields=['montant_total'])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✔ {vente.numero_facture}: {ancien} → {total_depuis_lignes} FC"
                    )
                )
                nb_corrigees += 1
            else:
                self.stdout.write(f"  {vente.numero_facture}: OK ({ancien} FC)")

        self.stdout.write(self.style.SUCCESS(f"\n{nb_corrigees} vente(s) corrigée(s)."))
