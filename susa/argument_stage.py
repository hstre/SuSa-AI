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


def add_sentence_anchors(structure: dict, passages: dict, kinds: dict) -> None:
    """Sätze ohne eigenen Claim (z. B. ein einleitender Rahmensatz) werden als zitierbare Stellen ergänzt: IDs
    <Seite>S<nn>, wörtliche Spanne und Offsets aus dem gespeicherten Text, keine Modellaussage. Damit kann eine
    Interpretation sich auf sie berufen, statt sie nur im Freitext zu erwähnen."""
    from .pair_analysis import speech_cues
    from .segment import split_sentences
    for side, p in passages.items():
        doc, (cs, ce) = p["document"], p["core"]
        sd = structure["sides"][side]
        claims = [(a["start"], a["end"]) for a in sd["anchors"]]
        paras = [(max(a, 0), min(b, len(doc)), k) for a, b, k in kinds.get(side, []) if b > 0 and a < len(doc)] or [(0, len(doc), None)]
        out = []
        for ps, pe, kind in paras:
            for s0, e0 in split_sentences(doc, ps, pe):
                covered = sum(max(0, min(e0, e) - max(s0, s)) for s, e in claims)
                if covered >= 0.5 * (e0 - s0):
                    continue
                out.append({"id": f"{side}S{len(out) + 1:02d}", "start": s0, "end": e0, "abs_start": p["offset"] + s0,
                            "abs_end": p["offset"] + e0, "kind": "Satz ohne Claim",
                            "region": "Kern" if s0 < ce and e0 > cs else ("Kontext davor" if e0 <= cs else "Kontext danach"),
                            "in_runs": [], "claim_types": [], "speech_cues": speech_cues(doc, s0, e0, kind),
                            "model_outputs": {}, "span": doc[s0:e0]})
        sd["sentences"] = out


def build_inputs(conn, pair_dir: Path) -> dict:
    passages = json.loads((pair_dir / "passages.json").read_text("utf-8"))
    kinds = paragraph_kinds(conn, passages)
    structure = build_structure(pair_dir, kinds)
    add_sentence_anchors(structure, passages, kinds)
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
        if s.get("sentences"):
            out.append(f"Sätze ohne Claim {side} (zitierbar wie Anker; keine Aussage der Läufe) (ID | Bereich | Hinweise | Originalstelle):")
            for a in s["sentences"]:
                out.append(f"- {a['id']} | {a['region']} | {'; '.join(a['speech_cues']) or '–'} | „{a['span']}“")
        out.append(f"Kanten innerhalb {side} (Quelle Typ Ziel, Läufe): " +
                   (", ".join(f"{e['source']} {e['type']} {e['target']} ({e['runs']}/{n})" for e in s["edges"]) or "keine"))
        out.append("")
    out.append("Kanten zwischen A und B: " + (", ".join(f"{e['source']} {e['type']} {e['target']} ({e['runs']}/{n})"
                                                     for e in S["cross_edges"]) or "keine (nicht erzeugt)"))
    return "\n".join(out)


# ------------------------------------------------------------------ Sprecherzuordnung (deterministisch)

UNSURE = re.compile(r"wahrscheinlich|vermutlich|unklar|unsicher|offen|möglicherweise|\boder\b|\?", re.I)
# Freitext, der eine Passage selbst zum Subjekt einer Festlegung macht („B behauptet …“)
OWN_CLAIM = r"(?<![\w-]){side}(?![\w+-])(?:\s*\([^)]*\))?[^.;:]{{0,25}}?\b(behauptet|vertritt|begründet|argumentiert|hält|meint|fordert|bestreitet|schließt)\b"


