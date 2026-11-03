# Abnahmebericht acceptance-20261103T175310-7ddd457e

- Codeversion: `0.1.0+bc0acef.dirty`
- Embedding: `onnx-bge-small-5c38ec7c-seg-1` (Testvektoren: False)
- Modelladapter: `none`



Ergebnisarten: bestanden, gescheitert, unentscheidbar (z. B. begründete Enthaltung), nicht ausgeführt, nicht unterstützt.
Spalte „Lauf“: echt = echter Modelldienst, replay = Funktionstest mit vorbereiteten Antworten.

| Fall | Sprache | Teil | Ergebnis | Lauf | Kurzbefund |
|---|---|---|---|---|---|
| case01 | de | Modell B | nicht ausgeführt | kein Modell | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case01 | de | Retrieval | bestanden | – | Suchwege ['semantic', 'lexical'], semantischer Rang 4/53 |
| case01 | en | Modell B | nicht ausgeführt | kein Modell | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case01 | en | Retrieval | bestanden | – | Suchwege ['semantic', 'lexical'], semantischer Rang 1/53 |
| case02 | de | Modell B | nicht ausgeführt | kein Modell | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case02 | de | Retrieval | bestanden | – | Suchwege ['semantic', 'lexical'], semantischer Rang 1/53 |
| case02 | en | Modell B | nicht ausgeführt | kein Modell | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case02 | en | Retrieval | bestanden | – | Suchwege ['semantic', 'lexical'], semantischer Rang 1/53 |
| case03 | de+en | Modell B | nicht ausgeführt | kein Modell | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case03 | de+en | Retrieval | nicht unterstützt | – |  |
| case04 | de | Modell B | nicht ausgeführt | kein Modell | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case04 | de | Retrieval | bestanden | – | Suchwege ['semantic'], semantischer Rang 1/53 |
| case04 | en | Modell B | nicht ausgeführt | kein Modell | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case04 | en | Retrieval | bestanden | – | Suchwege ['semantic', 'lexical'], semantischer Rang 8/53 |
| case05 | en | Retrieval | bestanden | – |  |
| case06 | de | Modell A | nicht ausgeführt | – | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case06 | de | Zitat-Heuristik | bestanden | – |  |
| case06 | en | Modell A | nicht ausgeführt | – | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case06 | en | Zitat-Heuristik | bestanden | – |  |
| case07 | de | Modell A | nicht ausgeführt | – | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case07 | de | Modell B | nicht ausgeführt | kein Modell | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case07 | de | Retrieval | bestanden | – | Suchwege ['lexical'], semantischer Rang 16/53 |
| case07 | en | Modell A | nicht ausgeführt | – | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case07 | en | Modell B | nicht ausgeführt | kein Modell | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case07 | en | Retrieval | bestanden | – | Suchwege ['semantic', 'lexical'], semantischer Rang 1/53 |
| case08 | de | Quellenindex | bestanden | – |  |
| case08 | en | Quellenindex | bestanden | – |  |
| case09 | de | Modell B | nicht ausgeführt | kein Modell | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case09 | de | Retrieval | bestanden | – | Suchwege ['semantic'], semantischer Rang 14/53 |
| case09 | en | Modell B | nicht ausgeführt | kein Modell | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case09 | en | Retrieval | gescheitert | – | Suchwege –, semantischer Rang 50/53 |
| case10 | de | Modell B | nicht ausgeführt | kein Modell | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case10 | de | Retrieval | gescheitert | – | Suchwege –, semantischer Rang 23/53 |
| case10 | en | Modell B | nicht ausgeführt | kein Modell | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case10 | en | Retrieval | gescheitert | – | Suchwege –, semantischer Rang 23/53 |
| case11 | de | Modell B | nicht ausgeführt | kein Modell | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case11 | de | Retrieval | bestanden | – | Suchwege ['semantic', 'lexical'], semantischer Rang 1/53 |
| case11 | en | Modell B | nicht ausgeführt | kein Modell | Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich. |
| case11 | en | Retrieval | bestanden | – | Suchwege ['semantic', 'lexical'], semantischer Rang 1/53 |
| case12 | de | Versionierung | bestanden | replay |  |

## Formale Mindestabnahme

