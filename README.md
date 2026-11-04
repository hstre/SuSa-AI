# SuSa-AI – Argumentanalyse für Substack-Beiträge (Prototyp)

Lokales Forschungswerkzeug, das in einem Korpus von Substack-Beiträgen über Maschinengeist und KI-Bewusstsein
**begründete Erweiterungen, Einschränkungen und Widersprüche** von Argumenten auffindbar und überprüfbar machen soll.
Es zeigt zwei Originalpassagen nebeneinander, mit Kontext, Sprecherhinweisen, Suchweg und Textstatus, und lässt einen
Menschen eine Interpretation erfassen, bestätigen, korrigieren oder verwerfen.

Das Werkzeug fällt **kein Wahrheitsurteil** und behauptet keine globale Neuheit. Ein Fund bedeutet: Im angegebenen,
durchsuchten Bestand wurde unter den dokumentierten Suchwegen dieses Paar gefunden.

Grundlage ist der Bauauftrag `Claude_Uebergabe_Argumentanalyse.md` (Arbeitsfassung 1.0, 3. November 2026).
Ausgangsdaten: öffentlicher Metadatenexport von Mike Thickes Projekt
[mc-lit-review](https://github.com/Epistemic-Technology/mc-lit-review) (siehe [NOTICE.md](NOTICE.md)).

## Stand (4. November 2026, Version 0.4.1)

| Bereich | Stand |
|---|---|
| Import posts.json (4.060 Datensätze), Abgleich mit summary.json | ausgeführt, alle Kennzahlen gleich ([Bericht](docs/IMPORT_REPORT.md)) |
| CSV-Import | implementiert, mit Testdaten geprüft; kein echter CSV-Download importiert |
| Volltextabruf | 40 Pilotbeiträge abgerufen, alle `ok_full` ([Abdeckung](docs/pilot_coverage.json)) |
| Segmentierung mit exakten Ankern | 709 Einheiten, Absatzabdeckung 100 % in allen 40 Texten |
| Embeddings (bge-small-en-v1.5, ONNX, CPU) | berechnet, keine Eingabe abgeschnitten |
| Lexikalische Suche (SQLite FTS5/BM25) | aktiv |
| Kandidatensuche | 18.777 Kandidatenpaare für alle Pilot-Einheiten gespeichert |
| Oberfläche (Übersicht, Dokument, Suche, Kandidaten, Vergleich/Prüfung, Verlauf, Quellen, Export) | lauffähig, im Browser getestet |
| Modellgestützte Rekonstruktion/Vergleich/Gegenprüfung | erster begrenzter Lauf über die Claude-CLI: 17 Aufrufe an synthetischen Fällen ([Bericht](docs/MODEL_ACCEPTANCE_1.md)) |
| Abnahmefälle (DE + EN) | [Retrieval ohne Modell](docs/acceptance/v2_retrieval_ohne_modell.md), [mit Modell](docs/acceptance/v2_modell_claude_cli.md), [v1](docs/acceptance/v1_2026-11-03_ohne_modell.md) |
| Reale Prüfauswahl | 10 Pilotpaare, vollständig übersetzt (lokal, ungeprüft), Blindansicht mit freiem Urteil vor Etiketten, **noch nicht beurteilt** ([Anleitung](docs/REVIEW_SET_1.md)) |
| Echte Paare mit Modell bewertet | **keine** |
| Goldstandard, Precision/Recall, Baselines A/B/C | **ausstehend** |

Details und Befunde: [docs/PILOT_REPORT.md](docs/PILOT_REPORT.md), Änderungen: [CHANGELOG.md](CHANGELOG.md).

## Installation

Python 3.11 oder neuer.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"            # optional: ".[anthropic]" für den API-Adapter
cp config.example.toml config.toml  # optional, nur bei Abweichungen von den Defaults
```

## Startbefehle

Alle Befehle laufen im Projektverzeichnis (oder mit `--home PFAD` bzw. `SUSA_HOME`). Daten landen in `data/`,
Modelldateien in `models/`; beide sind von Git ausgeschlossen.

```bash
python -m susa import-json --download     # versionsfester posts.json-Stand laut config, mit Importbericht
python -m susa import-json --path posts.json   # alternativ lokale Kopie (summary.json im selben Ordner wird verglichen)
python -m susa import-csv machine-minds-posts.csv --filters "keine Filter, 4060 Zeilen"
python -m susa pilot-select --n 40        # geschichtete Zufallsauswahl -> pilot/pilot_list.json
python -m susa fetch --pilot              # seriell, 2 s Abstand, keine Zugangsdaten
python -m susa import-text datei.md --url https://... --source "manuell kopiert am ..."
python -m susa download-model             # bge-small-en-v1.5 (ONNX, ~133 MB, Revision fest)
python -m susa segment
python -m susa embed                      # oder --backend test-hash (Testvektoren, ohne Modell)
python -m susa candidates --pilot
python -m susa search "are self-reports comparable across model versions"
python -m susa compare <comparison_id> --dry-run   # Aufwandsschätzung ohne Aufruf
python -m susa compare <comparison_id> --adapter anthropic_api
python -m susa acceptance                 # zwölf Abnahmefälle -> docs/ACCEPTANCE_REPORT.md
python -m susa report                     # Textabdeckung der Pilotdokumente
python -m susa export ergebnisse.jsonl    # eigene Ergebnisse, ohne fremde Volltexte
python -m susa review-set import pilot/review_set_1.json   # Prüfauswahl 1 wiederherstellen
python -m susa review-set load-translations data/review/translations_rs1_de_v2.json   # lokal, nicht versioniert
python -m susa review-set verify rs-2026-11-03-20261103
python -m susa review-set export-html rs-2026-11-03-20261103 data/export/blindpruefung_rs1.html
python -m susa serve                      # Oberfläche auf http://127.0.0.1:5005
python -m pytest                          # Tests
```

## Modellzugang

Standard ist `llm.adapter = "none"`: Es werden keine Modelle aufgerufen; Import, Suche, manuelle Interpretation und
Prüfung funktionieren trotzdem. Ein Lauf ohne Modell wird als `not_run` protokolliert und nie als Ergebnis angezeigt.

| Adapter | Voraussetzung |
|---|---|
| `anthropic_api` | `pip install ".[anthropic]"`, Zugangsdaten in der Umgebung (z. B. `ANTHROPIC_API_KEY`) |
| `claude_cli` | lokal installierte Claude-Code-CLI (`claude -p`), wie im Ausgangsprojekt |
| `replay` | JSON-Datei mit vorbereiteten Antworten; nur für Tests, nie als echter Lauf markiert |

Echte Dienste laufen nur mit einem ausdrücklich angelegten **Budget**:

```bash
python -m susa budget create --label "Lauf X" --max-calls 20 --adapter claude_cli   # gibt die Budget-ID aus
python -m susa reconstruct <unit_id> --adapter claude_cli --budget <ID>
python -m susa acceptance --adapter claude_cli --budget <ID> --plan B:case10:en A:case06:de --countercheck C:case02:de
python -m susa budget status <ID>
# Paar zerlegen (Budget-Review-Komponenten), dann Argumentstufe (Prompt D) auf die gespeicherten Läufe
python -m susa br-pair <set_id> <position> --adapter claude_cli --budget <ID> --repeats 1 --no-relations
python -m susa argument <set_id> <position> --adapter claude_cli --budget <ID> --public-out docs/pairN/ARGUMENT_STAGE_RAW.md
python -m susa argument <set_id> <position> --render <run_id> [--revalidate] [--public-short …]   # Berichte neu, kein Aufruf
```

Die **Argumentstufe** (`susa/argument_stage.py`, Prompt `D_argument`) rekonstruiert Sprechhandlungen,
Begründungsketten, Bezugsfragen, den Vergleich der Schlüsse und zusätzliche Gedanken. Eingaben sind nur die
gespeicherten Passagen, Extraktionsläufe und die deterministische Ankerstruktur; es gibt keine paarspezifische
Logik. Je Lauf liegen unter `data/semantic/<set>-p<pos>/argument-<run_id>/` Eingaben, Prompt, Rohantwort,
Validierung und Ergebnis. Die Validierung prüft Schema, Anker, Seiten, Kanten, ob jedes Belegzitat im genannten
Anker steht, und gibt markerbasierte Hinweise auf Bedeutungsverstärkung (nur Hinweise). Die versionierbare Fassung
ersetzt wörtliche Quellzitate über vier Wörter durch einen Platzhalter. Der Kurzbericht nennt, wer eine Aussage
vertritt; das wird aus den Sprechakten abgeleitet, nicht aus der Passage, und ein offener Sprecher bleibt offen.

Der Claude-CLI-Adapter ruft nur bei bestätigter reiner Abo-Nutzung auf (`llm.subscription_only`, Standard an):
OAuth-Anmeldung, kein API-Schlüssel, Zusatznutzung abgeschaltet, und keine frühere Antwort im Budget mit
nutzbarer oder genutzter Zusatznutzung oder ohne Rate-Limit-Angaben. Das von der CLI ausgewiesene
`total_cost_usd` ist ein Listenpreis-Äquivalent (Rechengröße), keine Abrechnung.

Der Zähler liegt in der Datenbank (`model_calls`). Jeder Versuch, auch Fehlversuche und Wiederholungen, wird vor dem
Aufruf eingetragen und zählt. Neue Adapterinstanzen, die Oberfläche oder ein Neustart setzen ihn nicht zurück. Bei
erschöpftem Budget stoppt der Lauf. Ergebnisse, die im selben Budget schon bezahlt wurden, werden wiederverwendet.
Die Oberfläche nutzt `llm.budget_id` aus `config.toml`.

Jede Modellantwort wird auf fünf Ebenen getrennt gespeichert und angezeigt: Antwort empfangen, Schema gültig,
Belege beidseitig gefunden, Modellurteil, menschliche Prüfung. Siehe `susa/validate.py`.
Prompts liegen versioniert in `prompts/` (A Rekonstruktion, B Vergleich, C Gegenprüfung; aktuell v2; D Argumentstufe v1).

## Grenzen

- Das Embedding-Modell ist englischsprachig. Deutsch-englische Vergleiche sind nicht belastbar (Abnahmefall 3).
- Die heuristischen Hinweise (Negation, Modalität, Bedingung …) sind Wortmarker. Bei Einheiten von 150–350 Tokens
  treffen sie in den meisten Paaren an, sind dort also wenig trennscharf.
- Sprecherhinweise beruhen auf HTML-Blockzitaten und Anführungszeichen. Pull-Quotes des Autors und indirekte Rede
  werden nicht sicher erkannt.
- Die Vollständigkeitsprüfung vergleicht Wortzahlen mit den Metadaten. Sie erkennt grobe Kürzungen, beweist aber
  keine Vollständigkeit.
- Der Pilot schließt Bezahlbeiträge vorab aus. Die 100 % Verfügbarkeit gilt nur für diese Auswahl.
- Übersetzungshilfen für englische Originale sind noch nicht umgesetzt.
- Die Oberfläche hat keine Anmeldung und ist nur für den lokalen Betrieb gedacht (127.0.0.1).

## Aufbau

```
susa/importer.py   Import posts.json/CSV, Provenienz, Importbericht
susa/fetch.py      Volltextabruf, Status- und Vollständigkeitsprüfung, manueller Textimport
susa/extract.py    HTML/Markdown -> kanonischer Text mit Absatz-, Link- und Zitatankern
susa/versions.py   Textversionen (Datei + SHA-256), keine Duplikate, alte Versionen bleiben
susa/segment.py    Argumentationseinheiten (150–350 Tokens, Tokenizer des Modells), Abdeckungsprüfung
susa/embed.py      ONNX-bge-small bzw. Testvektoren, getrennte Vektorablage mit Manifest
susa/search.py     semantische + lexikalische Suche, Zufallskontrollen, Hinweise, Quellenindex
susa/llm.py        austauschbare Modelladapter, Aufruflimit
susa/analysis.py   Prompt A/B/C, deterministische Zitatprüfung, manuelle Interpretation, Reviews
susa/acceptance.py zwölf Abnahmefälle und formale Mindestabnahme
susa/export.py     JSONL-Export mit Schema- und Versionsangabe
susa/web/          Flask-Oberfläche
prompts/           versionierte Prompts
docs/              Berichte, Architekturvermerk
```

Architektur und vorbereitete Alexandria-Anbindung: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Lizenz

Code: MIT (siehe [LICENSE](LICENSE)). Fremde Daten und Texte: siehe [NOTICE.md](NOTICE.md).
