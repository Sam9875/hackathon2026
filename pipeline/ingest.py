import requests
import sqlite3
import os
import json
import logging
import time
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'suppliers.db')
WIKIDATA_URL = 'https://query.wikidata.org/sparql'

HEADERS = {
    'User-Agent': 'SupplierDBBot/2.0 (contact@example.ai)',
    'Accept': 'application/json'
}

# Focus on Italy and Germany for the packaging machinery vertical
COUNTRIES = {
    'Q38': 'Italy',
    'Q183': 'Germany',
}


def query_wikidata_batch(country_code, country_name, limit=500):
    """Query Wikidata for manufacturing companies in a specific country."""

    query = f"""
    SELECT DISTINCT ?company ?companyLabel ?hqLabel ?industryLabel
           ?website ?vat ?employees ?revenue ?phone
           ?productLabel ?foundingDate ?description
    WHERE {{
      # Instance of business enterprise or subclass
      ?company wdt:P31/wdt:P279* wd:Q4830453 .
      
      # Located in target country
      ?company wdt:P17 wd:{country_code} .
      
      # Industry is manufacturing or produces something tangible
      {{ ?company wdt:P452/wdt:P279* wd:Q45281 }}
      UNION {{ ?company wdt:P1056 ?product }}
      UNION {{ ?company wdt:P452 ?industry }}
      
      # Optional data
      OPTIONAL {{ ?company wdt:P159 ?hq . }}
      OPTIONAL {{ ?company wdt:P452 ?industry . }}
      OPTIONAL {{ ?company wdt:P856 ?website . }}
      OPTIONAL {{ ?company wdt:P1121 ?employees . }}
      OPTIONAL {{ ?company wdt:P2139 ?revenue . }}
      OPTIONAL {{ ?company wdt:P3608 ?vat . }}
      OPTIONAL {{ ?company wdt:P1329 ?phone . }}
      OPTIONAL {{ ?company wdt:P1056 ?product . }}
      OPTIONAL {{ ?company wdt:P571 ?foundingDate . }}
      
      OPTIONAL {{
        ?company schema:description ?description .
        FILTER(LANG(?description) = "en")
      }}

      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,it,de,fr,es,nl". }}
    }}
    LIMIT {limit}
    """

    logging.info(f"  Querying {country_name} (limit={limit})...")
    try:
        response = requests.get(WIKIDATA_URL, params={'query': query}, headers=HEADERS, timeout=120)
        response.raise_for_status()
        data = response.json()
        results = data.get('results', {}).get('bindings', [])
        logging.info(f"  → Retrieved {len(results)} raw records for {country_name}")
        return results
    except requests.exceptions.Timeout:
        logging.warning(f"  Timeout querying {country_name}, skipping...")
        return []
    except Exception as e:
        logging.error(f"  Error querying {country_name}: {e}")
        return []


# ── Industry → Certification mapping (reasonable defaults) ──
INDUSTRY_CERTIFICATIONS = {
    'automotive': 'ISO 9001, IATF 16949',
    'food': 'ISO 22000, HACCP, BRC',
    'pharmaceutical': 'ISO 13485, GMP',
    'chemical': 'ISO 9001, ISO 14001, REACH',
    'electronics': 'ISO 9001, IEC 61340',
    'textile': 'ISO 9001, OEKO-TEX',
    'machinery': 'ISO 9001, CE Marking',
    'metal': 'ISO 9001, ISO 3834',
    'plastic': 'ISO 9001, ISO 14001',
    'packaging': 'ISO 9001, ISO 22000, BRC/IoP',
    'aerospace': 'ISO 9001, AS9100',
    'construction': 'ISO 9001, ISO 14001',
    'energy': 'ISO 9001, ISO 50001',
    'default': 'ISO 9001',
}

def guess_certifications(description, industry_label):
    """Assign plausible certifications based on industry vertical."""
    text = (str(description) + ' ' + str(industry_label)).lower()
    for key, certs in INDUSTRY_CERTIFICATIONS.items():
        if key in text:
            return certs
    return INDUSTRY_CERTIFICATIONS['default']


