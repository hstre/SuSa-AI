# Prüfauswahl rs-2026-11-03-20261103: gemeinsame Auswertung der Paare 1–10

Stand 4. November 2026. Auswahl, Reihenfolge und Textversionen sind unverändert (eingefrorene Auswahl,
`items_sha256` eb4f480c…). Die Modelleingaben enthielten nur die Passagen (Kontext davor, Kern, Kontext danach) und
deren Extraktion. Suchhypothese, Auswahlgrund und bisherige Einschätzungen waren nicht enthalten.

Diese Auswertung ist meine Durchsicht (Claude, dieselbe Modellfamilie wie das Werkzeug). Sie ist keine unabhängige
Modellprüfung und kein menschlicher Goldstandard. Aus zehn Paaren werden keine Precision-, Recall- oder
Zuverlässigkeitswerte abgeleitet.

## Entstehung der Ergebnisse

| Paar | Grundlage | Prompt | Software (Lauf) | Extraktion | Darstellung |
|---|---|---|---|---|---|
| 1 | **nachbearbeitete Referenz**: von Claude in der Sitzung aus 3 gespeicherten Läufen interpretiert, Fassung v2 korrigiert (v1 erhalten). Keine Ausgabe der Argumentstufe | – | `df57db0` (v1), `0a56f52` (v2) | 3 Läufe mit Relationsstufe | `PAIR1_ARGUMENT_ANALYSIS.md` |
| 2 | Argumentstufe; erster Versuch ungültig (geteilte CLI-Antwort), zweiter gültig | D_argument.v1 | `df57db0`+ (ohne Satzstellen) | 1 Lauf | r1 (Rohfassung), r2 (Kurzbericht mit Sprecher), Spur der Zuschreibung |
| 3 | Argumentstufe | D_argument.v1 | `0a56f52`+ (mit Satzstellen) | 1 Lauf | r2 |
| 4–5, 7–10 | Argumentstufe im Stapellauf | D_argument.v1 | `c8ee71d`+Laufdatei-Korrektur (`af36e7a`) bis `341e5d7` (danach nur Doku und eine Meldung geändert) | 1 Lauf | r3 |
| 6 | **nicht abgeschlossen**: Extraktion B ungültig (siehe [pair6/STATUS.md](pair6/STATUS.md)) | – | – | A gültig, B ungültig | – |

- Prompt D_argument.v1 ist für alle Läufe gleich. Er beschränkt Zusätze nicht auf solche, die den Schluss der
  anderen Passage ändern; deshalb gibt es keine neue Prompt-Version.
- Die Engführung stand im Kurzbericht r2 („ändert er eine Schlussfolgerung?“). r3 fragt neutral nach Zusatz,
  Grundlage und Bezug; r2-Dateien bleiben unverändert liegen.
- Die Versionsangabe in `runs.code_version` lautet `0.3.0+<commit>`, weil das installierte Paket die Versionsnummer
  nicht nachgeführt hat; maßgeblich ist der Commit.

## Übersicht

„Durchsicht“ heißt: Bestätigt, schränkt ein oder korrigiert meine Durchsicht den zentralen Befund des Werkzeugs?
Anker-IDs beziehen sich auf die jeweiligen `inputs.json`. Details stehen in `pairN/REVIEW_NOTES.md`.

