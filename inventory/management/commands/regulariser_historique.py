from collections import defaultdict

from django.core.management.base import BaseCommand

from inventory.models import Article, MouvementStock

LOT_ARTICLES = 200


class Command(BaseCommand):
    help = (
        "Regularise l'historique des mouvements de stock : "
        "mouvements d'ouverture (articles avec stock mais sans mouvement), "
        "rechainage des stock_avant/stock_apres et alignement du solde final "
        "sur le stock reel. Dry-run par defaut, --apply pour modifier."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help="Effectue les modifications (sinon dry-run)")
        parser.add_argument(
            '--boutique', type=int, default=None,
            help="Limiter a une boutique ou un depot (id)")
        parser.add_argument(
            '--no-rechainage', action='store_true',
            help="Ne pas re-ecrire les stock_avant/stock_apres existants")
        parser.add_argument(
            '--limit', type=int, default=None,
            help="Limiter le nombre d'articles analyses")
        parser.add_argument(
            '--sample', type=int, default=8,
            help="Nombre d'exemples affiches par categorie")

    @staticmethod
    def _analyser(liste):
        """Analyse les mouvements d'un article (ordre chronologique).

        Retourne (solde_recalcule, solde_enregistre, nb_bris, corrections).
        corrections est une liste de (id_mouvement, stock_avant, stock_apres)
        recalcules en chaine. Le delta de chaque mouvement est pris sur
        stock_apres - stock_avant (valeur deja appliquee au stock), pas sur le
        champ quantite dont le sens peut varier selon les flux.
        """
        corrections = []
        bris = 0
        roule = None
        dernier_apres = None
        for mid, _aid, avant, apres, quantite in liste:
            if avant is not None and apres is not None:
                delta = apres - avant
            else:
                delta = quantite or 0
            if roule is None:
                roule = avant if avant is not None else 0
            elif avant is not None and avant != roule:
                bris += 1
            nouveau_avant = roule
            nouveau_apres = roule + delta
            if avant != nouveau_avant or apres != nouveau_apres:
                corrections.append((mid, nouveau_avant, nouveau_apres))
            roule = nouveau_apres
            if apres is not None:
                dernier_apres = apres
        solde_enregistre = dernier_apres if dernier_apres is not None else roule
        return roule, solde_enregistre, bris, corrections

    def _parcourir(self, articles, rechainage=True):
        """Analyse par lots (memoire constante, meme sur un gros historique)."""
        ouvertures = []
        rechaines = []
        alignements = []
        corrections = []
        bris_total = 0

        for debut in range(0, len(articles), LOT_ARTICLES):
            lot = articles[debut:debut + LOT_ARTICLES]
            ids = [a['id'] for a in lot]
            mvts = defaultdict(list)
            lignes = (MouvementStock.objects
                      .filter(article_id__in=ids)
                      .order_by('article_id', 'date_mouvement', 'id')
                      .values_list('id', 'article_id',
                                   'stock_avant', 'stock_apres', 'quantite'))
            for ligne in lignes:
                mvts[ligne[1]].append(ligne)

            for art in lot:
                liste = mvts.get(art['id'], [])
                reel = art['quantite_stock']
                if not liste:
                    if reel > 0:
                        ouvertures.append(art)
                    continue
                solde, solde_enregistre, bris, a_corriger = \
                    self._analyser(liste)
                bris_total += bris
                if a_corriger:
                    corrections.extend(a_corriger)
                    rechaines.append((art, len(a_corriger), bris))
                solde_effectif = solde if rechainage else solde_enregistre
                if solde_effectif != reel:
                    alignements.append((art, solde, solde_enregistre, reel))

        return ouvertures, rechaines, alignements, corrections, bris_total

    @staticmethod
    def _appliquer(ouvertures, alignements, corrections, rechainage=True):
        lignes_modifiees = 0
        ouvertures_creees = 0
        alignements_crees = 0

        if rechainage and corrections:
            cibles = [MouvementStock(id=mid, stock_avant=av, stock_apres=ap)
                      for mid, av, ap in corrections]
            for debut in range(0, len(cibles), 500):
                lot = cibles[debut:debut + 500]
                MouvementStock.objects.bulk_update(
                    lot, ['stock_avant', 'stock_apres'])
                lignes_modifiees += len(lot)

        for art in ouvertures:
            MouvementStock.objects.create(
                article_id=art['id'],
                type_mouvement='ENTREE',
                quantite=art['quantite_stock'],
                stock_avant=0,
                stock_apres=art['quantite_stock'],
                commentaire='Solde initial a la creation',
                reference_document=f"INIT-{art['id']}",
            )
            ouvertures_creees += 1

        for art, solde, solde_enregistre, reel in alignements:
            # Si la chaine est rechainee, le dernier stock_apres devient le
            # solde recalcule, sinon on part du solde enregistre.
            depart = solde if rechainage else solde_enregistre
            ecart = reel - depart
            if ecart == 0:
                continue
            MouvementStock.objects.create(
                article_id=art['id'],
                type_mouvement='ENTREE' if ecart > 0 else 'SORTIE',
                quantite=abs(ecart),
                stock_avant=depart,
                stock_apres=reel,
                commentaire=f"Regularisation historique: solde {depart}, "
                            f"stock reel {reel}",
                reference_document=f"REGL-{art['id']}",
            )
            alignements_crees += 1

        return lignes_modifiees, ouvertures_creees, alignements_crees

    def handle(self, *args, **options):
        sample = options['sample']
        qs = Article.objects.all().order_by('id')
        if options['boutique']:
            qs = qs.filter(boutique_id=options['boutique'])
        articles = list(qs.values('id', 'nom', 'quantite_stock', 'boutique_id'))
        if options['limit']:
            articles = articles[:options['limit']]

        ouvertures, rechaines, alignements, corrections, bris = \
            self._parcourir(articles, rechainage=not options['no_rechainage'])

        self.stdout.write(f"Articles analyses : {len(articles)}"
                          + (f" (boutique {options['boutique']})"
                             if options['boutique'] else ""))
        self.stdout.write(f"Ouvertures a creer (stock>0, aucun mouvement) : "
                          f"{len(ouvertures)}")
        self.stdout.write(f"A rechainer (stock_avant/stock_apres incoherents) : "
                          f"{len(rechaines)} article(s), "
                          f"{len(corrections)} ligne(s), {bris} bris de chaine")
        self.stdout.write(f"Alignements du solde final (solde != stock reel) : "
                          f"{len(alignements)}")

        for art in ouvertures[:sample]:
            self.stdout.write(
                f"  OUVERTURE [{art['boutique_id']}] {art['nom'][:40]} "
                f"stock={art['quantite_stock']}")
        for art, nb, br in rechaines[:sample]:
            self.stdout.write(
                f"  RECHAINAGE [{art['boutique_id']}] {art['nom'][:40]} "
                f"lignes={nb} bris={br}")
        for art, solde, solde_enregistre, reel in alignements[:sample]:
            self.stdout.write(
                f"  ALIGNEMENT [{art['boutique_id']}] {art['nom'][:40]} "
                f"solde={solde} (enregistre={solde_enregistre}) "
                f"stock_reel={reel}")

        if not options['apply']:
            self.stdout.write(self.style.WARNING(
                "DRY-RUN : aucune modification effectuee "
                "(relancer avec --apply)."))
            return

        lignes, ouv, ali = self._appliquer(
            ouvertures, alignements, corrections,
            rechainage=not options['no_rechainage'])
        self.stdout.write(self.style.SUCCESS(
            f"Termine : {ouv} mouvement(s) d'ouverture, "
            f"{lignes} ligne(s) rechainee(s), {ali} alignement(s)."))
