"""Import der öffentlichen Metadaten des Ausgangsprojekts (posts.json bevorzugt, CSV als Alternative).

Grundsätze (Übergabedokument, Abschnitte 4 und 6):
- Alle Originalfelder bleiben unverändert in documents.upstream_payload erhalten.
- Upstream-IDs werden im Namensraum upstream:mc-lit-review geführt, nicht mit Substack-IDs gleichgesetzt.
- Klassifikationen sind historische Fremdcodes (upstream_codes), keine neu geprüften Bewertungen.
- Abweichungen zu summary.json werden berichtet, nicht wegkorrigiert.
- Es werden keine Artikeltexte aus Metadaten rekonstruiert.
"""
from __future__ import annotations

import collections
import csv
import io
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests

from . import db
from .config import Config

NS = "mc-lit-review"
AXES = ["experience_now", "cognition_now", "agency_now", "possible", "moral_status", "serious"]
CSV_COLUMNS = ["id", "date", "title", "publication", "type", "genre", "experience", "cognition", "agency",
               "moral", "topic", "reactions", "restacks", "over", "cited_by", "url"]


def doc_id_for(upstream_id) -> str:
    return f"upstream:{NS}:post:{upstream_id}"


def canonical_url(url: str | None) -> tuple[str | None, str | None, str | None]:
    """(kanonische URL, host, slug). Entfernt Query/Fragment und /comments-Suffixe."""
    if not url:
        return None, None, None
    parts = urlsplit(url.strip())
    host = parts.netloc.lower()
    path = parts.path.rstrip("/")
    slug = None
    segs = [s for s in path.split("/") if s]
    if len(segs) >= 2 and segs[0] == "p":
        slug = segs[1]
        path = f"/p/{slug}"
    return urlunsplit(("https", host, path, "", "")), host, slug


def download(url: str, dest: Path, user_agent: str) -> tuple[Path, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, headers={"User-Agent": user_agent}, timeout=120)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return dest, db.sha256_bytes(r.content)


def _inventory(records: list[dict]) -> dict:
    keys = collections.Counter()
    types: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in records:
        for k, v in r.items():
            keys[k] += 1
            types[k][type(v).__name__] += 1
    return {k: {"present": keys[k], "types": dict(types[k])} for k in sorted(keys)}


def _code_value_inventory(records: list[dict]) -> dict:
    """Tatsächlich vorkommende Codewerte, damit unbekannte Werte sichtbar werden statt still zu verschwinden."""
    out: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in records:
        for f in ("relevance", "genre", "claim_object", "axes_source", "group", "view_revised", "post_type"):
            out[f][str(r.get(f))] += 1
        for a, v in (r.get("axes") or {}).items():
            out[f"axes.{a}"][str(v)] += 1
        for code in r.get("arguments") or []:
            out["arguments"][code] += 1
    return {k: dict(v.most_common()) for k, v in out.items()}


def _compare_summary(records: list[dict], summary: dict | None) -> list[dict]:
    if not summary:
        return [{"check": "summary.json", "status": "nicht verfügbar"}]
    rows = []

    def cmp(name, ours, theirs):
        rows.append({"check": name, "import": ours, "summary_json": theirs,
                     "status": "gleich" if ours == theirs else "ABWEICHUNG"})

    cmp("Anzahl Beiträge (posts_relevant)", len(records), summary.get("posts_relevant"))
    cmp("Publikationen (publications_relevant)", len({r.get("publication_id") for r in records}), summary.get("publications_relevant"))
    dates = sorted(r["date"] for r in records if r.get("date"))
    cmp("Datumsbereich", [dates[0], dates[-1]] if dates else None, summary.get("date_range"))
    genre = collections.Counter(r.get("genre") for r in records)
    cmp("Genre (by_genre)", dict(sorted(genre.items())), dict(sorted((summary.get("by_genre") or {}).items())))
    rel = collections.Counter(r.get("relevance") for r in records)
    prisma_rel = (summary.get("prisma") or {}).get("relevance") or {}
    cmp("Relevanz central", rel.get("central"), prisma_rel.get("central"))
    cmp("Relevanz substantial", rel.get("substantial"), prisma_rel.get("substantial"))
    cmp("Codebook-Version", None, summary.get("codebook_version"))
    rows[-1]["status"] = "nur in summary.json (nicht pro Datensatz exportiert)"
    return rows


