"""Funktionstests für Budget, Schema-/Belegprüfung und Abnahmebewertung. Alle Antworten sind Replay-Antworten;
diese Tests sind KEINE Modellabnahme."""
import json

import pytest

from susa import analysis, db
from susa.acceptance import judge_compare, judge_reconstruct
from susa.embed import embed_units
from susa.extract import html_to_canonical
from susa.fixtures import cases, doc_id, load_fixtures
from susa.llm import Budget, CallLimitReached, ClaudeCLIAdapter, NotConfigured, ReplayAdapter, budget_status, create_budget, get_adapter
from susa.search import ensure_comparison
from susa.segment import segment_all
from susa.validate import validate_compare, validate_countercheck, validate_reconstruct
from susa.versions import add_version

CASES = {c["id"]: c for c in cases()}

L_TEXT = "Memory makes an agent consistent across sessions."
R_TEXT = "Memory can support consistency, but only if the agent revises conflicting memories."


def compare_payload(**over):
    p = {"shared_question": "Macht Gedächtnis konsistent?",
         "comparability": {"same_question": True, "definitions_compatible": True, "same_system_boundary": True,
                           "same_time_and_modality": True, "same_premises": None, "notes": ""},
         "relation_types": ["restricts_scope"], "left_claim": "Gedächtnis macht konsistent.", "right_claim": "Nur mit Revision.",
         "repeated_thought": None, "added_thought": "Revisionsbedingung", "contribution_kind": "reasoned_extension",
         "changes_conclusion_or_scope": True, "reasoning_present_in_text": True, "reasoning_summary": "B nennt Bedingung.",
         "left_quotes": ["Memory makes an agent consistent"], "right_quotes": ["only if the agent revises conflicting memories"],
         "alternative_readings": [], "uncertainties": [], "interpretation_confidence": "medium"}
    p.update(over)
    return p


def countercheck_payload(**over):
    p = {"decision": "confirmed", "problems_found": [], "corrected_relation_types": None, "corrected_added_thought": None,
         "needs_more_context": False, "reasoning": "passt", "left_quotes": ["Memory makes an agent consistent"],
         "right_quotes": ["only if the agent revises conflicting memories"]}
    p.update(over)
    return p


def _doc(cfg, conn, did, html, author):
    ts = db.now()
    conn.execute("INSERT INTO documents(id, origin, is_synthetic, author, date, title, first_seen_at, updated_at) VALUES(?,?,?,?,?,?,?,?)",
                 (did, "synthetic", 1, author, "2026-01-01", did, ts, ts))
    add_version(cfg, conn, did, source="synthetic_fixture", source_url=None, status="synthetic_fixture", availability="full",
                extracted=html_to_canonical(html))


@pytest.fixture
def pair(env):
    cfg, conn = env
    _doc(cfg, conn, "synthetic:t:A", f"<p>{L_TEXT}</p>", "A")
    _doc(cfg, conn, "synthetic:t:B", f"<p>{R_TEXT}</p>", "B")
    segment_all(cfg, conn)
    ua, ub = [r[0] for r in conn.execute("SELECT id FROM argument_units ORDER BY document_id")]
    return cfg, conn, ensure_comparison(conn, ua, ub)


def _hyp(conn, hid):
    return conn.execute("SELECT * FROM relation_hypotheses WHERE id=?", (hid,)).fetchone()


# ---------------------------------------------------------------- Budget

def test_budget_shared_across_adapter_instances_and_restart(pair, tmp_path):
    cfg, conn, cid = pair
    bid = create_budget(conn, "test", 3)
    ok = json.dumps(compare_payload())
    # drei verschiedene Adapterinstanzen, jede mit eigenem Antwortvorrat: zusammen nur 3 Aufrufe
    for _ in range(3):
        r = analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [ok], conn=conn, budget_id=bid), reuse=False)
        assert r["status"] == "anchored"
    # "Neustart": neue Verbindung, neuer Adapter
    conn2 = db.connect(cfg.db_path)
    r = analysis.compare(cfg, conn2, cid, adapter=ReplayAdapter({}, [ok], conn=conn2, budget_id=bid), reuse=False)
    assert r["status"] == "not_run" and "erschöpft" in r["reason"]
    st = budget_status(conn2, bid)
    assert st["used"] == 3 and st["by_outcome"] == {"success": 3, "refused_budget": 1}
    # kein neues Budget wurde angelegt
    assert conn2.execute("SELECT COUNT(*) FROM model_budgets").fetchone()[0] == 1


