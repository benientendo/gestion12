"""
Management command to fix USD sales that have montant_total_usd = 0 or NULL.
Recalculates montant_total_usd from the ligne_vente data.
"""
from django.core.management.base import BaseCommand
from django.db.models import Sum
from inventory.models import Vente, LigneVente
from decimal import Decimal


class Command(BaseCommand):
    help = 'Fix USD sales with missing or zero montant_total_usd'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Find USD sales with problematic montant_total_usd
        ventes_usd = Vente.objects.filter(devise='USD')
        
        self.stdout.write(f"Found {ventes_usd.count()} USD sales total")
        
        fixed_count = 0
        
        for vente in ventes_usd:
            # Calculate what montant_total_usd should be from lignes
            lignes = vente.lignes.all()
            
            calculated_usd = Decimal('0')
            for ligne in lignes:
                # For USD sales, use prix_unitaire_usd or fall back to prix_unitaire
                prix_usd = ligne.prix_unitaire_usd or ligne.prix_unitaire or Decimal('0')
                calculated_usd += prix_usd * ligne.quantite
            
            current_usd = vente.montant_total_usd or Decimal('0')
            
            # Check if fix is needed
            if calculated_usd > 0 and (current_usd == 0 or vente.montant_total_usd is None):
                self.stdout.write(
                    f"  Vente #{vente.numero_facture}: "
                    f"current={current_usd}, calculated={calculated_usd}"
                )
                
                if not dry_run:
                    vente.montant_total_usd = calculated_usd
                    vente.save(update_fields=['montant_total_usd'])
                    self.stdout.write(self.style.SUCCESS(f"    -> Fixed!"))
                else:
                    self.stdout.write(self.style.WARNING(f"    -> Would fix (dry-run)"))
                
                fixed_count += 1
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\nDry run: {fixed_count} sales would be fixed. "
                f"Run without --dry-run to apply changes."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\nFixed {fixed_count} USD sales."
            ))
