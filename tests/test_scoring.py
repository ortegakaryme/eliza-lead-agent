import pytest

from app.models import LeadIn
from app.scoring import score_lead

BASE = {
    "full_name": "Test Lead",
    "phone": "5512345678",
    "business_type": "office",
    "property_type": "office",
    "operation": "lease",
}


def lead(**overrides) -> LeadIn:
    return LeadIn(**{**BASE, **overrides})


@pytest.mark.parametrize(
    "role, budget, timeframe, expected",
    [
        ("decision_maker", 30000, "immediate", "Hot"),
        ("decision_maker", 30000, "1_3_months", "Hot"),
        ("decision_maker", 30000, "3_6_months", "Warm"),
        ("decision_maker", None, "1_3_months", "Warm"),
        ("influencer", 30000, "immediate", "Warm"),
        ("influencer", 30000, "6_plus_months", "Cold"),
        ("decision_maker", None, "undefined", "Cold"),
        ("researching_for_other", None, "undefined", "Cold"),
    ],
)
def test_score_rule(role, budget, timeframe, expected):
    result = score_lead(lead(decision_role=role, budget_max_mxn=budget, timeframe=timeframe))
    assert result.score == expected


def test_reason_is_readable():
    result = score_lead(lead(decision_role="decision_maker", budget_min_mxn=20000, timeframe="3_6_months"))
    assert result.reason == "decision maker ✓ · budget ✓ · timing ✗ (3–6 months)"


def test_zero_budget_means_no_budget():
    result = score_lead(lead(decision_role="decision_maker", budget_min_mxn=0, timeframe="immediate"))
    assert result.score == "Warm"


def test_reversed_budget_range_is_swapped():
    l = lead(decision_role="influencer", timeframe="undefined", budget_min_mxn=50000, budget_max_mxn=20000)
    assert (l.budget_min_mxn, l.budget_max_mxn) == (20000, 50000)


def test_messy_email_is_normalized_or_moved_to_notes():
    assert lead(decision_role="influencer", timeframe="undefined", email=" Ana@Gmail.COM").email == "ana@gmail.com"
    bad = lead(decision_role="influencer", timeframe="undefined", email="ana arroba gmail")
    assert bad.email is None and "ana arroba gmail" in bad.notes


def test_contact_method_required():
    with pytest.raises(ValueError):
        LeadIn(**{**BASE, "phone": None, "decision_role": "influencer", "timeframe": "undefined"})


def test_caller_id_counts_as_contact_and_unset_placeholder_is_ignored():
    l = LeadIn(**{**BASE, "phone": None, "caller_id": "+525511122233",
                  "decision_role": "influencer", "timeframe": "undefined"})
    assert l.best_phone == "+525511122233" and l.source == "Voice agent – phone"
    web = lead(decision_role="influencer", timeframe="undefined", caller_id="None")
    assert web.caller_id is None and web.source == "Voice agent – web"