def test_budget_counts_failures_and_retries(pair):
    cfg, conn, cid = pair
    bid = create_budget(conn, "retry", 3)
    ad = ReplayAdapter({"max_retries": 1}, ["TRANSIENT 529", "TRANSIENT 529", json.dumps(compare_payload())], conn=conn, budget_id=bid)
    r = analysis.compare(cfg, conn, cid, adapter=ad, reuse=False)
    assert r["status"] == "model_error"  # zwei Versuche (Erstversuch + 1 Wiederholung), beide transient
    calls = conn.execute("SELECT attempt, outcome, error FROM model_calls WHERE budget_id=? ORDER BY id", (bid,)).fetchall()
    assert [(c["attempt"], c["outcome"]) for c in calls] == [(1, "error"), (2, "error")]
    assert all("transient" in c["error"] for c in calls)
    r = analysis.compare(cfg, conn, cid, adapter=ad, reuse=False)
    assert r["status"] == "anchored"
    assert budget_status(conn, bid)["used"] == 3
    with pytest.raises(CallLimitReached):
        Budget(conn, bid).reserve(adapter="replay", model=None, is_real=False, purpose="x", run_id=None, attempt=1,
                                  est_input_tokens=1, max_output_tokens=1)


def test_retry_cannot_exceed_budget(pair):
    cfg, conn, cid = pair
    bid = create_budget(conn, "tight", 1)
    ad = ReplayAdapter({"max_retries": 3}, ["TRANSIENT a", "TRANSIENT b", json.dumps(compare_payload())], conn=conn, budget_id=bid)
    r = analysis.compare(cfg, conn, cid, adapter=ad, reuse=False)
    assert r["status"] == "not_run" and "erschöpft" in r["reason"]
    assert budget_status(conn, bid)["used"] == 1


def test_real_adapter_requires_budget(env, monkeypatch):
    cfg, conn = env
    monkeypatch.setattr("shutil.which", lambda b: "/bin/true")
    with pytest.raises(NotConfigured):
        ClaudeCLIAdapter({"cli": "claude"}, conn=conn)
    with pytest.raises(NotConfigured):
        get_adapter({"adapter": "claude_cli"}, conn=conn, budget_id="gibt-es-nicht")


def test_reuse_within_budget_avoids_second_call(pair):
    cfg, conn, cid = pair
    bid = create_budget(conn, "reuse", 5)
    ad = ReplayAdapter({}, [json.dumps(compare_payload())], conn=conn, budget_id=bid)
    r1 = analysis.compare(cfg, conn, cid, adapter=ad)
    r2 = analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [], conn=conn, budget_id=bid))
    assert r2["reused"] and r2["hypothesis_id"] == r1["hypothesis_id"]
    assert budget_status(conn, bid)["used"] == 1


# ---------------------------------------------------------------- Schema und Belege

def test_valid_response_is_anchored(pair):
    cfg, conn, cid = pair
    r = analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [json.dumps(compare_payload())]))
    h = _hyp(conn, r["hypothesis_id"])
    assert (h["response_status"], h["schema_status"], h["anchor_status"], h["evidence_status"]) == ("received", "valid", "complete", "anchored")
    run = conn.execute("SELECT * FROM runs WHERE id=?", (h["run_id"],)).fetchone()
    assert run["is_real_model_run"] == 0


def test_missing_anchor_on_one_side(pair):
    cfg, conn, cid = pair
    r = analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [json.dumps(compare_payload(right_quotes=[]))]))
    h = _hyp(conn, r["hypothesis_id"])
    assert h["schema_status"] == "valid" and h["anchor_status"] == "missing_side" and h["evidence_status"] == "anchors_failed"


def test_fabricated_quote(pair):
    cfg, conn, cid = pair
    p = compare_payload(right_quotes=["only if the agent revises conflicting memories", "the agent is conscious"])
    h = _hyp(conn, analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [json.dumps(p)]))["hypothesis_id"])
    assert h["anchor_status"] == "incomplete" and h["evidence_status"] == "anchors_failed"
    qc = json.loads(h["quote_check_json"])
    assert [q["found"] for q in qc["right"]] == [True, False]


def test_quote_from_wrong_side_is_not_found(pair):
    cfg, conn, cid = pair
    p = compare_payload(left_quotes=["only if the agent revises conflicting memories"])  # steht nur rechts
    h = _hyp(conn, analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [json.dumps(p)]))["hypothesis_id"])
    assert h["evidence_status"] == "anchors_failed"


