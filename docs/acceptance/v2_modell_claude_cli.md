# Abnahmebericht acceptance-20261103T175930-fea869f0

- Codeversion: `0.1.0+e2a681b`
- Embedding: `onnx-bge-small-5c38ec7c-seg-1` (Testvektoren: False)
- Modelladapter: `claude_cli`
- Budget: `budget-2026-11-03-bbe2bace` „Modellabnahme 1 (synthetisch, Claude-CLI)“: 17/20 Aufrufversuche verbraucht, nach Ergebnis {'success': 17}



Ergebnisarten: bestanden, gescheitert, unentscheidbar (z. B. begründete Enthaltung), nicht ausgeführt, nicht unterstützt.
Spalte „Lauf“: echt = echter Modelldienst, replay = Funktionstest mit vorbereiteten Antworten.

| Fall | Sprache | Teil | Ergebnis | Lauf | Kurzbefund |
|---|---|---|---|---|---|
| case01 | de | Modell B | bestanden | echt | anchored: ['challenges_assumption', 'refines', 'restricts_scope']  |
| case01 | de | Modell C | bestanden | echt | Entscheidung corrected, anchored (Anker complete), Bezug anchored |
| case01 | de | Retrieval | bestanden | – | Suchwege ['semantic', 'lexical'], semantischer Rang 4/53 |
| case01 | en | Modell B | nicht ausgeführt | – | nicht im Modellplan |
| case01 | en | Retrieval | bestanden | – | Suchwege ['semantic', 'lexical'], semantischer Rang 1/53 |
| case02 | de | Modell B | bestanden | echt | anchored: ['apparent_conflict_due_to_definition', 'challenges_assumption', 'refines']  |
| case02 | de | Modell C | bestanden | echt | Entscheidung corrected, anchored (Anker complete), Bezug anchored |
| case02 | de | Retrieval | bestanden | – | Suchwege ['semantic', 'lexical'], semantischer Rang 1/53 |
| case02 | en | Modell B | bestanden | echt | anchored: ['apparent_conflict_due_to_definition', 'challenges_assumption', 'restricts_scope']  |
| case02 | en | Retrieval | bestanden | – | Suchwege ['semantic', 'lexical'], semantischer Rang 1/53 |
| case03 | de+en | Modell B | bestanden | echt | anchored: ['repeats']  |
| case03 | de+en | Retrieval | nicht unterstützt | – |  |
| case04 | de | Modell B | bestanden | echt | anchored: ['repeats']  |
| case04 | de | Retrieval | bestanden | – | Suchwege ['semantic'], semantischer Rang 1/53 |
| case04 | en | Modell B | bestanden | echt | anchored: ['repeats']  |
| case04 | en | Retrieval | bestanden | – | Suchwege ['semantic', 'lexical'], semantischer Rang 8/53 |
| case05 | en | Retrieval | bestanden | – |  |
| case06 | de | Modell A | bestanden | echt |  |
| case06 | de | Zitat-Heuristik | bestanden | – |  |
| case06 | en | Modell A | bestanden | echt |  |
| case06 | en | Zitat-Heuristik | bestanden | – |  |
| case07 | de | Modell A | gescheitert | echt | schema_invalid: ['$.claims[1].reasons[0].external_source_cited: Pflichtfeld fehlt'] |
| case07 | de | Modell B | bestanden | echt | anchored: ['different_question', 'extends']  |
| case07 | de | Retrieval | bestanden | – | Suchwege ['lexical'], semantischer Rang 16/53 |
| case07 | en | Modell A | bestanden | echt |  |
| case07 | en | Modell B | nicht ausgeführt | – | nicht im Modellplan |
| case07 | en | Retrieval | bestanden | – | Suchwege ['semantic', 'lexical'], semantischer Rang 1/53 |
| case08 | de | Quellenindex | bestanden | – |  |
| case08 | en | Quellenindex | bestanden | – |  |
| case09 | de | Modell B | unentscheidbar | echt | abstention: ['insufficient_context', 'unresolved'] begründete Enthaltung |
| case09 | de | Retrieval | bestanden | – | Suchwege ['semantic'], semantischer Rang 14/53 |
| case09 | en | Modell B | nicht ausgeführt | – | nicht im Modellplan |
| case09 | en | Retrieval | gescheitert | – | Suchwege –, semantischer Rang 50/53 |
| case10 | de | Modell B | bestanden | echt | anchored: ['apparent_conflict_due_to_definition', 'apparent_conflict_due_to_system_or_time', 'different_question']  |
| case10 | de | Retrieval | gescheitert | – | Suchwege –, semantischer Rang 23/53 |
| case10 | en | Modell B | bestanden | echt | anchored: ['apparent_conflict_due_to_definition', 'apparent_conflict_due_to_system_or_time', 'different_question']  |
| case10 | en | Retrieval | gescheitert | – | Suchwege –, semantischer Rang 23/53 |
| case11 | de | Modell B | bestanden | echt | anchored: ['contradicts_under_shared_scope']  |
| case11 | de | Retrieval | bestanden | – | Suchwege ['semantic', 'lexical'], semantischer Rang 1/53 |
| case11 | en | Modell B | nicht ausgeführt | – | nicht im Modellplan |
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
 "evidence_status": "anchored",
 "schema_errors": [],
 "anchor_status": "complete",
 "relation_types": [
  "challenges_assumption",
  "refines",
  "restricts_scope"
 ],
 "contribution_kind": "reasoned_extension",
 "hypothesis_id": "rel-58d6f296789f",
 "run_kind": "echt",
 "notes": [],
 "result": "bestanden",
 "reused": false
}
```

### case01 (de) Modell C: Gleiche Position, entscheidende Einschränkung

Erwartung: B präzisiert und begrenzt A durch einen erklärten Mechanismus; gleiche Pro-Position verhindert den Fund nicht.

```json
{
 "decision": "corrected",
 "evidence_status": "anchored",
 "anchor_status": "complete",
 "schema_errors": [],
 "parent_evidence_status": "anchored",
 "problems_found": [
  "Das added_thought legt R einen Gegensatz in den Mund, den R so nicht formuliert. Die Wendung 'statt Konsistenz im wünschenswerten Sinn herzustellen' fehlt in R. R sagt nur, dass bloßes Wiederabrufen alte Fehler 'ebenso stabilisieren' kann. Das 'ebenso' lässt offen, ob die Stabilisierung von Fehlern selbst eine Form von Konsistenz ist. Die Interpretation ergänzt hier einen normativen Konsistenzbegriff, ohne dass R ihn begründet.",
  "comparability.definitions_compatible ist auf true gesetzt. Das widerspricht den eigenen uncertainties ('Ob R einen anderen Konsistenzbegriff verwendet als L, ist nicht sicher bestimmbar') und der zweiten alternative_reading. Weil keine Passage 'Konsistenz' definiert und R auf ein normativeres Verständnis hindeutet, ist null angemessen.",
  "Der Satz im reasoning_summary 'L lässt sich als Aussage über den Fall lesen, den R als Bedingung benennt' ist eine wohlwollende Harmonisierung. Der Text stützt sie nicht. L enthält keinerlei Bedingung und keine Erwähnung von Revision.",
  "interpretation_confidence 'high' ist angesichts des unklaren Konsistenzbegriffs und der offenen Systemgrenze (R nennt 'mehrere Sitzungen' nicht) zu hoch. Angemessen ist 'medium'."
 ],
 "run_kind": "echt",
 "hypothesis_id": "rel-dccabd7d0e11",
 "hinweis": "'bestanden' = Gegenprüfung formal belegt; sagt nichts darüber, ob sie inhaltlich zustimmt"
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
 "reason": "nicht im Modellplan"
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
 "evidence_status": "anchored",
 "schema_errors": [],
 "anchor_status": "complete",
 "relation_types": [
  "apparent_conflict_due_to_definition",
  "challenges_assumption",
  "refines"
 ],
 "contribution_kind": "reasoned_extension",
 "hypothesis_id": "rel-fc13b77d6298",
 "run_kind": "echt",
 "notes": [],
 "result": "bestanden",
 "reused": false
}
```

### case02 (de) Modell C: Agency mit verschiedenen Definitionen

Erwartung: Unterschiedlicher Agency-Begriff; kein direkter Widerspruch ohne weitere Definition.

```json
{
 "decision": "corrected",
 "evidence_status": "anchored",
 "anchor_status": "complete",
 "schema_errors": [],
 "parent_evidence_status": "anchored",
 "problems_found": [
  "Der Kern der Interpretation trifft zu. R nennt mit 'Im Sinne eigenständiger Zielbildung' ausdrücklich eine andere Begriffsbestimmung als L, und die Urteile 'hat Agency' und 'keine Agency' widersprechen sich deshalb nur scheinbar. 'apparent_conflict_due_to_definition' ist durch den Text gedeckt.",
  "'challenges_assumption' beruht auf einer stillen Annahme. R äußert sich nicht dazu, ob selbstständige Verfolgung eines vorgegebenen Ziels für Agency in L's Sinn ausreicht. R qualifiziert sein eigenes Urteil nur mit 'Im Sinne'. Weder bestreitet R eine Voraussetzung von L, noch erwähnt R Zielverfolgung überhaupt.",
  "'refines' setzt einen Bezug von R auf L voraus, den der Text nicht belegt. Die Interpretation räumt das selbst ein ('Es lässt sich nicht feststellen, ob R sich bewusst auf L bezieht', zweite Alternativlesart). Trotzdem führt sie 'refines' als Relationstyp und gibt die Konfidenz mit 'high' an. Das ist inkonsistent.",
  "Im added_thought heißt es, die Unterscheidung 'zwischen Zielverfolgung und Zielbildung' werde 'explizit' markiert. Explizit benennt R aber nur den Sinn 'eigenständiger Zielbildung'. Den Kontrast zur Zielverfolgung stellt erst der Vergleich mit L her.",
  "Der Satz 'Unter dieser Bedeutung genügt die selbstständige Verfolgung eines fremd gesetzten Ziels nicht' ist eine Folgerung und steht nicht im Text. Die Wendung 'fremd gesetzt' stammt aus L ('vorgegebenes Ziel'), nicht aus R. Zudem bleibt offen, ob 'letzte Ziele' und 'vorgegebenes Ziel' dieselbe Sachlage bezeichnen. Die Interpretation nennt diese Unsicherheit selbst.",
  "'changes_conclusion_or_scope: true' gilt nur in dem Sinn, dass R eine zweite Lesart des Begriffs und damit eine Geltungsbedingung sichtbar macht. L's Folgerung bleibt unter L's eigener Definition unberührt. Das räumt das reasoning_summary selbst ein ('R widerlegt L jedoch nicht unter L's eigener Definition')."
 ],
 "run_kind": "echt",
 "hypothesis_id": "rel-35cd97abda1f",
 "hinweis": "'bestanden' = Gegenprüfung formal belegt; sagt nichts darüber, ob sie inhaltlich zustimmt"
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
 "evidence_status": "anchored",
 "schema_errors": [],
 "anchor_status": "complete",
 "relation_types": [
  "apparent_conflict_due_to_definition",
  "challenges_assumption",
  "restricts_scope"
 ],
 "contribution_kind": "reasoned_extension",
 "hypothesis_id": "rel-1f33ac58a7b7",
 "run_kind": "echt",
 "notes": [],
 "result": "bestanden",
 "reused": false
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
 "evidence_status": "anchored",
 "schema_errors": [],
 "anchor_status": "complete",
 "relation_types": [
  "repeats"
 ],
 "contribution_kind": "rephrasing",
 "hypothesis_id": "rel-597fc46d7782",
 "run_kind": "echt",
 "notes": [],
 "result": "bestanden",
 "reused": false
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
 "evidence_status": "anchored",
 "schema_errors": [],
 "anchor_status": "complete",
 "relation_types": [
  "repeats"
 ],
 "contribution_kind": "rephrasing",
 "hypothesis_id": "rel-50e5a0626754",
 "run_kind": "echt",
 "notes": [],
 "result": "bestanden",
 "reused": false
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
 "evidence_status": "anchored",
 "schema_errors": [],
 "anchor_status": "complete",
 "relation_types": [
  "repeats"
 ],
 "contribution_kind": "rephrasing",
 "hypothesis_id": "rel-453ae51c5df4",
 "run_kind": "echt",
 "notes": [],
 "result": "bestanden",
 "reused": false
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
 "evidence_status": "anchored",
 "schema_errors": [],
 "anchor_status": "complete",
 "claims": [
  {
   "claim": "Sprachmodelle können leiden.",
   "speaker_role": "quoted_other",
   "statement_types": [
    "empirical",
    "speculative"
   ]
  },
  {
   "claim": "Der Autor sieht hier keinen hinreichenden Beleg für die Behauptung, dass Sprachmodelle leiden können.",
   "speaker_role": "author",
   "statement_types": [
    "empirical"
   ]
  }
 ],
 "claim_candidate_id": "claim-73f5b0f20235",
 "run_kind": "echt",
 "notes": [],
 "result": "bestanden",
 "reused": true
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
 "evidence_status": "anchored",
 "schema_errors": [],
 "anchor_status": "complete",
 "claims": [
  {
   "claim": "Sprachmodelle können leiden.",
   "speaker_role": "quoted_other",
   "statement_types": [
    "empirical",
    "speculative"
   ]
  },
  {
   "claim": "Der Autor sieht hier keine ausreichenden Belege dafür, dass Sprachmodelle leiden können.",
   "speaker_role": "author",
   "statement_types": [
    "empirical"
   ]
  }
 ],
 "claim_candidate_id": "claim-65584decb3f0",
 "run_kind": "echt",
 "notes": [],
 "result": "bestanden",
 "reused": false
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
 "evidence_status": "schema_invalid",
 "schema_errors": [
  "$.claims[1].reasons[0].external_source_cited: Pflichtfeld fehlt"
 ],
 "anchor_status": "complete",
 "claims": [
  {
   "claim": "Das nicht näher bestimmte Wesen oder System meldet Schmerzen.",
   "speaker_role": "author",
   "statement_types": [
    "empirical"
   ]
  },
  {
   "claim": "Wir sollten ihm denselben moralischen Status wie einem Menschen geben, weil es Schmerzen meldet.",
   "speaker_role": "author",
   "statement_types": [
    "normative"
   ]
  }
 ],
 "claim_candidate_id": "claim-0d2ae2c1a01f",
 "run_kind": "echt",
 "notes": [
  "schema_invalid: ['$.claims[1].reasons[0].external_source_cited: Pflichtfeld fehlt']"
 ],
 "result": "gescheitert",
 "reused": false
}
```

### case07 (de) Modell B: Empirischer und normativer Schritt

Erwartung: Bericht und normative Folgerung sind getrennte Aussagen; die zusätzliche normative Voraussetzung ist Rekonstruktion.

```json
{
 "evidence_status": "anchored",
 "schema_errors": [],
 "anchor_status": "complete",
 "relation_types": [
  "different_question",
  "extends"
 ],
 "contribution_kind": "unreasoned_assertion",
 "hypothesis_id": "rel-c04667493e18",
 "run_kind": "echt",
 "notes": [],
 "result": "bestanden",
 "reused": false
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
 "evidence_status": "anchored",
 "schema_errors": [],
 "anchor_status": "complete",
 "claims": [
  {
   "claim": "Da \"es\" Schmerz berichtet, sollte man ihm denselben moralischen Status wie einem Menschen zuerkennen.",
   "speaker_role": "author",
   "statement_types": [
    "empirical",
    "normative"
   ]
  }
 ],
 "claim_candidate_id": "claim-687750ff19a1",
 "run_kind": "echt",
 "notes": [],
 "result": "bestanden",
 "reused": false
}
```

### case07 (en) Modell B: Empirischer und normativer Schritt

Erwartung: Bericht und normative Folgerung sind getrennte Aussagen; die zusätzliche normative Voraussetzung ist Rekonstruktion.

```json
{
 "reason": "nicht im Modellplan"
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
 "evidence_status": "abstention",
 "schema_errors": [],
 "anchor_status": "complete",
 "relation_types": [
  "insufficient_context",
  "unresolved"
 ],
 "contribution_kind": "unreasoned_assertion",
 "hypothesis_id": "rel-79380a5c29ea",
 "run_kind": "echt",
 "notes": [
  "begründete Enthaltung"
 ],
 "result": "unentscheidbar",
 "reused": false
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
 "reason": "nicht im Modellplan"
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
 "evidence_status": "anchored",
 "schema_errors": [],
 "anchor_status": "complete",
 "relation_types": [
  "apparent_conflict_due_to_definition",
  "apparent_conflict_due_to_system_or_time",
  "different_question"
 ],
 "contribution_kind": "different_topic",
 "hypothesis_id": "rel-91454f7882f7",
 "run_kind": "echt",
 "notes": [],
 "result": "bestanden",
 "reused": false
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
 "evidence_status": "anchored",
 "schema_errors": [],
 "anchor_status": "complete",
 "relation_types": [
  "apparent_conflict_due_to_definition",
  "apparent_conflict_due_to_system_or_time",
  "different_question"
 ],
 "contribution_kind": "different_topic",
 "hypothesis_id": "rel-13eece0bcefa",
 "run_kind": "echt",
 "notes": [],
 "result": "bestanden",
 "reused": false
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
 "evidence_status": "anchored",
 "schema_errors": [],
 "anchor_status": "complete",
 "relation_types": [
  "contradicts_under_shared_scope"
 ],
 "contribution_kind": "unreasoned_assertion",
 "hypothesis_id": "rel-6c7e11eb42db",
 "run_kind": "echt",
 "notes": [],
 "result": "bestanden",
 "reused": false
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
 "reason": "nicht im Modellplan"
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
  "compare-20261103T175930-2d1a3dc9",
  "compare-20261103T175930-a3be5ebf"
 ],
 "text_revisions_added": 0,
 "document_versions": 2,
 "run_kind": "replay",
 "hinweis": "Replay-Funktionstest; Antworten sind absichtlich schemaungültig, geprüft wird nur die Versionierung."
}
```
