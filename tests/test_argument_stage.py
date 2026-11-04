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


def _pair(tmp_path, DOC_A=DOC_A, with_sentences=False):
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
    kinds = {"A": [(0, len("Can machines think?"), "h")]} if DOC_A.startswith("Can machines") else {}
    structure = build_structure(tmp_path, kinds)
    if with_sentences:
        st.add_sentence_anchors(structure, json.loads((tmp_path / "passages.json").read_text()), kinds)
    return structure


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
    assert "Brains are embodied" not in pub.read_text() and "Brains are embodied" in (d / f"report_full.{st.RENDER_VERSION}.md").read_text()


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


def test_reported_thesis_stays_reported_in_comparison_and_short_report(tmp_path):
    """Paar-2-Fehler: B gibt eine fremde These wieder (Sprecher laut Text nicht eindeutig); der Vergleichstext macht B
    selbst zum Subjekt („B … behauptet“). Der Hinweis muss anschlagen, der Kurzbericht muss die Wiedergabe und die
    Offenheit des Sprechers zeigen, nicht eine Position von B."""
    s = _pair(tmp_path)
    r = copy.deepcopy(GOOD)
    r["speech_acts"].append({"anchors": ["B02"], "act": "berichtet", "speaker": "wahrscheinlich die Paperautoren (Zitat)",
                             "note": "", "interpretation": False})
    r["conclusion_comparison"][0]["difference"] = "B (bzw. die zitierte Stimme) behauptet sie und begründet sie."
    v = st.validate(r, s)
    assert len(v["attribution_flags"]) == 1 and "B02" in v["attribution_flags"][0]
    meta = {"run_id": "t", "prompt_version": "D_argument.v1"}
    short = st.render_short(r, v, {"structure": s}, meta, with_text=False)
    line = next(x for x in short.splitlines() if x.startswith("- A02 ↔ B02"))
    assert "B vertreten von: berichtet: wahrscheinlich die Paperautoren (Zitat) — Sprecher nicht eindeutig" in line
    # neutrale Wiedergabe schlägt nicht an; eine eigene Position der Passage auch nicht
    r["conclusion_comparison"][0]["difference"] = "B gibt sie als Position der Paperautoren wieder."
    assert st.validate(r, s)["attribution_flags"] == []
    r["speech_acts"][-1]["act"] = "vertritt"
    r["speech_acts"][-1]["speaker"] = "Autor von B"
    r["conclusion_comparison"][0]["difference"] = "B behauptet sie."
    assert st.validate(r, s)["attribution_flags"] == []


def test_frame_sentence_without_claim_is_citable(tmp_path):
    doc = "To put their view briefly, it is roughly this:\n\n" + DOC_A
    s = _pair(tmp_path, DOC_A=doc, with_sentences=True)
    frame = [a for a in s["sides"]["A"]["sentences"] if a["span"].startswith("To put their view")]
    assert len(frame) == 1 and frame[0]["span"] == doc[frame[0]["start"]:frame[0]["end"]]
    assert not any(a["span"].startswith("Minds are not") for a in s["sides"]["A"]["sentences"])  # vom Claim abgedeckt
    r = copy.deepcopy(GOOD)
    r["speech_acts"].append({"anchors": [frame[0]["id"]], "act": "vertritt", "speaker": "Autor von A", "note": "Rahmensatz",
                             "interpretation": False})
    r["chains"][0]["parts"].append({"role": "Voraussetzung", "anchors": [frame[0]["id"]], "rendering": "A kündigt eine Wiedergabe an.",
                                    "evidence_quote": "To put their view briefly"})
    assert st.validate(r, s)["status"] == "valid"
