"""Gezielte Tests der aus Budget-Review übernommenen bzw. angebundenen Funktionen (Replay, kein Modellaufruf)."""
import ast
import json
from pathlib import Path

import pytest

from susa import analysis, br_bridge, db, vendor_br
from susa.extract import html_to_canonical
from susa.llm import ReplayAdapter
from susa.segment import segment_all
from susa.versions import add_version

BR_CHECKOUT = Path("/home/user/Budget-Review")

A_HTML = "<p>Context before A.</p><p>Memory makes an agent consistent across sessions. It does not make it conscious.</p><p>After A.</p>"
B_HTML = "<p>Before B.</p><p>Memory can support consistency, but only if the agent revises conflicting memories.</p><p>After B.</p>"


@pytest.fixture
def pair(env):
    cfg, conn = env
    ts = db.now()
    for did, html in (("synthetic:br:A", A_HTML), ("synthetic:br:B", B_HTML)):
        conn.execute("INSERT INTO documents(id, origin, is_synthetic, title, first_seen_at, updated_at) VALUES(?,?,?,?,?,?)",
                     (did, "synthetic", 1, did, ts, ts))
        add_version(cfg, conn, did, source="synthetic_fixture", source_url=None, status="synthetic_fixture", availability="full",
                    extracted=html_to_canonical(html))
    cfg.data["segment"]["min_tokens"] = 1  # jede Absatzgrenze bleibt eine Einheit
    segment_all(cfg, conn)
    ua = conn.execute("SELECT id FROM argument_units WHERE document_id='synthetic:br:A' AND text LIKE 'Memory%'").fetchone()[0]
    ub = conn.execute("SELECT id FROM argument_units WHERE document_id='synthetic:br:B' AND text LIKE 'Memory%'").fetchone()[0]
    return cfg, conn, ua, ub


def claim(pid, ctype, content, span, conf=0.9):
    return {"proposal_id": pid, "claim_type": ctype, "canonical_content": content, "raw_span": span, "confidence": conf, "source_ref": "x"}


def test_check_quotes_uses_budget_review_anchoring(pair):
    cfg, conn, ua, _ = pair
    c = analysis.unit_context(cfg, conn, ua)
    qc = analysis.check_quotes(conn, c, ["Memory makes an  agent\n consistent", "„It does not make it conscious.“",
                                         "Memory makes agents consistent", "memory makes an agent"], create_spans=False)
    assert [q["found"] for q in qc] == [True, True, False, False]  # Leerraum ja, Umformulierung/Kleinschreibung nein
    assert qc[0]["method"] == "whitespace_normalized"
    assert c["text"][qc[0]["start_char"]:qc[0]["end_char"]] == "Memory makes an agent consistent"  # Zeichen des Dokuments
    assert qc[0]["end_char"] - qc[0]["start_char"] == len("Memory makes an agent consistent")  # nicht die Länge des Modellzitats
    assert qc[1]["method"] == "outer_quotes_removed"


def test_extract_side_gate_and_core_coverage(pair):
    cfg, conn, ua, _ = pair
    p = br_bridge.passage(cfg, conn, ua)
    reply = {"claims": [claim("C01", "fact", "Memory makes an agent consistent across sessions.", "Memory makes an agent  consistent\nacross sessions."),
                        claim("C02", "fact", "Memory does not make an agent conscious.", "It does not make it conscious."),
                        claim("C03", "fact", "Paraphrase.", "Memory renders agents consistent."),
                        claim("C04", "conclusion", "Unknown type.", "After A."),
                        claim("C05", "fact", "Context.", "Context before A.", conf=0.3)],
             "relations": [{"source_id": "C02", "relation_type": "QUALIFIES", "target_id": "C01", "confidence": 0.8, "rationale": "r"}]}
    side = br_bridge.extract_side(ReplayAdapter({}, [json.dumps(reply)]), "A", p, "r1")
    d = side["dossier"]
    assert [c["proposal_id"] for c in d["claims"]] == ["C01", "C02"]
    reasons = {r["item_id"]: r["reason"] for r in d["rejections"]}
    assert reasons["C03"] == "source_span_not_found"
    assert reasons["C05"] == "confidence_below_floor"
    assert any("unknown claim_type" in r["reason"] for r in d["rejections"])  # C04 fällt mit Grund, der Rest bleibt
    assert d["claims"][0]["anchor_normalised"] is True and d["claims"][0]["raw_span"] == "Memory makes an agent consistent across sessions."
    assert len(d["relations"]) == 1
    cov = side["core_coverage"]
    assert cov["ratio"] == 1.0 and cov["gaps"] == []
    assert side["error"] is None and side["prompt_hash"]


