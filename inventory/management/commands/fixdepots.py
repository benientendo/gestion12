from django.core.management.base import BaseCommand
from inventory.models import Commercant, Boutique


class Command(BaseCommand):
    help = 'Create depots for commercants that do not have one'

    def handle(self, *args, **options):
        created = 0
        existing = 0
        
        for c in Commercant.objects.all():
            if not c.boutiques.filter(est_depot=True).exists():
                Boutique.objects.create(
                    nom='Depot Central - ' + c.nom_entreprise,
                    commercant=c,
                    type_commerce='DEPOT',
                    est_depot=True,
                    est_active=True
                )
                self.stdout.write(self.style.SUCCESS(f'Depot created for {c.nom_entreprise}'))
                created += 1
            else:
                self.stdout.write(f'{c.nom_entreprise} already has a depot')
                existing += 1
        
        self.stdout.write(self.style.SUCCESS(f'Done: {created} created, {existing} existing'))
