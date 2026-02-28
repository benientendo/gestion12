SELECT id, nom FROM inventory_boutique WHERE id = 44;
SELECT COUNT(*) AS nb_articles FROM inventory_article WHERE boutique_id = 44;
UPDATE inventory_article SET quantite_stock = 0, prix_vente = 0, date_mise_a_jour = NOW() WHERE boutique_id = 44;
SELECT COUNT(*) AS articles_reinitialises FROM inventory_article WHERE boutique_id = 44 AND quantite_stock = 0;
