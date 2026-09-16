"""
OMRank keyword/semantic ontology recommendation.

Ported from the OMRank project (src/query.py) so the marketplace backend can
serve the same ranking without depending on OMRank's Flask app. Reads the
same SQLite db + embeddings, copied locally into data/omrank/.
"""
import json
import math
import os
import re
import sqlite3
from functools import lru_cache
from pathlib import Path

BACKEND_ROOT = Path(__file__).parent.parent
OMRANK_DATA_DIR = Path(os.environ.get("OMRANK_DATA_DIR", str(BACKEND_ROOT / "data" / "omrank")))
OMRANK_DB_PATH = Path(os.environ.get("OMRANK_DB_PATH", str(OMRANK_DATA_DIR / "omrank.db")))

PROFILE = "proto-okn-default@1.0"

# Discovery profile weights: raise Relevance to 0.35, rescale rest to 0.65
DISCOVERY_WEIGHTS = {
    "relevance":   0.35,
    "semantic":    0.12,
    "structural":  0.04,
    "fair":        0.08,
    "interop":     0.12,
    "adoption":    0.04,
    "governance":  0.12,
    "maintenance": 0.08,
    "intl":        0.05,
}


def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(str(OMRANK_DB_PATH), check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


# ── Embedding-based query similarity ─────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_embeddings():
    """Load pre-built ontology embeddings once at startup."""
    try:
        import numpy as np
        emb = np.load(OMRANK_DATA_DIR / "onto_embeddings.npy")   # (N, 384) unit-normalised
        with open(OMRANK_DATA_DIR / "onto_index.json") as f:
            index = json.load(f)
        acr2row = {e["acronym"]: i for i, e in enumerate(index)}
        return emb, acr2row
    except Exception:
        return None, None


@lru_cache(maxsize=1)
def _get_embedding_model():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception:
        return None


def _embed_query(query: str):
    """Embed a query string using the same model as OMRank's build_embeddings.py."""
    model = _get_embedding_model()
    if model is None:
        return None
    try:
        import numpy as np
        vec = model.encode([query], normalize_embeddings=True)[0]
        return vec.astype(np.float32)
    except Exception:
        return None


@lru_cache(maxsize=256)
def _embedding_scores_for_query(query: str):
    """Return dict {acronym: cosine_similarity}. Empty dict if unavailable."""
    emb, acr2row = _load_embeddings()
    if emb is None:
        return {}
    vec = _embed_query(query)
    if vec is None:
        return {}
    scores = emb @ vec   # (N,) cosine similarities
    return {acr: float(scores[row]) for acr, row in acr2row.items()}


def semantic_mode_available() -> bool:
    """True if embeddings + sentence-transformers are both usable."""
    emb, _ = _load_embeddings()
    return emb is not None and _get_embedding_model() is not None


# ── Keyword matching ──────────────────────────────────────────────────────────

def tokenise(text: str) -> set:
    return set(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def term_match_score(query_tokens: set, text) -> float:
    if not text:
        return 0.0
    text_tokens = tokenise(text)
    hits = query_tokens & text_tokens
    return len(hits) / len(query_tokens) if query_tokens else 0.0


def label_match_score(query: str, label, synonyms_json) -> float:
    if not label:
        return 0.0
    q_lower = query.strip().lower()
    l_lower = label.strip().lower()

    if q_lower == l_lower:
        return 1.0
    if q_lower in l_lower:
        return 0.9

    if synonyms_json:
        try:
            syns = json.loads(synonyms_json)
            for syn in syns:
                if q_lower == syn.strip().lower():
                    return 0.9
                if q_lower in syn.strip().lower():
                    return 0.7
        except Exception:
            pass

    q_tokens = tokenise(query)
    return term_match_score(q_tokens, label)


def specialization_score(class_count, descendant_count) -> float:
    if class_count is None or class_count == 0:
        return 0.0
    desc = descendant_count or 0
    term1 = 0.5 * min(1.0, math.log10(1 + desc) / 4)
    term2 = 0.5 * min(1.0, desc / max(class_count, 1))
    return term1 + term2


# ── Relevance scoring per ontology ────────────────────────────────────────────

def compute_relevance(query, acronym, onto_name, onto_desc, domain_tags,
                       classes, class_count, emb_scores=None):
    """
    R = 100 x (0.40*Ctopic + 0.35*Cterm + 0.15*Spec + 0.10*ReqFit)
    Returns (R_score_0_to_100, evidence_coverage_0_to_1).
    """
    q_tokens = tokenise(query)

    tags_text = " ".join(json.loads(domain_tags) if domain_tags else [])
    c_name = term_match_score(q_tokens, " ".join(filter(None, [onto_name, acronym])))
    c_desc = term_match_score(q_tokens, " ".join(filter(None, [onto_desc, tags_text])))
    c_topic = 0.50 * c_name + 0.50 * c_desc

    if classes:
        match_scores = []
        for cls in classes:
            s = label_match_score(query, cls.get("label"), cls.get("synonyms"))
            if s > 0:
                depth = cls.get("depth") or 0
                weight = 1.0 / (1.0 + depth * 0.1)
                match_scores.append(s * weight)
        c_term_token = min(1.0, sum(sorted(match_scores, reverse=True)[:20]) / max(len(q_tokens), 1))
        c_term_evidence = 1.0
    else:
        c_term_token = term_match_score(q_tokens, " ".join(filter(None, [onto_name, onto_desc, tags_text]))) * 0.5
        c_term_evidence = 0.3

    c_emb = (emb_scores or {}).get(acronym, None)
    if c_emb is not None:
        c_emb_norm = max(0.0, c_emb)
        c_term = 0.50 * c_term_token + 0.50 * c_emb_norm
        c_term_evidence = max(c_term_evidence, 0.8)
    else:
        c_term = c_term_token

    best_cls = max(classes, key=lambda c: label_match_score(query, c.get("label"), c.get("synonyms")), default=None) if classes else None
    if best_cls:
        spec = specialization_score(class_count, best_cls.get("descendant_count"))
        spec_evidence = 1.0
    else:
        spec = 0.5
        spec_evidence = 0.0

    req_fit = None
    req_evidence = 0.0

    indicators = {
        "topic":    (c_topic,         0.40, 0.7),
        "term":     (c_term,          0.35, c_term_evidence),
        "spec":     (spec,            0.15, spec_evidence),
        "req_fit":  (req_fit,         0.10, req_evidence),
    }

    total_w = sum(w for _, w, _ in indicators.values())
    obs_w = sum(w for v, w, _ in indicators.values() if v is not None)
    cov = sum(w * e for v, w, e in indicators.values() if v is not None) / total_w

    if obs_w == 0:
        mj = 0.5
    else:
        mj = sum(v * w for v, w, _ in indicators.values() if v is not None) / obs_w

    r_score = 100.0 * (cov * mj + (1 - cov) * 0.5)
    return round(r_score, 2), round(cov, 4)


SOURCE_LABEL = {"owl+metadata": "OWL Parsed", "metadata_only": "Metadata Only", "no_file": "No File"}


def search(query: str, top_n: int = 20, profile: str = PROFILE, mode: str = "keyword") -> list:
    """
    mode: "keyword" - token-only Cterm (fast, exact match)
          "semantic" - blend token + embedding cosine in Cterm
    """
    con = get_db()

    rows = con.execute(
        """SELECT v.id AS version_id, v.acronym, v.release_date,
                  o.name, o.description, o.domain_tags,
                  s.class_count,
                  d.dim_semantic, d.dim_structural, d.dim_fair, d.dim_interop,
                  d.dim_adoption, d.dim_governance, d.dim_maintenance, d.dim_intl,
                  d.conf_semantic, d.conf_structural, d.conf_fair, d.conf_interop,
                  d.conf_adoption, d.conf_governance, d.conf_maintenance, d.conf_intl,
                  d.omrank_score, d.confidence, d.tier, d.data_source
           FROM ontology_version v
           JOIN ontology o ON o.acronym = v.acronym
           LEFT JOIN owl_stats s ON s.version_id = v.id
           LEFT JOIN dimension_score d ON d.version_id = v.id AND d.profile = ?
           WHERE v.is_latest = 1""",
        (profile,),
    ).fetchall()

    emb_scores = _embedding_scores_for_query(query) if mode == "semantic" else {}

    results = []
    for row in rows:
        vid = row["version_id"]
        acronym = row["acronym"]

        classes = con.execute(
            """SELECT label, synonyms, depth, descendant_count
               FROM ontology_class WHERE version_id=?
               ORDER BY depth ASC, descendant_count DESC
               LIMIT 5000""",
            (vid,),
        ).fetchall()
        classes = [dict(c) for c in classes]

        r_score, r_conf = compute_relevance(
            query, acronym, row["name"], row["description"], row["domain_tags"],
            classes, row["class_count"] or 0, emb_scores=emb_scores,
        )

        dim_scores = {
            "relevance":   r_score,
            "semantic":    row["dim_semantic"]    or 50.0,
            "structural":  row["dim_structural"]  or 50.0,
            "fair":        row["dim_fair"]        or 50.0,
            "interop":     row["dim_interop"]     or 50.0,
            "adoption":    row["dim_adoption"]    or 50.0,
            "governance":  row["dim_governance"]  or 50.0,
            "maintenance": row["dim_maintenance"] or 50.0,
            "intl":        row["dim_intl"]        or 50.0,
        }
        dim_confs = {
            "relevance":   r_conf,
            "semantic":    row["conf_semantic"]    or 0.0,
            "structural":  row["conf_structural"]  or 0.0,
            "fair":        row["conf_fair"]        or 0.0,
            "interop":     row["conf_interop"]     or 0.0,
            "adoption":    row["conf_adoption"]    or 0.0,
            "governance":  row["conf_governance"]  or 0.0,
            "maintenance": row["conf_maintenance"] or 0.0,
            "intl":        row["conf_intl"]        or 0.0,
        }

        final_score = sum(DISCOVERY_WEIGHTS[d] * dim_scores[d] for d in DISCOVERY_WEIGHTS)
        final_conf = sum(DISCOVERY_WEIGHTS[d] * dim_confs[d] for d in DISCOVERY_WEIGHTS)

        data_source = row["data_source"] or "no_file"
        results.append({
            "acronym":      acronym,
            "name":         row["name"] or acronym,
            "score":        round(final_score, 2),
            "confidence":   round(final_conf, 4),
            "tier":         row["tier"] or "EvidencePending",
            "relevance":    r_score,
            "semantic":     dim_scores["semantic"],
            "structural":   dim_scores["structural"],
            "fair":         dim_scores["fair"],
            "interop":      dim_scores["interop"],
            "adoption":     dim_scores["adoption"],
            "governance":   dim_scores["governance"],
            "maintenance":  dim_scores["maintenance"],
            "intl":         dim_scores["intl"],
            "class_count":  row["class_count"] or 0,
            "data_source":  data_source,
            "source_label": SOURCE_LABEL.get(data_source, "Unknown"),
        })

    con.close()
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]


@lru_cache(maxsize=1)
def _load_similarity_data():
    """Load embeddings + index + domain-tag profiles once, for find_similar()."""
    try:
        import numpy as np
        emb = np.load(OMRANK_DATA_DIR / "onto_embeddings.npy")
        with open(OMRANK_DATA_DIR / "onto_index.json") as f:
            index = json.load(f)
        with open(OMRANK_DATA_DIR / "onto_profiles.json") as f:
            profiles = json.load(f)
        acr2row = {e["acronym"]: i for i, e in enumerate(index)}
        return emb, index, profiles, acr2row
    except Exception:
        return None, None, None, None


def _jaccard(a: list, b: list) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def find_similar(acronym: str, top_n: int = 20) -> list:
    """
    Ontologies most similar to `acronym`, blending embedding cosine similarity
    (60%) with domain-tag Jaccard overlap (40%). Ported from OMRank's
    src/similar.py so the marketplace can offer the same "Find similar" feature.
    """
    embeddings, index, profiles, acr2row = _load_similarity_data()
    if embeddings is None:
        return []

    acronym = acronym.upper()
    if acronym not in acr2row:
        return []

    t_row = acr2row[acronym]
    t_vec = embeddings[t_row]
    t_tags = profiles.get(acronym, {}).get("tags", [])

    cos_scores = embeddings @ t_vec

    results = []
    for i, entry in enumerate(index):
        acr = entry["acronym"]
        if acr == acronym:
            continue

        sig_emb = float(cos_scores[i])
        sig_tag = _jaccard(t_tags, profiles.get(acr, {}).get("tags", []))

        other_tags = profiles.get(acr, {}).get("tags", [])
        if t_tags or other_tags:
            score = 0.60 * sig_emb + 0.40 * sig_tag
        else:
            score = sig_emb

        results.append({
            "acronym": acr,
            "name": entry["name"],
            "description": entry["description"],
            "data_source": entry["data_source"],
            "source_label": SOURCE_LABEL.get(entry["data_source"], "Unknown"),
            "omrank_score": None,
            "tier": None,
            "similarity": round(max(0.0, score) * 100, 1),
        })

    results.sort(key=lambda x: x["similarity"], reverse=True)
    top = results[:top_n]

    if top:
        con = get_db()
        placeholders = ",".join("?" * len(top))
        acrs = [r["acronym"] for r in top]
        rows = con.execute(
            f"""SELECT o.acronym, d.omrank_score, d.tier
                FROM ontology o
                JOIN ontology_version v ON v.acronym=o.acronym AND v.is_latest=1
                LEFT JOIN dimension_score d ON d.version_id=v.id AND d.profile=?
                WHERE o.acronym IN ({placeholders})""",
            [PROFILE] + acrs,
        ).fetchall()
        con.close()
        score_map = {r["acronym"]: (r["omrank_score"], r["tier"]) for r in rows}
        for r in top:
            om, tier = score_map.get(r["acronym"], (None, None))
            r["omrank_score"] = round(om, 1) if om else None
            r["tier"] = tier or "EvidencePending"

    return top


def get_domain_tags(tags_json):
    try:
        return json.loads(tags_json) if tags_json else []
    except Exception:
        return []


def get_detail(acronym: str, profile: str = PROFILE) -> dict | None:
    """
    Full detail record for a single ontology, keyed by acronym, sourced from
    the same OMRank SQLite db as search(). Mirrors OMRank's own
    /ontology/<acronym> detail page.
    """
    con = get_db()
    r = con.execute(
        """SELECT o.*, v.submission_id, v.version_iri, v.release_date, v.status,
                  v.owl_format, v.download_url, v.download_status, v.parse_status,
                  s.class_count, s.property_count, s.individual_count, s.axiom_count,
                  s.max_depth, s.avg_depth, s.has_label_count, s.has_definition_count,
                  s.has_synonym_count, s.owl_profile, s.language_tags,
                  s.external_ns_count, s.import_count,
                  d.omrank_score, d.confidence, d.tier, d.data_source,
                  d.dim_relevance, d.dim_semantic, d.dim_structural, d.dim_fair,
                  d.dim_interop, d.dim_adoption, d.dim_governance, d.dim_maintenance, d.dim_intl,
                  d.conf_semantic, d.conf_structural, d.conf_fair,
                  d.conf_interop, d.conf_adoption, d.conf_governance, d.conf_maintenance, d.conf_intl
           FROM ontology o
           JOIN ontology_version v ON v.acronym=o.acronym AND v.is_latest=1
           LEFT JOIN owl_stats s ON s.version_id=v.id
           LEFT JOIN dimension_score d ON d.version_id=v.id AND d.profile=?
           WHERE o.acronym=?""",
        (profile, acronym.upper()),
    ).fetchone()
    con.close()

    if not r:
        return None

    desc = re.sub(r"<[^>]+>", " ", r["description"] or "")
    desc = re.sub(r"\s+", " ", desc).strip()

    dims = [
        {"name": "Relevance",   "key": "relevance",   "score": r["dim_relevance"],   "conf": None,                "weight": 20, "desc": "How well this ontology matches a given query domain"},
        {"name": "Semantic",    "key": "semantic",    "score": r["dim_semantic"],    "conf": r["conf_semantic"],    "weight": 15, "desc": "Definition coverage, label quality, logical consistency"},
        {"name": "Structural",  "key": "structural",  "score": r["dim_structural"],  "conf": r["conf_structural"],  "weight": 5,  "desc": "Hierarchy depth, size fit, import reuse"},
        {"name": "FAIR",        "key": "fair",        "score": r["dim_fair"],        "conf": r["conf_fair"],        "weight": 10, "desc": "Findable, Accessible, Interoperable, Reusable metadata"},
        {"name": "Interop",     "key": "interop",     "score": r["dim_interop"],     "conf": r["conf_interop"],     "weight": 15, "desc": "External term reuse, mapping coverage, standards conformance"},
        {"name": "Adoption",    "key": "adoption",    "score": r["dim_adoption"],    "conf": r["conf_adoption"],    "weight": 5,  "desc": "Community usage: visits, downloads, project reuse"},
        {"name": "Governance",  "key": "governance",  "score": r["dim_governance"],  "conf": r["conf_governance"],  "weight": 15, "desc": "Issue tracker, responsiveness, governance process"},
        {"name": "Maintenance", "key": "maintenance", "score": r["dim_maintenance"], "conf": r["conf_maintenance"], "weight": 10, "desc": "Freshness, versioning discipline, changelog"},
        {"name": "Intl",        "key": "intl",        "score": r["dim_intl"],        "conf": r["conf_intl"],        "weight": 5,  "desc": "Multilingual labels and definitions"},
    ]
    for d in dims:
        if d["score"] is not None:
            d["score"] = round(d["score"], 1)
        if d["conf"] is not None:
            d["conf"] = round(d["conf"], 3)

    langs = []
    try:
        langs = json.loads(r["language_tags"] or "[]")
    except Exception:
        pass

    data_source = r["data_source"] or "no_file"
    return {
        "acronym": r["acronym"],
        "name": r["name"] or r["acronym"],
        "description": desc,
        "homepage": r["homepage"],
        "uri": r["uri"],
        "tags": get_domain_tags(r["domain_tags"]),
        "release_date": (r["release_date"] or "")[:10],
        "version_iri": r["version_iri"],
        "owl_format": r["owl_format"],
        "download_url": r["download_url"],
        "download_status": r["download_status"],
        "parse_status": r["parse_status"],
        "class_count": r["class_count"] or 0,
        "property_count": r["property_count"] or 0,
        "individual_count": r["individual_count"] or 0,
        "axiom_count": r["axiom_count"] or 0,
        "max_depth": r["max_depth"] or 0,
        "avg_depth": round(r["avg_depth"], 2) if r["avg_depth"] else 0,
        "has_label_count": r["has_label_count"] or 0,
        "has_definition_count": r["has_definition_count"] or 0,
        "has_synonym_count": r["has_synonym_count"] or 0,
        "owl_profile": r["owl_profile"],
        "language_tags": langs,
        "external_ns_count": r["external_ns_count"] or 0,
        "import_count": r["import_count"] or 0,
        "omrank_score": round(r["omrank_score"], 2) if r["omrank_score"] else None,
        "confidence": round(r["confidence"], 4) if r["confidence"] else None,
        "tier": r["tier"] or "EvidencePending",
        "data_source": data_source,
        "source_label": SOURCE_LABEL.get(data_source, "Unknown"),
        "dims": dims,
    }
