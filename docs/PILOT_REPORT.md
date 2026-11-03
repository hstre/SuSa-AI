# Pilotbericht (Arbeitsstand 3. November 2026)

Dieser Bericht beschreibt, was tatsächlich ausgeführt wurde. Er enthält **keine** Bewertung der Interpretationsqualität:
Es gab noch keinen Modelllauf und keinen Goldstandard.

## 1 Ausgeführt

### Metadatenimport

- Quelle: `posts.json` am Commit `37f371984dda…` (zum Abrufzeitpunkt identisch mit `main`), SHA-256 `86dea534…`.
- 4.060 Datensätze, 4.060 eindeutige IDs, keine doppelten URLs, 2.278 Autorennamen, 2.303 Publikationen.
- Alle verglichenen Kennzahlen aus `summary.json` stimmen überein (Anzahl, Publikationen, Datumsbereich, Genres,
  Relevanzstufen). Die Codebook-Version (0.4.1) steht nur in `summary.json`, nicht in den einzelnen Datensätzen.
- Bericht mit Feldinventar: [IMPORT_REPORT.md](IMPORT_REPORT.md).

### Pilotauswahl

- Grundgesamtheit für die Auswahl: 2.968 Beiträge (nicht als bezahlt markiert, Genre `essay`, 400–6.000 Wörter laut Upstream).
- Geschichtete Zufallsauswahl (Seed 20261103) über Gruppe × `experience_now` × Jahr, höchstens ein Beitrag je Autor.
- Ergebnis: 40 Beiträge. Gruppen: ai_field 13, general 8, journalism 7, religion 6, academic 6.
  `experience_now`: no 10, not_addressed 9, unsure 8, discussed 7, yes 6. Jahre: 2026 17, 2025 13, 2024 10.
- Keine gezielt ausgewählten Fälle. Liste: [`pilot/pilot_list.json`](../pilot/pilot_list.json).
- Die Auswahl ist eine Arbeitsgröße, keine repräsentative Stichprobe.

### Volltextabruf

- 40 Anfragen, seriell, 2 s Mindestabstand, ohne Zugangsdaten.
- Status: 40 × `ok_full`. Verhältnis extrahierter Wörter zur Wortzahl der API/Upstream-Metadaten: 0,98 bis 1,14.
- Einschränkung: Bezahlbeiträge waren vorab ausgeschlossen, und Wortzahlvergleiche erkennen nur grobe Kürzungen. Die
  100 % lassen sich daher nicht auf das Gesamtkorpus übertragen; laut `summary.json` sind 44 relevante Beiträge als
  bezahlt markiert. Paywall-, Fehler- und Teilstatus sind implementiert und getestet, kamen im Pilot aber nicht vor.
- Pro Text gespeichert: Rohantwort mit Hash, kanonischer Text mit Hash, Abrufzeit, Status, Detail.
  Siehe [pilot_coverage.json](pilot_coverage.json).

### Segmentierung

- 709 Argumentationseinheiten (seg-1), Tokens laut bge-Tokenizer: Minimum 10, Median 174, Maximum 349.
- Absatzabdeckung (Nicht-Leerzeichen inhaltlicher Absätze): 100 % in allen 40 Texten. Keine Begrenzung auf die
  ersten Abschnitte. Der längste Pilottext hat 5.451 Wörter.
- Drei Einheiten haben weniger als 50 Tokens. Das sind kurze Absätze vor sehr langen Absätzen; sie bleiben als eigene
  Einheit auffindbar.
- Überschriften können innerhalb einer Einheit stehen, wenn der vorherige Teil sehr kurz ist. Das ist sichtbar,
  aber nicht ideal.

### Embeddings und Suche

- bge-small-en-v1.5 (ONNX, CPU), CLS-Pooling, L2-normalisiert. 709 Vektoren in 41 s, keine Eingabe abgeschnitten.
- Kandidatensuche für alle 709 Einheiten: 18.777 Paare.

| Suchweg | Paare |
|---|---|
| nur semantisch | 7.914 |
| nur lexikalisch | 8.423 |
| beide | 1.022 |
| Zufallskontrolle | 1.418 |

- Semantischer und lexikalischer Weg überschneiden sich nur in etwa 5 % der Paare. Beide Wege liefern also
  weitgehend verschiedene Kandidaten. Welcher Weg die relevanten Paare findet, ist ohne Goldstandard offen.
- Kein Paar stammt vom selben Autor (Pilot: ein Beitrag je Autor).
- Zeitliche Lage: rechts später 10.331, rechts früher 8.395, gleiches Datum 51.

### Heuristische Unterschiedshinweise

