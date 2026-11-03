"""Kleine reale Prüfauswahl aus den Pilot-Kandidatenpaaren, ohne Modellaufrufe.

Die Auswahl folgt offen dokumentierten Suchhypothesen. Die Etiketten (Wiederholung, Erweiterung, …) beschreiben,
WARUM ein Paar ausgewählt wurde, nicht, was richtig ist. In der Blindansicht bleiben sie bis zum eigenen Urteil verborgen.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

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


def segment_ranges(text: str, u) -> dict:
    """Exakte Zeichenbereiche der angezeigten Segmente (Kontext davor, Kern, Kontext danach), ohne Randleerraum."""
    def strip(s, e):
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        return s, e
    return {"before": strip(u["ctx_start"], u["start_char"]), "core": (u["start_char"], u["end_char"]),
            "after": strip(u["end_char"], u["ctx_end"])}


# ------------------------------------------------------------------ Auswahlversionen (eingefroren)

def unit_anchor(conn, unit_id: str) -> dict:
    u = conn.execute("""SELECT u.document_id, u.start_char, u.end_char, v.text_sha256 FROM argument_units u
                        JOIN document_versions v ON v.id=u.version_id WHERE u.id=?""", (unit_id,)).fetchone()
    return {"document_id": u[0], "start_char": u[1], "end_char": u[2], "version_text_sha256": u[3]}


def items_hash(items: list[dict]) -> str:
    """Hash über Position, beide Anker, Suchhypothese und Auswahlgrund. Ändert sich ein Paar, ändert sich der Hash."""
    canon = [{"position": it["position"], "left": it["left"], "right": it["right"], "search_hypothesis": it["search_hypothesis"],
              "selection_reason": it["selection_reason"]} for it in sorted(items, key=lambda x: x["position"])]
    return db.sha256_text(json.dumps(canon, ensure_ascii=False, sort_keys=True))


def set_items(conn, sid: str) -> list[dict]:
    rows = conn.execute("""SELECT i.*, cc.left_unit_id, cc.right_unit_id FROM review_set_items i JOIN candidate_comparisons cc
                           ON cc.id=i.comparison_id WHERE set_id=? ORDER BY position""", (sid,)).fetchall()
    return [{"position": r["position"], "comparison_id": r["comparison_id"], "left": unit_anchor(conn, r["left_unit_id"]),
             "right": unit_anchor(conn, r["right_unit_id"]), "search_hypothesis": r["search_hypothesis"],
             "selection_reason": r["selection_reason"], "left_unit_id": r["left_unit_id"], "right_unit_id": r["right_unit_id"]} for r in rows]


class SetFrozen(RuntimeError):
    pass


def create_set(conn, label: str, per_hypothesis: int = 2, seed: int = 20261103, *, set_id: str | None = None,
               supersedes: str | None = None, change_reason: str | None = None) -> tuple[str, list[dict]]:
    """Neue Auswahlversion. Eine bestehende Auswahl wird nie überschrieben; ein Austausch braucht supersedes + Begründung."""
    sid = set_id or f"rs-{db.now()[:10]}-{seed}"
    if conn.execute("SELECT 1 FROM review_sets WHERE id=?", (sid,)).fetchone():
        raise SetFrozen(f"Auswahl {sid} existiert bereits und wird nicht überschrieben. Neue Version mit --set-id, --supersedes und --reason anlegen.")
    if supersedes and not change_reason:
        raise SetFrozen("Eine Nachfolgeversion braucht eine Begründung (--reason).")
    version = 1
    if supersedes:
        prev = conn.execute("SELECT version FROM review_sets WHERE id=?", (supersedes,)).fetchone()
        if prev is None:
            raise SetFrozen(f"Vorgängerversion {supersedes} unbekannt")
        version = (prev[0] or 1) + 1
    picked = select(conn, per_hypothesis, seed)
    conn.execute("INSERT INTO review_sets(id, label, method_json, created_at, version, supersedes, change_reason) VALUES(?,?,?,?,?,?,?)",
                 (sid, label, db.dumps({"seed": seed, "per_hypothesis": per_hypothesis, "hypotheses": HYPOTHESES,
                                        "hinweis": "Suchhypothesen, keine richtigen Antworten; kein Modellaufruf bei der Auswahl"}),
                  db.now(), version, supersedes, change_reason))
    for i, it in enumerate(picked, 1):
        conn.execute("INSERT INTO review_set_items(set_id, position, comparison_id, search_hypothesis, selection_reason) VALUES(?,?,?,?,?)",
                     (sid, i, it["comparison_id"], it["search_hypothesis"], it["selection_reason"]))
    conn.execute("UPDATE review_sets SET items_sha256=? WHERE id=?", (items_hash(set_items(conn, sid)), sid))
    conn.commit()
    return sid, picked


def freeze(conn, sid: str) -> str:
    """Hash einer bestehenden Auswahl festschreiben (für Auswahlen aus Version 0.2.0, die noch keinen Hash hatten)."""
    h = items_hash(set_items(conn, sid))
    cur = conn.execute("SELECT items_sha256 FROM review_sets WHERE id=?", (sid,)).fetchone()[0]
    if cur and cur != h:
        raise SetFrozen(f"Auswahl {sid} weicht vom festgeschriebenen Stand ab ({cur[:12]} ≠ {h[:12]})")
    conn.execute("UPDATE review_sets SET items_sha256=?, version=COALESCE(version, 1) WHERE id=?", (h, sid))
    conn.commit()
    return h


def resolve_unit(conn, unit_id: str, anchor: dict | None):
    """Einheit per ID oder – nach einem Neuaufbau mit anderen IDs – per Dokument, Zeichenbereich und Text-Hash finden."""
    u = conn.execute("SELECT id, text FROM argument_units WHERE id=?", (unit_id,)).fetchone()
    if anchor:
        if u is not None and conn.execute("""SELECT 1 FROM argument_units x JOIN document_versions v ON v.id=x.version_id WHERE x.id=? AND x.document_id=?
                                             AND x.start_char=? AND x.end_char=? AND v.text_sha256=?""",
                                          (unit_id, anchor["document_id"], anchor["start_char"], anchor["end_char"], anchor["version_text_sha256"])).fetchone():
            return u
        return conn.execute("""SELECT x.id, x.text FROM argument_units x JOIN document_versions v ON v.id=x.version_id WHERE x.document_id=?
                               AND x.start_char=? AND x.end_char=? AND v.text_sha256=?""",
                            (anchor["document_id"], anchor["start_char"], anchor["end_char"], anchor["version_text_sha256"])).fetchone()
    return u


def import_set(conn, data: dict) -> str:
    """Auswahl aus pilot/review_set_*.json wiederherstellen (über Anker). Existiert sie schon, muss sie identisch sein."""
    from .search import ensure_comparison
    sid = data["set_id"]
    resolved = []
    for it in data["items"]:
        lu, ru = resolve_unit(conn, "", it["left"]), resolve_unit(conn, "", it["right"])
        if lu is None or ru is None:
            raise KeyError(f"Paar {it['position']}: Einheit nicht auffindbar (Text nicht abgerufen, geändert oder anders segmentiert)")
        resolved.append((it, lu, ru))
    want = items_hash(data["items"])
    if data.get("items_sha256") and data["items_sha256"] != want:
        raise SetFrozen("Datei inkonsistent: items_sha256 passt nicht zu den Einträgen")
    existing = conn.execute("SELECT items_sha256 FROM review_sets WHERE id=?", (sid,)).fetchone()
    if existing:
        have = existing[0] or items_hash(set_items(conn, sid))
        if have != want:
            raise SetFrozen(f"Auswahl {sid} existiert mit anderem Inhalt; nicht überschrieben")
        return sid
    conn.execute("INSERT INTO review_sets(id, label, method_json, created_at, version, supersedes, change_reason, items_sha256) VALUES(?,?,?,?,?,?,?,?)",
                 (sid, data["label"], db.dumps({"seed": data.get("seed"), "imported": True, "hypotheses": HYPOTHESES}), db.now(),
                  data.get("version", 1), data.get("supersedes"), data.get("change_reason"), want))
    for it, lu, ru in resolved:
        cid = ensure_comparison(conn, lu["id"], ru["id"], "review_set_import")
        conn.execute("INSERT INTO review_set_items(set_id, position, comparison_id, search_hypothesis, selection_reason) VALUES(?,?,?,?,?)",
                     (sid, it["position"], cid, it["search_hypothesis"], it["selection_reason"]))
    conn.commit()
    return sid


def export_set_file(conn, sid: str) -> dict:
    s = conn.execute("SELECT * FROM review_sets WHERE id=?", (sid,)).fetchone()
    items = [{k: it[k] for k in ("position", "left", "right", "search_hypothesis", "selection_reason")} for it in set_items(conn, sid)]
    return {"set_id": sid, "label": s["label"], "version": s["version"] or 1, "supersedes": s["supersedes"], "change_reason": s["change_reason"],
            "seed": json.loads(s["method_json"] or "{}").get("seed"), "items_sha256": items_hash(items),
            "hinweis": "Suchhypothesen sind Auswahlgründe, keine richtigen Antworten. Vor der eigenen Blindbeurteilung nicht lesen.",
            "items": items}


# ------------------------------------------------------------------ Lesehilfen (archiviert) und Übersetzungen

def add_reading_aid(conn, unit_id: str, text: str, author: str, method: str, anchor: dict | None = None) -> None:
    u = resolve_unit(conn, unit_id, anchor)
    if u is None:
        raise KeyError(f"Einheit {unit_id} nicht auffindbar (Text geändert oder nicht abgerufen)")
    conn.execute("INSERT INTO reading_aids(unit_id, lang, text, author, method, source_text_sha256, created_at) VALUES(?,?,?,?,?,?,?)",
                 (u["id"], "de", text, author, method, db.sha256_text(u["text"]), db.now()))
    conn.commit()


def load_translations(cfg, conn, data: dict) -> dict:
    """Übersetzungen laden. Jeder Eintrag wird gegen den lokal gespeicherten Originaltext geprüft; passt der Hash nicht,
    wird er NICHT geladen, sondern als Abweichung gemeldet."""
    from .versions import read_text
    ok, mismatch = 0, []
    for e in data["entries"]:
        v = conn.execute("SELECT * FROM document_versions WHERE document_id=? AND text_sha256=?", (e["document_id"], e["version_text_sha256"])).fetchone()
        if v is None or not v["text_path"]:
            mismatch.append({**{k: e[k] for k in ("position", "side", "segment", "document_id")}, "reason": "Textversion lokal nicht vorhanden"})
            continue
        src = read_text(cfg, v)[e["start_char"]:e["end_char"]]
        if db.sha256_text(src) != e["source_sha256"]:
            mismatch.append({**{k: e[k] for k in ("position", "side", "segment", "document_id")}, "reason": "Quellsegment-Hash weicht ab"})
            continue
        conn.execute("""INSERT OR IGNORE INTO translations(translation_set, lang, document_id, version_text_sha256, start_char, end_char,
                        source_sha256, text, notes_json, method, created_by, review_status, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (data["translation_set"], data["lang"], e["document_id"], e["version_text_sha256"], e["start_char"], e["end_char"],
                      e["source_sha256"], e["de"], db.dumps(e.get("notes") or []), data["method"], data["created_by"], data["review_status"],
                      data["created_at"]))
        ok += 1
    conn.commit()
    return {"loaded_or_present": ok, "mismatch": mismatch}


