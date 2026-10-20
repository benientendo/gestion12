from django.db import migrations
from django.utils import timezone


CHAMPS_CONDITIONNEMENT = ['coefficient', 'prix_vente', 'prix_achat', 'ordre', 'est_actif']


def _cle_nom(nom):
    return (nom or '').strip().lower()


def reparer_attributs(apps, schema_editor):
    Article = apps.get_model('inventory', 'Article')
    Conditionnement = apps.get_model('inventory', 'Conditionnement')

    sources = (
        Article.objects
        .filter(boutique__type_commerce='BOUCHERIE', est_actif=True)
        .exclude(unite_base='')
        .select_related('boutique')
        .prefetch_related('conditionnements')
    )

    meilleures = {}
    for article in sources:
        nb_conditionnements = len(list(article.conditionnements.all()))
        cle = (article.boutique.commercant_id, _cle_nom(article.nom))
        score = (nb_conditionnements, article.date_mise_a_jour)
        actuel = meilleures.get(cle)
        if actuel is None or score > actuel[0]:
            meilleures[cle] = (score, article)

    candidats = (
        Article.objects
        .filter(boutique__type_commerce='BOUCHERIE', est_actif=True, unite_base='')
        .select_related('boutique')
        .prefetch_related('conditionnements')
    )

    reparés = 0
    for article in candidats:
        conditions = list(article.conditionnements.all())
        source = None
        if not conditions:
            entree = meilleures.get((article.boutique.commercant_id, _cle_nom(article.nom)))
            if entree is not None and entree[1].boutique_id != article.boutique_id:
                source = entree[1]

        if conditions:
            base = next((c for c in conditions if c.coefficient == 1), conditions[0])
            unite = base.libelle
        elif source is not None:
            unite = source.unite_base
        else:
            continue

        if not unite:
            continue

        article.unite_base = unite
        article.version = (article.version or 0) + 1
        article.last_updated = timezone.now()
        article.save(update_fields=['unite_base', 'version', 'last_updated'])
        reparés += 1

        if source is None:
            continue

        for cond_source in source.conditionnements.all():
            cond_dest, cree = Conditionnement.objects.get_or_create(
                article_id=article.id,
                libelle=cond_source.libelle,
                defaults={
                    'coefficient': cond_source.coefficient,
                    'prix_vente': cond_source.prix_vente,
                    'prix_achat': cond_source.prix_achat,
                    'ordre': cond_source.ordre,
                    'est_actif': cond_source.est_actif,
                },
            )
            if cree:
                continue
            modifies = []
            for champ in CHAMPS_CONDITIONNEMENT:
                if getattr(cond_dest, champ) != getattr(cond_source, champ):
                    setattr(cond_dest, champ, getattr(cond_source, champ))
                    modifies.append(champ)
            if modifies:
                cond_dest.save(update_fields=modifies)

    print(f"[reparer_attributs] {reparés} article(s) reparé(s)")


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0081_article_unite_base_lignevente_unite_coefficient_and_more'),
    ]

    operations = [
        migrations.RunPython(reparer_attributs, migrations.RunPython.noop),
    ]