| Paar | Frage(n) | wichtigster begründeter Zusatz | Art | wesentliche Unsicherheit oder Fehlinterpretation | Durchsicht |
|---|---|---|---|---|---|
| 1 (Referenz) | teilweise gemeinsam: Lässt sich aus äußerer Ähnlichkeit auf Bewusstsein schließen? | A+1: inhaltliche Gründe gegen den Schluss (Verkörperung, nicht allein auf Berechnung reduzierbar; A08/A10/A12). B+1: Mechanismus, warum äußere Anzeichen täuschen (B19–B21) | gleicher Schluss, andere Gründe; zusätzliche Begründung | Meine eigene v1 verstärkte „not … alone“ zu „Nicht-Berechenbarkeit“ (in v2 korrigiert). In einem der Läufe wurde eine Frage zur Behauptung (B16) | Referenz, nicht geprüft |
| 2 | überwiegend verschieden: A, ob man „bullshit“ verwenden soll; B, ob der Begriff zutrifft und warum „Halluzination“ falsch ist | B+1: B begründet (B11, Kontext danach) die Prämisse, die A nur einräumt (A04/A06) | zusätzliche Begründung; andere Fragestellung | Aus der berichteten These wurde im Vergleich eine eigene von B. Behoben in der Darstellung r2, siehe [pair2/ZUSCHREIBUNG.md](pair2/ZUSCHREIBUNG.md). Der Rahmensatz von A war ohne Anker | bestätigt; Zuschreibung im Vergleich korrigiert |
| 3 | teilweise gemeinsam (F1: wovon hängt der Weg der Menschheit ab); sonst verschieden | A+3 (A09): Steuerung am Rand schränkt A04 ein; im Verhältnis zu B14 nur eine Spannung | Einschränkung (eigene); andere Fragestellung | B+2: angekündigtes Argument („could argue“) als Aussage wiedergegeben. A04: eine von zwei Lesarten im Vergleich festgelegt | bestätigt |
| 4 | verschieden, mit parallelem Muster (beide verneinen einen Anschein) | A+3 (A16–A18): mechanistische Begründung der Verneinung, die B fehlt | zusätzliche Begründung; andere Fragestellung | A+3 überzeichnet: Aus „man kann es so codieren“ und „metaphorisch so nennen“ wird „lässt sich darauf zurückführen … nur metaphorisch“. F1 setzt Problemlösefähigkeit und „Erwachen“ unter einer abstrakten Frage gleich | schränkt ein |
| 5 | gemeinsam: Ist die Bewusstseinsfrage noch bloß philosophisch? | B+2 (B05–B08): B bindet die Folgenschwere an die Bedingung des Funktionalismus, A nicht. Dazu A+2 (A02/A03): historischer Grund, warum die Frage philosophisch bleiben konnte | Einschränkung (Voraussetzung sichtbar); zusätzliche Begründung | B+1 gibt B09 ohne die Bedingung wieder, die das Werkzeug an anderer Stelle selbst festhält | bestätigt |
| 6 | – | – | – | nicht abgeschlossen | – |
| 7 | gemeinsam: unter welchen Bedingungen KI-Systeme bewusst werden könnten | B+3 (B17): schwellenhafter Einsatz statt Kontinuum (A10/A11) als Teilfrage. B+4 (B04/B05): Messproblem, das A voraussetzt | andere Fragestellung (Teilfrage); Präzisierung | Vergleich: „Beide halten … für erreichbar“, obwohl B es nur für das Gedankenexperiment annimmt (B14). Die interne Prüfung von A ist stark (bedingte Frage wird zur Behauptung) | bestätigt, mit Einschränkung |
| 8 | verschieden (klinische Prüfbarkeit von Erklärungen gegenüber der Beziehung Mensch–Werkzeug) | keiner mit Bezug | andere Fragestellung | leicht: A+1 ohne „may“, A+2 ergänzt eine „gewollte Abwägung“ | bestätigt |
| 9 | teilweise gemeinsam: Wie erscheinen LLMs ihren Nutzern? | A+1 (A09): Die Ich-Ansprache ist bewusst gestaltet; das Werkzeug nennt das eine mögliche Gegenlesart zu B06 und vermerkt, dass A diesen Schluss nicht zieht | Voraussetzung sichtbar; andere Fragestellung | B-K1 trennt Verhalten (Turing-Test) und Verstehen richtig. Kleine Ergänzungen über den Text hinaus | bestätigt |
| 10 | teilweise gemeinsam: Was folgt aus der fehlenden Definition für Urteile über KI und für Vorsicht? | B+1 (B14/B15): Vorsicht begründet mit den Kosten eines Irrtums statt mit Nichtwissen (A19, berichtet). B+5 (B18): Beweisstandard präzisiert | gleiche Richtung, anderer Grund; Präzisierung | Der mögliche Widerspruch zu A21 (Kontext danach) ist richtig offen gelassen. „Beide setzen voraus“ überzeichnet A18 | bestätigt |

