# Paar 6: nicht abgeschlossen

Stand 4. November 2026, Budget `budget-2026-11-04-68ee171e`.

- **Extraktion A** (Aufruf 40): gültig, zwischengespeichert in `data/semantic/rs-2026-11-03-20261103-p6/run-1.A.json`.
- **Extraktion B** (Aufruf 41): Die Antwort ist da, aber ungültig. Das Modell gab zuerst ein JSON mit deutschen
  Propositionen zu einem englischen Text aus (der Übersetzungsfehler aus Budget-Review §4.12). Danach korrigierte
  es sich selbst im Freitext und lieferte ein zweites JSON. Der Parser erwartet genau ein Objekt und lehnt die
  Antwort deshalb ab („Extra data“). Das ist ein Fehler der Modellausgabe, kein technischer Fehler der Pipeline.
  Der Parser wurde nicht geändert; eine Ausnahmeregel nach einem einzelnen Fall ist nicht vorgesehen.
- **Argumentstufe:** nicht ausgeführt.
- **Keine Wiederholung:** Mit den Paaren 7–10 waren 20 von 21 Aufrufen nötig. Für Paar 6 fehlen 2 (neue
  Extraktion B und Argumentstufe).
- **Fortsetzung ohne Wiederholung abgeschlossener Aufrufe:** In einem neuen Budget mit mindestens 2 Aufrufen
  ausführen:
  `python -m susa argument-batch rs-2026-11-03-20261103 6 --adapter claude_cli --budget <ID> --retry-failed`.
  Extraktion A wird dabei wiederverwendet.
