# Modellabnahme 1 (synthetische Fälle, 3. November 2026)

Dieser Bericht fasst den ersten echten Modelllauf zusammen. Die vollständigen Ergebnisse stehen in
[acceptance/v2_modell_claude_cli.md](acceptance/v2_modell_claude_cli.md), jeder Aufruf in
[acceptance/v2_modell_aufrufprotokoll.md](acceptance/v2_modell_aufrufprotokoll.md).

**Einordnung:** Getestet wurden 12 kurze, eigens formulierte synthetische Fälle, je Fall genau ein Modellaufruf.
Das sind Funktions- und Plausibilitätstests. Sie zeigen nicht, dass das Werkzeug neue Gedanken in echten
Substack-Texten zuverlässig erkennt.

## Lauf

| | |
|---|---|
| Zugang | angemeldete Claude-Code-CLI (`claude -p`), kein neuer API-Zugang |
| Modell (angefragt / gemeldet) | `claude-opus-5-5` / `claude-opus-5-5` (alle 17 Aufrufe) |
| Einstellungen | Effort `medium`, max. 8.000 Ausgabe-Tokens, keine Werkzeuge, eigener Systemprompt, leeres Arbeitsverzeichnis |
| Prompts | A_reconstruct.v2, B_compare.v2, C_countercheck.v2 |
| Budget | `budget-2026-11-03-bbe2bace`, Obergrenze 20 |
| Verbraucht | 17 Versuche, 17 erfolgreich, 0 Fehler, 0 Wiederholungen, 3 übrig |
| Tokens | 59.246 Eingabe (inkl. Cache-Erstellung), 29.783 Ausgabe |
| Kosten | 0,89 USD Listenpreis-Äquivalent laut CLI (Abo-Nutzung, keine API-Abrechnung) |
| Dauer | 17:53–17:59 UTC |

Vorab geschätzt wurden rund 19.000 Eingabe-Tokens (Zeichen/4). Tatsächlich waren es etwa dreimal so viele, weil die
CLI eigenen Kontext hinzufügt. Für künftige Schätzungen: ca. 3.500 Eingabe- und bis 2.500 Ausgabe-Tokens je Aufruf.

Ablauf: zuerst ein einzelner Testaufruf (Prompt A, Fall 6 DE). Geprüft wurden JSON-Format, Schema, gemeldete
Modellkennung, Verbrauchsangaben, Speicherung von Rohantwort und Aufrufprotokoll sowie die Zitatprüfung. Danach lief
die Abnahme im selben Budget; das Ergebnis des Testaufrufs wurde wiederverwendet statt erneut bezahlt.

## Ergebnisse der Modellteile

| Fall | Sprache | Prompt | Ergebnis | Anmerkung |
|---|---|---|---|---|
| 1 Einschränkung | de | B | bestanden | refines, restricts_scope, challenges_assumption |
| 1 | de | C | formal belegt | Gegenprüfung **korrigiert**: Zusatzannahmen im Primärurteil nicht textgedeckt |
| 2 Definitionen | de | B | bestanden | erwarteter Typ vorhanden, dazu nicht gedeckte Zusatztypen |
| 2 | de | C | formal belegt | Gegenprüfung **korrigiert** auf nur `apparent_conflict_due_to_definition` |
| 2 | en | B | bestanden | wie DE |
| 3 sprachübergreifend | de+en | B | bestanden | `repeats`; das Modell erkennt die Übersetzung (das Retrieval nicht, siehe unten) |
| 4 Metapher | de / en | B | bestanden / bestanden | `repeats`, `rephrasing` |
| 6 Fremdzitat | de / en | A | bestanden / bestanden | Fremdposition `quoted_other`, Einwand `author`, Belege an den erwarteten Stellen |
| 7 empirisch/normativ | de | A | **gescheitert** | Schema: Pflichtfeld `external_source_cited` fehlt. Inhalt sonst passend (getrennte Aussagen, 3 rekonstruierte Voraussetzungen) |
| 7 | en | A | bestanden | aber Bericht und Folgerung in **einer** Behauptung mit beiden Typen, Prüfung hier zu nachsichtig |
| 7 | de | B | bestanden | extends, different_question; contribution `unreasoned_assertion` |
| 9 unbegründet | de | B | **unentscheidbar** | Enthaltung (`unresolved`, `insufficient_context`), obwohl `contribution_kind = unreasoned_assertion` der Erwartung entspricht |
| 10 Systemgrenzen | de / en | B | bestanden / bestanden | system_or_time vorhanden, zusätzlich `apparent_conflict_due_to_definition` |
| 11 Negation | de | B | bestanden | contradicts_under_shared_scope, R ohne Begründung |
| 1, 7, 9, 11 | en | B | nicht ausgeführt | bewusst nicht im Plan (Budget) |
| 12 Versionierung | de | – | bestanden | Replay-Funktionstest, kein Modelllauf |

