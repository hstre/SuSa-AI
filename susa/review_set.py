"""Kleine reale Prüfauswahl aus den Pilot-Kandidatenpaaren, ohne Modellaufrufe.

Die Auswahl folgt offen dokumentierten Suchhypothesen. Die Etiketten (Wiederholung, Erweiterung, …) beschreiben,
WARUM ein Paar ausgewählt wurde, nicht, was richtig ist. In der Blindansicht bleiben sie bis zum eigenen Urteil verborgen.
"""
from __future__ import annotations

import json
import random
import re

from . import db
from .config import Config

DEF_CUE = re.compile(r"\b(defin\w*|by [a-z]+ (?:I|we) mean|what (?:I|we) mean by|in the sense (?:of|that)|the term|strictly speaking|so-called)\b", re.I)
CONCEPTS = re.compile(r"\b(conscious\w*|sentien\w*|agency|agent\w*|understand\w*|mind\w*|think\w*|intelligen\w*|experienc\w*|feel\w*)\b", re.I)
CAUSAL = re.compile(r"\b(because|therefore|thus|hence|since|which means|so that)\b", re.I)
COND = re.compile(r"\b(if|unless|only if|provided|as long as|only|merely|by itself|alone)\b", re.I)
NEG = re.compile(r"\b(not|no|never|cannot|can't|isn't|aren't|doesn't|don't|won't)\b", re.I)
YES = {"yes", "yes_qualified"}

HYPOTHESES = {
    "wiederholung": "Suchhypothese Wiederholung: beide Suchwege, höchste semantische Ähnlichkeit",
    "erweiterung": "Suchhypothese begründete Erweiterung: hohe Ähnlichkeit, rechts später, rechts mit Begründungs- und Bedingungsmarkern",
    "definition": "Suchhypothese Definitionsunterschied: beide Seiten mit Definitionsmarker und gemeinsamem Kernbegriff",
    "widerspruch": "Suchhypothese möglicher Widerspruch: semantisch nah, gegensätzliche Upstream-Codes zu experience_now, Negation nur auf einer Seite",
    "unklar": "Suchhypothese unklarer Fall: Zufallskontrolle bzw. nur lexikalischer Treffer mittlerer Stärke",
}


def _pool(conn):
    rows = conn.execute(
        """SELECT cc.id, cc.channels_json, cc.scores_json, cc.temporal, l.text lt, r.text rt, l.document_id ld, r.document_id rd,
                  l.n_tokens ln, r.n_tokens rn, ucl.experience_now le, ucr.experience_now re
           FROM candidate_comparisons cc JOIN argument_units l ON l.id=cc.left_unit_id JOIN argument_units r ON r.id=cc.right_unit_id
           JOIN documents dl ON dl.id=l.document_id JOIN documents dr ON dr.id=r.document_id
           LEFT JOIN upstream_codes ucl ON ucl.document_id=l.document_id LEFT JOIN upstream_codes ucr ON ucr.document_id=r.document_id
           WHERE dl.is_synthetic=0 AND dr.is_synthetic=0 AND l.n_tokens>=80 AND r.n_tokens>=80""").fetchall()
    out = []
    for r in rows:
        ch = set(json.loads(r["channels_json"]))
        sc = json.loads(r["scores_json"] or "{}")
        out.append({**dict(r), "ch": ch, "sem": (sc.get("semantic") or {}).get("score"), "lex": (sc.get("lexical") or {}).get("score")})
    return out


