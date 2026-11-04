"""Argumentanalyse eines Paars aus gespeicherten Läufen, ohne Modellaufruf.

Drei Ebenen werden getrennt gehalten:
  1. Modellausgaben      die gespeicherten Läufe aus br_bridge (Claims, Kanten), unverändert gelesen
  2. deterministisch     Gruppierung über den Originalanker (Budget-Review §4.5: der Anker ist der stabile Träger),
                         Häufigkeit über die Läufe, Absatzart aus dem SuSa-Import, Sprechakt-Hinweise aus Textmarkern
  3. Interpretation      eine von Hand geschriebene Rekonstruktion (JSON), die nur über Anker-IDs auf die Ebenen 1
                         und 2 verweist; `check_interpretation` prüft, dass jeder Verweis existiert

Die Sprechakt-Hinweise sind Marker, keine Entscheidung. Für diese Ebene gibt es in Budget-Review, SPL und
Alexandria keine Komponente (siehe docs/COMPONENT_MAPPING.md); SuSas Absatzart (`paragraphs.kind`) und die
Marker aus `search.MARKERS` werden wiederverwendet.
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

from budget_review.anchoring import folded

from .search import markers_for
from .segment import split_sentences

REPORTING = re.compile(r"\b(argues|argued|argue|pointed out|points out|says|said|according to|claims|claimed|submitted|"
                       r"expressed|adopted a (?:minority )?position|contends|told)\b", re.I)
OTHERS_BELIEF = re.compile(r"\b(others|some people|some|they|people)\b[^.?!]{0,40}?\b(may|might|would|could)\b[^.?!]{0,20}?"
                           r"\b(be convinced|become convinced|believe|find|worry|see|think|form)\b", re.I)
FIRST_PERSON = re.compile(r"\(and I am\)|\bI\b|\bmy\b|\bme\b", re.I)
WE = re.compile(r"\b(we|our|us)\b", re.I)


def sentence_of(document: str, start: int, end: int) -> tuple[int, int]:
    for s, e in split_sentences(document, 0, len(document)):
        if s <= start < e or (start <= s < end):
            return s, e
    return start, end


def speech_cues(document: str, start: int, end: int, paragraph_kind: str | None) -> list[str]:
    """Hinweise zur Sprechhandlung einer Textstelle. Mehrere können zugleich zutreffen."""
    span = document[start:end]
    s, e = sentence_of(document, start, end)
    sentence = document[s:e]
    cues = []
    if paragraph_kind == "h":
        cues.append("Überschrift (Absatzart beim Import)")
    if sentence.rstrip().endswith("?"):
        cues.append("Frage (Satz endet mit Fragezeichen)")
    if REPORTING.search(sentence):
        cues.append(f"Redeverb im Satz: {REPORTING.search(sentence).group(0)}")
    if OTHERS_BELIEF.search(sentence):
        cues.append("mögliche Überzeugung/Haltung anderer (Subjekt + Modalverb + Einstellungsverb)")
    if FIRST_PERSON.search(span) or FIRST_PERSON.search(sentence):
        cues.append("erste Person Singular")
    elif WE.search(span):
        cues.append("erste Person Plural (wir/uns)")
    m = markers_for(span)
    for key, label in (("negation", "Negation"), ("modal", "Modalität"), ("condition", "Bedingung"), ("scope_limit", "Geltungseinschränkung")):
        if m[key]:
            cues.append(f"{label}: {', '.join(m[key][:3])}")
    return cues


def build_structure(out_dir: Path, paragraph_kinds: dict[str, list[tuple[int, int, str]]]) -> dict:
    """Anker-Gruppen und Kanten über alle gespeicherten Läufe. paragraph_kinds: je Seite (start, end, kind) relativ."""
    passages = json.loads((out_dir / "passages.json").read_text("utf-8"))
    runs = [json.loads(p.read_text("utf-8")) for p in sorted(out_dir.glob("run-*.json"))]
    n = len(runs)
    out = {"runs": n, "sides": {}, "cross_edges": []}
    keyid: dict[tuple[str, str], str] = {}
    for side in ("A", "B"):
        p = passages[side]
        doc, (cs, ce) = p["document"], p["core"]
        groups: dict[str, dict] = collections.OrderedDict()
        for k, r in enumerate(runs, 1):
            for c in r[side]["dossier"]["claims"]:
                g = groups.setdefault(folded(c["raw_span"]), {"start": c["anchor_start"], "end": c["anchor_end"], "runs": {}})
                g["runs"][k] = {"proposal_id": c["proposal_id"], "claim_type": c["claim_type"], "content": c["canonical_content"]}
        anchors = []
        for i, (key, g) in enumerate(sorted(groups.items(), key=lambda x: (x[1]["start"], x[1]["end"])), 1):
            aid = f"{side}{i:02d}"
            keyid[(side, key)] = aid
            kind = next((k for s, e, k in paragraph_kinds.get(side, []) if s <= g["start"] < e), None)
            anchors.append({"id": aid, "start": g["start"], "end": g["end"], "abs_start": p["offset"] + g["start"],
                            "abs_end": p["offset"] + g["end"],
                            "region": "Kern" if g["start"] < ce and g["end"] > cs else ("Kontext davor" if g["end"] <= cs else "Kontext danach"),
                            "in_runs": sorted(g["runs"]), "claim_types": sorted({v["claim_type"] for v in g["runs"].values()}),
                            "speech_cues": speech_cues(doc, g["start"], g["end"], kind), "model_outputs": g["runs"],
                            "span": doc[g["start"]:g["end"]]})
        edges = collections.Counter()
        for r in runs:
            d = r[side]["dossier"]
            by_node = {c["claim_node_id"]: folded(c["raw_span"]) for c in d["claims"]}
            for e in d["relations"]:
                edges[(keyid[(side, by_node[e["source_claim_node_id"]])], e["relation_type"],
                       keyid[(side, by_node[e["target_claim_node_id"]])])] += 1
        out["sides"][side] = {"document_id": p["document_id"], "version_text_sha256": p["version_text_sha256"], "core": p["core"],
                              "anchors": anchors, "edges": [{"source": a, "type": t, "target": b, "runs": c}
                                                            for (a, t, b), c in sorted(edges.items())]}
    cross = collections.Counter()
    for r in runs:
        ids = {}
        for side in ("A", "B"):
            for c in r[side]["dossier"]["claims"]:
                ids[f"{side}-{c['proposal_id']}"] = keyid[(side, folded(c["raw_span"]))]
        for e in (r.get("relations") or {}).get("relations", []):
            if e["cross"] and e["source"] in ids and e["target"] in ids:  # das Gate garantiert das; sonst nicht zählen
                cross[(ids[e["source"]], e["type"], ids[e["target"]])] += 1
    out["cross_edges"] = [{"source": a, "type": t, "target": b, "runs": c} for (a, t, b), c in sorted(cross.items())]
    return out


def without_text(structure: dict) -> dict:
    """Fassung ohne Originaltext und ohne Modellwortlaut (für versionierte Ablage)."""
    s = json.loads(json.dumps(structure))
    for side in s["sides"].values():
        for a in side["anchors"]:
            a.pop("span", None)
            a["model_outputs"] = {k: {"proposal_id": v["proposal_id"], "claim_type": v["claim_type"]} for k, v in a["model_outputs"].items()}
    return s


def check_interpretation(interp: dict, structure: dict) -> list[str]:
    """Jeder Verweis der Interpretation muss auf einen vorhandenen Anker zeigen; jede genannte Modellkante muss in
    den gespeicherten Läufen vorkommen."""
    known = {a["id"] for side in structure["sides"].values() for a in side["anchors"]}
    edges = {(e["source"], e["type"], e["target"]) for side in structure["sides"].values() for e in side["edges"]} | \
            {(e["source"], e["type"], e["target"]) for e in structure["cross_edges"]}
    problems = []

    def walk(obj, path):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("anchors", "anchor", "a", "b"):
                    for a in (v if isinstance(v, list) else [v]):
                        if a not in known:
                            problems.append(f"{path}.{k}: unbekannter Anker {a}")
                elif k == "model_edge":
                    t = tuple(v)
                    if t not in edges:
                        problems.append(f"{path}.model_edge: nicht in den gespeicherten Läufen {v}")
                else:
                    walk(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, x in enumerate(obj):
                walk(x, f"{path}[{i}]")
    walk(interp, "$")
    return problems


def render_markdown(interp: dict, structure: dict, with_text: bool) -> str:
    """Bericht aus Interpretation und Struktur. with_text=False: ohne Originaltext und Modellwortlaut (versionierbar)."""
    anchors = {a["id"]: a for side in structure["sides"].values() for a in side["anchors"]}
    n = structure["runs"]

    def ref(ids):
        ids = ids if isinstance(ids, list) else [ids]
        out = []
        for i in ids:
            a = anchors[i]
            s = f"{i} [{a['region']}, Z. {a['start']}–{a['end']}, {len(a['in_runs'])}/{n}]"
            if with_text:
                s += f" „{a['span']}“"
            out.append(s)
        return "; ".join(out)

    m = interp["meta"]
    L = ["# Paar 1: Begründungsketten und zusätzliche Gedanken", "",
         f"Grundlage: {m['basis']}. Interpretation: {m['author']} ({m['status']}).", "",
         "Drei Ebenen: **Modellausgabe** (gespeicherte Claims und Kanten), **deterministisch** (Anker-Gruppen, "
         "Häufigkeit über die Läufe, Sprechakt-Hinweise), **Interpretation** (alles Folgende in eigenen Worten). "
         f"Anker-Angaben: ID [Bereich, Zeichen, in wie vielen der {n} Läufe verankert]. {m['frequency_note']}.", ""]
    if not with_text:
        L += ["Originaltexte und Modellwortlaut stehen in der lokalen Fassung `data/semantic/rs-2026-11-03-20261103-p1/analysis_full.md`.", ""]
    L += ["## 1. Sprechhandlungen", "", "| Anker | Einordnung | Hinweis |", "|---|---|---|"]
    for sa in interp["speech_acts"]:
        ids = sa["anchor"] if isinstance(sa["anchor"], list) else [sa["anchor"]]
        cue = "; ".join(sorted({c for i in ids for c in anchors[i]["speech_cues"]})) or "–"
        note = " · ".join(x for x in (sa.get("speaker") and f"Sprecher: {sa['speaker']}", sa.get("modality"), sa.get("note"),
                                      sa.get("model_divergence") and f"Läufe: {sa['model_divergence']}") if x)
        L.append(f"| {', '.join(ids)} | **{sa['act']}** | {note}<br><span>Marker: {cue}</span> |")
    L += ["", "## 2. Begründungsketten", ""]
    for ch in interp["chains"]:
        c = ch["conclusion"]
        L += [f"### {ch['id']} (Passage {ch['side']}, Frage {ch['question']})", "",
              f"**Schlussfolgerung:** {c['rendering']} ({c.get('modality', '')})  ", f"Anker: {ref(c['anchors'])}", ""]
        for p in ch["parts"]:
            L.append(f"- *{p['role']}*: {p['rendering']} — {ref(p['anchors'])}")
        if ch.get("missing_premises"):
            L.append(f"- *Fehlende Voraussetzung*: {'; '.join(ch['missing_premises'])}")
        L += ["", f"**Interne Prüfung:** {ch['internal_assessment']}", ""]
        if ch.get("external_checks"):
            L += [f"**Extern zu prüfen (hier nicht geprüft):** {'; '.join(ch['external_checks'])}", ""]
        L.append("**Modellkanten:** " + ", ".join(f"{e['model_edge'][0]} {e['model_edge'][1]} {e['model_edge'][2]} ({e['runs']}/{n})"
                                                  for e in ch["model_support"]))
        if ch.get("run_differences"):
            L.append(f"  \n**Unterschiede zwischen den Läufen:** {ch['run_differences']}")
        L.append("")
    L += ["## 3. Bezugsfragen", "", "| Frage | A | B | Verhältnis |", "|---|---|---|---|"]
    for q in interp["questions"]:
        L.append(f"| {q['id']}: {q['text']} | {', '.join(q['A']) or '–'} | {', '.join(q['B']) or '–'} | {q['relation']} |")
    L += [""]
    for cc in interp["conclusion_comparison"]:
        L += [f"**Schlussfolgerungen {', '.join(cc['a'])} und {', '.join(cc['b'])}: {cc['match']} übereinstimmend.**", "",
              f"- Gemeinsam: {cc['common']}", f"- Unterschied: {cc['difference']}", f"- SuSa-Typ: {', '.join(cc['susa_relation_types'])}",
              f"- Darstellung: {cc['representation']}", ""]
    L += ["## 4. Zusätzliche Gedanken", "", "| | Gedanke | Art | in der anderen Passage? | verändert den Gedankengang? | textliche Grundlage | Anker |",
          "|---|---|---|---|---|---|---|"]
    for a in interp["additions"]:
        L.append(f"| {a['id']} | {a['thought']} | {a['kind']} | {a['contained_in_other']} | {a['changes_line']} | {a['textual_basis']} | {ref(a['anchors'])} |")
    L += ["", "## 5. Nicht ausreichend gestützte Beziehungen", "", "| Modellkante | Läufe | Warum schwach |", "|---|---|---|"]
    for w in interp["weak_relations"]:
        L.append(f"| {' '.join(w['model_edge'])} | {w['runs']}/{n} | {w['why_weak']} |")
    L += ["", "Geprüft, aber ohne Kante (eine fehlende Kante ist kein Befund):", ""]
    for x in interp["absent_but_checked"]:
        L.append(f"- {', '.join(x['anchors'])}: {x['note']}")
    L += ["", "## 6. Offene Lesarten", ""]
    for o in interp["open_readings"]:
        L.append(f"- {', '.join(o['anchors'])}: {o['text']}")
    h = interp["human_comparison"]
    L += ["", "## 7. Vergleich mit Steffens Einschätzung", "", f"Quelle: {h['source']}.", "", f"> {h['summary']}", "",
          "Übereinstimmung: " + "; ".join(h["agreement"]) + ".", "", "Unterschiede:", ""] + [f"- {d}" for d in h["differences"]]
    L += ["", "Die Einschätzung ist ein Vergleich, kein Goldstandard; die Analyse wurde nach ihrer Übermittlung geschrieben "
          "und ist von ihr nicht unabhängig.", ""]
    return "\n".join(L)