def holder(anchor_ids: list[str], result: dict) -> dict:
    """Wer vertritt die Aussage an diesen Ankern? Nur aus den Sprechakten des Ergebnisses abgeleitet, nicht aus dem
    Seitenetikett. Offenheit (act „offen“, unsichere Sprecherangabe, gemischte oder fehlende Einordnung) bleibt
    erhalten und wird nie zur eigenen Position der Passage aufgelöst."""
    acts, unsure, missing = [], False, []
    for a in anchor_ids or []:
        hits = [sa for sa in result.get("speech_acts", []) if a in (sa.get("anchors") or [])]
        if not hits:
            missing.append(a)
        for h in hits:
            acts.append((h.get("act"), h.get("speaker") or "–"))
            unsure |= h.get("act") == "offen" or bool(UNSURE.search(h.get("speaker") or "")) or bool(h.get("interpretation"))
    distinct = sorted(set(acts))
    unsure |= bool(missing)
    mixed = len({x[0] for x in distinct}) > 1
    readings = [o.get("text") for o in result.get("open_readings", []) if set(o.get("anchors") or []) & set(anchor_ids or [])]
    label = "; ".join(f"{act}: {spk}" for act, spk in distinct) or "nicht eingeordnet"
    if missing:
        label += f" (ohne Sprechakt: {', '.join(missing)})"
    return {"label": label, "acts": [x[0] for x in distinct], "own": bool(distinct) and all(x[0] == "vertritt" for x in distinct) and not missing,
            "unsure": unsure, "mixed": mixed, "open_readings": readings}


def holder_text(ids, result) -> str:
    h = holder(ids, result)
    return h["label"] + (" — Sprecher nicht eindeutig" if h["unsure"] else "") + \
        (" — Anker mit verschiedener Einordnung" if h["mixed"] else "") + (" — offene Lesart (siehe offene Lesarten)" if h["open_readings"] else "")


def attribution_flags(result: dict) -> list[str]:
    """Freitext im Vergleich oder bei Zusätzen schreibt einer Passage eine Festlegung zu, deren Anker dort nicht als
    eigene Position eingeordnet sind. Hinweis für die Durchsicht, kein Beweis."""
    flags = []
    for i, c in enumerate(result.get("conclusion_comparison", [])):
        for side, key in (("A", "a"), ("B", "b")):
            h = holder(c.get(key), result)
            if h["own"]:
                continue
            for field in ("common", "difference"):
                m = re.search(OWN_CLAIM.format(side=side), c.get(field) or "")
                if m:
                    flags.append(f"$.conclusion_comparison[{i}].{field}: „{m.group(0)}“, aber {', '.join(c.get(key) or [])} sind {h['label']}")
    for i, a in enumerate(result.get("additions", [])):
        h = holder(a.get("anchors"), result)
        if not h["own"] and re.search(OWN_CLAIM.format(side=a.get("side", "?")), a.get("thought") or ""):
            flags.append(f"$.additions[{i}].thought: Festlegung der Passage {a.get('side')} zugeschrieben, Anker sind {h['label']}")
    return flags


# ------------------------------------------------------------------ Validierung