def _upsert_document(conn, run_id: int, doc: dict, payload: dict) -> str:
    payload_json = db.dumps(payload)
    psha = db.sha256_text(payload_json)
    cur = conn.execute("SELECT payload_sha256, upstream_payload FROM documents WHERE id=?", (doc["id"],)).fetchone()
    ts = db.now()
    if cur is None:
        conn.execute(
            """INSERT INTO documents(id, origin, is_synthetic, upstream_ns, upstream_id, canonical_url, host, slug, title,
               subtitle, author, publication, date, upstream_words, upstream_paywalled, upstream_payload, payload_sha256,
               import_run_id, first_seen_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (doc["id"], doc["origin"], doc.get("is_synthetic", 0), doc.get("upstream_ns"), doc.get("upstream_id"),
             doc.get("canonical_url"), doc.get("host"), doc.get("slug"), doc.get("title"), doc.get("subtitle"),
             doc.get("author"), doc.get("publication"), doc.get("date"), doc.get("upstream_words"),
             doc.get("upstream_paywalled"), payload_json, psha, run_id, ts, ts),
        )
        return "new"
    if cur["payload_sha256"] == psha:
        return "unchanged"
    db.add_revision(conn, "document", doc["id"], {"payload_sha256": cur["payload_sha256"]},
                    {"payload_sha256": psha, "import_run_id": run_id}, "Upstream-Metadaten geändert", "importer")
    conn.execute(
        """UPDATE documents SET canonical_url=?, host=?, slug=?, title=?, subtitle=?, author=?, publication=?, date=?,
           upstream_words=?, upstream_paywalled=?, upstream_payload=?, payload_sha256=?, import_run_id=?, updated_at=?
           WHERE id=?""",
        (doc.get("canonical_url"), doc.get("host"), doc.get("slug"), doc.get("title"), doc.get("subtitle"),
         doc.get("author"), doc.get("publication"), doc.get("date"), doc.get("upstream_words"),
         doc.get("upstream_paywalled"), payload_json, psha, run_id, ts, doc["id"]),
    )
    return "updated"


def import_posts_json(cfg: Config, conn, path: Path | None = None, download_pinned: bool = False) -> dict:
    up = cfg.section("upstream")
    commit = up.get("commit")
    ua = cfg.section("fetch").get("user_agent", "susa-ai")
    source_url = None
    summary = None
    if download_pinned:
        source_url = up["posts_json_url"].format(commit=commit)
        path, _ = download(source_url, cfg.subdir(f"upstream/{commit}") / "posts.json", ua)
        try:
            spath, _ = download(up["summary_json_url"].format(commit=commit), cfg.subdir(f"upstream/{commit}") / "summary.json", ua)
            summary = json.loads(spath.read_text("utf-8"))
        except Exception as e:  # summary ist optional, Fehler wird berichtet
            summary = None
            print(f"Warnung: summary.json nicht geladen: {e}")
    else:
        assert path is not None, "Pfad zu posts.json oder --download angeben"
        path = Path(path)
        spath = path.with_name("summary.json")
        if spath.exists():
            summary = json.loads(spath.read_text("utf-8"))
    raw = path.read_bytes()
    sha = db.sha256_bytes(raw)
    records = json.loads(raw.decode("utf-8"))  # UTF-8 und valides JSON, sonst Abbruch mit Fehler
    if isinstance(records, dict):
        records = records.get("posts", [])
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO import_runs(kind, source_url, source_path, sha256, upstream_commit, license, started_at) VALUES(?,?,?,?,?,?,?)",
        ("upstream_json", source_url, str(path), sha, commit if (download_pinned or source_url) else up.get("commit") + " (angenommen, lokale Datei)",
         up.get("license_data"), ts),
    )
    run_id = cur.lastrowid
    counts = collections.Counter()
    ids = collections.Counter(r.get("id") for r in records)
    urls = collections.Counter(canonical_url(r.get("url"))[0] for r in records)
    errors = []
    for r in records:
        try:
            if r.get("id") is None:
                errors.append({"record": r.get("url"), "error": "fehlende id"})
                continue
            curl, host, slug = canonical_url(r.get("url"))
            doc = {
                "id": doc_id_for(r["id"]), "origin": "upstream_json", "upstream_ns": NS, "upstream_id": str(r["id"]),
                "canonical_url": curl, "host": host or r.get("host"), "slug": slug, "title": r.get("title"),
                "subtitle": r.get("subtitle"), "author": r.get("author"), "publication": r.get("publication"),
                "date": r.get("date"), "upstream_words": r.get("words") if isinstance(r.get("words"), int) else None,
                "upstream_paywalled": r.get("paywalled") if isinstance(r.get("paywalled"), int) else None,
            }
            counts[_upsert_document(conn, run_id, doc, r)] += 1
            axes = r.get("axes") or {}
            conn.execute(
                """INSERT OR REPLACE INTO upstream_codes(document_id, import_run_id, codebook_version, relevance, genre,
                   claim_object, community, grp, experience_now, cognition_now, agency_now, possible, moral_status, serious,
                   axes_source, arguments_json, features_json, stance_json, view_revised, cluster_label, quarter)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (doc["id"], run_id, (summary or {}).get("codebook_version"), r.get("relevance"), r.get("genre"),
                 r.get("claim_object"), r.get("community"), r.get("group"), *[axes.get(a) for a in AXES],
                 r.get("axes_source"), db.dumps(r.get("arguments") or []), db.dumps(r.get("features") or {}),
                 db.dumps(r.get("stance") or {}), r.get("view_revised"), r.get("cluster_label"), r.get("quarter")),
            )
        except Exception as e:
            errors.append({"record": r.get("id"), "error": repr(e)})
    dates = sorted(r["date"] for r in records if r.get("date"))
    report = {
        "source_path": str(path), "source_url": source_url, "sha256": sha, "bytes": len(raw),
        "upstream_commit": commit, "license": up.get("license_data"),
        "records": len(records), "unique_ids": len(ids), "duplicate_ids": [i for i, n in ids.items() if n > 1],
        "duplicate_urls": [u for u, n in urls.items() if n > 1 and u],
        "date_range": [dates[0], dates[-1]] if dates else None,
        "authors": len({r.get("author") for r in records}), "publications": len({r.get("publication_id") for r in records}),
        "result": dict(counts), "errors": errors,
        "summary_comparison": _compare_summary(records, summary),
        "field_inventory": _inventory(records), "code_values": _code_value_inventory(records),
        "volltexte": "Der Export enthält keine Artikeltexte. view_revised_quote ist ein fremdes Originalzitat, kein Volltext.",
    }
    conn.execute(
        "UPDATE import_runs SET finished_at=?, n_records=?, n_new=?, n_updated=?, n_unchanged=?, report_json=? WHERE id=?",
        (db.now(), len(records), counts["new"], counts["updated"], counts["unchanged"], db.dumps(report), run_id),
    )
    conn.commit()
    report["import_run_id"] = run_id
    write_import_report(cfg, run_id, report)
    return report


