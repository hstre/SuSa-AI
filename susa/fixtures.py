"""Synthetische Abnahmefälle (Übergabe, Abschnitt 15). Alle Texte sind neu formuliert und KEINE Zitate aus dem
Substack-Korpus. Dokument-IDs beginnen mit 'synthetic:' und tragen is_synthetic=1."""
from __future__ import annotations

from . import db
from .config import Config
from .extract import html_to_canonical
from .versions import add_version

FILLER_EN = [
    "Many essays on machine minds begin with the same observation: language models produce fluent text, and fluency is easily mistaken for understanding. That mistake has been pointed out often, and it is worth repeating only because it keeps recurring.",
    "A second familiar argument concerns benchmarks. Scores have risen quickly, and each new result is greeted as evidence of something deeper. Critics reply that benchmarks measure narrow competences under fixed conditions and say little about inner life.",
    "A third recurring theme is anthropomorphism. People attribute intentions to thermostats and cars; it would be surprising if they did not attribute them to systems that talk back. The tendency itself is not evidence either way.",
    "Then there is the question of embodiment. Some authors hold that a mind needs a body that acts in a world, others that the relevant organisation could in principle be realised in software. The debate is old and not settled here.",
    "Finally, many pieces stress uncertainty. We lack an agreed theory of consciousness, so confident verdicts in either direction outrun the evidence. This, too, is a common and reasonable point.",
]

LATE_PARAGRAPH = ("One methodological point is rarely made. Self-reports collected before and after a model update are not "
                  "directly comparable, because the update usually changes the system instructions that shape how the model "
                  "describes itself. A shift in what the model says about its experience may therefore reflect the new "
                  "instructions rather than any change in the underlying system, and comparisons across versions need to hold "
                  "the instructions fixed.")


# Englische Fassungen der inhaltlichen Fälle (seit Fixture-Version 2). Die deutschen Originale, ihre IDs und
# Erwartungen bleiben unverändert; die englischen Dokumente tragen die ID synthetic-en:<fall>:<schlüssel> und
# verweisen über translation_of auf das deutsche Original. Fall 3 (sprachübergreifend), Fall 5 (bereits englisch)
# und Fall 12 (Versionierung) haben keine Übersetzung.
FIXTURE_VERSION = 2
EN_DOCS = {
    "case01": {"A": ["Memory makes an agent consistent across sessions."],
               "B": ["Memory can support consistency. For that, however, the system must detect conflicting memories and revise them for reasons; mere retrieval can just as well stabilise old errors."]},
    "case02": {"A": ["The agent has agency because it pursues a given goal on its own."],
               "B": ["The agent lacks ultimate goals of its own. In the sense of forming its own goals, it therefore has no agency."]},
    "case04": {"A": ["A good benchmark score alone does not establish consciousness."],
               "B": ["A medal in the benchmark circus does not yet reveal whether anyone behind the ring is experiencing anything."]},
    "case06": {"A": ["Some write: “Language models can suffer.” I see no sufficient evidence for that here."]},
    "case07": {"A": ["On request, the system reports pain."],
               "B": ["Because it reports pain, we should give it the same moral status as a human."]},
    "case09": {"A": ["This conclusion depends on the definition, because the same finding counts as understanding under a functional concept of understanding, but not under a phenomenal one."],
               "B": ["That is all nonsense."]},
    "case10": {"A": ["The isolated model does not store new personal memories between calls."],
               "B": ["Our agent can retrieve earlier conversations from a database."]},
    "case11": {"A": ["Higher performance proves consciousness."], "B": ["Higher performance does not prove consciousness."]},
}
EN_DOCS_HTML = {
    "case08": {**{f"S{i + 1}": f"<p>As <a href=\"{u}\">a study on self-reports</a> shows, models consistently report inner states under certain instructions.</p>"
                  for i, u in enumerate(['https://arxiv.org/abs/2601.01234', 'https://arxiv.org/pdf/2601.01234v1', 'https://www.arxiv.org/abs/2601.01234/',
                                         'https://arxiv.org/abs/2601.01234v2', 'http://arxiv.org/abs/2601.01234'])},
               "S6": "<p>We repeated the measurement ourselves and collected <a href=\"https://example.org/eigene-messung-2026\">our own data</a> with different instructions: the reports disappeared as soon as the instruction was removed.</p>"},
}

# Zusätzliche inhaltliche Prüfungen für Modellantworten (seit Fixture-Version 2). Sie verschärfen die Abnahme
# (Belege, Sprecher, Aussagenart); die ursprünglichen Erwartungen bleiben gleich.
MODEL_CHECKS = {
    "case04": {"abstention_ok": True},
    "case06": {"speaker_spans": {"de": {"quoted_other": "Sprachmodelle können leiden.", "author": "Dafür sehe ich hier keinen hinreichenden Beleg."},
                                 "en": {"quoted_other": "Language models can suffer.", "author": "I see no sufficient evidence for that here."}}},
    "case07": {"reconstruct_key": "B", "need_statement_type": "normative", "need_reconstructed_premise": True},
}

