"""Absatzbasierte Segmentierung in Argumentationseinheiten mit exakten Zeichenankern.

- Kerneinheiten überlappen nicht (eine Textstelle wird nicht mehrfach gezählt); der überlappende Kontext
  (vorheriger/nächster Absatz) wird als ctx_start/ctx_end gespeichert und beim Vergleich nachgeladen.
- Keine Begrenzung auf die ersten Abschnitte: jeder inhaltliche Absatz landet in genau einer Einheit.
- Tokenzahlen werden mit dem Tokenizer des Embedding-Modells gemessen, sofern lokal vorhanden.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import db
from .config import Config, code_version
from .versions import read_text

METHOD = "paragraph-greedy"
METHOD_VERSION = "seg-1"
SENT_RE = re.compile(r"(?<=[.!?…:;])[\"'”“»)]*\s+(?=[\"'„“«(\[]?[A-ZÄÖÜ0-9])")


class TokenCounter:
    def __init__(self, cfg: Config):
        self.name = "approx_words_x1.3"
        self.tok = None
        path = model_dir(cfg) / "tokenizer.json"
        if path.exists():
            from tokenizers import Tokenizer
            self.tok = Tokenizer.from_file(str(path))
            self.tok.no_padding()
            self.tok.no_truncation()
            self.name = f"tokenizer:{cfg.section('embed').get('model_id')}"

    def count(self, text: str) -> int:
        if self.tok is not None:
            return len(self.tok.encode(text, add_special_tokens=False).ids)
        return int(len(text.split()) * 1.3) + 1


def model_dir(cfg: Config):
    return cfg.models_dir / cfg.section("embed").get("model_id", "model").replace("/", "__")


@dataclass
class Piece:
    start: int
    end: int
    para: int


def split_sentences(text: str, start: int, end: int) -> list[tuple[int, int]]:
    seg = text[start:end]
    out = []
    pos = 0
    for m in SENT_RE.finditer(seg):
        out.append((start + pos, start + m.start() + len(m.group(0).rstrip())))
        pos = m.end()
    out.append((start + pos, end))
    # Leerraum an den Rändern abschneiden
    clean = []
    for s, e in out:
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if e > s:
            clean.append((s, e))
    return clean


def _split_long(text: str, s: int, e: int, para: int, counter: TokenCounter, max_t: int, hard_max: int) -> list[list[Piece]]:
    """Langen Absatz an Satzgrenzen teilen; überlange Einzelsätze notfalls an Wortgrenzen."""
    groups: list[list[Piece]] = []
    cur: list[Piece] = []
    cur_t = 0
    for ss, se in split_sentences(text, s, e):
        t = counter.count(text[ss:se])
        if t > hard_max:
            if cur:
                groups.append(cur)
                cur, cur_t = [], 0
            words = [(m.start() + ss, m.end() + ss) for m in re.finditer(r"\S+", text[ss:se])]
            ws = words[0][0]
            acc = 0
            last_end = ws
            for a, b in words:
                wt = counter.count(text[a:b])
                if acc + wt > max_t and acc > 0:
                    groups.append([Piece(ws, last_end, para)])
                    ws, acc = a, 0
                acc += wt
                last_end = b
            groups.append([Piece(ws, last_end, para)])
            continue
        if cur and cur_t + t > max_t:
            groups.append(cur)
            cur, cur_t = [], 0
        cur.append(Piece(ss, se, para))
        cur_t += t
    if cur:
        groups.append(cur)
    return groups


def segment_version(cfg: Config, conn, version_id: int, counter: TokenCounter | None = None, force: bool = False) -> dict:
    sc = cfg.section("segment")
    min_t, max_t, hard_max = int(sc.get("min_tokens", 150)), int(sc.get("max_tokens", 350)), int(sc.get("hard_max_tokens", 500))
    v = conn.execute("SELECT * FROM document_versions WHERE id=?", (version_id,)).fetchone()
    if v is None or not v["text_path"]:
        return {"version_id": version_id, "status": "kein Text"}
    existing = conn.execute("SELECT COUNT(*) FROM argument_units WHERE version_id=? AND method_version=?",
                            (version_id, METHOD_VERSION)).fetchone()[0]
    if existing and not force:
        return {"version_id": version_id, "status": "bereits segmentiert", "units": existing}
    if existing and force:
        ids = [r[0] for r in conn.execute("SELECT id FROM argument_units WHERE version_id=? AND method_version=?", (version_id, METHOD_VERSION))]
        used = conn.execute(
            f"SELECT COUNT(*) FROM (SELECT left_unit_id u FROM candidate_comparisons UNION SELECT right_unit_id FROM candidate_comparisons "
            f"UNION SELECT unit_id FROM claim_candidates) WHERE u IN ({','.join('?' * len(ids))})", ids).fetchone()[0]
        if used:
            raise RuntimeError("Einheiten dieser Version werden bereits in Analysen verwendet. Statt --force eine neue "
                               "METHOD_VERSION verwenden, damit alte Analysen ihre Anker behalten.")
        for uid in ids:
            conn.execute("DELETE FROM units_fts WHERE unit_id=?", (uid,))
        conn.execute("DELETE FROM argument_units WHERE version_id=? AND method_version=?", (version_id, METHOD_VERSION))
    counter = counter or TokenCounter(cfg)
    text = read_text(cfg, v)
    paras = conn.execute("SELECT * FROM paragraphs WHERE version_id=? ORDER BY idx", (version_id,)).fetchall()
    groups: list[tuple[list[Piece], str | None]] = []
    cur: list[Piece] = []
    cur_t = 0
    heading = None
    cur_heading = None

    def flush():
        nonlocal cur, cur_t
        if cur:
            groups.append((cur, cur_heading))
        cur, cur_t = [], 0

    for p in paras:
        s, e = p["start_char"], p["end_char"]
        if p["kind"] == "h":
            if cur_t >= min_t // 3:
                flush()
            heading = text[s:e]
            if not cur:
                cur_heading = heading
            continue
        t = counter.count(text[s:e])
        if t > max_t:
            flush()
            for g in _split_long(text, s, e, p["idx"], counter, max_t, hard_max):
                groups.append((g, heading))
            cur_heading = heading
            continue
        if cur and cur_t + t > max_t:
            flush()
        if not cur:
            cur_heading = heading
        cur.append(Piece(s, e, p["idx"]))
        cur_t += t
        if cur_t >= min_t:
            flush()
    flush()
    # Sehr kurzen Rest an die vorherige Einheit anhängen, wenn das die Höchstgrenze nicht sprengt.
    if len(groups) >= 2:
        last, prev = groups[-1][0], groups[-2][0]
        lt = counter.count(text[last[0].start:last[-1].end])
        pt = counter.count(text[prev[0].start:prev[-1].end])
        if lt < min_t // 3 and lt + pt <= max_t and last[0].para != prev[-1].para:
            groups[-2] = (prev + last, groups[-2][1])
            groups.pop()
    para_bounds = {p["idx"]: (p["start_char"], p["end_char"]) for p in paras}
    n = 0
    covered = 0
    for seq, (g, head) in enumerate(groups):
        s, e = g[0].start, g[-1].end
        ps, pe = g[0].para, g[-1].para
        ctx_s = para_bounds.get(ps - 1, (s, s))[0] if ps - 1 in para_bounds else s
        ctx_e = para_bounds.get(pe + 1, (e, e))[1] if pe + 1 in para_bounds else e
        utext = text[s:e]
        uid = f"v{version_id}:{METHOD_VERSION}:{seq}"
        conn.execute(
            """INSERT OR REPLACE INTO argument_units(id, version_id, document_id, seq, start_char, end_char, para_start, para_end,
               ctx_start, ctx_end, n_tokens, token_counter, heading, text, method, method_version, created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (uid, version_id, v["document_id"], seq, s, e, ps, pe, ctx_s, ctx_e, counter.count(utext), counter.name, head,
             utext, METHOD, METHOD_VERSION, db.now()),
        )
        conn.execute("INSERT INTO units_fts(unit_id, text) VALUES(?,?)", (uid, utext))
        covered += sum(pc.end - pc.start for pc in g)
        n += 1
    content_chars = sum(p["end_char"] - p["start_char"] for p in paras if p["kind"] != "h")
    conn.commit()
    return {"version_id": version_id, "status": "segmentiert", "units": n, "content_chars": content_chars,
            "covered_chars": covered, "coverage": (covered / content_chars) if content_chars else None}


