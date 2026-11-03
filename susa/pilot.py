"""Pilotauswahl und Pilotbericht.

Auswahl: geschichtete Zufallsstichprobe (Seed dokumentiert) über Gruppe, Positionsachse und Quartal,
nicht nach Reichweite oder Clusterdichte. Gezielt ausgewählte Fälle werden getrennt markiert.
Die Auswahl ist eine Arbeitsgröße für den Prototyp, keine repräsentative Stichprobe.
"""
from __future__ import annotations

import collections
import json
import random
from pathlib import Path

from . import db
from .config import Config
from .segment import paragraph_coverage
from .versions import read_text


def select_pilot(cfg: Config, conn, n: int = 40, seed: int = 20261103, max_words: int = 6000, targeted: list[str] | None = None) -> dict:
    rows = conn.execute(
        """SELECT d.id, d.title, d.author, d.date, d.canonical_url, d.upstream_words, d.upstream_paywalled,
                  c.grp, c.quarter, c.experience_now, c.genre, c.relevance
           FROM documents d JOIN upstream_codes c ON c.document_id=d.id
           WHERE d.origin='upstream_json' AND COALESCE(d.upstream_paywalled,0)=0 AND d.slug IS NOT NULL
             AND c.genre='essay' AND COALESCE(d.upstream_words,0) BETWEEN 400 AND ?""", (max_words,)).fetchall()
    rng = random.Random(seed)
    strata: dict[tuple, list] = collections.defaultdict(list)
    for r in rows:
        strata[(r["grp"], r["experience_now"], (r["quarter"] or "")[:4])].append(r)
    keys = sorted(strata)
    rng.shuffle(keys)
    for k in keys:
        rng.shuffle(strata[k])
    chosen, authors = [], set()
    while len(chosen) < n and any(strata[k] for k in keys):
        for k in keys:
            while strata[k]:
                r = strata[k].pop()
                if r["author"] in authors:
                    continue
                chosen.append(r)
                authors.add(r["author"])
                break
            if len(chosen) >= n:
                break
    sel = [{"document_id": r["id"], "title": r["title"], "author": r["author"], "date": r["date"], "url": r["canonical_url"],
            "group": r["grp"], "experience_now": r["experience_now"], "quarter": r["quarter"], "selection": "stratified_random"} for r in chosen]
    for did in targeted or []:
        d = conn.execute("SELECT id, title, author, date, canonical_url FROM documents WHERE id=?", (did,)).fetchone()
        if d:
            sel.append({"document_id": d["id"], "title": d["title"], "author": d["author"], "date": d["date"], "url": d["canonical_url"],
                        "selection": "targeted"})
    out = {"seed": seed, "n_requested": n, "n_selected": len(sel), "population_filter":
           f"origin=upstream_json, nicht paywalled, genre=essay, 400–{max_words} Wörter (Upstream-Wortzahl)",
           "population_size": len(rows), "strata": "Gruppe × experience_now × Jahr, je Autor höchstens ein Beitrag",
           "created_at": db.now(), "items": sel}
    p = cfg.root / "pilot" / "pilot_list.json"
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
    return out


def coverage_report(cfg: Config, conn, doc_ids: list[str]) -> dict:
    st = collections.Counter()
    av = collections.Counter()
    details = []
    for did in doc_ids:
        v = conn.execute("SELECT * FROM document_versions WHERE document_id=? ORDER BY is_current DESC, id DESC LIMIT 1", (did,)).fetchone()
        if v is None:
            st["nicht_abgerufen"] += 1
            continue
        st[v["status"]] += 1
        av[v["availability"]] += 1
        units = conn.execute("SELECT COUNT(*) FROM argument_units WHERE version_id=?", (v["id"],)).fetchone()[0]
        cov = paragraph_coverage(conn, v["id"], read_text(cfg, v)) if v["text_path"] else {}
        details.append({"document_id": did, "status": v["status"], "availability": v["availability"], "detail": v["status_detail"],
                        "n_chars": v["n_chars"], "units": units, "coverage": cov.get("coverage"),
                        "paragraphs_not_fully_covered": cov.get("paragraphs_not_fully_covered")})
    return {"n": len(doc_ids), "status": dict(st), "availability": dict(av), "documents": details}