## Untersuchungsfrage

**Findet das Werkzeug bereits nachvollziehbar begründete zusätzliche Gedanken?** Ja, in mehreren Fällen. Jeweils
mit Textstelle und mit einem Bezug zur gemeinsamen Frage, der sich nachprüfen lässt:

- **Paar 5:** B macht eine Voraussetzung sichtbar (Folgenschwere nur unter Funktionalismus), die A nicht trifft.
- **Paar 10:** gleiche Richtung, anderer Grund. B begründet Vorsicht mit den Kosten eines Irrtums, der berichtete
  Appell in A mit Nichtwissen.
- **Paar 9:** Die bewusste Gestaltung der Ich-Ansprache in A ist ein möglicher Einwand gegen die Deutung von B. Das
  Werkzeug hält fest, dass A ihn nicht selbst erhebt.
- **Paar 2:** B liefert Gründe für eine Prämisse, die A nur einräumt.
- **Paar 7:** schwellenhaft gegen kontinuierlich als eigene Teilfrage.

Wo kein Zusatz mit Bezug vorliegt, sagt das Werkzeug das auch (Paar 8; weitgehend Paar 3 und 4). Fragen und
Überschriften wurden in keinem Lauf zu Behauptungen. Berichtete Stimmen sind auf Ebene der Sprechakte durchweg
richtig getrennt (Zitat und Kommentar in Paar 4, Steelmanning in Paar 10, Gedankenexperiment in Paar 7).

**Welche wiederkehrenden Fehler verhindern derzeit eine verlässliche Nutzung?**

1. **Die Festlegung wird beim Zusammenfassen verstärkt.** Das ist der häufigste Fehler. Möglichkeit, Bedingung,
   Annahme oder angekündigtes Argument werden in Zusätzen und Vergleichen zur Feststellung:
   - Paar 3, B+2 („could argue“);
   - Paar 4, A+3 („can“ → „lässt sich zurückführen“, dazu „nur“);
   - Paar 5, B+1 (Bedingung weggelassen);
   - Paar 7, Vergleich (Annahme fürs Beispiel → „halten für erreichbar“);
   - Paar 8, A+1 („may“).

   Auffällig ist: Dasselbe Ergebnis ordnet die Stelle bei den Sprechakten oder offenen Lesarten jeweils richtig
   ein. Der Fehler ist also eine Inkonsistenz zwischen den Ebenen einer Ausgabe, keine fehlende Information.
2. **Gemeinsame Festlegung in Formeln mit „Beide …“.** Paar 2, 7 und 10. Die Zuschreibungsregel erkennt nur
   „B … behauptet“ und schlägt hier nicht an; der Kurzbericht zeigt den Sprecher aber richtig an.
3. **Gleichsetzung über eine abstrakte gemeinsame Frage.** Paar 4 (Problemlösen gegenüber „Erwachen“), schwächer
   Paar 9. Der Unterschied wird im Freitext benannt, die Einstufung „teilweise gemeinsam“ bleibt.
4. **Schlüsse aus dem Kontext statt aus dem Kern.** Das betrifft fast jedes Paar. Das Werkzeug weist es aus,
   ebenso fehlende Begründungen außerhalb des Ausschnitts (Paar 4, 8, 10). Stillschweigend ergänzter Kontext kam
   nur in kleinen Folgerungen vor (Paar 8, A+2; Paar 9, „nicht unreflektierbar“).
