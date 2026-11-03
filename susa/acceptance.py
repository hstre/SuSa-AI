"""Abnahmefälle (Version 2) und formale Mindestabnahme.

Ergebnisse je Prüfung: bestanden | gescheitert | unentscheidbar | nicht ausgeführt | nicht unterstützt.
Ein Modellteil besteht nur, wenn (1) eine Antwort empfangen wurde, (2) das Schema gültig ist, (3) die Belege auf
den erforderlichen Seiten gefunden wurden und (4) der rekonstruierte Inhalt die Erwartung erfüllt. Eine begründete
Enthaltung ist 'unentscheidbar', außer der Fall lässt sie ausdrücklich zu.

Jede Zeile trägt die Art des Laufs: 'echt' (echter Modelldienst), 'replay' (Funktionstest mit vorbereiteten
Antworten) oder 'kein Modell'. Replay-Ergebnisse sind Funktionstests, keine Modellabnahme.

Retrieval-Prüfungen werten nur die Suchwege des aktuellen Suchlaufs aus. Suchparameter sind gegenüber Version 1
unverändert; deutsche Fälle durchsuchen denselben Bestand wie in Version 1.
"""
from __future__ import annotations

import json

from . import analysis, db
from .config import Config, code_version
from .embed import embed_units
from .fixtures import MODEL_CHECKS, POOL_PREFIXES, cases, doc_id, load_fixtures
from .llm import ReplayAdapter, get_adapter
from .search import Searcher, ensure_comparison, find_candidates, marker_diff, source_index
from .segment import paragraph_coverage, segment_all
from .versions import current_version, read_text

PAIR_CASES = ["case01", "case02", "case04", "case07", "case09", "case10", "case11"]
LANG_VARIANTS = {"case01": ["de", "en"], "case02": ["de", "en"], "case04": ["de", "en"], "case07": ["de", "en"], "case09": ["de", "en"],
                 "case10": ["de", "en"], "case11": ["de", "en"], "case06": ["de", "en"], "case08": ["de", "en"]}


def _units(conn, did: str):
    return conn.execute("""SELECT u.* FROM argument_units u JOIN document_versions v ON v.id=u.version_id
                           WHERE v.is_current=1 AND u.document_id=? ORDER BY seq""", (did,)).fetchall()


def _run_kind(conn, run_id: str | None) -> str:
    if not run_id:
        return "kein Modell"
    r = conn.execute("SELECT adapter, is_real_model_run FROM runs WHERE id=?", (run_id,)).fetchone()
    if r is None:
        return "?"
    return "echt" if r["is_real_model_run"] else ("replay" if r["adapter"] == "replay" else "kein Modell")


def judge_compare(conn, case: dict, h) -> dict:
    """Bewertung einer gespeicherten Prompt-B-Hypothese gegen die Fallerwartung."""
    p = json.loads(h["payload_json"] or "{}")
    rt = set(json.loads(h["relation_types_json"] or "[]"))
    ev = h["evidence_status"]
    out = {"evidence_status": ev, "schema_errors": json.loads(h["schema_errors_json"] or "[]"), "anchor_status": h["anchor_status"],
           "relation_types": sorted(rt), "contribution_kind": p.get("contribution_kind"), "hypothesis_id": h["id"],
           "run_kind": _run_kind(conn, h["run_id"]), "notes": []}
    if ev in ("no_response", "schema_invalid"):
        out["result"] = "gescheitert"
        out["notes"].append("Antwort unbrauchbar oder Schema ungültig")
        return out
    if ev == "anchors_failed":
        out["result"] = "gescheitert"
        out["notes"].append(f"Belegprüfung nicht bestanden ({h['anchor_status']})")
        return out
    if ev == "abstention":
        ok = MODEL_CHECKS.get(case["id"], {}).get("abstention_ok", False)
        out["result"] = "bestanden" if ok else "unentscheidbar"
        out["notes"].append("begründete Enthaltung" + (" (laut Fall zulässig)" if ok else ""))
        return out
    notes = []
    if case.get("expect_relations_any") and not rt & set(case["expect_relations_any"]):
        notes.append(f"erwartet eines von {case['expect_relations_any']}, erhalten {sorted(rt)}")
    if rt & set(case.get("expect_not", [])):
        notes.append(f"unerwünscht: {sorted(rt & set(case['expect_not']))}")
    ck = p.get("contribution_kind")
    if case.get("expect_contribution_any") and ck not in case["expect_contribution_any"]:
        notes.append(f"contribution_kind {ck}, erwartet {case['expect_contribution_any']}")
    if ck in case.get("expect_contribution_not", []):
        notes.append(f"contribution_kind {ck} unerwünscht")
    out["notes"] = notes
    out["result"] = "gescheitert" if notes else "bestanden"
    return out


