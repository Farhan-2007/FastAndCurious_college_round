"""Pick the PDF chunks most relevant to ONE claim (simple BM25 keyword ranking).

No embeddings, no vector DB, no extra dependencies. This is lexical matching: a chunk
that expresses the same fact in completely different words (e.g. "staff" vs
"employees") can be missed. Relevance is a ranking heuristic, not a guarantee, and
the LLM verifier still makes the actual judgement. Nothing is invented: every
returned record is an unmodified {"page", "text"} pair taken from the input.
"""
import math
import re

_TOKEN = re.compile(r"[a-z0-9]+(?:[.,'][a-z0-9]+)*")
_STOP = frozenset("""a an the and or but if of in on at to for from by with as is are was were be been
being it its this that these those has have had do does did not no so than then there their they he
she we you i his her our your which who whom what when where while will would can could should may
might also into over under about after before between during per via""".split())
K1, B = 1.5, 0.75


def retrieve_evidence(claim: dict, chunks: list, top_k: int = 5) -> list:
    """claim:  {"id": int, "text": str}  (only "text" is used)
    chunks: [{"page": int, "text": str}, ...] supplied by the backend
    Returns up to top_k chunks, most relevant first, each exactly
    {"page": int, "text": str} with the original page and unmodified text.
    Returns [] when nothing matches, or when claim/chunks are unusable.
    Chunks with a missing/blank text or a non-integer page are skipped."""
    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        top_k = 5
    text = claim.get("text") if isinstance(claim, dict) else None
    if top_k <= 0 or not isinstance(text, str) or not text.strip():
        return []

    docs, seen = [], set()
    for ch in chunks if isinstance(chunks, (list, tuple)) else []:
        if not isinstance(ch, dict) or not isinstance(ch.get("text"), str) or not ch["text"].strip():
            continue
        page = ch.get("page")
        if isinstance(page, bool):
            continue
        try:
            page = int(page)
        except (TypeError, ValueError):
            continue  # never invent a page number
        if (page, ch["text"]) in seen:
            continue
        seen.add((page, ch["text"]))
        docs.append((page, ch["text"], _tokens(ch["text"])))

    q_terms = set(_tokens(text))
    if not docs or not q_terms:
        return []

    n = len(docs)
    avg_len = sum(len(t) for _, _, t in docs) / n or 1.0
    df = {t: sum(1 for _, _, toks in docs if t in toks) for t in q_terms}

    scored = []
    for order, (page, raw, toks) in enumerate(docs):
        tf = {}
        for t in toks:
            if t in q_terms:
                tf[t] = tf.get(t, 0) + 1
        score = 0.0
        for t, f in tf.items():
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * len(toks) / avg_len))
        if score > 0:
            scored.append((-score, page, order, raw))
    scored.sort()  # best score first; ties -> lower page, then input order

    if not scored:
        return [
            {"page": page, "text": raw}
            for page, raw, _ in docs[:top_k]
        ]

    return [
        {"page": page, "text": raw}
        for _, page, _, raw in scored[:top_k]
    ]

def _tokens(text: str) -> list:
    out = []
    for tok in _TOKEN.findall(text.lower()):
        if tok in _STOP:
            continue
        if tok.isalpha() and len(tok) > 6:
            tok = tok[:6]  # crude stem: employees/employs/employed -> "employ"
        out.append(tok)
    return out