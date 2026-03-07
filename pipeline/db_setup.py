import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'suppliers.db')

def init_db():
    """Initialize the SQLite database with the full Challenge 1 schema."""
    # Delete old DB to start fresh with the new schema
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS suppliers (
            id TEXT PRIMARY KEY,

            -- IDENTITY
            company_name TEXT NOT NULL,
            country TEXT,
            city TEXT,
            headquarters TEXT,
            operational_hq TEXT,
            vat_number TEXT,
            founding_date TEXT,

            -- CONTACTS
            website TEXT,
            contact_email TEXT,
            phone TEXT,

            -- OFFER
            product_description TEXT,
            product_categories TEXT,
            product_keywords TEXT,
            production_capacity TEXT,

            -- OPERATIONS
            served_geographies TEXT,
            lead_time TEXT,
            moq TEXT,

            -- QUALITY & COMPLIANCE
            certifications TEXT,
            reference_standards TEXT,

            -- SIZE
            revenue INTEGER,
            revenue_currency TEXT DEFAULT 'EUR',
            employees INTEGER,

            -- SOURCE & TRACEABILITY
            source_url TEXT,
            extraction_date TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id TEXT,
            product_name TEXT,
            product_code TEXT,
            category TEXT,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        )
    ''')

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

if __name__ == "__main__":
    init_db()
