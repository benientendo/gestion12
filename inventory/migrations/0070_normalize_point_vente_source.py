from django.db import migrations, models


def normaliser_point_vente_source(apps, schema_editor):
    Article = apps.get_model('inventory', 'Article')

    def norm(pv):
        pv = (pv or '').strip()
        if not pv:
            return ''
        parts = pv.upper().replace('KIYAMBU', ' ').split()
        if not parts:
            return ''
        if len(parts) == 2 and parts[0].isdigit() and parts[1] == 'MPOLO':
            return f'{parts[1]} {parts[0]}'
        return ' '.join(parts)

    for art in Article.objects.exclude(point_vente_source='').iterator():
        sources = []
        for s in art.point_vente_source.split(','):
            ns = norm(s)
            if ns and ns not in sources:
                sources.append(ns)
        new_val = ', '.join(sources)
        if new_val != art.point_vente_source:
            Article.objects.filter(pk=art.pk).update(point_vente_source=new_val)


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0069_article_point_vente_source'),
    ]

    operations = [
        migrations.RunPython(normaliser_point_vente_source, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='article',
            name='point_vente_source',
            field=models.CharField(
                blank=True,
                default='',
                help_text="Point de vente d'origine (ex: MPOLO 04, DUBAI 04 MPOLO)",
                max_length=200,
            ),
        ),
    ]
