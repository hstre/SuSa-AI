"""Schema- und Belegprüfung für Modellantworten.

Fünf Ebenen werden getrennt gespeichert und nie ineinander umgerechnet:
  response_status  received | no_response            technisch empfangen?
  schema_status    valid | invalid                   Pflichtfelder, Typen, zulässige Werte
  anchor_status    complete | incomplete | missing_side | none_provided | not_checked
  judgment         das inhaltliche Modellurteil (Beziehungstypen, Entscheidung, Enthaltung)
  (menschliche Prüfung steht ausschließlich in der Tabelle reviews)

Daraus wird evidence_status abgeleitet:
  anchored         Schema gültig, alle Zitate gefunden, auf jeder erforderlichen Seite mindestens eines,
                   und kein Enthaltungsurteil
  abstention       Schema gültig, begründete Enthaltung (insufficient_context / unresolved bzw. undecidable);
                   zulässig, aber KEINE belegte Erweiterung oder Widerlegung
  anchors_failed   Schema gültig, Belege fehlen auf einer Seite oder Zitate sind nicht auffindbar
  schema_invalid   Schemafehler; Inhalt wird nicht als Ergebnis gewertet
  no_response      keine verwertbare Antwort (Transport- oder Parsefehler)
"""
from __future__ import annotations

RELATION_TYPES = ["repeats", "supports", "refines", "extends", "restricts_scope", "challenges_assumption",
                  "contradicts_under_shared_scope", "apparent_conflict_due_to_definition",
                  "apparent_conflict_due_to_system_or_time", "new_evidence_same_claim", "different_question",
                  "insufficient_context", "unresolved"]
ABSTENTION_TYPES = {"insufficient_context", "unresolved"}
CONTRIBUTION_KINDS = ["reasoned_extension", "unreasoned_assertion", "new_evidence_same_claim", "rephrasing", "different_topic", "none", "unclear"]
SPEAKER_ROLES = ["author", "quoted_other", "model_transcript", "hypothetical", "unclear"]
STATEMENT_TYPES = ["empirical", "conceptual", "normative", "speculative"]
TIME_REFS = ["current", "in_principle", "future", "unspecified"]
REASON_KINDS = ["empirical_evidence", "logical_argument", "analogy", "normative_standard", "authority", "other"]
DECISIONS = ["confirmed", "corrected", "rejected", "undecidable"]
CONFIDENCE = ["low", "medium", "high"]

STR, BOOL, NULL = "str", "bool", "null"


def _type_ok(v, types) -> bool:
    for t in types:
        if t == STR and isinstance(v, str):
            return True
        if t == BOOL and isinstance(v, bool):
            return True
        if t == NULL and v is None:
            return True
    return False


class V:
    def __init__(self):
        self.errors: list[str] = []

    def field(self, obj: dict, key: str, types, path: str, enum=None, nonempty_str=False):
        if not isinstance(obj, dict):
            self.errors.append(f"{path}: kein Objekt")
            return None
        if key not in obj:
            self.errors.append(f"{path}.{key}: Pflichtfeld fehlt")
            return None
        v = obj[key]
        if not _type_ok(v, types):
            self.errors.append(f"{path}.{key}: Typ {type(v).__name__}, erwartet {'|'.join(types)}")
            return None
        if enum is not None and v is not None and v not in enum:
            self.errors.append(f"{path}.{key}: unzulässiger Wert {v!r}")
        if nonempty_str and isinstance(v, str) and not v.strip():
            self.errors.append(f"{path}.{key}: leer")
        return v

    def str_list(self, obj: dict, key: str, path: str, enum=None, min_len=0, nullable=False):
        if not isinstance(obj, dict) or key not in obj:
            self.errors.append(f"{path}.{key}: Pflichtfeld fehlt")
            return None
        v = obj[key]
        if v is None and nullable:
            return None
        if not isinstance(v, list):
            self.errors.append(f"{path}.{key}: Typ {type(v).__name__}, erwartet Liste")
            return None
        for i, x in enumerate(v):
            if not isinstance(x, str):
                self.errors.append(f"{path}.{key}[{i}]: kein String")
            elif enum is not None and x not in enum:
                self.errors.append(f"{path}.{key}[{i}]: unzulässiger Wert {x!r}")
        if len(v) < min_len:
            self.errors.append(f"{path}.{key}: mindestens {min_len} Einträge erforderlich")
        return v

    def obj_list(self, obj: dict, key: str, path: str, item_check, min_len=0):
        if not isinstance(obj, dict) or key not in obj:
            self.errors.append(f"{path}.{key}: Pflichtfeld fehlt")
            return None
        v = obj[key]
        if not isinstance(v, list):
            self.errors.append(f"{path}.{key}: Typ {type(v).__name__}, erwartet Liste")
            return None
        for i, x in enumerate(v):
            if not isinstance(x, dict):
                self.errors.append(f"{path}.{key}[{i}]: kein Objekt")
            else:
                item_check(x, f"{path}.{key}[{i}]")
        if len(v) < min_len:
            self.errors.append(f"{path}.{key}: mindestens {min_len} Einträge erforderlich")
        return v


