"""Wörtlich übernommene Funktionen aus Budget-Review (hstre/Budget-Review, MIT, Steffen Rentschler).

Quelle: Commit 6fc50e783d1978c943e081ffcb2cb04d3a6fe547. Die Funktionen liegen dort unter scripts/ und gehören deshalb nicht zum installierbaren
Paket `content-review`, das SuSa-AI für Gate, Verankerung, Abdeckung und Extraktionsvertrag direkt importiert.

Einzige Änderung: In `score` ist das Modulpräfix `cases_module.` entfernt, weil die Funktionen hier im selben
Modul liegen. Der Text wurde per Syntaxbaum aus den Quelldateien gezogen; `tests/test_br_bridge.py` prüft das
gegen eine Kopie der Quelle, sofern vorhanden.
"""
from __future__ import annotations

import json
import re

from budget_review.prompts import RELATION_TYPES

# --- scripts/semantic_cases.py @ 6fc50e783d1978c943e081ffcb2cb04d3a6fe547


def _present(text: str, token: str) -> bool:
    """Whether a token group member occurs in the text.

    A single word is matched on word boundaries, so "kann" does not fire inside
    "bekannt"; a phrase is matched as a substring, since its own boundaries are
    carried by its words. Case is ignored, which is what a rendering check wants.
    """
    needle = token.strip().casefold()
    haystack = text.casefold()
    if not needle:
        return False
    if " " in needle:
        return needle in haystack
    return re.search(rf"\b{re.escape(needle)}\b", haystack) is not None


def satisfies(text: str, groups: list[list[str]]) -> bool:
    """Every group contributes at least one of its renderings."""
    return all(any(_present(text, token) for token in group) for group in groups)


def violates(text: str, forbids: list[str]) -> list[str]:
    """The forbidden patterns this text matches."""
    return [pattern for pattern in forbids if re.search(pattern, text, re.IGNORECASE)]


def distinct_claims(case: dict) -> list[list[list[str]]]:
    """What each separate claim on a multi-assertion span has to carry.

    One entry per claim, and an entry is a list of groups that **one** claim must
    satisfy together. The older shape was one group per claim, which both
    independent reviews broke the same way: a claim consisting of the single word
    "Haushalt" satisfied a group of ["Haushalt", "vier Prozent"], so two bare
    fragments passed a case whose whole point was that two assertions survive.
    A conjunction per claim is the smallest change that makes the requirement
    about the assertion rather than about a keyword.
    """
    return [list(groups) for groups in (case.get("requires_distinct_claims") or [])]


def groups_of(case: dict) -> list[list[str]]:
    """Every requirement group in the case, flattened, for the span check."""
    groups = list(case.get("requires_all_groups") or [])
    for claim_groups in distinct_claims(case):
        groups.extend(claim_groups)
    return groups


def validate(cases: list[dict]) -> list[str]:
    """Every invariant the set has to hold, as a list of failures."""
    problems: list[str] = []
    by_pair: dict[str, list[dict]] = {}
    for case in cases:
        name = case["case_id"]
        document, span = case["document"], case["span"]

        occurrences = document.count(span)
        if occurrences != 1:
            problems.append(f"{name}: span occurs {occurrences} times in the document")

        for index, group in enumerate(groups_of(case)):
            if not any(_present(span, token) for token in group):
                problems.append(
                    f"{name}: requirement group {index} demands a rendering the span "
                    f"does not contain: {group}"
                )

        matched = violates(span, case.get("forbids") or [])
        if matched:
            problems.append(f"{name}: forbids the source's own wording: {matched}")

        for reading in case.get("permitted_readings") or []:
            if not satisfies(reading, case.get("requires_all_groups") or []):
                problems.append(f"{name}: a permitted reading fails the requirements: {reading!r}")
            hit = violates(reading, case.get("forbids") or [])
            if hit:
                problems.append(f"{name}: a permitted reading trips {hit}: {reading!r}")

        for reading in case.get("forbidden_readings") or []:
            fails = not satisfies(reading, case.get("requires_all_groups") or [])
            tripped = bool(violates(reading, case.get("forbids") or []))
            if not (fails or tripped) and case.get("min_claims_on_span", 1) < 2:
                problems.append(
                    f"{name}: a forbidden reading passes every check, so the checks "
                    f"prove nothing here: {reading!r}"
                )

        by_pair.setdefault(case["pair_id"], []).append(case)

    for pair, members in sorted(by_pair.items()):
        languages = sorted(case["language"] for case in members)
        if languages != ["de", "en"]:
            problems.append(f"{pair}: languages {languages}, expected de and en")
            continue
        first, second = members
        for field in ("phenomenon", "min_claims_on_span"):
            if first.get(field) != second.get(field):
                problems.append(f"{pair}: {field} differs between the languages")
        if len(groups_of(first)) != len(groups_of(second)):
            problems.append(f"{pair}: different number of requirement groups per language")
        if len(first.get("forbids") or []) != len(second.get("forbids") or []):
            problems.append(f"{pair}: different number of forbidden patterns per language")
    return problems