Zählung der 17 echten Modellprüfungen: 15 bestanden, 1 gescheitert, 1 unentscheidbar. Unter den 15 sind
2 Gegenprüfungen, bei denen „bestanden“ nur formal belegt heißt. Mit Vorbehalt stehen außerdem Fall 2 (DE, EN) und
Fall 10 (DE, EN), deren Primärurteile zusätzliche, nicht gedeckte Typen enthalten, sowie Fall 7 EN (zu nachsichtig
bewertet). Ohne Vorbehalt bestanden damit 8.

## Retrieval (ohne Modell, echtes Embedding-Modell)

| Fall | DE | EN |
|---|---|---|
| 1, 2, 4, 7, 11 | gefunden | gefunden |
| 9 unbegründeter Widerspruch | gefunden (semantisch Rang 14, knapp innerhalb k=15) | **nicht gefunden** (Rang 50/53) |
| 10 Systemgrenzen | **nicht gefunden** (Rang 23/53) | **nicht gefunden** (Rang 23/53) |
| 3 sprachübergreifend | nicht unterstützt (Rang 46/52) | – |
| 5 späte Passage | – | gefunden, Rang 1 |

**Fall 10, Sprache oder Sache:** Die englische Fassung landet gegen das englische Embedding-Modell auf demselben
Rang wie die deutsche. Die Sprache ist also nicht die Ursache. Die beiden Sätze teilen kaum Vokabular („isolated model
… memories between calls“ / „agent … retrieve earlier conversations from a database“), und das Modell setzt sie nicht
nahe beieinander. Genau solche Paare über verschiedene Systemgrenzen verpasst die Suche. Das Sprachmodell bewertet
das Paar korrekt, wenn es ihm vorgelegt wird. Suchparameter wurden nicht angepasst.

## Was die Gegenprüfung zeigt

Beide Gegenprüfungen haben das Primärurteil korrigiert, nicht bestätigt. Beanstandet wurden Beziehungstypen, die
der Text nicht trägt (`refines` ohne erkennbaren Bezug, `challenges_assumption` auf Basis einer stillen Annahme),
eine zu hohe Konfidenz und eine Formulierung im `added_thought`, die nicht im Text steht. Das passt zu einer
Schwäche der Abnahmeregel: Sie verlangt nur, dass *ein* erwarteter Typ vorkommt, und bestraft zusätzliche,
unbelegte Typen nur, wenn sie ausdrücklich ausgeschlossen sind.

## Grenzen dieser Abnahme

- 12 kurze synthetische Fälle, ein Lauf je Fall: Über Stabilität (Wiederholung, Paraphrase) ist nichts bekannt.
- Die Erwartungen stammen aus dem Übergabedokument. Prüfer und Entwickler sind nicht unabhängig, ein
  Prüfbestand wurde nicht zurückgehalten.
- Die Bewertung von Mehrfachetiketten ist nachsichtig (siehe oben).
- Die Prompts sind deutsch; die Rekonstruktionen englischer Texte sind auf Deutsch formuliert, Zitate bleiben englisch.
- Zitatprüfung heißt nur: Der zitierte Text steht so in der Passage. Ob er die Interpretation trägt, prüft der
  Mensch.

## Vorschläge (nicht umgesetzt)

1. Abnahmeregel verschärfen: nicht gedeckte Zusatztypen als eigenes Ergebnis „mit Vorbehalt“ ausweisen.
2. Für Prompt A prüfen, ob `external_source_cited` optional sein soll. Bis dahin bleibt das Feld Pflicht.
3. Gegenprüfung nicht nur stichprobenhaft, sondern für alle als belegt ausgewiesenen Funde vor der menschlichen Prüfung.
4. Fall 10 als Grund für einen zusätzlichen Suchweg aufnehmen (z. B. „gemeinsame Bezugsbehauptung“ über
   rekonstruierte Claims), statt k zu erhöhen.
