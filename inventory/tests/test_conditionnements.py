"""
Conditionnements (boutiques Boucherie) :
- Modele Conditionnement + Article.unite_base + LigneVente.unite_coefficient
- Catalogue API : conditionnements exposes uniquement pour type BOUCHERIE
- Vente avec conditionnement_id : stock debite en unite de base (quantite x coefficient)
- Annulation : restauration du stock en unite de base
- Back-office : creation AJAX d'article avec conditionnements (BOUCHERIE seulement)
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, Client as TestClient
from django.urls import reverse

from inventory.models import (
    Article, Boutique, Client as Terminal, Commercant,
    Conditionnement, LigneVente, MouvementStock, Vente,
)

User = get_user_model()


class ConditionnementModeleTestCase(TestCase):
    """Proprietes du modele : prix effectif + quantite de base."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_cond_mod', password='pass1234', email='comm_cond_mod@test.cd'
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='COND MOD', nom_responsable='COND',
            email='comm_cond_mod@test.cd', user=self.user,
        )
        self.boutique = Boutique.objects.create(
            nom='Boucherie Mod', commercant=self.commercant,
            code_boutique='BT-CMOD-001', type_commerce='BOUCHERIE',
        )
        self.article = Article.objects.create(
            code='COND-M1', nom='Poisson frais',
            prix_vente=Decimal('1000'),
            boutique=self.boutique, quantite_stock=500,
            est_actif=True, est_valide_client=True,
            unite_base='kg',
        )

    def test_prix_vente_effectif_avec_prix_explicite(self):
        c = Conditionnement.objects.create(
            article=self.article, libelle='sac', coefficient=25,
            prix_vente=Decimal('20000'),
        )
        self.assertEqual(c.prix_vente_effectif, Decimal('20000'))

    def test_prix_vente_effectif_auto(self):
        c = Conditionnement.objects.create(
            article=self.article, libelle='sac', coefficient=25,
        )
        self.assertEqual(c.prix_vente_effectif, Decimal('25000'))

    def test_quantite_base_ligne(self):
        c = Conditionnement.objects.create(
            article=self.article, libelle='sac', coefficient=25,
        )
        ligne = LigneVente(
            article=self.article, conditionnement=c,
            unite_coefficient=25, quantite=3,
            prix_unitaire=Decimal('20000'),
        )
        self.assertEqual(ligne.quantite_base, 75)

    def test_quantite_base_ligne_sans_conditionnement(self):
        ligne = LigneVente(
            article=self.article, unite_coefficient=1, quantite=4,
            prix_unitaire=Decimal('1000'),
        )
        self.assertEqual(ligne.quantite_base, 4)