@pytest.mark.parametrize("mutate,expect", [
    (lambda p: p.pop("relation_types"), "relation_types: Pflichtfeld fehlt"),
    (lambda p: p.pop("left_quotes"), "left_quotes: Pflichtfeld fehlt"),
    (lambda p: p.update(relation_types="extends"), "relation_types: Typ str"),
    (lambda p: p.update(relation_types=[]), "mindestens 1"),
    (lambda p: p.update(changes_conclusion_or_scope="yes"), "changes_conclusion_or_scope: Typ str"),
    (lambda p: p.update(interpretation_confidence=0.8), "interpretation_confidence: Typ float"),
    (lambda p: p.update(contribution_kind="brilliant"), "unzulässiger Wert"),
    (lambda p: p.update(left_quotes=[1, 2]), "kein String"),
    (lambda p: p.pop("comparability"), "comparability"),
])
def test_schema_errors(pair, mutate, expect):
    cfg, conn, cid = pair
    p = compare_payload()
    mutate(p)
    h = _hyp(conn, analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [json.dumps(p)]))["hypothesis_id"])
    errs = json.loads(h["schema_errors_json"])
    assert h["schema_status"] == "invalid" and h["evidence_status"] == "schema_invalid"
    assert any(expect in e for e in errs), errs


def test_unknown_relation_type_is_schema_error_not_dropped(pair):
    cfg, conn, cid = pair
    p = compare_payload(relation_types=["restricts_scope", "deeply_insightful"])
    h = _hyp(conn, analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [json.dumps(p)]))["hypothesis_id"])
    assert h["evidence_status"] == "schema_invalid"
    assert "deeply_insightful" in json.loads(h["relation_types_json"])  # bleibt sichtbar
    assert any("deeply_insightful" in e for e in json.loads(h["schema_errors_json"]))


def test_empty_or_non_json_response(pair):
    cfg, conn, cid = pair
    for text in ["", "Ich denke, B erweitert A.", "[1, 2]", "{}"]:
        h = _hyp(conn, analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [text]))["hypothesis_id"])
        assert h["evidence_status"] in ("no_response", "schema_invalid"), text


def test_abstention_is_allowed_but_not_anchored(pair):
    cfg, conn, cid = pair
    p = compare_payload(relation_types=["insufficient_context"], left_quotes=[], right_quotes=[], contribution_kind="unclear")
    h = _hyp(conn, analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [json.dumps(p)]))["hypothesis_id"])
    assert h["schema_status"] == "valid" and h["evidence_status"] == "abstention" and h["judgment"] == "abstention"
    # Enthaltung mit erfundenem Zitat ist trotzdem ein Belegfehler
    p = compare_payload(relation_types=["unresolved"], left_quotes=["erfunden"], right_quotes=[])
    h = _hyp(conn, analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [json.dumps(p)]))["hypothesis_id"])
    assert h["evidence_status"] == "anchors_failed"


# ---------------------------------------------------------------- Gegenprüfung

def test_countercheck_confirmed_with_invalid_anchors_is_not_confirmed(pair):
    cfg, conn, cid = pair
    hid = analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [json.dumps(compare_payload())]))["hypothesis_id"]
    bad = countercheck_payload(left_quotes=["steht nirgends"], right_quotes=[])
    c = analysis.countercheck(cfg, conn, hid, adapter=ReplayAdapter({}, [json.dumps(bad)]))
    assert c["decision"] == "confirmed" and c["status"] == "anchors_failed"


def test_countercheck_confirming_unanchored_parent_is_not_confirmed(pair):
    cfg, conn, cid = pair
    hid = analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [json.dumps(compare_payload(right_quotes=[]))]))["hypothesis_id"]
    assert _hyp(conn, hid)["evidence_status"] == "anchors_failed"
    c = analysis.countercheck(cfg, conn, hid, adapter=ReplayAdapter({}, [json.dumps(countercheck_payload())]))
    assert c["decision"] == "confirmed" and c["status"] == "anchors_failed"


def test_countercheck_valid_and_schema(pair):
    cfg, conn, cid = pair
    hid = analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [json.dumps(compare_payload())]))["hypothesis_id"]
    assert analysis.countercheck(cfg, conn, hid, adapter=ReplayAdapter({}, [json.dumps(countercheck_payload())]))["status"] == "anchored"
    assert validate_countercheck(countercheck_payload(decision="maybe"))
    assert validate_countercheck({k: v for k, v in countercheck_payload().items() if k != "needs_more_context"})


