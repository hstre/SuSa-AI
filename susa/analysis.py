"""Rekonstruktion (Prompt A), Vergleich (Prompt B), Gegenprüfung (Prompt C), manuelle Annotation und Reviews.

Jede Interpretation speichert getrennt: Antwortempfang, Schemaprüfung, Belegprüfung, Modellurteil
(siehe validate.py). Menschliche Prüfungen stehen ausschließlich in reviews. Ein Modellurteil ersetzt nie eine
bestandene Belegprüfung.
"""
from __future__ import annotations

import json
import re
import uuid

from . import db
from .config import Config, code_version
from .llm import CallLimitReached, NotConfigured, estimate_tokens, extract_json, get_adapter, load_prompt
from .validate import (ABSTENTION_TYPES, DECISIONS, RELATION_TYPES, anchor_status, evidence_status, validate_compare,
                       validate_countercheck, validate_reconstruct)
from .versions import read_text

__all__ = ["RELATION_TYPES", "DECISIONS", "compare", "countercheck", "reconstruct", "add_manual_hypothesis", "add_review"]


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


def check_quotes(conn, c: dict, quotes, create_spans: bool = True) -> list[dict]:
    """Exakte Suche im kanonischen Text innerhalb des übergebenen Bereichs (Kern + Kontext). Toleriert nur
    abweichenden Leerraum und umschließende Anführungszeichen, keine Wortänderungen."""
    u, text = c["unit"], c["text"]
    lo, hi = u["ctx_start"], u["ctx_end"]
    out = []
    if not isinstance(quotes, list):
        return out
    for q in quotes:
        if not isinstance(q, str) or not q.strip():
            out.append({"quote": q, "found": False, "method": "empty_or_not_string"})
            continue
        q2 = q.strip().strip("„“”\"'‚‘’«»").strip()
        idx = text.find(q2, lo, hi) if q2 else -1
        method = "exact"
        if idx < 0 and q2:
            pattern = r"\s+".join(re.escape(w) for w in q2.split())
            m = re.search(pattern, text[lo:hi])
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


