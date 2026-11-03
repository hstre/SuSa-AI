import json

import pytest

from susa import analysis, db
from susa.acceptance import formal_checks, run_acceptance
from susa.embed import embed_units
from susa.export import export_jsonl
from susa.extract import html_to_canonical
from susa.fixtures import load_fixtures
from susa.importer import canonical_url, import_posts_json
from susa.llm import ReplayAdapter, get_adapter
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


def test_candidates_compare_review_flow(env):
    cfg, conn = env
    _doc_with_text(cfg, conn, "synthetic:t:A", "<p>Memory makes an agent consistent across sessions.</p>", "A")
    _doc_with_text(cfg, conn, "synthetic:t:B", "<p>Memory can support consistency, but only if the agent revises conflicting memories.</p>", "B", "2026-02-01")
    _doc_with_text(cfg, conn, "synthetic:t:C", "<p>Benchmarks do not establish consciousness.</p>", "C")
    segment_all(cfg, conn)
    embed_units(cfg, conn, "test-hash")
    ua = conn.execute("SELECT id FROM argument_units WHERE document_id='synthetic:t:A'").fetchone()[0]
    ub = conn.execute("SELECT id FROM argument_units WHERE document_id='synthetic:t:B'").fetchone()[0]
    res = find_candidates(cfg, conn, ua)
    cid = f"cmp:{ua}|{ub}"
    assert cid in res["candidates"]
    cmp_ = conn.execute("SELECT * FROM candidate_comparisons WHERE id=?", (cid,)).fetchone()
    assert cmp_["temporal"] == "right_later" and json.loads(cmp_["corpus_scope_json"])["embedding_is_test_vectors"] is True

    # Ohne Adapter: not_run, keine Interpretation
    r = analysis.compare(cfg, conn, cid, adapter=get_adapter({"adapter": "none"}))
    assert r["status"] == "not_run"
    assert conn.execute("SELECT COUNT(*) FROM relation_hypotheses").fetchone()[0] == 0

    # Replay: ein Zitat stimmt, eines ist erfunden -> quote_unverified
    reply = json.dumps({"relation_types": ["restricts_scope", "bogus"], "left_quotes": ["Memory makes an agent consistent"],
                        "right_quotes": ["only if the agent revises conflicting memories", "erfunden"], "added_thought": "x"})
    r = analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [reply]))
    h = conn.execute("SELECT * FROM relation_hypotheses WHERE id=?", (r["hypothesis_id"],)).fetchone()
    assert h["status"] == "quote_unverified" and json.loads(h["relation_types_json"]) == ["restricts_scope"]
    run = conn.execute("SELECT * FROM runs WHERE id=?", (h["run_id"],)).fetchone()
    assert run["is_real_model_run"] == 0 and run["adapter"] == "replay"
    qc = json.loads(h["quote_check_json"])
    assert qc["left"][0]["found"] and not qc["right"][1]["found"] and qc["unknown_relation_types"] == ["bogus"]

    rid = analysis.add_review(conn, "relation_hypothesis", h["id"], "tester", "corrected", "Zitat fehlt", {"relation_types": ["refines"]})
    with pytest.raises(Exception):
        conn.execute("UPDATE reviews SET decision='confirmed' WHERE id=?", (rid,))
    with pytest.raises(Exception):
        conn.execute("DELETE FROM reviews WHERE id=?", (rid,))

    hm = analysis.add_manual_hypothesis(cfg, conn, cid, "tester", ["refines"], {"left_quotes": [], "right_quotes": []})
    assert conn.execute("SELECT status FROM relation_hypotheses WHERE id=?", (hm,)).fetchone()[0] == "no_quotes"


def test_call_limit_pauses(env):
    cfg, conn = env
    _doc_with_text(cfg, conn, "synthetic:t:A", "<p>Eins.</p>")
    _doc_with_text(cfg, conn, "synthetic:t:B", "<p>Zwei.</p>")
    segment_all(cfg, conn)
    ua, ub = [r[0] for r in conn.execute("SELECT id FROM argument_units ORDER BY document_id")]
    cid = ensure_comparison(conn, ua, ub)
    ad = ReplayAdapter({"max_calls_per_run": 1}, ["{}", "{}"])
    assert analysis.compare(cfg, conn, cid, adapter=ad)["status"] != "not_run"
    assert analysis.compare(cfg, conn, cid, adapter=ad)["status"] == "not_run"


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
    by = {r["case"]: r for r in rep["cases"]}
    assert len(by) == 12
    for c in ("case05", "case06", "case08", "case11", "case12"):
        assert by[c]["deterministic_ok"], c
    assert by["case03"]["support"].startswith("ausdrücklich noch nicht unterstützt")
    assert all(r["model"] is None or r["model"]["model_part"] == "nicht ausgeführt" for r in rep["cases"])
    assert all(f["ok"] for f in rep["formal"])
    # Wiederholter Lauf erzeugt keine doppelten Versionen
    run_acceptance(cfg, conn, "none", "test-hash")
    assert all(f["ok"] for f in formal_checks(cfg, conn))