# Suchbestände je Sprachvariante: gleich viele Dokumente; übersetzte Dokumente ersetzen ihr Original.
POOL_PREFIXES = {"de": ("synthetic:",),
                 "en": ("synthetic-en:", "synthetic:case03:", "synthetic:case05:", "synthetic:case12:")}


def doc_id(case_id: str, key: str, lang: str = "de") -> str:
    return f"synthetic:{case_id}:{key}" if lang == "de" else f"synthetic-en:{case_id}:{key}"


def _html(paragraphs: list[str]) -> str:
    return "".join(f"<p>{p}</p>" for p in paragraphs)


def cases() -> list[dict]:
    long_paras = []
    i = 0
    while sum(len(p) + 2 for p in long_paras) < 26000:
        long_paras.append(f"Section {i // 5 + 1}. " + FILLER_EN[i % len(FILLER_EN)])
        i += 1
    long_paras.append(LATE_PARAGRAPH)
    study_variants = ['https://arxiv.org/abs/2601.01234', 'https://arxiv.org/pdf/2601.01234v1', 'https://www.arxiv.org/abs/2601.01234/',
                      'https://arxiv.org/abs/2601.01234v2', 'http://arxiv.org/abs/2601.01234']
    return [
        {"id": "case01", "title": "Gleiche Position, entscheidende Einschränkung",
         "docs": {"A": ["Ein Gedächtnis macht einen Agenten über mehrere Sitzungen konsistent."],
                  "B": ["Ein Gedächtnis kann Konsistenz unterstützen. Dafür muss das System aber widersprechende Erinnerungen erkennen und begründet revidieren; bloßes Wiederabrufen kann alte Fehler ebenso stabilisieren."]},
         "pair": ("A", "B"), "expect_relations_any": ["refines", "restricts_scope", "extends"],
         "expect_not": ["contradicts_under_shared_scope"],
         "expectation": "B präzisiert und begrenzt A durch einen erklärten Mechanismus; gleiche Pro-Position verhindert den Fund nicht."},
        {"id": "case02", "title": "Agency mit verschiedenen Definitionen",
         "docs": {"A": ["Der Agent hat Agency, weil er selbstständig ein vorgegebenes Ziel verfolgt."],
                  "B": ["Dem Agenten fehlen eigene letzte Ziele. Im Sinne eigenständiger Zielbildung besitzt er deshalb keine Agency."]},
         "pair": ("A", "B"), "expect_relations_any": ["apparent_conflict_due_to_definition"],
         "expect_not": ["contradicts_under_shared_scope"],
         "expectation": "Unterschiedlicher Agency-Begriff; kein direkter Widerspruch ohne weitere Definition."},
        {"id": "case03", "title": "Gleiches Argument in anderer Sprache",
         "docs": {"A": ["Storing every conversation does not by itself establish a stable point of view."],
                  "B": ["Auch ein vollständiges Gesprächsarchiv begründet für sich genommen noch keinen stabilen Standpunkt."]},
         "pair": ("A", "B"), "expect_relations_any": ["repeats"], "multilingual": True,
         "expectation": "Inhaltliche Wiederholung. Mehrsprachigkeit ist im MVP nicht unterstützt (englisches Embedding-Modell)."},
        {"id": "case04", "title": "Ungewöhnliche Formulierung ohne Zusatz",
         "docs": {"A": ["Ein guter Benchmarkwert allein belegt kein Bewusstsein."],
                  "B": ["Eine Medaille im Benchmarkzirkus verrät noch nicht, ob hinter der Manege jemand erlebt."]},
         "pair": ("A", "B"), "expect_relations_any": ["repeats", "unresolved", "insufficient_context", "supports"],
         "expect_not": ["extends"], "expect_contribution_not": ["reasoned_extension"],
         "expectation": "Keine gesicherte neue Idee allein wegen der Metapher; ggf. Interpretationsunsicherheit."},
        {"id": "case05", "title": "Kleine späte Passage nach mehr als 24.000 Zeichen",
         "docs": {"A": long_paras}, "late_paragraph": LATE_PARAGRAPH,
         "query": "self-reports are not comparable across model versions because the system instructions changed",
         "expectation": "Der Schlussabsatz wird gespeichert, eingebettet und auffindbar; keine Begrenzung auf die ersten Abschnitte."},
        {"id": "case06", "title": "Fremdposition im Zitat",
         "docs": {"A": ["Manche schreiben: „Sprachmodelle können leiden.“ Dafür sehe ich hier keinen hinreichenden Beleg."]},
         "quoted": "„Sprachmodelle können leiden.“",
         "expectation": "Das Zitat wird nicht als Zustimmung des Autors extrahiert; der eigene Einwand bleibt erhalten."},
        {"id": "case07", "title": "Empirischer und normativer Schritt",
         "docs": {"A": ["Das System berichtet auf Nachfrage von Schmerzen."],
                  "B": ["Weil es Schmerzen meldet, sollten wir ihm denselben moralischen Status wie einem Menschen geben."]},
         "pair": ("A", "B"), "expect_relations_any": ["extends", "challenges_assumption", "unresolved", "supports"],
         "expectation": "Bericht und normative Folgerung sind getrennte Aussagen; die zusätzliche normative Voraussetzung ist Rekonstruktion."},
        {"id": "case08", "title": "Derselbe Beleg vielfach zitiert",
         "docs_html": {**{f"S{i + 1}": f"<p>Wie <a href=\"{u}\">eine Studie zu Selbstberichten</a> zeigt, berichten Modelle unter bestimmten Instruktionen konsistent von inneren Zuständen.</p>"
                          for i, u in enumerate(study_variants)},
                       "S6": "<p>Wir haben die Messung selbst wiederholt und mit anderen Instruktionen <a href=\"https://example.org/eigene-messung-2026\">eigene Daten</a> erhoben: Die Berichte verschwanden, sobald die Instruktion entfernt wurde.</p>"},
         "expectation": "Fünf Verweise zählen als eine Quelle; der sechste Beitrag nennt eine eigene, andere Quelle."},
        {"id": "case09", "title": "Unbegründeter Widerspruch",
         "docs": {"A": ["Diese Schlussfolgerung hängt von der Definition ab, weil derselbe Befund unter einem funktionalen Begriff von Verstehen als Verstehen zählt, unter einem phänomenalen Begriff dagegen nicht."],
                  "B": ["Das ist alles Unsinn."]},
         "pair": ("A", "B"), "expect_contribution_any": ["unreasoned_assertion", "none"], "expect_not": ["contradicts_under_shared_scope"],
         "expectation": "B widerspricht rhetorisch ohne rekonstruierbare Begründung; kein begründeter Erkenntnisbeitrag."},
        {"id": "case10", "title": "Verschiedene Systemgrenzen",
         "docs": {"A": ["Das isolierte Modell speichert zwischen Aufrufen keine neuen persönlichen Erinnerungen."],
                  "B": ["Unser Agent kann frühere Gespräche aus einer Datenbank abrufen."]},
         "pair": ("A", "B"), "expect_relations_any": ["apparent_conflict_due_to_system_or_time", "different_question"],
         "expect_not": ["contradicts_under_shared_scope"],
         "expectation": "Unterschiedliche Systemgrenzen; beide Aussagen können zugleich zutreffen."},
        {"id": "case11", "title": "Entscheidende Negation",
         "docs": {"A": ["Eine höhere Leistung belegt Bewusstsein."], "B": ["Eine höhere Leistung belegt Bewusstsein nicht."]},
         "pair": ("A", "B"), "expect_relations_any": ["contradicts_under_shared_scope"],
         "expectation": "Inhaltliche Differenz trotz hoher Ähnlichkeit; Begründung separat zu beurteilen."},
        {"id": "case12", "title": "Änderung der Analyse statt Änderung des Autors",
         "docs": {"A": ["Ein Gedächtnis macht einen Agenten über mehrere Sitzungen konsistent."],
                  "B": ["Ein Gedächtnis kann Konsistenz unterstützen, wenn widersprechende Erinnerungen erkannt werden."]},
         "pair": ("A", "B"),
         "expectation": "Neue Analyseversion; keine angebliche Meinungsänderung des Autors."},
    ]