def _start_run(conn, kind: str, adapter, prompt_version: str, cfg_llm: dict, inputs: dict) -> str:
    rid = db.new_run_id(kind)
    budget_id = adapter.budget.id if getattr(adapter, "budget", None) else None
    conn.execute(
        """INSERT INTO runs(id, kind, code_version, adapter, model, prompt_version, is_real_model_run, is_dry_run, config_json,
           input_hashes_json, started_at, status, budget_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (rid, kind, code_version(), adapter.name, adapter.model, prompt_version, 0, 0,
         db.dumps({k: v for k, v in cfg_llm.items() if "key" not in k.lower()}), db.dumps(inputs), db.now(), "running", budget_id))
    return rid


def _finish_run(conn, rid: str, status: str, error: str | None = None, res=None):
    conn.execute("UPDATE runs SET finished_at=?, status=?, error=?, usage_json=?, model=COALESCE(?, model), is_real_model_run=? WHERE id=?",
                 (db.now(), status, error, db.dumps({**(res.usage or {}), "call_id": res.call_id, "attempts": res.attempts}) if res else None,
                  res.model if res else None, int(bool(res and res.is_real_model_run)), rid))


def _save_raw(cfg: Config, rid: str, text: str) -> str:
    p = cfg.subdir("model_responses") / f"{rid}.txt"
    p.write_text(text, "utf-8")
    return str(p.relative_to(cfg.root))


def _call(cfg, conn, adapter, kind, system, user, pv, inputs):
    """Gemeinsamer Ablauf: Lauf anlegen, Aufruf über das Budget, Ergebnis oder Fehlerstatus."""
    cfg_llm = cfg.section("llm")
    rid = _start_run(conn, kind, adapter, pv, cfg_llm, inputs)
    try:
        res = adapter.complete(system, user, purpose=f"{kind}:{inputs.get('target')}", run_id=rid, raw_dir=cfg.subdir("model_calls"))
    except (NotConfigured, CallLimitReached) as e:
        _finish_run(conn, rid, "not_run", str(e))
        conn.commit()
        return rid, None, {"status": "not_run", "reason": str(e), "run_id": rid}
    except Exception as e:
        _finish_run(conn, rid, "model_error", repr(e)[:2000])
        conn.commit()
        return rid, None, {"status": "model_error", "reason": repr(e)[:500], "run_id": rid}
    return rid, res, None


def _reuse(conn, table: str, key_col: str, key: str, kind: str, prompt_version: str, budget_id: str | None):
    """Bereits im selben Budget bezahltes Ergebnis wiederverwenden statt erneut aufzurufen."""
    if not budget_id:
        return None
    return conn.execute(
        f"""SELECT t.* FROM {table} t JOIN runs r ON r.id=t.run_id WHERE t.{key_col}=? AND r.kind=? AND r.prompt_version=?
            AND r.budget_id=? AND r.status='finished' ORDER BY t.created_at LIMIT 1""", (key, kind, prompt_version, budget_id)).fetchone()


def estimate(cfg: Config, conn, comparison_ids: list[str]) -> dict:
    """Aufwandsschätzung vor einem Lauf (Zeichen/4 als grobe Tokenschätzung)."""
    system, pv = load_prompt("B_compare")
    total_in = 0
    for cid in comparison_ids:
        cmp_ = conn.execute("SELECT * FROM candidate_comparisons WHERE id=?", (cid,)).fetchone()
        lc, rc = unit_context(cfg, conn, cmp_["left_unit_id"]), unit_context(cfg, conn, cmp_["right_unit_id"])
        total_in += estimate_tokens(system + render_passage("L", lc) + render_passage("R", rc))
    mo = int(cfg.section("llm").get("max_tokens", 4000))
    return {"prompt_version": pv, "comparisons": len(comparison_ids), "model_calls": len(comparison_ids),
            "est_input_tokens": total_in, "max_output_tokens": mo * len(comparison_ids),
            "hinweis": "Grobe Schätzung (Zeichen/4). Kosten hängen vom Modell und Thinking-Aufwand ab und werden nicht zugesagt."}


def compare_user_message(cfg, conn, comparison_id: str) -> tuple[str, dict, dict]:
    cmp_ = conn.execute("SELECT * FROM candidate_comparisons WHERE id=?", (comparison_id,)).fetchone()
    lc, rc = unit_context(cfg, conn, cmp_["left_unit_id"]), unit_context(cfg, conn, cmp_["right_unit_id"])
    scope = json.loads(cmp_["corpus_scope_json"] or "{}")
    user = (f"Vergleichsbestand: Paar aus Suchwegen {cmp_['channels_json']}; durchsuchter Bestand: {scope or 'explizit angelegtes Paar'}.\n"
            f"Zeitliche Lage: {cmp_['temporal']}.\n\n" + render_passage("L", lc) + "\n\n" + render_passage("R", rc))
    return user, lc, rc


def compare(cfg: Config, conn, comparison_id: str, adapter=None, dry_run: bool = False, reuse: bool = True) -> dict:
    cfg_llm = cfg.section("llm")
    adapter = adapter or get_adapter(cfg_llm, conn=conn)
    system, pv = load_prompt("B_compare")
    user, lc, rc = compare_user_message(cfg, conn, comparison_id)
    if dry_run:
        return {"dry_run": True, "est_input_tokens": estimate_tokens(system + user), "prompt_version": pv}
    bid = adapter.budget.id if getattr(adapter, "budget", None) else None
    if reuse and (old := _reuse(conn, "relation_hypotheses", "comparison_id", comparison_id, "compare", pv, bid)):
        return {"status": old["evidence_status"], "hypothesis_id": old["id"], "run_id": old["run_id"], "reused": True,
                "relation_types": json.loads(old["relation_types_json"] or "[]")}
    inputs = {"target": comparison_id, "left_text_sha256": lc["unit"]["text_sha256"], "right_text_sha256": rc["unit"]["text_sha256"],
              "prompt_sha256": db.sha256_text(system)}
    rid, res, err = _call(cfg, conn, adapter, "compare", system, user, pv, inputs)
    if err:
        return err
    raw_path = _save_raw(cfg, rid, res.text)
    rec = assess_compare(conn, res.text, lc, rc)
    hid = f"rel-{uuid.uuid4().hex[:12]}"
    conn.execute(
        """INSERT INTO relation_hypotheses(id, comparison_id, run_id, kind, status, relation_types_json, payload_json, quote_check_json,
           raw_response_path, created_at, response_status, schema_status, schema_errors_json, anchor_status, judgment, evidence_status)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (hid, comparison_id, rid, "model_primary", rec["evidence_status"], db.dumps(rec["relation_types"]), db.dumps(rec["payload"]),
         db.dumps(rec["quote_check"]), raw_path, db.now(), rec["response_status"], rec["schema_status"], db.dumps(rec["schema_errors"]),
         rec["anchor_status"], rec["judgment"], rec["evidence_status"]))
    _finish_run(conn, rid, "finished", None, res)
    conn.commit()
    return {"status": rec["evidence_status"], "hypothesis_id": hid, "run_id": rid, "relation_types": rec["relation_types"],
            "schema_errors": rec["schema_errors"], "anchor_status": rec["anchor_status"], "model": res.model}


