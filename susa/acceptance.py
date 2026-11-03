"""Ausführung der zwölf Abnahmefälle und der formalen Mindestabnahme.

Jeder Fall wird in deterministisch prüfbare Teile (ohne Modell) und modellabhängige Teile zerlegt. Ohne
konfigurierten Modellzugang werden modellabhängige Teile als 'nicht ausgeführt' berichtet, nie als bestanden.
"""
from __future__ import annotations

import json

from . import analysis, db
from .config import Config, code_version
from .fixtures import cases, load_fixtures
from .llm import ReplayAdapter, get_adapter
from .search import Searcher, ensure_comparison, find_candidates, markers_for, marker_diff, source_index
from .segment import paragraph_coverage, segment_all
from .embed import embed_units
from .versions import current_version, read_text


def _units(conn, doc_id: str):
    return conn.execute("SELECT u.* FROM argument_units u JOIN document_versions v ON v.id=u.version_id WHERE v.is_current=1 AND u.document_id=? ORDER BY seq",
                        (doc_id,)).fetchall()


def _did(case, key):
    return f"synthetic:{case}:{key}"


def _model_check(conn, cfg, case: dict, adapter_name: str | None) -> dict:
    a, b = case["pair"]
    lu, ru = _units(conn, _did(case["id"], a))[0], _units(conn, _did(case["id"], b))[0]
    cid = ensure_comparison(conn, lu["id"], ru["id"], "acceptance_pair")
    adapter = get_adapter(cfg.section("llm"), adapter_name)
    res = analysis.compare(cfg, conn, cid, adapter=adapter)
    if res["status"] in ("not_run", "model_error"):
        return {"model_part": "nicht ausgeführt", "reason": res.get("reason"), "comparison_id": cid}
    h = conn.execute("SELECT * FROM relation_hypotheses WHERE id=?", (res["hypothesis_id"],)).fetchone()
    p = json.loads(h["payload_json"])
    rt = set(json.loads(h["relation_types_json"]))
    ok = True
    notes = []
    if case.get("expect_relations_any") and not rt & set(case["expect_relations_any"]):
        ok = False
        notes.append(f"erwartet eines von {case['expect_relations_any']}, erhalten {sorted(rt)}")
    if rt & set(case.get("expect_not", [])):
        ok = False
        notes.append(f"unerwünscht: {sorted(rt & set(case['expect_not']))}")
    ck = p.get("contribution_kind")
    if case.get("expect_contribution_any") and ck not in case["expect_contribution_any"]:
        ok = False
        notes.append(f"contribution_kind {ck}")
    if ck in case.get("expect_contribution_not", []):
        ok = False
        notes.append(f"contribution_kind {ck} unerwünscht")
    return {"model_part": "erfüllt" if ok else "nicht erfüllt", "relation_types": sorted(rt), "contribution_kind": ck,
            "hypothesis_status": h["status"], "notes": notes, "comparison_id": cid, "run_id": res["run_id"],
            "real_model_run": bool(conn.execute("SELECT is_real_model_run FROM runs WHERE id=?", (res["run_id"],)).fetchone()[0])}