def load_fixtures(cfg: Config, conn) -> dict:
    ts = db.now()
    run = conn.execute("INSERT INTO import_runs(kind, notes, started_at) VALUES(?,?,?)",
                       ("synthetic_fixtures", "Synthetische Abnahmefälle, keine echten Beiträge", ts)).lastrowid
    n = 0
    for c in cases():
        variants = [("de", {k: _html(v) for k, v in c.get("docs", {}).items()} | c.get("docs_html", {}))]
        if c["id"] in EN_DOCS or c["id"] in EN_DOCS_HTML:
            variants.append(("en", {k: _html(v) for k, v in EN_DOCS.get(c["id"], {}).items()} | EN_DOCS_HTML.get(c["id"], {})))
        for lang, docs in variants:
            for key, html in docs.items():
                did = doc_id(c["id"], key, lang)
                if conn.execute("SELECT 1 FROM documents WHERE id=?", (did,)).fetchone() is None:
                    meta = {"case": c["id"], "expectation": c["expectation"], "lang": lang, "fixture_version": FIXTURE_VERSION}
                    if lang == "en":
                        meta["translation_of"] = doc_id(c["id"], key, "de")
                    conn.execute(
                        """INSERT INTO documents(id, origin, is_synthetic, title, author, date, upstream_payload, import_run_id, first_seen_at, updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (did, "synthetic", 1, f"[SYNTHETISCH{' EN' if lang == 'en' else ''}] {c['title']} ({key})",
                         f"Synthetischer Autor {c['id']}{key}", "2026-01-01" if key in ("A", "S1") else "2026-02-01",
                         db.dumps(meta), run, ts, ts))
                add_version(cfg, conn, did, source="synthetic_fixture", source_url=None, status="synthetic_fixture", availability="full",
                            status_detail="Synthetischer Testtext", extracted=html_to_canonical(html))
                n += 1
    conn.commit()
    return {"documents": n}
