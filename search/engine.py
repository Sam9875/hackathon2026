import os
import sqlite3
import json
import faiss
import numpy as np
import re
from sentence_transformers import SentenceTransformer

MODEL_NAME = 'all-MiniLM-L6-v2'

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'suppliers.db')
INDEX_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'suppliers.faiss')
ID_MAP_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'id_map.json')

# ── Supported country name variants ──
COUNTRY_ALIASES = {
    'italy': 'Italy', 'italian': 'Italy', 'italia': 'Italy',
    'germany': 'Germany', 'german': 'Germany', 'deutschland': 'Germany',
    'france': 'France', 'french': 'France',
    'spain': 'Spain', 'spanish': 'Spain', 'españa': 'Spain',
    'netherlands': 'Netherlands', 'dutch': 'Netherlands', 'holland': 'Netherlands',
    'austria': 'Austria', 'austrian': 'Austria',
    'switzerland': 'Switzerland', 'swiss': 'Switzerland',
    'poland': 'Poland', 'polish': 'Poland',
    'belgium': 'Belgium', 'belgian': 'Belgium',
    'portugal': 'Portugal', 'portuguese': 'Portugal',
    'sweden': 'Sweden', 'swedish': 'Sweden',
    'denmark': 'Denmark', 'danish': 'Denmark',
    'finland': 'Finland', 'finnish': 'Finland',
    'norway': 'Norway', 'norwegian': 'Norway',
    'czech republic': 'Czech Republic', 'czech': 'Czech Republic',
    'hungary': 'Hungary', 'hungarian': 'Hungary',
}

# ── Known city names (subset for detection) ──
CITY_ALIASES = {
    'milan': 'Milan', 'milano': 'Milan',
    'rome': 'Rome', 'roma': 'Rome',
    'turin': 'Turin', 'torino': 'Turin',
    'bologna': 'Bologna',
    'florence': 'Florence', 'firenze': 'Florence',
    'naples': 'Naples', 'napoli': 'Naples',
    'genoa': 'Genoa', 'genova': 'Genoa',
    'venice': 'Venice', 'venezia': 'Venice',
    'berlin': 'Berlin',
    'munich': 'Munich', 'münchen': 'Munich',
    'hamburg': 'Hamburg',
    'frankfurt': 'Frankfurt',
    'stuttgart': 'Stuttgart',
    'düsseldorf': 'Düsseldorf', 'dusseldorf': 'Düsseldorf',
    'cologne': 'Cologne', 'köln': 'Cologne',
    'hannover': 'Hannover', 'hanover': 'Hannover',
}