class CatalogueConditionnementsTestCase(TestCase):
    """Catalogue API : les conditionnements ne sortent que pour les boutiques Boucherie."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_cond_cat', password='pass1234', email='comm_cond_cat@test.cd'
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='COND CAT', nom_responsable='COND',
            email='comm_cond_cat@test.cd', user=self.user,
        )
        self.bout_boucherie = Boutique.objects.create(
            nom='Boucherie Cat', commercant=self.commercant,
            code_boutique='BT-CCAT-001', type_commerce='BOUCHERIE',
        )
        self.bout_general = Boutique.objects.create(
            nom='General Cat', commercant=self.commercant,
            code_boutique='BT-CCAT-002', type_commerce='GENERAL',
        )
        self.terminal_b = Terminal.objects.create(
            compte_proprietaire=self.user, boutique=self.bout_boucherie,
            nom_terminal='T-CAT-B', numero_serie='SERIAL-CCAT-B01', est_actif=True,
        )
        self.terminal_g = Terminal.objects.create(
            compte_proprietaire=self.user, boutique=self.bout_general,
            nom_terminal='T-CAT-G', numero_serie='SERIAL-CCAT-G01', est_actif=True,
        )
        self.article_b = Article.objects.create(
            code='COND-C1', nom='Poisson frais',
            prix_vente=Decimal('1000'),
            boutique=self.bout_boucherie, quantite_stock=500,
            est_actif=True, est_valide_client=True, unite_base='kg',
        )
        self.kg = Conditionnement.objects.create(
            article=self.article_b, libelle='kg', coefficient=1,
        )
        self.sac = Conditionnement.objects.create(
            article=self.article_b, libelle='sac', coefficient=25,
        )
        self.article_g = Article.objects.create(
            code='COND-C2', nom='Savon',
            prix_vente=Decimal('500'),
            boutique=self.bout_general, quantite_stock=10,
            est_actif=True, est_valide_client=True,
        )
        Conditionnement.objects.create(
            article=self.article_g, libelle='lot', coefficient=6,
        )
        self.api = TestClient(SERVER_NAME='127.0.0.1')
        self.url = reverse('api_v2_simple:articles_list')

    def test_boucherie_expose_conditionnements(self):
        r = self.api.get(
            self.url, {'boutique_id': self.bout_boucherie.id},
            HTTP_X_DEVICE_SERIAL='SERIAL-CCAT-B01',
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body.get('boutique_type'), 'BOUCHERIE')
        art = next(a for a in body['articles'] if a['id'] == self.article_b.id)
        self.assertEqual(art['unite_base'], 'kg')
        libelles = {c['libelle']: c for c in art['conditionnements']}
        self.assertIn('kg', libelles)
        self.assertIn('sac', libelles)
        self.assertEqual(libelles['sac']['coefficient'], 25)
        self.assertEqual(libelles['sac']['prix_vente'], '25000.00')
        self.assertEqual(libelles['kg']['prix_vente'], '1000.00')

    def test_general_cache_conditionnements(self):
        r = self.api.get(
            self.url, {'boutique_id': self.bout_general.id},
            HTTP_X_DEVICE_SERIAL='SERIAL-CCAT-G01',
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertNotEqual(body.get('boutique_type'), 'BOUCHERIE')
        art = next(a for a in body['articles'] if a['id'] == self.article_g.id)
        self.assertEqual(art['conditionnements'], [])


class VenteConditionnementTestCase(TestCase):
    """Vente via API POS : le stock est debite en unite de base."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_cond_vente', password='pass1234', email='comm_cond_vente@test.cd'
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='COND VENTE', nom_responsable='COND',
            email='comm_cond_vente@test.cd', user=self.user,
        )
        self.boutique = Boutique.objects.create(
            nom='Boucherie Vente', commercant=self.commercant,
            code_boutique='BT-CVNT-001', type_commerce='BOUCHERIE',
        )
        self.terminal = Terminal.objects.create(
            compte_proprietaire=self.user, boutique=self.boutique,
            nom_terminal='T-VNT', numero_serie='SERIAL-CVNT-001', est_actif=True,
        )
        self.article = Article.objects.create(
            code='COND-V1', nom='Poisson frais',
            prix_vente=Decimal('1000'),
            boutique=self.boutique, quantite_stock=500,
            est_actif=True, est_valide_client=True, unite_base='kg',
        )
        self.kg = Conditionnement.objects.create(
            article=self.article, libelle='kg', coefficient=1,
        )
        self.sac = Conditionnement.objects.create(
            article=self.article, libelle='sac', coefficient=25,
        )
        self.api = TestClient(SERVER_NAME='127.0.0.1')
        self.entete = {'HTTP_X_DEVICE_SERIAL': 'SERIAL-CVNT-001'}
        self.url_creer = reverse('api_v2_simple:create_vente')
        self.url_annuler = reverse('api_v2_simple:annuler_vente')

    def _payload(self, **kwargs):
        base = {
            'lignes': [{
                'article_id': self.article.id,
                'quantite': 1,
            }],
        }
        base.update(kwargs)
        return base

    def test_vente_sac_debite_stock_en_kg(self):
        r = self.api.post(
            self.url_creer,
            data=self._payload(lignes=[{
                'article_id': self.article.id,
                'quantite': 1,
                'conditionnement_id': self.sac.id,
                'prix_unitaire': 25000,
            }]),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 475)

        ligne = LigneVente.objects.get()
        self.assertEqual(ligne.conditionnement, self.sac)
        self.assertEqual(ligne.unite_coefficient, 25)
        self.assertEqual(ligne.quantite, 1)
        self.assertEqual(ligne.quantite_base, 25)

        mv = MouvementStock.objects.get(type_mouvement='VENTE')
        self.assertEqual(mv.quantite, -25)
        self.assertEqual(mv.stock_avant, 500)
        self.assertEqual(mv.stock_apres, 475)

        ligne_json = body['vente']['lignes'][0]
        self.assertEqual(ligne_json['conditionnement_id'], self.sac.id)
        self.assertEqual(ligne_json['conditionnement_libelle'], 'sac')
        self.assertEqual(ligne_json['unite_coefficient'], 25)

    def test_vente_kg_sans_conversion(self):
        r = self.api.post(
            self.url_creer,
            data=self._payload(lignes=[{
                'article_id': self.article.id,
                'quantite': 3,
                'conditionnement_id': self.kg.id,
                'prix_unitaire': 1000,
            }]),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 497)
        mv = MouvementStock.objects.get(type_mouvement='VENTE')
        self.assertEqual(mv.quantite, -3)

    def test_vente_sans_conditionnement_unite_de_base(self):
        r = self.api.post(
            self.url_creer,
            data=self._payload(lignes=[{
                'article_id': self.article.id,
                'quantite': 2,
                'prix_unitaire': 1000,
            }]),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 498)
        ligne = LigneVente.objects.get()
        self.assertIsNone(ligne.conditionnement)
        self.assertEqual(ligne.unite_coefficient, 1)

    def test_conditionnement_invalide_vend_en_unite_de_base(self):
        r = self.api.post(
            self.url_creer,
            data=self._payload(lignes=[{
                'article_id': self.article.id,
                'quantite': 2,
                'conditionnement_id': 999999,
                'prix_unitaire': 1000,
            }]),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 498)

    def test_annulation_restaure_en_unite_de_base(self):
        r = self.api.post(
            self.url_creer,
            data=self._payload(lignes=[{
                'article_id': self.article.id,
                'quantite': 1,
                'conditionnement_id': self.sac.id,
                'prix_unitaire': 25000,
            }]),
            content_type='application/json', **self.entete,
        )
        self.assertEqual(r.status_code, 201, r.content)
        numero_facture = r.json()['vente']['numero_facture']

        r2 = self.api.post(
            self.url_annuler,
            data={'numero_facture': numero_facture, 'motif': 'Erreur de caisse'},
            content_type='application/json', **self.entete,
        )
        self.assertEqual(r2.status_code, 200, r2.content)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 500)
        vente = Vente.objects.get(numero_facture=numero_facture)
        self.assertTrue(vente.est_annulee)