# --- scripts/semantic_score.py @ 6fc50e783d1978c943e081ffcb2cb04d3a6fe547


GERMAN_MARKERS = frozenset(
    "der die das und dass nicht den dem ein eine mit im in auf wird werden sei war"
    " ist alle für von zu sich des beim wenn".split()
)


ENGLISH_MARKERS = frozenset(
    "the and that not of to in on is was are were will all for with does if by"
    " from this its".split()
)


def language_of(text: str) -> str:
    """ "de", "en", or "?" when the markers do not separate."""
    words = set(re.findall(r"[\wäöüß]+", text.casefold()))
    german = len(words & GERMAN_MARKERS)
    english = len(words & ENGLISH_MARKERS)
    if german == english:
        return "?"
    return "de" if german > english else "en"


def _folded(text: str) -> str:
    """Whitespace, case and a trailing full stop ignored; nothing else."""
    return " ".join(text.split()).casefold().rstrip(".")


def claims_on_span(claims: list[dict], document: str, span: str) -> list[dict]:
    """Admitted claims whose anchor overlaps the annotated passage."""
    start = document.index(span)
    end = start + len(span)
    return [c for c in claims if c["anchor_start"] < end and c["anchor_end"] > start]


def score(case: dict, claims: list[dict]) -> dict:
    """The outcomes for one case, from the claims the gate admitted on its span."""
    on_span = claims_on_span(claims, case["document"], case["span"])
    contents = [c["canonical_content"] for c in on_span]

    groups = case.get("requires_all_groups") or []
    satisfied = [text for text in contents if satisfies(text, groups)]

    # One entry per claim the span has to carry, and an entry is the groups that
    # *one* claim must satisfy together. A single group per claim let two bare
    # fragments pass; see §3am.
    distinct = distinct_claims(case)
    assigned: list[str] = []
    for claim_groups in distinct:
        for text in contents:
            if text in assigned:
                continue
            if satisfies(text, claim_groups):
                assigned.append(text)
                break
    distinct_met = len(assigned) == len(distinct)

    forbidden_types = {t.lower() for t in (case.get("forbidden_claim_types") or [])}
    # A case's own worked failures. The validator checks that each one violates
    # some requirement, which proves the case is not vacuous; it never checked
    # whether a live claim *is* one. Found by the independent reviews: a forbidden
    # reading standing beside a compliant claim satisfied the requirements and
    # tripped no regex, so the case passed with the invented claim in the graph.
    forbidden_readings = {
        _folded(reading) for reading in (case.get("forbidden_readings") or [])
    }
    distortions = []
    for claim in on_span:
        tripped = violates(claim["canonical_content"], case.get("forbids") or [])
        if tripped:
            distortions.append({"claim": claim["canonical_content"][:90], "forbids": tripped})
        if str(claim["claim_type"]).lower() in forbidden_types:
            distortions.append(
                {"claim": claim["canonical_content"][:90], "claim_type": claim["claim_type"]}
            )
        if _folded(claim["canonical_content"]) in forbidden_readings:
            distortions.append(
                {"claim": claim["canonical_content"][:90], "forbidden_reading": True}
            )

    needed = case.get("min_claims_on_span", 1)
    languages = [language_of(text) for text in contents]
    translated = [
        text
        for text, found in zip(contents, languages, strict=True)
        if found not in (case["language"], "?")
    ]
    return {
        "case_id": case["case_id"],
        "anchored": bool(on_span),
        "claims_on_span": len(on_span),
        "enough_claims": len(on_span) >= needed,
        "requirements_met": bool(satisfied) if groups else True,
        "distinct_met": distinct_met,
        # A distortion now fails the case. It did not before: `distortions` was
        # reported beside `meaning_preserved` and never entered it, so a claim
        # that tripped a forbidden pattern or carried a forbidden claim type
        # still counted as meaning preserved. No run had ever produced one, so
        # no published figure moves — but the check could not have caught it.
        "meaning_preserved": (bool(satisfied) if groups else True)
        and distinct_met
        and len(on_span) >= needed
        and not distortions,
        "distortions": distortions,
        "translated": translated,
        "in_source_language": bool(contents) and not translated,
        "normalised_anchors": sum(1 for c in on_span if c.get("anchor_normalised")),
        "contents": contents,
    }


