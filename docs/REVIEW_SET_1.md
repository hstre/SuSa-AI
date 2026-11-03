# Reale Prüfauswahl 1

Zehn echte Textpaare aus dem Pilot zur Blindbeurteilung. Für diese Auswahl gab es keine Modellaufrufe, und für keines
der Paare liegt ein Modellurteil vor.

## Ablauf

1. `python -m susa serve`, dann **Prüfauswahl** öffnen, Prüfername eingeben, „Beginnen“.
2. Je Paar: beide Originalpassagen mit Kontext davor und danach lesen. Die deutsche Lesehilfe darunter ist eine
   ungeprüfte sinngemäße Zusammenfassung des Kernabschnitts (nicht des Kontexts) und ersetzt nicht das Original.
3. Eigenes Urteil speichern: Beziehungstypen (mehrere möglich, Enthaltung erlaubt), Art des Beitrags,
   Begründung, Belegzitate aus dem englischen Original. Die Zitate werden wie Modellzitate gegen den Text geprüft.
4. Erst danach werden Auswahlgrund (Suchhypothese), Suchwerte und heuristische Hinweise angezeigt. Ein anderer
   Prüfername sieht weiterhin die Blindansicht.

## Auswahl

Deterministisch (Seed 20261103) aus 18.777 Kandidatenpaaren, nur Einheiten ab 80 Tokens, jedes Dokument höchstens
einmal, Reihenfolge gemischt. Je zwei Paare pro Suchhypothese:

| Suchhypothese | Kriterium |
|---|---|
| Wiederholung | beide Suchwege, höchste semantische Ähnlichkeit |
| begründete Erweiterung | oberes Ähnlichkeitsquintil, rechts später publiziert, rechts mit Begründungs- und Bedingungsmarkern |
| Definitionsunterschied | Definitionsmarker auf beiden Seiten und gemeinsamer Kernbegriff |
| möglicher Widerspruch | gegensätzliche historische Upstream-Codes zu `experience_now`, Negation nur auf einer Seite |
| unklarer Fall | eine Zufallskontrolle, ein rein lexikalischer Treffer mittlerer Stärke |

Die Suchhypothesen sind Auswahlgründe, keine richtigen Antworten. Die Heuristiken sind grob; es ist zu erwarten,
dass viele Paare anders zu beurteilen sind als ihre Suchhypothese.

Die Zuordnung steht in [`pilot/review_set_1.json`](../pilot/review_set_1.json), **vor der Blindbeurteilung nicht öffnen**.
Die Datei referenziert die Passagen über Dokument-ID, Zeichenbereich und Text-Hash und enthält keine Originaltexte.
Lesehilfen: [`pilot/reading_aids_rs1.json`](../pilot/reading_aids_rs1.json).

Wiederherstellen nach einem Neuaufbau (Pilottexte müssen abgerufen und segmentiert sein):

```bash
python -m susa review-set import pilot/review_set_1.json
python -m susa review-set load-aids pilot/reading_aids_rs1.json --author "Claude (Claude-Code-Sitzung 3.11.2026), ungeprüft" \
  --method "sinngemäße deutsche Zusammenfassung des Kernabschnitts, keine Übersetzung"
```

## Bekannte Schwächen der Auswahl

- Die Hälfte der Kriterien beruht auf Wortmarkern bzw. den historischen Fremdcodes des Ausgangsprojekts.
- Ein Kernabschnitt endet mit einem Abonnement-Hinweis der Publikation (Extraktion entfernt solche Hinweise nur, wenn sie als Widget markiert sind).
- Kein Paar stammt vom selben Autor, weil der Pilot nur einen Beitrag je Autor enthält. Veränderungen innerhalb
  eines Autorenwerks lassen sich so nicht beobachten.
