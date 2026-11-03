"""Lokale Prüf-Oberfläche. Zeigt denselben gespeicherten Quellenstand wie die Berichte (liest dieselbe SQLite-DB
und dieselben Textdateien). Startet nur auf 127.0.0.1, ohne Authentifizierung: nicht öffentlich betreiben."""
from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

from flask import Flask, Response, abort, g, redirect, render_template, request, url_for
from markupsafe import Markup, escape

from .. import analysis, db
from ..config import Config
from ..export import export_jsonl
from ..llm import get_adapter
from ..search import Searcher, find_candidates, markers_for, shared_sources, source_index
from ..versions import current_version, read_text

AXES = ["experience_now", "cognition_now", "agency_now", "possible", "moral_status", "serious"]
STATUS_LABELS = {"ok_full": "vollständig (Wortzahl plausibel)", "ok_unverified_length": "Text vorhanden, Länge nicht prüfbar",
                 "partial_suspected": "vermutlich unvollständig", "paywalled_preview": "nur Vorschau (Bezahlschranke)",
                 "login_or_error_page": "Anmelde-/Fehlerseite", "empty": "kein Textkörper", "not_found": "nicht gefunden",
                 "http_error": "HTTP-Fehler", "network_error": "Netzwerkfehler", "manual_import": "manuell importiert",
                 "synthetic_fixture": "synthetischer Testtext"}
DECISION_LABELS = {"confirmed": "bestätigt", "corrected": "korrigiert", "rejected": "verworfen", "undecidable": "nicht entscheidbar"}


def highlight(text: str, start: int, end: int, marks: list[tuple[int, int, str, str]]) -> Markup:
    """Text[start:end] mit Markierungen (s, e, css, title) als HTML. Überlappungen werden an Grenzen aufgeteilt."""
    cuts = {start, end}
    for s, e, _, _ in marks:
        if e > start and s < end:
            cuts.add(max(s, start))
            cuts.add(min(e, end))
    pts = sorted(cuts)
    out = []
    for a, b in zip(pts, pts[1:]):
        seg = escape(text[a:b])
        act = [(c, t) for s, e, c, t in marks if s <= a and b <= e]
        if act:
            cls = " ".join(sorted({c for c, _ in act}))
            title = " | ".join(t for _, t in act if t)
            seg = Markup(f'<mark class="{cls}" title="{escape(title)}">') + seg + Markup("</mark>")
        out.append(seg)
    return Markup("").join(out).replace("\n\n", Markup("<br><br>"))