def import_csv(cfg: Config, conn, path: Path, filters_note: str) -> dict:
    """CSV aus dem Browser-Download. Anzeigebezeichnungen werden nicht als interne Codes interpretiert;
    possible und serious fehlen in der CSV und werden nicht ergänzt."""
    raw = Path(path).read_bytes()
    sha = db.sha256_bytes(raw)
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in CSV_COLUMNS if c not in (reader.fieldnames or [])]
    cur = conn.execute(
        "INSERT INTO import_runs(kind, source_path, sha256, license, notes, started_at) VALUES(?,?,?,?,?,?)",
        ("upstream_csv", str(path), sha, cfg.section("upstream").get("license_data"), f"Filter beim Download: {filters_note}", db.now()),
    )
    run_id = cur.lastrowid
    counts = collections.Counter()
    rows = list(reader)
    for r in rows:
        curl, host, slug = canonical_url(r.get("url"))
        doc = {"id": doc_id_for(r["id"]), "origin": "upstream_csv", "upstream_ns": NS, "upstream_id": str(r["id"]),
               "canonical_url": curl, "host": host, "slug": slug, "title": r.get("title"), "publication": r.get("publication"),
               "date": r.get("date")}
        existing = conn.execute("SELECT origin FROM documents WHERE id=?", (doc["id"],)).fetchone()
        if existing and existing["origin"] == "upstream_json":
            counts["skipped_json_present"] += 1  # JSON ist reichhaltiger; CSV überschreibt es nicht
            continue
        counts[_upsert_document(conn, run_id, doc, r)] += 1
        display = {k: r.get(k) for k in ("type", "genre", "experience", "cognition", "agency", "moral", "topic")}
        conn.execute(
            "INSERT OR REPLACE INTO upstream_codes(document_id, import_run_id, csv_display_json, genre, cluster_label) VALUES(?,?,?,?,?)",
            (doc["id"], run_id, db.dumps(display), None, r.get("topic")),
        )
    report = {"source_path": str(path), "sha256": sha, "rows": len(rows), "missing_columns": missing,
              "filters_note": filters_note, "result": dict(counts),
              "hinweis": "CSV enthält Anzeigebezeichnungen; possible und serious fehlen und wurden nicht erfunden."}
    conn.execute("UPDATE import_runs SET finished_at=?, n_records=?, n_new=?, n_updated=?, n_unchanged=?, report_json=? WHERE id=?",
                 (db.now(), len(rows), counts["new"], counts["updated"], counts["unchanged"], db.dumps(report), run_id))
    conn.commit()
    report["import_run_id"] = run_id
    return report