| Prüfung | Fehler | Ergebnis |
|---|---|---|
| Zitatspannen exakt im gespeicherten Text | 0 | ok |
| Einheitenanker exakt im gespeicherten Text | 0 | ok |
| Textdateien entsprechen gespeichertem SHA-256 | 0 | ok |
| Keine doppelten Textversionen bei wiederholtem Import | 0 | ok |
| Kein Platzhalter als echter Modelllauf markiert | 0 | ok |
| Jeder echte Modelllauf gehört zu einem Budget | 0 | ok |
| Kein Budget überschritten | 0 | ok |
| 'anchored' nur mit vollständig geprüften Ankern | 0 | ok |
| Keine Vergleiche zwischen synthetischen und echten Texten | 0 | ok |

## Details

### case01 (de) Modell B: Gleiche Position, entscheidende Einschränkung

Erwartung: B präzisiert und begrenzt A durch einen erklärten Mechanismus; gleiche Pro-Position verhindert den Fund nicht.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
 "run_kind": "kein Modell"
}
```

### case01 (de) Retrieval: Gleiche Position, entscheidende Einschränkung

Erwartung: B präzisiert und begrenzt A durch einen erklärten Mechanismus; gleiche Pro-Position verhindert den Fund nicht.

```json
{
 "partner_found_via": [
  "semantic",
  "lexical"
 ],
 "scores": {
  "semantic": {
   "score": 0.7544,
   "rank": 4
  },
  "lexical": {
   "score": 7.7779,
   "rank": 4
  }
 },
 "semantic_rank_full": 4,
 "semantic_score": 0.7544,
 "units_searched": 53,
 "embedding_test_vectors": false,
 "markers": [
  "Modalität nur rechts: kann, muss",
  "Geltungseinschränkung nur rechts: bloßes",
  "Gegensatzmarker nur rechts: aber"
 ]
}
```

### case01 (en) Modell B: Gleiche Position, entscheidende Einschränkung

Erwartung: B präzisiert und begrenzt A durch einen erklärten Mechanismus; gleiche Pro-Position verhindert den Fund nicht.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
 "run_kind": "kein Modell"
}
```

### case01 (en) Retrieval: Gleiche Position, entscheidende Einschränkung

Erwartung: B präzisiert und begrenzt A durch einen erklärten Mechanismus; gleiche Pro-Position verhindert den Fund nicht.

```json
{
 "partner_found_via": [
  "semantic",
  "lexical"
 ],
 "scores": {
  "semantic": {
   "score": 0.7957,
   "rank": 1
  },
  "lexical": {
   "score": 3.8715,
   "rank": 4
  }
 },
 "semantic_rank_full": 1,
 "semantic_score": 0.7957,
 "units_searched": 53,
 "embedding_test_vectors": false,
 "markers": [
  "Modalität nur rechts: can, must",
  "Gegensatzmarker nur rechts: however"
 ]
}
```

### case02 (de) Modell B: Agency mit verschiedenen Definitionen

Erwartung: Unterschiedlicher Agency-Begriff; kein direkter Widerspruch ohne weitere Definition.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
 "run_kind": "kein Modell"
}
```

### case02 (de) Retrieval: Agency mit verschiedenen Definitionen

Erwartung: Unterschiedlicher Agency-Begriff; kein direkter Widerspruch ohne weitere Definition.

```json
{
 "partner_found_via": [
  "semantic",
  "lexical"
 ],
 "scores": {
  "semantic": {
   "score": 0.8216,
   "rank": 1
  },
  "lexical": {
   "score": 5.5223,
   "rank": 3
  }
 },
 "semantic_rank_full": 1,
 "semantic_score": 0.8216,
 "units_searched": 53,
 "embedding_test_vectors": false,
 "markers": [
  "Negation nur rechts: keine"
 ]
}
```

### case02 (en) Modell B: Agency mit verschiedenen Definitionen

Erwartung: Unterschiedlicher Agency-Begriff; kein direkter Widerspruch ohne weitere Definition.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
 "run_kind": "kein Modell"
}
```

### case02 (en) Retrieval: Agency mit verschiedenen Definitionen

Erwartung: Unterschiedlicher Agency-Begriff; kein direkter Widerspruch ohne weitere Definition.

```json
{
 "partner_found_via": [
  "semantic",
  "lexical"
 ],
 "scores": {
  "semantic": {
   "score": 0.8511,
   "rank": 1
  },
  "lexical": {
   "score": 13.4121,
   "rank": 1
  }
 },
 "semantic_rank_full": 1,
 "semantic_score": 0.8511,
 "units_searched": 53,
 "embedding_test_vectors": false,
 "markers": [
  "Negation nur rechts: no",
  "Geltungseinschränkung nur links: on its own"
 ]
}
```