def _overlaps(q: dict, s: int, e: int) -> bool:
    return q.get("found") and q["start_char"] < e and s < q["end_char"]


def judge_reconstruct(cfg, conn, case: dict, lang: str, cc) -> dict:
    p = json.loads(cc["payload_json"] or "{}")
    qc = json.loads(cc["quote_check_json"] or "[]")
    ev = cc["evidence_status"]
    claims = p.get("claims") if isinstance(p.get("claims"), list) else []
    out = {"evidence_status": ev, "schema_errors": json.loads(cc["schema_errors_json"] or "[]"), "anchor_status": cc["anchor_status"],
           "claims": [{"claim": x.get("claim"), "speaker_role": x.get("speaker_role"), "statement_types": x.get("statement_types")}
                      for x in claims if isinstance(x, dict)],
           "claim_candidate_id": cc["id"], "run_kind": _run_kind(conn, cc["run_id"]), "notes": []}
    if ev in ("no_response", "schema_invalid", "anchors_failed"):
        out["result"] = "gescheitert"
        out["notes"].append(f"{ev}: {out['schema_errors'][:3] or cc['anchor_status']}")
        return out
    if ev == "abstention":
        out["result"] = "unentscheidbar"
        out["notes"].append("insufficient_context")
        return out
    if not claims:
        out["result"] = "gescheitert"
        out["notes"].append("leere Behauptungsliste")
        return out
    chk = MODEL_CHECKS.get(case["id"], {})
    notes = []
    if "speaker_spans" in chk:
        unit = conn.execute("SELECT * FROM claim_candidates WHERE id=?", (cc["id"],)).fetchone()
        u = conn.execute("SELECT * FROM argument_units WHERE id=?", (unit["unit_id"],)).fetchone()
        text = read_text(cfg, conn.execute("SELECT * FROM document_versions WHERE id=?", (u["version_id"],)).fetchone())
        spans = {}
        for role, s in chk["speaker_spans"][lang].items():
            i = text.find(s)
            spans[role] = (i, i + len(s))
        def claims_for(role_span):
            s, e = spans[role_span]
            return [pc for pc in qc if any(_overlaps(q, s, e) for q in pc["quotes"])]
        quoted = claims_for("quoted_other")
        own = claims_for("author")
        if not any(pc["speaker_role"] == "quoted_other" for pc in quoted):
            notes.append("referierte Fremdposition nicht als quoted_other belegt")
        # Fehlzuschreibung: eine author-Behauptung, deren Belege ausschließlich im Fremdzitat liegen (ein Beleg wie
        # "Manche schreiben: „…“" reicht über das Zitat hinaus und ist ein zulässiger Bericht des Autors)
        qs, qe = spans["quoted_other"]
        inside = lambda q: q.get("found") and q["start_char"] >= qs - 2 and q["end_char"] <= qe + 2
        if any(pc["speaker_role"] == "author" and pc["quotes"] and all(inside(q) for q in pc["quotes"]) for pc in qc):
            notes.append("Fremdposition fälschlich dem Autor zugeschrieben")
        if not any(pc["speaker_role"] == "author" for pc in own):
            notes.append("eigener Einwand des Autors nicht als author belegt")
    if chk.get("need_statement_type"):
        if not any(chk["need_statement_type"] in (x.get("statement_types") or []) for x in claims if isinstance(x, dict)):
            notes.append(f"keine Behauptung vom Typ {chk['need_statement_type']}")
    if chk.get("need_reconstructed_premise"):
        if not any((x.get("reconstructed_premises") or []) for x in claims if isinstance(x, dict)):
            notes.append("keine rekonstruierte (nicht ausdrückliche) Voraussetzung ausgewiesen")
    out["notes"] = notes
    out["result"] = "gescheitert" if notes else "bestanden"
    return out


def _latest(conn, sql: str, args) :
    return conn.execute(sql + " ORDER BY created_at DESC LIMIT 1", args).fetchone()


