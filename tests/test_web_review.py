"""Blindprüfung mit separaten Testdaten (keine echten Pilottexte, keine Urteile in der echten Prüfauswahl)."""
import json

import pytest

from susa import db
from susa import review_set as rs
from susa.blind_html import build_payload, export_html, import_judgments
from susa.config import Config
from susa.extract import html_to_canonical
from susa.search import ensure_comparison
from susa.segment import segment_all
from susa.versions import add_version, current_version, read_text
from susa.web.app import create_app

TEXTS = {
    "upstream:t:post:1": ("<h2>Kopf eins</h2><p>Consciousness requires a body, so current models lack it.</p><p>Context after one.</p>"),
    "upstream:t:post:2": ("<p>Context before two.</p><p>Consciousness may not require a body if the right functional organisation exists.</p>"),
}
SECRETS = ["AUTOR_GEHEIM", "PUB_GEHEIM", "TITEL_GEHEIM", "HYPOTHESE_GEHEIM", "GRUND_GEHEIM", "MODELLURTEIL_GEHEIM", "LESEHILFE_GEHEIM",
           "2026-01-05", "https://geheim.example", "experience_now"]


def build(cfg, conn, texts=TEXTS):
    ts = db.now()
    for i, (did, html) in enumerate(texts.items(), 1):
        conn.execute("""INSERT INTO documents(id, origin, is_synthetic, title, author, publication, date, canonical_url, upstream_payload,
                        first_seen_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                     (did, "upstream_json", 0, f"TITEL_GEHEIM {i}", f"AUTOR_GEHEIM {i}", "PUB_GEHEIM", "2026-01-05",
                      f"https://geheim.example/{i}", json.dumps({"reactions": 4711}), ts, ts))
        conn.execute("INSERT INTO upstream_codes(document_id, experience_now) VALUES(?, 'yes')", (did,))
        add_version(cfg, conn, did, source="manual_file", source_url=None, status="manual_import", availability="full",
                    extracted=html_to_canonical(html))
    segment_all(cfg, conn)
    ua = conn.execute("SELECT id FROM argument_units WHERE document_id='upstream:t:post:1' AND text LIKE 'Consciousness%'").fetchone()[0]
    ub = conn.execute("SELECT id FROM argument_units WHERE document_id='upstream:t:post:2'").fetchone()[0]
    cid = ensure_comparison(conn, ua, ub, "test")
    conn.execute("UPDATE candidate_comparisons SET scores_json=? WHERE id=?", (json.dumps({"semantic": {"score": 0.987654, "rank": 1}}), cid))
    conn.execute("INSERT INTO review_sets(id, label, created_at) VALUES('rs-test','Testauswahl',?)", (ts,))
    conn.execute("INSERT INTO review_set_items VALUES('rs-test',1,?,'HYPOTHESE_GEHEIM','GRUND_GEHEIM')", (cid,))
    conn.execute("""INSERT INTO relation_hypotheses(id, comparison_id, kind, status, relation_types_json, payload_json, created_at, evidence_status)
                    VALUES('rel-x', ?, 'model_primary', 'anchored', '["MODELLURTEIL_GEHEIM"]', '{}', ?, 'anchored')""", (cid, ts))
    conn.execute("INSERT INTO reading_aids(unit_id, lang, text, author, method, source_text_sha256, created_at) VALUES(?,?,?,?,?,?,?)",
                 (ua, "de", "LESEHILFE_GEHEIM", "t", "t", "x", ts))
    conn.commit()
    rs.freeze(conn, "rs-test")
    return ua, ub, cid


def translations_for(cfg, conn, sid="rs-test"):
    entries = []
    for it in rs.set_items(conn, sid):
        for side, uid in (("A", it["left_unit_id"]), ("B", it["right_unit_id"])):
            v = rs.side_view(cfg, conn, uid)
            for sg in v["segments"]:
                if sg["text"]:
                    entries.append({"position": it["position"], "side": side, "segment": sg["name"], "document_id": v["document_id"],
                                    "version_text_sha256": v["version_text_sha256"], "start_char": sg["start"], "end_char": sg["end"],
                                    "source_sha256": sg["source_sha256"], "de": f"ÜBERSETZUNG {side} {sg['name']}", "notes": ["Hinweis"]})
    return {"translation_set": "tr-test", "lang": "de", "method": "Test", "created_by": "Test", "created_at": db.now(),
            "review_status": "ungeprüft", "entries": entries}


@pytest.fixture
def app_env(env, monkeypatch):
    cfg, conn = env
    ids = build(cfg, conn)
    rs.load_translations(cfg, conn, translations_for(cfg, conn))

    def boom(*a, **k):
        raise AssertionError("Modellaufruf in der Blindprüfung")
    monkeypatch.setattr("susa.llm.get_adapter", boom)
    monkeypatch.setattr("susa.analysis.compare", boom)
    monkeypatch.setattr("susa.analysis.reconstruct", boom)
    monkeypatch.setattr("susa.analysis.countercheck", boom)
    return cfg, conn, ids, create_app(cfg).test_client()


def page(client, reviewer="anna"):
    return client.get(f"/review-sets/rs-test/1?reviewer={reviewer}").get_data(as_text=True)


def test_blind_view_hides_everything_until_free_judgment(app_env):
    cfg, conn, _, client = app_env
    html = page(client)
    for s in SECRETS:
        assert s not in html, s
    assert "0.9876" not in html and "4711" not in html
    assert "ÜBERSETZUNG A core" in html and "ÜBERSETZUNG A before" in html and "ÜBERSETZUNG B core" in html and "kein Original" in html
    assert "Passage A" in html and "Passage B" in html
    for label in rs.VERDICTS.values():
        assert label in html
    assert "Etiketten speichern" not in html  # Etiketten erst nach dem freien Urteil


def test_labels_require_free_judgment_first(app_env):
    cfg, conn, _, client = app_env
    r = client.post("/review-sets/rs-test/1", data={"reviewer": "anna", "action": "labels", "relation_types": ["extends"]})
    assert "Zuerst das freie Urteil" in r.get_data(as_text=True)
    assert conn.execute("SELECT COUNT(*) FROM blind_judgments").fetchone()[0] == 0


@pytest.mark.parametrize("verdict", ["difference", "no_relevant_difference", "undecidable"])
def test_all_verdicts_equal(app_env, verdict):
    cfg, conn, _, client = app_env
    r = client.post("/review-sets/rs-test/1", data={"reviewer": "anna", "action": "free", "verdict": verdict, "q1": "A sagt x."})
    assert r.status_code == 302
    row = conn.execute("SELECT * FROM blind_judgments").fetchone()
    assert row["verdict"] == verdict and row["stage"] == "free"


def test_free_judgment_needs_answer_and_verdict(app_env):
    cfg, conn, _, client = app_env
    client.post("/review-sets/rs-test/1", data={"reviewer": "anna", "action": "free", "verdict": "undecidable"})
    client.post("/review-sets/rs-test/1", data={"reviewer": "anna", "action": "free", "q1": "x"})
    assert conn.execute("SELECT COUNT(*) FROM blind_judgments").fetchone()[0] == 0


def test_flow_append_only_reveal_and_no_model_calls(app_env):
    cfg, conn, _, client = app_env
    runs_before = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    client.post("/review-sets/rs-test/1", data={"reviewer": "anna", "action": "free", "verdict": "difference", "q1": "A: Körper nötig.",
                                                "q4": "B nennt Bedingung.", "quotes_a": "requires a body", "quotes_b": "steht nicht im Text",
                                                "flags": ["context_missing"]})
    free = conn.execute("SELECT * FROM blind_judgments WHERE stage='free'").fetchone()
    qc = json.loads(free["quote_check_json"])
    assert qc["a"][0]["found"] and not qc["b"][0]["found"]
    assert json.loads(free["flags_json"]) == ["context_missing"]
    state = json.loads(free["source_state_json"])
    assert state["a"]["segments"]["core"]["translation_set"] == "tr-test"
    html = page(client)
    assert "Etiketten speichern" in html and "AUTOR_GEHEIM" not in html  # nach Urteil: Etiketten ja, Metadaten erst nach Aufdecken
    # zweites freies Urteil wird abgelehnt
    client.post("/review-sets/rs-test/1", data={"reviewer": "anna", "action": "free", "verdict": "undecidable", "q1": "neu"})
    assert conn.execute("SELECT COUNT(*) FROM blind_judgments WHERE stage='free'").fetchone()[0] == 1
    client.post("/review-sets/rs-test/1", data={"reviewer": "anna", "action": "labels", "relation_types": ["refines", "erfunden"]})
    client.post("/review-sets/rs-test/1", data={"reviewer": "anna", "action": "correction", "text": "doch unklar", "verdict": "undecidable"})
    client.post("/review-sets/rs-test/1", data={"reviewer": "anna", "action": "reveal"})
    client.post("/review-sets/rs-test/1", data={"reviewer": "anna", "action": "labels", "relation_types": ["extends"]})
    rows = conn.execute("SELECT * FROM blind_judgments ORDER BY id").fetchall()
    assert [r["stage"] for r in rows] == ["free", "labels", "correction", "reveal", "labels"]
    assert json.loads(rows[1]["relation_types_json"]) == ["refines"]
    assert rows[2]["parent_id"] == rows[0]["id"] and rows[0]["verdict"] == "difference"  # Original unverändert
    assert [r["revealed_before"] for r in rows] == [0, 0, 0, 0, 1]
    with pytest.raises(Exception):
        conn.execute("UPDATE blind_judgments SET verdict='undecidable' WHERE id=?", (rows[0]["id"],))
    with pytest.raises(Exception):
        conn.execute("DELETE FROM blind_judgments")
    conn.rollback()
    html = page(client)
    for s in ("AUTOR_GEHEIM", "PUB_GEHEIM", "HYPOTHESE_GEHEIM", "GRUND_GEHEIM", "MODELLURTEIL_GEHEIM", "LESEHILFE_GEHEIM"):
        assert s in html, s
    assert "AUTOR_GEHEIM" not in page(client, "ben")  # anderer Prüfer bleibt blind
    assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == runs_before
    assert conn.execute("SELECT COUNT(*) FROM model_calls").fetchone()[0] == 0


def test_translation_not_shown_for_changed_original(app_env):
    cfg, conn, (ua, ub, cid), client = app_env
    # Ladeversuch mit falschem Hash wird gemeldet und nicht übernommen
    bad = translations_for(cfg, conn)
    bad["translation_set"] = "tr-bad"
    bad["entries"][0]["source_sha256"] = "0" * 64
    res = rs.load_translations(cfg, conn, bad)
    assert res["mismatch"] and res["mismatch"][0]["reason"].startswith("Quellsegment")
    # Original ändert sich (neue Textversion): alte Übersetzung darf nicht angezeigt werden
    add_version(cfg, conn, "upstream:t:post:2", source="manual_file", source_url=None, status="manual_import", availability="full",
                extracted=html_to_canonical("<p>Context before two.</p><p>Consciousness may not require a body at all.</p>"))
    segment_all(cfg, conn)
    new_u = conn.execute("""SELECT u.id FROM argument_units u JOIN document_versions v ON v.id=u.version_id
                            WHERE v.is_current=1 AND u.document_id='upstream:t:post:2'""").fetchone()[0]
    v = rs.side_view(cfg, conn, new_u)
    assert all(sg["translation"] is None for sg in v["segments"])
    # Prüfauswahl selbst zeigt weiter die verankerte alte Version, aber verify meldet die veraltete Textversion
    findings = rs.side_view(cfg, conn, ub)["findings"]
    assert any("nicht mehr die aktuelle" in f for f in findings)


def test_set_is_frozen(app_env):
    cfg, conn, _, _ = app_env
    with pytest.raises(rs.SetFrozen):
        rs.create_set(conn, "x", set_id="rs-test")
    data = rs.export_set_file(conn, "rs-test")
    assert rs.import_set(conn, data) == "rs-test"  # identisch: in Ordnung
    data["items"][0]["selection_reason"] = "anders"
    with pytest.raises(rs.SetFrozen):
        rs.import_set(conn, data)
    with pytest.raises(rs.SetFrozen):
        rs.create_set(conn, "v2", set_id="rs-test-v2", supersedes="rs-test")  # ohne Begründung


def test_rebuild_loads_same_passages_and_translations(app_env, tmp_path):
    cfg, conn, _, _ = app_env
    set_file = rs.export_set_file(conn, "rs-test")
    tr = translations_for(cfg, conn)
    before = build_payload(cfg, conn, "rs-test")
    # Neuaufbau in einem anderen Verzeichnis mit absichtlich anderer Reihenfolge (andere lokale IDs)
    cfg2 = Config.load(tmp_path / "neu")
    conn2 = db.connect(cfg2.db_path)
    ts = db.now()
    conn2.execute("INSERT INTO documents(id, origin, is_synthetic, first_seen_at, updated_at) VALUES('upstream:t:post:0','manual',0,?,?)", (ts, ts))
    add_version(cfg2, conn2, "upstream:t:post:0", source="manual_file", source_url=None, status="manual_import", availability="full",
                extracted=html_to_canonical("<p>Anderes Dokument zuerst.</p>"))
    for did, html in reversed(list(TEXTS.items())):
        conn2.execute("""INSERT INTO documents(id, origin, is_synthetic, title, author, publication, date, canonical_url, upstream_payload,
                         first_seen_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                      (did, "upstream_json", 0, "T", "A", "P", "2026-01-05", "u", "{}", ts, ts))
        add_version(cfg2, conn2, did, source="manual_file", source_url=None, status="manual_import", availability="full",
                    extracted=html_to_canonical(html))
    segment_all(cfg2, conn2)
    assert rs.import_set(conn2, set_file) == "rs-test"
    assert rs.load_translations(cfg2, conn2, tr)["mismatch"] == []
    after = build_payload(cfg2, conn2, "rs-test")
    strip = lambda p: [[(sg["text"], sg["de"]) for k in ("A", "B") for sg in it["sides"][k]["segments"]] for it in p["items"]]
    assert strip(before) == strip(after)
    assert [it["sides"]["A"]["source_state"]["version_text_sha256"] for it in before["items"]] == \
           [it["sides"]["A"]["source_state"]["version_text_sha256"] for it in after["items"]]
    assert all(r["ok"] for r in rs.verify_set(cfg2, conn2, "rs-test"))


def test_html_export_and_import_roundtrip(app_env, tmp_path):
    cfg, conn, _, _ = app_env
    out = tmp_path / "blind.html"
    export_html(cfg, conn, "rs-test", out)
    html = out.read_text("utf-8")
    for s in ("HYPOTHESE_GEHEIM", "GRUND_GEHEIM", "MODELLURTEIL_GEHEIM", "LESEHILFE_GEHEIM", "0.9876", "experience_now"):
        assert s not in html, s
    assert "ÜBERSETZUNG A core" in html and "<script src" not in html and "http" not in html.split("<script id=\"data\"")[0].replace("https://geheim.example", "")
    payload = build_payload(cfg, conn, "rs-test")
    st = {"a": payload["items"][0]["sides"]["A"]["source_state"], "b": payload["items"][0]["sides"]["B"]["source_state"]}
    entries = [{"client_id": "c1", "position": 1, "reviewer": "anna", "stage": "free", "verdict": "no_relevant_difference",
                "answers": {"q1": "x"}, "flags": [], "quotes": {"a": ["requires a body"], "b": []}, "created_at": "2026-11-04T10:00:00Z", "source_state": st},
               {"client_id": "c2", "position": 1, "reviewer": "anna", "stage": "labels", "relation_types": ["repeats"],
                "answers": {}, "created_at": "2026-11-04T10:01:00Z", "source_state": st},
               {"client_id": "c3", "position": 1, "reviewer": "ben", "stage": "free", "verdict": "undecidable", "answers": {"q6": "unklar"},
                "created_at": "2026-11-04T10:02:00Z", "source_state": {"a": st["a"], "b": {**st["b"], "version_text_sha256": "anders"}}}]
    data = {"format": "susa-blind-judgments/1", "set_id": "rs-test", "items_sha256": payload["items_sha256"], "entries": entries}
    res = import_judgments(cfg, conn, data)
    assert res["imported"] == 2 and len(res["rejected"]) == 1 and "Quellstand" in res["rejected"][0]["reason"]
    assert import_judgments(cfg, conn, data)["skipped_duplicate"] == 2
    rows = conn.execute("SELECT * FROM blind_judgments WHERE origin='html_import' ORDER BY id").fetchall()
    assert [r["stage"] for r in rows] == ["free", "labels"]
    assert json.loads(rows[0]["quote_check_json"])["a"][0]["found"]
