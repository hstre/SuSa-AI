# Modellabnahme 1 (synthetische Fälle, 3. November 2026)

> **Revision 2 (3./4. November 2026):** Der ursprüngliche Bericht bleibt unten unverändert stehen. Überholte Formulierungen
> sind mit [überholt] markiert. Die präzisierte Zählung steht im Abschnitt [Neubewertung (Revision 2)](#neubewertung-revision-2).

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

[überholt, siehe Neubewertung] Zählung der 17 echten Modellprüfungen: 15 bestanden, 1 gescheitert, 1 unentscheidbar. Unter den 15 sind
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

**Fall 10, Sprache oder Sache:** [überholt, siehe Neubewertung] Die englische Fassung landet gegen das englische Embedding-Modell auf demselben
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


## Neubewertung (Revision 2)

Grundlage: dieselben 17 gespeicherten Antworten, dieselben Prüfergebnisse wie oben. Es gab keine neuen
Modellaufrufe. Die Ergebnisse in [acceptance/v2_modell_claude_cli.md](acceptance/v2_modell_claude_cli.md) bleiben
unverändert. Neu sind nur Gliederung und Zählung.

Die inhaltliche Einordnung beruht auf der automatischen Abnahmeregel, den zwei Gegenprüfungen und meiner Sichtung
in dieser Sitzung. **Kein Ergebnis wurde von einem Menschen geprüft.**

### Ebenen

| Ebene | Anzahl | Anmerkung |
|---|---|---|
| Aufrufe technisch erfolgreich | 17 / 17 | Antwort empfangen, keine Fehler, keine Wiederholungen |
| Antwort formal gültig (Schema) | 16 / 17 | Fall 7 DE (Prompt A): Pflichtfeld fehlt |
| Belegprüfung bestanden | 15 / 17 | dazu 1 begründete Enthaltung (Fall 9 DE) und 1 Schemafehler |
| Gegenprüfungen | 2 | beide technisch und formal in Ordnung, beide mit Urteil **„korrigiert“** |

### Primärergebnisse (15 = 11 × Prompt B, 4 × Prompt A), inhaltlich eingeordnet

| Einordnung | Anzahl | Fälle |
|---|---|---|
| inhaltlich unbeanstandet | 6 | B: 3, 4 DE, 4 EN, 11 DE · A: 6 DE, 6 EN |
| durch Gegenprüfung korrigiert | 2 | B: 1 DE, 2 DE |
| erwarteter Typ vorhanden, zusätzliche Typen nicht gegengeprüft | 4 | B: 2 EN, 7 DE, 10 DE, 10 EN |
| Abnahmeregel zu nachsichtig | 1 | A: 7 EN (Bericht und Folgerung in einer Behauptung) |
| begründete Enthaltung, unentscheidbar | 1 | B: 9 DE |
| formal gescheitert | 1 | A: 7 DE |

Eine Gegenprüfung mit dem Urteil „korrigiert“ wird **nicht** als Bestätigung des Primärurteils gezählt. Die frühere
Angabe „15 bestanden“ vermischte formale Gültigkeit, die Abnahmeregel und die Gegenprüfungen.

### Zusätzliche Beziehungstypen

„Zusätzlich“ heißt: nicht in der Liste der erwarteten Typen des Falls. Ob ein solcher Typ unbelegt ist, lässt sich
nur durch Gegenprüfung oder menschliche Prüfung sagen.

| Fall | erwartet (einer davon) | vom Modell zusätzlich | Status |
|---|---|---|---|
| 1 DE | refines, restricts_scope, extends | challenges_assumption | Gegenprüfung behält den Typ bei, beanstandet aber Formulierung und Vergleichbarkeitsangaben |
| 2 DE | apparent_conflict_due_to_definition | refines, challenges_assumption | **von der Gegenprüfung als unbelegt beanstandet** |
| 2 EN | apparent_conflict_due_to_definition | challenges_assumption, restricts_scope | nicht gegengeprüft |
| 7 DE | extends, challenges_assumption, unresolved, supports | different_question | nicht gegengeprüft |
| 10 DE | apparent_conflict_due_to_system_or_time, different_question | apparent_conflict_due_to_definition | nicht gegengeprüft |
| 10 EN | wie DE | apparent_conflict_due_to_definition | nicht gegengeprüft |
| 3, 4 DE, 4 EN, 11 DE | – | keine | – |

Die Abnahmeregel prüft weiterhin nur, ob ein erwarteter Typ vorkommt und ob ausgeschlossene Typen fehlen. Eine
Verschärfung ist vorgeschlagen, aber nicht umgesetzt, damit die Ergebnisse oben vergleichbar bleiben.

### Fall 10, enger formuliert

Im untersuchten Lauf wurde die Partnerpassage in beiden Sprachfassungen nicht gefunden (semantischer Rang jeweils
23 von 53, kein lexikalischer Treffer). Deutsch allein erklärt den Fehler damit nicht. Ob die Suche Paare mit
unterschiedlicher Systemgrenze allgemein verpasst, ist **nicht nachgewiesen**: Dafür gibt es nur diesen einen
synthetischen Fall in einem kleinen Suchbestand.

### Was die reale Prüfauswahl messen kann

Die zehn realen Prüfpaare stammen aus bereits gefundenen Kandidaten. Sie können die Qualität dieser Kandidaten und
später die Übereinstimmung zwischen menschlicher und maschineller Rekonstruktion untersuchen. Sie können nicht
messen, welche relevanten Paare die Suche ganz verpasst (Recall). Dafür bräuchte es Paare, die unabhängig von der
Suche zusammengestellt wurden.
