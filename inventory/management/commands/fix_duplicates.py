from django.core.management.base import BaseCommand
from django.db import transaction
from inventory.models import Article, MouvementStock
from django.db.models import Count, Sum, Min
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Corrige les articles avec validations en double (meme qte, intervalle court)'

    def add_arguments(self, parser):
        parser.add_argument('--boutique', type=int, default=44, help='ID de la boutique')
        parser.add_argument('--fix', action='store_true', help='Appliquer les corrections')
        parser.add_argument('--interval', type=int, default=5, help='Intervalle max en minutes pour considerer comme doublon')

    def is_doublon(self, mv1, mv2, interval_minutes):
        """
        Detecte si mv2 est un doublon de mv1.
        Criteres:
        - Meme quantite
        - Meme reference document
        - Intervalle < interval_minutes
        """
        if mv1.quantite != mv2.quantite:
            return False
        if mv1.reference_document != mv2.reference_document:
            return False
        delta = abs((mv2.date_mouvement - mv1.date_mouvement).total_seconds())
        if delta > interval_minutes * 60:
            return False
        return True

    def handle(self, *args, **options):
        boutique_id = options['boutique']
        dry_run = not options['fix']
        interval_minutes = options['interval']
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f"=== MODE SIMULATION (intervalle: {interval_minutes} min) ===\n"))
        else:
            self.stdout.write(self.style.SUCCESS(f"=== MODE CORRECTION (intervalle: {interval_minutes} min) ===\n"))

        # Trouver les articles avec plusieurs validations
        articles_multi = MouvementStock.objects.filter(
            article__boutique_id=boutique_id,
            reference_document__startswith="VALIDATION-"
        ).values("article__id").annotate(
            nb=Count("id")
        ).filter(nb__gt=1).order_by("-nb")

        if not articles_multi.exists():
            self.stdout.write("Aucun article avec validations multiples trouve.")
            return

        self.stdout.write(f"Articles avec validations multiples: {articles_multi.count()}\n")
        
        total_corrige = 0
        total_stock_reduit = 0
        total_doublons = 0

        for item in articles_multi:
            article_id = item['article__id']
            
            try:
                article = Article.objects.get(id=article_id)
            except Article.DoesNotExist:
                continue

            # Recuperer tous les mouvements de validation pour cet article
            mouvements = MouvementStock.objects.filter(
                article_id=article_id,
                reference_document__startswith="VALIDATION-"
            ).order_by("date_mouvement")

            mouvements_list = list(mouvements)
            if len(mouvements_list) <= 1:
                continue

            # Identifier les vrais doublons (meme qte, meme ref, intervalle court)
            doublons_a_supprimer = []
            mouvements_garder = []
            
            for i, mv in enumerate(mouvements_list):
                is_dup = False
                # Verifier si ce mouvement est un doublon d'un mouvement precedent
                for mv_garde in mouvements_garder:
                    if self.is_doublon(mv_garde, mv, interval_minutes):
                        doublons_a_supprimer.append(mv)
                        is_dup = True
                        break
                
                if not is_dup:
                    mouvements_garder.append(mv)

            if not doublons_a_supprimer:
                # Pas de vrais doublons pour cet article
                continue

            # Calculer la quantite en trop
            quantite_doublon = sum(m.quantite for m in doublons_a_supprimer)
            
            self.stdout.write(f"\n{article.nom[:40]}")
            self.stdout.write(f"  Code: {article.code}")
            self.stdout.write(f"  Validations: {len(mouvements_list)} | Doublons: {len(doublons_a_supprimer)} | Legitimes: {len(mouvements_garder)}")
            self.stdout.write(f"  Stock actuel: {article.quantite_stock}")
            self.stdout.write(f"  Quantite en trop: {quantite_doublon}")
            self.stdout.write(f"  Stock corrige: {article.quantite_stock - quantite_doublon}")
            
            for mv in mouvements_list:
                if mv in doublons_a_supprimer:
                    status = "DOUBLON"
                    style = self.style.ERROR
                else:
                    status = "LEGITIME"
                    style = self.style.SUCCESS
                self.stdout.write(style(f"    [{status}] {mv.date_mouvement.strftime('%m-%d %H:%M:%S')} +{mv.quantite} | {mv.reference_document}"))

            if not dry_run:
                with transaction.atomic():
                    # Reduire le stock
                    nouveau_stock = article.quantite_stock - quantite_doublon
                    if nouveau_stock < 0:
                        nouveau_stock = 0
                    
                    article.quantite_stock = nouveau_stock
                    article.save(update_fields=['quantite_stock'])
                    
                    # Supprimer les mouvements en double
                    for mv in doublons_a_supprimer:
                        mv.delete()
                    
                    # Creer un mouvement de correction
                    MouvementStock.objects.create(
                        article=article,
                        type_mouvement='CORRECTION',
                        quantite=-quantite_doublon,
                        reference_document=f'FIX-DOUBLON-V2-{timezone.now().strftime("%Y%m%d")}',
                        commentaire=f'Correction auto V2: {len(doublons_a_supprimer)} doublon(s) (meme qte, <{interval_minutes}min)'
                    )
                    
                    total_corrige += 1
                    total_stock_reduit += quantite_doublon
                    total_doublons += len(doublons_a_supprimer)
                    self.stdout.write(self.style.SUCCESS(f"  -> CORRIGE"))

        self.stdout.write(f"\n{'='*60}")
        if dry_run:
            self.stdout.write(self.style.WARNING(f"SIMULATION terminee"))
            self.stdout.write("Criteres de doublon: meme quantite + meme reference + intervalle < 5min")
            self.stdout.write("Executez avec --fix pour appliquer les corrections")
        else:
            self.stdout.write(self.style.SUCCESS(f"TERMINE: {total_corrige} articles corriges"))
            self.stdout.write(self.style.SUCCESS(f"Doublons supprimes: {total_doublons}"))
            self.stdout.write(self.style.SUCCESS(f"Stock total reduit de: {total_stock_reduit} unites"))
