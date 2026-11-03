"""Rekonstruktion (Prompt A), Vergleich (Prompt B), Gegenprüfung (Prompt C), manuelle Annotation und Reviews.

Jede Modellinterpretation wird mit Lauf, Adapter, Modell und Promptversion gespeichert. Zitate werden
deterministisch gegen die gespeicherte Textversion geprüft; nicht auffindbare Zitate führen zu
status=quote_unverified und werden in der Oberfläche als solche markiert.
"""
from __future__ import annotations

import json
import re
import uuid

from . import db
from .config import Config, code_version
from .llm import CallLimitReached, LLMResult, NotConfigured, estimate_tokens, extract_json, get_adapter, load_prompt
from .versions import read_text

RELATION_TYPES = ["repeats", "supports", "refines", "extends", "restricts_scope", "challenges_assumption",
                  "contradicts_under_shared_scope", "apparent_conflict_due_to_definition",
                  "apparent_conflict_due_to_system_or_time", "new_evidence_same_claim", "different_question",
                  "insufficient_context", "unresolved"]
DECISIONS = ["confirmed", "corrected", "rejected", "undecidable"]


def unit_context(cfg: Config, conn, unit_id: str) -> dict:
    u = conn.execute(
        """SELECT u.*, d.title, d.author, d.date, d.canonical_url, d.is_synthetic, v.status AS text_status,
           v.availability, v.text_path, v.text_sha256, v.is_current FROM argument_units u
           JOIN documents d ON d.id=u.document_id JOIN document_versions v ON v.id=u.version_id WHERE u.id=?""",
        (unit_id,)).fetchone()
    if u is None:
        raise KeyError(unit_id)
    text = read_text(cfg, u)
    quoted = [text[p["start_char"]:p["end_char"]] for p in conn.execute(
        "SELECT * FROM paragraphs WHERE version_id=? AND speaker_hint IN ('quoted_other','unclear') AND start_char>=? AND end_char<=?",
        (u["version_id"], u["ctx_start"], u["ctx_end"]))]
    return {"unit": u, "text": text, "before": text[u["ctx_start"]:u["start_char"]].strip(),
            "core": text[u["start_char"]:u["end_char"]], "after": text[u["end_char"]:u["ctx_end"]].strip(), "quoted_paragraphs": quoted}


