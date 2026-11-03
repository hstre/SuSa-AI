"""Kandidatensuche über mehrere Suchwege. Retrieval ist kein Urteil: jeder Kandidat trägt seine Suchwege,
Ähnlichkeitswerte, deterministische Unterschiedshinweise und den tatsächlich durchsuchten Bestand."""
from __future__ import annotations

import json
import random
import re

import numpy as np

from . import db
from .config import Config, code_version
from .embed import VectorStore, get_backend
from .segment import METHOD_VERSION

STOP = set("""a an and are as at be been but by can could did do does for from had has have he her his i if in into is it its
of on or our she so such than that the their them then there these they this those to was we were what when which who will
with would you your not no also just more most very about over only even because however other some any all one two
der die das ein eine einer eines und oder aber ist sind war waren wird werden hat haben mit von zu zum zur im in auf für
den dem des sich nicht kein keine auch als wie wenn dass da so noch nur schon bei aus nach über unter""".split())

MARKERS = {
    "negation": r"\b(not|no|never|none|nothing|cannot|can't|doesn't|don't|isn't|aren't|won't|without|nicht|kein\w*|nie|niemals|ohne|weder)\b",
    "modal": r"\b(may|might|could|can|must|should|would|possibly|perhaps|probably|kann|könnte\w*|muss|müsste\w*|soll\w*|vielleicht|wahrscheinlich|möglicherweise)\b",
    "condition": r"\b(if|unless|only if|provided|as long as|wenn|falls|sofern|nur wenn|vorausgesetzt|solange)\b",
    "scope_limit": r"\b(by itself|alone|in itself|on its own|merely|only|solely|allein|für sich genommen|an sich|bloß\w*|lediglich|nur)\b",
    "contrast": r"\b(but|however|although|yet|whereas|aber|jedoch|allerdings|dennoch|während|obwohl)\b",
    "causal": r"\b(because|since|therefore|thus|hence|so that|weil|da|deshalb|daher|folglich|denn)\b",
    "time_now": r"\b(currently|today|now|at present|current|derzeit|heute|aktuell|gegenwärtig|jetzt)\b",
    "time_future": r"\b(future|will|eventually|someday|could become|künftig|zukünftig|irgendwann|wird|werden)\b",
}
MARKER_RE = {k: re.compile(v, re.I) for k, v in MARKERS.items()}


def markers_for(text: str) -> dict[str, list[str]]:
    return {k: sorted({m.group(0).lower() for m in r.finditer(text)}) for k, r in MARKER_RE.items()}


def marker_diff(left: str, right: str) -> list[str]:
    """Heuristische Hinweise auf mögliche entscheidende Unterschiede (keine Interpretation)."""
    lm, rm = markers_for(left), markers_for(right)
    hints = []
    labels = {"negation": "Negation", "modal": "Modalität", "condition": "Bedingung", "scope_limit": "Geltungseinschränkung",
              "contrast": "Gegensatzmarker", "causal": "Begründungsmarker", "time_now": "Gegenwartsbezug", "time_future": "Zukunftsbezug"}
    for k, label in labels.items():
        if bool(lm[k]) != bool(rm[k]):
            side = "rechts" if rm[k] else "links"
            hints.append(f"{label} nur {side}: {', '.join((rm[k] or lm[k])[:4])}")
    return hints


def _fts_query(text: str, max_terms: int = 30) -> str | None:
    toks = [t.lower() for t in re.findall(r"\w{3,}", text)]
    seen, terms = set(), []
    for t in sorted(toks, key=len, reverse=True):
        if t in STOP or t in seen or t.isdigit():
            continue
        seen.add(t)
        terms.append('"' + t.replace('"', '') + '"')
        if len(terms) >= max_terms:
            break
    return " OR ".join(terms) if terms else None


def active_embedding_set(conn, prefer_real: bool = True):
    rows = conn.execute("SELECT * FROM embedding_sets ORDER BY is_test_vectors ASC, created_at DESC").fetchall()
    if not rows:
        return None
    return rows[0] if prefer_real else rows[-1]