def run_acceptance(cfg: Config, conn, adapter_name: str | None = None, embed_backend: str | None = None) -> dict:
    load_fixtures(cfg, conn)
    segment_all(cfg, conn, [r["id"] for r in conn.execute("SELECT id FROM documents WHERE is_synthetic=1")])
    emb = embed_units(cfg, conn, embed_backend)
    s = Searcher(cfg, conn)
    results = []
    by_id = {c["id"]: c for c in cases()}

    def add(cid, det, det_ok, model=None, support="unterstützt"):
        results.append({"case": cid, "title": by_id[cid]["title"], "expectation": by_id[cid]["expectation"], "support": support,
                        "deterministic": det, "deterministic_ok": det_ok, "model": model})

    # Fälle mit Paarvergleich: Retrieval-Teil deterministisch (wird das Partnerstück über die Suchwege gefunden?)
    for cid in ["case01", "case02", "case04", "case07", "case09", "case10", "case11"]:
        c = by_id[cid]
        a, b = c["pair"]
        lu, ru = _units(conn, _did(cid, a))[0], _units(conn, _did(cid, b))[0]
        fc = find_candidates(cfg, conn, lu["id"], prefix="synthetic:", searcher=s)
        cmp_id = f"cmp:{lu['id']}|{ru['id']}"
        row = conn.execute("SELECT channels_json, markers_json FROM candidate_comparisons WHERE id=?", (cmp_id,)).fetchone()
        chans = json.loads(row["channels_json"]) if row else []
        found = any(ch in chans for ch in ("semantic", "lexical"))
        det = {"partner_found_via": chans, "units_searched": fc["scope"]["units_searched"],
               "embedding_test_vectors": fc["scope"]["embedding_is_test_vectors"],
               "markers": json.loads(row["markers_json"]) if row else marker_diff(lu["text"], ru["text"])}
        det_ok = found
        if cid == "case11":
            det["negation_hint"] = any("Negation" in m for m in det["markers"])
            det_ok = found and det["negation_hint"]
        add(cid, det, det_ok, _model_check(conn, cfg, c, adapter_name))

    # Fall 3: Mehrsprachigkeit
    c = by_id["case03"]
    lu, ru = _units(conn, _did("case03", "A"))[0], _units(conn, _did("case03", "B"))[0]
    sem = dict(s.semantic_for_unit(lu["id"], 10 ** 6, exclude_doc=lu["document_id"], synthetic=1, prefix="synthetic:"))
    add("case03", {"semantic_score_to_translation": round(sem[ru["id"]], 4) if ru["id"] in sem else None,
                   "semantic_rank": (list(sem).index(ru["id"]) + 1) if ru["id"] in sem else None,
                   "units_ranked": len(sem),
                   "hinweis": "Englisches Embedding-Modell; sprachübergreifende Nähe ist nicht belastbar."},
        None, _model_check(conn, cfg, c, adapter_name), support="ausdrücklich noch nicht unterstützt (Mehrsprachigkeit)")

    # Fall 5: späte Passage
    c = by_id["case05"]
    did = _did("case05", "A")
    v = current_version(conn, did)
    text = read_text(cfg, v)
    pos = text.find(c["late_paragraph"])
    units = _units(conn, did)
    holder = [u for u in units if u["start_char"] <= pos < u["end_char"]]
    q_sem = s.semantic_for_query(c["query"], 3, exclude_doc=None, synthetic=1, prefix="synthetic:case05")
    q_lex = s.lexical(c["query"], 3, exclude_doc=None, synthetic=1, prefix="synthetic:case05")
    cov = paragraph_coverage(conn, v["id"], text)
    hid = holder[0]["id"] if holder else None
    det = {"text_chars": len(text), "late_paragraph_offset": pos, "units": len(units),
           "late_unit": hid, "late_unit_is_embedded": bool(hid and hid in s.store.index),
           "paragraph_coverage": cov["coverage"], "paragraphs_not_fully_covered": cov["paragraphs_not_fully_covered"],
           "semantic_top3": [u for u, _ in q_sem], "lexical_top3": [u for u, _ in q_lex]}
    det_ok = bool(pos > 24000 and hid and det["late_unit_is_embedded"] and cov["coverage"] == 1.0
                  and (hid in det["semantic_top3"] or hid in det["lexical_top3"]))
    add("case05", det, det_ok, None)

    # Fall 6: Zitat im Absatz
    c = by_id["case06"]
    v = current_version(conn, _did("case06", "A"))
    spans = conn.execute("SELECT * FROM spans WHERE version_id=? AND origin='quote_heuristic'", (v["id"],)).fetchall()
    det = {"quote_spans": [{"text": sp["text"], "speaker": sp["speaker"]} for sp in spans]}
    det_ok = any(sp["text"] == c["quoted"] and sp["speaker"] == "quoted_other" for sp in spans)
    u = _units(conn, _did("case06", "A"))[0]
    adapter = get_adapter(cfg.section("llm"), adapter_name)
    r = analysis.reconstruct(cfg, conn, u["id"], adapter=adapter)
    model = {"model_part": "nicht ausgeführt", "reason": r.get("reason")} if r["status"] == "not_run" else {"model_part": "auszuwerten", **r}
    if r["status"] != "not_run":
        p = json.loads(conn.execute("SELECT payload_json FROM claim_candidates WHERE id=?", (r["claim_candidate_id"],)).fetchone()[0])
        roles = [(cl.get("claim"), cl.get("speaker_role")) for cl in p.get("claims", [])]
        bad = [cl for cl, role in roles if role == "author" and "leiden" in (cl or "") and "kein" not in (cl or "").lower() and "nicht" not in (cl or "").lower()]
        model.update({"claims": roles, "model_part": "nicht erfüllt" if bad else "erfüllt"})
    add("case06", det, det_ok, model)

    # Fall 8: Mehrfachzitate derselben Quelle
    idx = source_index(conn, min_docs=1, synthetic=1)
    case8 = [x for x in idx if any(d.startswith("synthetic:case08") for d in x["documents"])]
    det = {"sources": [{"target": x["target"], "n_documents": x["n_documents"]} for x in case8]}
    det_ok = any(x["n_documents"] == 5 for x in case8) and any(x["n_documents"] == 1 and x["documents"] == ["synthetic:case08:S6"] for x in case8)
    add("case08", det, det_ok, None)

    # Fall 12: zwei Analyseversionen desselben unveränderten Texts
    c = by_id["case12"]
    lu, ru = _units(conn, _did("case12", "A"))[0], _units(conn, _did("case12", "B"))[0]
    cid = ensure_comparison(conn, lu["id"], ru["id"], "acceptance_pair")
    replies = [json.dumps({"relation_types": ["supports"], "left_quotes": [], "right_quotes": [], "contribution_kind": "unclear"}),
               json.dumps({"relation_types": ["restricts_scope"], "left_quotes": [], "right_quotes": [], "contribution_kind": "reasoned_extension"})]
    rep = ReplayAdapter({"max_calls_per_run": 5}, replies)
    rev_before = conn.execute("SELECT COUNT(*) FROM revisions WHERE entity_type='document_text' AND entity_id IN (?,?)",
                              (lu["document_id"], ru["document_id"])).fetchone()[0]
    r1, r2 = analysis.compare(cfg, conn, cid, adapter=rep), analysis.compare(cfg, conn, cid, adapter=rep)
    rev_after = conn.execute("SELECT COUNT(*) FROM revisions WHERE entity_type='document_text' AND entity_id IN (?,?)",
                             (lu["document_id"], ru["document_id"])).fetchone()[0]
    versions = conn.execute("SELECT COUNT(*) FROM document_versions WHERE document_id IN (?,?)", (lu["document_id"], ru["document_id"])).fetchone()[0]
    det = {"hypotheses": [r1["hypothesis_id"], r2["hypothesis_id"]], "runs": [r1["run_id"], r2["run_id"]],
           "text_revisions_added": rev_after - rev_before, "document_versions": versions,
           "hinweis": "Replay-Adapter simuliert zwei Analyseversionen; kein echter Modelllauf."}
    det_ok = r1["run_id"] != r2["run_id"] and rev_after == rev_before and versions == 2
    add("case12", det, det_ok, None)

    results.sort(key=lambda r: r["case"])
    formal = formal_checks(cfg, conn)
    rid = db.new_run_id("acceptance")
    report = {"run_id": rid, "code_version": code_version(), "embedding": emb, "adapter": adapter_name or cfg.section("llm").get("adapter"),
              "cases": results, "formal": formal}
    conn.execute("INSERT INTO runs(id, kind, code_version, started_at, finished_at, status, usage_json) VALUES(?,?,?,?,?,?,?)",
                 (rid, "acceptance", code_version(), db.now(), db.now(), "finished", db.dumps({"cases": len(results)})))
    conn.commit()
    return report