def test_cross_relations_admitted_by_gate(pair):
    cfg, conn, ua, ub = pair
    pa, pb = br_bridge.passage(cfg, conn, ua), br_bridge.passage(cfg, conn, ub)
    sa = br_bridge.extract_side(ReplayAdapter({}, [json.dumps({"claims": [claim("C01", "fact", "Memory makes an agent consistent.", "Memory makes an agent consistent across sessions.")], "relations": []})]), "A", pa, "r")
    sb = br_bridge.extract_side(ReplayAdapter({}, [json.dumps({"claims": [claim("C01", "limitation", "Only if the agent revises conflicting memories.", "but only if the agent revises conflicting memories")], "relations": []})]), "B", pb, "r")
    rel_reply = {"claims": [], "relations": [
        {"source_id": "B-C01", "relation_type": "QUALIFIES", "target_id": "A-C01", "confidence": 0.8, "rationale": "condition"},
        {"source_id": "B-C99", "relation_type": "SUPPORTS", "target_id": "A-C01", "confidence": 0.8, "rationale": "invented id"},
        {"source_id": "B-C01", "relation_type": "REFINES", "target_id": "A-C01", "confidence": 0.8, "rationale": "not in vocabulary"},
        {"source_id": "A-C01", "relation_type": "SUPPORTS", "target_id": "A-C01", "confidence": 0.8, "rationale": "self"}]}
    rel = br_bridge.cross_relations(ReplayAdapter({}, [json.dumps(rel_reply)]), pa, pb, sa, sb, "r")
    assert rel["dropped_unknown_ids"] == ["B-C99->A-C01"]
    assert [(r["source"], r["type"], r["target"], r["cross"]) for r in rel["relations"]] == [("B-C01", "QUALIFIES", "A-C01", True)]
    reasons = [r["reason"] for r in rel["rejections"]]
    assert any("unknown relation_type: REFINES" in r for r in reasons) and "self_relation" in reasons


def test_meaning_scorer_catches_dropped_condition():
    doc = "Before. Memory can support consistency, but only if the agent revises conflicting memories. After."
    span = "Memory can support consistency, but only if the agent revises conflicting memories."
    case = {"case_id": "t", "pair_id": "t", "language": "en", "phenomenon": "condition", "document": doc, "span": span,
            "requires_all_groups": [["only if", "if", "provided"], ["can", "may", "could"]], "forbids": [r"\bmemory (makes|ensures)\b"],
            "forbidden_readings": ["Memory supports consistency."], "min_claims_on_span": 1}
    assert [p for p in vendor_br.validate([case]) if "languages" not in p] == []
    s0 = doc.index(span)
    good = [{"canonical_content": "Memory can support consistency only if the agent revises conflicting memories.", "claim_type": "fact",
             "anchor_start": s0, "anchor_end": s0 + len(span)}]
    bad = [{"canonical_content": "Memory supports consistency.", "claim_type": "fact", "anchor_start": s0, "anchor_end": s0 + 40}]
    assert vendor_br.score(case, good)["meaning_preserved"] is True
    assert vendor_br.score(case, bad)["meaning_preserved"] is False
    assert vendor_br.language_of("Das Gedächtnis kann die Konsistenz nicht sichern, wenn es alte Fehler stabilisiert.") == "de"
    assert vendor_br.score(case, [{**good[0], "canonical_content": "Das Gedächtnis kann Konsistenz nur dann stützen, wenn der Agent revidiert."}])["translated"]


@pytest.mark.skipif(not BR_CHECKOUT.exists(), reason="Budget-Review-Checkout nicht vorhanden")
def test_vendored_functions_are_verbatim():
    vendored = Path(vendor_br.__file__).read_text("utf-8")
    for rel, names in (("scripts/semantic_cases.py", ["_present", "satisfies", "violates", "distinct_claims", "groups_of", "validate"]),
                       ("scripts/semantic_score.py", ["language_of", "_folded", "claims_on_span", "score"]),
                       ("scripts/two_stage_extract.py", ["relation_prompt", "resolved"])):
        src = (BR_CHECKOUT / rel).read_text("utf-8")
        for node in ast.parse(src).body:
            if getattr(node, "name", None) in names:
                assert ast.get_source_segment(src, node).replace("cases_module.", "") in vendored, node.name
