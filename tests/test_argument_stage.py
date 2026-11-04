"""Gezielte Tests der Argumentstufe: fehlende/falsche Anker, Zitat nicht im genannten Anker, Bedeutungsverstärkung,
ungültiges Schema, Anker der falschen Seite, Frage als Grund, Ablauf über Budget. Synthetische Texte, Replay-Adapter."""
import copy
import json

from susa import argument_stage as st
from susa import db
from susa.llm import ReplayAdapter, budget_status, create_budget
from susa.pair_analysis import build_structure

DOC_A = "Can machines think?\n\nMinds are not reducible to computation alone. Brains are embodied, so minds may need bodies."
DOC_B = "Machines will think. Computation is all there is to minds."
SPANS_A = ["Can machines think?", "Minds are not reducible to computation alone.", "Brains are embodied", "so minds may need bodies."]
SPANS_B = ["Machines will think.", "Computation is all there is to minds."]


def _pair(tmp_path):
    (tmp_path / "passages.json").write_text(json.dumps({
        "A": {"document": DOC_A, "core": [0, len(DOC_A)], "offset": 0, "document_id": "syn-a", "version_text_sha256": "x"},
        "B": {"document": DOC_B, "core": [0, len(DOC_B)], "offset": 0, "document_id": "syn-b", "version_text_sha256": "y"}}))

    def claims(side, doc, spans):
        return [{"proposal_id": f"C{i:02d}", "claim_type": "claim", "canonical_content": s, "raw_span": s,
                 "anchor_start": doc.index(s), "anchor_end": doc.index(s) + len(s), "claim_node_id": f"{side}{i}",
                 "anchor_normalised": False} for i, s in enumerate(spans, 1)]
    run = {"A": {"dossier": {"claims": claims("A", DOC_A, SPANS_A),
                             "relations": [{"source_claim_node_id": "A3", "relation_type": "SUPPORTS", "target_claim_node_id": "A4"}]}},
           "B": {"dossier": {"claims": claims("B", DOC_B, SPANS_B), "relations": []}}, "relations": {"relations": []}}
    (tmp_path / "run-1.json").write_text(json.dumps(run))
    return build_structure(tmp_path, {"A": [(0, len("Can machines think?"), "h")]})


GOOD = {
    "speech_acts": [{"anchors": ["A01"], "act": "Frage", "speaker": None, "note": "", "interpretation": False},
                    {"anchors": ["A02"], "act": "vertritt", "speaker": None, "note": "", "interpretation": False}],
    "chains": [{"id": "A-K1", "side": "A", "questions": ["F1"],
                "conclusion": {"anchors": ["A04"], "rendering": "Der Geist könnte einen Körper brauchen.",
                               "evidence_quote": "minds may need bodies", "modality": "möglich"},
                "parts": [{"role": "Grund", "anchors": ["A03"], "rendering": "Gehirne sind verkörpert.",
                           "evidence_quote": "Brains are embodied"}],
                "reconstructed_premises": ["Was für Gehirne gilt, gilt für den Geist."], "internal_assessment": "trägt nur mit der Voraussetzung",
                "support": "teilweise gestützt", "external_checks": [], "model_support": [{"model_edge": ["A03", "SUPPORTS", "A04"], "runs": 1}]}],
    "questions": [{"id": "F1", "text": "Können Maschinen denken?", "A": ["A-K1"], "B": [], "relation": "nur A"}],
    "conclusion_comparison": [{"a": ["A02"], "b": ["B02"], "match": "unvereinbar", "common": "", "difference": "",
                               "reasons_a": [], "reasons_b": []}],
    "additions": [{"id": "A+1", "side": "A", "thought": "Der Geist ist nicht allein auf Berechnung reduzierbar.", "anchors": ["A02"],
                   "evidence_quote": "not reducible to computation alone", "kind": "Widerspruch", "contained_in_other": "nein",
                   "changes_line": "ja", "textual_basis": "ausdrücklich"}],
    "weak_relations": [], "open_readings": [], "uncertainties": []}


def test_valid_result_passes(tmp_path):
    v = st.validate(GOOD, _pair(tmp_path))
    assert v["status"] == "valid", v
    assert v["amplification_flags"] == [] and v["context_flags"] == []


def test_unknown_anchor_and_quote_from_uncited_anchor(tmp_path):
    s = _pair(tmp_path)
    bad = copy.deepcopy(GOOD)
    bad["speech_acts"][0]["anchors"] = ["A99"]
    # Zitat existiert im Text (A02), aber der genannte Anker A03 trägt es nicht
    bad["chains"][0]["parts"][0]["evidence_quote"] = "not reducible to computation"
    bad["additions"][0]["anchors"] = []
    v = st.validate(bad, s)
    assert v["status"] == "invalid"
    assert any("A99" in e for e in v["errors"]) and any("additions[0].anchors" in e for e in v["errors"])
    assert any("parts[0]" in q for q in v["quote_failures"])