def _anchor_index(structure):
    return {a["id"]: (side, a) for side, s in structure["sides"].items() for a in s["anchors"] + s.get("sentences", [])}


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
            "amplification_flags": amplif, "context_flags": context_flags, "consistency_flags": consistency,
            "attribution_flags": attribution_flags(result), "status": status}


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

    def hl(ids):
        return holder_text(ids, result)

    L = [f"# Argumentstufe: Werkzeugergebnis {meta['run_id']}", "",
         f"Prompt `{meta['prompt_version']}`, Modell `{meta.get('model')}`, Eingaben `{meta['inputs_sha256'][:16]}…`, "
         f"Extraktionsläufe {', '.join(meta['extraction_runs'])}. **Unbearbeitete Ausgabe** des Werkzeugs; "
         "Prüfanmerkungen stehen getrennt.", "",
         f"Validierung: **{validation.get('status')}** · Schemafehler {len(validation.get('errors', []))} · "
         f"Belegzitat nicht im Anker {len(validation.get('quote_failures', []))} · falsche Seite {len(validation.get('side_errors', []))} · "
         f"Verstärkungshinweise {len(validation.get('amplification_flags', []))} · Kontext/Frage/Überschrift {len(validation.get('context_flags', []))} · "
         f"Zuschreibung {len(validation.get('attribution_flags', []))}" + (f" ({validation['note']})" if validation.get("note") else ""), ""]
    L += ["## Sprechhandlungen", "", "| Anker | Einordnung | Sprecher | Anmerkung |", "|---|---|---|---|"]
    for s in result.get("speech_acts", []):
        L.append(f"| {', '.join(s.get('anchors', []))} | {s.get('act')}{' (Interpretation)' if s.get('interpretation') else ''} | "
                 f"{s.get('speaker') or '–'} | {s.get('note', '')} |")
    L += ["", "## Begründungsketten", ""]
    for c in result.get("chains", []):
        con = c.get("conclusion", {})
        L += [f"### {c.get('id')} (Passage {c.get('side')}, Fragen {', '.join(c.get('questions', []))}) – {c.get('support')}", "",
              f"**Schluss:** {con.get('rendering')} ({con.get('modality', '')}) — {ref(con.get('anchors'))}{q(con.get('evidence_quote'))}", "",
              f"**Vertreten von** (aus den Sprechakten): {hl(con.get('anchors'))}", ""]
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
              f"Unterschied: {c.get('difference')} Gründe A: {', '.join(c.get('reasons_a', [])) or '–'}; Gründe B: {', '.join(c.get('reasons_b', [])) or '–'}.",
              f"  Vertreten von (aus den Sprechakten): A {hl(c.get('a'))} · B {hl(c.get('b'))}"]
    L += ["", "## Zusätzliche Gedanken", "", "| | Gedanke | Art | vertreten von | in der anderen Passage? | verändert den Gedankengang? | Grundlage | Anker |",
          "|---|---|---|---|---|---|---|---|"]
    for a in result.get("additions", []):
        L.append(f"| {a.get('id')} ({a.get('side')}) | {a.get('thought')} | {a.get('kind')} | {hl(a.get('anchors'))} | {a.get('contained_in_other')} | "
                 f"{a.get('changes_line')} | {a.get('textual_basis')} | {ref(a.get('anchors'))}{q(a.get('evidence_quote'))} |")
    L += ["", "## Nicht ausreichend gestützte Beziehungen", ""]
    for w in result.get("weak_relations", []):
        L.append(f"- {' '.join(w['model_edge']) if w.get('model_edge') else 'eigene Beziehung'} ({ref(w.get('anchors'))}): {w.get('why_weak')}")
    L += ["", "## Offene Lesarten und Unsicherheiten", ""]
    L += [f"- {', '.join(o.get('anchors', []))}: {o.get('text')}" for o in result.get("open_readings", [])]
    L += [f"- {u}" for u in result.get("uncertainties", [])]
    L += ["", "## Validierung im Einzelnen (deterministisch)", ""]
    for k, label in (("errors", "Schemafehler"), ("quote_failures", "Belegzitat nicht im Anker"), ("side_errors", "falsche Seite"),
                     ("context_flags", "Kontext/Frage/Überschrift"), ("consistency_flags", "Bezugsfragen inkonsistent"),
                     ("attribution_flags", "Zuschreibung im Freitext weicht von den Sprechakten ab")):
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


RENDER_VERSION = "r2"  # r1: ohne Sprecherzuordnung in Ketten/Vergleichen; r1-Dateien bleiben unverändert liegen


