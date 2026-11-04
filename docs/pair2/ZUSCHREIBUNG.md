# Paar 2: Spur der Sprecherzuordnung vom Originalsatz bis zum Schlussvergleich

Stand 4. November 2026. Grundlage sind nur gespeicherte Daten: `passages.json`, `run-1.json`, der Lauf
`argument_stage-20261104T165110-bcf29374` (`inputs.json`, `result.json`, `validation.json`). Es gab keinen neuen
Modellaufruf. Die ursprüngliche Ausgabe bleibt unverändert: [ARGUMENT_STAGE_RAW.md](ARGUMENT_STAGE_RAW.md) (Darstellung r1),
lokal `report_full.md` und `result.json`.

## Spur für den Schluss von B (B16, Bullshit-These)

| Schritt | Was dort über den Sprecher steht | erhalten? |
|---|---|---|
| 1. Originalsatz B16 (Kontext danach) | kurzer Aussagesatz ohne Redeverb. Der Absatz ist beim Import als gewöhnlicher Absatz (`p`) erfasst, nicht als Blockzitat. Ein Hinweis auf fremde Stimme steht nur zwei Sätze davor in B12 (Rückverweis in der ersten Person Plural). Im Kern steht ausdrücklich zugeschrieben B05 (nach den Autoren) und B08 (die Autoren behaupten). | **Der Text selbst lässt den Sprecher offen.** |
| 2. Extraktion (Budget-Review, Lauf 1) | Die Proposition zu B16 enthält keinen Sprecher, denn der Satz hat keinen. Bei B12 lässt die Proposition den Rückverweis weg; die wörtliche Spanne behält ihn. B05 und B08 behalten die Zuschreibung. | Spanne ja, Proposition bei B12 nein |
| 3. Deterministische Struktur | Hinweise je Anker: B12 Redeverb plus erste Person Plural, B05 Redeverb, B16 kein Hinweis, Bereich Kontext danach | ja |
| 4. Sprechakte (Modell, Prompt D) | B10–B16: berichtet, Sprecher „wahrscheinlich die Artikelautoren (Zitat)“; dazu eine offene Lesart (Zitat oder eigene Stellungnahme von B) | **ja, mit Unsicherheit** |
| 5. Kette B-K3 | Feld `side: "B"`, kein Sprecherfeld. Die Unsicherheit steht nur im Freitext `modality` | nur im Freitext |
| 6. Bezugsfragen | F1 ordnet B-K3 der Spalte B zu (Passage, nicht Sprecher) | **nein** (es gibt keine Stelle dafür) |
| 7. Schlussvergleich `conclusion_comparison[0]` | `common`: B gebe die These (wahrscheinlich zitierend) als Position der Artikelautoren wieder. `difference`: „B (bzw. die zitierte Stimme) behauptet sie und begründet sie“ | **hier kippt es**: Im selben Eintrag wird aus der Wiedergabe eine Behauptung von B |
| 8. Bericht r1 | Ketten unter „Passage B“, Vergleich nur mit Anker-IDs und Modellfreitext, kein Sprecher | **nein**, die Verschiebung wird weitergereicht |

Die Information ist bis Schritt 4 vorhanden. Verloren geht sie beim Zusammenfassen (Schritte 5 bis 8): Ketten,
Fragen und Vergleiche sind nach Passage geordnet, die Sprechakte sind mit ihnen nicht verbunden, und der Freitext
des Vergleichs macht die Passage zum Subjekt.

## Rahmensatz

Der einleitende Rahmensatz von A kündigt eine knappe Wiedergabe der Gegenposition an und leitet A03–A05 ein.
Er ist in `passages.json` gespeichert (Offsets 222–363 relativ zur Passage), hat aber keinen Claim ergeben.

- **Bis r1:** Er ist nicht als Quellenstelle referenzierbar. Anker entstehen nur aus Claims; eine ID dafür hätte die
  Validierung als unbekannten Anker abgelehnt. Das Modell konnte ihn nur im Freitext einer Anmerkung erwähnen
  (Befund R1).
- **Jetzt:** Sätze ohne Claim werden deterministisch als zitierbare Stellen ergänzt (`<Seite>S<nn>`, wörtliche
  Spanne, Offsets, Hinweise, keine Modellaussage). Für Paar 2 ist der Rahmensatz `AS04` (Kern). Ebenfalls neu
  zitierbar sind die Eingangsfragen `AS02` und `AS03` und die Überschriften `AS01` und `BS01`. Das gespeicherte
  Ergebnis von Paar 2 nutzt diese IDs nicht, weil es vorher erzeugt wurde. Für Paar 3 standen sie zur Verfügung,
  und das Modell hat `AS01` dort zusammen mit A01 verwendet.

## Änderung (nur an der Stelle des Verlusts)

- `argument_stage.holder()` bestimmt für eine Ankermenge, wer die Aussage vertritt. Grundlage sind allein die
  Sprechakte des Ergebnisses, nicht das Seitenetikett. Ein offener Sprecher (act `offen`, unsichere
  Sprecherangabe, Interpretation, fehlende Einordnung), gemischte Einordnungen und offene Lesarten bleiben als
  solche markiert.
- Bericht r2 und neuer **Kurzbericht** zeigen „vertreten von“ an Ketten, Fragen, Vergleichen und Zusätzen.
- Prüfregel `attribution_flags`: Ein Hinweis entsteht, wenn der Freitext eines Vergleichs oder Zusatzes eine
  Passage zum Subjekt einer Festlegung macht (behauptet, vertritt, begründet …), deren Anker dort nicht als eigene
  Position eingeordnet sind.
- Am Prompt und an der Modellausgabe ändert sich nichts. Der Test
  `test_reported_thesis_stays_reported_in_comparison_and_short_report` sichert genau diesen Fehler ab.

## Ergebnis auf den gespeicherten Daten (Nachprüfung r2, getrennt abgelegt)

- `validation_recheck.r2.json`: genau ein Zuschreibungshinweis, nämlich an `conclusion_comparison[0].difference`.
  Die übrigen Vergleiche und Zusätze lösen keinen aus.
- [KURZBERICHT.r2.md](KURZBERICHT.r2.md) zum Schluss B-K3: „vertreten von: berichtet: wahrscheinlich die
  Artikelautoren (Zitat) — Sprecher nicht eindeutig“. Im Vergleich A03, A06 ↔ B16 steht für B dieselbe Angabe
  statt einer Position von B.
- Grenze: Die Regel erkennt die typische Formulierung „B … behauptet“, keine umschriebene Zuschreibung. Sie ist ein
  Hinweis für die Durchsicht und ersetzt sie nicht.

Nebenbefund, nicht geändert: Die Hinweisfunktion `speech_cues` vergibt bei einer Überschrift ohne Satzzeichen
„erste Person Singular“. Ursache ist, dass die Satzgrenze in den Folgesatz reicht (`BS01` in Paar 2).