def test_amplification_flag_alone(tmp_path):
    bad = copy.deepcopy(GOOD)
    bad["additions"][0]["thought"] = "Der Geist ist nicht berechenbar."
    v = st.validate(bad, _pair(tmp_path))
    flags = [f for x in v["amplification_flags"] for f in x["flags"]]
    assert any("scope_limit" in f and "alone" in f for f in flags)
    bad["chains"][0]["conclusion"]["rendering"] = "Der Geist braucht einen Körper."  # „may“ verloren
    v = st.validate(bad, _pair(tmp_path))
    assert any(x["path"].endswith("conclusion") and any("modal" in f for f in x["flags"]) for x in v["amplification_flags"])


def test_invalid_schema(tmp_path):
    s = _pair(tmp_path)
    assert st.validate({"chains": []}, s)["schema_valid"] is False
    bad = copy.deepcopy(GOOD)
    bad["additions"][0]["kind"] = "Erweiterung"
    bad["chains"][0]["model_support"] = [{"model_edge": ["A02", "SUPPORTS", "A04"], "runs": 3}]  # nicht in den Läufen
    bad["questions"][0]["A"] = ["A-K9"]
    v = st.validate(bad, s)
    assert not v["schema_valid"] and len(v["errors"]) == 3


def test_wrong_side_and_question_as_reason(tmp_path):
    bad = copy.deepcopy(GOOD)
    bad["chains"][0]["parts"].append({"role": "Grund", "anchors": ["B02"], "rendering": "Berechnung ist alles.",
                                      "evidence_quote": "Computation is all there is"})
    bad["chains"][0]["parts"].append({"role": "Voraussetzung", "anchors": ["A01"], "rendering": "Können Maschinen denken?",
                                      "evidence_quote": "Can machines think?"})
    v = st.validate(bad, _pair(tmp_path))
    assert v["status"] == "invalid" and any("B02" in e for e in v["side_errors"])
    assert any("A01" in c and "Frage" in c for c in v["context_flags"])


def test_run_stores_everything_and_respects_budget(tmp_path):
    _pair(tmp_path)
    conn = db.connect(tmp_path / "t.sqlite")
    bid = create_budget(conn, "test", 2, adapter="replay")
    ad = ReplayAdapter({}, [json.dumps(GOOD), "kein json"], conn=conn, budget_id=bid)
    m1 = st.run(None, conn, ad, tmp_path)
    d = tmp_path / f"argument-{m1['run_id']}"
    assert m1["status"] == "valid"
    assert {p.name for p in d.iterdir()} >= {"inputs.json", "prompt_system.txt", "prompt_user.txt", "response.txt",
                                             "validation.json", "result.json", "meta.json"}
    assert m1["prompt_version"] == "D_argument.v1"
    m2 = st.run(None, conn, ad, tmp_path)
    assert m2["status"] == "invalid" and m2["inputs_sha256"] == m1["inputs_sha256"]  # gleiche Eingaben, reproduzierbar
    assert (tmp_path / f"argument-{m2['run_id']}" / "response.txt").read_text() == "kein json"
    m3 = st.run(None, conn, ad, tmp_path)
    assert m3["status"] == "not_run" and budget_status(conn, bid)["used"] == 2
    # Bericht ohne Originalzitate enthält keine Originalsätze
    pub = tmp_path / "pub.md"
    st.write_reports(d, pub)
    assert "Brains are embodied" not in pub.read_text() and "Brains are embodied" in (d / "report_full.md").read_text()


def test_split_cli_answer_is_rejected(tmp_path):
    """Die CLI setzt bei erreichter Ausgabegrenze in einem zweiten Zug fort und liefert nur dessen Text."""
    from susa.llm import LLMResult
    r = st._parse(LLMResult(text=json.dumps(GOOD), model="m", stop_reason="output_split"), _pair(tmp_path))
    assert r[0] is None and r[1]["status"] == "invalid"


def test_question_relation_consistency(tmp_path):
    bad = copy.deepcopy(GOOD)
    bad["questions"][0]["relation"] = "teilweise gemeinsam"  # B hat keine Kette zu F1
    v = st.validate(bad, _pair(tmp_path))
    assert v["consistency_flags"] and st.validate(GOOD, _pair(tmp_path))["consistency_flags"] == []
