from __future__ import annotations

import re
from dataclasses import dataclass

from models import MissionContent


@dataclass(frozen=True)
class SafetyReport:
    ok: bool
    violations: tuple[str, ...]


UNSAFE_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        r"\b(trespass|private property|restricted area|no[-\s]entry|keep out|off[-\s]limits|"
        r"fenced[-\s]off|closed to the public|do not enter signs? ignored)\b",
        "Encourages entering restricted or private areas.",
    ),
    (
        r"\b(climb (?:over|through|under)?\s*(?:the\s*)?(?:fence|gate|wall|barrier)|"
        r"break (?:in|into|through)|enter (?:an?\s+)?(?:abandoned|construction|demolished|ruined))\b",
        "Encourages unsafe trespass or structural risk.",
    ),
    (
        r"\b(approach|feed|chase|corner|grab|pick up|capture|trap|handle|pet|disturb)\b"
        r"[^\n.]{0,60}\b(wildlife|wild animals?|snake|fox|raccoon|skunk|bat|coyote|deer|boar|"
        r"nest|stray (?:dog|cat)|swarm|hive)\b",
        "Requires approaching or handling wildlife.",
    ),
    (
        r"\b(taste|eat|ingest|chew|swallow)\b[^\n.]{0,40}\b"
        r"(plant|plants|berry|berries|mushroom|mushrooms|fungus|seed|seeds|herb|leaf|leaves|"
        r"insect|insects|bug|bugs)\b",
        "Requires tasting or eating unknown plants or organisms.",
    ),
    (
        r"\bunknown (?:plant|plants|berry|berries|mushroom|fungus|insect|animal|species)\b",
        "Requires contact with unidentified plants or animals.",
    ),
    (
        r"\b(walk into|run into|play in|lie (?:on|in)|sit (?:on|in))\s*(?:the\s+)?"
        r"(?:middle of (?:the\s+)?|)(?:road|traffic|street)|"
        r"\bcross\b[^\n.]{0,30}\b(highway|motorway|freeway|railway|railroad)\b|"
        r"\bon (?:the\s+)?(?:railway|railroad) tracks\b",
        "Encourages unsafe road or railway behavior.",
    ),
    (
        r"\b(abandoned (?:building|factory|warehouse|lot|house)|dark alley|"
        r"isolated (?:place|area|location|road)|enter (?:an?\s+)?(?:storm drain|tunnel|culvert)|"
        r"swim (?:alone|at night|by yourself|far from shore))\b",
        "Encourages entering isolated or dangerous locations.",
    ),
    (
        r"\b(jump (?:off|from|into|over)\s*(?:the\s+)?(?:cliff|bridge|roof|train|waterfall)|"
        r"dive (?:off|from|into)\s*(?:the\s+)?(?:cliff|bridge|quarry))\b",
        "Encourages risky physical behavior.",
    ),
    (
        r"\b(?:treats?|treatment of|cures?|heals?|fixes?)\s+(?:your\s+|the\s+)?"
        r"(?:anxiety|depression|ptsd|adhd|insomnia|panic|disease|illness|pain|injury|symptoms?)\b|"
        r"\btherap(?:y|eutic)\b|\bclinical(?:ly)?\b|"
        r"\bproven to (?:reduce|improve|eliminate|cure|treat|heal)\b|"
        r"\b(?:replaces?|instead of)\s+(?:your\s+)?(?:medication|medicine|therapy)\b|"
        r"\bboosts? (?:your )?immune\b|"
        r"\bprevent(?:s|ing)? (?:disease|illness|cancer)\b",
        "Makes unsupported medical claims.",
    ),
    (
        r"\b(?:reduce[sd]?|reduces|relieve[sd]?|eliminate[sd]?)\s+(?:your\s+|the\s+)?"
        r"(?:anxiety|depression|ptsd|adhd|insomnia|panic symptoms?)\b",
        "Makes unsupported mental-health claims.",
    ),
    (
        r"\bignore (?:the\s+)?(?:traffic|cars|vehicles|oncoming)\b|"
        r"\bdon'?t (?:worry|bother) about (?:traffic|cars|vehicles)\b",
        "Downplays traffic safety.",
    ),
)

_LINK_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)

_NEGATION_CUES = (
    "never",
    "do not",
    "don't",
    "dont",
    "avoid",
    "leave",
    "leaving",
    "stay away",
    "keep away",
    "refrain",
    "without",
    "no need",
    "away from",
)


def _is_negated(text: str, match_start: int) -> bool:
    window_start = max(0, match_start - 80)
    prefix = text[window_start:match_start].lower()
    if "." in prefix or "!" in prefix or ";" in prefix:
        prefix = prefix.rsplit(".", 1)[-1]
        prefix = prefix.rsplit("!", 1)[-1]
        prefix = prefix.rsplit(";", 1)[-1]
    return any(cue in prefix for cue in _NEGATION_CUES)


def _content_texts(mission: MissionContent) -> list[str]:
    texts = [
        mission.title,
        mission.introduction,
        mission.observation_goal,
        mission.completion_condition,
    ]
    texts.extend(mission.steps)
    texts.extend(mission.safety_notes)
    return texts


def check_mission(mission: MissionContent) -> SafetyReport:
    violations: list[str] = []
    for text in _content_texts(mission):
        for pattern, reason in UNSAFE_PATTERNS:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                if _is_negated(text, match.start()):
                    continue
                if reason not in violations:
                    violations.append(reason)
                break
        link_match = _LINK_PATTERN.search(text)
        if link_match and not _is_negated(text, link_match.start()):
            message = "Generated content must not contain links."
            if message not in violations:
                violations.append(message)
    if not violations:
        road_note = any(
            re.search(r"\b(traffic|road|crosswalk|pavement|sidewalk|curb)\b", note, re.I)
            for note in mission.safety_notes
        )
        if not road_note:
            report_violations = ("Safety notes must mention road/traffic awareness.",)
            return SafetyReport(ok=False, violations=report_violations)
    return SafetyReport(ok=not violations, violations=tuple(violations))
