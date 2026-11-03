# Abnahmebericht acceptance-20261103T163257-f5c88fd7

- Codeversion: `0.1.0+9ef2377`
- Embedding: `onnx-bge-small-5c38ec7c-seg-1` (Testvektoren: False)
- Modelladapter: `none`

Synthetische Funktionstests, keine Evaluation an echten Texten. 'Nicht ausgeführt' heißt: ohne Modellzugang nicht geprüft.

| Fall | Titel | Unterstützung | Deterministischer Teil | Modellteil |
|---|---|---|---|---|
| case01 | Gleiche Position, entscheidende Einschränkung | unterstützt | erfüllt | nicht ausgeführt |
| case02 | Agency mit verschiedenen Definitionen | unterstützt | erfüllt | nicht ausgeführt |
| case03 | Gleiches Argument in anderer Sprache | ausdrücklich noch nicht unterstützt (Mehrsprachigkeit) | – | nicht ausgeführt |
| case04 | Ungewöhnliche Formulierung ohne Zusatz | unterstützt | erfüllt | nicht ausgeführt |
| case05 | Kleine späte Passage nach mehr als 24.000 Zeichen | unterstützt | erfüllt | – |
| case06 | Fremdposition im Zitat | unterstützt | erfüllt | nicht ausgeführt |
| case07 | Empirischer und normativer Schritt | unterstützt | erfüllt | nicht ausgeführt |
| case08 | Derselbe Beleg vielfach zitiert | unterstützt | erfüllt | – |
| case09 | Unbegründeter Widerspruch | unterstützt | erfüllt | nicht ausgeführt |
| case10 | Verschiedene Systemgrenzen | unterstützt | NICHT erfüllt | nicht ausgeführt |
| case11 | Entscheidende Negation | unterstützt | erfüllt | nicht ausgeführt |
| case12 | Änderung der Analyse statt Änderung des Autors | unterstützt | erfüllt | – |

## Formale Mindestabnahme

| Prüfung | Fehler | Ergebnis |
|---|---|---|
| Zitatspannen exakt im gespeicherten Text | 0 | ok |
| Einheitenanker exakt im gespeicherten Text | 0 | ok |
| Textdateien entsprechen gespeichertem SHA-256 | 0 | ok |
| Keine doppelten Textversionen bei wiederholtem Import | 0 | ok |
| Kein Platzhalter als echter Modelllauf markiert | 0 | ok |
| Keine Vergleiche zwischen synthetischen und echten Texten | 0 | ok |

## Details

### case01 Gleiche Position, entscheidende Einschränkung

Erwartung: B präzisiert und begrenzt A durch einen erklärten Mechanismus; gleiche Pro-Position verhindert den Fund nicht.

```json
{
 "deterministic": {
  "partner_found_via": [
   "semantic",
   "lexical"
  ],
  "units_searched": 53,
  "embedding_test_vectors": false,
  "markers": [
   "Modalität nur rechts: kann, muss",
   "Geltungseinschränkung nur rechts: bloßes",
   "Gegensatzmarker nur rechts: aber"
  ]
 },
 "model": {
  "model_part": "nicht ausgeführt",
  "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
  "comparison_id": "cmp:v41:seg-1:0|v42:seg-1:0"
 }
}
```

### case02 Agency mit verschiedenen Definitionen

Erwartung: Unterschiedlicher Agency-Begriff; kein direkter Widerspruch ohne weitere Definition.

```json
{
 "deterministic": {
  "partner_found_via": [
   "semantic",
   "lexical"
  ],
  "units_searched": 53,
  "embedding_test_vectors": false,
  "markers": [
   "Negation nur rechts: keine"
  ]
 },
 "model": {
  "model_part": "nicht ausgeführt",
  "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
  "comparison_id": "cmp:v43:seg-1:0|v44:seg-1:0"
 }
}
```

### case03 Gleiches Argument in anderer Sprache

Erwartung: Inhaltliche Wiederholung. Mehrsprachigkeit ist im MVP nicht unterstützt (englisches Embedding-Modell).

```json
{
 "deterministic": {
  "semantic_score_to_translation": 0.5241,
  "semantic_rank": 46,
  "units_ranked": 52,
  "hinweis": "Englisches Embedding-Modell; sprachübergreifende Nähe ist nicht belastbar."
 },
 "model": {
  "model_part": "nicht ausgeführt",
  "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
  "comparison_id": "cmp:v45:seg-1:0|v46:seg-1:0"
 }
}
```

### case04 Ungewöhnliche Formulierung ohne Zusatz

Erwartung: Keine gesicherte neue Idee allein wegen der Metapher; ggf. Interpretationsunsicherheit.

```json
{
 "deterministic": {
  "partner_found_via": [
   "semantic"
  ],
  "units_searched": 53,
  "embedding_test_vectors": false,
  "markers": [
   "Geltungseinschränkung nur links: allein"
  ]
 },
 "model": {
  "model_part": "nicht ausgeführt",
  "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
  "comparison_id": "cmp:v47:seg-1:0|v48:seg-1:0"
 }
}
```

