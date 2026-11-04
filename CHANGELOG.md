# Änderungsprotokoll

## 0.4.0 – 4. November 2026 (Argumentstufe)

- **Argumentstufe** als wiederverwendbare, werkzeugseitig ausgeführte Stufe (`susa/argument_stage.py`, Prompt
  `D_argument.v1`, Befehl `susa argument`). Eingaben: gespeicherte Passagen, Extraktionsläufe und Ankerstruktur.
  Gespeichert werden Promptversion, Eingaben mit Hash, Rohantwort, Validierung und Ergebnis. Übernommene
  Modellausgaben, deterministische Ableitungen und die neue Interpretation bleiben getrennt.
- **Validierung:** Schema und Wertelisten, bekannte Anker und Kanten, Anker der richtigen Passage, Belegzitat
  wörtlich im genannten Anker (Budget-Review `anchor_spans`), Hinweise auf Bedeutungsverstärkung (Marker),
  Schlüsse nur aus Kontext, Frage oder Überschrift als Grund, Konsistenz der Bezugsfragen.
- **Claude-CLI-Adapter:** Erreicht die Ausgabe die Grenze, setzt die CLI in einem zweiten Zug fort und liefert nur
  dessen Text. Solche Antworten werden jetzt als `output_split` markiert und nicht weiterverarbeitet.
- `br-pair --no-relations` lässt die Relationsstufe aus.
- Paar 1: Referenzanalyse v2 korrigiert („nicht allein auf Berechnung reduzierbar“ statt „Nicht-Berechenbarkeit“),
  v1 bleibt erhalten. Paar 1 ist nachbearbeitete Referenz, kein Gold.
- Paar 2: erste Anwendung, unbearbeitetes Ergebnis (`docs/pair2/ARGUMENT_STAGE_RAW.md`) und getrennte
  Prüfnotizen (`docs/pair2/REVIEW_NOTES.md`).

## 0.3.0 – 3./4. November 2026 (Blindbeurteilung vorbereitet)

- **Vollständige Übersetzungen** statt Zusammenfassungen: Kontext davor, Kern und Kontext danach, getreu übersetzt,
  mit getrennten Übersetzungshinweisen. Verankert an Dokument, Textversions-Hash, Zeichenbereich und Segment-Hash
  (Tabelle `translations`). Bei abweichendem Hash wird nichts angezeigt. Die Übersetzungen bleiben lokal
  (`data/review/`). Version v2 ersetzt v1 (neutrale Formen statt erschlossenem Geschlecht).
- **Freies Urteil vor Etiketten:** sechs offene Fragen und drei gleichwertige Gesamteinschätzungen. Etiketten,
  Ergänzungen, Korrekturen und das Aufdecken sind jeweils neue Einträge in `blind_judgments` (append-only, per
  Trigger erzwungen). Gespeichert wird auch der Quellstand (Text- und Übersetzungs-Hashes) zum Urteilszeitpunkt.
- **Blindheit:** Bis zum ersten Urteil sind Titel, Autor, Publikation, Datum, Quelle, Reaktionszahlen, historische
  Codes, Suchhypothese, Suchwerte, Hinweise, Lesehilfen und Modellurteile verborgen; die Seiten heißen A und B.
  Die Blindansicht erzeugt keinen Modelladapter (per Test abgesichert). Autoren- und Publikationsnamen im
  Originaltext selbst werden als Befund gemeldet, nicht entfernt.
- **Auswahl eingefroren:** `items_sha256`, Versionen mit `supersedes` und Pflichtbegründung. Eine bestehende
  Auswahl wird nie überschrieben. `review-set verify` prüft Anker, Textversionen und Übersetzungen.
- **HTML-Fassung** (`review-set export-html`) für die lokale Nutzung ohne laufendes Werkzeug, mit
  Rückimport (`review-set import-judgments`); der Quellstand wird dabei abgeglichen.
- **Berichte:** Neubewertung der Modellabnahme mit getrennten Ebenen, Korrekturen durch Gegenprüfung und
  zusätzlichen Typen; Fall 10 enger formuliert; die Grenze der Prüfauswahl (kein Recall) ist festgehalten.
- Kleinere Korrekturen: Leere Kontextsegmente werden nicht als fehlende Übersetzung gezählt. `connect()` schreibt
  die Schemaversion nur noch bei Änderung.

## 0.2.0 – 3. November 2026 (Modellabnahme)

### Behobene Fehler

1. **Aufrufbudget umgehbar.** Der Zähler lag im Adapterobjekt; jede neue Instanz (Abnahmesuite, Oberfläche, Neustart)
   begann bei null. Jetzt gibt es ausdrücklich angelegte Budgets (`model_budgets`). Jeder Aufrufversuch wird vor dem
   Aufruf atomar in `model_calls` eingetragen (`BEGIN IMMEDIATE`) und zählt, auch Fehlversuche und Wiederholungen.
   Abgelehnte Versuche werden als `refused_budget` protokolliert. Echte Dienste laufen nur mit Budget. Die internen
   SDK-Wiederholungen des API-Adapters sind abgeschaltet, damit jede Wiederholung über das Budget läuft. Bei
   erschöpftem Budget stoppt der Lauf; es wird kein neues Budget angelegt.