def formal_checks(cfg: Config, conn) -> list[dict]:
    out = []
    # 1. Alle gespeicherten Zitatspannen verweisen exakt auf gespeicherte Textstellen
    spans = conn.execute("SELECT s.*, v.text_path FROM spans s JOIN document_versions v ON v.id=s.version_id").fetchall()
    cache, bad = {}, 0
    for sp in spans:
        t = cache.setdefault(sp["text_path"], (cfg.root / sp["text_path"]).read_text("utf-8"))
        if t[sp["start_char"]:sp["end_char"]] != sp["text"]:
            bad += 1
    out.append({"check": "Zitatspannen exakt im gespeicherten Text", "n": len(spans), "fehler": bad, "ok": bad == 0})
    units = conn.execute("SELECT u.*, v.text_path FROM argument_units u JOIN document_versions v ON v.id=u.version_id").fetchall()
    bad = sum(1 for u in units if cache.setdefault(u["text_path"], (cfg.root / u["text_path"]).read_text("utf-8"))[u["start_char"]:u["end_char"]] != u["text"])
    out.append({"check": "Einheitenanker exakt im gespeicherten Text", "n": len(units), "fehler": bad, "ok": bad == 0})
    vers = conn.execute("SELECT * FROM document_versions WHERE text_path IS NOT NULL").fetchall()
    bad = sum(1 for v in vers if db.sha256_text((cfg.root / v["text_path"]).read_text("utf-8")) != v["text_sha256"])
    out.append({"check": "Textdateien entsprechen gespeichertem SHA-256", "n": len(vers), "fehler": bad, "ok": bad == 0})
    dup = conn.execute("SELECT COUNT(*) FROM (SELECT document_id, text_sha256, COUNT(*) c FROM document_versions WHERE text_sha256 IS NOT NULL GROUP BY 1,2 HAVING c>1)").fetchone()[0]
    out.append({"check": "Keine doppelten Textversionen bei wiederholtem Import", "fehler": dup, "ok": dup == 0})
    fake = conn.execute("SELECT COUNT(*) FROM runs WHERE is_real_model_run=1 AND adapter IN ('none','replay')").fetchone()[0]
    out.append({"check": "Kein Platzhalter als echter Modelllauf markiert", "fehler": fake, "ok": fake == 0})
    mixed = conn.execute("""SELECT COUNT(*) FROM candidate_comparisons c JOIN argument_units l ON l.id=c.left_unit_id JOIN argument_units r ON r.id=c.right_unit_id
                            JOIN documents dl ON dl.id=l.document_id JOIN documents dr ON dr.id=r.document_id WHERE dl.is_synthetic != dr.is_synthetic""").fetchone()[0]
    out.append({"check": "Keine Vergleiche zwischen synthetischen und echten Texten", "fehler": mixed, "ok": mixed == 0})
    return out


