"""Gezielte Tests für die deterministische Argumentstruktur (Sprechakt-Hinweise, Anker-Gruppierung, Verweisprüfung)."""
import json

from susa import pair_analysis as pa

DOC = ("Experts disagree\n\nSome people may be convinced that X. Seth argues that Y cannot be Z. If you doubt it (and I am), "
       "it feels far. What happens if they act against us? We are not taking steps.")


def cues(span, kind=None):
    s = DOC.index(span)
    return pa.speech_cues(DOC, s, s + len(span), kind)


def test_speech_cues():
    assert any("Überschrift" in c for c in cues("Experts disagree", "h"))
    assert any("mögliche Überzeugung" in c for c in cues("Some people may be convinced that X."))
    assert any("Redeverb" in c for c in cues("Seth argues that Y cannot be Z."))
    assert any("Negation" in c for c in cues("Seth argues that Y cannot be Z."))
    c = cues("If you doubt it (and I am)")
    assert any("erste Person Singular" in x for x in c) and any("Bedingung" in x for x in c)
    assert any("Frage" in x for x in cues("What happens if they act against us?"))
    assert not any("Frage" in x for x in cues("We are not taking steps."))


def _run(tmp_path, claims_a, rel=None):
    doc_b = "Other text here."
    (tmp_path / "passages.json").write_text(json.dumps({"A": {"document": DOC, "core": [0, len(DOC)], "offset": 0, "document_id": "a", "version_text_sha256": "x"},
                                                        "B": {"document": doc_b, "core": [0, len(doc_b)], "offset": 0, "document_id": "b", "version_text_sha256": "y"}}))
    for k, ca in enumerate(claims_a, 1):
        def claim(pid, span, doc):
            s = doc.index(span)
            return {"proposal_id": pid, "claim_type": "fact", "canonical_content": span, "raw_span": span, "anchor_start": s,
                    "anchor_end": s + len(span), "claim_node_id": f"n{pid}{k}", "anchor_normalised": False}
        a = [claim(p, sp, DOC) for p, sp in ca]
        b = [claim("C01", "Other text here.", doc_b)]
        relations = [{"source_claim_node_id": a[1]["claim_node_id"], "relation_type": "SUPPORTS", "target_claim_node_id": a[0]["claim_node_id"]}]
        run = {"A": {"dossier": {"claims": a, "relations": relations}}, "B": {"dossier": {"claims": b, "relations": []}},
               "relations": {"relations": rel or []}}
        (tmp_path / f"run-{k}.json").write_text(json.dumps(run))


def test_structure_groups_by_anchor_and_counts_runs(tmp_path):
    seth, cond = "Seth argues that Y cannot be Z.", "If you doubt it (and I am)"
    _run(tmp_path, [[("C01", seth), ("C02", cond)], [("C01", seth), ("C03", cond)], [("C01", seth), ("C02", "it feels far.")]],
         rel=[{"source": "A-C01", "type": "SUPPORTS", "target": "B-C01", "cross": True}])
    st = pa.build_structure(tmp_path, {"A": [(0, 16, "h")]})
    ids = {a["start"]: a for a in st["sides"]["A"]["anchors"]}
    seth_a = ids[DOC.index(seth)]
    assert seth_a["in_runs"] == [1, 2, 3]  # unterschiedliche Proposal-IDs, ein Anker
    assert ids[DOC.index(cond)]["in_runs"] == [1, 2]
    edges = {(e["source"], e["type"], e["target"]): e["runs"] for e in st["sides"]["A"]["edges"]}
    assert edges[(ids[DOC.index(cond)]["id"], "SUPPORTS", seth_a["id"])] == 2
    assert st["cross_edges"][0]["runs"] == 3
    bare = pa.without_text(st)
    assert seth not in json.dumps(bare)
    # Verweisprüfung: bekannte Anker und Kanten ok, unbekannte gemeldet
    good = {"x": {"anchors": [seth_a["id"]], "model_edge": [seth_a["id"], "SUPPORTS", "B01"]}}
    assert pa.check_interpretation(good, st) == []
    bad = {"c": [{"a": ["A99"], "b": [seth_a["id"]]}], "y": {"model_edge": [seth_a["id"], "CONTRADICTS", "B01"]}}
    assert len(pa.check_interpretation(bad, st)) == 2


def test_side_caches_are_not_counted_as_runs(tmp_path):
    for n in ("run-1.json", "run-1.A.json", "run-1.B.json", "run-10.json", "run-2.json"):
        (tmp_path / n).write_text("{}")
    assert [p.name for p in pa.run_files(tmp_path)] == ["run-1.json", "run-2.json", "run-10.json"]