class Searcher:
    def __init__(self, cfg: Config, conn, set_id: str | None = None):
        self.cfg, self.conn = cfg, conn
        es = conn.execute("SELECT * FROM embedding_sets WHERE id=?", (set_id,)).fetchone() if set_id else active_embedding_set(conn)
        self.eset = es
        self.store = VectorStore(cfg, es["id"]) if es else None
        self._backend = None
        self.unit_meta = {r["id"]: r for r in conn.execute(
            """SELECT u.id, u.document_id, d.author, d.date, d.is_synthetic FROM argument_units u
               JOIN documents d ON d.id=u.document_id JOIN document_versions v ON v.id=u.version_id
               WHERE v.is_current=1 AND u.method_version=?""", (METHOD_VERSION,))}

    @property
    def backend(self):
        if self._backend is None and self.eset is not None:
            self._backend = get_backend(self.cfg, self.eset["backend"])
        return self._backend

    def _allowed(self, uid: str, exclude_doc: str | None, synthetic: int | None, prefix: str | None) -> bool:
        m = self.unit_meta.get(uid)
        if m is None:
            return False
        if exclude_doc and m["document_id"] == exclude_doc:
            return False
        if synthetic is not None and m["is_synthetic"] != synthetic:
            return False
        if prefix and not m["document_id"].startswith(prefix):
            return False
        return True

    def semantic(self, vec: np.ndarray, k: int, **flt) -> list[tuple[str, float]]:
        if self.store is None or self.store.vecs is None:
            return []
        sims = self.store.vecs @ vec
        order = np.argsort(-sims)
        out = []
        for i in order:
            uid = self.store.ids[i]
            if self._allowed(uid, **flt):
                out.append((uid, float(sims[i])))
                if len(out) >= k:
                    break
        return out

    def semantic_for_unit(self, uid: str, k: int, **flt):
        if self.store is None or uid not in self.store.index:
            return []
        return self.semantic(self.store.vecs[self.store.index[uid]], k, **flt)

    def semantic_for_query(self, q: str, k: int, **flt):
        if self.backend is None:
            return []
        return self.semantic(self.backend.encode_query(q), k, **flt)

    def lexical(self, text: str, k: int, **flt) -> list[tuple[str, float]]:
        q = _fts_query(text)
        if not q:
            return []
        out = []
        for r in self.conn.execute("SELECT unit_id, bm25(units_fts) AS s FROM units_fts WHERE units_fts MATCH ? ORDER BY s LIMIT ?",
                                   (q, k * 6 + 20)):
            if self._allowed(r["unit_id"], **flt):
                out.append((r["unit_id"], float(-r["s"])))  # bm25(): kleiner = besser
                if len(out) >= k:
                    break
        return out

    def scope(self, synthetic: int | None, prefix: str | None) -> dict:
        ids = [u for u in self.unit_meta if self._allowed(u, None, synthetic, prefix)]
        docs = {self.unit_meta[u]["document_id"] for u in ids}
        return {"units_searched": len(ids), "documents_searched": len(docs), "synthetic_filter": synthetic, "prefix": prefix,
                "embedding_set": self.eset["id"] if self.eset else None,
                "embedding_is_test_vectors": bool(self.eset["is_test_vectors"]) if self.eset else None,
                "segmentation": METHOD_VERSION}


def temporal(left_date: str | None, right_date: str | None) -> str:
    if not left_date or not right_date:
        return "undated"
    if left_date == right_date:
        return "same_date"
    return "right_later" if right_date > left_date else "right_earlier"


