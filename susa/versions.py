"""Textversionen: unveränderter kanonischer Text auf der Platte, Metadaten und Anker in SQLite."""
from __future__ import annotations

import re
from pathlib import Path

from . import db
from .config import Config
from .extract import EXTRACT_VERSION, Extracted, inline_quotes, word_count


def safe_name(doc_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", doc_id)


def read_text(cfg: Config, version_row) -> str:
    return (cfg.root / version_row["text_path"]).read_text("utf-8")


def store_raw(cfg: Config, content: bytes, ext: str) -> tuple[str, str]:
    sha = db.sha256_bytes(content)
    p = cfg.subdir("raw") / f"{sha}.{ext}"
    if not p.exists():
        p.write_bytes(content)
    return str(p.relative_to(cfg.root)), sha


def add_version(cfg: Config, conn, document_id: str, *, source: str, source_url: str | None, status: str,
                availability: str, status_detail: str | None = None, extracted: Extracted | None = None,
                raw: tuple[str, str] | None = None, http_status: int | None = None, language: str | None = None) -> tuple[int, bool]:
    """Legt eine neue Version an. Rückgabe (version_id, created). Gleicher Text wie die aktuelle Version -> keine neue
    Version (verhindert Duplikate bei wiederholtem Import). Eine Version mit geändertem Text ersetzt die alte als
    'aktuell', ohne sie zu löschen; Analysen der alten Version bleiben erhalten und gelten als veraltet."""
    text = extracted.text if extracted else None
    tsha = db.sha256_text(text) if text is not None else None
    cur = conn.execute("SELECT * FROM document_versions WHERE document_id=? AND is_current=1 ORDER BY id DESC LIMIT 1",
                       (document_id,)).fetchone()
    if cur is not None and tsha is not None and cur["text_sha256"] == tsha and cur["status"] == status:
        return cur["id"], False
    if cur is not None and tsha is None and cur["text_sha256"] is not None:
        # Erneuter Abruf scheitert, älterer Text existiert: alten Text als aktuell behalten, Fehlversuch protokollieren.
        conn.execute(
            """INSERT INTO document_versions(document_id, fetched_at, source, source_url, http_status, raw_path, raw_sha256,
               status, availability, status_detail, is_current) VALUES(?,?,?,?,?,?,?,?,?,?,0)""",
            (document_id, db.now(), source, source_url, http_status, raw[0] if raw else None, raw[1] if raw else None,
             status, availability, (status_detail or "") + " (ältere Textversion bleibt aktuell)"),
        )
        conn.commit()
        return cur["id"], False
    text_path = None
    if text is not None:
        p = cfg.subdir("texts") / safe_name(document_id) / f"{tsha}.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, "utf-8")
        text_path = str(p.relative_to(cfg.root))
    conn.execute("UPDATE document_versions SET is_current=0 WHERE document_id=?", (document_id,))
    c = conn.execute(
        """INSERT INTO document_versions(document_id, fetched_at, source, source_url, http_status, raw_path, raw_sha256,
           text_path, text_sha256, n_chars, n_words, status, availability, status_detail, language, is_current)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
        (document_id, db.now(), source, source_url, http_status, raw[0] if raw else None, raw[1] if raw else None,
         text_path, tsha, len(text) if text is not None else None, word_count(text) if text else None,
         status, availability, status_detail, language),
    )
    vid = c.lastrowid
    if extracted:
        for i, p in enumerate(extracted.paragraphs):
            conn.execute("INSERT INTO paragraphs(version_id, idx, start_char, end_char, kind, speaker_hint) VALUES(?,?,?,?,?,?)",
                         (vid, i, p.start, p.end, p.kind, p.speaker_hint))
            for qs, qe in inline_quotes(text, p):
                qt = text[qs:qe]
                conn.execute(
                    "INSERT INTO spans(id, version_id, start_char, end_char, text, paragraph_idx, speaker, origin, text_sha256, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (f"v{vid}:q:{qs}-{qe}", vid, qs, qe, qt, i, "quoted_other", "quote_heuristic", db.sha256_text(qt), db.now()),
                )
        for ln in extracted.links:
            conn.execute("INSERT INTO links(version_id, start_char, end_char, href, target) VALUES(?,?,?,?,?)",
                         (vid, ln.start, ln.end, ln.href, ln.target))
    if cur is not None and cur["text_sha256"] and tsha and cur["text_sha256"] != tsha:
        db.add_revision(conn, "document_text", document_id, {"version_id": cur["id"], "text_sha256": cur["text_sha256"]},
                        {"version_id": vid, "text_sha256": tsha, "extract": EXTRACT_VERSION},
                        "Neue Textversion; Anker und Analysen der alten Version gelten als veraltet", "versions")
    conn.commit()
    return vid, True


def current_version(conn, document_id: str):
    return conn.execute("SELECT * FROM document_versions WHERE document_id=? AND is_current=1 ORDER BY id DESC LIMIT 1",
                        (document_id,)).fetchone()


def verify_anchor(cfg: Config, conn, version_id: int, start: int, end: int, expected: str) -> bool:
    v = conn.execute("SELECT * FROM document_versions WHERE id=?", (version_id,)).fetchone()
    if v is None or not v["text_path"]:
        return False
    return read_text(cfg, v)[start:end] == expected
