"""Beurteilungsheft für eine Prüfauswahl: eine lokal zu öffnende HTML-Datei, in der eine Person zuerst blind urteilt
und danach das Werkzeugergebnis und die Durchsicht einsieht und bewertet.

Die Datei enthält fremde Originaltexte und Übersetzungen: nur lokal verwenden (Standardziel unter data/export/),
nicht veröffentlichen, nicht versionieren. Nicht enthalten sind Suchhypothesen, Auswahlgründe und Ähnlichkeitswerte.
Titel, Autor und Publikation stehen zugeklappt am Ende jedes Paars.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from . import db
from . import review_set as rs
from .argument_stage import holder_text as _holder_text
from .blind_html import build_payload

SEG_LABEL = {"before": "Kontext davor", "core": "Kernabschnitt", "after": "Kontext danach"}


def holder_text(ids, result) -> str:
    return _holder_text(ids, result).replace(": –", ": Sprecher nicht angegeben")


def _e(x) -> str:
    return html.escape(str(x if x is not None else ""))


def _overview_rows(path: Path) -> dict[int, list[str]]:
    rows = {}
    if not path.exists():
        return rows
    text = path.read_text("utf-8")
    text = text.split("## Übersicht", 1)[-1].split("\n## ", 1)[0]  # nur die Übersichtstabelle
    for line in text.splitlines():
        m = re.match(r"\|\s*(\d+)(?:\s*\(Referenz\))?\s*\|(.*)\|\s*$", line)
        if m:
            rows[int(m.group(1))] = [c.strip() for c in m.group(2).split("|")]
    return rows


def _latest_valid(pair_dir: Path) -> Path | None:
    for m in sorted(pair_dir.glob("argument-*/meta.json"), reverse=True):
        if json.loads(m.read_text("utf-8")).get("status") == "valid":
            return m.parent
    return None


def _tool_section(pos: int, pair_dir: Path, docs: Path) -> str:
    if pos == 1:
        ref = docs / "pair1" / "argument_analysis.json"
        if not ref.exists():
            return "<p>Keine Referenz vorhanden.</p>"
        r = json.loads(ref.read_text("utf-8"))
        out = ["<p class=note>Paar 1 ist eine <b>nachbearbeitete Referenz</b>: Claude hat sie in der Sitzung aus drei "
               "Extraktionsläufen interpretiert (Fassung 2). Sie ist keine Ausgabe der wiederverwendbaren Argumentstufe.</p>"]
        out.append("<h4>Bezugsfragen</h4><ul>" + "".join(f"<li><b>{_e(q['id'])}</b> {_e(q['text'])} — <i>{_e(q['relation'])}</i></li>"
                                                     for q in r.get("questions", [])) + "</ul>")
        out.append("<h4>Vergleich der Schlüsse</h4><ul>" + "".join(
            f"<li>{_e(', '.join(c['a']))} ↔ {_e(', '.join(c['b']))}: <b>{_e(c['match'])}</b>. Gemeinsam: {_e(c['common'])} "
            f"Unterschied: {_e(c['difference'])}</li>" for c in r.get("conclusion_comparison", [])) + "</ul>")
        out.append("<h4>Zusätzliche Gedanken</h4><ul>" + "".join(
            f"<li><b>{_e(a['id'])}</b> ({_e(a['kind'])}): {_e(a['thought'])}<br><span class=sub>Anker {_e(', '.join(a['anchors']))} · "
            f"in der anderen Passage: {_e(a['contained_in_other'])}</span></li>" for a in r.get("additions", [])) + "</ul>")
        return "\n".join(out)
    run = _latest_valid(pair_dir)
    if run is None:
        status = docs / f"pair{pos}" / "STATUS.md"
        return "<p class=warn>Kein gültiges Werkzeugergebnis.</p>" + (f"<pre>{_e(status.read_text('utf-8'))}</pre>" if status.exists() else "")
    r = json.loads((run / "result.json").read_text("utf-8"))
    inputs = json.loads((run / "inputs.json").read_text("utf-8"))
    meta = json.loads((run / "meta.json").read_text("utf-8"))
    idx = {a["id"]: a for s in inputs["structure"]["sides"].values() for a in s["anchors"] + s.get("sentences", [])}

    def anchors(ids):
        return "".join(f"<div class=anc><code>{_e(i)}</code> <span class=sub>[{_e(idx[i]['region'])}]</span> „{_e(idx[i]['span'])}“</div>"
                       if i in idx else f"<div class=anc><code>{_e(i)}</code> (unbekannt)</div>" for i in ids or [])

    chains = {c["id"]: c for c in r.get("chains", [])}
    out = [f"<p class=sub>Lauf <code>{_e(meta['run_id'])}</code>, Prompt <code>{_e(meta['prompt_version'])}</code>, unveränderte "
           "Werkzeugausgabe. „vertreten von“ ist aus den Sprechakten abgeleitet.</p>", "<h4>Bezugsfragen und Schlüsse</h4><ul>"]
    for q in r.get("questions", []):
        items = []
        for side in ("A", "B"):
            for cid in q.get(side) or []:
                con = chains.get(cid, {}).get("conclusion", {})
                items.append(f"<div><b>{side}</b> ({_e(cid)}): {_e(con.get('rendering'))} <span class=sub>— vertreten von: "
                             f"{_e(holder_text(con.get('anchors'), r))}</span>{anchors(con.get('anchors'))}</div>")
        out.append(f"<li><b>{_e(q['id'])}</b> {_e(q['text'])} — <i>{_e(q['relation'])}</i>{''.join(items)}</li>")
    out.append("</ul><h4>Vergleich der Schlüsse</h4><ul>")
    for c in r.get("conclusion_comparison", []):
        out.append(f"<li>{_e(', '.join(c['a']))} ↔ {_e(', '.join(c['b']))}: <b>{_e(c['match'])}</b><br>Gemeinsam: {_e(c['common'])}<br>"
                   f"Unterschied: {_e(c['difference'])}<br><span class=sub>A vertreten von: {_e(holder_text(c['a'], r))} · "
                   f"B vertreten von: {_e(holder_text(c['b'], r))}</span></li>")
    out.append("</ul><h4>Zusätzliche Gedanken (Kandidaten)</h4><ul>")
    for a in r.get("additions", []):
        out.append(f"<li><b>{_e(a['id'])}</b> <span class=tag>{_e(a['kind'])}</span> {_e(a['thought'])}<br>"
                   f"<span class=sub>vertreten von: {_e(holder_text(a['anchors'], r))} · in der anderen Passage: {_e(a['contained_in_other'])} · "
                   f"Bezug: {_e(a['changes_line'])}</span>{anchors(a['anchors'])}</li>")
    out.append("</ul><h4>Offene Lesarten</h4><ul>" + "".join(f"<li>{_e(', '.join(o['anchors']))}: {_e(o['text'])}</li>"
                                                         for o in r.get("open_readings", [])) + "</ul>")
    return "\n".join(out)


def _review_section(pos: int, docs: Path, rows: dict) -> str:
    row = rows.get(pos)
    cols = ["Frage(n)", "wichtigster begründeter Zusatz", "Art", "wesentliche Unsicherheit oder Fehlinterpretation", "Durchsicht"]
    out = ["<p class=sub>Durchsicht durch Claude (dieselbe Modellfamilie wie das Werkzeug): keine unabhängige Prüfung, kein Goldstandard.</p>"]
    if row:
        out.append("<table>" + "".join(f"<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>" for k, v in zip(cols, row)) + "</table>")
    notes = docs / f"pair{pos}" / "REVIEW_NOTES.md"
    if notes.exists():
        body = notes.read_text("utf-8").split("\n", 1)[1]
        out.append(f"<details><summary>Ausführliche Durchsicht</summary><pre class=md>{_e(body.strip())}</pre></details>")
    return "\n".join(out)


def build(cfg, conn, sid: str, docs: Path, out: Path) -> Path:
    payload = build_payload(cfg, conn, sid)
    rows = _overview_rows(docs / "AUSWERTUNG_PAARE_1-10.md")
    parts = []
    for it in payload["items"]:
        pos = int(it["position"])
        pair_dir = cfg.subdir(f"semantic/{sid}-p{pos}")
        sides_html = []
        for key in ("A", "B"):
            s = it["sides"][key]
            segs = []
            for sg in s["segments"]:
                if not (sg["text"] or "").strip():
                    continue
                warn = "<div class=warn>Übersetzung passt nicht zur Textfassung</div>" if sg.get("translation_mismatch") else ""
                notes = "".join(f"<li>{_e(n)}</li>" for n in sg.get("notes") or [])
                segs.append(f"<div class='seg {sg['name']}'><div class=seglabel>{_e(SEG_LABEL.get(sg['name'], sg['name']))}</div>{warn}"
                            f"<div class=cols><div class=orig>{_e(sg['text'])}</div><div class=de>{_e(sg['de'] or '— keine Übersetzung —')}"
                            f"{'<ul class=trnotes>' + notes + '</ul>' if notes else ''}</div></div></div>")
            sides_html.append(f"<section class=side><h3>Passage {key}</h3>{''.join(segs)}</section>")
        q = "".join(f"<label>{_e(t)}<textarea data-k='p{pos}.{k}'></textarea></label>" for k, t in payload["questions"])
        verdicts = "".join(f"<label class=opt><input type=radio name='v{pos}' value='{k}' data-k='p{pos}.verdict'> {_e(t)}</label>"
                           for k, t in payload["verdicts"].items())
        flags = "".join(f"<label class=opt><input type=checkbox value='{k}' data-k='p{pos}.flag.{k}'> {_e(t)}</label>"
                        for k, t in payload["flags"].items())
        tool_q = (f"<label>Ist der wichtigste vom Werkzeug genannte Zusatz relevant und durch die Textstellen gedeckt?"
                  + "".join(f"<label class=opt><input type=radio name='t{pos}' value='{v}' data-k='p{pos}.tool_relevant'> {v}</label>"
                            for v in ("ja", "teilweise", "nein", "nicht beurteilbar")) + "</label>"
                  f"<label>Fehlinterpretationen im Werkzeugergebnis (berichtet → eigen, Möglichkeit → Feststellung, Gleichsetzung, "
                  f"fehlende Begründung, ergänzter Kontext)<textarea data-k='p{pos}.tool_errors'></textarea></label>"
                  f"<label>Stimmen Sie der Durchsicht zu? Wo nicht?<textarea data-k='p{pos}.review_comment'></textarea></label>")
        meta = "".join(f"<div><b>{_e(k)}:</b> {_e(it['sides'][k]['meta'].get('title'))} · {_e(it['sides'][k]['meta'].get('author'))} · "
                       f"{_e(it['sides'][k]['meta'].get('publication'))} · {_e(it['sides'][k]['meta'].get('date'))}</div>" for k in ("A", "B"))
        parts.append(f"""<article id=p{pos}><h2>Paar {pos}</h2>