def find_candidates(cfg: Config, conn, unit_id: str, *, prefix: str | None = None, include_random: bool = True,
                    searcher: Searcher | None = None) -> dict:
    sc = cfg.section("search")
    s = searcher or Searcher(cfg, conn)
    unit = conn.execute("SELECT u.*, d.is_synthetic, d.author, d.date FROM argument_units u JOIN documents d ON d.id=u.document_id WHERE u.id=?",
                        (unit_id,)).fetchone()
    if unit is None:
        raise KeyError(unit_id)
    flt = {"exclude_doc": unit["document_id"], "synthetic": unit["is_synthetic"], "prefix": prefix}
    sem = s.semantic_for_unit(unit_id, int(sc.get("k_semantic", 15)), **flt)
    lex = s.lexical(unit["text"], int(sc.get("k_lexical", 15)), **flt)
    merged: dict[str, dict] = {}
    for ch, hits in (("semantic", sem), ("lexical", lex)):
        for rank, (uid, score) in enumerate(hits, 1):
            m = merged.setdefault(uid, {"channels": [], "scores": {}})
            m["channels"].append(ch)
            m["scores"][ch] = {"score": round(score, 4), "rank": rank}
    # Autorendiversität: höchstens max_per_author Kandidaten je Autor (beste Rangsumme zuerst)
    per_author: dict[str, int] = {}
    ranked = sorted(merged.items(), key=lambda kv: min(v["rank"] for v in kv[1]["scores"].values()))
    kept = {}
    for uid, m in ranked:
        a = s.unit_meta[uid]["author"] or "?"
        if per_author.get(a, 0) >= int(sc.get("max_per_author", 3)):
            continue
        per_author[a] = per_author.get(a, 0) + 1
        kept[uid] = m
    if include_random:
        pool = [u for u in s.unit_meta if s._allowed(u, **flt) and u not in kept]
        rng = random.Random(f"{sc.get('seed', 0)}:{unit_id}")
        for uid in rng.sample(pool, min(int(sc.get("random_controls", 2)), len(pool))):
            kept[uid] = {"channels": ["random_control"], "scores": {}}
    run_id = db.new_run_id("search")
    scope = s.scope(unit["is_synthetic"], prefix)
    conn.execute("INSERT INTO runs(id, kind, code_version, config_json, started_at, finished_at, status, notes) VALUES(?,?,?,?,?,?,?,?)",
                 (run_id, "search", code_version(), db.dumps(sc), db.now(), db.now(), "finished", db.dumps(scope)))
    created = []
    for uid, m in kept.items():
        other = conn.execute("SELECT u.text, d.date FROM argument_units u JOIN documents d ON d.id=u.document_id WHERE u.id=?", (uid,)).fetchone()
        cid = f"cmp:{unit_id}|{uid}"
        existing = conn.execute("SELECT channels_json FROM candidate_comparisons WHERE id=?", (cid,)).fetchone()
        if existing:
            chans = sorted(set(json.loads(existing["channels_json"])) | set(m["channels"]))
            conn.execute("UPDATE candidate_comparisons SET channels_json=?, scores_json=?, search_run_id=?, corpus_scope_json=? WHERE id=?",
                         (db.dumps(chans), db.dumps(m["scores"]), run_id, db.dumps(scope), cid))
        else:
            conn.execute(
                """INSERT INTO candidate_comparisons(id, left_unit_id, right_unit_id, channels_json, scores_json, markers_json, temporal,
                   search_run_id, corpus_scope_json, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (cid, unit_id, uid, db.dumps(m["channels"]), db.dumps(m["scores"]), db.dumps(marker_diff(unit["text"], other["text"])),
                 temporal(unit["date"], other["date"]), run_id, db.dumps(scope), db.now()))
        created.append(cid)
    conn.commit()
    return {"unit_id": unit_id, "search_run_id": run_id, "scope": scope, "semantic": len(sem), "lexical": len(lex),
            "candidates": created}


def ensure_comparison(conn, left: str, right: str, channel: str = "manual_pair") -> str:
    """Explizit angelegtes Paar (z. B. für Goldstandard oder Abnahmefälle) ohne Suchlauf."""
    cid = f"cmp:{left}|{right}"
    if conn.execute("SELECT 1 FROM candidate_comparisons WHERE id=?", (cid,)).fetchone() is None:
        lt = conn.execute("SELECT u.text, d.date FROM argument_units u JOIN documents d ON d.id=u.document_id WHERE u.id=?", (left,)).fetchone()
        rt = conn.execute("SELECT u.text, d.date FROM argument_units u JOIN documents d ON d.id=u.document_id WHERE u.id=?", (right,)).fetchone()
        conn.execute(
            "INSERT INTO candidate_comparisons(id, left_unit_id, right_unit_id, channels_json, scores_json, markers_json, temporal, created_at) VALUES(?,?,?,?,?,?,?,?)",
            (cid, left, right, db.dumps([channel]), db.dumps({}), db.dumps(marker_diff(lt["text"], rt["text"])),
             temporal(lt["date"], rt["date"]), db.now()))
        conn.commit()
    return cid


def shared_sources(conn, doc_a: str, doc_b: str) -> list[str]:
    q = """SELECT DISTINCT l.target FROM links l JOIN document_versions v ON v.id=l.version_id
           WHERE v.is_current=1 AND v.document_id=?"""
    a = {r[0] for r in conn.execute(q, (doc_a,))}
    b = {r[0] for r in conn.execute(q, (doc_b,))}
    return sorted(a & b)


def source_index(conn, min_docs: int = 2, synthetic: int | None = None) -> list[dict]:
    """Welche Quellen werden von mehreren Beiträgen zitiert? Mehrfachzitate derselben Quelle sind EINE Quelle."""
    rows = conn.execute(
        """SELECT l.target, v.document_id, d.is_synthetic FROM links l JOIN document_versions v ON v.id=l.version_id
           JOIN documents d ON d.id=v.document_id WHERE v.is_current=1""").fetchall()
    by: dict[str, set] = {}
    for r in rows:
        if synthetic is not None and r["is_synthetic"] != synthetic:
            continue
        by.setdefault(r["target"], set()).add(r["document_id"])
    out = [{"target": t, "n_documents": len(ds), "documents": sorted(ds)} for t, ds in by.items() if len(ds) >= min_docs]
    return sorted(out, key=lambda x: -x["n_documents"])