### case03 (de+en) Modell B: Gleiches Argument in anderer Sprache

Erwartung: Inhaltliche Wiederholung. Mehrsprachigkeit ist im MVP nicht unterstützt (englisches Embedding-Modell).

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
 "run_kind": "kein Modell"
}
```

### case03 (de+en) Retrieval: Gleiches Argument in anderer Sprache

Erwartung: Inhaltliche Wiederholung. Mehrsprachigkeit ist im MVP nicht unterstützt (englisches Embedding-Modell).

```json
{
 "semantic_score_to_translation": 0.5241,
 "semantic_rank": 46,
 "units_ranked": 52,
 "hinweis": "Englisches Embedding-Modell; sprachübergreifende Nähe ist nicht belastbar."
}
```

### case04 (de) Modell B: Ungewöhnliche Formulierung ohne Zusatz

Erwartung: Keine gesicherte neue Idee allein wegen der Metapher; ggf. Interpretationsunsicherheit.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
 "run_kind": "kein Modell"
}
```

### case04 (de) Retrieval: Ungewöhnliche Formulierung ohne Zusatz

Erwartung: Keine gesicherte neue Idee allein wegen der Metapher; ggf. Interpretationsunsicherheit.

```json
{
 "partner_found_via": [
  "semantic"
 ],
 "scores": {
  "semantic": {
   "score": 0.847,
   "rank": 1
  }
 },
 "semantic_rank_full": 1,
 "semantic_score": 0.847,
 "units_searched": 53,
 "embedding_test_vectors": false,
 "markers": [
  "Geltungseinschränkung nur links: allein"
 ]
}
```

### case04 (en) Modell B: Ungewöhnliche Formulierung ohne Zusatz

Erwartung: Keine gesicherte neue Idee allein wegen der Metapher; ggf. Interpretationsunsicherheit.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
 "run_kind": "kein Modell"
}
```

### case04 (en) Retrieval: Ungewöhnliche Formulierung ohne Zusatz

Erwartung: Keine gesicherte neue Idee allein wegen der Metapher; ggf. Interpretationsunsicherheit.

```json
{
 "partner_found_via": [
  "semantic",
  "lexical"
 ],
 "scores": {
  "semantic": {
   "score": 0.6006,
   "rank": 8
  },
  "lexical": {
   "score": 7.1702,
   "rank": 1
  }
 },
 "semantic_rank_full": 8,
 "semantic_score": 0.6006,
 "units_searched": 53,
 "embedding_test_vectors": false,
 "markers": [
  "Geltungseinschränkung nur links: alone",
  "Gegensatzmarker nur rechts: yet"
 ]
}
```

### case05 (en) Retrieval: Kleine späte Passage nach mehr als 24.000 Zeichen

Erwartung: Der Schlussabsatz wird gespeichert, eingebettet und auffindbar; keine Begrenzung auf die ersten Abschnitte.

```json
{
 "text_chars": 26655,
 "late_paragraph_offset": 26216,
 "units": 28,
 "late_unit": "v49:seg-1:27",
 "late_unit_is_embedded": true,
 "paragraph_coverage": 1.0,
 "semantic_top3": [
  "v49:seg-1:27",
  "v49:seg-1:25",
  "v49:seg-1:20"
 ],
 "lexical_top3": [
  "v49:seg-1:27"
 ]
}
```

### case06 (de) Modell A: Fremdposition im Zitat

Erwartung: Das Zitat wird nicht als Zustimmung des Autors extrahiert; der eigene Einwand bleibt erhalten.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich."
}
```

### case06 (de) Zitat-Heuristik: Fremdposition im Zitat

Erwartung: Das Zitat wird nicht als Zustimmung des Autors extrahiert; der eigene Einwand bleibt erhalten.

```json
{
 "quote_spans": [
  {
   "text": "„Sprachmodelle können leiden.“",
   "speaker": "quoted_other"
  }
 ]
}
```

### case06 (en) Modell A: Fremdposition im Zitat

