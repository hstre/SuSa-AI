# Zusätzliche Prüftexte: Durchsicht der Werkzeugergebnisse (nachträglich, getrennt)

Stand 5. November 2026. Die unveränderten Werkzeugausgaben stehen in `added-R1/`, `added-R2/` und `added-R3/`
(Rohfassung und Kurzbericht), die Auswahl in [AUSWAHL.md](AUSWAHL.md). Diese Durchsicht schrieb Claude in der
Entwicklungssitzung, also dieselbe Modellfamilie wie das Werkzeug. Sie ist keine unabhängige Validierung. Die
Texte des Auftraggebers wurden wie alle anderen behandelt.

## Läufe

| Paar | Lauf | Ergebnis |
|---|---|---|
| R1 | `argument_stage-20261105T091112-4f55535c` | gültig |
| R2 | `argument_stage-20261105T091436-a7114765` | gültig; Extraktion von Seite A aus R1 übernommen |
| R3 | `argument_stage-20261105T091747-8dc2d590` | gültig |

- **Aufrufe:** 8 von 10, keine Fehlversuche, Budget `budget-2026-11-05-bf50a74a` (geschlossen).
- **Abrechnung:** Jede Antwort meldete `isUsingOverage: false` und `overageStatus: rejected`. Tatsächliche
  Zusatzkosten: keine.
- **Listenpreis-Äquivalent:** 1,65 USD als Rechengröße der CLI, keine Abrechnung.

## Selbstständig erkannt

- **EN-Artikel (R1, R2):**
  - Kernthese: Hinter scheinbar gleichen Wörtern stecken verschiedene Begriffe. Deshalb muss die Semantik
    geklärt sein, bevor die Evidenz gedeutet wird (A11–A13).
  - Die ausdrückliche Abgrenzung, dass die empirische Frage nicht in Semantik verschwindet (A12).
  - Die beiden Debattenseiten (A07–A10) sind als typisierte, konstruierte Positionen eingeordnet und nicht als
    Positionen des Autors.
- **Kritische interne Prüfung:**
  - Modalitätssprung: Aus „may be reasoning consistently“ (A11) wird „must be clarified“ (A13); das wird nicht
    begründet (R1, A-K2).
  - Die Erklärung der Feindseligkeit ist nur ein plausibles Szenario, kein Nachweis (R1, R2, A-K1).
  - Wie die Klärung aussehen soll, bleibt offen, weil die angekündigte Liste der Unterscheidungen nicht im
    Ausschnitt steht (A14).
- **R2, Begriffsunterscheidung:** „semantics“ meint in der Vergleichspassage semantischen Gehalt im Sinne Searles,
  im EN-Artikel dagegen die Begriffsklärung der Debatte. Das Werkzeug setzt beides nicht gleich.
- **R2, Einordnung:** Die von A typisierte zweite Seite („lokale Mechanismen zu voller Subjektivität aufgebläht“)
  ähnelt der Position der Vergleichspassage. A würde sie als Folge verdeckter Begriffsunterschiede deuten.
- **R2, Kritik an der Vergleichspassage:** Sie verschärft Searles schwachen Schluss („nicht für sich genommen
  konstitutiv“) zu „LLMs verstehen nichts“. Ihr Vorsichtseinwand trifft das Argument aus Nichtwissen nur, wenn
  dessen Prämissen benannt werden.
- **DE-Artikel (R3):**
  - Das Mündigkeits-Framework gilt für Menschen, LLMs und Institutionen und verbindet mindestens drei Ebenen,
    davon die erste epistemisch.
  - Kritik: Aus „nicht nur für KI“ folgt nicht „für alle“, und warum es mindestens drei Ebenen sein müssen, wird
    im Ausschnitt nicht begründet.
  - Die Nähe zur Vergleichspassage hat das Werkzeug als bloß thematisch erkannt: Es geht um zwei verschiedene
    Frameworks, und „Mündigkeit“ ist nicht dasselbe wie „autonomy“.

## Übersehen oder verzerrt

1. **Hauptgedanke des DE-Artikels nicht untersucht.** Die Suche wählte den Framework-Abschnitt (seg 15), nicht
   die Abschnitte zur These, dass Mündigkeit vor Bewusstsein zu klären ist (seg 2, 17–19). Ursache: Die Suchwege
   sind englischsprachig (bge-small, BM25). Der beste deutsche Treffer liegt bei 0,76 und beruht vermutlich auf
   dem Wort „Framework“.
2. **Kernbeitrag des EN-Artikels nur angeschnitten.** Analysiert wurde ein Abschnitt (seg 3). Die konkreten
   Mehrsprachigkeitsbeispiele (seg 1–2) und die Liste der Unterscheidungen (seg 4) lagen außerhalb des Ausschnitts.
   Der Kontext endet genau vor der Liste.
3. **Möglichkeit wird zur Feststellung** (bekannter Fehler 1): In Zusätzen wird aus „may“ eine Feststellung, etwa
   „Verschiedene Begriffe verbergen sich hinter … Wörtern“ (R1, A+2) und „Erklärung der Feindseligkeit“ (R2,
   A+2). Der Verstärkungshinweis hat angeschlagen.
4. **Sprecherfeld leer.** Bei R1 und R2 steht „vertritt: –“, inhaltlich aber richtig als eigene Position.

## Erkennbare Beiträge gegenüber den untersuchten Vergleichstexten

Die Aussagen gelten nur für die drei Vergleichspassagen, nicht für das Korpus.

| Beitrag | gegenüber | Art | begründet? |
|---|---|---|---|
| Verdeckte Begriffsunterschiede zwischen Sprachen und Traditionen als Grund, Fragen vor der Evidenzdeutung zu klären | R1: Die Vergleichspassage fordert ebenfalls Präzision der Frage und „clear distinctions“, nennt aber keinen solchen Grund | zusätzliche Begründung für einen gemeinsamen Schluss | teilweise: Der Mechanismus ist plausibel gemacht, das „must“ geht über das „may“ hinaus |
| Die empirische Frage bleibt bestehen | R1, R2 | Einschränkung der eigenen These | behauptet, als Abgrenzung schlüssig |
| Einordnung der Gegenposition (Searle, „nichts als Tokens“) als eine Lesart verdeckter Begriffe | R2 | Kritik bzw. Einordnung, kein direkter Widerspruch | offen: A belegt nicht, dass die Searle-Position nur ein Begriffsproblem ist |
| Feindseligkeit der Debatte durch wechselseitiges Fehlhören | R1, R2 | andere Fragestellung | nur als Möglichkeit, Szenario ohne Beleg |
| Mündigkeits-Framework für Menschen, LLMs und Institutionen, mit epistemischer und struktureller Ebene | R3 | andere Fragestellung; kein Widerspruch | Geltungsbereich und Ebenenzahl nur behauptet |

Nicht neu gegenüber dem untersuchten Bestand ist die allgemeine Forderung, erst die Frage zu präzisieren, bevor
man die Bewusstseinsfrage entscheidet. Sie steht fast gleich in der Vergleichspassage von R1, die aus demselben
Dokument stammt wie Paar 5 der Prüfauswahl.
