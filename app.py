import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from search.engine import SearchEngine

st.set_page_config(
    page_title="Supplier Intelligence Engine",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Premium CSS ──
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .main-header {
        font-size: 2.8rem; font-weight: 800;
        background: linear-gradient(135deg, #FF6B6B, #4ECDC4, #45B7D1);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0; letter-spacing: -1px;
    }
    .sub-header { font-size: 1.1rem; color: #8b949e; margin-bottom: 30px; font-weight: 300; }
    .filter-banner {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border: 1px solid #30363d; border-radius: 12px;
        padding: 14px 20px; margin: 12px 0 20px 0;
        color: #e6edf3; font-size: 0.92rem;
    }
    .filter-banner .filter-tag {
        background: #21262d; border: 1px solid #30363d;
        border-radius: 6px; padding: 4px 10px; margin: 3px 4px;
        display: inline-block; font-size: 0.85rem;
    }
    .relevance-badge {
        display: inline-block; padding: 3px 10px;
        border-radius: 12px; font-weight: 700; font-size: 0.8rem;
        color: white;
    }
    .rel-high { background: linear-gradient(135deg, #10b981, #059669); }
    .rel-mid  { background: linear-gradient(135deg, #f59e0b, #d97706); }
    .rel-low  { background: linear-gradient(135deg, #ef4444, #dc2626); }
    .match-semantic {
        display: inline-block; padding: 2px 8px; border-radius: 8px;
        font-size: 0.75rem; font-weight: 600;
        background: #2d1b69; color: #a78bfa; border: 1px solid #4c3399;
        margin-left: 6px;
    }
    .match-keyword {
        display: inline-block; padding: 2px 8px; border-radius: 8px;
        font-size: 0.75rem; font-weight: 600;
        background: #1b3a4b; color: #67e8f9; border: 1px solid #164e63;
        margin-left: 6px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_engine():
    return SearchEngine()

engine = get_engine()

# ── Header ──
st.markdown('<div class="main-header">Supplier Intelligence</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI-powered supplier discovery · Natural language search with semantic matching across European manufacturing</div>', unsafe_allow_html=True)

# ── Stats ──
try:
    stats = engine.get_db_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Suppliers", f"{stats['total']:,}")
    c2.metric("Countries", len(stats['countries']))
    c3.metric("With Website", f"{stats['with_website']:,}")
    c4.metric("With Certifications", f"{stats['with_certs']:,}")
except Exception:
    pass

st.divider()

# ── Search ──
query = st.text_input(
    "Search query",
    placeholder="e.g. Find manufacturing companies in Italy, with revenue above 30 million euros, that produce packaging machinery",
    help="Supports: product, geography, certification, size — also works semantically by meaning.",
    label_visibility="collapsed"
)

col_btn, col_info = st.columns([1, 4])
with col_btn:
    search_btn = st.button("🚀 Search", type="primary", use_container_width=True)
with col_info:
    st.caption("🧠 Semantic search (matches by meaning) + 🔑 Keyword filters (exact field matches)")

if search_btn and query:
    with st.spinner("Analyzing query and searching vector space..."):
        try:
            response = engine.search(query, top_k=25)

            if isinstance(response, dict) and "error" in response:
                st.error(f"⚠️ {response['error']}")
            elif isinstance(response, dict):
                results = response.get('results', [])
                parsed = response.get('parsed', [])
                filters = response.get('filters', {})
                total_candidates = response.get('total_candidates', 0)
                after_filters = response.get('after_filters', 0)

                # ── Parsed Filters Banner ──
                if parsed:
                    tags_html = ''.join(f'<span class="filter-tag">{p}</span>' for p in parsed)
                    st.markdown(f"""
                    <div class="filter-banner">
                        <strong>🧠 Query understood as:</strong><br>
                        {tags_html}
                        <br><small style="color:#8b949e; margin-top:6px; display:block;">
                            Scanned {total_candidates:,} semantic candidates → {after_filters:,} matched filters → showing top {len(results)}
                        </small>
                    </div>
                    """, unsafe_allow_html=True)

                if not results:
                    st.warning("No suppliers found matching your criteria. Try broadening your search.")
                else:
                    # Semantic fallback notice
                    if response.get('semantic_fallback'):
                        st.info("🧠 **Semantic mode**: No exact keyword matches found for the product terms — results are ranked purely by AI semantic similarity.")

                    st.success(f"✅ Found **{len(results)}** matching suppliers, ordered by relevance")

                    # CSV export
                    df = pd.DataFrame(results)
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 Download Results as CSV",
                        csv, "supplier_results.csv", "text/csv"
                    )

                    # ── Render each supplier as a card ──
                    for i, res in enumerate(results):
                        with st.container(border=True):
                            # ── Title row with relevance badge + match type ──
                            score = res.get('relevance_score', 0)
                            if score >= 70:
                                badge_class = 'rel-high'
                            elif score >= 40:
                                badge_class = 'rel-mid'
                            else:
                                badge_class = 'rel-low'

                            match_type = res.get('match_type', 'semantic')
                            if match_type == 'keyword':
                                match_html = '<span class="match-keyword">🔑 Keyword match</span>'
                            else:
                                match_html = '<span class="match-semantic">🧠 Semantic match</span>'

                            st.markdown(f"""
                                <span class="relevance-badge {badge_class}">{score}% relevant</span>
                                {match_html}
                            """, unsafe_allow_html=True)

                            st.subheader(f"#{i+1} · {res['company_name']}")

                            # ── IDENTITY ──
                            st.caption("🆔 IDENTITY")
                            id_cols = st.columns(4)
                            city = res.get('city') or res.get('headquarters') or ''
                            location = f"{city}, {res['country']}" if city else (res.get('country') or 'N/A')
                            id_cols[0].markdown(f"**📍 Location:** {location}")
                            id_cols[1].markdown(f"**🏛️ HQ:** {res.get('headquarters') or 'N/A'}")
                            id_cols[2].markdown(f"**🆔 VAT:** {res.get('vat_number') or 'N/A'}")
                            id_cols[3].markdown(f"**📅 Founded:** {res.get('founding_date') or 'N/A'}")

                            # ── CONTACTS ──
                            st.caption("📞 CONTACTS")
                            ct_cols = st.columns(3)
                            website = res.get('website')
                            ct_cols[0].markdown(f"**🌐 Website:** [{website}]({website})" if website else "**🌐 Website:** N/A")
                            ct_cols[1].markdown(f"**✉️ Email:** {res.get('contact_email') or 'N/A'}")
                            ct_cols[2].markdown(f"**📞 Phone:** {res.get('phone') or 'N/A'}")

                            # ── OFFER ──
                            st.caption("📦 OFFER")
                            desc = res.get('product_description') or 'N/A'
                            st.markdown(f"{desc[:400]}{'...' if len(desc) > 400 else ''}")
                            cats = res.get('product_categories') or ''
                            kw = res.get('product_keywords') or ''
                            if cats or kw:
                                tag_line = " · ".join(filter(None, [cats, kw]))
                                st.markdown(f"**Tags:** `{tag_line}`")

                            # ── OPERATIONS ──
                            st.caption("🌍 OPERATIONS")
                            op_cols = st.columns(3)
                            op_cols[0].markdown(f"**Served:** {res.get('served_geographies') or 'N/A'}")
                            op_cols[1].markdown(f"**Lead time:** {res.get('lead_time') or 'N/A'}")
                            op_cols[2].markdown(f"**MOQ:** {res.get('moq') or 'N/A'}")

                            # ── QUALITY ──
                            st.caption("🏅 QUALITY & COMPLIANCE")
                            certs = res.get('certifications') or 'N/A'
                            st.markdown(f"**Certifications:** {certs}")

                            # ── SIZE ──
                            st.caption("📊 SIZE")
                            sz_cols = st.columns(2)
                            emp = f"{res['employees']:,}" if res.get('employees') else "N/A"
                            rev = f"€{res['revenue']:,}" if res.get('revenue') else "N/A"
                            sz_cols[0].markdown(f"**👥 Employees:** {emp}")
                            sz_cols[1].markdown(f"**💰 Revenue:** {rev}")

                            # ── SOURCE ──
                            source = res.get('source_url') or ''
                            ext_date = res.get('extraction_date') or ''
                            st.caption(f"📎 Source: [{source}]({source}) · Extracted: {ext_date}")
            else:
                st.warning("No suppliers found. Try broadening your search.")

        except Exception as e:
            st.error(f"Search failed: {e}")

# ── Sidebar ──
with st.sidebar:
    st.markdown("### 🔎 Search Guide")
    st.markdown("""
    **Enter any natural language query.** The engine will:
    
    1. **Parse structured filters** from your text
    2. **Search semantically** using AI embeddings
    3. **Intersect & rank** by relevance
    
    ---
    
    **Supported filter dimensions:**
    
    🌍 **Geography**: *"in Italy"*, *"German companies"*, *"based in Milan"*
    
    💰 **Revenue**: *"revenue above 30 million"*, *"revenue below 1 billion"*
    
    👥 **Size**: *"more than 500 employees"*, *"fewer than 100 employees"*
    
    🏅 **Quality**: *"ISO 9001 certified"*, *"HACCP"*, *"IATF 16949"*
    
    🏭 **Products**: *"packaging machinery"*, *"automotive components"*, *"food processing"*
    
    ---
    
    🧠 **Semantic matching**: Even if your wording doesn't match exactly, the AI finds suppliers by *meaning*. 
    For example, searching *"bottle capping equipment"* can find suppliers tagged as *"packaging machinery"*.
    """)
    
    st.divider()
    st.markdown("### 💡 Example Queries")
    examples = [
        "Find manufacturing companies in Italy that produce packaging machinery",
        "German automotive part producers with more than 1000 employees",
        "ISO 9001 certified Italian companies with revenue above 10 million",
        "Food processing companies in Germany",
        "Companies in Milan producing plastic components",
        "Textile companies with fewer than 500 employees",
    ]
    for ex in examples:
        st.code(ex, language=None)
    
    st.divider()
    st.markdown("### 🏗️ Pipeline Info")
    st.markdown("""
    **Data Source:** Wikidata SPARQL  
    **Embeddings:** `all-MiniLM-L6-v2`  
    **Index:** FAISS (L2 distance)  
    **Storage:** SQLite  
    """)
