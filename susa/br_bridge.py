"""Semantische Zerlegung eines Prüfpaars mit den vorhandenen Komponenten aus Budget-Review.

Hier wird nichts neu erfunden. Übernommen werden (Paket `content-review`, gepinnt auf Commit 6fc50e7):
  - Extraktionsvertrag      budget_review.prompts.extraction_prompt (atomare Claims, wörtliche raw_span,
                            canonical_content in der Sprache des Dokuments, geschlossene Relationstypen)
  - Paketprüfung            budget_review.models.SemanticPacket, provider._reject_invalid_proposals
                            (ein schemawidriger Vorschlag fällt mit Grund, der Rest bleibt)
  - Zulassungs-Gate         budget_review.gate.govern_packet (Layer-9-Gate: Verankerung, Konfidenzboden,
                            inhaltsadressierte Knoten, Relationen nur zwischen zugelassenen Endpunkten)
  - Abdeckung               budget_review.coverage.measure_coverage (verankerter Anteil, benannte Lücken)
  - zweite Stufe            relation_prompt/resolved aus scripts/two_stage_extract.py (vendor_br)
  - Bedeutungsprüfung       satisfies/violates/score/language_of/validate aus scripts/ (vendor_br)

Was SuSa-AI hinzufügt, ist nur der Teil, den Budget-Review nicht hat: zwei Passagen aus verschiedenen
Dokumenten. Jede Passage wird als eigenes Dokument extrahiert und gegatet; die zweite Stufe schlägt Kanten über
die feste Claim-Liste beider Passagen vor, und dasselbe Gate lässt sie über einem zusammengesetzten Dokument zu.

Abweichungen von der Produktionsstrecke in Budget-Review, bewusst und hier benannt:
  - kein Regenerationsaufruf bei Schemafehlern (Budget); stattdessen sofort _reject_invalid_proposals
  - Modell über den SuSa-Budgetadapter (Claude-CLI), nicht DeepSeek; Provenienz nennt das gemeldete Modell
"""
from __future__ import annotations

import dataclasses
import json
import uuid
from pathlib import Path

from budget_review.coverage import measure_coverage
from budget_review.gate import govern_packet, prompt_fingerprint, sha256_text
from budget_review.models import SchemaError, SemanticPacket
from budget_review.prompts import extraction_prompt
from budget_review.provider import _reject_invalid_proposals, _strip_fence

from . import db
from . import vendor_br
from .analysis import unit_context

BR_COMMIT = "6fc50e783d1978c943e081ffcb2cb04d3a6fe547"
SEPARATOR = "\n\n=====\n\n"


def passage(cfg, conn, unit_id: str) -> dict:
    """Die angezeigte Auswahl (Kontext davor, Kern, Kontext danach) als ein Dokument, mit Kernbereich."""
    x = unit_context(cfg, conn, unit_id)
    u = x["unit"]
    document = x["text"][u["ctx_start"]:u["ctx_end"]]
    return {"unit_id": unit_id, "document_id": u["document_id"], "version_text_sha256": u["text_sha256"],
            "offset": u["ctx_start"], "document": document, "document_sha256": sha256_text(document),
            "core": (u["start_char"] - u["ctx_start"], u["end_char"] - u["ctx_start"])}


def _packet(document_id: str, system: str, user: str, text: str, model: str) -> tuple[SemanticPacket | None, str | None]:
    try:
        data = json.loads(_strip_fence(text))
    except json.JSONDecodeError as e:
        return None, f"kein JSON: {e}"
    if not isinstance(data, dict):
        return None, "JSON-Wurzel ist kein Objekt"
    packet_data = {
        "schema_version": "content-review.semantic-packet/0.2",
        "document_id": document_id,
        "provenance": {"provider": "claude_cli", "model_id": model, "run_id": str(uuid.uuid4()),
                       "prompt_hash": prompt_fingerprint(system, user), "output_hash": sha256_text(text), "temperature": 0.0},
        "claims": data.get("claims"),
        "relations": data.get("relations", []),
    }
    try:
        return SemanticPacket.from_dict(packet_data), None
    except SchemaError as e:
        recovered = _reject_invalid_proposals(packet_data)
        return (recovered, None) if recovered is not None else (None, f"Schema: {e}")


