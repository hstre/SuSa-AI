# Reale Prüfauswahl 1: Blindbeurteilung

Zehn echte Textpaare aus dem Pilot. Für keines der Paare gibt es ein Modellurteil; beim Öffnen oder Speichern wird
kein Modell aufgerufen.

## Was die Auswahl leisten kann

Die Paare stammen aus den 18.777 bereits gefundenen Kandidaten. Sie können die Qualität dieser Kandidaten untersuchen
und später menschliche mit maschinellen Rekonstruktionen vergleichen. Sie können **nicht** messen, welche relevanten
Paare die Suche ganz verpasst.

## Ablauf

1. **Freies Urteil** zu sechs Fragen in eigenen Worten: Was behauptet A? Was behauptet B? Dieselbe Frage, dasselbe
   System? Welcher zusätzliche Gedanke? Welche Textstellen? Fehlt Kontext? Dazu eine von drei gleichwertigen
   Gesamteinschätzungen: *relevanter Unterschied*, *kein relevanter Unterschied*, *nicht entscheidbar*.
   Optional kommen Befunde dazu (Kontext reicht nicht, Paar ungeeignet, Übersetzungsproblem) sowie wörtliche
   Belegstellen aus dem englischen Original. Diese werden gegen den Text geprüft.
2. Erst danach: **optionale Beziehungsetiketten**, **Ergänzungen** und **Korrekturen**, jeweils als neuer Eintrag.
   Das freie Urteil bleibt unverändert; die Datenbank verhindert Änderungen und Löschungen.
3. **Aufdecken** auf Knopfdruck: Titel, Autor, Publikation, Datum, Quelle, Reaktionszahlen, historische
   Positionscodes, Suchhypothese, Auswahlgrund, Suchwerte, heuristische Hinweise, archivierte Lesehilfen und
   gegebenenfalls Modellurteile. Das Aufdecken wird protokolliert; spätere Etiketten sind als „nach dem Aufdecken“
   markiert.

Bis zum ersten Urteil heißen die Passagen nur A und B.

## Texte und Übersetzungen

Je Seite werden Kontext davor, Kernabschnitt und Kontext danach angezeigt, jeweils englisches Original und deutsche
Übersetzung nebeneinander.

- **Übersetzungssatz `tr-rs1-de-v2`:** möglichst getreue Übersetzung aller 60 Segmente (5.225 Wörter). Erstellt
  direkt von Claude in der Claude-Code-Sitzung vom 3. November 2026, ohne externen Modelllauf. Prüfstatus:
  **ungeprüft**. Mehrdeutigkeiten, Sprecherwechsel, Textlücken und Extraktionsfehler stehen in getrennten
  Übersetzungshinweisen.
- `tr-rs1-de-v1` ist archiviert. v2 ersetzt geschlechtsspezifische Formen, die nicht im Original standen,
  durch neutrale.
- Jede Übersetzung ist an Dokument, Textversions-Hash, Zeichenbereich und den Hash des übersetzten Segments gebunden.
  Weicht der Text ab, wird die Übersetzung nicht angezeigt; stattdessen erscheint ein Hinweis.
- Die früheren sinngemäßen Lesehilfen (`pilot/reading_aids_rs1.json`) bleiben archiviert und erscheinen erst nach
  dem Aufdecken. Sie fassen zusammen und könnten das Urteil vorwegnehmen. Teilweise schreiben sie den Personen
  ohne Grundlage ein Geschlecht zu.
- **Übersetzungen und Originaltexte bleiben lokal** (`data/review/`, von Git ausgeschlossen). Sie werden nicht
  veröffentlicht.

## Befunde zur Auswahl (bleiben sichtbar, nichts wurde ausgetauscht)

- Bei 13 von 20 Seiten ist der Kontext davor oder danach kürzer als 15 Wörter, meist nur eine Zwischenüberschrift.
- Drei Seiten enthalten im Original als Blockzitat formatierte Absätze (Sprecherwechsel möglich).
- Paar 9, Seite B: Eine Bildunterschrift im Kontext nennt den Namen der verfassenden Person. Paar 8, Seite B: Der
  Text nennt den Namen der Newsletter-Reihe. Das Original wird dafür nicht verändert. Die automatische Erkennung
  findet nur den ersten Fall, weil der Newsletter-Name nicht dem hinterlegten Publikationsnamen entspricht.
- Paar 9, Seite A: Ein eingebetteter Beitrag nach einem Doppelpunkt fehlt in der Textextraktion.
- Ein Kernabschnitt endet mit einem Abonnement-Hinweis der Publikation.

Ein späterer Austausch von Paaren braucht eine neue Auswahlversion (`review-set create --set-id … --supersedes
rs-2026-11-03-20261103 --reason "…"`). Die Auswahl ist über `items_sha256` festgeschrieben
(`eb4f480ce0a2…`, auch in `pilot/review_set_1.json`).

## Start im Werkzeug

```bash
python -m susa serve
# Browser: http://127.0.0.1:5005/review-sets/rs-2026-11-03-20261103/1?reviewer=Steffen
```

Nach einem Neuaufbau (Pilottexte abgerufen und segmentiert):

```bash
python -m susa review-set import pilot/review_set_1.json
python -m susa review-set load-translations data/review/translations_rs1_de_v2.json
python -m susa review-set verify rs-2026-11-03-20261103
```

## Start ohne laufendes Werkzeug (HTML-Fassung)

`python -m susa review-set export-html rs-2026-11-03-20261103 data/export/blindpruefung_rs1.html` erzeugt eine
eigenständige Datei ohne Netzzugriff. Antworten werden im Browser gespeichert und lassen sich als JSON
herunterladen. Später übernimmt `python -m susa review-set import-judgments <datei.json>` sie ins Werkzeug. Einträge,
deren Text- oder Übersetzungsstand abweicht, werden dabei abgelehnt.

Die HTML-Datei enthält fremde Texte und Übersetzungen: nicht veröffentlichen oder weitergeben. Sie enthält keine
Suchhypothesen, Suchwerte oder Modellurteile. Titel, Autor, Publikation, Datum und Quelle sind enthalten und werden
erst nach dem freien Urteil angezeigt; im Quelltext der Datei sind sie lesbar.

Die Zuordnung der Suchhypothesen steht in [`pilot/review_set_1.json`](../pilot/review_set_1.json). **Vor der
Blindbeurteilung nicht öffnen.**