<div class=step>Schritt 1 · Lesen</div>{''.join(sides_html)}
<div class=step>Schritt 2 · Eigenes Urteil (vor dem Öffnen des Werkzeugergebnisses)</div>
<div class=form>{q}<div class=row><b>Gesamteinschätzung:</b> {verdicts}</div><div class=row><b>Hinweise:</b> {flags}</div></div>
<details class=tool><summary>Schritt 3 · Werkzeugergebnis öffnen (erst nach dem eigenen Urteil)</summary>{_tool_section(pos, pair_dir, docs)}
<h4>Durchsicht</h4>{_review_section(pos, docs, rows)}</details>
<div class=step>Schritt 4 · Werkzeug bewerten</div><div class=form>{tool_q}</div>
<details><summary>Herkunft der Passagen (nach dem Urteil)</summary>{meta}</details></article>""")
    toc = " ".join(f"<a href='#p{int(i['position'])}'>{int(i['position'])}</a>" for i in payload["items"])
    doc = f"""<!doctype html><html lang=de><head><meta charset=utf-8><meta name=viewport content="width=device-width, initial-scale=1">
<title>Beurteilungsheft</title><style>
:root{{--bg:#fff;--fg:#1d1d1f;--muted:#666;--line:#ddd;--core:#fff8e1;--ctx:#f6f6f6;--acc:#0b57d0;--warn:#b3261e}}
@media (prefers-color-scheme: dark){{:root{{--bg:#121212;--fg:#eee;--muted:#aaa;--line:#333;--core:#2b2612;--ctx:#1c1c1c;--acc:#8ab4f8;--warn:#f2b8b5}}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;margin:0;padding:0 16px}}
main{{max-width:1100px;margin:0 auto}} h1{{margin:24px 0 4px}} h2{{border-top:3px solid var(--fg);padding-top:16px;margin-top:40px}}
.intro,.sub,.seglabel{{color:var(--muted)}} .sub{{font-size:.9em}} nav{{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line);z-index:1}}
nav a{{margin-right:10px;color:var(--acc)}} .step{{font-weight:600;margin:20px 0 8px;color:var(--acc)}}
.side{{border:1px solid var(--line);border-radius:6px;padding:8px 12px;margin:8px 0}} .seg{{margin:8px 0;padding:6px 8px;border-radius:4px;background:var(--ctx)}}
.seg.core{{background:var(--core)}} .seglabel{{font-size:.8em;text-transform:uppercase;letter-spacing:.04em}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:16px}} @media (max-width:760px){{.cols{{grid-template-columns:1fr}}}}
.orig,.de{{white-space:pre-wrap}} .de{{border-left:2px solid var(--line);padding-left:12px}} .trnotes{{font-size:.85em;color:var(--muted)}}
.form label{{display:block;margin:8px 0}} textarea{{width:100%;min-height:64px;box-sizing:border-box;font:inherit;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:4px}}
.opt{{display:inline-block!important;margin-right:14px!important}} .row{{margin:8px 0}} details{{margin:12px 0}} summary{{cursor:pointer;font-weight:600}}
details.tool{{border:1px dashed var(--acc);border-radius:6px;padding:8px 12px}} .anc{{font-size:.9em;margin:2px 0 2px 12px;color:var(--muted)}}
.tag{{border:1px solid var(--line);border-radius:10px;padding:0 6px;font-size:.85em}} table{{border-collapse:collapse;width:100%}}
th,td{{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}} th{{width:28%}} .warn{{color:var(--warn)}}
pre.md{{white-space:pre-wrap;font:inherit;font-size:.92em}} .note{{border-left:3px solid var(--acc);padding-left:8px}} button{{font:inherit;padding:6px 12px}}
@media print{{nav,button{{display:none}} details{{display:block}} details>*{{display:block}}}}
</style></head><body><main>
<h1>Beurteilungsheft: Prüfauswahl {_e(sid)}</h1>
<p class=intro>Erzeugt {_e(db.now()[:16])} UTC. Enthält fremde Originaltexte und Übersetzungen (von Claude erstellt, ungeprüft): nur lokal verwenden, nicht weitergeben.
Suchhypothesen, Auswahlgründe und Ähnlichkeitswerte sind nicht enthalten. Ablauf je Paar: 1 lesen · 2 eigenes Urteil · 3 Werkzeugergebnis
und Durchsicht öffnen · 4 Werkzeug bewerten. Eingaben werden nur in diesem Browser gespeichert; mit „Antworten speichern“ als Datei sichern.</p>
<nav>Paar: {toc} <button id=save>Antworten speichern</button></nav>
{''.join(parts)}
</main><script>
const KEY='susa-sheet-{_e(sid)}';let st={{}};try{{st=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
const els=document.querySelectorAll('[data-k]');
els.forEach(el=>{{const k=el.dataset.k;if(el.type==='radio'){{el.checked=st[k]===el.value}}else if(el.type==='checkbox'){{el.checked=!!st[k]}}else{{el.value=st[k]||''}}
el.addEventListener(el.tagName==='TEXTAREA'?'input':'change',()=>{{st[k]=el.type==='checkbox'?el.checked:el.value;try{{localStorage.setItem(KEY,JSON.stringify(st))}}catch(e){{}}}})}});
document.getElementById('save').onclick=()=>{{const b=new Blob([JSON.stringify({{format:'susa-judgment-sheet/1',set_id:'{_e(sid)}',saved_at:new Date().toISOString(),answers:st}},null,1)],{{type:'application/json'}});
const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='beurteilung_{_e(sid)}.json';a.click()}};
</script></body></html>"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, "utf-8")
    return out
