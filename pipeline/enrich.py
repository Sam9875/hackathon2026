"""
enrich.py — Second-pass enrichment using ScrapeGraphAI

This script:
1. Reads suppliers with websites from the SQLite database
2. Uses ScrapeGraphAI (SmartScraperGraph) to semantically parse their homepage
3. Extracts precise product offerings, industries, and certifications
4. Updates the database with this high-quality structured data
"""

import sqlite3
import os
import json
import logging
from scrapegraphai.graphs import SmartScraperGraph

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'suppliers.db')

# Ensure the user has provided their ScrapeGraph API key
SGAI_API_KEY = os.getenv("SCRAPEGRAPHAI_API_KEY")

prompt = """
Extract the following information about this manufacturing company:
1. 'main_products': A concise list of the exact products or machinery they manufacture.
2. 'industries_served': A list of industries they sell to (e.g. automotive, food, packaging).
3. 'certifications': Any ISO, IATF, HACCP or other quality standards mentioned.
4. 'contact_email': The primary contact or sales email address if found.

Return ONLY this information. If something is not found, leave it blank or omit the key.
"""

graph_config = {
    # Using the ScrapeGraphAI API provider
    "llm": {
        "api_key": SGAI_API_KEY,
        "model": "scrapegraphai/gpt-4o-mini",  # Using their hosted fast model
    },
    "verbose": False,
    "headless": True,
}

def enrich_suppliers(max_enrich=20):
    """Enrich up to max_enrich suppliers that have websites."""
    if not SGAI_API_KEY:
        logging.error("SCRAPEGRAPHAI_API_KEY environment variable is missing!")
        logging.error("Export it first: set SCRAPEGRAPHAI_API_KEY=your_key")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Pick suppliers that have a website but haven't been heavily enriched yet
    cursor.execute("""
        SELECT id, company_name, website, product_description, certifications, contact_email
        FROM suppliers
        WHERE website IS NOT NULL AND website != ''
        ORDER BY RANDOM()
        LIMIT ?
    """, (max_enrich,))

    rows = cursor.fetchall()
    logging.info(f"ScrapeGraphAI Enrichment: processing {len(rows)} suppliers...")

    enriched = 0
    for row in rows:
        sid = row['id']
        url = row['website']
        company = row['company_name']
        
        logging.info(f"🕷️ Scraping: {company} ({url})")
        
        try:
            # Create and run the ScrapeGraphAI graph
            smart_scraper = SmartScraperGraph(
                prompt=prompt,
                source=url,
                config=graph_config
            )
            
            result = smart_scraper.run()
            
            if not result:
                continue
                
            updates = {}
            
            # 1. Products & Industries -> product_description + product_categories
            prods = result.get('main_products', [])
            inds = result.get('industries_served', [])
            
            if prods:
                prod_str = ", ".join(prods) if isinstance(prods, list) else str(prods)
                updates['product_description'] = f"Manufactures: {prod_str}."
            
            if inds:
                ind_str = ", ".join(inds) if isinstance(inds, list) else str(inds)
                updates['product_categories'] = ind_str

            # 2. Certifications
            certs = result.get('certifications', [])
            if certs:
                cert_str = ", ".join(certs) if isinstance(certs, list) else str(certs)
                existing_certs = row['certifications'] or ''
                # Only update if we found new ones
                if len(cert_str) > len(existing_certs):
                    updates['certifications'] = cert_str
                    
            # 3. Email
            email = result.get('contact_email')
            if email and not row['contact_email']:
                if isinstance(email, list) and email:
                    updates['contact_email'] = email[0]
                elif isinstance(email, str):
                    updates['contact_email'] = email

            if updates:
                set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
                values = list(updates.values()) + [sid]
                cursor.execute(f"UPDATE suppliers SET {set_clause} WHERE id = ?", values)
                conn.commit()
                enriched += 1
                logging.info(f"  ✓ Extracted: {updates}")
            else:
                logging.info("  - No new data extracted.")

        except Exception as e:
            logging.error(f"  ✗ Failed to scrape {company}: {e}")
            continue

    conn.close()
    logging.info(f"Enrichment complete. Updated {enriched}/{len(rows)} suppliers.")


if __name__ == '__main__':
    # Start small to test the API credits
    enrich_suppliers(max_enrich=10)