def render_passage(label: str, c: dict) -> str:
    u = c["unit"]
    parts = [f'<passage id="{label}" document="{u["document_id"]}" title="{u["title"] or ""}" author="{u["author"] or ""}" '
             f'date="{u["date"] or ""}" text_status="{u["text_status"]}" availability="{u["availability"]}">']
    if c["before"]:
        parts += ["[Kontext davor]", c["before"]]
    parts += ["[Kernabschnitt]", c["core"]]
    if c["after"]:
        parts += ["[Kontext danach]", c["after"]]
    parts.append("</passage>")
    if c["quoted_paragraphs"]:
        parts.append(f"Hinweis zu {label}: Folgende Absätze sind im Original als Blockzitat formatiert (Sprecher ggf. nicht der Autor): "
                     + " | ".join(q[:80] for q in c["quoted_paragraphs"]))
    return "\n".join(parts)


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def check_quotes(conn, c: dict, quotes: list[str], create_spans: bool = True) -> list[dict]:
    """Exakte Suche im kanonischen Text innerhalb des übergebenen Kontextbereichs (Kern + Kontext)."""
    u, text = c["unit"], c["text"]
    lo, hi = u["ctx_start"], u["ctx_end"]
    out = []
    for q in quotes or []:
        if not isinstance(q, str) or not q.strip():
            continue
        q2 = q.strip().strip("„“\"'")
        idx = text.find(q2, lo, hi)
        method = "exact"
        if idx < 0:
            # Toleranz nur für Leerraum; keine Wortänderungen
            region = text[lo:hi]
            pattern = r"\s+".join(re.escape(w) for w in q2.split())
            m = re.search(pattern, region)
            if m:
                idx, q2, method = lo + m.start(), m.group(0), "whitespace_normalized"
        if idx < 0:
            out.append({"quote": q, "found": False, "method": "not_found"})
            continue
        s, e = idx, idx + len(q2)
        sid = f"v{u['version_id']}:m:{s}-{e}"
        if create_spans:
            conn.execute(
                "INSERT OR IGNORE INTO spans(id, version_id, start_char, end_char, text, speaker, origin, text_sha256, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (sid, u["version_id"], s, e, text[s:e], None, "model_quote", db.sha256_text(text[s:e]), db.now()))
        out.append({"quote": q, "found": True, "method": method, "span_id": sid, "start_char": s, "end_char": e,
                    "in_core": u["start_char"] <= s and e <= u["end_char"]})
    return out


def _start_run(conn, kind: str, adapter, prompt_version: str, cfg_llm: dict, inputs: dict, dry: bool) -> str:
    rid = f"{kind}-{uuid.uuid4().hex[:12]}"
    conn.execute(
        """INSERT INTO runs(id, kind, code_version, adapter, model, prompt_version, is_real_model_run, is_dry_run, config_json,
           input_hashes_json, started_at, status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (rid, kind, code_version(), adapter.name, cfg_llm.get("model") if adapter.name in ("anthropic_api", "claude_cli") else adapter.name,
         prompt_version, int(adapter.name in ("anthropic_api", "claude_cli")), int(dry),
         db.dumps({k: v for k, v in cfg_llm.items() if "key" not in k.lower()}), db.dumps(inputs), db.now(), "running"))
    return rid


def _finish_run(conn, rid: str, status: str, error: str | None = None, res: LLMResult | None = None):
    conn.execute("UPDATE runs SET finished_at=?, status=?, error=?, usage_json=?, model=COALESCE(?, model), is_real_model_run=? WHERE id=?",
                 (db.now(), status, error, db.dumps(res.usage) if res else None, res.model if res else None,
                  int(res.is_real_model_run) if res else 0, rid))


def _save_raw(cfg: Config, rid: str, text: str) -> str:
    p = cfg.subdir("model_responses") / f"{rid}.txt"
    p.write_text(text, "utf-8")
    return str(p.relative_to(cfg.root))


def estimate(cfg: Config, conn, comparison_ids: list[str]) -> dict:
    """Aufwandsschätzung vor einem Lauf (Zeichen/4 als grobe Tokenschätzung)."""
    system, pv = load_prompt("B_compare")
    total_in = 0
    for cid in comparison_ids:
        cmp_ = conn.execute("SELECT * FROM candidate_comparisons WHERE id=?", (cid,)).fetchone()
        lc, rc = unit_context(cfg, conn, cmp_["left_unit_id"]), unit_context(cfg, conn, cmp_["right_unit_id"])
        total_in += estimate_tokens(system + render_passage("L", lc) + render_passage("R", rc))
    return {"prompt_version": pv, "comparisons": len(comparison_ids), "model_calls": len(comparison_ids),
            "est_input_tokens": total_in, "est_output_tokens_upper": len(comparison_ids) * 1500,
            "hinweis": "Grobe Schätzung (Zeichen/4). Kosten hängen vom Modell und Thinking-Aufwand ab und werden nicht zugesagt."}


def compare(cfg: Config, conn, comparison_id: str, adapter=None, dry_run: bool = False) -> dict:
    cfg_llm = cfg.section("llm")
    adapter = adapter or get_adapter(cfg_llm)
    system, pv = load_prompt("B_compare")
    cmp_ = conn.execute("SELECT * FROM candidate_comparisons WHERE id=?", (comparison_id,)).fetchone()
    lc, rc = unit_context(cfg, conn, cmp_["left_unit_id"]), unit_context(cfg, conn, cmp_["right_unit_id"])
    scope = json.loads(cmp_["corpus_scope_json"] or "{}")
    user = (f"Vergleichsbestand: Paar aus Suchwegen {cmp_['channels_json']}; durchsuchter Bestand: {scope or 'explizit angelegtes Paar'}.\n"
            f"Zeitliche Lage: {cmp_['temporal']}.\n\n" + render_passage("L", lc) + "\n\n" + render_passage("R", rc))
    inputs = {"comparison_id": comparison_id, "left_text_sha256": lc["unit"]["text_sha256"], "right_text_sha256": rc["unit"]["text_sha256"],
              "prompt_sha256": db.sha256_text(system)}
    if dry_run:
        return {"dry_run": True, "est_input_tokens": estimate_tokens(system + user), "prompt_version": pv}
    rid = _start_run(conn, "compare", adapter, pv, cfg_llm, inputs, False)
    try:
        res = adapter.complete(system, user)
    except (NotConfigured, CallLimitReached) as e:
        _finish_run(conn, rid, "not_run", str(e))
        conn.commit()
        return {"status": "not_run", "reason": str(e), "run_id": rid}
    except Exception as e:
        _finish_run(conn, rid, "model_error", repr(e)[:1000])
        conn.commit()
        return {"status": "model_error", "reason": repr(e)[:300], "run_id": rid}
    raw_path = _save_raw(cfg, rid, res.text)
    hid = f"rel-{uuid.uuid4().hex[:12]}"
    try:
        payload = extract_json(res.text)
        rtypes = [t for t in payload.get("relation_types", []) if t in RELATION_TYPES]
        unknown = [t for t in payload.get("relation_types", []) if t not in RELATION_TYPES]
        qc = {"left": check_quotes(conn, lc, payload.get("left_quotes", [])),
              "right": check_quotes(conn, rc, payload.get("right_quotes", [])), "unknown_relation_types": unknown}
        all_q = qc["left"] + qc["right"]
        status = "ok" if all_q and all(q["found"] for q in all_q) else "quote_unverified"
        if "insufficient_context" in rtypes:
            status = "insufficient_context" if status == "ok" else status
    except (ValueError, json.JSONDecodeError) as e:
        payload, rtypes, qc, status = {"parse_error": str(e)}, [], {}, "parse_error"
    conn.execute(
        """INSERT INTO relation_hypotheses(id, comparison_id, run_id, kind, status, relation_types_json, payload_json, quote_check_json,
           raw_response_path, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (hid, comparison_id, rid, "model_primary", status, db.dumps(rtypes), db.dumps(payload), db.dumps(qc), raw_path, db.now()))
    _finish_run(conn, rid, "finished", None, res)
    conn.commit()
    return {"status": status, "hypothesis_id": hid, "run_id": rid, "relation_types": rtypes}


def countercheck(cfg: Config, conn, hypothesis_id: str, adapter=None) -> dict:
    cfg_llm = cfg.section("llm")
    adapter = adapter or get_adapter(cfg_llm)
    system, pv = load_prompt("C_countercheck")
    h = conn.execute("SELECT * FROM relation_hypotheses WHERE id=?", (hypothesis_id,)).fetchone()
    cmp_ = conn.execute("SELECT * FROM candidate_comparisons WHERE id=?", (h["comparison_id"],)).fetchone()
    lc, rc = unit_context(cfg, conn, cmp_["left_unit_id"]), unit_context(cfg, conn, cmp_["right_unit_id"])
    user = ("Vorgeschlagene Interpretation (zu prüfen):\n" + json.dumps(json.loads(h["payload_json"] or "{}"), ensure_ascii=False, indent=1)
            + "\n\n" + render_passage("L", lc) + "\n\n" + render_passage("R", rc))
    rid = _start_run(conn, "countercheck", adapter, pv, cfg_llm, {"hypothesis_id": hypothesis_id}, False)
    try:
        res = adapter.complete(system, user)
    except (NotConfigured, CallLimitReached) as e:
        _finish_run(conn, rid, "not_run", str(e))
        conn.commit()
        return {"status": "not_run", "reason": str(e)}
    raw_path = _save_raw(cfg, rid, res.text)
    try:
        payload = extract_json(res.text)
        qc = {"left": check_quotes(conn, lc, payload.get("left_quotes", [])), "right": check_quotes(conn, rc, payload.get("right_quotes", []))}
        status = payload.get("decision") if payload.get("decision") in DECISIONS else "parse_error"
    except (ValueError, json.JSONDecodeError) as e:
        payload, qc, status = {"parse_error": str(e)}, {}, "parse_error"
    cid = f"rel-{uuid.uuid4().hex[:12]}"
    conn.execute(
        """INSERT INTO relation_hypotheses(id, comparison_id, run_id, kind, parent_id, status, relation_types_json, payload_json,
           quote_check_json, raw_response_path, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (cid, h["comparison_id"], rid, "model_countercheck", hypothesis_id, status,
         db.dumps(payload.get("corrected_relation_types") or []), db.dumps(payload), db.dumps(qc), raw_path, db.now()))
    _finish_run(conn, rid, "finished", None, res)
    conn.commit()
    return {"status": status, "hypothesis_id": cid}


def reconstruct(cfg: Config, conn, unit_id: str, adapter=None) -> dict:
    cfg_llm = cfg.section("llm")
    adapter = adapter or get_adapter(cfg_llm)
    system, pv = load_prompt("A_reconstruct")
    c = unit_context(cfg, conn, unit_id)
    rid = _start_run(conn, "reconstruct", adapter, pv, cfg_llm, {"unit_id": unit_id, "text_sha256": c["unit"]["text_sha256"]}, False)
    try:
        res = adapter.complete(system, render_passage("P", c))
    except (NotConfigured, CallLimitReached) as e:
        _finish_run(conn, rid, "not_run", str(e))
        conn.commit()
        return {"status": "not_run", "reason": str(e)}
    raw_path = _save_raw(cfg, rid, res.text)
    try:
        payload = extract_json(res.text)
        quotes = []
        for cl in payload.get("claims", []):
            quotes += cl.get("quotes", [])
            for key in ("explicit_definitions", "explicit_premises", "reasons", "qualifications"):
                quotes += [x.get("quote") for x in cl.get(key, []) if isinstance(x, dict) and x.get("quote")]
        qc = check_quotes(conn, c, quotes)
        status = payload.get("status", "ok")
        if status == "ok" and (not qc or not all(q["found"] for q in qc)):
            status = "quote_unverified"
    except (ValueError, json.JSONDecodeError) as e:
        payload, qc, status = {"parse_error": str(e)}, [], "parse_error"
    cid = f"claim-{uuid.uuid4().hex[:12]}"
    conn.execute("INSERT INTO claim_candidates(id, unit_id, run_id, status, payload_json, quote_check_json, raw_response_path, created_at) VALUES(?,?,?,?,?,?,?,?)",
                 (cid, unit_id, rid, status, db.dumps(payload), db.dumps(qc), raw_path, db.now()))
    _finish_run(conn, rid, "finished", None, res)
    conn.commit()
    return {"status": status, "claim_candidate_id": cid}


def add_manual_hypothesis(cfg: Config, conn, comparison_id: str, author: str, relation_types: list[str], payload: dict) -> str:
    """Menschliche Interpretation ohne Modell. Zitate werden genauso deterministisch geprüft."""
    cmp_ = conn.execute("SELECT * FROM candidate_comparisons WHERE id=?", (comparison_id,)).fetchone()
    lc, rc = unit_context(cfg, conn, cmp_["left_unit_id"]), unit_context(cfg, conn, cmp_["right_unit_id"])
    qc = {"left": check_quotes(conn, lc, payload.get("left_quotes", [])), "right": check_quotes(conn, rc, payload.get("right_quotes", []))}
    all_q = qc["left"] + qc["right"]
    if not all_q:
        status = "no_quotes"
    else:
        status = "ok" if all(q["found"] for q in all_q) else "quote_unverified"
    hid = f"rel-{uuid.uuid4().hex[:12]}"
    conn.execute(
        """INSERT INTO relation_hypotheses(id, comparison_id, kind, author, status, relation_types_json, payload_json, quote_check_json, created_at)
           VALUES(?,?,?,?,?,?,?,?,?)""",
        (hid, comparison_id, "manual", author, status, db.dumps([t for t in relation_types if t in RELATION_TYPES]), db.dumps(payload),
         db.dumps(qc), db.now()))
    conn.commit()
    return hid


def add_review(conn, target_type: str, target_id: str, reviewer: str, decision: str, comment: str = "", corrected: dict | None = None) -> int:
    if decision not in DECISIONS:
        raise ValueError(decision)
    c = conn.execute("INSERT INTO reviews(target_type, target_id, reviewer, decision, comment, corrected_json, created_at) VALUES(?,?,?,?,?,?,?)",
                     (target_type, target_id, reviewer, decision, comment, db.dumps(corrected) if corrected else None, db.now()))
    conn.commit()
    return c.lastrowid
