# Änderungsprotokoll

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
