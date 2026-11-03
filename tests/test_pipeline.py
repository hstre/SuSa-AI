import json

import pytest

from susa import analysis, db
from susa.acceptance import formal_checks, run_acceptance
from susa.embed import embed_units
from susa.export import export_jsonl
from susa.extract import html_to_canonical
from susa.fixtures import load_fixtures
from susa.importer import canonical_url, import_posts_json
from susa.search import ensure_comparison, find_candidates, marker_diff
from susa.segment import paragraph_coverage, segment_all
from susa.versions import add_version, current_version, read_text


def test_import_json_idempotent(env, tmp_path):
    cfg, conn = env
    posts = [{"id": 1, "title": "T", "url": "https://x.substack.com/p/slug-a?utm=1", "date": "2025-01-01", "publication_id": 9,
              "genre": "essay", "relevance": "central", "axes": {"experience_now": "no"}, "unknown_field": {"a": 1}, "words": None},
             {"id": 2, "title": "U", "url": "https://x.substack.com/p/slug-b/comments", "date": "2025-02-01", "publication_id": 9,
              "genre": "essay", "relevance": "substantial", "axes": {}, "subscribers": "1K+"}]
    p = tmp_path / "posts.json"
    p.write_text(json.dumps(posts), "utf-8")
    (tmp_path / "summary.json").write_text(json.dumps({"posts_relevant": 3, "date_range": ["2025-01-01", "2025-02-01"]}))
    r1 = import_posts_json(cfg, conn, p)
    r2 = import_posts_json(cfg, conn, p)
    assert r1["result"] == {"new": 2} and r2["result"] == {"unchanged": 2}
    d = conn.execute("SELECT * FROM documents WHERE id='upstream:mc-lit-review:post:1'").fetchone()
    assert d["canonical_url"] == "https://x.substack.com/p/slug-a" and d["slug"] == "slug-a"
    assert json.loads(d["upstream_payload"])["unknown_field"] == {"a": 1}
    rows = {r["check"]: r["status"] for r in r1["summary_comparison"]}
    assert rows["Anzahl Beiträge (posts_relevant)"] == "ABWEICHUNG"  # berichtet, nicht korrigiert
    assert canonical_url("https://x.substack.com/p/s/comments")[2] == "s"


def _doc_with_text(cfg, conn, did, html, author="A", date="2026-01-01"):
    ts = db.now()
    conn.execute("INSERT INTO documents(id, origin, is_synthetic, author, date, title, first_seen_at, updated_at) VALUES(?,?,?,?,?,?,?,?)",
                 (did, "synthetic", 1, author, date, did, ts, ts))
    return add_version(cfg, conn, did, source="synthetic_fixture", source_url=None, status="synthetic_fixture", availability="full",
                       extracted=html_to_canonical(html))[0]


def test_segmentation_covers_everything_and_splits_long(env):
    cfg, conn = env
    long_para = " ".join(f"Satz Nummer {i} enthält ein paar Wörter zur Füllung." for i in range(200))
    html = "<h2>Kopf</h2><p>Kurz.</p><p>" + long_para + "</p><p>Schluss mit entscheidendem Gedanken.</p>"
    vid = _doc_with_text(cfg, conn, "synthetic:t:L", html)
    segment_all(cfg, conn)
    units = conn.execute("SELECT * FROM argument_units WHERE version_id=? ORDER BY seq", (vid,)).fetchall()
    text = read_text(cfg, current_version(conn, "synthetic:t:L"))
    assert len(units) > 3
    assert all(text[u["start_char"]:u["end_char"]] == u["text"] for u in units)
    assert all(u["n_tokens"] <= int(cfg.section("segment")["hard_max_tokens"]) for u in units)
    assert paragraph_coverage(conn, vid, text)["coverage"] == 1.0
    assert any("Schluss mit entscheidendem" in u["text"] for u in units)
    # keine Überlappung der Kerneinheiten
    assert all(a["end_char"] <= b["start_char"] for a, b in zip(units, units[1:]))


def test_marker_diff_negation():
    hints = marker_diff("Eine höhere Leistung belegt Bewusstsein.", "Eine höhere Leistung belegt Bewusstsein nicht.")
    assert any("Negation nur rechts" in h for h in hints)


def test_export_excludes_real_texts(env, tmp_path):
    cfg, conn = env
    ts = db.now()
    conn.execute("INSERT INTO documents(id, origin, is_synthetic, first_seen_at, updated_at) VALUES('upstream:x:post:1','upstream_json',0,?,?)", (ts, ts))
    add_version(cfg, conn, "upstream:x:post:1", source="manual_file", source_url=None, status="manual_import", availability="full",
                extracted=html_to_canonical("<p>Geheimer fremder Volltext.</p>"))
    segment_all(cfg, conn)
    out = tmp_path / "e.jsonl"
    export_jsonl(conn, out, include_quotes=True)
    raw = out.read_text("utf-8")
    assert "Geheimer fremder Volltext" not in raw
    assert all(json.loads(line)["schema"].startswith("susa-export/") for line in raw.splitlines())


def test_acceptance_runs_with_test_vectors(env):
    cfg, conn = env
    rep = run_acceptance(cfg, conn, "none", "test-hash")
    rows = rep["cases"]
    assert {r["case"] for r in rows} == {f"case{i:02d}" for i in range(1, 13)}
    get = lambda c, lang, part: next(r for r in rows if r["case"] == c and r["lang"] == lang and r["part"] == part)
    for c, lang, part in [("case05", "en", "Retrieval"), ("case06", "de", "Zitat-Heuristik"), ("case06", "en", "Zitat-Heuristik"),
                          ("case08", "de", "Quellenindex"), ("case08", "en", "Quellenindex"), ("case12", "de", "Versionierung")]:
        assert get(c, lang, part)["result"] == "bestanden", (c, lang, part)
    assert get("case03", "de+en", "Retrieval")["result"] == "nicht unterstützt"
    # ohne Modell: kein Modellteil darf bestanden sein
    assert all(r["result"] == "nicht ausgeführt" for r in rows if r["part"].startswith("Modell"))
    assert all(f["ok"] for f in rep["formal"])
    run_acceptance(cfg, conn, "none", "test-hash")
    assert all(f["ok"] for f in formal_checks(cfg, conn))
