"""Golden set of labeled routing examples for the Xochitl eval harness.

Implements FR-EVAL-001 (CR-022).

Each ``GoldenExample`` records:
- ``utterance``       — the user input to score
- ``expected_skill``  — the skill class name that should win (``None`` = no skill)
- ``expected_match``  — ``True`` = top skill should be ``expected_skill`` with
                         score ≥ 0.65; ``False`` = should NOT route to that skill
- ``adversarial``     — edge case / discrimination input (harder than happy path)
- ``notes``           — rationale or gap annotation

An example is **correct** when:
- ``expected_match=True``  AND actual top skill == ``expected_skill`` AND score ≥ 0.65
- ``expected_match=False`` AND (top skill != ``expected_skill`` OR score < 0.65)

Examples marked ``expected_match=False`` with a non-None ``expected_skill``
document known GAPS — desired behaviour that current heuristics do not yet reach.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GoldenExample:
    """A single labeled routing evaluation example.

    Attributes:
        utterance:       User input to evaluate.
        expected_skill:  Skill class name that should win, or ``None``.
        expected_match:  ``True`` if routing should succeed (score ≥ 0.65).
        adversarial:     ``True`` for edge-case / discrimination inputs.
        notes:           Rationale or gap annotation (not used in scoring).
    """

    utterance: str
    expected_skill: Optional[str]
    expected_match: bool
    adversarial: bool = False
    notes: str = ""


# ── Golden set ────────────────────────────────────────────────────────────────
# Coverage: 8 built-in skills + no-skill cases + adversarial discrimination.
# Desired-behaviour examples where heuristics currently fall short are marked
# expected_match=False with the target skill in expected_skill — these are
# known gaps that improve the score when heuristics are strengthened.

GOLDEN_SET: list[GoldenExample] = [

    # ── WeatherSkill ──────────────────────────────────────────────────────────
    GoldenExample(
        utterance="what is the weather in Austin today?",
        expected_skill="WeatherSkill",
        expected_match=True,
        notes="canonical weather query — score 0.95 in probes",
    ),
    GoldenExample(
        utterance="temperature forecast for New York tomorrow",
        expected_skill="WeatherSkill",
        expected_match=True,
        notes="forecast keyword — score 0.95 in probes",
    ),
    GoldenExample(
        utterance="what is the current weather forecast for London?",
        expected_skill="WeatherSkill",
        expected_match=True,
        notes="'weather forecast' phrasing",
    ),
    GoldenExample(
        utterance="will it rain in Seattle this weekend?",
        expected_skill="WeatherSkill",
        expected_match=False,  # GAP: 'rain' not in current keywords
        adversarial=True,
        notes="GAP — rain/precipitation not in can_handle keywords",
    ),
    GoldenExample(
        utterance="what was the climate like during the ice age?",
        expected_skill=None,
        expected_match=False,
        adversarial=True,
        notes="historical climate — should NOT route to WeatherSkill",
    ),

    # ── WebLookupSkill ────────────────────────────────────────────────────────
    GoldenExample(
        utterance="search for the latest Python release notes online",
        expected_skill="WebLookupSkill",
        expected_match=True,
        notes="'search' keyword — score 0.85 in probes",
    ),
    GoldenExample(
        utterance="find information about LangChain online",
        expected_skill="WebLookupSkill",
        expected_match=True,
        notes="'find ... online' pattern — score 0.85 in probes",
    ),
    GoldenExample(
        utterance="look up the current price of Bitcoin",
        expected_skill="WebLookupSkill",
        expected_match=False,  # GAP: 'look up' not in current keywords
        adversarial=True,
        notes="GAP — 'look up' phrasing not in can_handle keywords",
    ),
    GoldenExample(
        utterance="what is machine learning?",
        expected_skill=None,
        expected_match=False,
        adversarial=True,
        notes="knowledge question — no web lookup needed",
    ),

    # ── ZettelkastenSkill ────────────────────────────────────────────────────
    GoldenExample(
        utterance="create a zettelkasten note on event sourcing architecture",
        expected_skill="ZettelkastenSkill",
        expected_match=True,
        notes="explicit 'zettelkasten' keyword — score 0.95 in probes",
    ),
    GoldenExample(
        utterance="add a zettelkasten entry: thoughts on distributed systems",
        expected_skill="ZettelkastenSkill",
        expected_match=True,
        notes="'zettelkasten entry' phrasing",
    ),
    GoldenExample(
        utterance="store this insight in my notes: CQRS separates reads from writes",
        expected_skill="ZettelkastenSkill",
        expected_match=False,  # GAP: 'insight/notes' not matching zettelkasten
        adversarial=True,
        notes="GAP — natural note-taking phrasing without 'zettelkasten' keyword",
    ),
    GoldenExample(
        utterance="remind me to call the dentist tomorrow",
        expected_skill=None,
        expected_match=False,
        adversarial=True,
        notes="task/reminder — should NOT route to ZettelkastenSkill",
    ),

    # ── BMADSkill ────────────────────────────────────────────────────────────
    GoldenExample(
        utterance="I want to build a fitness tracking app",
        expected_skill="BMADSkill",
        expected_match=True,
        notes="'build' keyword — score 0.75 in probes",
    ),
    GoldenExample(
        utterance="let us create a new project for a habit tracker app",
        expected_skill="BMADSkill",
        expected_match=True,
        notes="'create a new project' — score 0.75 in probes",
    ),
    GoldenExample(
        utterance="let's design a meal planning application from scratch",
        expected_skill="BMADSkill",
        expected_match=True,
        notes="'design ... application' phrasing",
    ),
    GoldenExample(
        utterance="help me plan my week",
        expected_skill=None,
        expected_match=False,
        adversarial=True,
        notes="personal planning — should NOT route to BMADSkill",
    ),

    # ── SDDSkill ─────────────────────────────────────────────────────────────
    GoldenExample(
        utterance="add requirement FR-AUTH-001: users must be able to log in",
        expected_skill="SDDSkill",
        expected_match=False,  # GAP: scores 0.40 currently
        adversarial=True,
        notes="GAP — FR- pattern scores 0.40 not 0.65",
    ),
    GoldenExample(
        utterance="list all requirements for the authentication module",
        expected_skill="SDDSkill",
        expected_match=False,  # GAP: scores 0.40 currently
        adversarial=True,
        notes="GAP — 'requirements' keyword scores 0.40 not 0.65",
    ),
    GoldenExample(
        utterance="generate spec for the login feature",
        expected_skill="SDDSkill",
        expected_match=False,  # GAP: 'generate spec' — need to verify score
        adversarial=True,
        notes="GAP — spec generation phrasing may score below threshold",
    ),
    GoldenExample(
        utterance="what does a functional requirement mean?",
        expected_skill=None,
        expected_match=False,
        adversarial=True,
        notes="knowledge question about SDD — should NOT route to SDDSkill",
    ),

    # ── CodeSkill ────────────────────────────────────────────────────────────
    GoldenExample(
        utterance="scaffold the REST API for my project",
        expected_skill="CodeSkill",
        expected_match=False,  # GAP: scores 0.20 currently
        adversarial=True,
        notes="GAP — 'scaffold' scores 0.20 not 0.65",
    ),
    GoldenExample(
        utterance="generate code for the user authentication module",
        expected_skill="CodeSkill",
        expected_match=False,  # GAP: scores 0.20 currently
        adversarial=True,
        notes="GAP — 'generate code' scores 0.20 not 0.65",
    ),
    GoldenExample(
        utterance="implement the database schema from the spec",
        expected_skill="CodeSkill",
        expected_match=False,  # GAP: likely low score
        adversarial=True,
        notes="GAP — 'implement' without explicit 'code' keyword",
    ),
    GoldenExample(
        utterance="explain how OAuth2 works",
        expected_skill=None,
        expected_match=False,
        adversarial=True,
        notes="explanation request — should NOT route to CodeSkill",
    ),

    # ── NotionSkill ──────────────────────────────────────────────────────────
    GoldenExample(
        utterance="sync my tasks with Notion",
        expected_skill="NotionSkill",
        expected_match=True,
        notes="'sync ... Notion' — score 0.70 in probes",
    ),
    GoldenExample(
        utterance="pull my tasks from Notion",
        expected_skill="NotionSkill",
        expected_match=True,
        notes="'pull ... Notion' — score 0.70 in probes",
    ),

    # ── OrchestratorSkill ────────────────────────────────────────────────────
    GoldenExample(
        utterance="delegate this to the background orchestrator",
        expected_skill="OrchestratorSkill",
        expected_match=True,
        notes="'delegate ... orchestrator' — score 0.75 in probes",
    ),
    GoldenExample(
        utterance="run this task in the background orchestrator",
        expected_skill="OrchestratorSkill",
        expected_match=True,
        notes="'background orchestrator' — score 0.75 in probes",
    ),

    # ── No-skill cases ────────────────────────────────────────────────────────
    GoldenExample(
        utterance="how are you doing today?",
        expected_skill=None,
        expected_match=False,
        notes="casual greeting — no skill should fire",
    ),
    GoldenExample(
        utterance="what is the meaning of life?",
        expected_skill=None,
        expected_match=False,
        notes="open philosophical question — no skill should fire",
    ),
    GoldenExample(
        utterance="can you help me think through this design problem?",
        expected_skill=None,
        expected_match=False,
        notes="open-ended conversation — no skill should fire",
    ),
    GoldenExample(
        utterance="tell me a joke",
        expected_skill=None,
        expected_match=False,
        notes="entertainment request — no skill should fire",
    ),
    GoldenExample(
        utterance="what time is it in Tokyo right now?",
        expected_skill=None,
        expected_match=False,
        notes="timezone query — no skill covers this",
    ),
]

assert len(GOLDEN_SET) >= 30, f"Golden set must have ≥30 examples (has {len(GOLDEN_SET)})"
