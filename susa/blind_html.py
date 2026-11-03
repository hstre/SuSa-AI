"""Lokal öffnungsfähige HTML-Fassung der Blindprüfung und Rückimport der Antworten.

Die erzeugte Datei enthält fremde Originaltexte und deren Übersetzungen. Sie ist nur für die lokale Nutzung durch
die prüfende Person gedacht: nicht veröffentlichen, nicht versionieren (Standardziel liegt unter data/).

Nicht enthalten: Suchhypothesen, Auswahlgründe, Ähnlichkeitswerte, heuristische Hinweise, Modellurteile. Diese
bleiben im Werkzeug und in pilot/review_set_*.json. Titel, Autor, Publikation, Datum und Quelle sind enthalten,
werden aber erst nach dem freien Urteil angezeigt (im Quelltext der Datei sind sie lesbar).
"""
from __future__ import annotations

import json
from pathlib import Path

from . import db
from . import review_set as rs
from .validate import RELATION_TYPES

FORMAT = "susa-blind-judgments/1"


def build_payload(cfg, conn, sid: str) -> dict:
    s = conn.execute("SELECT * FROM review_sets WHERE id=?", (sid,)).fetchone()
    items = []
    for it in rs.set_items(conn, sid):
        sides = {}
        for key, uid in (("A", it["left_unit_id"]), ("B", it["right_unit_id"])):
            v = rs.side_view(cfg, conn, uid)
            sides[key] = {"segments": [{"name": sg["name"], "text": sg["text"], "words": sg["words"],
                                        "de": sg["translation"]["text"] if sg["translation"] else None,
                                        "notes": json.loads(sg["translation"]["notes_json"] or "[]") if sg["translation"] else [],
                                        "translation_mismatch": sg["translation_mismatch"]} for sg in v["segments"]],
                          "findings": v["findings"], "meta": {k: v["meta"][k] for k in ("title", "author", "publication", "date", "url")},
                          "source_state": v["source_state"]}
            tr = next((sg["translation"] for sg in v["segments"] if sg["translation"]), None)
            if tr:
                sides[key]["translation_info"] = {"set": tr["translation_set"], "by": tr["created_by"], "at": tr["created_at"][:10],
                                                  "status": tr["review_status"]}
        items.append({"position": it["position"], "sides": sides})
    return {"format": FORMAT, "set_id": sid, "label": s["label"], "items_sha256": s["items_sha256"] or rs.items_hash(rs.set_items(conn, sid)),
            "generated_at": db.now(), "questions": rs.QUESTIONS, "verdicts": rs.VERDICTS, "flags": rs.FLAGS,
            "relation_types": RELATION_TYPES, "items": items}


def export_html(cfg, conn, sid: str, out: Path) -> str:
    data = build_payload(cfg, conn, sid)
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, "utf-8")
    return str(out)


