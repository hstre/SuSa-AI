"""Kommandozeile: python -m susa <befehl>. Alle Befehle arbeiten lokal; Netz nur bei import-json --download,
download-model und fetch."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import db
from .config import Config


def _conn(cfg):
    return db.connect(cfg.db_path)


def _pilot_ids(cfg) -> list[str]:
    p = cfg.root / "pilot" / "pilot_list.json"
    if not p.exists():
        sys.exit("Keine Pilotliste. Erst `susa pilot-select` ausführen.")
    return [x["document_id"] for x in json.loads(p.read_text("utf-8"))["items"]]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="susa", description="SuSa-AI Argumentanalyse (lokaler Prototyp)")
    ap.add_argument("--home", help="Projektverzeichnis (Default: aktuelles Verzeichnis oder SUSA_HOME)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="Datenbank anlegen")
    p = sub.add_parser("import-json", help="posts.json des Ausgangsprojekts importieren")
    p.add_argument("--path")
    p.add_argument("--download", action="store_true", help="versionsfesten Stand laut config herunterladen")
    p = sub.add_parser("import-csv", help="CSV-Download der Beitragsseite importieren")
    p.add_argument("path")
    p.add_argument("--filters", required=True, help="beim Download aktive Filter und Zeilenzahl, z. B. 'keine Filter, 4060 Zeilen'")
    p = sub.add_parser("pilot-select", help="Pilotliste erzeugen (pilot/pilot_list.json)")
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--seed", type=int, default=20261103)
    p.add_argument("--targeted", nargs="*", default=[])
    p = sub.add_parser("fetch", help="Volltexte abrufen (nur öffentlich verfügbare)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--pilot", action="store_true")
    g.add_argument("--doc", nargs="+")
    p.add_argument("--refetch", action="store_true")
    p = sub.add_parser("add-url", help="Einzelnen Substack-Beitrag als zusätzlichen Prüftext eintragen und abrufen (getrennt vom Ausgangsdatensatz)")
    p.add_argument("url")
    p.add_argument("--note", required=True, help="Anlass/Herkunft der Aufnahme")
    p = sub.add_parser("import-text", help="TXT/Markdown/HTML-Datei als Textversion importieren")
    p.add_argument("path")
    p.add_argument("--doc-id")
    p.add_argument("--url")
    p.add_argument("--title")
    p.add_argument("--author")
    p.add_argument("--date")
    p.add_argument("--source", required=True, help="Quellenangabe, z. B. 'manuell kopiert am 2026-11-03 aus <URL>'")
    sub.add_parser("fixtures", help="synthetische Abnahmefälle laden")
    p = sub.add_parser("segment", help="aktuelle Textversionen segmentieren")
    p.add_argument("--doc", nargs="*")
    sub.add_parser("download-model", help="Embedding-Modell (bge-small, ONNX) in models/ laden")
    p = sub.add_parser("embed", help="Abschnittsvektoren berechnen")
    p.add_argument("--backend", choices=["onnx-bge-small", "test-hash"])
    p = sub.add_parser("candidates", help="Kandidaten für Einheiten suchen")
    p.add_argument("--unit", nargs="*")
    p.add_argument("--pilot", action="store_true", help="alle Einheiten der Pilotdokumente")
    p = sub.add_parser("search", help="Freitextsuche (semantisch + lexikalisch)")
    p.add_argument("query")
    p.add_argument("--k", type=int, default=10)
    p = sub.add_parser("budget", help="Aufrufbudget anlegen oder anzeigen")
    bsub = p.add_subparsers(dest="bcmd", required=True)
    b = bsub.add_parser("create")
    b.add_argument("--label", required=True)
    b.add_argument("--max-calls", type=int, required=True)
    b.add_argument("--adapter")
    b.add_argument("--notes", default="")
    b = bsub.add_parser("status")
    b.add_argument("budget_id")
    b = bsub.add_parser("close")
    b.add_argument("budget_id")
    p = sub.add_parser("compare", help="Paarvergleich mit Modelladapter (Prompt B)")
    p.add_argument("comparison_ids", nargs="+")
    p.add_argument("--adapter")
    p.add_argument("--budget")
    p.add_argument("--dry-run", action="store_true", help="nur Aufwandsschätzung, kein Aufruf")
    p = sub.add_parser("countercheck", help="Gegenprüfung (Prompt C)")
    p.add_argument("hypothesis_id")
    p.add_argument("--adapter")
    p.add_argument("--budget")
    p = sub.add_parser("reconstruct", help="Argumentrekonstruktion (Prompt A)")
    p.add_argument("unit_id")
    p.add_argument("--adapter")
    p.add_argument("--budget")
    p = sub.add_parser("acceptance", help="Abnahmefälle ausführen")
    p.add_argument("--adapter")
    p.add_argument("--budget")
    p.add_argument("--backend", choices=["onnx-bge-small", "test-hash"])
    p.add_argument("--plan", nargs="*", help="Modellprüfungen, z. B. B:case10:en A:case06:de (Default: alle)")
    p.add_argument("--countercheck", nargs="*", default=[], help="Gegenprüfungen, z. B. C:case02:de")
    p.add_argument("--out", default="docs/ACCEPTANCE_REPORT.md")
    p = sub.add_parser("report", help="Abdeckungsbericht für die Pilotdokumente")
    p.add_argument("--out", default="docs/pilot_coverage.json")
    p = sub.add_parser("export", help="JSONL-Export eigener Ergebnisse")
    p.add_argument("out")
    p.add_argument("--include-quotes", action="store_true")
    p.add_argument("--only", choices=["real", "synthetic"])
    p = sub.add_parser("review-set", help="reale Prüfauswahl (ohne Modellaufrufe)")
    rsub = p.add_subparsers(dest="rcmd", required=True)
    r = rsub.add_parser("create", help="neue Auswahlversion (bestehende werden nie überschrieben)")
    r.add_argument("--label", default="Reale Prüfauswahl")
    r.add_argument("--per-hypothesis", type=int, default=2)
    r.add_argument("--seed", type=int, default=20261103)
    r.add_argument("--set-id")
    r.add_argument("--supersedes")
    r.add_argument("--reason")
    r = rsub.add_parser("export", help="Auswahl als JSON (Anker, keine Texte)")
    r.add_argument("set_id")
    r.add_argument("out")
    r = rsub.add_parser("load-translations", help="Übersetzungen laden (nur bei passendem Text-Hash)")
    r.add_argument("path")
    r = rsub.add_parser("verify", help="Anker, Textversionen und Übersetzungen der Auswahl prüfen")
    r.add_argument("set_id")
    r = rsub.add_parser("export-html", help="lokal öffnungsfähige Blindprüfung (enthält fremde Texte: nicht veröffentlichen)")
    r.add_argument("set_id")
    r.add_argument("out")
    r = rsub.add_parser("import-judgments", help="Antworten aus der HTML-Fassung übernehmen")
    r.add_argument("path")
    r = rsub.add_parser("show")
    r.add_argument("set_id")
    r = rsub.add_parser("import", help="Prüfauswahl aus JSON (z. B. pilot/review_set_1.json) wiederherstellen")
    r.add_argument("path")
    r = rsub.add_parser("load-aids", help="Lesehilfen aus JSON laden ({unit_id: text})")
    r.add_argument("path")
    r.add_argument("--author", required=True)
    r.add_argument("--method", required=True)
    p = sub.add_parser("br-pair", help="Paar einer Prüfauswahl mit den Budget-Review-Komponenten zerlegen")
    p.add_argument("set_id")
    p.add_argument("position", type=int)
    p.add_argument("--adapter")
    p.add_argument("--budget")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--evaluate-only", action="store_true")
    p.add_argument("--no-relations", action="store_true", help="Relationsstufe zwischen den Passagen auslassen (spart einen Aufruf)")
    p = sub.add_parser("argument", help="Argumentstufe (Prompt D) auf ein bereits zerlegtes Paar anwenden")
    p.add_argument("set_id")
    p.add_argument("position", type=int)
    p.add_argument("--adapter")
    p.add_argument("--budget")
    p.add_argument("--render", metavar="RUN_ID", help="nur Bericht eines gespeicherten Laufs neu erzeugen, kein Aufruf")
    p.add_argument("--public-out", help="Pfad für die Fassung ohne Originalzitate (versionierbar)")
    p.add_argument("--public-short", help="Pfad für den Kurzbericht ohne Originalzitate (versionierbar)")
    p.add_argument("--revalidate", action="store_true", help="mit --render: aktuelle Prüfregeln getrennt anwenden")
    p = sub.add_parser("argument-batch", help="Extraktion und Argumentstufe für mehrere Paare, fortsetzbar")
    p.add_argument("set_id")
    p.add_argument("positions", help="z. B. 4-10 oder 4,6,7")
    p.add_argument("--adapter")
    p.add_argument("--budget", required=True)
    p.add_argument("--retry-failed", action="store_true")
    p = sub.add_parser("argument-units", help="Extraktion (falls nötig) und Argumentstufe für ein frei gewähltes Einheitenpaar")
    p.add_argument("name", help="Verzeichnisname unter data/semantic/")
    p.add_argument("left_unit")
    p.add_argument("right_unit")
    p.add_argument("--adapter")
    p.add_argument("--budget", required=True)
    p.add_argument("--public-dir", default=None)
    p = sub.add_parser("review-sheet", help="Beurteilungsheft (lokale HTML-Datei: blind lesen, urteilen, dann Werkzeugergebnis)")
    p.add_argument("set_id")
    p.add_argument("--out", default=None)
    p = sub.add_parser("serve", help="lokale Oberfläche starten")
    p.add_argument("--port", type=int, default=5005)
    p.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args(argv)
    cfg = Config.load(a.home)

    if a.cmd == "init":
        _conn(cfg)
        print(f"Datenbank: {cfg.db_path}")
    elif a.cmd == "import-json":
        from .importer import import_posts_json
        rep = import_posts_json(cfg, _conn(cfg), Path(a.path) if a.path else None, a.download)
        print(json.dumps({k: rep[k] for k in ("import_run_id", "records", "unique_ids", "result", "date_range", "sha256")}, ensure_ascii=False))
        for row in rep["summary_comparison"]:
            print(f"  {row['status']:<12} {row['check']}: {row.get('import')} / {row.get('summary_json')}")
        print(f"Bericht: data/reports/import_{rep['import_run_id']}.md")
    elif a.cmd == "import-csv":
        from .importer import import_csv
        print(json.dumps(import_csv(cfg, _conn(cfg), Path(a.path), a.filters), ensure_ascii=False, indent=1))
    elif a.cmd == "pilot-select":
        from .pilot import select_pilot
        out = select_pilot(cfg, _conn(cfg), a.n, a.seed, targeted=a.targeted)
        print(f"{out['n_selected']} Beiträge ausgewählt aus {out['population_size']} -> pilot/pilot_list.json")
    elif a.cmd == "fetch":
        from .fetch import fetch_many
        ids = _pilot_ids(cfg) if a.pilot else a.doc
        res = fetch_many(cfg, _conn(cfg), ids, a.refetch)
        c = {}
        for r in res:
            c[r["status"]] = c.get(r["status"], 0) + 1
        print(json.dumps(c, ensure_ascii=False))
    elif a.cmd == "add-url":
        from urllib.parse import urlparse
        from .fetch import fetch_many
        conn = _conn(cfg)
        u = urlparse(a.url)
        slug = u.path.rstrip("/").split("/p/")[-1] if "/p/" in u.path else None
        doc_id = f"added:{u.netloc}:{slug}"
        if conn.execute("SELECT 1 FROM documents WHERE id=?", (doc_id,)).fetchone() is None:
            ts = db.now()
            conn.execute("INSERT INTO documents(id, origin, is_synthetic, canonical_url, host, slug, upstream_payload, first_seen_at, updated_at) "
                         "VALUES(?,?,?,?,?,?,?,?,?)", (doc_id, "added_review_text", 0, a.url, u.netloc, slug,
                                                       db.dumps({"note": a.note, "added_at": ts}), ts, ts))
            conn.commit()
        for r in fetch_many(cfg, conn, [doc_id]):
            print(json.dumps(r, ensure_ascii=False))
    elif a.cmd == "import-text":
        from .fetch import import_text_file
        vid = import_text_file(cfg, _conn(cfg), Path(a.path), doc_id=a.doc_id, url=a.url, title=a.title, author=a.author,
                               date=a.date, source_note=a.source)
        print(f"Version {vid} angelegt")
    elif a.cmd == "fixtures":
        from .fixtures import load_fixtures
        print(load_fixtures(cfg, _conn(cfg)))
    elif a.cmd == "segment":
        from .segment import segment_all
        out = segment_all(cfg, _conn(cfg), a.doc or None)
        n_units = sum(o.get("units", 0) for o in out)
        low = [o for o in out if o.get("coverage") is not None and o["coverage"] < 0.999]
        print(f"{len(out)} Versionen, {n_units} Einheiten; Versionen mit Abdeckung < 99,9 %: {len(low)}")
    elif a.cmd == "download-model":
        from .embed import download_model
        print(json.dumps(download_model(cfg), indent=1))
    elif a.cmd == "embed":
        from .embed import embed_units
        print(json.dumps(embed_units(cfg, _conn(cfg), a.backend), ensure_ascii=False))
    elif a.cmd == "candidates":
        from .search import Searcher, find_candidates
        conn = _conn(cfg)
        units = a.unit or []
        if a.pilot:
            ids = _pilot_ids(cfg)
            units += [r["id"] for d in ids for r in conn.execute(
                "SELECT u.id FROM argument_units u JOIN document_versions v ON v.id=u.version_id WHERE v.is_current=1 AND u.document_id=?", (d,))]
        s = Searcher(cfg, conn)
        total = 0
        for u in units:
            total += len(find_candidates(cfg, conn, u, searcher=s)["candidates"])
        print(f"{len(units)} Einheiten, {total} Kandidatenpaare gespeichert")
    elif a.cmd == "search":
        from .search import Searcher
        conn = _conn(cfg)
        s = Searcher(cfg, conn)
        for ch, hits in (("semantisch", s.semantic_for_query(a.query, a.k, exclude_doc=None, synthetic=None, prefix=None)),
                         ("lexikalisch", s.lexical(a.query, a.k, exclude_doc=None, synthetic=None, prefix=None))):
            print(f"== {ch}")
            for uid, score in hits:
                u = conn.execute("SELECT u.text, d.title FROM argument_units u JOIN documents d ON d.id=u.document_id WHERE u.id=?", (uid,)).fetchone()
                print(f"{score:8.3f}  {uid}  {u['title'][:50]!r}  {u['text'][:100]!r}")
    elif a.cmd == "budget":
        from .llm import budget_status, create_budget
        conn = _conn(cfg)
        if a.bcmd == "create":
            bid = create_budget(conn, a.label, a.max_calls, a.adapter, cfg.section("llm").get("model"), a.notes)
            print(bid)
        elif a.bcmd == "close":
            conn.execute("UPDATE model_budgets SET closed_at=? WHERE id=?", (db.now(), a.budget_id))
            conn.commit()
        print(json.dumps(budget_status(conn, a.budget_id if a.bcmd != "create" else bid), ensure_ascii=False))
    elif a.cmd in ("compare", "countercheck", "reconstruct"):
        from . import analysis
        from .llm import NotConfigured, get_adapter
        conn = _conn(cfg)
        if a.cmd == "compare" and a.dry_run:
            print(json.dumps(analysis.estimate(cfg, conn, a.comparison_ids), ensure_ascii=False, indent=1))
            return
        try:
            ad = get_adapter(cfg.section("llm"), a.adapter, conn=conn, budget_id=a.budget)
        except NotConfigured as e:
            sys.exit(str(e))
        if a.cmd == "compare":
            for cid in a.comparison_ids:
                print(json.dumps(analysis.compare(cfg, conn, cid, adapter=ad), ensure_ascii=False))
        elif a.cmd == "countercheck":
            print(json.dumps(analysis.countercheck(cfg, conn, a.hypothesis_id, ad), ensure_ascii=False))
        else:
            print(json.dumps(analysis.reconstruct(cfg, conn, a.unit_id, ad), ensure_ascii=False))
    elif a.cmd == "acceptance":
        from .acceptance import render_markdown, run_acceptance
        rep = run_acceptance(cfg, _conn(cfg), a.adapter, a.backend, budget_id=a.budget,
                             model_plan=set(a.plan) if a.plan is not None else None, countercheck_plan=set(a.countercheck))
        out = cfg.root / a.out
        out.parent.mkdir(exist_ok=True)
        out.write_text(render_markdown(rep), "utf-8")
        for r in rep["cases"]:
            print(f"{r['case']:<7} {r['lang']:<6} {r['part']:<16} {r['result']:<17} {(r['detail'] or {}).get('run_kind', '')}")
        for f in rep["formal"]:
            print(f"formal: {'ok ' if f['ok'] else 'FEHLER'} {f['check']} ({f['fehler']})")
        if rep.get("budget"):
            print("Budget:", json.dumps(rep["budget"], ensure_ascii=False))
        if rep.get("stopped"):
            print("GESTOPPT:", rep["stopped"])
        print(f"Bericht: {out}")
    elif a.cmd == "report":
        from .pilot import coverage_report
        rep = coverage_report(cfg, _conn(cfg), _pilot_ids(cfg))
        out = cfg.root / a.out
        out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), "utf-8")
        print(json.dumps({k: rep[k] for k in ("n", "status", "availability")}, ensure_ascii=False))
    elif a.cmd == "export":
        from .export import export_jsonl
        only = None if a.only is None else (a.only == "synthetic")
        print(export_jsonl(_conn(cfg), Path(a.out), a.include_quotes, only))
    elif a.cmd == "review-set":
        from . import review_set
        conn = _conn(cfg)
        if a.rcmd == "create":
            try:
                sid, items = review_set.create_set(conn, a.label, a.per_hypothesis, a.seed, set_id=a.set_id,
                                                   supersedes=a.supersedes, change_reason=a.reason)
            except review_set.SetFrozen as e:
                sys.exit(str(e))
            print(sid, len(items))
        elif a.rcmd == "export":
            Path(a.out).write_text(json.dumps(review_set.export_set_file(conn, a.set_id), ensure_ascii=False, indent=1), "utf-8")
        elif a.rcmd == "load-translations":
            print(json.dumps(review_set.load_translations(cfg, conn, json.loads(Path(a.path).read_text("utf-8"))), ensure_ascii=False, indent=1))
        elif a.rcmd == "verify":
            res = review_set.verify_set(cfg, conn, a.set_id)
            for r in res:
                print(f"{'ok    ' if r['ok'] else 'FEHLER'} {r['check']}: {r['detail']}")
            if not all(r["ok"] for r in res):
                sys.exit(1)
        elif a.rcmd == "export-html":
            from .blind_html import export_html
            print(export_html(cfg, conn, a.set_id, Path(a.out)))
        elif a.rcmd == "import-judgments":
            from .blind_html import import_judgments
            print(json.dumps(import_judgments(cfg, conn, json.loads(Path(a.path).read_text("utf-8"))), ensure_ascii=False, indent=1))
        elif a.rcmd == "import":
            print(review_set.import_set(conn, json.loads(Path(a.path).read_text("utf-8"))))
        elif a.rcmd == "load-aids":
            data = json.loads(Path(a.path).read_text("utf-8"))
            for uid, text in data["aids"].items():
                review_set.add_reading_aid(conn, uid, text, a.author, a.method, (data.get("anchors") or {}).get(uid))
            print(f"{len(data['aids'])} Lesehilfen geladen")
        else:
            for r in conn.execute("""SELECT i.*, cc.left_unit_id, cc.right_unit_id FROM review_set_items i JOIN candidate_comparisons cc
                                     ON cc.id=i.comparison_id WHERE set_id=? ORDER BY position""", (a.set_id,)):
                print(r["position"], r["search_hypothesis"], r["comparison_id"], r["selection_reason"])
    elif a.cmd == "br-pair":
        from . import br_bridge, review_set
        from .llm import CallLimitReached, NotConfigured, get_adapter
        conn = _conn(cfg)
        out_dir = cfg.subdir(f"semantic/{a.set_id}-p{a.position}")
        if not a.evaluate_only:
            it = next(i for i in review_set.set_items(conn, a.set_id) if i["position"] == a.position)
            try:
                ad = get_adapter(cfg.section("llm"), a.adapter, conn=conn, budget_id=a.budget)
                br_bridge.run_pair(cfg, conn, ad, it["left_unit_id"], it["right_unit_id"], a.repeats, out_dir,
                                  relations=not a.no_relations)
            except (NotConfigured, CallLimitReached) as e:
                print("GESTOPPT:", e)
        rep = br_bridge.evaluate(out_dir)
        (out_dir / "evaluation.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), "utf-8")
        print(json.dumps({k: rep[k] for k in ("runs", "relations")}, ensure_ascii=False, default=str)[:2000])
    elif a.cmd == "argument":
        from . import argument_stage
        from .llm import NotConfigured, get_adapter
        conn = _conn(cfg)
        pair_dir = cfg.subdir(f"semantic/{a.set_id}-p{a.position}")
        if a.render:
            run_dir = pair_dir / f"argument-{a.render}"
        else:
            try:
                ad = get_adapter(cfg.section("llm"), a.adapter, conn=conn, budget_id=a.budget)
            except NotConfigured as e:
                print("GESTOPPT:", e)
                return
            meta = argument_stage.run(cfg, conn, ad, pair_dir)
            print(json.dumps({k: meta.get(k) for k in ("run_id", "status", "error", "model", "usage")}, ensure_ascii=False))
            if meta.get("status") in ("not_run", "error"):
                return
            run_dir = pair_dir / f"argument-{meta['run_id']}"
        paths = argument_stage.write_reports(run_dir, Path(a.public_out) if a.public_out else None,
                                             Path(a.public_short) if a.public_short else None, revalidate=a.revalidate)
        print("Berichte:", ", ".join(str(p) for p in paths))
    elif a.cmd == "argument-batch":
        from . import batch
        from .llm import NotConfigured, get_adapter
        conn = _conn(cfg)
        pos = [int(x) for part in a.positions.split(",") for x in
               (range(int(part.split("-")[0]), int(part.split("-")[1]) + 1) if "-" in part else [part])]
        cfg_llm = {**cfg.section("llm"), "max_retries": 0}  # keine automatischen Wiederholungen im Stapellauf
        try:
            ad = get_adapter(cfg_llm, a.adapter, conn=conn, budget_id=a.budget)
        except NotConfigured as e:
            print("GESTOPPT:", e)
            return
        st = batch.run(cfg, conn, ad, a.set_id, pos, Path("docs"), retry_failed=a.retry_failed)
        print(json.dumps(st, ensure_ascii=False, indent=1))
    elif a.cmd == "argument-units":
        from . import argument_stage, br_bridge
        from .batch import extraction_ok, stage_runs
        from .llm import CallLimitReached, NotConfigured, get_adapter
        conn = _conn(cfg)
        pair_dir = cfg.subdir(f"semantic/{a.name}")
        try:
            ad = get_adapter({**cfg.section("llm"), "max_retries": 0}, a.adapter, conn=conn, budget_id=a.budget)
            cur = {"A": br_bridge.passage(cfg, conn, a.left_unit), "B": br_bridge.passage(cfg, conn, a.right_unit)}
            if not extraction_ok(pair_dir, cur):
                br_bridge.run_pair(cfg, conn, ad, a.left_unit, a.right_unit, 1, pair_dir, relations=False)
                rep = br_bridge.evaluate(pair_dir)
                (pair_dir / "evaluation.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), "utf-8")
            if not extraction_ok(pair_dir, cur):
                print("GESTOPPT: Extraktion ungültig"); return
            if not any(m.get("status") == "valid" for m in stage_runs(pair_dir)):
                meta = argument_stage.run(cfg, conn, ad, pair_dir, label=a.name)
                print(json.dumps({k: meta.get(k) for k in ("run_id", "status", "error")}, ensure_ascii=False))
        except (NotConfigured, CallLimitReached) as e:
            print("GESTOPPT:", e); return
        valid = [m for m in stage_runs(pair_dir) if m.get("status") == "valid"]
        if valid:
            pub = Path(a.public_dir) if a.public_dir else None
            print(argument_stage.write_reports(Path(valid[-1]["dir"]), pub / "ARGUMENT_STAGE_RAW.md" if pub else None,
                                               pub / "KURZBERICHT.md" if pub else None))
    elif a.cmd == "review-sheet":
        from . import judgment_sheet
        out = Path(a.out) if a.out else cfg.subdir("export") / f"beurteilungsheft_{a.set_id}.html"
        print(judgment_sheet.build(cfg, _conn(cfg), a.set_id, Path("docs"), out))
    elif a.cmd == "serve":
        from .web.app import create_app
        create_app(cfg).run(host=a.host, port=a.port, debug=False)


if __name__ == "__main__":
    main()
