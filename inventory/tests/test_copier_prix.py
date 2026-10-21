"""
Copie de prix entre points de vente (même commerçant)
=====================================================
Après un import d'articles (créés avec prix = 0), le back-office doit pouvoir
recopier les prix d'un autre point de vente, article par article.

Vérifie :
- appariement par code, puis par nom identique (règle des transferts) ;
- stock / variantes / catégorie jamais touchés ;
- un prix source à 0 n'écrase jamais un prix existant ;
- conversion USD recopiée (une vente en USD facture 0 sans elle) ;
- AUCUNE notification + AUCUN push FCM par article (1147 articles !) ;
- last_updated / version mis à jour → la sync incrémentale voit le changement ;
- source d'un autre commerçant refusée.
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.urls import reverse

from inventory.models import (
    Article, Boutique, DetailModificationPrix, JournalValeurStock,
    NotificationStock,
)
from inventory.tests.test_demande_annulation import DemandeAnnulationBase


class CopierPrixEntreBoutiquesBase(DemandeAnnulationBase):

    def setUp(self):
        super().setUp()

        self.boutique_source = Boutique.objects.create(
            nom='KIYAMBU 04',
            commercant=self.commercant,
            code_boutique='BT-PRIX-SRC',
        )
        # Article source bien tarifé (mêmes code et nom que self.article)
        self.src_savon = Article.objects.create(
            code='ART-ANN-1',
            nom='Savon',
            prix_achat=Decimal('600'),
            prix_vente=Decimal('1500'),
            prix_vente_usd=Decimal('0.75'),
            boutique=self.boutique_source,
            quantite_stock=42,
        )
        # Article source jamais tarifé (prix = 0)
        self.src_huile = Article.objects.create(
            code='ART-ANN-2',
            nom='Huile',
            prix_achat=Decimal('0'),
            prix_vente=Decimal('0'),
            boutique=self.boutique_source,
        )
        # Article présent uniquement dans la source
        self.src_seul = Article.objects.create(
            code='ART-SRC-SEUL',
            nom='Absent de la destination',
            prix_achat=Decimal('100'),
            prix_vente=Decimal('250'),
            boutique=self.boutique_source,
        )

        self.url = reverse(
            'inventory:copier_prix_entre_boutiques', args=[self.boutique.id],
        )
        self.web.force_login(self.user)

    def _copier(self, source=None, follow=False):
        data = {'boutique_source': (source or self.boutique_source).id}
        with patch('inventory.websocket_utils.notify_sync_required') as notify:
            r = self.web.post(self.url, data, follow=follow)
        return r, notify

    def _messages(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]


class CopierPrixTest(CopierPrixEntreBoutiquesBase):

    def test_copie_prix_achat_et_vente_par_code(self):
        version_avant = self.article.version
        maj_avant = self.article.last_updated

        r, notify = self._copier()
        self.assertEqual(r.status_code, 302)

        self.article.refresh_from_db()
        self.assertEqual(self.article.prix_achat, Decimal('600.00'))
        self.assertEqual(self.article.prix_vente, Decimal('1500.00'))
        self.assertEqual(self.article.prix_vente_usd, Decimal('0.75'))

        # Version + last_updated : la sync incrémentale doit voir le changement
        self.assertGreater(self.article.version, version_avant)
        self.assertGreater(self.article.last_updated, maj_avant)

        # Une seule resynchronisation demandée au terminal
        notify.assert_called_once()

    def test_stock_nest_pas_touche(self):
        self._copier()
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)

    def test_prix_source_zero_ne_vide_pas_la_destination(self):
        """Huile : source à 0, destination à 2000 → la destination est conservée."""
        self._copier()
        self.article2.refresh_from_db()

        self.assertEqual(self.article2.prix_vente, Decimal('2000.00'))
        self.assertEqual(self.article2.prix_achat, Decimal('0.00'))

    def test_article_present_uniquement_dans_la_source_est_ignore(self):
        self._copier()
        self.assertFalse(Article.objects.filter(
            boutique=self.boutique, code='ART-SRC-SEUL',
        ).exists())

    def test_appariement_par_nom_quand_le_code_differe(self):
        dest = Article.objects.create(
            code='AUTRE-CODE',
            nom='Savon',
            prix_vente=Decimal('1000'),
            boutique=self.boutique,
        )
        self._copier()

        dest.refresh_from_db()
        self.assertEqual(dest.prix_vente, Decimal('1500.00'))
        self.assertEqual(dest.prix_achat, Decimal('600.00'))

    def test_aucune_notification_ni_push_par_article(self):
        """1147 articles × N terminaux = 1147 notifications/pushs à éviter."""
        # Baseline : la création des articles avec stock a déjà généré des
        # notifications « OUVERTURE- » — on compare donc avant / après.
        notifs_avant = NotificationStock.objects.count()
        self.assertGreater(notifs_avant, 0)

        self._copier()

        self.assertEqual(NotificationStock.objects.count(), notifs_avant)
        # Le « Modif. prix » du journal n'est pas pollué par une copie en masse
        self.assertEqual(DetailModificationPrix.objects.count(), 0)
        self.assertFalse(JournalValeurStock.objects.filter(
            boutique=self.boutique,
            impact_modification_prix__isnull=False,
        ).exclude(impact_modification_prix=Decimal('0')).exists())

    def test_source_dun_autre_commercant_est_refusee(self):
        from django.contrib.auth import get_user_model

        autre_user = get_user_model().objects.create_user(
            username='autre_prix', password='x',
        )
        from inventory.models import Commercant
        autre_commercant = Commercant.objects.create(
            nom_entreprise='AUTRE',
            nom_responsable='AUTRE',
            email='autre_prix@test.cd',
            user=autre_user,
        )
        boutique_etrangere = Boutique.objects.create(
            nom='PAS LA MIENNE',
            commercant=autre_commercant,
            code_boutique='BT-PRIX-ETR',
        )
        avant = self.article.prix_vente

        r, notify = self._copier(source=boutique_etrangere)

        self.assertEqual(r.status_code, 302)
        self.article.refresh_from_db()
        self.assertEqual(self.article.prix_vente, avant)
        notify.assert_not_called()

    def test_get_redirige_vers_la_page_import(self):
        r = self.web.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/articles/importer/', r['Location'])

    def test_affiche_les_compteurs_au_retour(self):
        r, _ = self._copier(follow=True)
        self.assertEqual(r.status_code, 200)

        textes = self._messages(r)
        self.assertTrue(
            any('prix(s) copié(s)' in t for t in textes),
            textes,
        )
        # Le bouton et le formulaire de copie sont bien dans la page
        self.assertContains(r, 'copierPrixForm')
        self.assertContains(r, 'Copier les prix')

    def test_deja_a_jour_ne_renvoie_aucune_modification(self):
        # Première copie : tout change
        _, notify = self._copier()
        notify.assert_called_once()

        # Seconde copie : plus rien à changer → pas de nouvelle resynchronisation
        _, notify2 = self._copier()
        notify2.assert_not_called()