def import_judgments(cfg, conn, data: dict) -> dict:
    """Antworten aus der HTML-Fassung übernehmen. Nur Einträge, deren Quellstand (Text- und Übersetzungs-Hashes) mit dem
    aktuellen lokalen Stand übereinstimmt; bereits importierte Einträge (client_id) werden übersprungen."""
    if data.get("format") != FORMAT:
        raise ValueError("unbekanntes Format")
    sid = data["set_id"]
    have = conn.execute("SELECT items_sha256 FROM review_sets WHERE id=?", (sid,)).fetchone()
    if have is None or (have[0] and have[0] != data["items_sha256"]):
        raise ValueError("Auswahl unbekannt oder verändert; Import abgebrochen")
    done = {json.loads(r[0] or "{}").get("_client_id") for r in conn.execute("SELECT answers_json FROM blind_judgments WHERE origin='html_import'")}
    pos_items = {it["position"]: it for it in rs.set_items(conn, sid)}
    res = {"imported": 0, "skipped_duplicate": 0, "rejected": []}
    order = {"free": 0, "labels": 1, "amendment": 1, "correction": 1, "reveal": 1}
    for e in sorted(data["entries"], key=lambda e: (e["created_at"], order.get(e["stage"], 2))):
        if e["client_id"] in done:
            res["skipped_duplicate"] += 1
            continue
        it = pos_items.get(e["position"])
        cur = {"a": rs.side_view(cfg, conn, it["left_unit_id"])["source_state"], "b": rs.side_view(cfg, conn, it["right_unit_id"])["source_state"]}
        if json.dumps(cur, sort_keys=True) != json.dumps(e["source_state"], sort_keys=True):
            res["rejected"].append({"client_id": e["client_id"], "position": e["position"], "reason": "Quellstand weicht ab (Text oder Übersetzung geändert)"})
            continue
        answers = dict(e.get("answers") or {}, _client_id=e["client_id"], _client_created_at=e["created_at"])
        try:
            rs.add_blind_judgment(cfg, conn, sid, e["position"], e["reviewer"], e["stage"], verdict=e.get("verdict"), answers=answers,
                                  relation_types=e.get("relation_types"), flags=e.get("flags"), quotes=e.get("quotes"),
                                  origin="html_import", source_state=cur)
            res["imported"] += 1
        except ValueError as ex:
            res["rejected"].append({"client_id": e["client_id"], "position": e["position"], "reason": str(ex)})
    return res