def render_markdown(rep: dict) -> str:
    L = [f"# Abnahmebericht {rep['run_id']}", "", f"- Codeversion: `{rep['code_version']}`",
         f"- Embedding: `{rep['embedding']['set_id']}` (Testvektoren: {rep['embedding']['is_test_vectors']})",
         f"- Modelladapter: `{rep['adapter']}`", "",
         "Synthetische Funktionstests, keine Evaluation an echten Texten. 'Nicht ausgeführt' heißt: ohne Modellzugang nicht geprüft.", "",
         "| Fall | Titel | Unterstützung | Deterministischer Teil | Modellteil |", "|---|---|---|---|---|"]
    for r in rep["cases"]:
        d = "–" if r["deterministic_ok"] is None else ("erfüllt" if r["deterministic_ok"] else "NICHT erfüllt")
        m = "–" if r["model"] is None else r["model"].get("model_part")
        L.append(f"| {r['case']} | {r['title']} | {r['support']} | {d} | {m} |")
    L += ["", "## Formale Mindestabnahme", "", "| Prüfung | Fehler | Ergebnis |", "|---|---|---|"]
    for f in rep["formal"]:
        L.append(f"| {f['check']} | {f['fehler']} | {'ok' if f['ok'] else 'FEHLER'} |")
    L += ["", "## Details", ""]
    for r in rep["cases"]:
        L += [f"### {r['case']} {r['title']}", "", f"Erwartung: {r['expectation']}", "", "```json",
              json.dumps({"deterministic": r["deterministic"], "model": r["model"]}, ensure_ascii=False, indent=1), "```", ""]
    return "\n".join(L)
