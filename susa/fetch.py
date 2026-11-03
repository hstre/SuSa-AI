"""Abruf öffentlich verfügbarer Volltexte über den im Ausgangsprojekt verwendeten Endpunkt
https://HOST/api/v1/posts/SLUG (keine offizielle oder garantierte API).

- seriell, mit Mindestabstand zwischen Anfragen, kurzen Wiederholungen bei 429/5xx
- keine Zugangsdaten, keine Cookies, keine Umgehung von Bezahlschranken
- Status und beobachtete Abdeckung werden pro Version gespeichert; HTTP 200 gilt nicht als Vollständigkeitsbeweis
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

from . import db
from .config import Config, code_version
from .extract import html_to_canonical, markdown_to_canonical, word_count
from .versions import add_version, current_version, store_raw

# status -> availability
STATUSES = {
    "ok_full": "full",                     # Text extrahiert, Wortzahl plausibel gegenüber Metadaten
    "ok_unverified_length": "full",        # Text extrahiert, keine Vergleichswortzahl verfügbar
    "partial_suspected": "partial",        # deutlich weniger Wörter als in den Metadaten angegeben
    "paywalled_preview": "preview",        # nur Vorschau eines bezahlten Beitrags
    "login_or_error_page": "unavailable",  # Antwort ist keine Beitrags-JSON (z. B. HTML-Seite)
    "empty": "unavailable",                # Beitrag ohne Textkörper (z. B. reiner Podcast)
    "not_found": "unavailable",
    "http_error": "unavailable",
    "network_error": "unavailable",
    "manual_import": "full",               # vom Nutzer bereitgestellter Text; Vollständigkeit nicht geprüft
    "synthetic_fixture": "full",
}
PAID = {"only_paid", "founding"}
PARTIAL_RATIO = 0.8


class RateLimiter:
    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self.last = 0.0

    def wait(self):
        dt_ = time.monotonic() - self.last
        if dt_ < self.min_interval:
            time.sleep(self.min_interval - dt_)
        self.last = time.monotonic()


def classify_response(status_code: int, content: bytes, upstream_words: int | None) -> tuple[str, str, dict | None, object]:
    """Rückgabe (status, detail, json|None, extracted|None). Reine Funktion, damit sie ohne Netz testbar ist."""
    if status_code in (404, 410):
        return "not_found", f"HTTP {status_code}", None, None
    if status_code != 200:
        return "http_error", f"HTTP {status_code}", None, None
    try:
        d = json.loads(content.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return "login_or_error_page", "Antwort ist kein JSON (möglicherweise Anmelde- oder Fehlerseite)", None, None
    if not isinstance(d, dict):
        return "login_or_error_page", "JSON hat unerwartete Form", None, None
    html = d.get("body_html") or ""
    audience = d.get("audience")
    if not html.strip():
        if audience in PAID:
            return "paywalled_preview", f"audience={audience}, kein body_html", d, None
        return "empty", f"kein body_html (type={d.get('type')})", d, None
    ex = html_to_canonical(html)
    if not ex.text.strip():
        return "empty", "body_html ohne extrahierbaren Text", d, ex
    ours = word_count(ex.text)
    if audience in PAID or "paywall" in html[-4000:]:
        return "paywalled_preview", f"audience={audience}; {ours} Wörter extrahiert (Vorschau)", d, ex
    refs = {k: v for k, v in (("api_wordcount", d.get("wordcount")), ("upstream_words", upstream_words)) if isinstance(v, int) and v > 0}
    if not refs:
        return "ok_unverified_length", f"{ours} Wörter extrahiert; keine Vergleichswortzahl", d, ex
    ref = max(refs.values())
    ratio = ours / ref
    detail = f"{ours} Wörter extrahiert; Vergleich {refs}; Quote {ratio:.2f}"
    if ratio < PARTIAL_RATIO:
        return "partial_suspected", detail, d, ex
    return "ok_full", detail, d, ex


def fetch_document(cfg: Config, conn, doc, session: requests.Session, limiter: RateLimiter) -> dict:
    fc = cfg.section("fetch")
    if not doc["host"] or not doc["slug"]:
        vid, _ = add_version(cfg, conn, doc["id"], source="substack_api", source_url=doc["canonical_url"],
                             status="http_error", availability="unavailable", status_detail="keine auflösbare /p/SLUG-URL")
        return {"doc": doc["id"], "status": "http_error", "detail": "keine /p/SLUG-URL"}
    url = f"https://{doc['host']}/api/v1/posts/{doc['slug']}"
    attempt = 0
    while True:
        limiter.wait()
        try:
            r = session.get(url, timeout=fc.get("timeout_seconds", 30))
        except requests.RequestException as e:
            if attempt < fc.get("max_retries", 2):
                attempt += 1
                time.sleep(fc.get("backoff_seconds", 30))
                continue
            add_version(cfg, conn, doc["id"], source="substack_api", source_url=url, status="network_error",
                        availability="unavailable", status_detail=repr(e)[:500])
            return {"doc": doc["id"], "status": "network_error", "detail": repr(e)[:200]}
        if (r.status_code == 429 or r.status_code >= 500) and attempt < fc.get("max_retries", 2):
            attempt += 1
            wait = fc.get("backoff_seconds", 30)
            ra = r.headers.get("Retry-After")
            if ra and ra.isdigit():
                wait = min(int(ra), 600)
            time.sleep(wait)
            continue
        break
    status, detail, d, ex = classify_response(r.status_code, r.content, doc["upstream_words"])
    raw = store_raw(cfg, r.content, "json" if d is not None else "bin")
    vid, created = add_version(cfg, conn, doc["id"], source="substack_api", source_url=url, status=status,
                               availability=STATUSES[status], status_detail=detail, extracted=ex, raw=raw,
                               http_status=r.status_code, language=(d or {}).get("language"))
    return {"doc": doc["id"], "status": status, "detail": detail, "version_id": vid, "new_version": created}


def fetch_many(cfg: Config, conn, doc_ids: list[str], refetch: bool = False) -> list[dict]:
    fc = cfg.section("fetch")
    session = requests.Session()
    session.headers["User-Agent"] = fc.get("user_agent", "susa-ai")
    limiter = RateLimiter(float(fc.get("min_interval_seconds", 2.0)))
    run_id = db.new_run_id("fetch")
    conn.execute("INSERT INTO runs(id, kind, code_version, config_json, started_at, status) VALUES(?,?,?,?,?,?)",
                 (run_id, "fetch", code_version(), db.dumps(fc), db.now(), "running"))
    results = []
    for i, did in enumerate(doc_ids, 1):
        doc = conn.execute("SELECT * FROM documents WHERE id=?", (did,)).fetchone()
        if doc is None:
            results.append({"doc": did, "status": "unknown_document"})
            continue
        cur = current_version(conn, did)
        if cur is not None and not refetch and cur["text_sha256"]:
            results.append({"doc": did, "status": cur["status"], "detail": "Cache (bereits abgerufen)", "version_id": cur["id"]})
            continue
        res = fetch_document(cfg, conn, doc, session, limiter)
        results.append(res)
        print(f"[{i}/{len(doc_ids)}] {res['status']:<22} {did}  {res.get('detail', '')[:90]}")
    summary = {}
    for r in results:
        summary[r["status"]] = summary.get(r["status"], 0) + 1
    conn.execute("UPDATE runs SET finished_at=?, status=?, usage_json=? WHERE id=?",
                 (db.now(), "finished", db.dumps({"requests_status": summary, "n": len(doc_ids)}), run_id))
    conn.commit()
    return results


def import_text_file(cfg: Config, conn, path: Path, *, doc_id: str | None, url: str | None, title: str | None,
                     author: str | None, date: str | None, source_note: str) -> int:
    """Manueller TXT-/Markdown-Import mit Quellenangabe (Ersatzweg laut Übergabe, Abschnitt 7)."""
    content = Path(path).read_bytes()
    text = content.decode("utf-8")
    ex = html_to_canonical(text) if path.suffix.lower() in (".html", ".htm") else markdown_to_canonical(text)
    sha = db.sha256_bytes(content)
    if doc_id is None:
        if url:
            row = conn.execute("SELECT id FROM documents WHERE canonical_url=?", (url,)).fetchone()
            doc_id = row["id"] if row else None
        doc_id = doc_id or f"manual:{sha[:12]}"
    if conn.execute("SELECT 1 FROM documents WHERE id=?", (doc_id,)).fetchone() is None:
        ts = db.now()
        conn.execute(
            "INSERT INTO documents(id, origin, is_synthetic, canonical_url, title, author, date, upstream_payload, first_seen_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (doc_id, "manual", 0, url, title, author, date, db.dumps({"source_note": source_note}), ts, ts),
        )
    raw = store_raw(cfg, content, path.suffix.lstrip(".") or "txt")
    vid, _ = add_version(cfg, conn, doc_id, source="manual_file", source_url=url, status="manual_import",
                         availability="full", status_detail=f"Manueller Import aus {path.name}; Quelle: {source_note}",
                         extracted=ex, raw=raw)
    return vid