def select(conn, per_hypothesis: int = 2, seed: int = 20261103) -> list[dict]:
    pool = _pool(conn)
    rng = random.Random(seed)
    used_docs: set[str] = set()
    chosen = []

    def take(cands, hyp, reason_fn, limit=None):
        n = 0
        limit = limit or per_hypothesis
        for c in cands:
            if c["ld"] in used_docs or c["rd"] in used_docs:
                continue
            chosen.append({"comparison_id": c["id"], "search_hypothesis": hyp, "selection_reason": reason_fn(c)})
            used_docs.update((c["ld"], c["rd"]))
            n += 1
            if n >= limit:
                break

    sem = [c for c in pool if c["sem"] is not None]
    take(sorted([c for c in sem if {"semantic", "lexical"} <= c["ch"]], key=lambda c: -c["sem"]), "wiederholung",
         lambda c: f"semantisch {c['sem']:.3f}, lexikalisch {c['lex']:.2f}")
    hi = sorted(c["sem"] for c in sem)[int(len(sem) * 0.8)] if sem else 1
    take(sorted([c for c in sem if c["sem"] >= hi and c["temporal"] == "right_later" and CAUSAL.search(c["rt"]) and COND.search(c["rt"])],
                key=lambda c: -c["sem"]), "erweiterung", lambda c: f"semantisch {c['sem']:.3f} (oberes Quintil), rechts später")
    def shared_concept(c):
        a = {m.group(0).lower()[:6] for m in CONCEPTS.finditer(c["lt"])}
        b = {m.group(0).lower()[:6] for m in CONCEPTS.finditer(c["rt"])}
        return a & b
    take(sorted([c for c in sem if DEF_CUE.search(c["lt"]) and DEF_CUE.search(c["rt"]) and shared_concept(c)], key=lambda c: -c["sem"]),
         "definition", lambda c: f"Definitionsmarker beidseitig, gemeinsamer Begriff {sorted(shared_concept(c))[:3]}, semantisch {c['sem']:.3f}")
    take(sorted([c for c in sem if ((c["le"] in YES and c["re"] == "no") or (c["le"] == "no" and c["re"] in YES))
                 and bool(NEG.search(c["lt"])) != bool(NEG.search(c["rt"]))], key=lambda c: -c["sem"]), "widerspruch",
         lambda c: f"Upstream experience_now {c['le']} / {c['re']} (historische Fremdcodes), semantisch {c['sem']:.3f}")
    if not any(x["search_hypothesis"] == "widerspruch" for x in chosen):  # Fallback ohne Negationsbedingung
        take(sorted([c for c in sem if (c["le"] in YES and c["re"] == "no") or (c["le"] == "no" and c["re"] in YES)], key=lambda c: -c["sem"]),
             "widerspruch", lambda c: f"Upstream experience_now {c['le']} / {c['re']}, semantisch {c['sem']:.3f} (ohne Negationsbedingung)")
    rnd = [c for c in pool if c["ch"] == {"random_control"}]
    rng.shuffle(rnd)
    take(rnd, "unklar", lambda c: "Zufallskontrolle", limit=max(1, per_hypothesis // 2))
    lex_only = sorted([c for c in pool if c["ch"] == {"lexical"} and c["lex"] is not None], key=lambda c: c["lex"])
    mid = lex_only[len(lex_only) // 3: 2 * len(lex_only) // 3]
    rng.shuffle(mid)
    take(mid, "unklar", lambda c: f"nur lexikalisch, BM25 {c['lex']:.2f} (mittleres Drittel)", limit=max(1, per_hypothesis - per_hypothesis // 2))
    # Reihenfolge mischen, damit die Position die Suchhypothese nicht verrät
    rng.shuffle(chosen)
    return chosen


def create_set(conn, label: str, per_hypothesis: int = 2, seed: int = 20261103) -> tuple[str, list[dict]]:
    items = select(conn, per_hypothesis, seed)
    sid = f"rs-{db.now()[:10]}-{seed}"
    conn.execute("INSERT OR REPLACE INTO review_sets(id, label, method_json, created_at) VALUES(?,?,?,?)",
                 (sid, label, db.dumps({"seed": seed, "per_hypothesis": per_hypothesis, "hypotheses": HYPOTHESES,
                                        "hinweis": "Suchhypothesen, keine richtigen Antworten; kein Modellaufruf bei der Auswahl"}), db.now()))
    conn.execute("DELETE FROM review_set_items WHERE set_id=?", (sid,))
    for i, it in enumerate(items, 1):
        conn.execute("INSERT INTO review_set_items(set_id, position, comparison_id, search_hypothesis, selection_reason) VALUES(?,?,?,?,?)",
                     (sid, i, it["comparison_id"], it["search_hypothesis"], it["selection_reason"]))
    conn.commit()
    return sid, items


def add_reading_aid(conn, unit_id: str, text: str, author: str, method: str) -> None:
    u = conn.execute("SELECT text FROM argument_units WHERE id=?", (unit_id,)).fetchone()
    conn.execute("INSERT INTO reading_aids(unit_id, lang, text, author, method, source_text_sha256, created_at) VALUES(?,?,?,?,?,?,?)",
                 (unit_id, "de", text, author, method, db.sha256_text(u["text"]), db.now()))
    conn.commit()