def run_acceptance(cfg: Config, conn, adapter_name: str | None = None, embed_backend: str | None = None, *, budget_id: str | None = None,
                   model_plan: set[str] | None = None, countercheck_plan: set[str] | None = None, adapter=None) -> dict:
    """model_plan: Menge von Schlüsseln 'B:<fall>:<sprache>' bzw. 'A:<fall>:<sprache>', die mit dem Modell geprüft werden
    (None = alle). countercheck_plan: Schlüssel 'C:<fall>:<sprache>' für Gegenprüfungen."""
    load_fixtures(cfg, conn)
    segment_all(cfg, conn, [r["id"] for r in conn.execute("SELECT id FROM documents WHERE is_synthetic=1")])
    emb = embed_units(cfg, conn, embed_backend)
    s = Searcher(cfg, conn)
    by_id = {c["id"]: c for c in cases()}
    if adapter is None:
        adapter = get_adapter(cfg.section("llm"), adapter_name, conn=conn, budget_id=budget_id)
    results = []
    stop = {"reason": None}

    def planned(key):
        return model_plan is None or key in model_plan

    def add(cid, lang, part, result, detail, support="unterstützt"):
        results.append({"case": cid, "lang": lang, "part": part, "title": by_id[cid]["title"], "expectation": by_id[cid]["expectation"],
                        "support": support, "result": result, "detail": detail})

    def model_compare(cid, lang, lu, ru):
        key = f"B:{cid}:{lang}"
        if not planned(key):
            return add(cid, lang, "Modell B", "nicht ausgeführt", {"reason": "nicht im Modellplan"})
        cmp_id = ensure_comparison(conn, lu["id"], ru["id"], "acceptance_pair")
        r = analysis.compare(cfg, conn, cmp_id, adapter=adapter)
        if r["status"] in ("not_run", "model_error"):
            if "erschöpft" in (r.get("reason") or ""):
                stop["reason"] = r["reason"]
            return add(cid, lang, "Modell B", "nicht ausgeführt" if r["status"] == "not_run" else "gescheitert",
                       {"reason": r.get("reason"), "run_kind": _run_kind(conn, r.get("run_id"))})
        h = conn.execute("SELECT * FROM relation_hypotheses WHERE id=?", (r["hypothesis_id"],)).fetchone()
        j = judge_compare(conn, by_id[cid], h)
        j["reused"] = bool(r.get("reused"))
        add(cid, lang, "Modell B", j["result"], j)
        ckey = f"C:{cid}:{lang}"
        if countercheck_plan and ckey in countercheck_plan:
            c = analysis.countercheck(cfg, conn, h["id"], adapter=adapter)
            if c["status"] in ("not_run", "model_error"):
                add(cid, lang, "Modell C", "nicht ausgeführt" if c["status"] == "not_run" else "gescheitert", {"reason": c.get("reason")})
            else:
                ch = conn.execute("SELECT * FROM relation_hypotheses WHERE id=?", (c["hypothesis_id"],)).fetchone()
                res = {"anchored": "bestanden", "abstention": "unentscheidbar"}.get(ch["evidence_status"], "gescheitert")
                add(cid, lang, "Modell C", res, {"decision": ch["judgment"], "evidence_status": ch["evidence_status"],
                                                 "anchor_status": ch["anchor_status"], "schema_errors": json.loads(ch["schema_errors_json"] or "[]"),
                                                 "parent_evidence_status": h["evidence_status"], "problems_found": json.loads(ch["payload_json"]).get("problems_found"),
                                                 "run_kind": _run_kind(conn, ch["run_id"]), "hypothesis_id": ch["id"],
                                                 "hinweis": "'bestanden' = Gegenprüfung formal belegt; sagt nichts darüber, ob sie inhaltlich zustimmt"})

    def model_reconstruct(cid, lang, unit):
        key = f"A:{cid}:{lang}"
        if not planned(key):
            return add(cid, lang, "Modell A", "nicht ausgeführt", {"reason": "nicht im Modellplan"})
        r = analysis.reconstruct(cfg, conn, unit["id"], adapter=adapter)
        if r["status"] in ("not_run", "model_error"):
            if "erschöpft" in (r.get("reason") or ""):
                stop["reason"] = r["reason"]
            return add(cid, lang, "Modell A", "nicht ausgeführt" if r["status"] == "not_run" else "gescheitert", {"reason": r.get("reason")})
        cc = conn.execute("SELECT * FROM claim_candidates WHERE id=?", (r["claim_candidate_id"],)).fetchone()
        j = judge_reconstruct(cfg, conn, by_id[cid], lang, cc)
        j["reused"] = bool(r.get("reused"))
        add(cid, lang, "Modell A", j["result"], j)

    # --- Paarfälle: Retrieval (deterministisch) und Modell B
    for cid in PAIR_CASES:
        c = by_id[cid]
        a, b = c["pair"]
        for lang in LANG_VARIANTS[cid]:
            lu, ru = _units(conn, doc_id(cid, a, lang))[0], _units(conn, doc_id(cid, b, lang))[0]
            fc = find_candidates(cfg, conn, lu["id"], prefix=POOL_PREFIXES[lang], searcher=s)
            this = fc["this_run"].get(ru["id"], {"channels": [], "scores": {}})
            found = any(ch in this["channels"] for ch in ("semantic", "lexical"))
            sem_all = dict(s.semantic_for_unit(lu["id"], 10 ** 6, exclude_doc=lu["document_id"], synthetic=1, prefix=POOL_PREFIXES[lang]))
            det = {"partner_found_via": this["channels"], "scores": this["scores"],
                   "semantic_rank_full": (list(sem_all).index(ru["id"]) + 1) if ru["id"] in sem_all else None,
                   "semantic_score": round(sem_all[ru["id"]], 4) if ru["id"] in sem_all else None,
                   "units_searched": fc["scope"]["units_searched"], "embedding_test_vectors": fc["scope"]["embedding_is_test_vectors"],
                   "markers": marker_diff(lu["text"], ru["text"])}
            ok = found
            if cid == "case11":
                det["negation_hint"] = any("Negation" in m for m in det["markers"])
                ok = found and det["negation_hint"]
            add(cid, lang, "Retrieval", "bestanden" if ok else "gescheitert", det)
            if cid == "case07":
                model_reconstruct(cid, lang, _units(conn, doc_id(cid, MODEL_CHECKS["case07"]["reconstruct_key"], lang))[0])
            model_compare(cid, lang, lu, ru)

    # --- Fall 3: sprachübergreifend (ausdrücklich nicht unterstützt)
    lu, ru = _units(conn, doc_id("case03", "A"))[0], _units(conn, doc_id("case03", "B"))[0]
    sem = dict(s.semantic_for_unit(lu["id"], 10 ** 6, exclude_doc=lu["document_id"], synthetic=1, prefix=POOL_PREFIXES["de"]))
    add("case03", "de+en", "Retrieval", "nicht unterstützt",
        {"semantic_score_to_translation": round(sem[ru["id"]], 4) if ru["id"] in sem else None,
         "semantic_rank": (list(sem).index(ru["id"]) + 1) if ru["id"] in sem else None, "units_ranked": len(sem),
         "hinweis": "Englisches Embedding-Modell; sprachübergreifende Nähe ist nicht belastbar."},
        support="ausdrücklich noch nicht unterstützt (Mehrsprachigkeit)")
    model_compare("case03", "de+en", lu, ru)

    # --- Fall 5: späte Passage
    c = by_id["case05"]
    did = doc_id("case05", "A")
    v = current_version(conn, did)
    text = read_text(cfg, v)
    pos = text.find(c["late_paragraph"])
    units = _units(conn, did)
    holder = [u for u in units if u["start_char"] <= pos < u["end_char"]]
    q_sem = s.semantic_for_query(c["query"], 3, exclude_doc=None, synthetic=1, prefix="synthetic:case05")
    q_lex = s.lexical(c["query"], 3, exclude_doc=None, synthetic=1, prefix="synthetic:case05")
    cov = paragraph_coverage(conn, v["id"], text)
    hid = holder[0]["id"] if holder else None
    det = {"text_chars": len(text), "late_paragraph_offset": pos, "units": len(units), "late_unit": hid,
           "late_unit_is_embedded": bool(hid and hid in s.store.index), "paragraph_coverage": cov["coverage"],
           "semantic_top3": [u for u, _ in q_sem], "lexical_top3": [u for u, _ in q_lex]}
    ok = bool(pos > 24000 and hid and det["late_unit_is_embedded"] and cov["coverage"] == 1.0
              and (hid in det["semantic_top3"] or hid in det["lexical_top3"]))
    add("case05", "en", "Retrieval", "bestanden" if ok else "gescheitert", det)

    # --- Fall 6: Sprecher (deterministischer Hinweis + Modell A mit positiver Sprecherprüfung)
    for lang in LANG_VARIANTS["case06"]:
        v = current_version(conn, doc_id("case06", "A", lang))
        spans = conn.execute("SELECT * FROM spans WHERE version_id=? AND origin='quote_heuristic'", (v["id"],)).fetchall()
        target = MODEL_CHECKS["case06"]["speaker_spans"][lang]["quoted_other"]
        ok = any(target in sp["text"] and sp["speaker"] == "quoted_other" for sp in spans)
        add("case06", lang, "Zitat-Heuristik", "bestanden" if ok else "gescheitert",
            {"quote_spans": [{"text": sp["text"], "speaker": sp["speaker"]} for sp in spans]})
        model_reconstruct("case06", lang, _units(conn, doc_id("case06", "A", lang))[0])

    # --- Fall 8: Mehrfachzitate derselben Quelle
    idx = source_index(conn, min_docs=1, synthetic=1)
    for lang in LANG_VARIANTS["case08"]:
        pre = doc_id("case08", "", lang)
        case8 = [x for x in idx if any(d.startswith(pre) for d in x["documents"])]
        case8 = [{**x, "documents": [d for d in x["documents"] if d.startswith(pre)]} for x in case8]
        ok = any(len(x["documents"]) == 5 for x in case8) and any(x["documents"] == [doc_id("case08", "S6", lang)] for x in case8)
        add("case08", lang, "Quellenindex", "bestanden" if ok else "gescheitert",
            {"sources": [{"target": x["target"], "n_documents": len(x["documents"])} for x in case8]})

    # --- Fall 12: zwei Analyseversionen desselben unveränderten Texts (Replay-Funktionstest)
    lu, ru = _units(conn, doc_id("case12", "A"))[0], _units(conn, doc_id("case12", "B"))[0]
    cid = ensure_comparison(conn, lu["id"], ru["id"], "acceptance_pair")
    rep = ReplayAdapter({}, [json.dumps({"relation_types": ["supports"]}), json.dumps({"relation_types": ["restricts_scope"]})])
    rev_before = conn.execute("SELECT COUNT(*) FROM revisions WHERE entity_type='document_text' AND entity_id IN (?,?)",
                              (lu["document_id"], ru["document_id"])).fetchone()[0]
    r1, r2 = analysis.compare(cfg, conn, cid, adapter=rep, reuse=False), analysis.compare(cfg, conn, cid, adapter=rep, reuse=False)
    rev_after = conn.execute("SELECT COUNT(*) FROM revisions WHERE entity_type='document_text' AND entity_id IN (?,?)",
                             (lu["document_id"], ru["document_id"])).fetchone()[0]
    versions = conn.execute("SELECT COUNT(*) FROM document_versions WHERE document_id IN (?,?)", (lu["document_id"], ru["document_id"])).fetchone()[0]
    ok = r1["run_id"] != r2["run_id"] and rev_after == rev_before and versions == 2
    add("case12", "de", "Versionierung", "bestanden" if ok else "gescheitert",
        {"runs": [r1["run_id"], r2["run_id"]], "text_revisions_added": rev_after - rev_before, "document_versions": versions,
         "run_kind": "replay", "hinweis": "Replay-Funktionstest; Antworten sind absichtlich schemaungültig, geprüft wird nur die Versionierung."})

    results.sort(key=lambda r: (r["case"], r["lang"], r["part"]))
    formal = formal_checks(cfg, conn)
    rid = db.new_run_id("acceptance")
    budget = None
    if getattr(adapter, "budget", None):
        from .llm import budget_status
        budget = budget_status(conn, adapter.budget.id)
    report = {"run_id": rid, "code_version": code_version(), "embedding": emb, "adapter": adapter.name, "budget": budget,
              "stopped": stop["reason"], "cases": results, "formal": formal}
    conn.execute("INSERT INTO runs(id, kind, code_version, started_at, finished_at, status, usage_json, budget_id) VALUES(?,?,?,?,?,?,?,?)",
                 (rid, "acceptance", code_version(), db.now(), db.now(), "finished", db.dumps({"rows": len(results)}),
                  adapter.budget.id if getattr(adapter, "budget", None) else None))
    conn.commit()
    return report


