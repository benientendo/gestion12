#!/usr/bin/env python
"""
Script pour restaurer la base de données à l'état original
"""
import sqlite3
import os
import sys

# Chemin vers la base de données
DB_PATH = "db.sqlite3"

def restore_original_db():
    """Restaurer la base de données à l'état original"""
    
    if not os.path.exists(DB_PATH):
        print("❌ Base de données introuvable!")
        return False
    
    try:
        # Connexion à la base de données
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("🔄 Restauration de la base de données...")
        
        # Désactiver les contraintes de clés étrangères temporairement
        cursor.execute("PRAGMA foreign_keys=OFF;")
        
        # Supprimer les tables problématiques
        cursor.execute("DROP TABLE IF EXISTS inventory_commercant;")
        cursor.execute("DROP TABLE IF EXISTS inventory_boutique;")
        cursor.execute("DROP TABLE IF EXISTS inventory_terminalmau;")
        cursor.execute("DROP TABLE IF EXISTS inventory_sessionterminalmau;")
        
        print("✅ Tables problématiques supprimées")
        
        # Supprimer les colonnes boutique_id des tables existantes si elles existent
        tables_to_clean = [
            'inventory_article',
            'inventory_categorie', 
            'inventory_vente',
            'inventory_scanrecent',
            'inventory_mouvementstock'
        ]
        
        for table in tables_to_clean:
            try:
                # Vérifier si la colonne existe
                cursor.execute(f"PRAGMA table_info({table});")
                columns = cursor.fetchall()
                has_boutique_id = any(col[1] == 'boutique_id' for col in columns)
                
                if has_boutique_id:
                    print(f"🧹 Suppression de boutique_id de {table}")
                    # Créer une nouvelle table sans boutique_id
                    cursor.execute(f"CREATE TABLE {table}_temp AS SELECT * FROM {table};")
                    cursor.execute(f"DROP TABLE {table};")
                    
                    # Recréer la table sans boutique_id (structure simplifiée)
                    if table == 'inventory_article':
                        cursor.execute(f"""
                            CREATE TABLE {table} AS 
                            SELECT id, nom, description, prix_achat, prix_vente, stock, code, 
                                   qr_code, image, date_creation, date_modification, categorie_id
                            FROM {table}_temp;
                        """)
                    elif table == 'inventory_categorie':
                        cursor.execute(f"""
                            CREATE TABLE {table} AS 
                            SELECT id, nom, description, date_creation
                            FROM {table}_temp;
                        """)
                    elif table == 'inventory_vente':
                        cursor.execute(f"""
                            CREATE TABLE {table} AS 
                            SELECT id, numero_facture, date_vente, total, client_maui_id,
                                   adresse_ip_client, version_app_maui
                            FROM {table}_temp;
                        """)
                    else:
                        # Pour les autres tables, garder toutes les colonnes sauf boutique_id
                        columns_str = ', '.join([col[1] for col in columns if col[1] != 'boutique_id'])
                        cursor.execute(f"""
                            CREATE TABLE {table} AS 
                            SELECT {columns_str}
                            FROM {table}_temp;
                        """)
                    
                    cursor.execute(f"DROP TABLE {table}_temp;")
                    print(f"✅ {table} nettoyée")
                    
            except Exception as e:
                print(f"⚠️  Erreur lors du nettoyage de {table}: {e}")
        
        # Réactiver les contraintes de clés étrangères
        cursor.execute("PRAGMA foreign_keys=ON;")
        
        # Valider les changements
        conn.commit()
        conn.close()
        
        print("✅ Base de données restaurée à l'état original!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la restauration: {e}")
        return False

if __name__ == "__main__":
    success = restore_original_db()
    sys.exit(0 if success else 1)
