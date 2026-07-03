"""RAG (Retrieval Augmented Generation) + Keyword-Analyse.

Strategie:
- Der Lebenslauf wird in Chunks zerlegt.
- Wenn ein OpenAI-Key vorhanden ist, werden echte Embeddings berechnet.
- Andernfalls fällt das System automatisch auf TF-IDF (pure Python, offline) zurück.
- Beim Generieren werden die für die Stellenbeschreibung relevantesten Chunks
  abgerufen und dynamisch in den Prompt injiziert (Dynamic Context Injection).
"""

import json
import math
import re
from collections import Counter
from typing import List, Optional

from .config import get_settings

settings = get_settings()

# Slash NICHT erlaubt -> "m/w/d" / "eine/n" zerfallen in einzelne Tokens.
_WORD_RE = re.compile(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß0-9+#.-]*")

# Häufige Stoppwörter (DE + EN) + Stellenanzeigen-Floskeln,
# damit die Keyword-/ATS-Analyse nur sinnvolle Begriffe zeigt.
_STOPWORDS = set(
    """
    der die das und oder aber mit für von zu im in den dem des ein eine einen einem einer
    ist sind war waren sein wird werden auf als auch nach bei aus an am vom zum zur durch
    über unter wir sie ihr ich du er es man sich dass weil wenn dann noch nur sehr mehr
    deine deinem deiner dein eng sowie bzw etc plus pluspunkt idealerweise wünschenswert
    zusammen gemeinsam jeweils sowohl ausserdem außerdem zudem dabei hierbei darüber
    suchen suchst gesucht bieten bietest fuehrst führst arbeitest optimierst übernimmst
    kleines kleine kleiner großes große fundierter fundierte fundiertes fundiert
    modernen moderne modernes erfahrung erfahrungen kenntnisse kenntnis aufgaben profil
    the a an and or but with for of to in on at as by from is are was were be been being
    this that these those you your we our they their it its he she his her i me my will shall
    can could should would have has had do does did not no yes new used using use within across
    you'll your role responsibilities requirements nice strong good experience experiences
    """.split()
)

# Kurze, aber echte Fachbegriffe, die trotz Kürze als Keyword zählen.
_TECH_SHORT = {
    "sql", "git", "api", "css", "html", "php", "aws", "gcp", "ci", "cd", "qa", "ux",
    "ui", "seo", "c++", "c#", "go", "erp", "crm", "kfz", "haccp", "ihk", "sap", "tüv",
    "b2b", "b2c", "hr", "ki", "ml", "ai", "vr", "ar", "saas", "rest", "npm",
}

# Generische Stellenanzeigen-Wörter, die KEINE echten Keywords sind.
_GENERIC = set(
    """
    stelle stellen position mitarbeiter mitarbeiterin mitarbeitende kollegen kolleginnen
    team teams kunde kunden kundinnen unternehmen firma bereich abteilung standort
    aufgabe aufgaben anforderung anforderungen voraussetzung voraussetzungen umfeld
    rahmen monat monate jahr jahre woche tag tage zeit gehören gehört bringst bietest
    freuen freust abgeschlossene abgeschlossenes erfolgreich gerne ideale idealer
    umgang chance chancen möglichkeit möglichkeiten weiterbildung vollzeit teilzeit
    festanstellung einsatz einstieg beginn person personen bewerbung bewerber
    """.split()
)


def _is_tech_token(low: str) -> bool:
    return low in _TECH_SHORT or "+" in low or "#" in low or any(c.isdigit() for c in low)


def tokenize(text: str) -> List[str]:
    out: List[str] = []
    for w in _WORD_RE.findall(text or ""):
        w = w.strip(".-+#").lower()  # Satzzeichen am Rand entfernen
        if w:
            out.append(w)
    return out


# ──────────────────────────────────────────────────────────────────────────
# Chunking
# ──────────────────────────────────────────────────────────────────────────
def chunk_text(
    text: str,
    chunk_size: Optional[int] = None,
    overlap: Optional[int] = None,
) -> List[str]:
    chunk_size = chunk_size or settings.rag_chunk_size
    overlap = overlap or settings.rag_chunk_overlap

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 1 <= chunk_size:
            current = (current + "\n" + para).strip()
            continue
        if current:
            chunks.append(current)
        if len(para) <= chunk_size:
            current = para
        else:
            step = max(1, chunk_size - overlap)
            for i in range(0, len(para), step):
                chunks.append(para[i : i + chunk_size])
            current = ""

    if current:
        chunks.append(current)
    return chunks or [text[:chunk_size]]


# ──────────────────────────────────────────────────────────────────────────
# Index aufbauen (Embeddings, sonst TF-IDF)
# ──────────────────────────────────────────────────────────────────────────
def build_index(text: str, openai_key: Optional[str] = None) -> dict:
    chunks = chunk_text(text)
    embeddings = None
    key = (openai_key or "").strip() or settings.openai_api_key
    if key:
        try:
            from .llm.openai_provider import OpenAIProvider

            embeddings = OpenAIProvider(api_key=key).embed(chunks)
        except Exception:
            embeddings = None  # robuster Fallback auf TF-IDF
    return {"chunks": chunks, "embeddings": embeddings}


def index_mode(index: dict) -> str:
    return "embeddings" if index.get("embeddings") else "tfidf"


# ──────────────────────────────────────────────────────────────────────────
# Retrieval
# ──────────────────────────────────────────────────────────────────────────
def retrieve(
    index: dict,
    query: str,
    top_k: Optional[int] = None,
    openai_key: Optional[str] = None,
) -> List[str]:
    top_k = top_k or settings.rag_top_k
    chunks: List[str] = index.get("chunks", [])
    if not chunks:
        return []

    embeddings = index.get("embeddings")
    key = (openai_key or "").strip() or settings.openai_api_key
    if embeddings and key:
        try:
            from .llm.openai_provider import OpenAIProvider

            query_vec = OpenAIProvider(api_key=key).embed([query])[0]
            scored = [
                (_cosine(query_vec, emb), chunk)
                for chunk, emb in zip(chunks, embeddings)
            ]
            scored.sort(key=lambda x: x[0], reverse=True)
            return [c for _, c in scored[:top_k]]
        except Exception:
            pass  # fällt unten auf TF-IDF zurück

    return _tfidf_retrieve(chunks, query, top_k)


def _tfidf_retrieve(chunks: List[str], query: str, top_k: int) -> List[str]:
    docs_tokens = [tokenize(c) for c in chunks]
    df: Counter = Counter()
    for toks in docs_tokens:
        for t in set(toks):
            df[t] += 1
    n_docs = len(chunks)
    idf = {t: math.log((n_docs + 1) / (c + 1)) + 1 for t, c in df.items()}

    def vec(tokens: List[str]) -> dict:
        if not tokens:
            return {}
        tf = Counter(tokens)
        length = len(tokens)
        return {t: (tf[t] / length) * idf.get(t, 0.0) for t in tf}

    doc_vecs = [vec(toks) for toks in docs_tokens]
    q_vec = vec(tokenize(query))
    scored = [(_sparse_cosine(q_vec, dv), chunks[i]) for i, dv in enumerate(doc_vecs)]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


# ──────────────────────────────────────────────────────────────────────────
# Use-Case-spezifische Keyword-/ATS-Analyse
# ──────────────────────────────────────────────────────────────────────────
def extract_keywords(job_description: str, limit: int = 12) -> List[str]:
    """Die wichtigsten, aussagekräftigen Begriffe der Stellenanzeige.

    Bevorzugt echte Fach-/Kompetenzbegriffe statt Füllwörter. Signale:
    im Original großgeschrieben (DE-Nomen/Skill), Fachbegriff, Wortlänge.
    """
    scores: dict = {}
    for tok in _WORD_RE.findall(job_description or ""):
        low = tok.strip(".-+#").lower()
        if not low or low in _STOPWORDS or low in _GENERIC:
            continue
        tech = _is_tech_token(low)
        if len(low) < 4 and not tech:  # kurze Wörter nur, wenn Fachbegriff
            continue
        score = 1.0
        if tok[:1].isupper():           # großgeschrieben -> meist Nomen/Skill
            score += 1.5
        if tech:                        # Technologie/Zertifikat
            score += 1.5
        score += min(len(low), 12) / 12.0  # längere Begriffe leicht bevorzugen
        scores[low] = scores.get(low, 0.0) + score

    ranked = sorted(scores, key=lambda k: scores[k], reverse=True)
    result: List[str] = []
    for low in ranked:
        # Zusammengesetzte Dubletten vermeiden ("haccp" vs "haccp-standards").
        hit = next((i for i, a in enumerate(result) if a in low or low in a), None)
        if hit is None:
            result.append(low)
        elif len(low) < len(result[hit]):
            result[hit] = low  # kürzeren Kernbegriff bevorzugen (matcht besser)
    return result[:limit]


def analyze(job_description: str, cv_text: str) -> dict:
    """Vergleicht den generierten Lebenslauf mit der Stellenanzeige (ATS-Stil)."""
    keywords = extract_keywords(job_description)
    cv_tokens = set(tokenize(cv_text))
    matched = [k for k in keywords if k in cv_tokens]
    missing = [k for k in keywords if k not in cv_tokens]
    score = round(100 * len(matched) / len(keywords), 1) if keywords else 0.0
    return {
        "ats_score": score,
        "matched_keywords": matched,
        "missing_keywords": missing,
    }


# ──────────────────────────────────────────────────────────────────────────
# Helfer
# ──────────────────────────────────────────────────────────────────────────
def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _sparse_cosine(a: dict, b: dict) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def dumps(index: dict) -> str:
    return json.dumps(index, ensure_ascii=False)


def loads(raw: Optional[str]) -> dict:
    if not raw:
        return {"chunks": [], "embeddings": None}
    return json.loads(raw)