def assess_compare(conn, text: str, lc: dict, rc: dict) -> dict:
    """Reine Bewertung einer Antwort auf Prompt B (ohne Datenbankeintrag der Hypothese)."""
    try:
        payload = extract_json(text)
    except (ValueError, json.JSONDecodeError) as e:
        return {"payload": {"parse_error": str(e)}, "relation_types": [], "quote_check": {}, "response_status": "received_unparseable",
                "schema_status": "invalid", "schema_errors": [f"$: kein JSON-Objekt ({e})"], "anchor_status": "not_checked",
                "judgment": None, "evidence_status": "no_response"}
    errors = validate_compare(payload)
    rtypes = payload.get("relation_types") if isinstance(payload.get("relation_types"), list) else []
    qc = {"left": check_quotes(conn, lc, payload.get("left_quotes")), "right": check_quotes(conn, rc, payload.get("right_quotes"))}
    known = [t for t in rtypes if t in RELATION_TYPES]
    abstention = bool(known) and set(known) <= ABSTENTION_TYPES
    anchors = anchor_status(qc, ["left", "right"])
    return {"payload": payload, "relation_types": [t for t in rtypes if isinstance(t, str)], "quote_check": qc,
            "response_status": "received", "schema_status": "invalid" if errors else "valid", "schema_errors": errors,
            "anchor_status": anchors, "judgment": "abstention" if abstention else ",".join(known),
            "evidence_status": evidence_status(schema_errors=errors, anchors=anchors, abstention=abstention)}