def validate_compare(p: dict) -> list[str]:
    v = V()
    v.field(p, "shared_question", [STR, NULL], "$")
    comp = p.get("comparability") if isinstance(p, dict) else None
    if not isinstance(comp, dict):
        v.errors.append("$.comparability: Pflichtfeld fehlt oder kein Objekt")
    else:
        for k in ("same_question", "definitions_compatible", "same_system_boundary", "same_time_and_modality", "same_premises"):
            v.field(comp, k, [BOOL, NULL], "$.comparability")
        v.field(comp, "notes", [STR], "$.comparability")
    v.str_list(p, "relation_types", "$", enum=RELATION_TYPES, min_len=1)
    v.field(p, "left_claim", [STR], "$", nonempty_str=True)
    v.field(p, "right_claim", [STR], "$", nonempty_str=True)
    v.field(p, "repeated_thought", [STR, NULL], "$")
    v.field(p, "added_thought", [STR, NULL], "$")
    v.field(p, "contribution_kind", [STR], "$", enum=CONTRIBUTION_KINDS)
    v.field(p, "changes_conclusion_or_scope", [BOOL, NULL], "$")
    v.field(p, "reasoning_present_in_text", [BOOL, NULL], "$")
    v.field(p, "reasoning_summary", [STR], "$", nonempty_str=True)
    v.str_list(p, "left_quotes", "$")
    v.str_list(p, "right_quotes", "$")
    v.str_list(p, "alternative_readings", "$")
    v.str_list(p, "uncertainties", "$")
    v.field(p, "interpretation_confidence", [STR], "$", enum=CONFIDENCE)
    return v.errors


def validate_reconstruct(p: dict) -> list[str]:
    v = V()
    status = v.field(p, "status", [STR], "$", enum=["ok", "insufficient_context"])
    v.str_list(p, "missing_information", "$")

    def quoted(x, path, key_text):
        v.field(x, key_text, [STR], path, nonempty_str=True)
        v.field(x, "quote", [STR], path, nonempty_str=True)

    def claim(c, path):
        v.field(c, "claim", [STR], path, nonempty_str=True)
        v.field(c, "speaker_role", [STR], path, enum=SPEAKER_ROLES)
        v.str_list(c, "statement_types", path, enum=STATEMENT_TYPES, min_len=1)
        v.field(c, "subject", [STR], path)
        v.field(c, "system_considered", [STR, NULL], path)
        v.field(c, "time_reference", [STR], path, enum=TIME_REFS)
        v.field(c, "scope", [STR, NULL], path)
        v.field(c, "modality", [STR, NULL], path)
        v.obj_list(c, "explicit_definitions", path, lambda x, pp: (v.field(x, "term", [STR], pp), quoted(x, pp, "definition")))
        v.obj_list(c, "explicit_premises", path, lambda x, pp: quoted(x, pp, "premise"))
        v.str_list(c, "reconstructed_premises", path)
        v.obj_list(c, "reasons", path, lambda x, pp: (quoted(x, pp, "reason"), v.field(x, "kind", [STR], pp, enum=REASON_KINDS),
                                                       v.field(x, "external_source_cited", [STR, NULL], pp)))
        v.obj_list(c, "qualifications", path, lambda x, pp: quoted(x, pp, "text"))
        v.field(c, "conclusion", [STR, NULL], path)
        v.str_list(c, "quotes", path, min_len=1)
        v.str_list(c, "alternative_readings", path)

    claims = v.obj_list(p, "claims", "$", claim)
    if status == "ok" and isinstance(claims, list) and not claims:
        v.errors.append("$.claims: status ok, aber leere Behauptungsliste")
    return v.errors


def validate_countercheck(p: dict) -> list[str]:
    v = V()
    v.field(p, "decision", [STR], "$", enum=DECISIONS)
    v.str_list(p, "problems_found", "$")
    v.str_list(p, "corrected_relation_types", "$", enum=RELATION_TYPES, nullable=True)
    v.field(p, "corrected_added_thought", [STR, NULL], "$")
    v.field(p, "needs_more_context", [BOOL], "$")
    v.field(p, "reasoning", [STR], "$", nonempty_str=True)
    v.str_list(p, "left_quotes", "$")
    v.str_list(p, "right_quotes", "$")
    return v.errors


def anchor_status(sides: dict[str, list[dict]], required_sides: list[str]) -> str:
    """sides: {'left': [quote_check...], 'right': [...]}. Alle Zitate müssen gefunden werden, und jede erforderliche
    Seite braucht mindestens ein gefundenes Zitat."""
    allq = [q for qs in sides.values() for q in qs]
    if not allq:
        return "none_provided"
    if any(not q["found"] for q in allq):
        return "incomplete"
    if any(not any(q["found"] for q in sides.get(s, [])) for s in required_sides):
        return "missing_side"
    return "complete"


def evidence_status(*, schema_errors: list[str], anchors: str, abstention: bool) -> str:
    if schema_errors:
        return "schema_invalid"
    if abstention:
        # Enthaltung braucht keine Belege; vorhandene Zitate müssen trotzdem stimmen
        return "anchors_failed" if anchors == "incomplete" else "abstention"
    return "anchored" if anchors == "complete" else "anchors_failed"
