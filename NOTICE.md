# Quellen- und Lizenzhinweise

## Metadaten und Klassifikationen: mc-lit-review (Mike Thicke)

- Projekt: https://github.com/Epistemic-Technology/mc-lit-review
- Begleitwebsite: https://machine.epistemic.technology/
- Verwendeter Stand: Commit `37f371984dda64ebbded0d3eca1bd1b61b1542c1` (beim Import am 3. November 2026 identisch mit `main`)
- Datei: `site/src/data/posts.json`, SHA-256 `86dea53453b58d6c5e8309c6350ed1f6c3545821b9e1e3a422c9965b8b4fcb3d`
- Lizenz der exportierten Daten laut README des Projekts: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Code des Projekts: MIT License, Copyright 2026 Mike Thicke. Aus dem Code wurde nichts kopiert; Abrufmuster,
  Feldbedeutungen und Statuskategorien wurden anhand des Quellcodes nachvollzogen und neu implementiert.

Änderungen gegenüber dem Original: Die Datensätze werden unverändert gespeichert und zusätzlich in eigene Tabellen
übernommen (Namensraum `upstream:mc-lit-review:post:<id>`). Die Klassifikationen werden als historische Fremdcodes
angezeigt und nicht neu bewertet. `pilot/pilot_list.json` enthält eine Auswahl dieser Metadaten (Titel, Autor,
Datum, URL, Codes).

## Artikeltexte

Volltexte stammen von den jeweiligen Substack-Autorinnen und -Autoren und unterliegen deren Rechten. Die
Projektlizenz von mc-lit-review lizenziert sie nicht weiter. SuSa-AI speichert abgerufene Texte nur lokal in `data/`
(von Git ausgeschlossen), veröffentlicht sie nicht und exportiert sie nicht. Die Oberfläche zeigt Ausschnitte mit
Herkunftsangabe zur Prüfung.

## Embedding-Modell

BAAI/bge-small-en-v1.5, Revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`, MIT License
(https://huggingface.co/BAAI/bge-small-en-v1.5). Wird bei Bedarf nach `models/` geladen, nicht mitgeliefert.

## Synthetische Testfälle

Die Texte in `susa/fixtures.py` sind neu formulierte synthetische Beispiele aus dem Übergabedokument bzw. für den
Prototyp verfasst. Sie sind keine Zitate aus dem Substack-Korpus.