TEMPLATE = r"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blindprüfung</title>
<style>
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a65;--line:#dedbd2;--card:#fff;--accent:#2f5d8a;--warn:#9a5b00;--warnbg:#fff4e0;--bad:#a1262b;--badbg:#fde9ea;--ok:#2d6a3e;--okbg:#e6f3e9}
@media (prefers-color-scheme:dark){:root{--bg:#17181a;--fg:#e8e6e1;--muted:#a19f99;--line:#34353a;--card:#1f2023;--accent:#8fb8e3;--warn:#e6b35c;--warnbg:#3a2c12;--bad:#f08b8f;--badbg:#3b1a1c;--ok:#8fd19f;--okbg:#173022}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1200px;margin:0 auto;padding:16px}h1{font-size:21px}h2{font-size:17px;margin:18px 0 6px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:10px 0}
.banner{padding:8px 12px;border-radius:6px;margin:8px 0}.warn{background:var(--warnbg);color:var(--warn)}.bad{background:var(--badbg);color:var(--bad)}.okb{background:var(--okbg);color:var(--ok)}
table{border-collapse:collapse;width:100%}td,th{vertical-align:top;text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}th{color:var(--muted);font-size:13px}
.passage{font-family:Georgia,serif;font-size:15.5px;line-height:1.6;white-space:pre-wrap}.ctx .passage{color:var(--muted);font-size:14px}
.small{font-size:13px}.muted{color:var(--muted)}.tag{display:inline-block;padding:1px 7px;border-radius:10px;font-size:12px;border:1px solid var(--line);margin:1px 2px}
textarea,input[type=text],select{font:inherit;width:100%;padding:5px 7px;border:1px solid var(--line);border-radius:4px;background:var(--bg);color:var(--fg)}
button{font:inherit;padding:5px 12px;border-radius:5px;border:1px solid var(--accent);background:var(--accent);color:#fff;cursor:pointer;margin:4px 4px 4px 0}
button.sec{background:transparent;color:var(--accent)}nav button{min-width:36px}.cols{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media (max-width:800px){.cols{grid-template-columns:1fr}td{display:block}}
.checks{columns:2;font-size:13px}@media (max-width:600px){.checks{columns:1}}
</style></head><body><main>
<h1>Blindprüfung <span id="setlabel" class="muted small"></span></h1>
<div class="banner warn small">Lokale Datei mit fremden Originaltexten und ungeprüften Übersetzungen. Nur zur eigenen Prüfung verwenden, nicht veröffentlichen oder weitergeben.
Antworten werden nur in diesem Browser gespeichert (localStorage). Bitte regelmäßig „Antworten herunterladen“.</div>
<div class="card small">Prüfer <input type="text" id="reviewer" style="width:220px;display:inline-block">
 <button class="sec" id="dl">Antworten herunterladen (JSON)</button> <label class="sec">Antworten laden <input type="file" id="ul" accept=".json"></label>
 <span id="status" class="muted"></span></div>
<nav class="small" id="nav"></nav>
<div id="pair"></div>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const KEY = 'susa-blind:' + D.set_id + ':' + D.items_sha256;
let store = {entries: []};
try { store = JSON.parse(localStorage.getItem(KEY)) || store; } catch (e) {}
let pos = 1;
const $ = s => document.querySelector(s);
const esc = s => (s == null ? '' : String(s)).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(store)); $('#status').textContent = store.entries.length + ' Einträge gespeichert'; }
                     catch (e) { $('#status').textContent = 'Speichern im Browser nicht möglich – bitte herunterladen'; } };
const reviewer = () => $('#reviewer').value.trim();
try { $('#reviewer').value = localStorage.getItem('susa-blind-reviewer') || ''; } catch (e) {}
$('#reviewer').addEventListener('change', () => { try { localStorage.setItem('susa-blind-reviewer', reviewer()); } catch (e) {} render(); });
const mine = p => store.entries.filter(e => e.position === p && e.reviewer === reviewer());
const SEG = {before: 'Kontext davor', core: 'Kernabschnitt', after: 'Kontext danach'};
const STAGE = {free: 'Freies Urteil', labels: 'Etiketten', amendment: 'Ergänzung', correction: 'Korrektur', reveal: 'Aufgedeckt'};
function add(stage, fields) {
  const it = D.items.find(i => i.position === pos);
  const e = Object.assign({client_id: (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random()), set_id: D.set_id,
    position: pos, reviewer: reviewer(), stage, created_at: new Date().toISOString(),
    revealed_before: mine(pos).some(x => x.stage === 'reveal'),
    source_state: {a: it.sides.A.source_state, b: it.sides.B.source_state}}, fields);
  store.entries.push(Object.freeze(e)); save(); render();
}
function sideHtml(k, s) {
  let h = '<div class="card"><h2>Passage ' + k + '</h2>';
  if (s.findings.length) h += '<div class="banner warn small">Befunde zur Textauswahl: ' + esc(s.findings.join(' · ')) + '</div>';
  h += '<table><tr><th style="width:50%">Original (Englisch)</th><th>Deutsche Übersetzung <span class="tag">kein Original</span></th></tr>';
  for (const g of s.segments) { if (!g.text) continue;
    h += '<tr class="' + (g.name === 'core' ? '' : 'ctx') + '"><td><div class="small muted">' + SEG[g.name] + ' · ' + g.words + ' Wörter</div><div class="passage" lang="en">' + esc(g.text) + '</div></td><td>';
    if (g.de) { h += '<div class="passage" lang="de">' + esc(g.de) + '</div>';
      if (g.notes.length) h += '<details class="small"><summary>Übersetzungshinweise (' + g.notes.length + ')</summary>' + g.notes.map(n => '<div>• ' + esc(n) + '</div>').join('') + '</details>'; }
    else if (g.translation_mismatch) h += '<div class="banner bad small">Übersetzung gehört zu einer anderen Textfassung und wird nicht angezeigt.</div>';
    else h += '<div class="small muted">keine Übersetzung</div>';
    h += '</td></tr>'; }
  h += '</table>';
  if (s.translation_info) h += '<div class="small muted">Übersetzung: ' + esc(s.translation_info.by) + ' · ' + esc(s.translation_info.at) + ' · Prüfstatus: ' + esc(s.translation_info.status) + '</div>';
  return h + '</div>';
}
function render() {
  $('#setlabel').textContent = D.label;
  $('#nav').innerHTML = D.items.map(i => { const done = store.entries.some(e => e.position === i.position && e.reviewer === reviewer() && e.stage === 'free');
    return '<button class="' + (i.position === pos ? '' : 'sec') + '" onclick="pos=' + i.position + ';render()">' + i.position + (done ? ' ✓' : '') + '</button>'; }).join('');
  const it = D.items.find(i => i.position === pos);
  const m = mine(pos), free = m.filter(e => e.stage === 'free'), revealed = m.some(e => e.stage === 'reveal');
  let h = '<h2>Prüfpaar ' + pos + ' von ' + D.items.length + '</h2>';
  if (!free.length) h += '<div class="banner warn small">Blindansicht: Titel, Autor, Publikation, Datum und Quelle sind verborgen. Die Passagen heißen neutral A und B. Maßgeblich ist das englische Original.</div>';
  h += sideHtml('A', it.sides.A) + sideHtml('B', it.sides.B);
  if (!reviewer()) { h += '<div class="banner warn">Bitte oben einen Prüfernamen eintragen.</div>'; $('#pair').innerHTML = h; return; }
  if (!free.length) {
    h += '<div class="card"><h2>1. Freies Urteil</h2><p class="small muted">Erst in eigenen Worten, ohne Etiketten. Alle drei Gesamteinschätzungen sind gleichwertig. Das Urteil bleibt unverändert; Ergänzungen und Korrekturen sind später als neue Einträge möglich.</p>';
    h += D.questions.map((q, i) => '<label class="small"><b>' + (i + 1) + '. ' + esc(q[1]) + '</b></label><textarea id="' + q[0] + '" rows="3"></textarea>').join('');
    h += '<div class="small"><b>Gesamteinschätzung</b><br>' + Object.entries(D.verdicts).map(([k, v]) => '<label><input type="radio" name="verdict" value="' + k + '"> ' + esc(v) + '</label><br>').join('') + '</div>';
    h += '<div class="small"><b>Befunde zum Paar</b> (optional)<br>' + Object.entries(D.flags).map(([k, v]) => '<label><input type="checkbox" class="flag" value="' + k + '"> ' + esc(v) + '</label><br>').join('') + '</div>';
    h += '<div class="cols small"><div>Wörtliche Belegstellen aus A (englisch, eine pro Zeile)<textarea id="qa" rows="2"></textarea></div><div>Wörtliche Belegstellen aus B<textarea id="qb" rows="2"></textarea></div></div>';
    h += '<button id="savefree">Freies Urteil speichern</button></div>';
  } else {
    h += '<div class="card"><h2>Deine Einträge (unveränderlich)</h2>' + m.map(e => {
      let s = '<div class="small" style="border-top:1px solid var(--line);padding:6px 0"><b>' + STAGE[e.stage] + '</b> · ' + esc(e.created_at) + (e.revealed_before ? ' · <span class="tag">nach dem Aufdecken</span>' : '');
      if (e.verdict) s += '<div>Gesamteinschätzung: <b>' + esc(D.verdicts[e.verdict]) + '</b></div>';
      for (const [q, l] of D.questions) if (e.answers && e.answers[q]) s += '<div><i>' + esc(l) + '</i><br>' + esc(e.answers[q]) + '</div>';
      if (e.answers && e.answers.text) s += '<div>' + esc(e.answers.text) + '</div>';
      if (e.relation_types) s += '<div>' + (e.relation_types.length ? e.relation_types.map(t => '<span class="tag">' + esc(t) + '</span>').join('') : 'keine Etiketten') + '</div>';
      if (e.flags && e.flags.length) s += '<div>' + e.flags.map(f => '<span class="tag">' + esc(D.flags[f]) + '</span>').join('') + '</div>';
      if (e.quotes) for (const sd of ['a', 'b']) for (const q of (e.quotes[sd] || [])) s += '<div>' + sd.toUpperCase() + ': „' + esc(q) + '“ <span class="muted">(Abgleich mit dem Original erst beim Import)</span></div>';
      return s + '</div>'; }).join('') + '</div>';
    h += '<div class="cols"><div class="card"><h2>2. Optionale Beziehungsetiketten</h2><div class="checks">' + D.relation_types.map(t => '<label><input type="checkbox" class="rt" value="' + t + '"> ' + t + '</label><br>').join('') + '</div>';
    h += '<textarea id="lcomment" rows="2" placeholder="Anmerkung"></textarea><button id="savelabels">Etiketten speichern</button></div>';
    h += '<div class="card"><h2>Ergänzung oder Korrektur</h2><select id="kind"><option value="amendment">Ergänzung</option><option value="correction">Korrektur</option></select><textarea id="atext" rows="3"></textarea>';
    h += '<select id="averdict"><option value="">Gesamteinschätzung unverändert</option>' + Object.entries(D.verdicts).map(([k, v]) => '<option value="' + k + '">' + esc(v) + '</option>').join('') + '</select>';
    h += '<button id="saveamend">Als neuen Eintrag speichern</button></div></div>';
    if (!revealed) h += '<div class="card"><button class="sec" id="reveal">Quellen und Metadaten aufdecken</button> <span class="small muted">Wird protokolliert.</span></div>';
    else { h += '<div class="card"><h2>Aufgedeckt</h2><div class="cols">' + ['A', 'B'].map(k => { const mm = it.sides[k].meta;
      return '<div class="small"><b>' + k + '</b><br>Titel: ' + esc(mm.title) + '<br>Autor: ' + esc(mm.author) + '<br>Publikation: ' + esc(mm.publication) + '<br>Datum: ' + esc(mm.date) + '<br>Quelle: ' + esc(mm.url) + '</div>'; }).join('') + '</div>';
      h += '<p class="small muted">Auswahlgrund, Suchwerte und Modellurteile sind nicht in dieser Datei; sie stehen im Werkzeug.</p></div>'; }
  }
  $('#pair').innerHTML = h;
  const b = id => document.getElementById(id);
  if (b('savefree')) b('savefree').onclick = () => {
    const v = (document.querySelector('input[name=verdict]:checked') || {}).value;
    const answers = Object.fromEntries(D.questions.map(q => [q[0], b(q[0]).value.trim()]));
    if (!v) return alert('Bitte eine Gesamteinschätzung wählen.');
    if (!Object.values(answers).some(x => x)) return alert('Bitte mindestens eine Frage frei beantworten.');
    const lines = id => b(id).value.split('\n').map(x => x.trim()).filter(x => x);
    add('free', {verdict: v, answers, flags: [...document.querySelectorAll('.flag:checked')].map(x => x.value), quotes: {a: lines('qa'), b: lines('qb')}}); };
  if (b('savelabels')) b('savelabels').onclick = () => add('labels', {relation_types: [...document.querySelectorAll('.rt:checked')].map(x => x.value), answers: {comment: b('lcomment').value.trim()}});
  if (b('saveamend')) b('saveamend').onclick = () => add(b('kind').value, {answers: {text: b('atext').value.trim()}, verdict: b('kind').value === 'correction' && b('averdict').value ? b('averdict').value : null});
  if (b('reveal')) b('reveal').onclick = () => add('reveal', {});
}
$('#dl').onclick = () => { const blob = new Blob([JSON.stringify({format: D.format, set_id: D.set_id, items_sha256: D.items_sha256, exported_at: new Date().toISOString(), entries: store.entries}, null, 1)], {type: 'application/json'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'blindurteile-' + D.set_id + '-' + (reviewer() || 'ohne-name') + '.json'; a.click(); };
$('#ul').onchange = ev => { const f = ev.target.files[0]; if (!f) return; f.text().then(t => { const d = JSON.parse(t);
  if (d.set_id !== D.set_id || d.items_sha256 !== D.items_sha256) return alert('Datei gehört zu einer anderen Auswahl.');
  const ids = new Set(store.entries.map(e => e.client_id)); let n = 0; for (const e of d.entries) if (!ids.has(e.client_id)) { store.entries.push(e); n++; }
  save(); render(); alert(n + ' Einträge übernommen'); }); };
render();
</script></body></html>
"""