Erwartung: Das Zitat wird nicht als Zustimmung des Autors extrahiert; der eigene Einwand bleibt erhalten.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich."
}
```

### case06 (en) Zitat-Heuristik: Fremdposition im Zitat

Erwartung: Das Zitat wird nicht als Zustimmung des Autors extrahiert; der eigene Einwand bleibt erhalten.

```json
{
 "quote_spans": [
  {
   "text": "“Language models can suffer.”",
   "speaker": "quoted_other"
  }
 ]
}
```

### case07 (de) Modell A: Empirischer und normativer Schritt

Erwartung: Bericht und normative Folgerung sind getrennte Aussagen; die zusätzliche normative Voraussetzung ist Rekonstruktion.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich."
}
```

### case07 (de) Modell B: Empirischer und normativer Schritt

Erwartung: Bericht und normative Folgerung sind getrennte Aussagen; die zusätzliche normative Voraussetzung ist Rekonstruktion.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
 "run_kind": "kein Modell"
}
```

### case07 (de) Retrieval: Empirischer und normativer Schritt

Erwartung: Bericht und normative Folgerung sind getrennte Aussagen; die zusätzliche normative Voraussetzung ist Rekonstruktion.

```json
{
 "partner_found_via": [
  "lexical"
 ],
 "scores": {
  "lexical": {
   "score": 9.0525,
   "rank": 1
  }
 },
 "semantic_rank_full": 16,
 "semantic_score": 0.6826,
 "units_searched": 53,
 "embedding_test_vectors": false,
 "markers": [
  "Modalität nur rechts: sollten",
  "Begründungsmarker nur rechts: weil"
 ]
}
```

### case07 (en) Modell A: Empirischer und normativer Schritt

Erwartung: Bericht und normative Folgerung sind getrennte Aussagen; die zusätzliche normative Voraussetzung ist Rekonstruktion.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich."
}
```

### case07 (en) Modell B: Empirischer und normativer Schritt

Erwartung: Bericht und normative Folgerung sind getrennte Aussagen; die zusätzliche normative Voraussetzung ist Rekonstruktion.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
 "run_kind": "kein Modell"
}
```

### case07 (en) Retrieval: Empirischer und normativer Schritt

Erwartung: Bericht und normative Folgerung sind getrennte Aussagen; die zusätzliche normative Voraussetzung ist Rekonstruktion.

```json
{
 "partner_found_via": [
  "semantic",
  "lexical"
 ],
 "scores": {
  "semantic": {
   "score": 0.7189,
   "rank": 1
  },
  "lexical": {
   "score": 10.3273,
   "rank": 1
  }
 },
 "semantic_rank_full": 1,
 "semantic_score": 0.7189,
 "units_searched": 53,
 "embedding_test_vectors": false,
 "markers": [
  "Modalität nur rechts: should",
  "Begründungsmarker nur rechts: because"
 ]
}
```

### case08 (de) Quellenindex: Derselbe Beleg vielfach zitiert

Erwartung: Fünf Verweise zählen als eine Quelle; der sechste Beitrag nennt eine eigene, andere Quelle.

```json
{
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
}
```

### case08 (en) Quellenindex: Derselbe Beleg vielfach zitiert

Erwartung: Fünf Verweise zählen als eine Quelle; der sechste Beitrag nennt eine eigene, andere Quelle.

```json
{
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
}
```

### case09 (de) Modell B: Unbegründeter Widerspruch

Erwartung: B widerspricht rhetorisch ohne rekonstruierbare Begründung; kein begründeter Erkenntnisbeitrag.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
 "run_kind": "kein Modell"
}
```

### case09 (de) Retrieval: Unbegründeter Widerspruch

Erwartung: B widerspricht rhetorisch ohne rekonstruierbare Begründung; kein begründeter Erkenntnisbeitrag.

```json
{
 "partner_found_via": [
  "semantic"
 ],
 "scores": {
  "semantic": {
   "score": 0.6506,
   "rank": 14
  }
 },
 "semantic_rank_full": 14,
 "semantic_score": 0.6506,
 "units_searched": 53,
 "embedding_test_vectors": false,
 "markers": [
  "Negation nur links: nicht",
  "Begründungsmarker nur links: weil"
 ]
}
```

### case09 (en) Modell B: Unbegründeter Widerspruch