def formal_checks(cfg: Config, conn) -> list[dict]:
    out = []
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
    fake = conn.execute("SELECT COUNT(*) FROM runs WHERE is_real_model_run=1 AND adapter NOT IN ('anthropic_api','claude_cli')").fetchone()[0]
    out.append({"check": "Kein Platzhalter als echter Modelllauf markiert", "fehler": fake, "ok": fake == 0})
    nob = conn.execute("SELECT COUNT(*) FROM runs WHERE is_real_model_run=1 AND budget_id IS NULL").fetchone()[0]
    out.append({"check": "Jeder echte Modelllauf gehört zu einem Budget", "fehler": nob, "ok": nob == 0})
    over = conn.execute("""SELECT COUNT(*) FROM model_budgets b WHERE (SELECT COUNT(*) FROM model_calls c WHERE c.budget_id=b.id
                           AND c.outcome!='refused_budget') > b.max_calls""").fetchone()[0]
    out.append({"check": "Kein Budget überschritten", "fehler": over, "ok": over == 0})
    unanch = conn.execute("""SELECT COUNT(*) FROM relation_hypotheses WHERE evidence_status='anchored' AND anchor_status!='complete'""").fetchone()[0]
    out.append({"check": "'anchored' nur mit vollständig geprüften Ankern", "fehler": unanch, "ok": unanch == 0})
    mixed = conn.execute("""SELECT COUNT(*) FROM candidate_comparisons c JOIN argument_units l ON l.id=c.left_unit_id JOIN argument_units r ON r.id=c.right_unit_id
                            JOIN documents dl ON dl.id=l.document_id JOIN documents dr ON dr.id=r.document_id WHERE dl.is_synthetic != dr.is_synthetic""").fetchone()[0]
    out.append({"check": "Keine Vergleiche zwischen synthetischen und echten Texten", "fehler": mixed, "ok": mixed == 0})
    return out