Bei Einheiten von 150–350 Tokens tritt fast jeder Markertyp in fast jedem Paar auf einer Seite auf
(z. B. Gegensatzmarker 8.807, Negation 6.718 von 18.777). In dieser Form sind die Hinweise für lange Einheiten
**nicht trennscharf**. Bei kurzen Passagen (Fall 11) zeigen sie die entscheidende Negation korrekt an. Mögliche nächste
Schritte: Hinweise auf Satzebene berechnen oder nur bei hoher Ähnlichkeit anzeigen.

### Quellenindex

- 430 Links in den 40 Texten. Vier Ziele werden von genau zwei Beiträgen zitiert.
- Fehler gefunden und behoben: In der ersten Fassung entfernte die Normalisierung alle Query-Parameter. Dadurch
  verschmolzen sieben verschiedene YouTube-Videos zu einer „Quelle“. Jetzt bleiben Query-Parameter erhalten,
  nur Tracking-Parameter werden entfernt, und YouTube-IDs werden normalisiert. Ein Test deckt das ab.

### Oberfläche

Im Browser (Playwright) geprüft: Übersicht mit Filtern, Dokumentansicht mit Ankern, Einheit/Kandidaten,
Vergleichsansicht mit Kontext, Modellvergleich ohne Adapter (wird als `not_run` protokolliert), manuelle
Interpretation mit Zitatprüfung (echtes Zitat gefunden mit Position, erfundenes Zitat als „nicht gefunden“ markiert),
Prüfentscheidung, Verlauf, Quellen, JSONL-Export. Testeinträge wurden danach aus der lokalen Datenbank entfernt.

## 2 Abnahmefälle

Stand v1 (ohne Modell), archiviert unter [acceptance/v1_2026-11-03_ohne_modell.md](acceptance/v1_2026-11-03_ohne_modell.md). Neuere Ergebnisse mit englischen Fassungen und erstem Modelllauf: [MODEL_ACCEPTANCE_1.md](MODEL_ACCEPTANCE_1.md). Kurzfassung v1:

| Fall | Deterministisch geprüft | Modellteil |
|---|---|---|
| 1, 2, 4, 7, 9, 11 | Partnerpassage über Suchwege gefunden; Fall 11 zusätzlich Negationshinweis | nicht ausgeführt |
| 3 Mehrsprachigkeit | ausdrücklich nicht unterstützt: Übersetzung semantisch nur auf Rang 46 von 52 | nicht ausgeführt |
| 5 späte Passage | Absatz bei Zeichen 26.216 gespeichert, eingebettet, Rang 1 semantisch und lexikalisch | – |
| 6 Fremdzitat | Inline-Zitat als `quoted_other` markiert | nicht ausgeführt |
| 8 Mehrfachzitat | fünf URL-Varianten als eine Quelle erkannt, eigene Quelle getrennt | – |
| 10 Systemgrenzen | **nicht erfüllt**: Partnerpassage über keinen Suchweg gefunden (kein gemeinsames Vokabular, deutsche Texte mit englischem Modell) | nicht ausgeführt |
| 12 Analyseversion | zwei Interpretationen mit getrennten Läufen, keine Textrevision (Replay-Adapter, kein echter Modelllauf) | – |

Formale Mindestabnahme: alle sechs Prüfungen ohne Fehler. Die synthetischen Fälle sind Funktionstests, keine Evaluation.

## 3 Nicht ausgeführt / offen

1. **Modellläufe für echte Paare.** Synthetische Fälle: erster Lauf am 3.11.2026, siehe [MODEL_ACCEPTANCE_1.md](MODEL_ACCEPTANCE_1.md). Früherer Stand: Prompt A/B/C für synthetische und echte Paare offen. Adapter `anthropic_api` und `claude_cli` sind
   implementiert, aber ungetestet gegen einen echten Dienst. Ohne Läufe gibt es keine Aussage zur Interpretationsqualität.
2. **Goldstandard**: Auswahl von Pilotpaaren durch Steffen (und ggf. eine zweite Person), getrennt in Entwicklungs-
   und zurückgehaltenen Prüfbestand.
3. **Metriken**: Recall der Suchwege an Goldpaaren, Precision der Erweiterungs-/Widerspruchsvorschläge, Verwechslung
   Autor/Zitat und Definition/Sachgegensatz, Anteil insufficient_context, Kosten und Latenz.
4. **Baselines** A (Dokumentvektoren), B (Abschnittsvektoren allein) gegen C (Abschnitt + lexikalisch + Vergleich).
   Die Dokumentbaseline wäre eine eigene, keine nachgebildete Upstream-Baseline (Upstream-Chunking 2.000 Zeichen,
   12 Abschnitte, Mittelung ist nicht reproduziert).
5. Übersetzungshilfen, Mehrsprachigkeit, Alexandria-Adapter.

## 4 Kosten

Bisher keine Modellkosten. Abruf: 40 HTTP-Anfragen. Embeddings lokal auf CPU.
Für einen Vergleichslauf liefert `python -m susa compare <ids> --dry-run` eine grobe Tokenschätzung (Zeichen/4).