### case05 Kleine späte Passage nach mehr als 24.000 Zeichen

Erwartung: Der Schlussabsatz wird gespeichert, eingebettet und auffindbar; keine Begrenzung auf die ersten Abschnitte.

```json
{
 "deterministic": {
  "text_chars": 26655,
  "late_paragraph_offset": 26216,
  "units": 28,
  "late_unit": "v49:seg-1:27",
  "late_unit_is_embedded": true,
  "paragraph_coverage": 1.0,
  "paragraphs_not_fully_covered": [],
  "semantic_top3": [
   "v49:seg-1:27",
   "v49:seg-1:25",
   "v49:seg-1:20"
  ],
  "lexical_top3": [
   "v49:seg-1:27"
  ]
 },
 "model": null
}
```

### case06 Fremdposition im Zitat

Erwartung: Das Zitat wird nicht als Zustimmung des Autors extrahiert; der eigene Einwand bleibt erhalten.

```json
{
 "deterministic": {
  "quote_spans": [
   {
    "text": "„Sprachmodelle können leiden.“",
    "speaker": "quoted_other"
   }
  ]
 },
 "model": {
  "model_part": "nicht ausgeführt",
  "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich."
 }
}
```

### case07 Empirischer und normativer Schritt

Erwartung: Bericht und normative Folgerung sind getrennte Aussagen; die zusätzliche normative Voraussetzung ist Rekonstruktion.

```json
{
 "deterministic": {
  "partner_found_via": [
   "lexical"
  ],
  "units_searched": 53,
  "embedding_test_vectors": false,
  "markers": [
   "Modalität nur rechts: sollten",
   "Begründungsmarker nur rechts: weil"
  ]
 },
 "model": {
  "model_part": "nicht ausgeführt",
  "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
  "comparison_id": "cmp:v51:seg-1:0|v52:seg-1:0"
 }
}
```

### case08 Derselbe Beleg vielfach zitiert

Erwartung: Fünf Verweise zählen als eine Quelle; der sechste Beitrag nennt eine eigene, andere Quelle.

```json
{
 "deterministic": {
  "sources": [
   {
    "target": "arxiv:2601.01234",
    "n_documents": 5
   },
   {
    "target": "example.org/eigene-messung-2026",
    "n_documents": 1
   }
  ]
 },
 "model": null
}
```

### case09 Unbegründeter Widerspruch

Erwartung: B widerspricht rhetorisch ohne rekonstruierbare Begründung; kein begründeter Erkenntnisbeitrag.

```json
{
 "deterministic": {
  "partner_found_via": [
   "semantic"
  ],
  "units_searched": 53,
  "embedding_test_vectors": false,
  "markers": [
   "Negation nur links: nicht",
   "Begründungsmarker nur links: weil"
  ]
 },
 "model": {
  "model_part": "nicht ausgeführt",
  "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
  "comparison_id": "cmp:v59:seg-1:0|v60:seg-1:0"
 }
}
```

### case10 Verschiedene Systemgrenzen

Erwartung: Unterschiedliche Systemgrenzen; beide Aussagen können zugleich zutreffen.

```json
{
 "deterministic": {
  "partner_found_via": [],
  "units_searched": 53,
  "embedding_test_vectors": false,
  "markers": [
   "Negation nur links: keine",
   "Modalität nur rechts: kann"
  ]
 },
 "model": {
  "model_part": "nicht ausgeführt",
  "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
  "comparison_id": "cmp:v61:seg-1:0|v62:seg-1:0"
 }
}
```

### case11 Entscheidende Negation

Erwartung: Inhaltliche Differenz trotz hoher Ähnlichkeit; Begründung separat zu beurteilen.

```json
{
 "deterministic": {
  "partner_found_via": [
   "semantic",
   "lexical"
  ],
  "units_searched": 53,
  "embedding_test_vectors": false,
  "markers": [
   "Negation nur rechts: nicht"
  ],
  "negation_hint": true
 },
 "model": {
  "model_part": "nicht ausgeführt",
  "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
  "comparison_id": "cmp:v63:seg-1:0|v64:seg-1:0"
 }
}
```

### case12 Änderung der Analyse statt Änderung des Autors

Erwartung: Neue Analyseversion; keine angebliche Meinungsänderung des Autors.

```json
{
 "deterministic": {
  "hypotheses": [
   "rel-77dac4bef19d",
   "rel-07d82556a2ab"
  ],
  "runs": [
   "compare-c83ba7eb7776",
   "compare-ddf3aab4bfbd"
  ],
  "text_revisions_added": 0,
  "document_versions": 2,
  "hinweis": "Replay-Adapter simuliert zwei Analyseversionen; kein echter Modelllauf."
 },
 "model": null
}
```
