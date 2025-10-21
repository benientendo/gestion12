#!/usr/bin/env python
"""
Script pour corriger directement la base de données SQLite
"""
import sqlite3
import os
import sys

# Chemin vers la base de données
DB_PATH = "db.sqlite3"

def fix_database():
    """Corriger la structure de la base de données"""
    
    if not os.path.exists(DB_PATH):
        print("❌ Base de données introuvable!")
        return False
    
    try:
        # Connexion à la base de données
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("🔧 Correction de la base de données...")
        
        # Désactiver les contraintes de clés étrangères temporairement
        cursor.execute("PRAGMA foreign_keys=OFF;")
        
        # 1. Vérifier si la table inventory_commercant existe et la supprimer si nécessaire
        cursor.execute("DROP TABLE IF EXISTS inventory_commercant;")
        
        # 2. Créer la nouvelle table inventory_commercant avec la bonne structure
        cursor.execute("""
            CREATE TABLE inventory_commercant (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom_entreprise VARCHAR(200) NOT NULL,
                nom_responsable VARCHAR(100) NOT NULL,
                email VARCHAR(254) UNIQUE NOT NULL,
                telephone VARCHAR(20) NOT NULL DEFAULT '',
                adresse TEXT NOT NULL DEFAULT '',
                numero_registre_commerce VARCHAR(50) NOT NULL DEFAULT '',
                numero_fiscal VARCHAR(50) NOT NULL DEFAULT '',
                est_actif BOOLEAN NOT NULL DEFAULT 1,
                date_creation DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                date_mise_a_jour DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                type_abonnement VARCHAR(50) NOT NULL DEFAULT 'GRATUIT',
                limite_boutiques INTEGER NOT NULL DEFAULT 1,
                limite_articles_par_boutique INTEGER NOT NULL DEFAULT 100,
                notes_admin TEXT NOT NULL DEFAULT '',
                utilisateur_id INTEGER UNIQUE NOT NULL REFERENCES auth_user(id)
            );
        """)
        
        # 3. Créer la table inventory_boutique
        cursor.execute("DROP TABLE IF EXISTS inventory_boutique;")
        cursor.execute("""
            CREATE TABLE inventory_boutique (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom VARCHAR(200) NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                type_commerce VARCHAR(50) NOT NULL DEFAULT 'BOUTIQUE',
                adresse TEXT NOT NULL DEFAULT '',
                ville VARCHAR(100) NOT NULL DEFAULT '',
                quartier VARCHAR(100) NOT NULL DEFAULT '',
                telephone VARCHAR(20) NOT NULL DEFAULT '',
                code_boutique VARCHAR(50) UNIQUE NOT NULL DEFAULT '',
                cle_api_boutique VARCHAR(100) UNIQUE NOT NULL DEFAULT '',
                est_active BOOLEAN NOT NULL DEFAULT 1,
                devise VARCHAR(10) NOT NULL DEFAULT 'CDF',
                date_creation DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                date_mise_a_jour DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                commercant_id INTEGER NOT NULL REFERENCES inventory_commercant(id)
            );
        """)
        
        # 4. Créer la table inventory_terminalmau
        cursor.execute("DROP TABLE IF EXISTS inventory_terminalmau;")
        cursor.execute("""
            CREATE TABLE inventory_terminalmau (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom_terminal VARCHAR(200) NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                numero_serie VARCHAR(50) UNIQUE NOT NULL,
                cle_api VARCHAR(100) UNIQUE NOT NULL,
                nom_utilisateur VARCHAR(100) NOT NULL DEFAULT '',
                est_actif BOOLEAN NOT NULL DEFAULT 1,
                derniere_connexion DATETIME NULL,
                derniere_activite DATETIME NULL,
                date_creation DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                date_mise_a_jour DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                version_app_maui VARCHAR(20) NOT NULL DEFAULT '',
                derniere_adresse_ip VARCHAR(39) NULL,
                boutique_id INTEGER NOT NULL REFERENCES inventory_boutique(id)
            );
        """)
        
        # 5. Créer la table inventory_sessionterminalmau
        cursor.execute("DROP TABLE IF EXISTS inventory_sessionterminalmau;")
        cursor.execute("""
            CREATE TABLE inventory_sessionterminalmau (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_session VARCHAR(100) UNIQUE NOT NULL,
                adresse_ip VARCHAR(39) NOT NULL,
                user_agent TEXT NOT NULL DEFAULT '',
                version_app VARCHAR(50) NOT NULL DEFAULT '',
                date_debut DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                date_fin DATETIME NULL,
                est_active BOOLEAN NOT NULL DEFAULT 1,
                terminal_id INTEGER NOT NULL REFERENCES inventory_terminalmau(id)
            );
        """)
        
        # 6. Insérer un commerçant par défaut (ID 1)
        cursor.execute("""
            INSERT OR IGNORE INTO inventory_commercant 
            (id, nom_entreprise, nom_responsable, email, utilisateur_id) 
            VALUES (1, 'Commerçant par défaut', 'Admin', 'admin@example.com', 1);
        """)
        
        # 7. Insérer une boutique par défaut (ID 1)
        cursor.execute("""
            INSERT OR IGNORE INTO inventory_boutique 
            (id, nom, description, type_commerce, code_boutique, cle_api_boutique, commercant_id) 
            VALUES (1, 'Boutique par défaut', 'Boutique créée automatiquement', 'BOUTIQUE', 'BOUT_001', 'default-api-key', 1);
        """)
        
        # 8. Ajouter les colonnes boutique_id aux tables existantes si elles n'existent pas
        try:
            cursor.execute("ALTER TABLE inventory_article ADD COLUMN boutique_id INTEGER NOT NULL DEFAULT 1;")
        except sqlite3.OperationalError:
            pass  # La colonne existe déjà
            
        try:
            cursor.execute("ALTER TABLE inventory_categorie ADD COLUMN boutique_id INTEGER NOT NULL DEFAULT 1;")
        except sqlite3.OperationalError:
            pass  # La colonne existe déjà
            
        try:
            cursor.execute("ALTER TABLE inventory_vente ADD COLUMN boutique_id INTEGER NOT NULL DEFAULT 1;")
        except sqlite3.OperationalError:
            pass  # La colonne existe déjà
            
        try:
            cursor.execute("ALTER TABLE inventory_scanrecent ADD COLUMN boutique_id INTEGER NOT NULL DEFAULT 1;")
        except sqlite3.OperationalError:
            pass  # La colonne existe déjà
            
        try:
            cursor.execute("ALTER TABLE inventory_mouvementstock ADD COLUMN boutique_id INTEGER NOT NULL DEFAULT 1;")
        except sqlite3.OperationalError:
            pass  # La colonne existe déjà
        
        # Réactiver les contraintes de clés étrangères
        cursor.execute("PRAGMA foreign_keys=ON;")
        
        # Valider les changements
        conn.commit()
        conn.close()
        
        print("✅ Base de données corrigée avec succès!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la correction: {e}")
        return False

if __name__ == "__main__":
    success = fix_database()
    sys.exit(0 if success else 1)