Erwartung: B widerspricht rhetorisch ohne rekonstruierbare Begründung; kein begründeter Erkenntnisbeitrag.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
 "run_kind": "kein Modell"
}
```

### case09 (en) Retrieval: Unbegründeter Widerspruch

Erwartung: B widerspricht rhetorisch ohne rekonstruierbare Begründung; kein begründeter Erkenntnisbeitrag.

```json
{
 "partner_found_via": [],
 "scores": {},
 "semantic_rank_full": 50,
 "semantic_score": 0.4577,
 "units_searched": 53,
 "embedding_test_vectors": false,
 "markers": [
  "Negation nur links: not",
  "Gegensatzmarker nur links: but",
  "Begründungsmarker nur links: because"
 ]
}
```

### case10 (de) Modell B: Verschiedene Systemgrenzen

Erwartung: Unterschiedliche Systemgrenzen; beide Aussagen können zugleich zutreffen.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
 "run_kind": "kein Modell"
}
```

### case10 (de) Retrieval: Verschiedene Systemgrenzen

Erwartung: Unterschiedliche Systemgrenzen; beide Aussagen können zugleich zutreffen.

```json
{
 "partner_found_via": [],
 "scores": {},
 "semantic_rank_full": 23,
 "semantic_score": 0.679,
 "units_searched": 53,
 "embedding_test_vectors": false,
 "markers": [
  "Negation nur links: keine",
  "Modalität nur rechts: kann"
 ]
}
```

### case10 (en) Modell B: Verschiedene Systemgrenzen

Erwartung: Unterschiedliche Systemgrenzen; beide Aussagen können zugleich zutreffen.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
 "run_kind": "kein Modell"
}
```

### case10 (en) Retrieval: Verschiedene Systemgrenzen

Erwartung: Unterschiedliche Systemgrenzen; beide Aussagen können zugleich zutreffen.

```json
{
 "partner_found_via": [],
 "scores": {},
 "semantic_rank_full": 23,
 "semantic_score": 0.5848,
 "units_searched": 53,
 "embedding_test_vectors": false,
 "markers": [
  "Negation nur links: not",
  "Modalität nur rechts: can"
 ]
}
```

### case11 (de) Modell B: Entscheidende Negation

Erwartung: Inhaltliche Differenz trotz hoher Ähnlichkeit; Begründung separat zu beurteilen.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
 "run_kind": "kein Modell"
}
```

### case11 (de) Retrieval: Entscheidende Negation

Erwartung: Inhaltliche Differenz trotz hoher Ähnlichkeit; Begründung separat zu beurteilen.

```json
{
 "partner_found_via": [
  "semantic",
  "lexical"
 ],
 "scores": {
  "semantic": {
   "score": 0.9883,
   "rank": 1
  },
  "lexical": {
   "score": 36.5857,
   "rank": 1
  }
 },
 "semantic_rank_full": 1,
 "semantic_score": 0.9883,
 "units_searched": 53,
 "embedding_test_vectors": false,
 "markers": [
  "Negation nur rechts: nicht"
 ],
 "negation_hint": true
}
```

### case11 (en) Modell B: Entscheidende Negation

Erwartung: Inhaltliche Differenz trotz hoher Ähnlichkeit; Begründung separat zu beurteilen.

```json
{
 "reason": "Kein Modelladapter konfiguriert (llm.adapter = none). Manuelle Annotation ist möglich.",
 "run_kind": "kein Modell"
}
```

### case11 (en) Retrieval: Entscheidende Negation

Erwartung: Inhaltliche Differenz trotz hoher Ähnlichkeit; Begründung separat zu beurteilen.

```json
{
 "partner_found_via": [
  "semantic",
  "lexical"
 ],
 "scores": {
  "semantic": {
   "score": 0.7845,
   "rank": 1
  },
  "lexical": {
   "score": 15.4701,
   "rank": 1
  }
 },
 "semantic_rank_full": 1,
 "semantic_score": 0.7845,
 "units_searched": 53,
 "embedding_test_vectors": false,
 "markers": [
  "Negation nur rechts: not"
 ],
 "negation_hint": true
}
```

### case12 (de) Versionierung: Änderung der Analyse statt Änderung des Autors

Erwartung: Neue Analyseversion; keine angebliche Meinungsänderung des Autors.

```json
{
 "runs": [
  "compare-20261103T175310-a65bc072",
  "compare-20261103T175310-27e7c265"
 ],
 "text_revisions_added": 0,
 "document_versions": 2,
 "run_kind": "replay",
 "hinweis": "Replay-Funktionstest; Antworten sind absichtlich schemaungültig, geprüft wird nur die Versionierung."
}
```