def write_import_report(cfg: Config, run_id: int, rep: dict) -> Path:
    lines = [f"# Importbericht {run_id}", "",
             f"- Quelle: `{rep.get('source_url') or rep.get('source_path')}`",
             f"- SHA-256: `{rep['sha256']}` ({rep['bytes']:,} Bytes)",
             f"- Upstream-Commit: `{rep['upstream_commit']}`",
             f"- Lizenz der Daten: {rep['license']}",
             f"- Datensätze: {rep['records']}, eindeutige IDs: {rep['unique_ids']}, doppelte IDs: {len(rep['duplicate_ids'])}, "
             f"doppelte URLs: {len(rep['duplicate_urls'])}",
             f"- Datumsbereich: {rep['date_range']}, Autoren: {rep['authors']}, Publikationen: {rep['publications']}",
             f"- Ergebnis: {rep['result']}, Fehler: {len(rep['errors'])}", "",
             "## Vergleich mit summary.json", "", "| Prüfung | Import | summary.json | Status |", "|---|---|---|---|"]
    for row in rep["summary_comparison"]:
        lines.append(f"| {row['check']} | {row.get('import')} | {row.get('summary_json')} | {row['status']} |")
    lines += ["", "## Feldinventar", "", "| Feld | vorhanden | Typen |", "|---|---|---|"]
    for k, v in rep["field_inventory"].items():
        lines.append(f"| {k} | {v['present']} | {v['types']} |")
    lines += ["", f"Hinweis: {rep['volltexte']}", ""]
    p = cfg.subdir("reports") / f"import_{run_id}.md"
    p.write_text("\n".join(lines), "utf-8")
    return p
