"""
enrich.py — Second-pass enrichment for the supplier database.

This script:
1. Reads suppliers with websites from the database
2. Attempts to fetch meta descriptions from their homepages
3. Updates product_description with richer content
4. Fills in missing product_keywords from meta tags
"""

import sqlite3
import os
import re
import logging
import requests
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'suppliers.db')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html',
}


def extract_meta(html: str) -> dict:
    """Extract title and meta description from raw HTML."""
    result = {}

    # Title
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if title_match:
        result['title'] = title_match.group(1).strip()[:500]

    # Meta description
    desc_match = re.search(
        r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']',
        html, re.IGNORECASE | re.DOTALL
    )
    if not desc_match:
        desc_match = re.search(
            r'<meta[^>]*content=["\'](.*?)["\'][^>]*name=["\']description["\']',
            html, re.IGNORECASE | re.DOTALL
        )
    if desc_match:
        result['description'] = desc_match.group(1).strip()[:1000]

    # Meta keywords
    kw_match = re.search(
        r'<meta[^>]*name=["\']keywords["\'][^>]*content=["\'](.*?)["\']',
        html, re.IGNORECASE | re.DOTALL
    )
    if not kw_match:
        kw_match = re.search(
            r'<meta[^>]*content=["\'](.*?)["\'][^>]*name=["\']keywords["\']',
            html, re.IGNORECASE | re.DOTALL
        )
    if kw_match:
        result['keywords'] = kw_match.group(1).strip()[:500]

    return result


def enrich_suppliers(max_enrich=200):
    """Enrich up to max_enrich suppliers that have websites."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, website, product_description, product_keywords
        FROM suppliers
        WHERE website IS NOT NULL AND website != ''
        ORDER BY RANDOM()
        LIMIT ?
    """, (max_enrich,))

    rows = cursor.fetchall()
    logging.info(f"Enrichment pass: processing {len(rows)} suppliers with websites...")

    enriched = 0
    for row in rows:
        sid = row['id']
        url = row['website']
        
        try:
            resp = requests.get(url, headers=HEADERS, timeout=5, allow_redirects=True)
            if resp.status_code != 200:
                continue

            meta = extract_meta(resp.text[:50000])  # Only parse first 50KB
            
            updates = {}
            
            if 'description' in meta:
                existing = row['product_description'] or ''
                if len(meta['description']) > len(existing):
                    updates['product_description'] = f"{meta['description']}. {existing}"
            
            if 'keywords' in meta and not row['product_keywords']:
                updates['product_keywords'] = meta['keywords']

            if updates:
                set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
                values = list(updates.values()) + [sid]
                cursor.execute(f"UPDATE suppliers SET {set_clause} WHERE id = ?", values)
                enriched += 1

        except Exception:
            continue  # Skip failed enrichments silently

    conn.commit()
    conn.close()
    logging.info(f"Enrichment complete. Updated {enriched} suppliers with richer descriptions.")


if __name__ == '__main__':
    enrich_suppliers(max_enrich=200)
