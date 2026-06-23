from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from inventory.models import MouvementStock


class Command(BaseCommand):
    help = "Supprime les mouvements de stock de plus de 3 mois"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Affiche le nombre de lignes à supprimer sans rien supprimer",
        )

    def handle(self, *args, **options):
        limite = timezone.now() - timedelta(days=90)
        qs = MouvementStock.objects.filter(date_mouvement__lt=limite)
        total = qs.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS("Aucun mouvement de plus de 3 mois trouvé."))
            return

        self.stdout.write(f"Mouvements de stock antérieurs au {limite.strftime('%d/%m/%Y')} : {total} ligne(s)")

        if options['dry_run']:
            self.stdout.write(self.style.WARNING("Mode --dry-run : aucune suppression effectuée."))
            return

        deleted, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(f"{deleted} mouvement(s) supprimé(s) avec succès."))