2. **Belegprüfung zu schwach.** Ein gefundenes Zitat auf einer beliebigen Seite ergab `ok`. Jetzt braucht eine belegte
   Beziehung mindestens ein gefundenes Zitat auf jeder Seite. Jedes angegebene Zitat muss auffindbar sein, und zwar in
   der Passage der jeweiligen Seite.
3. **Keine Schemaprüfung.** Fehlende Felder galten als leere Ergebnisse, unbekannte Beziehungstypen wurden still
   verworfen. Jetzt prüft `susa/validate.py` Pflichtfelder, Typen und zulässige Werte für Prompt A, B und C. Unbekannte
   Beziehungstypen sind ein Schemafehler und bleiben sichtbar.
4. **Prüfebenen vermischt.** Gespeichert werden jetzt getrennt: `response_status`, `schema_status`
   (+ `schema_errors_json`), `anchor_status`, `judgment` (Modellurteil) und daraus abgeleitet `evidence_status`
   (`anchored`, `abstention`, `anchors_failed`, `schema_invalid`, `no_response`). Menschliche Prüfung steht weiter
   nur in `reviews`.
5. **Gegenprüfung ohne Belege galt als Bestätigung.** `confirmed` zählt nur als belegte Bestätigung, wenn die
   Gegenprüfung selbst beidseitig belegt ist und die geprüfte Interpretation ihre Belegprüfung bestanden hat.
6. **Begründete Enthaltung.** `insufficient_context`/`unresolved` (bzw. `undecidable`) ist zulässig und wird als
   `abstention` gespeichert. Das ist kein belegter Befund.
7. **Falsch positive Abnahme beim Sprecher-Test.** Eine leere Behauptungsliste konnte bestehen. Jetzt wird positiv
   geprüft, dass ein Beleg im Fremdzitat einer `quoted_other`-Behauptung und ein Beleg im eigenen Einwand einer
   `author`-Behauptung zugeordnet ist, und dass keine `author`-Behauptung nur auf dem Fremdzitat beruht.
8. **Retrieval-Abnahme las alte Suchläufe mit.** `candidate_comparisons` vereinigt Suchwege über Läufe hinweg; die
   Abnahme wertete diese Vereinigung aus. Jetzt zählen nur die Suchwege des aktuellen Laufs (`this_run`).
9. **Lauf-IDs kollidierten** bei Läufen innerhalb derselben Sekunde (bereits in 0.1.0 behoben, hier erwähnt, weil
   die Abnahme mehrere Läufe pro Sekunde erzeugt).

### Begründete Änderungen an Abnahme und Prompts

- **Prompts v2** (A, B, C): Es kommen nur Formatregeln hinzu (alle Felder angeben, wörtliche Zitate, Belege auf beiden
  Seiten, zulässige Enthaltung). Die inhaltlichen Anweisungen sind unverändert. v1 lief nie gegen ein Modell und
  bleibt im Repository.
- **Fixtures v2:** Englische Fassungen der Fälle 1, 2, 4, 6, 7, 8, 9, 10, 11 als `synthetic-en:<fall>:<schlüssel>`
  mit `translation_of`. Deutsche IDs, Texte und Erwartungen sind unverändert. Fall 3 bleibt sprachübergreifend,
  Fall 5 war schon englisch, Fall 12 betrifft nur die Versionierung.
- **Suchbestände je Sprache:** Deutsche Fälle durchsuchen denselben Bestand wie in v1 (`synthetic:`). Englische Fälle
  durchsuchen einen gleich großen Bestand, in dem jedes übersetzte Dokument sein Original ersetzt. Suchparameter
  (k=15/15, höchstens 3 je Autor, 2 Zufallskontrollen) sind unverändert.
- **Zusätzliche Modellprüfungen** (`MODEL_CHECKS`): Fall 4 lässt Enthaltung zu, weil die Erwartung ausdrücklich
  „Interpretationsunsicherheit“ nennt. Fall 6 prüft die Sprecherzuordnung, Fall 7 Aussagenart und rekonstruierte
  Voraussetzung.

Frühere Ergebnisse: [docs/acceptance/v1_2026-11-03_ohne_modell.md](docs/acceptance/v1_2026-11-03_ohne_modell.md).

### Neu

- Reale Prüfauswahl (`susa review-set`) mit Blindansicht und getrennten deutschen Lesehilfen.
- Budgetansicht in der Oberfläche.

## 0.1.0 – 3. November 2026

Erster Prototyp (Import, Volltexte, Segmentierung, Suche, Prüfoberfläche, Abnahme ohne Modell).
