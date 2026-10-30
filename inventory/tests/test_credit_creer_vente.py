"""
Vente à crédit (API Android) :
- article_id + quantite : lien vers le catalogue, prix toujours = prix_vente × quantité
- quantite stockée sur VenteAcompte, article FK renseigné, réponses JSON complètes
- compatibilité : ancien payload (article_nom + prix_total libre) toujours accepté
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, Client as TestClient
from django.urls import reverse

from inventory.models import (
    Article, Boutique, Client, Commercant, LigneVenteAcompte, MouvementStock,
    VenteAcompte,
)

User = get_user_model()


class CreditCreerVenteCatalogueTestCase(TestCase):
    """Fixtures : boutique, terminal, article du catalogue."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_credit', password='pass1234', email='comm_credit@test.cd'
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='CRED SARL',
            nom_responsable='CRED',
            email='comm_credit@test.cd',
            user=self.user,
        )
        self.boutique = Boutique.objects.create(
            nom='Boutique CRED',
            commercant=self.commercant,
            code_boutique='BT-CRED-001',
        )
        self.terminal = Client.objects.create(
            compte_proprietaire=self.user,
            boutique=self.boutique,
            nom_terminal='T1',
            numero_serie='SERIAL-CRED-001',
            est_actif=True,
        )
        self.article = Article.objects.create(
            code='CRED-1', nom='Televiseur Samsung',
            prix_vente=Decimal('30000'),
            boutique=self.boutique,
            quantite_stock=10,
            est_actif=True, est_valide_client=True,
        )
        self.article2 = Article.objects.create(
            code='CRED-2', nom='Radio Philips',
            prix_vente=Decimal('10000'),
            boutique=self.boutique,
            quantite_stock=5,
            est_actif=True, est_valide_client=True,
        )

        self.api = TestClient(SERVER_NAME='127.0.0.1')
        self.entete = {'HTTP_X_DEVICE_SERIAL': 'SERIAL-CRED-001'}
        self.url_creer = reverse('inventory:api_credit_creer_vente', args=[self.boutique.id])

    def _payload(self, **kwargs):
        base = {
            'client_id':    None,
            'nom':          'KABILA',
            'prenom':       'Jean',
            'telephone':    '0810000000',
            'adresse':      'Kinshasa',
            'article_nom':  'Televiseur Samsung',
            'prix_total':   float(Decimal('30000') * 2),
            'acompte_initial': 0,
            'commentaire':  '',
        }
        base.update(kwargs)
        return base

    # ── Création avec article du catalogue ───────────────────────────────

    def test_creation_avec_article_catalogue(self):
        """article_id + quantite : prix catalogue appliqué, FK article renseigné."""
        resp = self.api.post(
            self.url_creer,
            data=self._payload(article_id=self.article.id, quantite=2),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        vente = VenteAcompte.objects.get()
        self.assertEqual(vente.article, self.article)
        self.assertEqual(vente.quantite, 2)
        self.assertEqual(vente.article_nom, 'Televiseur Samsung')
        self.assertEqual(vente.prix_total, Decimal('60000.00'))
        # Plus de seuil : forcé au prix total (retrait à paiement complet)
        self.assertEqual(vente.seuil_retrait, Decimal('60000.00'))
        self.assertEqual(vente.statut, 'EN_COURS')
        self.assertEqual(resp.json()['quantite'], 2)

    def test_prix_total_faux_rejete(self):
        """Un prix total qui ne correspond pas au catalogue est refusé."""
        resp = self.api.post(
            self.url_creer,
            data=self._payload(
                article_id=self.article.id, quantite=2,
                prix_total=10000,
            ),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('prix catalogue', resp.json()['error'].lower())
        self.assertFalse(VenteAcompte.objects.exists())

    def test_ancien_seuil_ignore_force_au_prix_total(self):
        """Payload legacy avec seuil_retrait : le champ est ignoré,
        le seuil est forcé au prix total (retrait = paiement complet)."""
        resp = self.api.post(
            self.url_creer,
            data=self._payload(article_id=self.article.id, quantite=2,
                               seuil_retrait=5000),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        vente = VenteAcompte.objects.get()
        self.assertEqual(vente.seuil_retrait, vente.prix_total)
        self.assertFalse(vente.peut_recuperer)  # pas encore payé

    def test_quantite_invalide_rejete(self):
        resp = self.api.post(
            self.url_creer,
            data=self._payload(article_id=self.article.id, quantite=0),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(VenteAcompte.objects.exists())

    # ── Multi-articles (nouveau format `articles`) ───────────────────────

    def _articles_payload(self, *lignes):
        return [
            {
                'article_id': article.id,
                'article_nom': article.nom,
                'quantite': quantite,
                'prix_total': float(article.prix_vente * quantite),
            }
            for article, quantite in lignes
        ]

    def test_creation_multi_articles(self):
        payload = self._payload(articles=self._articles_payload(
            (self.article, 2), (self.article2, 1),
        ))
        resp = self.api.post(
            self.url_creer, data=payload,
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 201, resp.content)

        vente = VenteAcompte.objects.get()
        self.assertIsNone(vente.article)
        self.assertEqual(vente.quantite, 3)
        self.assertEqual(vente.prix_total, Decimal('70000.00'))
        self.assertEqual(vente.article_nom, 'Televiseur Samsung, Radio Philips')

        lignes = list(vente.lignes.order_by('id'))
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[0].article, self.article)
        self.assertEqual(lignes[0].quantite, 2)
        self.assertEqual(lignes[0].prix_unitaire, Decimal('30000.00'))
        self.assertEqual(lignes[1].article, self.article2)
        self.assertEqual(lignes[1].quantite, 1)
        self.assertEqual(lignes[1].prix_unitaire, Decimal('10000.00'))

        self.article.refresh_from_db()
        self.article2.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 8)
        self.assertEqual(self.article2.quantite_stock, 4)

        data = resp.json()
        self.assertEqual(len(data['lignes']), 2)
        self.assertEqual(data['lignes'][0]['article_id'], self.article.id)
        self.assertEqual(data['lignes'][0]['stock_avant'], 10)
        self.assertEqual(data['lignes'][0]['stock_restant'], 8)
        self.assertEqual(data['lignes'][1]['article_id'], self.article2.id)
        self.assertEqual(data['lignes'][1]['stock_avant'], 5)
        self.assertEqual(data['lignes'][1]['stock_restant'], 4)

    def test_multi_articles_doublon_fusionne(self):
        payload = self._payload(articles=self._articles_payload(
            (self.article, 1), (self.article, 2),
        ))
        resp = self.api.post(
            self.url_creer, data=payload,
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 201, resp.content)

        vente = VenteAcompte.objects.get()
        self.assertEqual(vente.lignes.count(), 1)
        ligne = vente.lignes.get()
        self.assertEqual(ligne.quantite, 3)
        self.assertEqual(ligne.prix_total, Decimal('90000.00'))
        self.assertEqual(vente.prix_total, Decimal('90000.00'))
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 7)

    def test_multi_articles_stock_insuffisant_rejete(self):
        payload = self._payload(articles=self._articles_payload(
            (self.article, 2), (self.article2, 6),
        ))
        resp = self.api.post(
            self.url_creer, data=payload,
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('stock insuffisant', resp.json()['error'].lower())
        self.assertFalse(VenteAcompte.objects.exists())

        self.article.refresh_from_db()
        self.article2.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)
        self.assertEqual(self.article2.quantite_stock, 5)

    def test_multi_articles_prix_catalogue_rejete(self):
        articles = self._articles_payload((self.article, 2), (self.article2, 1))
        articles[1]['prix_total'] = 1
        resp = self.api.post(
            self.url_creer, data=self._payload(articles=articles),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('prix catalogue', resp.json()['error'].lower())
        self.assertFalse(VenteAcompte.objects.exists())

    def test_liste_et_detail_incluent_lignes(self):
        payload = self._payload(articles=self._articles_payload(
            (self.article, 2), (self.article2, 1),
        ))
        self.api.post(
            self.url_creer, data=payload,
            content_type='application/json', **self.entete,
        )
        vente = VenteAcompte.objects.get()

        liste = self.api.get(
            f'/api/credit/boutique/{self.boutique.id}/ventes/', **self.entete)
        self.assertEqual(liste.status_code, 200)
        self.assertEqual(len(liste.json()['ventes'][0]['lignes']), 2)

        detail = self.api.get(f'/api/credit/vente/{vente.id}/', **self.entete)
        self.assertEqual(detail.status_code, 200)
        lignes = detail.json()['lignes']
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[0]['article_nom'], 'Televiseur Samsung')
        self.assertEqual(lignes[0]['quantite'], 2)
        self.assertEqual(lignes[1]['article_nom'], 'Radio Philips')

    def test_annulation_multi_articles_rend_le_stock(self):
        payload = self._payload(articles=self._articles_payload(
            (self.article, 2), (self.article2, 3),
        ))
        resp = self.api.post(
            self.url_creer, data=payload,
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 201, resp.content)

        vente = VenteAcompte.objects.get()
        self.article.refresh_from_db()
        self.article2.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 8)
        self.assertEqual(self.article2.quantite_stock, 2)

        self.client.force_login(self.user)
        url_annul = reverse('inventory:annuler_vente_credit',
                            args=[self.boutique.id, vente.id])
        resp = self.client.post(url_annul)
        self.assertEqual(resp.status_code, 302)

        vente.refresh_from_db()
        self.assertEqual(vente.statut, 'ANNULE')
        self.article.refresh_from_db()
        self.article2.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)
        self.assertEqual(self.article2.quantite_stock, 5)
        self.assertEqual(MouvementStock.objects.filter(
            type_mouvement='RETOUR', article=self.article).count(), 1)
        self.assertEqual(MouvementStock.objects.filter(
            type_mouvement='RETOUR', article=self.article2).count(), 1)

    def test_article_autre_boutique_rejete(self):
        autre_boutique = Boutique.objects.create(
            nom='Boutique AUTRE', commercant=self.commercant, code_boutique='BT-AUTRE',
        )
        article_autre = Article.objects.create(
            code='AUTRE-1', nom='Article autre boutique',
            prix_vente=Decimal('5000'), boutique=autre_boutique,
            quantite_stock=5, est_actif=True, est_valide_client=True,
        )
        resp = self.api.post(
            self.url_creer,
            data=self._payload(article_id=article_autre.id, quantite=1,
                               prix_total=5000),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(VenteAcompte.objects.exists())

    # ── Compatibilité ancien payload ─────────────────────────────────────

    def test_ancien_payload_sans_article_id(self):
        """Sans article_id : article_nom libre, quantite=1, pas de FK article."""
        resp = self.api.post(
            self.url_creer,
            data=self._payload(quantite=None, article_id=None),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        vente = VenteAcompte.objects.get()
        self.assertIsNone(vente.article)
        self.assertEqual(vente.quantite, 1)
        self.assertEqual(vente.prix_total, Decimal('60000.00'))

    # ── Listes / détails ─────────────────────────────────────────────────

    def test_liste_et_detail_incluent_quantite(self):
        self.api.post(
            self.url_creer,
            data=self._payload(article_id=self.article.id, quantite=3,
                               prix_total=float(Decimal('30000') * 3)),
            content_type='application/json', **self.entete,
        )
        vente = VenteAcompte.objects.get()

        liste = self.api.get(f'/api/credit/boutique/{self.boutique.id}/ventes/',
                             **self.entete)
        self.assertEqual(liste.status_code, 200)
        self.assertEqual(liste.json()['ventes'][0]['quantite'], 3)

        detail = self.api.get(f'/api/credit/vente/{vente.id}/', **self.entete)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['quantite'], 3)
        self.assertEqual(detail.json()['prix_total'], 90000.0)

    # ── Stock : décrément immédiat à la création ─────────────────────────

    def test_stock_decremente_avec_mouvement(self):
        """La création décrémente le stock et crée un MouvementStock VENTE."""
        resp = self.api.post(
            self.url_creer,
            data=self._payload(article_id=self.article.id, quantite=2),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 201, resp.content)

        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 8)

        data = resp.json()
        self.assertEqual(data['stock_avant'], 10)
        self.assertEqual(data['stock_restant'], 8)

        mv = MouvementStock.objects.get(article=self.article,
                                        type_mouvement='VENTE')
        self.assertEqual(mv.type_mouvement, 'VENTE')
        self.assertEqual(mv.quantite, -2)
        self.assertEqual(mv.stock_avant, 10)
        self.assertEqual(mv.stock_apres, 8)
        self.assertEqual(mv.reference_document,
                         VenteAcompte.objects.get().reference)

    def test_stock_insuffisant_rejete(self):
        """Quantité supérieure au stock : 400, aucune vente, stock intact."""
        resp = self.api.post(
            self.url_creer,
            data=self._payload(article_id=self.article.id, quantite=11,
                               prix_total=float(Decimal('30000') * 11)),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('stock insuffisant', resp.json()['error'].lower())
        self.assertFalse(VenteAcompte.objects.exists())
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)

    def test_sans_article_id_stock_intact(self):
        """Ancien payload (pas d'article_id) : ni décrément, ni mouvement."""
        resp = self.api.post(
            self.url_creer,
            data=self._payload(quantite=None, article_id=None),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertIsNone(data['stock_avant'])
        self.assertIsNone(data['stock_restant'])
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)
        # Seul le mouvement d'ouverture (ENTREE) existe : aucun VENTE/RETOUR
        self.assertFalse(MouvementStock.objects.filter(
            article=self.article).exclude(type_mouvement='ENTREE').exists())

    def test_annulation_rend_le_stock(self):
        """L'annulation web remet le stock et crée un MouvementStock RETOUR."""
        resp = self.api.post(
            self.url_creer,
            data=self._payload(article_id=self.article.id, quantite=3,
                               prix_total=float(Decimal('30000') * 3)),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        vente = VenteAcompte.objects.get()
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 7)

        self.client.force_login(self.user)
        url_annul = reverse('inventory:annuler_vente_credit',
                            args=[self.boutique.id, vente.id])
        resp = self.client.post(url_annul)
        self.assertEqual(resp.status_code, 302)

        vente.refresh_from_db()
        self.assertEqual(vente.statut, 'ANNULE')
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)

        mv = MouvementStock.objects.filter(type_mouvement='RETOUR',
                                           article=self.article).get()
        self.assertEqual(mv.quantite, 3)
        self.assertEqual(mv.stock_apres, 10)

        # Seconde annulation (déjà annulée) : pas de double retour de stock
        resp = self.client.post(url_annul)
        self.assertEqual(resp.status_code, 302)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 10)
