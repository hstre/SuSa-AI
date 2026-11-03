# Architekturvermerk

## Datenfluss

```
posts.json / CSV ──► documents + upstream_codes (Fremdcodes, unveränderter Payload)
                         │
URL (/p/SLUG) ──► fetch ──► raw/<sha>.json ──► extract ──► texts/<doc>/<sha>.txt
                         │                         │
                         ▼                         ▼
                 document_versions        paragraphs, links, spans (Zeichenanker)
                         │
                         ▼
                 argument_units (seg-1) ──► units_fts (BM25)
                         │
                         ▼
                 vectors/<set>/vectors.npy + unit_ids.json + manifest.json
                         │
                         ▼
     find_candidates: semantic ∪ lexical, ≤3 je Autor, + random_control
                         │
                         ▼
     candidate_comparisons (Suchwege, Werte, Hinweise, Zeitlage, durchsuchter Bestand)
                         │
             ┌───────────┴────────────┐
             ▼                        ▼
 relation_hypotheses           relation_hypotheses
 kind=model_primary /          kind=manual
 model_countercheck (run_id)   (Autor)
             └───────────┬────────────┘
                         ▼
                 reviews (append-only, per Trigger erzwungen)
```

## Vertrauensstufen

| Stufe | Tabellen | Kennzeichnung |
|---|---|---|
| Quelldaten | documents, document_versions, paragraphs, links | Herkunft, Abrufzeit, SHA-256, Status |
| Fremdcodes | upstream_codes | Import-Lauf, Codebook-Version, „nicht neu geprüft“ |
| Maschine | claim_candidates, relation_hypotheses (model_*) | run_id → Adapter, Modell, Prompt, `is_real_model_run` |
| Mensch | relation_hypotheses (manual), reviews | Prüfer, Zeitpunkt; Reviews sind unveränderlich |
| Formale Prüfung | quote_check_json | jedes Zitat: gefunden/nicht gefunden, Position, Methode |

Formale Gültigkeit (Zitat gefunden, Schema korrekt) sagt nichts über die fachliche Tragfähigkeit.

## Versionierung

- Ein neuer Text mit anderem Hash erzeugt eine neue Version. Die alte bleibt gespeichert, wird aber nicht mehr als
  aktuell geführt. Ihre Einheiten und Analysen bleiben mit ihr verknüpft und erscheinen in der Oberfläche als
  „veraltete Textversion“.
- Ein gescheiterter Neuabruf ersetzt einen vorhandenen Text nicht.
- Segmentierung ist versioniert (`seg-1`). Bei Änderungen des Verfahrens wird `METHOD_VERSION` erhöht, statt
  verwendete Einheiten zu überschreiben.
- Prompts sind versioniert (`prompts/<name>.v<n>.txt`). Jede Interpretation verweist auf ihren Lauf. Eine geänderte
  Analyse erscheint als neue Interpretation, nicht als Meinungsänderung des Autors (Abnahmefall 12).

## Vorbereitung für Alexandria und Layer 9

Noch nicht umgesetzt. Absichtlich vorbereitet:

- Stabile Quellenanker (Version + Zeichenposition + Hash) für jede Behauptung und jedes Zitat.
- Getrennte Einträge für Behauptungskandidaten (Prompt A) und Relationshypothesen (Prompt B/C) mit Herkunft.
- Beziehungstypen als Liste. Mehrere Typen pro Paar sind möglich, Dissens bleibt über mehrere Reviews erhalten.
- JSONL-Export mit `schema: susa-export/0.1` als Übergabeformat.

Ein späterer Adapter übersetzt diese Vorschläge anhand des dann aktuellen Alexandria-Schemas
(`hstre/Alexandria-Protokoll`, `schema.py`) in Claim-Kandidaten. Der dokumentierte Weg Text → SemanticUnit →
SemanticProjection → ClaimCandidate → ClaimNode wird dabei nicht abgekürzt: SuSa-AI liefert höchstens
ClaimCandidate-Vorschläge, keine validierten oder versiegelten ClaimNodes.

Geprüft am 3. November 2026: `hstre/Alexandria-Protokoll` steht auf `45865bd585fddc6c17d8217eda34f4f1763c7b2d`
(wie im Übergabedokument). `hstre/Layer_9` enthält nur eine LICENSE-Datei (ein Commit). Für Layer 9 gibt es also
kein lesbares Schema. Die Anforderungen aus
Abschnitt 13 des Übergabedokuments (gleicher Inhalt, Präzisierung, Definitionsunterschiede, offene Einwände,
Revisionen) sind über die Relationstypen und Reviews abbildbar. Eine Graphnavigation folgt erst nach der
Pilotbewertung.