# ---------------------------------------------------------------- Rekonstruktion und Sprecher (Fall 6)

def claim(text, role, quotes, types=("empirical",), premises=()):
    return {"claim": text, "speaker_role": role, "statement_types": list(types), "subject": "s", "system_considered": None,
            "time_reference": "unspecified", "scope": None, "modality": None, "explicit_definitions": [], "explicit_premises": [],
            "reconstructed_premises": list(premises), "reasons": [], "qualifications": [], "conclusion": None, "quotes": quotes,
            "alternative_readings": []}


@pytest.fixture
def case6(env):
    cfg, conn = env
    load_fixtures(cfg, conn)
    segment_all(cfg, conn)
    embed_units(cfg, conn, "test-hash")
    u = conn.execute("SELECT * FROM argument_units WHERE document_id=?", (doc_id("case06", "A"),)).fetchone()
    return cfg, conn, u


def _judge6(cfg, conn, u, payload):
    r = analysis.reconstruct(cfg, conn, u["id"], adapter=ReplayAdapter({}, [json.dumps(payload)]))
    cc = conn.execute("SELECT * FROM claim_candidates WHERE id=?", (r["claim_candidate_id"],)).fetchone()
    return judge_reconstruct(cfg, conn, CASES["case06"], "de", cc)


def test_speaker_correct(case6):
    cfg, conn, u = case6
    p = {"status": "ok", "missing_information": [], "claims": [
        claim("Manche behaupten, Sprachmodelle können leiden.", "quoted_other", ["Sprachmodelle können leiden."]),
        claim("Der Autor sieht keinen hinreichenden Beleg dafür.", "author", ["Dafür sehe ich hier keinen hinreichenden Beleg."])]}
    j = _judge6(cfg, conn, u, p)
    assert j["result"] == "bestanden", j


def test_speaker_empty_claims_fail(case6):
    cfg, conn, u = case6
    assert validate_reconstruct({"status": "ok", "missing_information": [], "claims": []})
    j = _judge6(cfg, conn, u, {"status": "ok", "missing_information": [], "claims": []})
    assert j["result"] == "gescheitert"


def test_speaker_formally_valid_but_wrong_attribution(case6):
    cfg, conn, u = case6
    p = {"status": "ok", "missing_information": [], "claims": [
        claim("Sprachmodelle können leiden.", "author", ["Sprachmodelle können leiden."]),
        claim("Kein Beleg.", "author", ["Dafür sehe ich hier keinen hinreichenden Beleg."])]}
    j = _judge6(cfg, conn, u, p)
    assert j["evidence_status"] == "anchored"  # formal einwandfrei …
    assert j["result"] == "gescheitert"        # … inhaltlich falsch
    assert any("Fremdposition" in n for n in j["notes"])


def test_speaker_missing_own_objection(case6):
    cfg, conn, u = case6
    p = {"status": "ok", "missing_information": [], "claims": [
        claim("Manche behaupten, Sprachmodelle können leiden.", "quoted_other", ["Sprachmodelle können leiden."])]}
    j = _judge6(cfg, conn, u, p)
    assert j["result"] == "gescheitert" and any("Einwand" in n for n in j["notes"])


def test_reconstruct_fabricated_quote_fails(case6):
    cfg, conn, u = case6
    p = {"status": "ok", "missing_information": [], "claims": [
        claim("x", "quoted_other", ["Sprachmodelle können leiden."]), claim("y", "author", ["Ich halte das für bewiesen."])]}
    j = _judge6(cfg, conn, u, p)
    assert j["evidence_status"] == "anchors_failed" and j["result"] == "gescheitert"


def test_reconstruct_insufficient_context_is_undecidable(case6):
    cfg, conn, u = case6
    j = _judge6(cfg, conn, u, {"status": "insufficient_context", "missing_information": ["Kontext"], "claims": []})
    assert j["result"] == "unentscheidbar"


# ---------------------------------------------------------------- Abnahmebewertung Paarvergleich

def test_judge_compare_requires_expected_content(pair):
    cfg, conn, cid = pair
    hid = analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [json.dumps(compare_payload(relation_types=["contradicts_under_shared_scope"]))]))["hypothesis_id"]
    j = judge_compare(conn, CASES["case02"], _hyp(conn, hid))
    assert j["result"] == "gescheitert" and j["run_kind"] == "replay"
    hid = analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [json.dumps(compare_payload(relation_types=["apparent_conflict_due_to_definition"]))]), reuse=False)["hypothesis_id"]
    assert judge_compare(conn, CASES["case02"], _hyp(conn, hid))["result"] == "bestanden"
    hid = analysis.compare(cfg, conn, cid, adapter=ReplayAdapter({}, [json.dumps(compare_payload(relation_types=["apparent_conflict_due_to_definition"], right_quotes=[]))]), reuse=False)["hypothesis_id"]
    assert judge_compare(conn, CASES["case02"], _hyp(conn, hid))["result"] == "gescheitert"


