"""
Initialise les unités de conditionnement standard des articles de Boucherie.

Pour chaque article actif d'une boutique BOUCHERIE qui n'a AUCUN
conditionnement, crée :

    kg   = 1 × unité de base
    demi = 5
    rame = 10
    carton = 30

Si l'unité de base est 'g' (ou 'ml'), les coefficients sont multipliés par
1000 (kg = 1000 g, demi = 5000 g, ...). Les prix sont laissés vides : prix
auto = prix de base × coefficient, ajustables ensuite dans le modal « Prix »
du back office.

Articles déjà pourvus d'unités : ignorés (jamais écrasés).

Usage:
    python manage.py initialiser_unites_boucherie                 # simulation
    python manage.py initialiser_unites_boucherie --apply         # écriture
    python manage.py initialiser_unites_boucherie --boutique-id 106 --apply
"""

from django.core.management.base import BaseCommand

from inventory.models import Article, Boutique, Conditionnement

# unité de base -> (libellé de l'unité entière, coefficient dans l'unité de base)
BASES_GEREE = {
    'kg': ('kg', 1),
    'g': ('kg', 1000),
    'gr': ('kg', 1000),
    'gramme': ('kg', 1000),
    'grammes': ('kg', 1000),
    'l': ('L', 1),
    'litre': ('L', 1),
    'litres': ('L', 1),
    'ml': ('L', 1000),
}

# (libellé, multiple de l'unité entière) — hiérarchie 1 / 5 / 10 / 30
MULTIPLES = [('demi', 5), ('rame', 10), ('carton', 30)]


def construire_unites(unite_base):
    """Construit la liste standard [kg, demi, rame, carton] pour une base.

    Retourne (unites, erreur) : unites = liste de dicts compatible avec
    _valider_hierarchie_conditionnements, erreur = message ou None.
    """
    from inventory.views_commercant import _valider_hierarchie_conditionnements

    base = (unite_base or '').strip().lower()
    if not base:
        return [], "unité de base vide"
    if base not in BASES_GEREE:
        return [], f"unité de base non gérée : {unite_base}"
    libelle_entier, facteur = BASES_GEREE[base]

    unites = [{
        'libelle': libelle_entier,
        'coefficient': 1 * facteur,
        'prix_vente': None,
        'actif': True,
    }]
    for libelle, multiple in MULTIPLES:
        unites.append({
            'libelle': libelle,
            'coefficient': multiple * facteur,
            'prix_vente': None,
            'actif': True,
        })

    erreur = _valider_hierarchie_conditionnements(unites)
    if erreur:
        return [], erreur
    return unites, None


class Command(BaseCommand):
    help = (
        "Crée les unités standard (kg, demi, rame, carton) sur les articles "
        "de Boucherie qui n'en ont pas. Simulation par défaut, --apply pour écrire."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help="Écrit réellement en base (sans ce drapeau : simulation)",
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Force la simulation (ignoré si --apply est aussi fourni)",
        )
        parser.add_argument(
            '--boutique-id',
            type=int,
            help="Limiter à une boutique (optionnel : toutes les BOUCHERIE)",
        )

    def handle(self, *args, **options):
        appliquer = options['apply'] and not options['dry_run']
        boutique_id = options.get('boutique_id')

        if appliquer:
            self.stdout.write(self.style.SUCCESS('MODE ECRITURE : les unités vont être créées'))
        else:
            self.stdout.write(self.style.WARNING(
                'SIMULATION - aucune modification. Relancer avec --apply pour écrire.'
            ))

        boutiques = Boutique.objects.filter(type_commerce='BOUCHERIE', est_active=True)
        if boutique_id:
            try:
                cible = boutiques.get(id=boutique_id)
            except Boutique.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f'Boutique {boutique_id} introuvable (ou pas de type BOUCHERIE)'
                ))
                return
            boutiques = [cible]
            self.stdout.write(f'Boutique : {cible.nom} (ID {cible.id})')

        stats = {'cree': 0, 'deja': 0, 'ignore': 0}
        motifs = {}

        for boutique in boutiques:
            articles = boutique.articles.filter(est_actif=True).order_by('nom')
            for article in articles:
                if article.conditionnements.exists():
                    stats['deja'] += 1
                    continue

                unites, erreur = construire_unites(article.unite_base)
                if erreur:
                    stats['ignore'] += 1
                    motifs.setdefault(erreur, []).append(f'{article.nom} (ID {article.id})')
                    continue

                self.stdout.write(
                    f'\n{article.nom} (ID {article.id}) - {boutique.nom}'
                    f' - base: {article.unite_base} - prix base: {article.prix_vente}'
                )
                for unite in unites:
                    auto = (article.prix_vente or 0) * unite['coefficient']
                    self.stdout.write(
                        f"   {unite['libelle']:<8} x{unite['coefficient']:<6} "
                        f"prix auto = {auto}"
                    )

                if appliquer:
                    for ordre, unite in enumerate(unites):
                        Conditionnement.objects.create(
                            article=article,
                            libelle=unite['libelle'],
                            coefficient=unite['coefficient'],
                            prix_vente=None,
                            ordre=ordre,
                        )
                    # bump last_updated -> sync incrémentale des terminaux MAUI
                    article.save()
                stats['cree'] += 1

        self.stdout.write('\n--- Resume ---')
        if appliquer:
            self.stdout.write(self.style.SUCCESS(
                f"{stats['cree']} article(s) : unités créées"
            ))
        else:
            self.stdout.write(
                f"{stats['cree']} article(s) seraient créés (simulation)"
            )
        self.stdout.write(f"{stats['deja']} article(s) déjà pourvus d'unités (ignorés)")
        self.stdout.write(f"{stats['ignore']} article(s) ignorés")
        for motif, articles in motifs.items():
            self.stdout.write(f"   - {motif} : {len(articles)} article(s)")
            for nom in articles[:5]:
                self.stdout.write(f"       {nom}")
            if len(articles) > 5:
                self.stdout.write(f"       ... et {len(articles) - 5} autres")

        if not appliquer and stats['cree']:
            self.stdout.write(self.style.WARNING(
                '\nPour appliquer : python manage.py initialiser_unites_boucherie --apply'
            ))