def side_view(cfg, conn, unit_id: str) -> dict:
    """Alles, was für eine Seite angezeigt wird: Original-Segmente, passende Übersetzungen (nur bei identischem Hash),
    Kontextbefunde und – getrennt, erst nach dem Urteil sichtbar – Metadaten."""
    from .analysis import unit_context
    x = unit_context(cfg, conn, unit_id)
    u, text = x["unit"], x["text"]
    rng = segment_ranges(text, u)
    segs = []
    for name in ("before", "core", "after"):
        a, b = rng[name]
        src = text[a:b]
        tr = conn.execute("""SELECT * FROM translations WHERE document_id=? AND start_char=? AND end_char=? AND lang='de'
                             ORDER BY created_at DESC""", (u["document_id"], a, b)).fetchall()
        match = [t for t in tr if t["source_sha256"] == db.sha256_text(src) and t["version_text_sha256"] == u["text_sha256"]]
        segs.append({"name": name, "start": a, "end": b, "text": src, "words": len(src.split()), "source_sha256": db.sha256_text(src),
                     "translation": match[0] if match else None,
                     "translation_mismatch": bool(tr and not match)})
    findings = []
    for sg in segs:
        where = "davor" if sg["name"] == "before" else "danach"
        if sg["name"] != "core" and sg["words"] == 0:
            findings.append(f"Kein Kontext {where} (Textanfang/-ende oder im Kernabschnitt enthalten)")
        elif sg["name"] != "core" and sg["words"] < 15:
            findings.append(f"Kontext {where} nur {sg['words']} Wörter (vermutlich Überschrift)")
    if x["quoted_paragraphs"]:
        findings.append("Enthält im Original als Blockzitat formatierte Absätze")
    if not u["is_current"]:
        findings.append("Textversion ist nicht mehr die aktuelle")
    if u["availability"] != "full":
        findings.append(f"Text nicht vollständig verfügbar ({u['availability']})")
    d = conn.execute("SELECT * FROM documents WHERE id=?", (u["document_id"],)).fetchone()
    shown = " ".join(sg["text"] for sg in segs).lower()
    leaks = [label for label, val in (("Autor", d["author"]), ("Publikation", d["publication"]))
             if val and len(val) >= 4 and val.lower() in shown]
    if leaks:
        findings.append(f"Originaltext nennt {' und '.join(leaks)} (nicht ausgeblendet, um das Original nicht zu verändern)")
    codes = conn.execute("SELECT * FROM upstream_codes WHERE document_id=?", (u["document_id"],)).fetchone()
    payload = json.loads(d["upstream_payload"] or "{}")
    meta = {"title": d["title"], "author": d["author"], "publication": d["publication"], "date": d["date"], "url": d["canonical_url"],
            "reactions": payload.get("reactions"), "restacks": payload.get("restacks"),
            "upstream_axes": {k: codes[k] for k in ("experience_now", "cognition_now", "agency_now", "possible", "moral_status", "serious")} if codes else None}
    return {"unit_id": unit_id, "document_id": u["document_id"], "version_text_sha256": u["text_sha256"], "text_status": u["text_status"],
            "availability": u["availability"], "segments": segs, "findings": findings, "meta": meta,
            "source_state": {"document_id": u["document_id"], "version_text_sha256": u["text_sha256"],
                             "segments": {sg["name"]: {"start": sg["start"], "end": sg["end"], "source_sha256": sg["source_sha256"],
                                                       "translation_id": sg["translation"]["id"] if sg["translation"] else None,
                                                       "translation_set": sg["translation"]["translation_set"] if sg["translation"] else None}
                                          for sg in segs}}}