def test_subscription_guard_blocks_after_overage_or_missing_rate_limit(tmp_path, monkeypatch):
    """Nach einem Aufruf, der nutzbare Zusatznutzung meldet oder keine Rate-Limit-Angaben hat, wird nicht weiter aufgerufen."""
    from susa.llm import check_subscription_only
    conn = db.connect(tmp_path / "t.sqlite")
    bid = create_budget(conn, "t", 4, adapter="claude_cli")
    for usage in ({"rate_limit_info": {"status": "allowed", "overageStatus": "rejected", "overageDisabledReason": "org_level_disabled"}},):
        conn.execute("INSERT INTO model_calls(budget_id, attempt, adapter, is_real_service, started_at, outcome, usage_json) VALUES(?,?,?,?,?,?,?)",
                     (bid, 1, "claude_cli", 1, db.now(), "success", json.dumps(usage)))
    conn.commit()
    base = [p for p in check_subscription_only("claude-gibt-es-nicht", conn, bid) if p.startswith("Aufruf")]
    assert base == []
    conn.execute("INSERT INTO model_calls(budget_id, attempt, adapter, is_real_service, started_at, outcome, usage_json) VALUES(?,?,?,?,?,?,?)",
                 (bid, 1, "claude_cli", 1, db.now(), "success", json.dumps({"rate_limit_info": {"status": "allowed", "overageStatus": "allowed"}})))
    conn.execute("INSERT INTO model_calls(budget_id, attempt, adapter, is_real_service, started_at, outcome, usage_json) VALUES(?,?,?,?,?,?,?)",
                 (bid, 1, "claude_cli", 1, db.now(), "success", json.dumps({})))
    conn.commit()
    p = [x for x in check_subscription_only("claude-gibt-es-nicht", conn, bid) if x.startswith("Aufruf")]
    assert len(p) == 2 and "Zusatznutzung" in p[0] and "ohne Rate-Limit" in p[1]


def test_quota_guard_pauses_before_exhausted_window(tmp_path):
    from susa.llm import quota_problems
    conn = db.connect(tmp_path / "q.sqlite")
    bid = create_budget(conn, "q", 2, adapter="claude_cli")
    rl = {"status": "allowed", "resetsAt": 2000, "unifiedWindows": {"five_hour": {"status": "allowed", "resetsAt": 2000, "utilization": 0.97},
                                                                     "seven_day": {"status": "allowed", "resetsAt": 9000, "utilization": 0.3}}}
    conn.execute("INSERT INTO model_calls(budget_id, attempt, adapter, is_real_service, started_at, outcome, usage_json) VALUES(?,?,?,?,?,?,?)",
                 (bid, 1, "claude_cli", 1, db.now(), "success", json.dumps({"rate_limit_info": rl})))
    conn.commit()
    assert len(quota_problems(conn, now=1000)) == 1 and "five_hour" in quota_problems(conn, now=1000)[0]
    assert quota_problems(conn, now=3000) == []  # Fenster zurückgesetzt


def test_run_pair_resumes_after_side_a(tmp_path, monkeypatch):
    """Abbruch nach Seite A: bei der Fortsetzung wird nur Seite B aufgerufen."""
    from susa import br_bridge
    p = {"A": {"document": "a", "document_sha256": "ha"}, "B": {"document": "b", "document_sha256": "hb"}}
    monkeypatch.setattr(br_bridge, "passage", lambda cfg, conn, uid: p[uid])
    calls = []

    def fake(adapter, key, pp, run_id):
        calls.append(key)
        if key == "B" and calls.count("B") == 1:
            raise CallLimitReached("Budget")
        return {"dossier": {"claims": []}, "call_id": len(calls)}
    monkeypatch.setattr(br_bridge, "extract_side", fake)
    with pytest.raises(CallLimitReached):
        br_bridge.run_pair(None, None, None, "A", "B", 1, tmp_path, relations=False)
    br_bridge.run_pair(None, None, None, "A", "B", 1, tmp_path, relations=False)
    assert calls == ["A", "B", "B"] and (tmp_path / "run-1.json").exists()