def paragraph_coverage(conn, version_id: int, text: str) -> dict:
    """Anteil der Nicht-Leerzeichen inhaltlicher Absätze (ohne Überschriften), die in einer Einheit liegen.
    Leerzeichen an Satzgrenzen zwischen zwei Teilstücken eines langen Absatzes zählen nicht als Lücke."""
    paras = conn.execute("SELECT * FROM paragraphs WHERE version_id=? AND kind!='h' ORDER BY idx", (version_id,)).fetchall()
    units = conn.execute("SELECT start_char, end_char FROM argument_units WHERE version_id=? AND method_version=? ORDER BY start_char",
                         (version_id, METHOD_VERSION)).fetchall()
    inside = bytearray(len(text))
    for u in units:
        inside[u["start_char"]:u["end_char"]] = b"\x01" * (u["end_char"] - u["start_char"])
    total = covered = 0
    uncovered = []
    for p in paras:
        n = c = 0
        for i in range(p["start_char"], p["end_char"]):
            if not text[i].isspace():
                n += 1
                c += inside[i]
        total += n
        covered += c
        if c < n:
            uncovered.append(p["idx"])
    return {"content_paragraphs": len(paras), "content_chars": total, "covered_chars": covered,
            "coverage": round(covered / total, 4) if total else None, "paragraphs_not_fully_covered": uncovered}


def segment_all(cfg: Config, conn, doc_ids: list[str] | None = None, force: bool = False) -> list[dict]:
    counter = TokenCounter(cfg)
    q = "SELECT id FROM document_versions WHERE is_current=1 AND text_path IS NOT NULL"
    rows = conn.execute(q).fetchall() if doc_ids is None else [
        r for d in doc_ids for r in conn.execute(q + " AND document_id=?", (d,)).fetchall()]
    run_id = db.new_run_id("segment")
    conn.execute("INSERT INTO runs(id, kind, code_version, config_json, started_at, status, notes) VALUES(?,?,?,?,?,?,?)",
                 (run_id, "segment", code_version(), db.dumps(cfg.section("segment")), db.now(), "running",
                  f"{METHOD}/{METHOD_VERSION}; Tokenzähler {counter.name}"))
    out = [segment_version(cfg, conn, r["id"], counter, force) for r in rows]
    conn.execute("UPDATE runs SET finished_at=?, status='finished', usage_json=? WHERE id=?",
                 (db.now(), db.dumps({"versions": len(out)}), run_id))
    conn.commit()
    return out