def core_coverage(p: dict, claims) -> dict:
    """Abdeckung des Kernabschnitts: dieselbe Messung, auf den Kern zugeschnitten."""
    s, e = p["core"]
    clipped = [dataclasses.replace(c, anchor_start=max(c.anchor_start, s) - s, anchor_end=min(c.anchor_end, e) - s)
               for c in claims if c.anchor_start < e and c.anchor_end > s]
    cov = measure_coverage(p["document"][s:e], clipped)
    return {"document_characters": cov.document_characters, "anchored_characters": cov.anchored_characters,
            "ratio": cov.ratio, "gaps": [{"start": g.start + s, "end": g.end + s, "excerpt": g.excerpt} for g in cov.gaps]}


def extract_side(adapter, key: str, p: dict, run_id: str) -> dict:
    system, user = extraction_prompt(f"{key}:{p['document_id']}", p["document"], "general")
    res = adapter.complete(system, user, purpose=f"br_extract:{key}", run_id=run_id)
    packet, error = _packet(f"{key}:{p['document_id']}", system, user, res.text, res.model)
    out = {"call_id": res.call_id, "model": res.model, "usage": res.usage, "raw": res.text, "error": error,
           "prompt_hash": prompt_fingerprint(system, user)}
    if packet is None:
        return out
    dossier = govern_packet(p["document"], packet)
    out["dossier"] = dossier.to_dict()
    out["_claims"] = dossier.claims
    out["core_coverage"] = core_coverage(p, dossier.claims)
    return out


def cross_relations(adapter, pa: dict, pb: dict, sa: dict, sb: dict, run_id: str) -> dict:
    """Zweite Stufe über beide Claim-Listen; Zulassung durch dasselbe Gate über dem zusammengesetzten Dokument."""
    listed, proposals = [], []
    for key, side in (("A", sa), ("B", sb)):
        for c in side.get("_claims", ()):
            pid = f"{key}-{c.proposal_id}"
            listed.append({"proposal_id": pid, "claim_type": c.claim_type.value, "canonical_content": c.canonical_content,
                           "raw_span": c.raw_span})
            proposals.append({"proposal_id": pid, "claim_type": c.claim_type.value, "canonical_content": c.canonical_content,
                              "raw_span": c.raw_span, "confidence": c.confidence, "source_ref": c.source_ref})
    combined = "PASSAGE A\n" + pa["document"] + SEPARATOR + "PASSAGE B\n" + pb["document"]
    system, user = vendor_br.relation_prompt("pair", combined, listed)
    res = adapter.complete(system, user, purpose="br_relations:A-B", run_id=run_id)
    out = {"call_id": res.call_id, "model": res.model, "usage": res.usage, "raw": res.text, "prompt_hash": prompt_fingerprint(system, user)}
    try:
        data = json.loads(_strip_fence(res.text))
        relations = data.get("relations") if isinstance(data, dict) else None
    except json.JSONDecodeError as e:
        out["error"] = f"kein JSON: {e}"
        return out
    if not isinstance(relations, list):
        out["error"] = "relations fehlt oder ist keine Liste"
        return out
    kept, dropped = vendor_br.resolved(relations, listed)
    packet, error = _packet("pair", system, user, json.dumps({"claims": proposals, "relations": kept}), res.model)
    out.update({"dropped_unknown_ids": dropped, "error": error})
    if packet is None:
        return out
    dossier = govern_packet(combined, packet)
    by_node = {c.claim_node_id: c.proposal_id for c in dossier.claims}
    out["relations"] = [{"source": by_node[r.source_claim_node_id], "type": r.relation_type.value, "target": by_node[r.target_claim_node_id],
                         "confidence": r.confidence, "rationale": r.rationale,
                         "cross": by_node[r.source_claim_node_id][0] != by_node[r.target_claim_node_id][0]}
                        for r in dossier.relations]
    out["rejections"] = [dataclasses.asdict(x) for x in dossier.rejections]
    return out


def claims_for_scoring(side: dict) -> list[dict]:
    return [{"canonical_content": c.canonical_content, "claim_type": c.claim_type.value, "anchor_start": c.anchor_start,
             "anchor_end": c.anchor_end, "anchor_normalised": c.anchor_normalised} for c in side.get("_claims", ())]


