SELECT b.id, b.nom, c.nom_entreprise FROM inventory_boutique b JOIN inventory_commercant c ON b.commercant_id = c.id WHERE b.id = 44;
SELECT COUNT(*) AS nombre_articles FROM inventory_stock WHERE boutique_id = 44;
