"""Blindansicht: Suchhypothese und Modellurteile bleiben bis zum eigenen Urteil verborgen."""
import json

from susa import db
from susa.extract import html_to_canonical
from susa.search import ensure_comparison
from susa.segment import segment_all
from susa.versions import add_version
from susa.web.app import create_app


def test_blind_review_hides_until_own_judgment(env):
    cfg, conn = env
    ts = db.now()
    for did, txt in (("upstream:x:post:1", "Consciousness requires a body, so current models lack it."),
                     ("upstream:x:post:2", "Consciousness may not require a body if the right functional organisation exists.")):
        conn.execute("INSERT INTO documents(id, origin, is_synthetic, title, author, date, first_seen_at, updated_at) VALUES(?,?,?,?,?,?,?,?)",
                     (did, "upstream_json", 0, did, did[-1], "2026-01-0" + did[-1], ts, ts))
        add_version(cfg, conn, did, source="manual_file", source_url=None, status="manual_import", availability="full",
                    extracted=html_to_canonical(f"<p>{txt}</p>"))
    segment_all(cfg, conn)
    ua, ub = [r[0] for r in conn.execute("SELECT id FROM argument_units ORDER BY document_id")]
    cid = ensure_comparison(conn, ua, ub, "test")
    conn.execute("INSERT INTO review_sets(id, label, created_at) VALUES('rs-t','t',?)", (ts,))
    conn.execute("INSERT INTO review_set_items VALUES('rs-t',1,?,'widerspruch','GEHEIMER_GRUND')", (cid,))
    conn.execute("INSERT INTO reading_aids(unit_id, lang, text, author, method, source_text_sha256, created_at) VALUES(?,?,?,?,?,?,?)",
                 (ua, "de", "LESEHILFE_L", "test", "Zusammenfassung", db.sha256_text(conn.execute("SELECT text FROM argument_units WHERE id=?", (ua,)).fetchone()[0]), ts))
    conn.commit()
    client = create_app(cfg).test_client()
    html = client.get("/review-sets/rs-t/1?reviewer=anna").get_data(as_text=True)
    assert "LESEHILFE_L" in html and "kein Original" in html
    assert "GEHEIMER_GRUND" not in html and "widerspruch" not in html.split("Dein Urteil")[0]
    r = client.post("/review-sets/rs-t/1", data={"reviewer": "anna", "relation_types": ["challenges_assumption"],
                                                 "left_quotes": "Consciousness requires a body", "right_quotes": "may not require a body"})
    assert r.status_code == 302
    html = client.get("/review-sets/rs-t/1?reviewer=anna").get_data(as_text=True)
    assert "GEHEIMER_GRUND" in html and "Aufgedeckt" in html
    h = db.connect(cfg.db_path).execute("SELECT * FROM relation_hypotheses WHERE kind='manual_blind'").fetchone()
    assert h["author"] == "anna" and h["evidence_status"] == "anchored"
    assert json.loads(h["payload_json"])["blind"] is True
    # anderer Prüfer sieht weiterhin die Blindansicht
    assert "GEHEIMER_GRUND" not in client.get("/review-sets/rs-t/1?reviewer=ben").get_data(as_text=True)
    assert client.get("/budgets").status_code == 200
