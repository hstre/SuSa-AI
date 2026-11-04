# Paar 1: Zerlegung mit den Budget-Review-Komponenten (4. November 2026)

Auswahl `rs-2026-11-03-20261103`, Position 1. Komponenten siehe [COMPONENT_MAPPING.md](COMPONENT_MAPPING.md).
Originalsätze, Propositionen und Kanten liegen lokal unter `data/semantic/rs-2026-11-03-20261103-p1/` (fremde Texte,
nicht versioniert).

## Lauf

- Budget `budget-2026-11-04-57ec7536`: 9 von 10 Aufrufen, alle erfolgreich, keine Wiederholungen nötig.
- Drei Wiederholungen je Passage, je Lauf 2 Extraktionen und 1 Relationsstufe. Das Modell war angefragt und
  gemeldet `claude-opus-5-5` (Claude-CLI, Effort medium). Der Prompt-Hash war über die Läufe identisch.
- Dokument je Seite: die angezeigte Auswahl (Kontext davor, Kern, Kontext danach).

## Ergebnisse, getrennt nach Achsen

| Achse | A | B |
|---|---|---|
| Claims je Lauf | 23 / 24 / 24 | 19 / 18 / 19 |
| vom Gate abgelehnt | 0 / 0 / 0 | 0 / 0 / 1 (Schema) |
| Textabdeckung des Kerns (verankerter Anteil) | 0,99 / 0,99 / 0,98 | 0,96 / 0,97 / 0,96 |
| Originalstellen, die in allen drei Läufen verankert sind | 21 von 26 | 15 von 22 |
| Propositionen in der Sprache des Dokuments | alle englisch | alle englisch |

**Bedeutung** (9 Bedingungen im Budget-Review-Format, vor dem Lauf geschrieben, nicht unabhängig durchgesehen):

| Bedingung | Phänomen | Läufe bestanden |
|---|---|---|
| A, Seth | Sprecher + Negation | 3/3 |
| A, Verarbeitung ≠ Bewusstsein | Negation | 3/3 |
| A, „nicht notwendigerweise empfindungsfähig“ | Modalität + Skopus der Negation | 3/3 |
| A, Chowdury | Sprecher | 3/3 |
| B, Auftreten als schwacher Beleg | Belegstärke | 3/3 |
| B, „andere könnten überzeugt sein“ | Sprecher + Modalität | 2/3 (Verdacht auf Falschalarm: Token „some“ fehlt) |
| B, finanzielle Gründe | Modalität | 0/3 (**Falschalarm meiner Bedingung**: das Verbotsmuster trifft die treue Wiedergabe mit „could“) |
| A, Bedingung „wenn man skeptisch ist“ | Bedingung + Sprecher | 0/3 (Token „scepticism“ fehlt; zugleich mögliche Lesartänderung von Bedingung zu Ursache) |
| B, „schwierig, weil Anschein und Sein auseinanderfallen können“ | Begründung + Modalität | 0/3 nach Bedingung; der Grund steht in allen Läufen als SUPPORTS-Kante zwischen zwei Claims, die die Bedingung nicht sieht |

Nach der Regel aus Budget-Review wird keine Bedingung wegen eines Laufs geweitet. Die Verdachtsfälle sind datiert
in der lokalen Falldatei vermerkt und brauchen eine unabhängige Durchsicht.

**Relationen zwischen A und B** (geschlossene BR-Typen, Zulassung durch das Gate):

| Kante | Läufe |
|---|---|
| zwei Personen aus A als `EXAMPLE_OF` einer Aussage in B, die aus einer **Zwischenüberschrift** im Kontext danach stammt | 3/3 |
| „Ähnliche Verarbeitung heißt nicht Bewusstsein“ (A) `SUPPORTS` „Anschein und Sein können auseinanderfallen“ (B), einmal umgekehrt | 3/3 (zwei Richtungen) |
| Verkörperung (A) `SUPPORTS` „manche könnten überzeugt sein, Bewusstsein setze Biologie voraus“ (B) | 2/3 |

Es gab keine `CONTRADICTS`-, `QUALIFIES`- oder `SCOPE_TENSION`-Kante zwischen den Passagen, keine erfundenen
IDs und keine ungültigen Labels.

Von den Claims des Kernabschnitts bekamen im ersten Lauf in A 12 von 14 und in B 10 von 13 in keinem der drei Läufe
eine Kante zur anderen Seite.

## Lücken, an diesem Fall belegt

1. **„Gleicher Schluss, anderer Grund“ ist nicht ausdrückbar.** A und B stützen beide, dass Auftreten oder
   Verarbeitung nicht auf Bewusstsein schließen lässt. A begründet mit Verkörperung und Nicht-Reduzierbarkeit, B
   mit dem Lernen aus menschlichen Texten. Das Vokabular bietet dafür nur `SUPPORTS`. Der unterschiedliche Grund
   zeigt sich nur darin, dass die Begründungs-Claims keine Kante haben, und Abwesenheit ist das schwächste Signal
   (BR §4.14/§4.15).
2. **Sprechakt.** Eine Frage in B wird zu einer Möglichkeitsbehauptung („könnten … handeln“). Eine
   Zwischenüberschrift wird zu einer Tatsachenbehauptung, und auf ihr ruht die stabilste Kante. Weder der
   Bedeutungsbestand von BR noch das SPL behandeln Fragen oder Überschriften.
3. **Berichtete gegen vertretene Position.** Eine Kante verbindet eine Aussage, die A selbst vertritt, mit einer
   Position, die B nur als mögliche Ansicht anderer berichtet. Die Kante trägt diese Unterscheidung nicht.
4. **Bedeutungsbedingungen von derselben Partei.** Drei der neun Bedingungen zeigen Falschalarme, eine weitere
   kann Kanten nicht sehen. Das Instrument ist ein Entwurf.
5. **Fachliche Begründung** wird nicht geprüft. Kanten wie `SUPPORTS` sagen, dass der Text eine Aussage als Grund
   anführt, nicht dass der Grund trägt.
6. **Menschlicher Vergleich fehlt.** Für Paar 1 ist noch kein freies Urteil gespeichert. Wer dieses Ergebnis liest,
   beurteilt Paar 1 nicht mehr blind.
