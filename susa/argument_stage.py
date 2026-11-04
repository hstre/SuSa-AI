"""Wiederverwendbare Analysestufe: Argumentrekonstruktion und Vergleich eines Paars (Prompt D).

Eingaben (dokumentiert und gehasht, keine paarspezifische Logik, keine vorab ausgefüllte Interpretation):
  - passages.json und run-*.json aus br_bridge (Budget-Review-Extraktion und -Gate)
  - die deterministische Struktur aus pair_analysis.build_structure (Anker-Gruppen, Häufigkeiten, Kanten,
    Sprechakt-Hinweise)

Ebenen im Ergebnis:
  übernommen      Modellausgaben früherer Läufe (Claims, Kanten), nur gelesen
  deterministisch Struktur, Hinweise, Validierung
  neu             die Interpretation dieses Modellaufrufs (Prompt D_argument)

Die Validierung prüft, was sich ohne Modell prüfen lässt: Schema und Wertelisten, existierende Anker und Kanten,
dass jedes Belegzitat wörtlich in einem der genannten Anker steht (der Anker trägt die Stelle, nicht bloß „es gibt
ihn“), dass Ketten nur Anker ihrer Passage nutzen, und Hinweise auf Bedeutungsverstärkung: Negation, Modalität,
Bedingung oder Geltungseinschränkung im Anker, aber nicht in der Wiedergabe. Diese Hinweise sind Marker, kein
Beweis; sie können falsch anschlagen und eine Verstärkung übersehen.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from budget_review.anchoring import anchor_spans

from . import db
from .analysis import _finish_run, _start_run
from .llm import CallLimitReached, NotConfigured, extract_json, load_prompt
from .pair_analysis import build_structure
from .search import markers_for

ACTS = ["vertritt", "berichtet", "mögliche Überzeugung anderer", "Frage", "Überschrift", "offen"]
ROLES = ["Grund", "Voraussetzung", "Einschränkung", "Folgerung", "Autorität", "Gegenposition", "Beispiel"]
SUPPORT = ["gestützt", "teilweise gestützt", "nicht ausreichend gestützt"]
QREL = ["gemeinsam", "teilweise gemeinsam", "nur A", "nur B"]
MATCH = ["gleich", "teilweise", "verschieden", "unvereinbar"]
KINDS = ["Wiederholung", "zusätzliche Begründung", "Präzisierung", "Einschränkung", "Widerspruch", "andere Fragestellung"]
# Ergänzt search.MARKERS für Geltungswörter, die dort fehlen (nur hier verwendet).
EXTRA_SCOPE = re.compile(r"\b(necessarily|simply|entirely|fully|currently|notwendigerweise|zwingend|einfach|vollständig|derzeit|gegenwärtig)\b", re.I)
MAX_OUTPUT_TOKENS = 32000  # 16000 reichte für Paar 2 nicht (Lauf 20261104T164733: 20125 Token, Antwort geteilt)


def paragraph_kinds(conn, passages: dict) -> dict:
    out = {}
    for side, p in passages.items():
        v = conn.execute("SELECT id FROM document_versions WHERE document_id=? AND text_sha256=?",
                         (p["document_id"], p["version_text_sha256"])).fetchone()
        out[side] = [] if v is None else [(r[0] - p["offset"], r[1] - p["offset"], r[2]) for r in
                                          conn.execute("SELECT start_char, end_char, kind FROM paragraphs WHERE version_id=?", (v[0],))]
    return out


def build_inputs(conn, pair_dir: Path) -> dict:
    passages = json.loads((pair_dir / "passages.json").read_text("utf-8"))
    structure = build_structure(pair_dir, paragraph_kinds(conn, passages))
    runs = sorted(p.name for p in pair_dir.glob("run-*.json"))
    return {"passages": passages, "structure": structure, "runs": runs,
            "inputs_sha256": db.sha256_text(json.dumps({"p": passages, "s": structure}, sort_keys=True, ensure_ascii=False))}


def render_user(inputs: dict) -> str:
    P, S = inputs["passages"], inputs["structure"]
    n = S["runs"]
    out = [f"Vorliegende Extraktionsläufe: {n}. Häufigkeit zeigt Stabilität, nicht Richtigkeit.\n"]
    for side in ("A", "B"):
        p, s = P[side], S["sides"][side]
        doc, (cs, ce) = p["document"], p["core"]
        out.append(f'<passage id="{side}">')
        for label, a, b in (("Kontext davor", 0, cs), ("Kernabschnitt", cs, ce), ("Kontext danach", ce, len(doc))):
            if doc[a:b].strip():
                out.append(f"[{label}]\n{doc[a:b].strip()}")
        out.append("</passage>")
        out.append(f"Anker {side} (ID | Bereich | in Läufen | Hinweise | Originalstelle | Aussagen der Läufe):")
        for a in s["anchors"]:
            contents = sorted({v["content"] for v in a["model_outputs"].values()})
            out.append(f"- {a['id']} | {a['region']} | {len(a['in_runs'])}/{n} | {'; '.join(a['speech_cues']) or '–'} | "
                       f"„{a['span']}“ | " + " || ".join(contents))
        out.append(f"Kanten innerhalb {side} (Quelle Typ Ziel, Läufe): " +
                   (", ".join(f"{e['source']} {e['type']} {e['target']} ({e['runs']}/{n})" for e in s["edges"]) or "keine"))
        out.append("")
    out.append("Kanten zwischen A und B: " + (", ".join(f"{e['source']} {e['type']} {e['target']} ({e['runs']}/{n})"
                                                     for e in S["cross_edges"]) or "keine (nicht erzeugt)"))
    return "\n".join(out)


# ------------------------------------------------------------------ Validierung

def _anchor_index(structure):
    return {a["id"]: (side, a) for side, s in structure["sides"].items() for a in s["anchors"]}


def _edges(structure):
    e = {(x["source"], x["type"], x["target"]) for s in structure["sides"].values() for x in s["edges"]}
    return e | {(x["source"], x["type"], x["target"]) for x in structure["cross_edges"]}


def amplification_flags(rendering: str, spans: list[str]) -> list[str]:
    """Marker im Original, die in der Wiedergabe fehlen. Hinweis auf mögliche Verstärkung, kein Beweis."""
    src = markers_for(" ".join(spans))
    ren = markers_for(rendering or "")
    flags = [f"{k} im Original ({', '.join(src[k][:3])}), nicht in der Wiedergabe"
             for k in ("negation", "modal", "condition", "scope_limit") if src[k] and not ren[k]]
    if EXTRA_SCOPE.search(" ".join(spans)) and not EXTRA_SCOPE.search(rendering or "") and not ren["scope_limit"]:
        flags.append(f"Geltungswort im Original ({EXTRA_SCOPE.search(' '.join(spans)).group(0)}), nicht in der Wiedergabe")
    return flags


def validate(result: dict, structure: dict) -> dict:
    idx, edges = _anchor_index(structure), _edges(structure)
    errors, quote_fail, side_err, amplif, context_flags = [], [], [], [], []
    req = {"speech_acts": list, "chains": list, "questions": list, "conclusion_comparison": list, "additions": list,
           "weak_relations": list, "open_readings": list, "uncertainties": list}
    for k, t in req.items():
        if not isinstance(result.get(k), t):
            errors.append(f"$.{k}: fehlt oder kein {t.__name__}")
    if errors:
        return {"schema_valid": False, "errors": errors}

    def anchors_ok(path, ids, side=None, nonempty=True):
        if not isinstance(ids, list) or (nonempty and not ids):
            errors.append(f"{path}.anchors: fehlt oder leer")
            return []
        good = []
        for i in ids:
            if i not in idx:
                errors.append(f"{path}.anchors: unbekannter Anker {i}")
            else:
                good.append(i)
                if side and idx[i][0] != side:
                    side_err.append(f"{path}: Anker {i} gehört zu Passage {idx[i][0]}, nicht {side}")
        return good

    def quote_ok(path, quote, ids):
        if not isinstance(quote, str) or not quote.strip():
            quote_fail.append(f"{path}: kein Belegzitat")
            return
        spans = [idx[i][1]["span"] for i in ids if i in idx]
        if not any(anchor_spans(s, quote.strip().strip("„“\"'"))[0] for s in spans):
            quote_fail.append(f"{path}: Belegzitat steht in keinem der genannten Anker: „{quote[:80]}“")

    def amp(path, rendering, ids):
        f = amplification_flags(rendering, [idx[i][1]["span"] for i in ids if i in idx])
        if f:
            amplif.append({"path": path, "rendering": rendering, "flags": f})

    def enum(path, value, allowed):
        if value not in allowed:
            errors.append(f"{path}: unzulässiger Wert {value!r}")

    for i, s in enumerate(result["speech_acts"]):
        anchors_ok(f"$.speech_acts[{i}]", s.get("anchors"))
        enum(f"$.speech_acts[{i}].act", s.get("act"), ACTS)
    chain_ids = set()
    for i, c in enumerate(result["chains"]):
        p = f"$.chains[{i}]"
        chain_ids.add(c.get("id"))
        enum(f"{p}.side", c.get("side"), ["A", "B"])
        enum(f"{p}.support", c.get("support"), SUPPORT)
        con = c.get("conclusion") or {}
        ids = anchors_ok(f"{p}.conclusion", con.get("anchors"), c.get("side"))
        quote_ok(f"{p}.conclusion", con.get("evidence_quote"), ids)
        amp(f"{p}.conclusion", con.get("rendering"), ids)
        if ids and all(idx[x][1]["region"] != "Kern" for x in ids):
            context_flags.append(f"{p}.conclusion: stützt sich nur auf Kontextanker")
        for x in ids:
            cues = " ".join(idx[x][1]["speech_cues"])
            if "Frage" in cues or "Überschrift" in cues:
                context_flags.append(f"{p}.conclusion: Anker {x} ist Frage/Überschrift")
        if not isinstance(c.get("parts"), list):
            errors.append(f"{p}.parts: fehlt")
            continue
        for j, part in enumerate(c["parts"]):
            q = f"{p}.parts[{j}]"
            enum(f"{q}.role", part.get("role"), ROLES)
            pid = anchors_ok(q, part.get("anchors"), c.get("side"))
            quote_ok(q, part.get("evidence_quote"), pid)
            amp(q, part.get("rendering"), pid)
            if part.get("role") in ("Grund", "Voraussetzung", "Folgerung"):
                for x in pid:
                    cues = " ".join(idx[x][1]["speech_cues"])
                    if "Frage" in cues or "Überschrift" in cues:
                        context_flags.append(f"{q}: {part.get('role')} beruht auf Frage/Überschrift {x}")
        for e in c.get("model_support") or []:
            if tuple(e.get("model_edge") or ()) not in edges:
                errors.append(f"{p}.model_support: Kante nicht in den Läufen {e.get('model_edge')}")
    consistency = []
    for i, q in enumerate(result["questions"]):
        enum(f"$.questions[{i}].relation", q.get("relation"), QREL)
        has_a, has_b = bool(q.get("A")), bool(q.get("B"))
        expected = {"nur A": (True, False), "nur B": (False, True)}.get(q.get("relation"), (True, True))
        if (has_a, has_b) != expected:
            consistency.append(f"$.questions[{i}]: Verhältnis {q.get('relation')!r}, aber Ketten A={q.get('A')} B={q.get('B')}")
        for k in ("A", "B"):
            for cid in q.get(k) or []:
                if cid not in chain_ids:
                    errors.append(f"$.questions[{i}].{k}: unbekannte Kette {cid}")
    for i, c in enumerate(result["conclusion_comparison"]):
        p = f"$.conclusion_comparison[{i}]"
        enum(f"{p}.match", c.get("match"), MATCH)
        anchors_ok(p + ".a", c.get("a"), "A")
        anchors_ok(p + ".b", c.get("b"), "B")
        anchors_ok(p + ".reasons_a", c.get("reasons_a"), "A", nonempty=False)
        anchors_ok(p + ".reasons_b", c.get("reasons_b"), "B", nonempty=False)
    for i, a in enumerate(result["additions"]):
        p = f"$.additions[{i}]"
        enum(f"{p}.kind", a.get("kind"), KINDS)
        ids = anchors_ok(p, a.get("anchors"), a.get("side"))
        quote_ok(p, a.get("evidence_quote"), ids)
        amp(p, a.get("thought"), ids)
    for i, w in enumerate(result["weak_relations"]):
        if w.get("model_edge") is not None and tuple(w["model_edge"]) not in edges:
            errors.append(f"$.weak_relations[{i}]: Kante nicht in den Läufen {w['model_edge']}")
        anchors_ok(f"$.weak_relations[{i}]", w.get("anchors"), nonempty=False)
    for i, o in enumerate(result["open_readings"]):
        anchors_ok(f"$.open_readings[{i}]", o.get("anchors"))
    status = "valid" if not (errors or quote_fail or side_err) else "invalid"
    return {"schema_valid": not errors, "errors": errors, "quote_failures": quote_fail, "side_errors": side_err,
            "amplification_flags": amplif, "context_flags": context_flags, "consistency_flags": consistency, "status": status}


# ------------------------------------------------------------------ Ausführung

def _parse(res, structure) -> tuple[dict | None, dict]:
    if res.stop_reason == "output_split":
        return None, {"schema_valid": False, "status": "invalid",
                      "errors": ["Antwort unvollständig: Ausgabegrenze erreicht, die CLI lieferte nur die Fortsetzung"]}
    try:
        result = extract_json(res.text)
    except (ValueError, json.JSONDecodeError) as e:
        return None, {"schema_valid": False, "errors": [f"kein JSON: {e}"], "status": "invalid"}
    try:
        return result, validate(result, structure)
    except (AttributeError, TypeError, KeyError) as e:
        return result, {"schema_valid": False, "errors": [f"Struktur unlesbar: {e!r}"], "status": "invalid"}


def run(cfg, conn, adapter, pair_dir: Path, label: str = "") -> dict:
    """Ein Aufruf über das Budget. Speichert Eingaben, Prompt, Antwort, Validierung und Ergebnis."""
    system, pv = load_prompt("D_argument")
    inputs = build_inputs(conn, pair_dir)
    user = render_user(inputs)
    meta = {"prompt_version": pv, "prompt_sha256": db.sha256_text(system), "user_sha256": db.sha256_text(user),
            "inputs_sha256": inputs["inputs_sha256"], "extraction_runs": inputs["runs"], "label": label, "started_at": db.now()}
    rid = _start_run(conn, "argument_stage", adapter, pv, {**adapter.cfg, "max_output_tokens": MAX_OUTPUT_TOKENS}, meta)
    meta["run_id"] = rid
    out = pair_dir / f"argument-{rid}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=1), "utf-8")
    (out / "prompt_system.txt").write_text(system, "utf-8")
    (out / "prompt_user.txt").write_text(user, "utf-8")
    conn.commit()
    previous = adapter.max_output_tokens
    adapter.max_output_tokens = MAX_OUTPUT_TOKENS
    try:
        res = adapter.complete(system, user, purpose=f"argument:{pair_dir.name}", run_id=rid)
    except (NotConfigured, CallLimitReached) as e:
        _finish_run(conn, rid, "not_run", str(e))
        conn.commit()
        meta["status"] = "not_run"
        meta["error"] = str(e)
        (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), "utf-8")
        return meta
    except Exception as e:  # Fehlversuch nach Wiederholungen: zählt im Budget, wird protokolliert
        _finish_run(conn, rid, "error", repr(e)[:2000])
        conn.commit()
        meta.update({"status": "error", "error": repr(e)[:2000]})
        (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), "utf-8")
        return meta
    finally:
        adapter.max_output_tokens = previous
    (out / "response.txt").write_text(res.text, "utf-8")
    result, validation = _parse(res, inputs["structure"])
    meta.update({"model": res.model, "usage": res.usage, "call_id": res.call_id, "stop_reason": res.stop_reason, "finished_at": db.now(),
                 "status": validation.get("status")})
    if result is not None:
        (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), "utf-8")
    (out / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=1), "utf-8")
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), "utf-8")
    _finish_run(conn, rid, "finished" if result is not None else "invalid_json", None, res)
    conn.commit()
    meta["dir"] = str(out)
    return meta


# ------------------------------------------------------------------ Bericht

def render_report(result: dict, validation: dict, inputs: dict, meta: dict, with_text: bool) -> str:
    idx = _anchor_index(inputs["structure"])
    n = inputs["structure"]["runs"]

    def ref(ids):
        parts = []
        for i in ids or []:
            if i not in idx:
                parts.append(f"{i} [unbekannt]")
                continue
            a = idx[i][1]
            s = f"{i} [{a['region']}, {len(a['in_runs'])}/{n}]"
            parts.append(s + (f" „{a['span']}“" if with_text else ""))
        return "; ".join(parts) or "–"

    def q(x):
        return f" Beleg: „{x}“" if with_text and x else ""

    L = [f"# Argumentstufe: Werkzeugergebnis {meta['run_id']}", "",
         f"Prompt `{meta['prompt_version']}`, Modell `{meta.get('model')}`, Eingaben `{meta['inputs_sha256'][:16]}…`, "
         f"Extraktionsläufe {', '.join(meta['extraction_runs'])}. **Unbearbeitete Ausgabe** des Werkzeugs; "
         "Prüfanmerkungen stehen getrennt.", "",
         f"Validierung: **{validation.get('status')}** · Schemafehler {len(validation.get('errors', []))} · "
         f"Belegzitat nicht im Anker {len(validation.get('quote_failures', []))} · falsche Seite {len(validation.get('side_errors', []))} · "
         f"Verstärkungshinweise {len(validation.get('amplification_flags', []))} · Kontext/Frage/Überschrift {len(validation.get('context_flags', []))}", ""]
    L += ["## Sprechhandlungen", "", "| Anker | Einordnung | Sprecher | Anmerkung |", "|---|---|---|---|"]
    for s in result.get("speech_acts", []):
        L.append(f"| {', '.join(s.get('anchors', []))} | {s.get('act')}{' (Interpretation)' if s.get('interpretation') else ''} | "
                 f"{s.get('speaker') or '–'} | {s.get('note', '')} |")
    L += ["", "## Begründungsketten", ""]
    for c in result.get("chains", []):
        con = c.get("conclusion", {})
        L += [f"### {c.get('id')} (Passage {c.get('side')}, Fragen {', '.join(c.get('questions', []))}) – {c.get('support')}", "",
              f"**Schluss:** {con.get('rendering')} ({con.get('modality', '')}) — {ref(con.get('anchors'))}{q(con.get('evidence_quote'))}", ""]
        for p in c.get("parts", []):
            L.append(f"- *{p.get('role')}*: {p.get('rendering')} — {ref(p.get('anchors'))}{q(p.get('evidence_quote'))}")
        for r in c.get("reconstructed_premises", []):
            L.append(f"- *rekonstruierte Voraussetzung*: {r}")
        L += ["", f"**Interne Prüfung:** {c.get('internal_assessment')}", ""]
        if c.get("external_checks"):
            L += [f"**Extern zu prüfen:** {'; '.join(c['external_checks'])}", ""]
        if c.get("model_support"):
            L += ["**Modellkanten:** " + ", ".join(f"{' '.join(e['model_edge'])} ({e.get('runs')}/{n})" for e in c["model_support"]), ""]
    L += ["## Bezugsfragen", "", "| Frage | A | B | Verhältnis |", "|---|---|---|---|"]
    for x in result.get("questions", []):
        L.append(f"| {x.get('id')}: {x.get('text')} | {', '.join(x.get('A', [])) or '–'} | {', '.join(x.get('B', [])) or '–'} | {x.get('relation')} |")
    L += ["", "## Vergleich der Schlussfolgerungen", ""]
    for c in result.get("conclusion_comparison", []):
        L += [f"- **{', '.join(c.get('a', []))} ↔ {', '.join(c.get('b', []))}: {c.get('match')}.** Gemeinsam: {c.get('common')} "
              f"Unterschied: {c.get('difference')} Gründe A: {', '.join(c.get('reasons_a', [])) or '–'}; Gründe B: {', '.join(c.get('reasons_b', [])) or '–'}."]
    L += ["", "## Zusätzliche Gedanken", "", "| | Gedanke | Art | in der anderen Passage? | verändert den Gedankengang? | Grundlage | Anker |",
          "|---|---|---|---|---|---|---|"]
    for a in result.get("additions", []):
        L.append(f"| {a.get('id')} ({a.get('side')}) | {a.get('thought')} | {a.get('kind')} | {a.get('contained_in_other')} | "
                 f"{a.get('changes_line')} | {a.get('textual_basis')} | {ref(a.get('anchors'))}{q(a.get('evidence_quote'))} |")
    L += ["", "## Nicht ausreichend gestützte Beziehungen", ""]
    for w in result.get("weak_relations", []):
        L.append(f"- {' '.join(w['model_edge']) if w.get('model_edge') else 'eigene Beziehung'} ({ref(w.get('anchors'))}): {w.get('why_weak')}")
    L += ["", "## Offene Lesarten und Unsicherheiten", ""]
    L += [f"- {', '.join(o.get('anchors', []))}: {o.get('text')}" for o in result.get("open_readings", [])]
    L += [f"- {u}" for u in result.get("uncertainties", [])]
    L += ["", "## Validierung im Einzelnen (deterministisch)", ""]
    for k, label in (("errors", "Schemafehler"), ("quote_failures", "Belegzitat nicht im Anker"), ("side_errors", "falsche Seite"),
                     ("context_flags", "Kontext/Frage/Überschrift"), ("consistency_flags", "Bezugsfragen inkonsistent")):
        items = validation.get(k, [])
        L.append(f"**{label}:** " + ("keine" if not items else ""))
        L += [f"- {x}" for x in items]
    L.append("**Verstärkungshinweise** (Marker im Original, nicht in der Wiedergabe; Hinweis, kein Beweis):")
    L += [f"- {x['path']}: {'; '.join(x['flags'])} — „{x['rendering']}“" for x in validation.get("amplification_flags", [])] or ["- keine"]
    return "\n".join(L) + "\n"


QUOTED = re.compile(r"[„“\"]([^„“”\"]{3,400})[“”\"]")


def mask_source_quotes(text: str, documents: list[str], max_words: int = 4) -> str:
    """Ersetzt in der versionierten Fassung wörtliche Quellzitate mit mehr als max_words Wörtern (auch in freien
    Modelltexten) durch einen Platzhalter. Kurze Wendungen bleiben lesbar, ganze Sätze verlassen data/ nicht."""
    from budget_review.anchoring import folded
    docs = [folded(d) for d in documents]

    def repl(m):
        inner = m.group(1).strip()
        if len(inner.split()) > max_words and any(folded(inner).strip(" .,;:!?…") in d for d in docs):
            return "[Quellzitat, nur lokal]"
        return m.group(0)
    return QUOTED.sub(repl, text)


def write_reports(run_dir: Path, public_out: Path | None = None) -> list[Path]:
    """Vollfassung lokal (mit Originalzitaten); optional eine Fassung ohne Originalzitate zum Versionieren."""
    meta = json.loads((run_dir / "meta.json").read_text("utf-8"))
    inputs = json.loads((run_dir / "inputs.json").read_text("utf-8"))
    validation = json.loads((run_dir / "validation.json").read_text("utf-8"))
    rp = run_dir / "result.json"
    result = json.loads(rp.read_text("utf-8")) if rp.exists() else {}
    full = run_dir / "report_full.md"
    full.write_text(render_report(result, validation, inputs, meta, with_text=True), "utf-8")
    out = [full]
    if public_out is not None:
        public_out.parent.mkdir(parents=True, exist_ok=True)
        docs = [p["document"] for p in inputs["passages"].values()]
        public_out.write_text(mask_source_quotes(render_report(result, validation, inputs, meta, with_text=False), docs), "utf-8")
        out.append(public_out)
    return out