def render_markdown(rep: dict, preface: str = "") -> str:
    L = [f"# Abnahmebericht {rep['run_id']}", "", f"- Codeversion: `{rep['code_version']}`",
         f"- Embedding: `{rep['embedding']['set_id']}` (Testvektoren: {rep['embedding']['is_test_vectors']})",
         f"- Modelladapter: `{rep['adapter']}`"]
    if rep.get("budget"):
        b = rep["budget"]
        L.append(f"- Budget: `{b['id']}` „{b['label']}“: {b['used']}/{b['max_calls']} Aufrufversuche verbraucht, nach Ergebnis {b['by_outcome']}")
    if rep.get("stopped"):
        L.append(f"- **Gestoppt:** {rep['stopped']}")
    L += ["", preface, "",
          "Ergebnisarten: bestanden, gescheitert, unentscheidbar (z. B. begründete Enthaltung), nicht ausgeführt, nicht unterstützt.",
          "Spalte „Lauf“: echt = echter Modelldienst, replay = Funktionstest mit vorbereiteten Antworten.", "",
          "| Fall | Sprache | Teil | Ergebnis | Lauf | Kurzbefund |", "|---|---|---|---|---|---|"]
    for r in rep["cases"]:
        d = r["detail"] or {}
        brief = "; ".join(d.get("notes") or []) or d.get("reason") or ""
        if r["part"] == "Retrieval" and "partner_found_via" in d:
            brief = f"Suchwege {d['partner_found_via'] or '–'}, semantischer Rang {d.get('semantic_rank_full')}/{d.get('units_searched')}"
        if r["part"].startswith("Modell") and d.get("relation_types") is not None:
            brief = f"{d.get('evidence_status')}: {d.get('relation_types')} " + brief
        if r["part"] == "Modell C":
            brief = f"Entscheidung {d.get('decision')}, {d.get('evidence_status')} (Anker {d.get('anchor_status')}), Bezug {d.get('parent_evidence_status')}"
        L.append(f"| {r['case']} | {r['lang']} | {r['part']} | {r['result']} | {d.get('run_kind', '–')} | {brief[:180]} |")
    L += ["", "## Formale Mindestabnahme", "", "| Prüfung | Fehler | Ergebnis |", "|---|---|---|"]
    for f in rep["formal"]:
        L.append(f"| {f['check']} | {f['fehler']} | {'ok' if f['ok'] else 'FEHLER'} |")
    L += ["", "## Details", ""]
    for r in rep["cases"]:
        L += [f"### {r['case']} ({r['lang']}) {r['part']}: {r['title']}", "", f"Erwartung: {r['expectation']}", "", "```json",
              json.dumps(r["detail"], ensure_ascii=False, indent=1), "```", ""]
    return "\n".join(L)