# ------------------------------------------------------------------ Blindurteile (append-only)

QUESTIONS = [
    ("q1", "Was behauptet Passage A?"),
    ("q2", "Was behauptet Passage B?"),
    ("q3", "Beantworten beide dieselbe Frage und betrachten sie dasselbe System?"),
    ("q4", "Welchen zusätzlichen Gedanken enthält eine Seite gegenüber der anderen?"),
    ("q5", "Welche Textstellen begründen meine Einschätzung?"),
    ("q6", "Fehlt Kontext oder bleibt etwas unklar?"),
]
VERDICTS = {"difference": "Eine Seite enthält einen relevanten zusätzlichen Gedanken oder Unterschied",
            "no_relevant_difference": "Kein relevanter Unterschied",
            "undecidable": "Nicht entscheidbar"}
FLAGS = {"context_missing": "Kontext reicht für ein Urteil nicht aus", "pair_unsuitable": "Paar ist für die Fragestellung ungeeignet",
         "translation_problem": "Übersetzung weicht vom Original ab oder ist missverständlich"}


def reviewer_state(conn, sid: str, pos: int, reviewer: str) -> dict:
    rows = conn.execute("SELECT * FROM blind_judgments WHERE set_id=? AND position=? AND reviewer=? ORDER BY id", (sid, pos, reviewer)).fetchall() if reviewer else []
    return {"entries": rows, "free": [r for r in rows if r["stage"] == "free"], "revealed": any(r["stage"] == "reveal" for r in rows)}