5. **Prüfhinweise sind grob.**
   - Die Verstärkungsmarker erkennen echte Fälle (Paar 3, 4, 8), schlagen aber überwiegend falsch an:
     Konjunktiv, Präteritum, Konditionalsatz mit „wer“, aufgelöste Verneinung.
   - Der Kurzbericht schreibt bei einer Annahme („offen“) „Sprecher nicht eindeutig“, obwohl der Sprecher klar und
     nur die Festlegung offen ist. Fehlt die Sprecherangabe, steht „–“.
6. **Formatfehler bei der Extraktion.** Paar 6: zuerst ein JSON mit deutschen Propositionen, dann eine
   Selbstkorrektur in derselben Antwort. Das war 1 von 14 Extraktionsaufrufen dieses Durchlaufs. Der Parser hat
   die Antwort korrekt abgelehnt; das Paar blieb offen.
7. **Grenzen jeder Aussage hier.** Pro Paar gibt es nur einen Extraktionslauf und einen Lauf der Argumentstufe.
   Der Prüfer gehört zur selben Modellfamilie. Es gibt kein menschliches Urteil zu diesen Paaren.

## Verbrauch

| Budget | Zweck | Aufrufe | Listenpreis-Äquivalent (Rechengröße) |
|---|---|---|---|
| budget-2026-11-04-57ec7536 | Paar 1, 3 Läufe | 9 | 0,91 USD |
| budget-2026-11-04-b1eee8bf | Paar 2 (davon 1 ungültig) | 4 | 1,13 USD |
| budget-2026-11-04-8f9189f5 | Paar 3 | 3 | 0,65 USD |
| budget-2026-11-04-68ee171e | Paare 4–10 | 20 von 21 (1 ungültige Extraktion, Paar 6) | 3,55 USD |

- **Paare 4–10:** etwa 89.000 Eingabe- und 147.000 Ausgabe-Token. Extraktionen 1,19 USD, Argumentstufe 2,36 USD.
- **Tatsächliche Zusatzkosten: keine.** Jede Antwort meldete `isUsingOverage: false` und `overageStatus: rejected`
  (Zusatznutzung auf Organisationsebene deaktiviert). Das Listenpreis-Äquivalent stammt aus der CLI und ist keine
  Abrechnung.
- **Pause:** Vor Paar 9 stand das Fünf-Stunden-Kontingent bei 90 % (`allowed_warning`). Der Lauf pausierte, ohne
  einen Aufruf zu verbrauchen, und wurde nach dem Zurücksetzen fortgesetzt.

## Empfehlung für den nächsten Schritt

Als Nächstes sollte Steffen einige Paare blind beurteilen, nicht weitere Paare automatisch gerechnet werden.

- **Welche Paare:** 5, 9, 10 und 2. Dort behauptet das Werkzeug nachvollziehbare Zusätze.
- **Wie:** mit der vorhandenen Blindansicht und deren HTML-Fassung, ohne Modellaufruf. Danach wird das
  Werkzeugergebnis seinem freien Urteil gegenübergestellt.
- **Warum:** Offen ist nicht mehr, ob das Werkzeug Kandidaten findet. Offen ist, ob die gefundenen Zusätze aus
  fachlicher Sicht relevant sind und ob die Fehler aus Punkt 1 den Befund dort ändern. Meine Durchsicht kann das
  nicht klären, weil sie aus derselben Modellfamilie kommt.

Daneben, ohne Modellaufrufe und klein gehalten:

- **Konsistenzprüfung der Ebenen** (wiederkehrender Fehler 1): Steht für einen Anker ein „offen“, eine Bedingung
  oder eine Möglichkeit in den Sprechakten oder offenen Lesarten, muss die Wiedergabe in Zusätzen und Vergleichen
  einen entsprechenden Marker tragen; sonst gibt es einen Hinweis. Dazu die Zuschreibungsregel um Formeln mit
  „Beide …“ erweitern.
- **Paar 6 abschließen:** 2 Aufrufe in einem neuen Budget, ohne Wiederholung der Extraktion A.

Weitere Paare, Wiederholungsläufe zur Stabilität oder eine Änderung am Prompt würde ich erst danach angehen.