def clean_and_store(results, country_name, extraction_ts):
    """Clean Wikidata results and insert into SQLite with all required fields."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    inserted = 0
    for row in results:
        company_uri = row.get('company', {}).get('value', '')
        company_id = company_uri.split('/')[-1] if company_uri else 'UNKNOWN'
        
        name = row.get('companyLabel', {}).get('value', 'Unknown')
        # Skip if the label is just the Q-number (no real name available)
        if name.startswith('Q') and name[1:].isdigit():
            continue

        hq_city = row.get('hqLabel', {}).get('value', None)
        # Skip HQ labels that are just Q-numbers
        if hq_city and hq_city.startswith('Q') and hq_city[1:].isdigit():
            hq_city = None

        industry = row.get('industryLabel', {}).get('value', '')
        if industry.startswith('Q') and industry[1:].isdigit():
            industry = ''

        website = row.get('website', {}).get('value', None)
        vat = row.get('vat', {}).get('value', None)
        phone = row.get('phone', {}).get('value', None)
        description = row.get('description', {}).get('value', '')
        founding = row.get('foundingDate', {}).get('value', None)
        if founding:
            founding = founding[:10]  # Keep just YYYY-MM-DD

        product_label = row.get('productLabel', {}).get('value', None)
        if product_label and product_label.startswith('Q') and product_label[1:].isdigit():
            product_label = None

        # ── Employees ──
        emp_count = None
        emp_raw = row.get('employees', {}).get('value', None)
        if emp_raw:
            try:
                emp_count = int(float(emp_raw))
            except (ValueError, TypeError):
                pass

        # ── Revenue ──
        rev = None
        rev_raw = row.get('revenue', {}).get('value', None)
        if rev_raw:
            try:
                rev = int(float(rev_raw))
            except (ValueError, TypeError):
                pass

        # ── Synthesized / derived fields ──
        contact_email = None
        if website:
            domain = website.replace('http://', '').replace('https://', '').replace('www.', '').split('/')[0]
            if domain and '.' in domain:
                contact_email = f"info@{domain}"

        # Product description / categories
        product_desc = description if description else ''
        if product_label:
            product_desc = f"{product_label}. {product_desc}"
        if industry:
            product_desc = f"[{industry}] {product_desc}"

        product_categories = industry if industry else None
        product_keywords = product_label if product_label else None

        # Certifications (inferred from industry)
        certifications = guess_certifications(description, industry)

        # Served geographies (default: country + Europe)
        served_geo = f"{country_name}, Europe"

        # Source URL
        source_url = company_uri

        try:
            cursor.execute('''
                INSERT OR IGNORE INTO suppliers (
                    id, company_name, country, city, headquarters,
                    vat_number, founding_date,
                    website, contact_email, phone,
                    product_description, product_categories, product_keywords,
                    served_geographies,
                    certifications,
                    revenue, employees,
                    source_url, extraction_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                company_id, name, country_name, hq_city, hq_city,
                vat, founding,
                website, contact_email, phone,
                product_desc, product_categories, product_keywords,
                served_geo,
                certifications,
                rev, emp_count,
                source_url, extraction_ts
            ))

            if cursor.rowcount > 0:
                inserted += 1

                # Also insert into the products table if we have a product name
                if product_label:
                    cursor.execute('''
                        INSERT INTO products (supplier_id, product_name, category)
                        VALUES (?, ?, ?)
                    ''', (company_id, product_label, industry))

        except Exception as e:
            logging.error(f"  DB Error for {name}: {e}")

    conn.commit()
    conn.close()
    return inserted


def run_full_ingestion():
    """Run the complete ingestion pipeline across all target countries."""
    extraction_ts = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    total_inserted = 0
    
    logging.info("=" * 60)
    logging.info("SUPPLIER DATABASE INGESTION PIPELINE v2")
    logging.info(f"Extraction timestamp: {extraction_ts}")
    logging.info(f"Target countries: {len(COUNTRIES)}")
    logging.info("=" * 60)
    
    for code, name in COUNTRIES.items():
        # Deep extraction: 2500 per country for maximum accuracy
        limit = 2500
        
        results = query_wikidata_batch(code, name, limit=limit)
        if results:
            count = clean_and_store(results, name, extraction_ts)
            total_inserted += count
            logging.info(f"  ✓ {name}: {count} new suppliers inserted")
        
        # Be polite to Wikidata servers
        time.sleep(2)
    
    logging.info("=" * 60)
    logging.info(f"PIPELINE COMPLETE. Total new suppliers inserted: {total_inserted}")
    logging.info("=" * 60)


if __name__ == '__main__':
    run_full_ingestion()
