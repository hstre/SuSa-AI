# Zuordnung: Budget-Review, Semantic Projection Layer, Alexandria → SuSa-AI

Stand 4. November 2026. Gelesen: Budget-Review `docs/research-report.md` vollständig (deutsche Fassung, §1–§10
einschließlich der neun zurückgezogenen Aussagen), `docs/architecture.md` §1–§3a, `src/budget_review/` (gate,
anchoring, coverage, prompts, models, provider) und `scripts/` (semantic_cases, semantic_score,
two_stage_extract); SPL README, `spl_frontend.py`, `spl.py`; Alexandria `schema.py` (`ClaimNode`, `Category`,
`Modality`, `RelationType` Annex F, `EpistemicIdentity`).

Versionen: Budget-Review `6fc50e7`, SPL `dddcbc9`, Alexandria `45865bd`.

## Zuordnung

| Bedarf in SuSa-AI | Vorhanden in | Entscheidung | Stand in SuSa-AI |
|---|---|---|---|
| Zitat wörtlich im Original verankern, Offsets des Dokuments | BR `anchoring.anchor_spans` (Bericht §4.3) | **übernommen** | `analysis.check_quotes` nutzt es; SuSa behält nur das Entfernen umschließender Anführungszeichen als zweiten Versuch |
| Zulassung von Claims und Kanten (Verankerung, Konfidenzboden, inhaltsadressierte Knoten, geschlossene Typen, Endpunkte) | BR `gate.govern_packet` („Layer-9-Gate“, architecture §3) | **übernommen** | `br_bridge` |
| Atomare Claims mit wörtlicher Spanne, Proposition in der Sprache des Dokuments | BR `prompts.extraction_prompt` (§4.12: 38/122 → 0/123 übersetzt) | **übernommen** | `br_bridge.extract_side`; SuSas eigener Prompt A ist für die Zerlegung abgelöst (er schrieb deutsche Propositionen zu englischen Texten, genau der Fehler aus §4.12) |
| Schemafehler einzelner Vorschläge, ohne das Paket zu verlieren | BR `provider._reject_invalid_proposals` | **übernommen** | ohne Regenerationsaufruf (Budget) |
| Textabdeckung (verankerter Anteil, benannte Lücken) | BR `coverage.measure_coverage` (§4.4, architecture §3a) | **übernommen**, auf den Kernabschnitt zugeschnitten | `br_bridge.core_coverage`; SuSas `paragraph_coverage` misst etwas anderes (Segmentierung) und bleibt |
| Bedeutungstreue (Negation, Modalität, Bedingung, Geltungsbereich, Sprecher, mehrere Aussagen) ohne Modell als Prüfer | BR `scripts/semantic_cases.py`, `semantic_score.py` (§4.12, §4.16) | **wörtlich übernommen** (`vendor_br`), Fälle für Paar 1 im selben Format geschrieben | Fälle lokal, weil sie Originalsätze enthalten |
| Sprache der Proposition als eigene Achse | BR `language_of` (§4.12) | **übernommen** | `vendor_br` |
| Relationen über eine feste Claim-Liste, erfundene IDs verwerfen | BR `scripts/two_stage_extract.py` (§4.11: 0 ungültige Labels über 192 Kanten) | **übernommen**, neu angewendet **über zwei Passagen** | `br_bridge.cross_relations`, Zulassung durch dasselbe Gate |
| Ein Lauf ist eine Ziehung | BR §4.2, §4.15, §7 (sechs von neun Rücknahmen) | **übernommen** als Regel: drei Wiederholungen, Stabilität über Anker | `br_bridge.evaluate` |
| Angefragtes und ausgeliefertes Modell protokollieren | BR §4.8 | war in SuSa schon vorhanden (`model_calls`) | – |
| Sprecher, Negation, Modalität, Bedingung, Geltungsbereich als **eigene Felder** | SPL: Modalität, Scope, Zeit per Regex, **keine Negation, kein Sprecher**; BR: offen (§10.5); Alexandria `ClaimNode`: `modality` (epistemische Stärke), `scope`, `qualifiers` | **nicht neu gebaut**. Wie in BR bleiben sie im Wortlaut der Proposition und werden über Bedingungen geprüft | SuSas Prompt-A-Felder (`speaker_role` usw.) nicht weiterentwickelt |
| Text → Projektion ohne Modell | SPL Offline-Frontend M1–M3 | **nicht verwendet**: auf Paar 1 null Einheiten für A, zwei Fehllesungen für B (Sprecher verloren, „may be convinced“ als Aussagemodalität); das ist die im SPL-README dokumentierte Grenze | – |
| Entropie/JSD über Relationsverteilungen | SPL `spl.py`, WP2 | **nicht übertragbar** (BR §8: eine JSON-Antwort liefert keine kalibrierte Verteilung); die übertragbare Anpassung, Wiederholungen als empirische Verteilung, ist übernommen | Häufigkeit je Kante über drei Läufe |
| Kanonischer Claim mit Lineage, Patch, Siegel | Alexandria `ClaimNode`, Gateway | **noch nicht** (WP2-Weg Text → SemanticUnit → Projection → ClaimCandidate → ClaimNode). SuSa liefert höchstens Kandidaten | – |
| Claim-Typen als Grundlage von Befunden | BR: 21 Typen ohne Definition, 8 von 24 Dokumenten wechseln den Typ (§4.13) | **nicht als Grundlage verwendet**, nur angezeigt | – |
| Identität eines Claims | BR §4.5: Anker stabil, Modellwortlaut instabil; Anker-only-Identität **zurückgezogen** (§7.8) | Anker als Schlüssel für Laufvergleiche; mehrere Claims je Anker erlaubt, keine Verschmelzung | `evaluate` |

