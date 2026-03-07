import sqlite3
import os
import json
import logging
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'suppliers.db')
INDEX_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'suppliers.faiss')
ID_MAP_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'id_map.json')

MODEL_NAME = 'all-MiniLM-L6-v2'

def create_embeddings():
    logging.info(f"Loading SentenceTransformer model '{MODEL_NAME}'...")
    model = SentenceTransformer(MODEL_NAME)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Embed company name + product description + categories for rich semantic matching
    cursor.execute("SELECT id, company_name, product_description, product_categories, product_keywords FROM suppliers")
    rows = cursor.fetchall()
    
    if not rows:
        logging.warning("No suppliers found in database. Run ingest.py first.")
        return
        
    texts = []
    supplier_ids = []
    
    for row in rows:
        supplier_id, name, desc, cats, keywords = row
        desc = desc if desc else ""
        cats = cats if cats else ""
        keywords = keywords if keywords else ""
        text_to_embed = f"{name}. {desc} Categories: {cats}. Keywords: {keywords}"
        texts.append(text_to_embed)
        supplier_ids.append(supplier_id)
        
    logging.info(f"Generating embeddings for {len(texts)} suppliers...")
    embeddings = model.encode(texts, show_progress_bar=True)
    embeddings = np.array(embeddings).astype('float32')
    
    dimension = embeddings.shape[1]
    
    # Create FAISS Index (L2 distance)
    logging.info("Building FAISS index...")
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    
    # Save the index to disk
    faiss.write_index(index, INDEX_PATH)
    logging.info(f"Saved FAISS index to {INDEX_PATH}")
    
    # Save the mapping from FAISS index ID (integer) to Supplier ID (string)
    # FAISS row index corresponds exactly to the array index
    mapping = {str(i): sid for i, sid in enumerate(supplier_ids)}
    with open(ID_MAP_PATH, 'w') as f:
        json.dump(mapping, f)
        
    logging.info(f"Saved ID mapping to {ID_MAP_PATH}")
    
    conn.close()

if __name__ == '__main__':
    create_embeddings()