def render_short(result: dict, validation: dict, inputs: dict, meta: dict, with_text: bool) -> str:
    """Kurzbericht zu drei Fragen. Wer eine Aussage vertritt, kommt nur aus den Sprechakten (holder), nie aus dem
    Seitenetikett; offene Sprecher bleiben als offen markiert."""
    idx = _anchor_index(inputs["structure"])

    def ref(ids):
        return "; ".join(f"{i} [{idx[i][1]['region']}" + (", Satz ohne Claim" if idx[i][1].get("kind") else "") + "]"
                         + (f" „{idx[i][1]['span']}“" if with_text else "") if i in idx else f"{i} [unbekannt]" for i in ids or []) or "–"

    def who(ids):
        return holder_text(ids, result)

    chains = {c.get("id"): c for c in result.get("chains", [])}
    L = [f"# Kurzbericht {meta['run_id']}", "",
         f"Abgeleitet aus dem unveränderten Werkzeugergebnis (Prompt `{meta['prompt_version']}`), Darstellung {RENDER_VERSION}. "
         "„Vertreten von“ stammt aus den Sprechakten des Ergebnisses, nicht aus der Passage, in der die Aussage steht.", "",
         "## 1. Welche Frage behandelt jede Passage, und wer vertritt die Aussage?", ""]
    for side in ("A", "B"):
        L.append(f"**Passage {side}**")
        for qn in result.get("questions", []):
            for cid in qn.get(side) or []:
                c = chains.get(cid, {})
                con = c.get("conclusion", {})
                L.append(f"- {qn.get('id')} ({qn.get('relation')}): {qn.get('text')} — Schluss {cid}: {con.get('rendering')} "
                         f"— vertreten von: {who(con.get('anchors'))} — {ref(con.get('anchors'))}")
        unasked = [c for c in chains.values() if c.get("side") == side and not any(c.get("id") in (qn.get(side) or []) for qn in result.get("questions", []))]
        L += [f"- ohne Frage: Schluss {c.get('id')}: {c.get('conclusion', {}).get('rendering')} — vertreten von: {who(c.get('conclusion', {}).get('anchors'))}" for c in unasked]
        L.append("")
    L += ["Vergleich der Schlüsse:", ""]
    for c in result.get("conclusion_comparison", []):
        L.append(f"- {', '.join(c.get('a', []))} ↔ {', '.join(c.get('b', []))}: {c.get('match')}. A vertreten von: {who(c.get('a'))}; "
                 f"B vertreten von: {who(c.get('b'))}.")
    L += ["", "## 2. Welcher Gedanke kommt hinzu, welche Textstelle begründet ihn, ändert er eine Schlussfolgerung?", ""]
    for a in result.get("additions", []) or []:
        L += [f"- **{a.get('id')} ({a.get('kind')})**: {a.get('thought')}",
              f"  - vertreten von: {who(a.get('anchors'))}",
              f"  - Textstelle: {ref(a.get('anchors'))}" + (f"; Beleg „{a.get('evidence_quote')}“" if with_text and a.get("evidence_quote") else ""),
              f"  - in der anderen Passage: {a.get('contained_in_other')}",
              f"  - ändert den Gedankengang/Schluss: {a.get('changes_line')}"]
    if not result.get("additions"):
        L.append("- Kein zusätzlicher Gedanke ausgewiesen.")
    L += ["", "## 3. Wo erlauben Wortlaut oder Kontext mehrere Lesarten?", ""]
    L += [f"- {', '.join(o.get('anchors', []))}: {o.get('text')}" for o in result.get("open_readings", [])] or ["- keine ausgewiesen"]
    flags = validation.get("attribution_flags") or []
    if flags:
        L += ["", "Prüfhinweise zur Zuschreibung (Freitext des Modells weicht von seinen Sprechakten ab):", ""] + [f"- {f}" for f in flags]
    ctx = validation.get("context_flags") or []
    if ctx:
        L += ["", "Schlüsse, die nur auf Kontext, Frage oder Überschrift beruhen:", ""] + [f"- {f}" for f in ctx]
    return "\n".join(L) + "\n"


def write_reports(run_dir: Path, public_out: Path | None = None, public_short: Path | None = None,
                  revalidate: bool = False) -> list[Path]:
    """Vollfassung und Kurzbericht lokal (mit Originalzitaten); optional Fassungen ohne längere Originalzitate zum
    Versionieren. revalidate: aktuelle Prüfregeln auf das gespeicherte Ergebnis anwenden und getrennt ablegen
    (validation.json bleibt unverändert)."""
    meta = json.loads((run_dir / "meta.json").read_text("utf-8"))
    inputs = json.loads((run_dir / "inputs.json").read_text("utf-8"))
    validation = json.loads((run_dir / "validation.json").read_text("utf-8"))
    rp = run_dir / "result.json"
    result = json.loads(rp.read_text("utf-8")) if rp.exists() else {}
    if revalidate and result:
        from .config import code_version
        validation = validate(result, inputs["structure"])
        validation.update({"note": f"Nachprüfung {RENDER_VERSION} mit aktuellen Prüfregeln; validation.json ist der Stand zum Laufzeitpunkt",
                           "code_version": code_version()})
        (run_dir / f"validation_recheck.{RENDER_VERSION}.json").write_text(json.dumps(validation, ensure_ascii=False, indent=1), "utf-8")
    docs = [p["document"] for p in inputs["passages"].values()]
    out = []
    for name, fn, pub in (("report_full", render_report, public_out), ("report_short", render_short, public_short)):
        local = run_dir / f"{name}.{RENDER_VERSION}.md"
        local.write_text(fn(result, validation, inputs, meta, with_text=True), "utf-8")
        out.append(local)
        if pub is not None:
            pub.parent.mkdir(parents=True, exist_ok=True)
            pub.write_text(mask_source_quotes(fn(result, validation, inputs, meta, with_text=False), docs), "utf-8")
            out.append(pub)
    return out