def add_blind_judgment(cfg, conn, sid: str, pos: int, reviewer: str, stage: str, *, verdict: str | None = None, answers: dict | None = None,
                       relation_types: list[str] | None = None, flags: list[str] | None = None, quotes: dict | None = None,
                       parent_id: int | None = None, origin: str = "web", source_state: dict | None = None) -> int:
    from .analysis import check_quotes, unit_context
    from .validate import RELATION_TYPES
    if not reviewer:
        raise ValueError("Prüfername fehlt")
    it = conn.execute("SELECT i.*, cc.left_unit_id, cc.right_unit_id FROM review_set_items i JOIN candidate_comparisons cc ON cc.id=i.comparison_id "
                      "WHERE set_id=? AND position=?", (sid, pos)).fetchone()
    if it is None:
        raise KeyError((sid, pos))
    st = reviewer_state(conn, sid, pos, reviewer)
    if stage == "free":
        if st["free"]:
            raise ValueError("Ein erstes freies Urteil existiert bereits; Ergänzungen und Korrekturen werden als neue Einträge gespeichert.")
        if verdict not in VERDICTS:
            raise ValueError("Gesamteinschätzung fehlt")
        answers = answers or {}
        if not any((answers.get(q) or "").strip() for q, _ in QUESTIONS):
            raise ValueError("Mindestens eine Frage frei beantworten")
    elif stage in ("labels", "amendment", "correction"):
        if not st["free"]:
            raise ValueError("Zuerst das freie Urteil speichern")
        if stage == "correction" and verdict is not None and verdict not in VERDICTS:
            raise ValueError("unzulässige Gesamteinschätzung")
        parent_id = parent_id or st["free"][0]["id"]
    elif stage == "reveal":
        if not st["free"]:
            raise ValueError("Aufdecken erst nach dem freien Urteil")
    else:
        raise ValueError(stage)
    rtypes = [t for t in (relation_types or []) if t in RELATION_TYPES]
    qc = None
    if quotes and (quotes.get("a") or quotes.get("b")):
        qc = {"a": check_quotes(conn, unit_context(cfg, conn, it["left_unit_id"]), quotes.get("a") or [], create_spans=False),
              "b": check_quotes(conn, unit_context(cfg, conn, it["right_unit_id"]), quotes.get("b") or [], create_spans=False)}
    if source_state is None:
        source_state = {"a": side_view(cfg, conn, it["left_unit_id"])["source_state"], "b": side_view(cfg, conn, it["right_unit_id"])["source_state"]}
    c = conn.execute("""INSERT INTO blind_judgments(set_id, position, comparison_id, reviewer, stage, parent_id, verdict, answers_json,
                        relation_types_json, flags_json, quote_check_json, revealed_before, source_state_json, origin, created_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (sid, pos, it["comparison_id"], reviewer, stage, parent_id, verdict, db.dumps(answers) if answers else None,
                      db.dumps(rtypes) if relation_types is not None else None, db.dumps([f for f in (flags or []) if f in FLAGS]),
                      db.dumps(qc) if qc else None, int(st["revealed"]), db.dumps(source_state), origin, db.now()))
    conn.commit()
    return c.lastrowid


def verify_set(cfg, conn, sid: str) -> list[dict]:
    """Prüft für jedes Paar: Anker auflösbar, Textversion aktuell, alle Segmente übersetzt und hash-gleich."""
    out = []
    want = conn.execute("SELECT items_sha256 FROM review_sets WHERE id=?", (sid,)).fetchone()[0]
    have = items_hash(set_items(conn, sid))
    out.append({"check": "Auswahl unverändert (items_sha256)", "ok": want == have, "detail": f"{(want or '–')[:12]} / {have[:12]}"})
    for it in set_items(conn, sid):
        for side, key in (("A", "left_unit_id"), ("B", "right_unit_id")):
            v = side_view(cfg, conn, it[key])
            missing = [s["name"] for s in v["segments"] if s["text"] and s["translation"] is None]
            mism = [s["name"] for s in v["segments"] if s["translation_mismatch"]]
            out.append({"check": f"Paar {it['position']}{side}", "ok": not missing and not mism,
                        "detail": f"ohne Übersetzung: {missing or '–'}; abweichender Hash: {mism or '–'}; Befunde: {v['findings'] or '–'}"})
    return out