class SearchEngine:
    def __init__(self):
        self.model = None
        self.index = None
        self.id_mapping = None

    def _load(self):
        if self.model is None:
            self.model = SentenceTransformer(MODEL_NAME)
        if self.index is None and os.path.exists(INDEX_PATH):
            self.index = faiss.read_index(INDEX_PATH)
        if self.id_mapping is None and os.path.exists(ID_MAP_PATH):
            with open(ID_MAP_PATH, 'r') as f:
                self.id_mapping = json.load(f)

    def extract_structured_filters(self, query: str):
        """
        Extract structured parameters from a natural language query.
        Returns a dict of filters AND a human-readable summary of what was parsed.
        Supports: country, city, revenue (min/max), employees (min/max),
                  certifications, and product keywords.
        """
        filters = {}
        parsed_labels = []  # Human-readable descriptions of each filter
        q_lower = query.lower()

        # ── Country ──
        for alias, canonical in COUNTRY_ALIASES.items():
            if alias in q_lower:
                filters['country'] = canonical
                parsed_labels.append(f"🌍 Country: {canonical}")
                break

        # ── City ──
        for alias, canonical in CITY_ALIASES.items():
            # Use word-boundary matching to avoid false positives
            if re.search(r'\b' + re.escape(alias) + r'\b', q_lower):
                filters['city'] = canonical
                parsed_labels.append(f"📍 City: {canonical}")
                break

        # ── Revenue (min) ──
        rev_min = re.search(
            r'revenue\s+(?:above|over|>|greater than|exceeding|minimum|at least)\s+(\d+)\s*(million|m|billion|b)',
            q_lower
        )
        if rev_min:
            amount = int(rev_min.group(1))
            unit = rev_min.group(2)
            multiplier = 1_000_000_000 if unit in ('billion', 'b') else 1_000_000
            filters['min_revenue'] = amount * multiplier
            parsed_labels.append(f"💰 Revenue ≥ €{amount}{unit[0].upper()}")

        # ── Revenue (max) ──
        rev_max = re.search(
            r'revenue\s+(?:below|under|<|less than|at most|up to)\s+(\d+)\s*(million|m|billion|b)',
            q_lower
        )
        if rev_max:
            amount = int(rev_max.group(1))
            unit = rev_max.group(2)
            multiplier = 1_000_000_000 if unit in ('billion', 'b') else 1_000_000
            filters['max_revenue'] = amount * multiplier
            parsed_labels.append(f"💰 Revenue ≤ €{amount}{unit[0].upper()}")

        # ── Employees (min) ──
        emp_min = re.search(
            r'(?:more than|over|above|>|at least|minimum)\s+(\d[\d,]*)\s*employees',
            q_lower
        )
        if emp_min:
            val = int(emp_min.group(1).replace(',', ''))
            filters['min_employees'] = val
            parsed_labels.append(f"👥 Employees ≥ {val:,}")

        emp_min2 = re.search(r'employees?\s+(?:above|over|>)\s+(\d[\d,]*)', q_lower)
        if emp_min2 and 'min_employees' not in filters:
            val = int(emp_min2.group(1).replace(',', ''))
            filters['min_employees'] = val
            parsed_labels.append(f"👥 Employees ≥ {val:,}")

        # ── Employees (max) ──
        emp_max = re.search(
            r'(?:fewer than|less than|under|below|<|at most|up to)\s+(\d[\d,]*)\s*employees',
            q_lower
        )
        if emp_max:
            val = int(emp_max.group(1).replace(',', ''))
            filters['max_employees'] = val
            parsed_labels.append(f"👥 Employees ≤ {val:,}")

        # ── Certifications ──
        cert_match = re.findall(
            r'(iso\s*\d+|iatf\s*\d+|haccp|gmp|brc|as\s*\d+|ce\s+marking|oeko[- ]?tex|reach)',
            q_lower
        )
        if cert_match:
            certs = [c.upper().replace('  ', ' ') for c in cert_match]
            filters['certifications'] = certs
            parsed_labels.append(f"🏅 Certs: {', '.join(certs)}")

        # ── Product / industry keywords ──
        # Strip out the parts already parsed (country, city, numbers, certs, filler words)
        product_query = q_lower
        # Remove known structural phrases
        removals = [
            r'find\b', r'search\s+for\b', r'show\s+me\b', r'list\b', r'get\b',
            r'manufacturing\s+companies?', r'companies?', r'suppliers?', r'producers?',
            r'firms?\b', r'businesses?\b',
            r'\bin\b', r'\bfrom\b', r'\bbased\s+in\b', r'\blocated\s+in\b',
            r'\bwith\b', r'\bthat\b', r'\bwhich\b', r'\bwho\b', r'\band\b', r'\bor\b',
            r'\bthe\b', r'\ba\b', r'\ban\b',
            r'\bproduce\b', r'\bproducing\b', r'\bmanufacture\b', r'\bmanufacturing\b',
            r'\bmake\b', r'\bmaking\b',
            r'revenue\s+\w+\s+\d+\s*\w*',
            r'(?:more|fewer|less|over|above|below|under|at\s+least|at\s+most|up\s+to|minimum)\s+(?:than\s+)?\d[\d,]*\s*employees?',
            r'employees?\s+(?:above|over|>|below|under|<)\s+\d[\d,]*',
            r'iso\s*\d+|iatf\s*\d+|haccp|gmp|brc|as\s*\d+|ce\s+marking|oeko[- ]?tex|reach',
            r'\bcertified\b', r'\bcertification\b',
        ]
        # Remove country & city aliases
        for alias in COUNTRY_ALIASES:
            removals.append(r'\b' + re.escape(alias) + r'\b')
        for alias in CITY_ALIASES:
            removals.append(r'\b' + re.escape(alias) + r'\b')

        for pattern in removals:
            product_query = re.sub(pattern, ' ', product_query)
        # Clean up whitespace
        product_query = re.sub(r'\s+', ' ', product_query).strip()
        # Remove dangling punctuation
        product_query = re.sub(r'[,.\-;:]+$', '', product_query).strip()

        if product_query and len(product_query) > 2:
            filters['product_keywords'] = product_query
            parsed_labels.append(f"🔎 Product: \"{product_query}\"")

        return filters, parsed_labels

    def _distance_to_relevance(self, distances):
        """Convert FAISS L2 distances to 0-100 relevance scores.
        Uses a sigmoid-like normalization: closer distance → higher score."""
        if len(distances) == 0:
            return []
        # L2 distances: smaller = more similar
        # Map through an exponential decay: score = 100 * exp(-distance / scale)
        distances = np.array(distances, dtype=np.float32)
        # Use median distance as the scale factor for adaptive normalization
        scale = float(np.median(distances)) if np.median(distances) > 0 else 1.0
        scores = 100.0 * np.exp(-distances / (scale * 1.5))
        return scores.tolist()

    def search(self, query: str, top_k: int = 20):
        """
        Full natural-language search pipeline:
        1. Parse structured filters from the query text
        2. Encode query into a vector and search FAISS for semantic candidates
        3. Intersect with SQL filters (country, city, revenue, employees, certs, product)
        4. Return results ordered by relevance with scores and parsed filter info
        """
        self._load()
        if not self.index or not self.id_mapping:
            return {"error": "Index not built. Run the ingestion pipeline first."}

        filters, parsed_labels = self.extract_structured_filters(query)

        # ── Semantic vector search ──
        query_vector = self.model.encode([query])
        query_vector = np.array(query_vector).astype('float32')

        # Wider fetch to give SQL filters enough candidates to work with
        fetch_k = min(top_k * 10, self.index.ntotal)
        distances, indices = self.index.search(query_vector, fetch_k)

        # Map FAISS indices → supplier IDs + distances
        supplier_ids = []
        distance_map = {}
        for i, idx in enumerate(indices[0]):
            if idx != -1:
                string_id = str(idx)
                if string_id in self.id_mapping:
                    sid = self.id_mapping[string_id]
                    supplier_ids.append(sid)
                    distance_map[sid] = float(distances[0][i])

        if not supplier_ids:
            return {"results": [], "filters": filters, "parsed": parsed_labels}

        # ── Helper: run SQL query with given filters ──
        def _run_filtered_query(include_product_kw=True):
            _conn = sqlite3.connect(DB_PATH)
            _conn.row_factory = sqlite3.Row
            _cursor = _conn.cursor()

            _placeholders = ','.join(['?'] * len(supplier_ids))
            _sql = f"SELECT * FROM suppliers WHERE id IN ({_placeholders})"
            _params = list(supplier_ids)

            if 'country' in filters:
                _sql += " AND country = ?"
                _params.append(filters['country'])

            if 'city' in filters:
                _sql += " AND (city LIKE ? OR headquarters LIKE ?)"
                _params.extend([f"%{filters['city']}%", f"%{filters['city']}%"])

            if 'min_revenue' in filters:
                _sql += " AND revenue >= ?"
                _params.append(filters['min_revenue'])

            if 'max_revenue' in filters:
                _sql += " AND revenue <= ?"
                _params.append(filters['max_revenue'])

            if 'min_employees' in filters:
                _sql += " AND employees >= ?"
                _params.append(filters['min_employees'])

            if 'max_employees' in filters:
                _sql += " AND employees <= ?"
                _params.append(filters['max_employees'])

            if 'certifications' in filters:
                for cert in filters['certifications']:
                    _sql += " AND certifications LIKE ?"
                    _params.append(f"%{cert}%")

            if include_product_kw and 'product_keywords' in filters:
                kw_parts = filters['product_keywords'].split()
                for kw in kw_parts:
                    if len(kw) > 2:
                        _sql += " AND (product_description LIKE ? OR product_categories LIKE ? OR product_keywords LIKE ?)"
                        _params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])

            _cursor.execute(_sql, _params)
            _rows = _cursor.fetchall()
            _conn.close()
            return _rows

        # ── Two-pass: try with product keywords first, fall back to semantic-only ──
        semantic_fallback = False
        rows = _run_filtered_query(include_product_kw=True)
        if not rows and 'product_keywords' in filters:
            # Product keyword filter was too strict — fall back to pure semantic ranking
            rows = _run_filtered_query(include_product_kw=False)
            semantic_fallback = True

        # ── Build results with relevance scores ──
        results = [dict(row) for row in rows]
        id_to_result = {r['id']: r for r in results}

        # Collect distances for matched results in FAISS rank order
        ordered_ids = [sid for sid in supplier_ids if sid in id_to_result]
        ordered_distances = [distance_map[sid] for sid in ordered_ids]

        # Convert distances to relevance percentages
        relevance_scores = self._distance_to_relevance(ordered_distances)

        ordered = []
        for i, sid in enumerate(ordered_ids):
            result = id_to_result[sid]
            result['relevance_score'] = round(relevance_scores[i], 1) if i < len(relevance_scores) else 0.0

            # Determine match type
            product_kw = filters.get('product_keywords', '')
            desc = (result.get('product_description') or '').lower()
            cats = (result.get('product_categories') or '').lower()
            kws = (result.get('product_keywords') or '').lower()
            combined = f"{desc} {cats} {kws}"

            if product_kw and any(word in combined for word in product_kw.split() if len(word) > 2):
                result['match_type'] = 'keyword'
            else:
                result['match_type'] = 'semantic'

            ordered.append(result)
            if len(ordered) >= top_k:
                break

        return {
            "results": ordered,
            "filters": filters,
            "parsed": parsed_labels,
            "total_candidates": len(supplier_ids),
            "after_filters": len(results),
            "semantic_fallback": semantic_fallback,
        }

    def get_db_stats(self):
        """Return database statistics for the UI."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        stats = {}
        cursor.execute("SELECT COUNT(*) FROM suppliers")
        stats['total'] = cursor.fetchone()[0]

        cursor.execute("SELECT DISTINCT country FROM suppliers WHERE country IS NOT NULL")
        stats['countries'] = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT COUNT(*) FROM suppliers WHERE website IS NOT NULL")
        stats['with_website'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM suppliers WHERE employees IS NOT NULL")
        stats['with_employees'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM suppliers WHERE certifications IS NOT NULL")
        stats['with_certs'] = cursor.fetchone()[0]

        conn.close()
        return stats


if __name__ == '__main__':
    engine = SearchEngine()
    print("Test: 'manufacturing companies in Italy producing packaging machinery'")
    res = engine.search("manufacturing companies in Italy producing packaging machinery")
    if isinstance(res, dict) and 'results' in res:
        print(f"  Parsed filters: {res['parsed']}")
        print(f"  Candidates: {res['total_candidates']} → After filters: {res['after_filters']}")
        for r in res['results'][:3]:
            print(f"  [{r['relevance_score']}%] {r['company_name']} ({r['country']}) [{r['match_type']}]")
