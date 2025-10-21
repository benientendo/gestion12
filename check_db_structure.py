#!/usr/bin/env python
"""
Script pour vérifier la structure de la base de données
"""
import sqlite3
import os

DB_PATH = "db.sqlite3"

def check_db_structure():
    """Vérifier la structure des tables"""
    
    if not os.path.exists(DB_PATH):
        print("❌ Base de données introuvable!")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Lister toutes les tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = cursor.fetchall()
        
        print("📋 Tables dans la base de données:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Vérifier la structure de la table boutique
        if any('boutique' in table[0].lower() for table in tables):
            print("\n🏪 Structure de la table inventory_boutique:")
            cursor.execute("PRAGMA table_info(inventory_boutique);")
            columns = cursor.fetchall()
            
            for col in columns:
                print(f"  - {col[1]} ({col[2]}) {'NOT NULL' if col[3] else 'NULL'}")
        
        # Vérifier la structure de la table commercant
        if any('commercant' in table[0].lower() for table in tables):
            print("\n👤 Structure de la table inventory_commercant:")
            cursor.execute("PRAGMA table_info(inventory_commercant);")
            columns = cursor.fetchall()
            
            for col in columns:
                print(f"  - {col[1]} ({col[2]}) {'NOT NULL' if col[3] else 'NULL'}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

if __name__ == "__main__":
    check_db_structure()
