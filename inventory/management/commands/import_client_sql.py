"""
Exporte l'autocomplétion (articles, familles, fournisseurs, pièces/carton)
depuis un dump MySQL legacy vers un JSON — sans remplir le dépôt.

Usage:
    python manage.py import_client_sql --sql "C:/Users/PC/Downloads/client_034846.sql"
    python manage.py import_client_sql --clear-depot 13
"""
import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import Article, Boutique


class Command(BaseCommand):
    help = "Exporte autocomplete legacy (JSON) et/ou vide un dépôt — n'écrit pas d'articles en stock"

    def add_arguments(self, parser):
        parser.add_argument('--sql', help='Chemin vers le fichier .sql (export JSON)')
        parser.add_argument(
            '--out',
            default='inventory/data/autocomplete_client.json',
            help='Chemin de sortie JSON (défaut: inventory/data/autocomplete_client.json)',
        )
        parser.add_argument(
            '--clear-depot',
            type=int,
            default=None,
            metavar='BOUTIQUE_ID',
            help="Supprimer TOUS les articles du dépôt/boutique indiqué",
        )

    def handle(self, *args, **options):
        if options['clear_depot'] is not None:
            self._clear_depot(options['clear_depot'])
        if options['sql']:
            self._export_json(options['sql'], options['out'])
        if not options['sql'] and options['clear_depot'] is None:
            self.stdout.write(self.style.WARNING("Rien à faire: passez --sql et/ou --clear-depot <id>"))

    # ---------- clear ----------

    def _clear_depot(self, boutique_id: int):
        try:
            boutique = Boutique.objects.get(id=boutique_id)
        except Boutique.DoesNotExist:
            raise CommandError(f"Boutique {boutique_id} introuvable")

        qs = Article.objects.filter(boutique=boutique)
        n = qs.count()
        with transaction.atomic():
            qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f"Dépôt vidé: {n} article(s) supprimé(s) de « {boutique.nom} »"
        ))

    # ---------- export JSON ----------

    def _export_json(self, sql_path_str: str, out_rel: str):
        sql_path = Path(sql_path_str)
        if not sql_path.exists():
            raise CommandError(f"Fichier introuvable: {sql_path}")

        raw = sql_path.read_bytes()
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            text = raw.decode('latin-1', errors='replace')

        inserts = self._extract_inserts(text)

        familles = self._parse_famille(inserts.get('famille', []))
        fournisseurs = self._parse_fournisseurs(
            inserts.get('achat', []) + inserts.get('fournisseur', [])
        )
        produits = self._parse_produit(inserts.get('produit', []))
        achat_meta = self._parse_achat_meta(inserts.get('achat', []))

        # Filtre familles invalides
        familles_valides = []
        for nom in familles:
            nom = nom.strip()
            if not nom or len(nom) < 3 or len(nom) > 100:
                continue
            if re.match(r'^[\d\-\*\%\#\$\@\!\?\.]+$', nom):
                continue
            familles_valides.append(nom)

        articles = []
        seen = set()
        for designation, famille_nom, prix, piece in produits:
            designation = designation.strip()
            if not designation or len(designation) > 100 or designation in seen:
                continue
            seen.add(designation)

            try:
                prix_f = float(prix) if prix else 0
            except (TypeError, ValueError):
                prix_f = 0
            try:
                piece_i = int(float(piece)) if piece else 1
            except (TypeError, ValueError):
                piece_i = 1

            meta = achat_meta.get(designation)
            if meta and meta.get('piece') and meta['piece'] > 0:
                piece_i = int(meta['piece'])

            articles.append({
                'nom': designation,
                'famille': (famille_nom or '').strip(),
                'prix_vente': round(prix_f, 2),
                'pieces_par_carton': max(1, piece_i),
            })

        data = {
            'source': sql_path.name,
            'familles': familles_valides,
            'fournisseurs': sorted({f.strip() for f in fournisseurs if f and f.strip()}),
            'articles': articles,
        }

        out_path = Path(settings.BASE_DIR) / out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=0),
            encoding='utf-8',
        )
        self.stdout.write(self.style.SUCCESS(
            f"JSON autocomplete: {len(articles)} articles, "
            f"{len(data['familles'])} familles, {len(data['fournisseurs'])} fournisseurs -> {out_path}"
        ))

    # ---------- parsing ----------

    def _extract_inserts(self, text: str) -> dict:
        pattern = re.compile(
            r"INSERT INTO `(\w+)` VALUES\s+(\(.*?\));",
            re.DOTALL | re.IGNORECASE,
        )
        result = {}
        for m in pattern.finditer(text):
            table = m.group(1).lower()
            result.setdefault(table, []).append(m.group(2))
        return result

    @staticmethod
    def _split_tuples(values_blob: str):
        tuples = []
        i = 0
        n = len(values_blob)
        while i < n:
            if values_blob[i] != '(':
                i += 1
                continue
            i += 1
            fields = []
            buf = []
            in_str = False
            while i < n:
                ch = values_blob[i]
                if in_str:
                    if ch == '\\' and i + 1 < n:
                        buf.append(values_blob[i + 1])
                        i += 2
                        continue
                    if ch == "'":
                        in_str = False
                        i += 1
                        continue
                    buf.append(ch)
                    i += 1
                    continue
                if ch == "'":
                    in_str = True
                    i += 1
                    continue
                if ch == ',':
                    fields.append(''.join(buf).strip())
                    buf = []
                    i += 1
                    continue
                if ch == ')':
                    fields.append(''.join(buf).strip())
                    i += 1
                    break
                buf.append(ch)
                i += 1
            if fields:
                tuples.append(fields)
        return tuples

    def _parse_famille(self, inserts) -> list:
        noms = []
        for blob in inserts:
            for t in self._split_tuples(blob):
                if t:
                    noms.append(t[0])
        return noms

    def _parse_produit(self, inserts):
        out = []
        for blob in inserts:
            for t in self._split_tuples(blob):
                if len(t) >= 4:
                    out.append((t[0], t[1], t[2], t[3]))
                elif len(t) >= 2:
                    out.append((t[0], t[1], 0, 1))
        return out

    def _parse_fournisseurs(self, inserts) -> list:
        noms = set()
        for blob in inserts:
            for t in self._split_tuples(blob):
                if not t:
                    continue
                if len(t) >= 3 and re.match(r'^\d+$', t[0]) and re.match(r'^\d{4}-\d{2}-\d{2}$', t[1]):
                    noms.add(t[2].strip())
                elif len(t) == 5 and t[0] and not t[0].isdigit():
                    noms.add(t[0].strip())
        return [n for n in noms if n]

    def _parse_achat_meta(self, inserts) -> dict:
        meta = {}
        for blob in inserts:
            for t in self._split_tuples(blob):
                if len(t) >= 9 and re.match(r'^\d+$', t[0]) and re.match(r'^\d{4}-\d{2}-\d{2}$', t[1]):
                    produit = t[5].strip()
                    dte = t[1]
                    try:
                        piece = int(float(t[6]))
                    except (ValueError, IndexError):
                        piece = 0
                    try:
                        pau = float(t[8])
                    except (ValueError, IndexError):
                        pau = 0
                    prev = meta.get(produit)
                    if not prev or dte >= prev['dte']:
                        meta[produit] = {'dte': dte, 'piece': piece, 'pau': pau, 'fournisseur': t[2].strip()}
        return meta