# --- scripts/two_stage_extract.py @ 6fc50e783d1978c943e081ffcb2cb04d3a6fe547


def relation_prompt(document_id: str, document: str, claims: list[dict]) -> tuple[str, str]:
    """Stage two: edges over a claim list that is already fixed."""
    system = f"""You are a non-authoritative semantic relation sensor.
Return JSON only. Never judge whether a claim is true, good, human-written or AI-written.
The claim list is final: propose no new claims and change none of the given ones.
Allowed relation_type values: {RELATION_TYPES}.
The relation_type field must contain one of those UPPERCASE relation values only. If no
allowed relation fits with high confidence, omit that relation instead of inventing a label.
Relation direction is semantic: source SUPPORTS target; source claim EVIDENCED_BY target
evidence; source broader claim GENERALIZES target narrower basis; source QUALIFIES target;
source premise ENTAILS target conclusion; source example EXAMPLE_OF target general claim;
source part PART_OF target whole.
Use only the given proposal_id values as source_id and target_id.

Return exactly this JSON object, with no extra keys:
{{
  "claims": [],
  "relations": [{{
    "source_id": "C01",
    "relation_type": "DEPENDS_ON",
    "target_id": "C02",
    "confidence": 0.0,
    "rationale": "Short structural reason, not a verdict."
  }}]
}}"""
    listed = "\n".join(
        f"{claim['proposal_id']} [{claim['claim_type']}] {claim['canonical_content']}\n"
        f"    Quoted: {' '.join(claim['raw_span'].split())[:200]}"
        for claim in claims
    )
    user = (
        f"DOCUMENT ID: {document_id}\n\nDOCUMENT:\n{document}\n\nCLAIMS ({len(claims)}):\n{listed}"
    )
    return system, user


def resolved(relations: list[dict], claims: list[dict]) -> tuple[list[dict], list[str]]:
    """Edges whose endpoints stage one actually produced, and the dropped ids.

    Stage two sees a list rather than the packet, so an id it invents would
    otherwise arrive as a relation nobody can resolve. The gate would reject it,
    but rejecting it here keeps the reason attached to the pass that caused it.
    """
    known = {claim["proposal_id"] for claim in claims}
    kept, dropped = [], []
    for relation in relations:
        if relation.get("source_id") in known and relation.get("target_id") in known:
            kept.append(relation)
        else:
            dropped.append(f"{relation.get('source_id')}->{relation.get('target_id')}")
    return kept, dropped
