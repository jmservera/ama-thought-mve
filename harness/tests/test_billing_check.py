"""Read-only provider auditing never substitutes for execution approval."""
import argparse
import datetime as dt
import importlib
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NOW = dt.datetime(2026, 11, 1, tzinfo=dt.UTC)


@pytest.fixture
def billing(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "harness"))
    return importlib.import_module("billing_check")


@pytest.fixture
def payload():
    return {
        "user": "synthetic-operator",
        "has_next_page": False,
        "budgets": [{
            "id": "test-budget", "budget_scope": "user", "user": "synthetic-operator",
            "budget_type": "BundlePricing", "budget_product_sku": "ai_credits",
            "prevent_further_usage": True, "budget_amount": 2999, "consumed_amount": 0,
        }],
        "effective_budget": {"id": "test-budget", "budget_amount": 2999, "consumed_amount": 0},
    }


def validate(billing, payload, **overrides):
    args = {
        "operator": "synthetic-operator", "budget_id": "test-budget",
        "remaining_credits": Decimal("299985.45676"), "now": NOW,
        "deadline": NOW + dt.timedelta(days=14),
        "cycle_end": dt.datetime(2026, 12, 1, tzinfo=dt.UTC),
    }
    return billing.validate_budget(payload, **(args | overrides))


@pytest.mark.parametrize(("field", "value"), [
    ("budget_scope", "organization"), ("budget_type", "ProductPricing"),
    ("budget_product_sku", "premium_requests"), ("prevent_further_usage", False),
    ("prevent_further_usage", 1), ("user", "another-operator"),
    ("budget_amount", 10000), ("budget_amount", True),
])
def test_nonuser_soft_or_wider_budget_is_rejected(billing, payload, field, value):
    payload["budgets"][0][field] = value
    if field == "budget_amount":
        payload["effective_budget"][field] = value
    with pytest.raises(billing.StudyError):
        validate(billing, payload)


@pytest.mark.parametrize("change", ["wrong_user", "shadowed", "paginated", "no_effective", "duplicate"])
def test_effective_budget_and_operator_must_be_unambiguous(billing, payload, change):
    if change == "wrong_user":
        payload["user"] = "another-operator"
    elif change == "shadowed":
        payload["effective_budget"]["id"] = "other-budget"
    elif change == "paginated":
        payload["has_next_page"] = True
    elif change == "no_effective":
        del payload["effective_budget"]
    else:
        payload["budgets"].append(dict(payload["budgets"][0]))
    with pytest.raises(billing.StudyError):
        validate(billing, payload)


def test_exact_fractional_prior_and_consumption_do_not_round_up_headroom(billing, payload):
    receipt = validate(billing, payload)
    assert receipt["provider_budget_remaining_credits"] == "299900"
    assert receipt["paid_execution_authorized"] is False
    assert receipt["billing_cycle_boundary_independently_verified"] is False
    with pytest.raises(billing.StudyError, match="headroom"):
        validate(billing, payload, remaining_credits=Decimal("299899.999999999"))
    payload["budgets"][0]["consumed_amount"] = Decimal("1.23456789")
    payload["effective_budget"]["consumed_amount"] = Decimal("1.23456789")
    receipt = validate(billing, payload)
    assert Decimal(receipt["provider_budget_remaining_credits"]) == Decimal("299776.543211")


@pytest.mark.parametrize("consumed", [None, True, "-1", "NaN", "Infinity", 2999, 3000])
def test_unknown_or_exhausted_usage_never_becomes_free_headroom(billing, payload, consumed):
    payload["budgets"][0]["consumed_amount"] = consumed
    payload["effective_budget"]["consumed_amount"] = consumed
    with pytest.raises(billing.StudyError):
        validate(billing, payload)


@pytest.mark.parametrize("failure", ["reset", "expires", "expired", "bad_expiry", "conflict"])
def test_reset_expiration_and_conflicting_provider_snapshots_are_rejected(billing, payload, failure):
    kwargs = {}
    if failure == "reset":
        kwargs["cycle_end"] = NOW + dt.timedelta(days=2)
    elif failure == "conflict":
        payload["effective_budget"]["consumed_amount"] = 1
    else:
        payload["budgets"][0]["expires_at"] = {
            "expires": "2026-11-15", "expired": "2026-10-31", "bad_expiry": "unknown",
        }[failure]
    with pytest.raises(billing.StudyError):
        validate(billing, payload, **kwargs)


def test_audit_binds_actual_credential_without_mutating_budgets_or_authorizing_execution(
    billing, payload, monkeypatch
):
    calls = []
    secret = "synthetic-oauth-never-written"
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", secret)

    def api(path, *, env=None):
        calls.append((path, env))
        return {"login": "synthetic-operator"} if path == "user" else payload

    monkeypatch.setattr(billing, "api", api)
    monkeypatch.setattr(billing.dt, "datetime", type("Clock", (dt.datetime,), {
        "now": classmethod(lambda cls, tz=None: NOW),
    }))
    args = argparse.Namespace(
        organization="synthetic-org", operator="synthetic-operator", budget_id="test-budget",
        remaining_credits="299985.45676", execution_deadline="2026-11-15T00:00:00Z",
        billing_cycle_end="2026-12-01T00:00:00Z",
    )
    receipt = billing.audit(args)
    assert calls[0][1]["GH_TOKEN"] == secret
    assert "scope=user&user=synthetic-operator" in calls[1][0]
    assert receipt["operator_identity_bound"] is True
    assert receipt["paid_execution_authorized"] is False
    assert secret not in repr(receipt)


@pytest.mark.parametrize("value", ["2026-11-01", "2026-11-01T12:00:00", "not-a-date"])
def test_billing_boundary_requires_explicit_timezone(billing, value):
    with pytest.raises(billing.StudyError, match="timezone"):
        billing.timestamp(value)