## Was SuSa-AI tatsächlich neu beiträgt

Nur der Vergleich **über zwei Dokumente**. Budget-Review prüft ein Dokument in sich. Alexandria hat mit Annex F
(`REFINES`, `EXTENDS`, `PARTIALLY_CONTRADICTS` …) das Vokabular für Beziehungen zwischen Claims, aber keinen Weg
dorthin aus Text.

## Lücken, die bleiben

1. **Relationsvokabular zwischen Passagen.** Die 14 BR-Typen sind für Kanten innerhalb eines Dokuments gebaut:
   Es gibt `QUALIFIES`, `CONTRADICTS`, `SCOPE_TENSION`, `GENERALIZES`, aber kein `REFINES`/`EXTENDS` (Alexandria
   hat beide). Weder BR noch Alexandria können „beantwortet eine andere Frage“ oder „scheinbarer Widerspruch durch
   andere Definition“ ausdrücken; SuSas eigene Typen tun es, haben aber keine Wahrheitsbedingungen (gleicher
   Befund wie BR §4.13). Nach BR §4.10 wird das Vokabular nicht ohne Evidenz erweitert.
2. **Bedeutungsbedingungen stammen von derselben Partei**, die das System baut, und sind nicht unabhängig
   durchgesehen (BR §4.16 verlangt zwei unabhängige Durchsichten).
3. **Relationen sind nicht annotiert**: Es gibt kein Gold dafür, welche Kante zwischen zwei Passagen richtig ist
   (BR §4.12 „Relationen bleiben nicht messbar“). Für Paar 1 fehlt auch Steffens freies Urteil als Vergleich.
4. **Fachliche Begründung** (ob ein Argument trägt) prüft keine Komponente. BR: „Keine Komponente darf einen Claim
   als wahr markieren.“

## Berücksichtigte zurückgezogene Aussagen (BR §7)

- Keine Ein-Lauf-Vergleiche (Rücknahmen 1, 2, 9): drei Wiederholungen, und auch diese liegen in einem Zeitfenster,
  das die Streuung nach §4.2 unterschätzt.
- Anker-only-Identität (8): nicht verwendet.
- Relationslabels als Vokabularlücke (5): Ein unbekanntes Label wird abgelehnt und gezählt, nicht als Bedarf
  gelesen.
- Lückenliste skalenabhängig (6): Die Abdeckung wird nur auf kurzen Kernabschnitten berichtet.