def run_pair(cfg, conn, adapter, left_unit: str, right_unit: str, repeats: int, out_dir: Path, relations: bool = True) -> list[dict]:
    """Wiederholte Läufe (Budget-Review §4.2/§4.15: ein einzelner Lauf ist eine Ziehung, keine Stichprobe)."""
    pa, pb = passage(cfg, conn, left_unit), passage(cfg, conn, right_unit)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "passages.json").write_text(json.dumps({"A": pa, "B": pb}, ensure_ascii=False, indent=1), "utf-8")
    runs = []
    for k in range(1, repeats + 1):
        run_id = db.new_run_id("br_pair")
        sa = extract_side(adapter, "A", pa, run_id)
        sb = extract_side(adapter, "B", pb, run_id)
        if not relations:
            rel = {"skipped": "Relationsstufe nicht ausgeführt (Budget)", "relations": []}
        elif sa.get("_claims") and sb.get("_claims"):
            rel = cross_relations(adapter, pa, pb, sa, sb, run_id)
        else:
            rel = {"error": "keine Claims"}
        record = {"repeat": k, "run_id": run_id, "br_commit": BR_COMMIT, "A": {x: y for x, y in sa.items() if x != "_claims"},
                  "B": {x: y for x, y in sb.items() if x != "_claims"}, "relations": rel}
        (out_dir / f"run-{k}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str), "utf-8")
        runs.append({"A": sa, "B": sb, "relations": rel, "record": record})
    return runs


def evaluate(out_dir: Path) -> dict:
    """Auswertung der gespeicherten Läufe, ohne Modellaufruf. Achsen getrennt (Budget-Review §4.12):
    Textabdeckung, Bedeutung (Token-Bedingungen), Sprache, Relationen, Stabilität über Wiederholungen."""
    from budget_review.anchoring import folded
    runs = [json.loads(p.read_text("utf-8")) for p in sorted(out_dir.glob("run-*.json"))]
    cases_path = out_dir / "meaning_cases.json"
    cases = json.loads(cases_path.read_text("utf-8"))["cases"] if cases_path.exists() else []
    report = {"runs": len(runs), "sides": {}, "meaning": {}, "relations": {}}
    for key in ("A", "B"):
        per_run = []
        anchor_sets = []
        for r in runs:
            d = r[key].get("dossier")
            if not d:
                per_run.append({"error": r[key].get("error")})
                anchor_sets.append(set())
                continue
            claims = d["claims"]
            per_run.append({"claims": len(claims), "rejections": len(d["rejections"]),
                            "rejection_reasons": sorted({x["reason"].split(":")[0] for x in d["rejections"]}),
                            "core_ratio": r[key]["core_coverage"]["ratio"], "core_gaps": len(r[key]["core_coverage"]["gaps"]),
                            "normalised_anchors": sum(1 for c in claims if c["anchor_normalised"]),
                            "languages": sorted({vendor_br.language_of(c["canonical_content"]) for c in claims}),
                            "model": r[key].get("model"), "prompt_hash": r[key].get("prompt_hash")})
            anchor_sets.append({folded(c["raw_span"]) for c in claims})
        union = set().union(*anchor_sets) if anchor_sets else set()
        report["sides"][key] = {"per_run": per_run, "anchors_total": len(union),
                                "anchors_in_all_runs": sum(1 for a in union if all(a in s for s in anchor_sets)),
                                "prompt_hash_identical": len({x.get("prompt_hash") for x in per_run}) == 1}
    for case in cases:
        rows = []
        for r in runs:
            d = r[case["side"]].get("dossier")
            rows.append(vendor_br.score(case, d["claims"]) if d else {"meaning_preserved": None})
        report["meaning"][case["case_id"]] = {"phenomenon": case["phenomenon"], "per_run": [
            {"anchored": x.get("anchored"), "meaning_preserved": x.get("meaning_preserved"), "distortions": x.get("distortions"),
             "translated": x.get("translated"), "contents": x.get("contents")} for x in rows]}
    edges = []
    for r in runs:
        rel = r.get("relations") or {}
        claims = {}
        for key in ("A", "B"):
            for c in (r[key].get("dossier") or {}).get("claims", []):
                claims[f"{key}-{c['proposal_id']}"] = folded(c["raw_span"])
        edges.append({(claims.get(e["source"]), e["type"], claims.get(e["target"])) for e in rel.get("relations", []) if e["cross"]})
    allk = set().union(*edges) if edges else set()
    report["relations"] = {"per_run_cross_edges": [len(e) for e in edges],
                           "per_run_errors": [(r.get("relations") or {}).get("error") for r in runs],
                           "cross_edges_by_frequency": sorted(([sum(1 for e in edges if k in e), k[1]] for k in allk), reverse=True),
                           "types_by_frequency": {t: sum(1 for e in edges for k in e if k[1] == t) for t in sorted({k[1] for k in allk})}}
    return report
