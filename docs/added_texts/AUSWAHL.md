# Zusätzliche Prüftexte: Aufnahme und Auswahl der Vergleichspassagen

Festgelegt am 5. November 2026, **vor** der Argumentanalyse. Bis dahin gab es keine Modellaufrufe zu diesen Texten.

## Aufnahme

| Dokument-ID | Titel | Datum | Sprache | Textversion | Abruf |
|---|---|---|---|---|---|
| `added:steffenrentschler.substack.com:die-falsche-frage-ist-ki-bewusst` | Die falsche Frage: Ist KI bewusst? | 2026-07-14 | de | v88, sha256 `6505d226…` | Substack-API, `ok_full`, 1361 Wörter (API-Angabe 1361) |
| `added:steffenrentschler.substack.com:are-llms-conscious-or-are-we-arguing` | Are LLMs Conscious — or Are We Arguing Across Languages? | 2026-07-19 | en | v89, sha256 `18c3e04f…` | Substack-API, `ok_full`, 696 Wörter (API-Angabe 696) |

- **Kennzeichnung:** Herkunft `added_review_text`, aufgenommen mit dem neuen Befehl `susa add-url` über den
  vorhandenen Abrufweg.
- **Unverändert:** der Ausgangsdatensatz (`upstream_json`, 4060 Beiträge) und die eingefrorene Prüfauswahl
  `rs-2026-11-03-20261103`.
- **Segmentierung:** 21 bzw. 6 Einheiten mit `seg-1`.
- **Einbettung:** dieselbe Vektormenge (`onnx-bge-small-5c38ec7c-seg-1`), um 27 Vektoren ergänzt. Das Modell ist
  englischsprachig; Ähnlichkeitswerte für den deutschen Text sind deshalb nur eingeschränkt aussagekräftig.

## Warum fehlen die Texte im Ausgangsdatensatz?

Grundlage ist das Erhebungsprotokoll laut `summary.json` von mc-lit-review (Commit `37f3719`, erzeugt
2026-10-23). Die Stufen: Korpus 42.807 → Zeitraum 40.624 → Sprache 39.294 → Textkörper → Mindestlänge →
Ausschlüsse → Relevanzkodierung → 4.060 relevante Beiträge. Entdeckt wurden Beiträge über die Kanäle Brave-Suche,
Kopplung, Substack-Posts, Zitate und Archivkontext.

- **Zeitraum (2024-01-02 bis 2026-10-14):** Beide Texte liegen darin. **Das erklärt das Fehlen nicht.**
- **Deutscher Artikel:** Er wäre wahrscheinlich am Sprachfilter ausgeschieden. Der Export enthält, soweit
  erkennbar, nur englische Beiträge. Das ist eine plausible Erklärung, kein Nachweis, denn das Protokoll nennt das
  Sprachkriterium nicht im Wortlaut.
- **Englischer Artikel:** Ursache **unbekannt**. Die Publikation (ID 9899132, angelegt 2026-07-07) kommt im Export
  gar nicht vor. Weil nur die 4.060 relevanten Beiträge exportiert sind und nicht das Gesamtkorpus, lässt sich
  nicht unterscheiden, ob der Beitrag nie entdeckt oder später ausgeschlossen bzw. als nicht relevant kodiert wurde.

## Auswahl der Vergleichspassagen

- **Suchweg:** der vorhandene `find_candidates` (semantisch und lexikalisch, Autorendiversität, Zufallskontrollen)
  für alle 27 neuen Einheiten.
- **Bestand:** nur Einheiten aus dem Pilotbestand (Herkunft `upstream_json`, 40 abgerufene Pilotdokumente).
  Gegenseitige Treffer der beiden neuen Texte sind ausgeschlossen.
- **Regel**, festgelegt vor der Durchsicht der Ergebnisse:
  1. Paar 1: der Kandidat mit dem höchsten semantischen Wert zum englischen Artikel.
  2. Paar 2: der bestbewertete Kandidat zum englischen Artikel aus einem Dokument, das im Ausgangsdatensatz eine
     andere Haltung zur Erlebensfrage trägt (`experience_now = no` statt `unsure`).
  3. Paar 3: der Kandidat mit dem höchsten semantischen Wert zum deutschen Artikel.

| Paar | Eigener Text (Einheit) | Vergleichspassage | Suchwert | Ausgangskodierung der Vergleichsquelle |
|---|---|---|---|---|
| R1 | EN, `v89:seg-1:3` | „Clarity Around AI Consciousness“, `v4:seg-1:15` | semantisch 0,846 (Rang 1 von 584) | experience_now unsure |
| R2 | EN, `v89:seg-1:3` | „The Soul Doesn't Pop In“, `v27:seg-1:6` | semantisch 0,811 | experience_now no (Chinesisches Zimmer, biologisches Argument) |
| R3 | DE, `v88:seg-1:15` | „Letter 13A: They Want To Prevent What We’re Becoming“, `v37:seg-1:6` | semantisch 0,760 (bester Wert des deutschen Texts) | experience_now discussed, agency asserts |

Anmerkungen:

- Die Vergleichsquelle von R1 ist dasselbe Dokument wie Seite A von Paar 5 der Prüfauswahl (anderer Abschnitt).
- Bei R3 liegt der Treffer vermutlich am gemeinsamen Wort „Framework“, das in beiden Texten etwas anderes
  bezeichnet. Ich lasse ihn regelgemäß stehen, weil die Suche selbst geprüft werden soll.
- Die eigene Einheit von R1 und R2 ist dieselbe. Ihre Extraktion wird aus R1 übernommen (gleiche Textfassung).

## Modelleingaben

Wie in der Prüfauswahl: Budget-Review-Extraktionsprompt und Prompt `D_argument.v1`, beide unverändert. Eingabe
sind nur die Passagen mit Kontext und deren Extraktion. Bisherige Zusammenfassungen, erwartete Ergebnisse und
dieser Arbeitsauftrag gehen nicht ein.

Höchstens 10 Aufrufe: 5 Extraktionen und 3 Argumentläufe, also 8 erwartet, dazu 2 als Reserve.
