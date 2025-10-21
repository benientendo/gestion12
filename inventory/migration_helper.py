"""
Script d'aide pour la migration vers l'architecture multi-commerçants.
Ce script doit être exécuté AVANT d'appliquer les nouvelles migrations.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from inventory.models import Commercant, Boutique, Client, Article, Categorie, Vente, ScanRecent, MouvementStock

class Command(BaseCommand):
    help = 'Migre les données existantes vers la nouvelle architecture multi-commerçants'

    def handle(self, *args, **options):
        self.stdout.write('Début de la migration des données...')
        
        try:
            with transaction.atomic():
                # 1. Créer un commerçant par défaut pour les données existantes
                admin_user = User.objects.filter(is_superuser=True).first()
                if not admin_user:
                    self.stdout.write(self.style.ERROR('Aucun super utilisateur trouvé. Créez-en un d\'abord.'))
                    return
                
                # Créer un commerçant par défaut
                commercant_defaut, created = Commercant.objects.get_or_create(
                    user=admin_user,
                    defaults={
                        'nom_entreprise': 'Entreprise par défaut',
                        'est_actif': True,
                        'max_boutiques': 10,
                        'notes_admin': 'Commerçant créé automatiquement lors de la migration'
                    }
                )
                
                if created:
                    self.stdout.write(f'Commerçant par défaut créé: {commercant_defaut.nom_entreprise}')
                
                # 2. Créer une boutique par défaut
                boutique_defaut, created = Boutique.objects.get_or_create(
                    commercant=commercant_defaut,
                    nom='Boutique principale',
                    defaults={
                        'type_commerce': 'AUTRE',
                        'adresse': 'Adresse non spécifiée',
                        'ville': 'Ville non spécifiée',
                        'code_postal': '00000',
                        'est_active': True
                    }
                )
                
                if created:
                    self.stdout.write(f'Boutique par défaut créée: {boutique_defaut.nom}')
                
                self.stdout.write(self.style.SUCCESS('Migration des données terminée avec succès!'))
                self.stdout.write(f'Commerçant ID: {commercant_defaut.id}')
                self.stdout.write(f'Boutique ID: {boutique_defaut.id}')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erreur lors de la migration: {str(e)}'))
            raise