class BackOfficeConditionnementsTestCase(TestCase):
    """Formulaire commerant : conditionnements crees uniquement pour les boutiques Boucherie."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_cond_bo', password='pass1234', email='comm_cond_bo@test.cd'
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='COND BO', nom_responsable='COND',
            email='comm_cond_bo@test.cd', user=self.user,
        )
        self.bout_boucherie = Boutique.objects.create(
            nom='Boucherie BO', commercant=self.commercant,
            code_boutique='BT-CBO-001', type_commerce='BOUCHERIE',
        )
        self.bout_general = Boutique.objects.create(
            nom='General BO', commercant=self.commercant,
            code_boutique='BT-CBO-002', type_commerce='GENERAL',
        )
        self.web = TestClient()
        self.web.force_login(self.user)

    def _post_ajax(self, boutique, **extra):
        url = reverse('inventory:ajouter_article_boutique', args=[boutique.id])
        data = {
            'nom': 'Poisson frais',
            'prix_vente': '1000',
            'quantite_stock': '500',
            'devise': 'CDF',
            'unite_base': 'kg',
            'cond_libelle_0': 'kg',
            'cond_coefficient_0': '1',
            'cond_prix_0': '',
            'cond_libelle_1': 'sac',
            'cond_coefficient_1': '25',
            'cond_prix_1': '25000',
        }
        data.update(extra)
        return self.web.post(url, data=data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def test_ajout_ajax_boucherie_cree_conditionnements(self):
        r = self._post_ajax(self.bout_boucherie)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['success'])
        article = Article.objects.get(boutique=self.bout_boucherie)
        self.assertEqual(article.unite_base, 'kg')
        conds = {c.libelle: c for c in article.conditionnements.all()}
        self.assertEqual(set(conds), {'kg', 'sac'})
        self.assertEqual(conds['sac'].coefficient, 25)
        self.assertEqual(conds['sac'].prix_vente, Decimal('25000'))
        self.assertEqual(conds['kg'].coefficient, 1)

    def test_ajout_ajax_general_ignore_conditionnements(self):
        r = self._post_ajax(self.bout_general, nom='Savon')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()['success'])
        article = Article.objects.get(boutique=self.bout_general)
        self.assertEqual(article.unite_base, '')
        self.assertEqual(article.conditionnements.count(), 0)

    def test_modification_remplace_conditionnements(self):
        self._post_ajax(self.bout_boucherie)
        article = Article.objects.get(boutique=self.bout_boucherie)
        url = reverse('inventory:modifier_article_boutique',
                      args=[self.bout_boucherie.id, article.id])
        r = self.web.post(url, data={
            'nom': 'Poisson frais',
            'prix_vente': '1200',
            'quantite_stock': '500',
            'devise': 'CDF',
            'est_actif': 'on',
            'unite_base': 'kg',
            'cond_libelle_0': 'kg',
            'cond_coefficient_0': '1',
            'cond_libelle_1': 'plateau',
            'cond_coefficient_1': '10',
        })
        self.assertEqual(r.status_code, 302)
        article.refresh_from_db()
        self.assertEqual(article.unite_base, 'kg')
        self.assertEqual(article.prix_vente, Decimal('1200'))
        libelles = set(article.conditionnements.values_list('libelle', flat=True))
        self.assertEqual(libelles, {'kg', 'plateau'})


class StockDecomposeTestCase(TestCase):
    """Affichage mixte « 20 cartons · 15 kg · 500 g » + reception en cartons."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_cond_dec', password='pass1234', email='comm_cond_dec@test.cd'
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='COND DEC', nom_responsable='COND',
            email='comm_cond_dec@test.cd', user=self.user,
        )
        self.bout_boucherie = Boutique.objects.create(
            nom='Boucherie Dec', commercant=self.commercant,
            code_boutique='BT-CDEC-001', type_commerce='BOUCHERIE',
        )
        self.bout_general = Boutique.objects.create(
            nom='General Dec', commercant=self.commercant,
            code_boutique='BT-CDEC-002', type_commerce='GENERAL',
        )
        # Article Boucherie : base = gramme (la plus petite unite)
        self.article = Article.objects.create(
            boutique=self.bout_boucherie, nom='Poisson', code='POI-1',
            prix_vente=Decimal('2'), devise='CDF', quantite_stock=515500,
            est_actif=True, est_valide_client=True, unite_base='g',
        )
        Conditionnement.objects.create(article=self.article, libelle='carton', coefficient=25000, ordre=0)
        Conditionnement.objects.create(article=self.article, libelle='kg', coefficient=1000, ordre=1)
        Conditionnement.objects.create(article=self.article, libelle='g', coefficient=1, ordre=2)
        self.web = TestClient()
        self.web.force_login(self.user)

    def test_decomposition_gloutonne(self):
        self.assertEqual(
            self.article.stock_decompose,
            [('carton', 20), ('kg', 15), ('g', 500)],
        )
        self.assertEqual(
            self.article.stock_decompose_formate,
            '20 carton · 15 kg · 500 g',
        )

    def test_decomposition_sans_reste(self):
        self.article.quantite_stock = 500000  # 20 cartons exactement
        self.assertEqual(self.article.stock_decompose, [('carton', 20)])

    def test_decomposition_stock_zero(self):
        self.article.quantite_stock = 0
        self.assertEqual(self.article.stock_decompose, [('g', 0)])

    def test_decomposition_article_general(self):
        autre = Article.objects.create(
            boutique=self.bout_general, nom='Savon', code='SAV-1',
            prix_vente=Decimal('100'), devise='CDF', quantite_stock=30,
            est_actif=True, est_valide_client=True,
        )
        self.assertEqual(autre.stock_decompose, [('unités', 30)])
        self.assertEqual(autre.stock_decompose_formate, '30 unités')

    def test_reception_en_cartons_convertie_en_base(self):
        """2 cartons envoyes depuis le back-office → quantite_envoyee = 50000 g."""
        url = reverse('inventory:ajuster_stock_article',
                      args=[self.bout_boucherie.id, self.article.id])
        r = self.web.post(url, data={
            'type_ajustement': 'ajouter',
            'quantite': '2',
            'unite_coefficient': '25000',
            'commentaire': 'Réception 2 cartons',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['quantite_en_attente'], 50000)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_envoyee, 50000)
        self.assertFalse(self.article.est_valide_client)

    def test_reception_unite_base_sans_conversion(self):
        url = reverse('inventory:ajuster_stock_article',
                      args=[self.bout_boucherie.id, self.article.id])
        r = self.web.post(url, data={
            'type_ajustement': 'retirer',
            'quantite': '1000',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200, r.content)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 515500 - 1000)
        self.assertTrue(
            MouvementStock.objects.filter(article=self.article, quantite=-1000).exists()
        )

    def test_reception_definir_en_cartons(self):
        url = reverse('inventory:ajuster_stock_article',
                      args=[self.bout_boucherie.id, self.article.id])
        r = self.web.post(url, data={
            'type_ajustement': 'definir',
            'quantite': '25',
            'unite_coefficient': '1000',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200, r.content)
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_stock, 25000)

    def test_ajouts_en_attente_accumulent(self):
        """Un 2e ajout ne doit JAMAIS ecraser le 1er (re-confirmation par erreur)."""
        url = reverse('inventory:ajuster_stock_article',
                      args=[self.bout_boucherie.id, self.article.id])
        self.web.post(url, data={
            'type_ajustement': 'ajouter', 'quantite': '40',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_envoyee, 40)
        # Re-confirmation accidentelle avec la valeur par defaut (1) → 41, pas 1
        r = self.web.post(url, data={
            'type_ajustement': 'ajouter', 'quantite': '1',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(r.json()['success'])
        self.article.refresh_from_db()
        self.assertEqual(self.article.quantite_envoyee, 41)

    def test_ajouts_en_attente_accumulent_en_cartons(self):
        url = reverse('inventory:ajuster_stock_article',
                      args=[self.bout_boucherie.id, self.article.id])
        for qte in ('2', '1'):
            self.web.post(url, data={
                'type_ajustement': 'ajouter',
                'quantite': qte,
                'unite_coefficient': '25000',
            }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.article.refresh_from_db()
        # 2 cartons + 1 carton = 75000 g
        self.assertEqual(self.article.quantite_envoyee, 75000)


class HierarchieUnitesTestCase(TestCase):
    """Bonnes pratiques (Mbolongo) : carton 30 = 3 rames de 10, demi 5, kg 1.
    Chaque coefficient doit etre un multiple de l'unite plus petite."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='comm_cond_hier', password='pass1234', email='comm_cond_hier@test.cd'
        )
        self.commercant = Commercant.objects.create(
            nom_entreprise='COND HIER', nom_responsable='COND',
            email='comm_cond_hier@test.cd', user=self.user,
        )
        self.boutique = Boutique.objects.create(
            nom='Boucherie Hier', commercant=self.commercant,
            code_boutique='BT-CHIER-001', type_commerce='BOUCHERIE',
        )
        self.bout_general = Boutique.objects.create(
            nom='General Hier', commercant=self.commercant,
            code_boutique='BT-CHIER-002', type_commerce='GENERAL',
        )
        self.article = Article.objects.create(
            code='POI-MBO', nom='Poisson Mbolongo',
            prix_vente=Decimal('1000'),
            boutique=self.boutique, quantite_stock=90000,
            est_actif=True, est_valide_client=True, unite_base='kg',
        )
        Conditionnement.objects.create(article=self.article, libelle='carton', coefficient=30, ordre=0)
        Conditionnement.objects.create(article=self.article, libelle='rame', coefficient=10, ordre=1)
        Conditionnement.objects.create(article=self.article, libelle='demi', coefficient=5, ordre=2)
        Conditionnement.objects.create(article=self.article, libelle='kg', coefficient=1, ordre=3)
        self.web = TestClient()
        self.web.force_login(self.user)

    def test_unites_resume(self):
        self.assertEqual(
            self.article.unites_resume,
            'carton 30 kg · rame 10 kg · demi 5 kg · kg 1 kg',
        )

    def test_unites_equivalences(self):
        self.assertEqual(
            self.article.unites_equivalences,
            '1 carton = 3 rame · 1 rame = 2 demi · 1 demi = 5 kg',
        )

    def test_unites_resume_vide_hors_boucherie(self):
        autre = Article.objects.create(
            boutique=self.bout_general, nom='Savon', code='SAV-H1',
            prix_vente=Decimal('100'), devise='CDF', quantite_stock=30,
            est_actif=True, est_valide_client=True,
        )
        Conditionnement.objects.create(article=autre, libelle='lot', coefficient=6)
        self.assertEqual(autre.unites_resume, '')
        self.assertEqual(autre.unites_equivalences, '')

    def test_helper_hierarchie_valide(self):
        from inventory.views_commercant import _valider_hierarchie_conditionnements
        unites = [
            {'libelle': 'carton', 'coefficient': 30},
            {'libelle': 'rame', 'coefficient': 10},
            {'libelle': 'demi', 'coefficient': 5},
            {'libelle': 'kg', 'coefficient': 1},
        ]
        self.assertIsNone(_valider_hierarchie_conditionnements(unites))

    def test_helper_non_multiple_refuse(self):
        from inventory.views_commercant import _valider_hierarchie_conditionnements
        unites = [
            {'libelle': 'carton', 'coefficient': 30},
            {'libelle': 'sac', 'coefficient': 25},
            {'libelle': 'kg', 'coefficient': 1},
        ]
        erreur = _valider_hierarchie_conditionnements(unites)
        self.assertIsNotNone(erreur)
        self.assertIn("n'est pas un multiple", erreur)

    def test_helper_unite_seule_ignorée(self):
        from inventory.views_commercant import _valider_hierarchie_conditionnements
        self.assertIsNone(_valider_hierarchie_conditionnements(
            [{'libelle': 'kg', 'coefficient': 1}]
        ))

    def test_ajout_ajax_hierarchie_invalide_refuse(self):
        url = reverse('inventory:ajouter_article_boutique', args=[self.boutique.id])
        r = self.web.post(url, data={
            'nom': 'Autre poisson',
            'prix_vente': '1000',
            'quantite_stock': '100',
            'devise': 'CDF',
            'unite_base': 'kg',
            'cond_libelle_0': 'kg',
            'cond_coefficient_0': '1',
            'cond_libelle_1': 'sac',
            'cond_coefficient_1': '25',
            'cond_libelle_2': 'carton',
            'cond_coefficient_2': '30',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body['success'])
        self.assertIn("n'est pas un multiple", body['message'])
        self.assertFalse(Article.objects.filter(nom='Autre poisson').exists())

    def test_modification_hierarchie_invalide_refuse(self):
        url = reverse('inventory:modifier_article_boutique',
                      args=[self.boutique.id, self.article.id])
        r = self.web.post(url, data={
            'nom': 'Poisson Mbolongo',
            'prix_vente': '1000',
            'quantite_stock': '90000',
            'devise': 'CDF',
            'est_actif': 'on',
            'unite_base': 'kg',
            'cond_libelle_0': 'kg',
            'cond_coefficient_0': '1',
            'cond_libelle_1': 'sac',
            'cond_coefficient_1': '25',
            'cond_libelle_2': 'carton',
            'cond_coefficient_2': '30',
        })
        # Re-rendu du formulaire avec erreur (article et unites inchanges)
        self.assertEqual(r.status_code, 200)
        libelles = set(self.article.conditionnements.values_list('libelle', flat=True))
        self.assertEqual(libelles, {'carton', 'rame', 'demi', 'kg'})

