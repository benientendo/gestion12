"""
Importe familles, fournisseurs, noms d'articles et pièces/carton
depuis un dump MySQL legacy (ex: client_034846.sql) vers Django.

Usage:
    python manage.py import_client_sql --sql "C:/Users/PC/Downloads/client_034846.sql" --boutique <ID>
"""
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import Article, Boutique, Categorie, Fournisseur


class Command(BaseCommand):
    help = "Importe familles, fournisseurs, articles et pieces/carton depuis un dump SQL legacy"

    def add_arguments(self, parser):
        parser.add_argument('--sql', required=True, help='Chemin vers le fichier .sql')
        parser.add_argument('--boutique', type=int, required=True, help='ID de la boutique/dépôt cible')
        parser.add_argument('--commercant', type=int, default=None, help='ID commerçant (déduit de la boutique si absent)')

    def handle(self, *args, **options):
        sql_path = Path(options['sql'])
        if not sql_path.exists():
            raise CommandError(f"Fichier introuvable: {sql_path}")

        try:
            boutique = Boutique.objects.get(id=options['boutique'])
        except Boutique.DoesNotExist:
            raise CommandError(f"Boutique {options['boutique']} introuvable")

        commercant = boutique.commercant
        self.stdout.write(f"Import vers boutique: {boutique.nom} (commercant={commercant})")

        # Lire le dump (latin-1 pour accents MySQL)
        raw = sql_path.read_bytes()
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            text = raw.decode('latin-1', errors='replace')

        # Extraire les blocs INSERT INTO `table` VALUES (...);
        inserts = self._extract_inserts(text)

        familles = self._parse_famille(inserts.get('famille', []))
        fournisseurs = self._parse_fournisseurs(
            inserts.get('achat', []) + inserts.get('fournisseur', [])
        )
        produits = self._parse_produit(inserts.get('produit', []))
        # Dernier piece/pau par produit depuis achat
        achat_meta = self._parse_achat_meta(inserts.get('achat', []))

        self.stdout.write(f"  familles: {len(familles)}")
        self.stdout.write(f"  fournisseurs: {len(fournisseurs)}")
        self.stdout.write(f"  produits: {len(produits)}")
        self.stdout.write(f"  meta achat: {len(achat_meta)}")

        nb_cat = nb_four = nb_art = nb_upd = 0

        with transaction.atomic():
            # 1. Catégories (familles)
            cat_map = {}
            for nom in familles:
                nom = nom.strip()
                if not nom or len(nom) > 100:
                    continue
                cat, created = Categorie.objects.get_or_create(
                    nom=nom,
                    boutique=boutique,
                    defaults={'description': 'Importée depuis dump legacy'},
                )
                cat_map[nom] = cat
                if created:
                    nb_cat += 1

            # 2. Fournisseurs
            for nom in fournisseurs:
                nom = nom.strip()
                if not nom or len(nom) > 200:
                    continue
                _, created = Fournisseur.objects.get_or_create(
                    nom=nom,
                    commercant=commercant,
                    defaults={'est_actif': True},
                )
                if created:
                    nb_four += 1

            # 3. Articles (produits)
            for designation, famille_nom, prix, piece in produits:
                designation = designation.strip()
                if not designation or len(designation) > 100:
                    continue

                prix = float(prix) if prix else 0
                piece = int(piece) if piece else 1

                # Préférer meta achat (dernier achat) pour piece/pau
                meta = achat_meta.get(designation)
                if meta:
                    if meta.get('piece') and meta['piece'] > 0:
                        piece = int(meta['piece'])
                    # pau non stocké comme prix_achat principal ici (devise variable)

                cat = cat_map.get((famille_nom or '').strip())
                code = designation[:50].upper().replace(' ', '_')

                art, created = Article.objects.get_or_create(
                    code=code,
                    boutique=boutique,
                    defaults={
                        'nom': designation,
                        'devise': 'CDF',
                        'prix_vente': round(prix, 2),
                        'prix_achat': 0,
                        'categorie': cat,
                        'quantite_stock': 0,
                        'est_actif': True,
                        'pieces_par_carton': max(1, piece),
                    },
                )
                if created:
                    nb_art += 1
                else:
                    # Mettre à jour pieces_par_carton et catégorie si vides
                    changed_fields = []
                    if art.pieces_par_carton in (0, 1) and piece > 1:
                        art.pieces_par_carton = piece
                        changed_fields.append('pieces_par_carton')
                    if not art.categorie_id and cat:
                        art.categorie = cat
                        changed_fields.append('categorie')
                    if art.prix_vente == 0 and prix > 0:
                        art.prix_vente = round(prix, 2)
                        changed_fields.append('prix_vente')
                    if changed_fields:
                        art.save(update_fields=changed_fields)
                        nb_upd += 1

        self.stdout.write(self.style.SUCCESS(
            f"Import terminé: +{nb_cat} catégories, +{nb_four} fournisseurs, "
            f"+{nb_art} articles, {nb_upd} mis à jour"
        ))

    # ---------- parsing ----------

    def _extract_inserts(self, text: str) -> dict:
        """Retourne {table: [raw_values_string, ...]}"""
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
        """Split MySQL VALUES blob en tuples, en gérant les quotes/escapes."""
        tuples = []
        i = 0
        n = len(values_blob)
        while i < n:
            if values_blob[i] != '(':
                i += 1
                continue
            i += 1  # skip (
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
        """designation, famille, prix, piece"""
        out = []
        for blob in inserts:
            for t in self._split_tuples(blob):
                if len(t) >= 4:
                    out.append((t[0], t[1], t[2], t[3]))
                elif len(t) >= 2:
                    out.append((t[0], t[1], 0, 1))
        return out

    def _parse_fournisseurs(self, inserts) -> list:
        """Depuis achat: champ 2 = fournisseur; depuis fournisseur: champ 0 = nom."""
        noms = set()
        # On re-scan les blobs achat pour champ fournisseur (index 2)
        # et table fournisseur champ 0
        # Mais _extract_inserts ne nous donne pas le type ici — on reçoit déjà les blobs mélangés.
        # On distingue: achat tuples ont un int en premier champ + date; fournisseur commence par string.
        for blob in inserts:
            for t in self._split_tuples(blob):
                if not t:
                    continue
                # achat: (id, date, fournisseur, ...)
                if len(t) >= 3 and re.match(r'^\d+$', t[0]) and re.match(r'^\d{4}-\d{2}-\d{2}$', t[1]):
                    noms.add(t[2].strip())
                # fournisseur table: (nom, tel, produit, prix, dte)
                elif len(t) >= 3 and t[0] and not t[0].isdigit():
                    # éviter de confondre avec produit — fournisseur a 5 champs, 2e non numérique souvent
                    if len(t) == 5:
                        noms.add(t[0].strip())
        return [n for n in noms if n]

    def _parse_achat_meta(self, inserts) -> dict:
        """produit -> {piece, pau, fournisseur} du dernier achat (par date)."""
        meta = {}
        for blob in inserts:
            for t in self._split_tuples(blob):
                # achat: id, dte, fournisseur, facture, famille, produit, piece, qt, pau, pvu, type
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