def countercheck(cfg: Config, conn, hypothesis_id: str, adapter=None, reuse: bool = True) -> dict:
    cfg_llm = cfg.section("llm")
    adapter = adapter or get_adapter(cfg_llm, conn=conn)
    system, pv = load_prompt("C_countercheck")
    h = conn.execute("SELECT * FROM relation_hypotheses WHERE id=?", (hypothesis_id,)).fetchone()
    bid = adapter.budget.id if getattr(adapter, "budget", None) else None
    if reuse and bid:
        old = conn.execute("""SELECT t.* FROM relation_hypotheses t JOIN runs r ON r.id=t.run_id WHERE t.parent_id=? AND r.kind='countercheck'
                              AND r.prompt_version=? AND r.budget_id=? AND r.status='finished'""", (hypothesis_id, pv, bid)).fetchone()
        if old:
            return {"status": old["evidence_status"], "decision": old["judgment"], "hypothesis_id": old["id"], "reused": True}
    cmp_ = conn.execute("SELECT * FROM candidate_comparisons WHERE id=?", (h["comparison_id"],)).fetchone()
    lc, rc = unit_context(cfg, conn, cmp_["left_unit_id"]), unit_context(cfg, conn, cmp_["right_unit_id"])
    user = ("Vorgeschlagene Interpretation (zu prüfen):\n" + json.dumps(json.loads(h["payload_json"] or "{}"), ensure_ascii=False, indent=1)
            + "\n\n" + render_passage("L", lc) + "\n\n" + render_passage("R", rc))
    rid, res, err = _call(cfg, conn, adapter, "countercheck", system, user, pv, {"target": hypothesis_id})
    if err:
        return err
    raw_path = _save_raw(cfg, rid, res.text)
    rec = assess_countercheck(conn, res.text, lc, rc, h["evidence_status"])
    cid = f"rel-{uuid.uuid4().hex[:12]}"
    conn.execute(
        """INSERT INTO relation_hypotheses(id, comparison_id, run_id, kind, parent_id, status, relation_types_json, payload_json,
           quote_check_json, raw_response_path, created_at, response_status, schema_status, schema_errors_json, anchor_status, judgment,
           evidence_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cid, h["comparison_id"], rid, "model_countercheck", hypothesis_id, rec["evidence_status"],
         db.dumps(rec["payload"].get("corrected_relation_types") or []), db.dumps(rec["payload"]), db.dumps(rec["quote_check"]), raw_path,
         db.now(), rec["response_status"], rec["schema_status"], db.dumps(rec["schema_errors"]), rec["anchor_status"], rec["judgment"],
         rec["evidence_status"]))
    _finish_run(conn, rid, "finished", None, res)
    conn.commit()
    return {"status": rec["evidence_status"], "decision": rec["judgment"], "hypothesis_id": cid, "schema_errors": rec["schema_errors"],
            "anchor_status": rec["anchor_status"]}


def assess_countercheck(conn, text: str, lc: dict, rc: dict, parent_evidence: str | None) -> dict:
    """'confirmed' gilt nur dann als belegte Bestätigung, wenn die Gegenprüfung selbst auf beiden Seiten gültige Belege
    liefert UND die geprüfte Interpretation ihre Belegprüfung bestanden hat."""
    try:
        payload = extract_json(text)
    except (ValueError, json.JSONDecodeError) as e:
        return {"payload": {"parse_error": str(e)}, "quote_check": {}, "response_status": "received_unparseable", "schema_status": "invalid",
                "schema_errors": [f"$: kein JSON-Objekt ({e})"], "anchor_status": "not_checked", "judgment": None, "evidence_status": "no_response"}
    errors = validate_countercheck(payload)
    qc = {"left": check_quotes(conn, lc, payload.get("left_quotes")), "right": check_quotes(conn, rc, payload.get("right_quotes")),
          "parent_evidence_status": parent_evidence}
    decision = payload.get("decision") if payload.get("decision") in DECISIONS else None
    anchors = anchor_status({"left": qc["left"], "right": qc["right"]}, ["left", "right"])
    ev = evidence_status(schema_errors=errors, anchors=anchors, abstention=decision == "undecidable")
    if ev == "anchored" and decision == "confirmed" and parent_evidence != "anchored":
        ev = "anchors_failed"  # Bestätigung einer unbelegten Interpretation ist keine belegte Bestätigung
    return {"payload": payload, "quote_check": qc, "response_status": "received", "schema_status": "invalid" if errors else "valid",
            "schema_errors": errors, "anchor_status": anchors, "judgment": decision, "evidence_status": ev}


def reconstruct(cfg: Config, conn, unit_id: str, adapter=None, reuse: bool = True) -> dict:
    cfg_llm = cfg.section("llm")
    adapter = adapter or get_adapter(cfg_llm, conn=conn)
    system, pv = load_prompt("A_reconstruct")
    bid = adapter.budget.id if getattr(adapter, "budget", None) else None
    if reuse and (old := _reuse(conn, "claim_candidates", "unit_id", unit_id, "reconstruct", pv, bid)):
        return {"status": old["evidence_status"], "claim_candidate_id": old["id"], "reused": True}
    c = unit_context(cfg, conn, unit_id)
    rid, res, err = _call(cfg, conn, adapter, "reconstruct", system, render_passage("P", c), pv,
                          {"target": unit_id, "text_sha256": c["unit"]["text_sha256"]})
    if err:
        return err
    raw_path = _save_raw(cfg, rid, res.text)
    rec = assess_reconstruct(conn, res.text, c)
    cid = f"claim-{uuid.uuid4().hex[:12]}"
    conn.execute("""INSERT INTO claim_candidates(id, unit_id, run_id, status, payload_json, quote_check_json, raw_response_path, created_at,
                    response_status, schema_status, schema_errors_json, anchor_status, judgment, evidence_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                 (cid, unit_id, rid, rec["evidence_status"], db.dumps(rec["payload"]), db.dumps(rec["quote_check"]), raw_path, db.now(),
                  rec["response_status"], rec["schema_status"], db.dumps(rec["schema_errors"]), rec["anchor_status"], rec["judgment"],
                  rec["evidence_status"]))
    _finish_run(conn, rid, "finished", None, res)
    conn.commit()
    return {"status": rec["evidence_status"], "claim_candidate_id": cid, "schema_errors": rec["schema_errors"],
            "anchor_status": rec["anchor_status"], "model": res.model}


def assess_reconstruct(conn, text: str, c: dict) -> dict:
    try:
        payload = extract_json(text)
    except (ValueError, json.JSONDecodeError) as e:
        return {"payload": {"parse_error": str(e)}, "quote_check": [], "response_status": "received_unparseable", "schema_status": "invalid",
                "schema_errors": [f"$: kein JSON-Objekt ({e})"], "anchor_status": "not_checked", "judgment": None, "evidence_status": "no_response"}
    errors = validate_reconstruct(payload)
    per_claim = []
    for cl in payload.get("claims") or []:
        if not isinstance(cl, dict):
            continue
        own = check_quotes(conn, c, cl.get("quotes"))
        nested = []
        for key in ("explicit_definitions", "explicit_premises", "reasons", "qualifications"):
            items = cl.get(key) if isinstance(cl.get(key), list) else []
            nested += check_quotes(conn, c, [x.get("quote") for x in items if isinstance(x, dict)])
        per_claim.append({"claim": cl.get("claim"), "speaker_role": cl.get("speaker_role"), "quotes": own, "nested": nested})
    allq = [q for pc in per_claim for q in pc["quotes"] + pc["nested"]]
    if not allq:
        anchors = "none_provided"
    elif any(not q["found"] for q in allq):
        anchors = "incomplete"
    elif any(not any(q["found"] for q in pc["quotes"]) for pc in per_claim):
        anchors = "missing_side"
    else:
        anchors = "complete"
    abstention = payload.get("status") == "insufficient_context"
    return {"payload": payload, "quote_check": per_claim, "response_status": "received", "schema_status": "invalid" if errors else "valid",
            "schema_errors": errors, "anchor_status": anchors, "judgment": payload.get("status"),
            "evidence_status": evidence_status(schema_errors=errors, anchors=anchors, abstention=abstention)}


def add_manual_hypothesis(cfg: Config, conn, comparison_id: str, author: str, relation_types: list[str], payload: dict,
                          kind: str = "manual") -> str:
    """Menschliche Interpretation ohne Modell. Zitate werden genauso deterministisch geprüft."""
    cmp_ = conn.execute("SELECT * FROM candidate_comparisons WHERE id=?", (comparison_id,)).fetchone()
    lc, rc = unit_context(cfg, conn, cmp_["left_unit_id"]), unit_context(cfg, conn, cmp_["right_unit_id"])
    qc = {"left": check_quotes(conn, lc, payload.get("left_quotes", [])), "right": check_quotes(conn, rc, payload.get("right_quotes", []))}
    rtypes = [t for t in relation_types if t in RELATION_TYPES]
    abstention = bool(rtypes) and set(rtypes) <= ABSTENTION_TYPES
    anchors = anchor_status(qc, ["left", "right"])
    ev = evidence_status(schema_errors=[] if rtypes else ["relation_types: keine Auswahl"], anchors=anchors, abstention=abstention)
    if anchors == "none_provided" and not abstention:
        ev = "no_quotes"
    hid = f"rel-{uuid.uuid4().hex[:12]}"
    conn.execute(
        """INSERT INTO relation_hypotheses(id, comparison_id, kind, author, status, relation_types_json, payload_json, quote_check_json, created_at,
           response_status, schema_status, anchor_status, judgment, evidence_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (hid, comparison_id, kind, author, ev, db.dumps(rtypes), db.dumps(payload), db.dumps(qc), db.now(), "human",
         "valid" if rtypes else "invalid", anchors, ",".join(rtypes), ev))
    conn.commit()
    return hid


def add_review(conn, target_type: str, target_id: str, reviewer: str, decision: str, comment: str = "", corrected: dict | None = None) -> int:
    if decision not in DECISIONS:
        raise ValueError(decision)
    c = conn.execute("INSERT INTO reviews(target_type, target_id, reviewer, decision, comment, corrected_json, created_at) VALUES(?,?,?,?,?,?,?)",
                     (target_type, target_id, reviewer, decision, comment, db.dumps(corrected) if corrected else None, db.now()))
    conn.commit()
    return c.lastrowid