def create_app(cfg: Config | None = None) -> Flask:
    cfg = cfg or Config.load()
    app = Flask(__name__)
    app.config["SUSA_CFG"] = cfg

    def conn():
        if "conn" not in g:
            g.conn = db.connect(cfg.db_path)
        return g.conn

    @app.teardown_appcontext
    def _close(exc):
        c = g.pop("conn", None)
        if c is not None:
            c.close()

    @app.template_filter("fromjson")
    def fromjson(s):
        return json.loads(s) if s else None

    @app.template_filter("status_label")
    def status_label(s):
        return STATUS_LABELS.get(s, s)

    @app.context_processor
    def ctx():
        return {"DECISION_LABELS": DECISION_LABELS, "RELATION_TYPES": analysis.RELATION_TYPES}

    @app.route("/")
    def overview():
        c = conn()
        f = {k: request.args.get(k, "") for k in ("q", "kind", "text", "relevance", "grp", "axis", "value")}
        where, params = ["1=1"], []
        if f["q"]:
            where.append("(d.title LIKE ? OR d.author LIKE ? OR d.publication LIKE ?)")
            params += [f"%{f['q']}%"] * 3
        if f["kind"] == "real":
            where.append("d.is_synthetic=0")
        elif f["kind"] == "synthetic":
            where.append("d.is_synthetic=1")
        if f["text"] == "with":
            where.append("v.text_path IS NOT NULL")
        elif f["text"] == "without":
            where.append("v.id IS NOT NULL AND v.text_path IS NULL")
        elif f["text"] == "notfetched":
            where.append("v.id IS NULL")
        if f["relevance"]:
            where.append("uc.relevance=?")
            params.append(f["relevance"])
        if f["grp"]:
            where.append("uc.grp=?")
            params.append(f["grp"])
        if f["axis"] in AXES and f["value"]:
            where.append(f"uc.{f['axis']}=?")
            params.append(f["value"])
        page = max(1, int(request.args.get("page", 1)))
        base = f"""FROM documents d LEFT JOIN upstream_codes uc ON uc.document_id=d.id
                   LEFT JOIN document_versions v ON v.document_id=d.id AND v.id=(SELECT MAX(id) FROM document_versions WHERE document_id=d.id)
                   WHERE {' AND '.join(where)}"""
        total = c.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
        rows = c.execute(f"""SELECT d.*, uc.relevance, uc.grp, uc.experience_now, uc.axes_source, v.status AS vstatus, v.availability
                             {base} ORDER BY d.is_synthetic, d.date DESC LIMIT 50 OFFSET ?""", params + [(page - 1) * 50]).fetchall()
        stats = {
            "docs_real": c.execute("SELECT COUNT(*) FROM documents WHERE is_synthetic=0").fetchone()[0],
            "docs_synth": c.execute("SELECT COUNT(*) FROM documents WHERE is_synthetic=1").fetchone()[0],
            "versions": c.execute("""SELECT d.is_synthetic, v.status, COUNT(*) n FROM document_versions v JOIN documents d ON d.id=v.document_id
                                    WHERE v.is_current=1 GROUP BY 1,2 ORDER BY 1,3 DESC""").fetchall(),
            "units": c.execute("SELECT d.is_synthetic, COUNT(*) n FROM argument_units u JOIN documents d ON d.id=u.document_id GROUP BY 1").fetchall(),
            "comparisons": c.execute("SELECT COUNT(*) FROM candidate_comparisons").fetchone()[0],
            "hypotheses": c.execute("SELECT kind, COUNT(*) n FROM relation_hypotheses GROUP BY 1").fetchall(),
            "reviews": c.execute("SELECT COUNT(*) FROM reviews").fetchone()[0],
        }
        imports = c.execute("SELECT * FROM import_runs ORDER BY id DESC LIMIT 5").fetchall()
        esets = c.execute("SELECT * FROM embedding_sets ORDER BY created_at DESC").fetchall()
        groups = [r[0] for r in c.execute("SELECT DISTINCT grp FROM upstream_codes WHERE grp IS NOT NULL ORDER BY 1")]
        return render_template("overview.html", rows=rows, total=total, page=page, f=f, stats=stats, imports=imports,
                               esets=esets, groups=groups, axes=AXES, llm=cfg.section("llm"))

    @app.route("/doc/<path:doc_id>")
    def document(doc_id):
        c = conn()
        d = c.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        if d is None:
            abort(404)
        codes = c.execute("SELECT * FROM upstream_codes WHERE document_id=?", (doc_id,)).fetchone()
        versions = c.execute("SELECT * FROM document_versions WHERE document_id=? ORDER BY id DESC", (doc_id,)).fetchall()
        vid = request.args.get("version", type=int)
        v = c.execute("SELECT * FROM document_versions WHERE id=?", (vid,)).fetchone() if vid else current_version(c, doc_id)
        body, units, links = None, [], []
        if v is not None and v["text_path"]:
            text = read_text(cfg, v)
            units = c.execute("SELECT * FROM argument_units WHERE version_id=? ORDER BY seq", (v["id"],)).fetchall()
            paras = c.execute("SELECT * FROM paragraphs WHERE version_id=? ORDER BY idx", (v["id"],)).fetchall()
            spans = c.execute("SELECT * FROM spans WHERE version_id=?", (v["id"],)).fetchall()
            links = c.execute("SELECT * FROM links WHERE version_id=? ORDER BY start_char", (v["id"],)).fetchall()
            marks = [(s["start_char"], s["end_char"], "quote" if s["origin"] == "quote_heuristic" else "evidence",
                      f"{s['origin']}: {s['speaker'] or ''}") for s in spans]
            marks += [(ln["start_char"], ln["end_char"], "link", ln["href"]) for ln in links]
            blocks = []
            for u in units:
                ps = [p for p in paras if p["start_char"] < u["end_char"] and p["end_char"] > u["start_char"]]
                blocks.append({"unit": u, "paras": [{"kind": p["kind"], "speaker": p["speaker_hint"],
                                                      "html": highlight(text, max(p["start_char"], u["start_char"]), min(p["end_char"], u["end_char"]), marks)} for p in ps]})
            heads = {p["start_char"]: p for p in paras if p["kind"] == "h"}
            body = {"blocks": blocks, "headings": heads, "text_len": len(text)}
        payload = json.loads(d["upstream_payload"] or "{}")
        return render_template("document.html", d=d, codes=codes, versions=versions, v=v, body=body, links=links,
                               payload=payload, axes=AXES)

    @app.route("/unit/<path:uid>", methods=["GET", "POST"])
    def unit(uid):
        c = conn()
        if request.method == "POST":
            find_candidates(cfg, c, uid, prefix=request.form.get("prefix") or None)
            return redirect(url_for("unit", uid=uid))
        ctx_ = analysis.unit_context(cfg, c, uid)
        cands = c.execute(
            """SELECT cc.*, ru.text AS rtext, ru.document_id AS rdoc, d.title, d.author, d.date, v.status AS rstatus,
                      (SELECT COUNT(*) FROM relation_hypotheses h WHERE h.comparison_id=cc.id) AS n_hyp
               FROM candidate_comparisons cc JOIN argument_units ru ON ru.id=cc.right_unit_id JOIN documents d ON d.id=ru.document_id
               JOIN document_versions v ON v.id=ru.version_id WHERE cc.left_unit_id=? ORDER BY cc.created_at""", (uid,)).fetchall()
        return render_template("unit.html", c=ctx_, cands=cands, uid=uid)

    @app.route("/search")
    def search():
        q = request.args.get("q", "").strip()
        only = request.args.get("only", "real")
        res = {}
        s = None
        if q:
            c = conn()
            s = Searcher(cfg, c)
            synth = {"real": 0, "synthetic": 1}.get(only)
            k = 15
            for ch, hits in (("semantic", s.semantic_for_query(q, k, exclude_doc=None, synthetic=synth, prefix=None)),
                             ("lexical", s.lexical(q, k, exclude_doc=None, synthetic=synth, prefix=None))):
                rows = []
                for uid, score in hits:
                    u = c.execute("""SELECT u.*, d.title, d.author, d.date, d.is_synthetic FROM argument_units u JOIN documents d ON d.id=u.document_id
                                     WHERE u.id=?""", (uid,)).fetchone()
                    rows.append({"u": u, "score": score})
                res[ch] = rows
        return render_template("search.html", q=q, res=res, only=only, eset=s.eset if s else None)

    @app.route("/compare/<path:cid>", methods=["GET", "POST"])
    def compare(cid):
        c = conn()
        cmp_ = c.execute("SELECT * FROM candidate_comparisons WHERE id=?", (cid,)).fetchone()
        if cmp_ is None:
            abort(404)
        msg = None
        if request.method == "POST":
            act = request.form.get("action")
            reviewer = request.form.get("reviewer", "").strip() or "unbenannt"
            if act == "model_compare":
                r = analysis.compare(cfg, c, cid, adapter=get_adapter(cfg.section("llm")))
                msg = f"Modellvergleich: {r.get('status')} {r.get('reason') or ''}"
            elif act == "countercheck":
                r = analysis.countercheck(cfg, c, request.form["hypothesis_id"], adapter=get_adapter(cfg.section("llm")))
                msg = f"Gegenprüfung: {r.get('status')} {r.get('reason') or ''}"
            elif act == "manual":
                lines = lambda k: [x.strip() for x in request.form.get(k, "").splitlines() if x.strip()]
                payload = {k: request.form.get(k, "").strip() or None for k in ("shared_question", "left_claim", "right_claim", "added_thought", "reasoning_summary")}
                payload.update({"left_quotes": lines("left_quotes"), "right_quotes": lines("right_quotes"), "uncertainties": lines("uncertainties"),
                                "comparability": {"notes": request.form.get("comparability_notes", "")}})
                hid = analysis.add_manual_hypothesis(cfg, c, cid, reviewer, request.form.getlist("relation_types"), payload)
                msg = f"Manuelle Interpretation {hid} gespeichert."
            elif act == "review":
                corrected = None
                if request.form.get("decision") == "corrected":
                    corrected = {"relation_types": request.form.getlist("corr_relation_types"),
                                 "added_thought": request.form.get("corr_added_thought") or None}
                analysis.add_review(c, "relation_hypothesis", request.form["hypothesis_id"], reviewer, request.form["decision"],
                                    request.form.get("comment", ""), corrected)
                msg = "Prüfentscheidung gespeichert (append-only)."
            return redirect(url_for("compare", cid=cid, msg=msg))
        sides = {}
        hyps = c.execute("""SELECT h.*, r.adapter, r.model, r.prompt_version, r.is_real_model_run, r.started_at AS run_at FROM relation_hypotheses h
                            LEFT JOIN runs r ON r.id=h.run_id WHERE h.comparison_id=? ORDER BY h.created_at""", (cid,)).fetchall()
        for side, key in (("left", "left_unit_id"), ("right", "right_unit_id")):
            x = analysis.unit_context(cfg, c, cmp_[key])
            u = x["unit"]
            spans = c.execute("SELECT * FROM spans WHERE version_id=?", (u["version_id"],)).fetchall()
            marks = [(s["start_char"], s["end_char"], "quote" if s["origin"] == "quote_heuristic" else "evidence", s["origin"]) for s in spans]
            sides[side] = {"x": x, "u": u,
                           "before": highlight(x["text"], u["ctx_start"], u["start_char"], marks),
                           "core": highlight(x["text"], u["start_char"], u["end_char"], marks),
                           "after": highlight(x["text"], u["end_char"], u["ctx_end"], marks),
                           "markers": markers_for(x["core"])}
        reviews = {h["id"]: c.execute("SELECT * FROM reviews WHERE target_type='relation_hypothesis' AND target_id=? ORDER BY id", (h["id"],)).fetchall()
                   for h in hyps}
        shared = shared_sources(c, sides["left"]["u"]["document_id"], sides["right"]["u"]["document_id"])
        return render_template("compare.html", cmp=cmp_, sides=sides, hyps=hyps, reviews=reviews, shared=shared,
                               msg=request.args.get("msg"), llm=cfg.section("llm"))

    @app.route("/sources")
    def sources():
        only = request.args.get("only", "real")
        return render_template("sources.html", rows=source_index(conn(), 2, {"real": 0, "synthetic": 1}.get(only))[:300], only=only)

    @app.route("/history")
    def history():
        c = conn()
        return render_template("history.html",
                               reviews=c.execute("SELECT * FROM reviews ORDER BY id DESC LIMIT 300").fetchall(),
                               revisions=c.execute("SELECT * FROM revisions ORDER BY id DESC LIMIT 300").fetchall(),
                               runs=c.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 300").fetchall())

    @app.route("/export.jsonl")
    def export():
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
            path = Path(tf.name)
        export_jsonl(conn(), path, include_quotes=False)
        data = path.read_bytes()
        path.unlink()
        return Response(data, mimetype="application/x-ndjson",
                        headers={"Content-Disposition": "attachment; filename=susa-export.jsonl"})

    return app
