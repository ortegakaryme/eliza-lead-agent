"""Lead scoring: a transparent, deterministic rule that lives in code, not in the LLM.

Three signals are checked:
  1. Decision maker   -> the person on the call can sign
  2. Budget defined   -> at least a minimum or a maximum budget was given
  3. Timing <= 3 mo   -> they need to move in within three months

    3 signals -> Hot     2 signals -> Warm     0-1 signals -> Cold

To adjust the rule, edit FAST_TIMEFRAMES or the thresholds in score_lead().
"""
from dataclasses import dataclass

from .models import DecisionRole, LeadIn, Timeframe, notion_label

FAST_TIMEFRAMES = {Timeframe.immediate, Timeframe.one_to_three}


@dataclass(frozen=True)
class ScoreResult:
    score: str   # "Hot" | "Warm" | "Cold"
    reason: str  # e.g. "decision maker ✓ · budget ✓ · timing ✗ (3–6 months)"


def score_lead(lead: LeadIn) -> ScoreResult:
    is_decision_maker = lead.decision_role == DecisionRole.decision_maker
    has_budget = lead.budget_min_mxn is not None or lead.budget_max_mxn is not None
    is_soon = lead.timeframe in FAST_TIMEFRAMES

    signals = [is_decision_maker, has_budget, is_soon]
    met = sum(signals)

    if met == 3:
        score = "Hot"
    elif met == 2:
        score = "Warm"
    else:
        score = "Cold"

    def mark(ok: bool) -> str:
        return "✓" if ok else "✗"

    reason = (
        f"decision maker {mark(is_decision_maker)} · "
        f"budget {mark(has_budget)} · "
        f"timing {mark(is_soon)} ({notion_label(lead.timeframe)})"
    )
    return ScoreResult(score=score, reason=reason)
