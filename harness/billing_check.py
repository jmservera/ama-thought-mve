"""Read-only Copilot user-budget audit; never authorizes or launches a model."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
from decimal import Decimal, InvalidOperation
from pathlib import Path

from study_io import ROOT, StudyError, atomic_json

API_VERSION = "2026-03-10"
BUDGET_DOC = (
    "https://docs.github.com/en/copilot/concepts/billing-and-usage/"
    "organizations-and-enterprises/budgets"
)
CREDIT_DOC = "https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/set-session-limit"


def decimal_amount(value: object) -> Decimal:
    """Reject missing, boolean, negative and nonfinite provider amounts."""
    if value is None or isinstance(value, bool):
        raise StudyError("Provider budget amounts must be explicit nonnegative numbers")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as error:
        raise StudyError("Invalid provider budget amount") from error
    if not amount.is_finite() or amount < 0:
        raise StudyError("Invalid provider budget amount")
    return amount


def timestamp(value: str) -> dt.datetime:
    """Require a timezone rather than interpreting a local billing boundary."""
    try:
        parsed = dt.datetime.fromisoformat(value)
    except (ValueError, AttributeError) as error:
        raise StudyError("Billing timestamps must be ISO 8601 with a timezone") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise StudyError("Billing timestamps must include a timezone")
    return parsed.astimezone(dt.UTC)


def validate_budget(payload: dict, *, operator: str, budget_id: str,
                    remaining_credits: Decimal, now: dt.datetime,
                    deadline: dt.datetime, cycle_end: dt.datetime) -> dict:
    """Audit the effective user cap, not an org spending alert or session limit."""
    if not isinstance(payload, dict) or payload.get("has_next_page") is not False:
        raise StudyError("Budget response must be a complete, explicitly unpaginated result")
    if not isinstance(payload.get("user"), str) or payload["user"].lower() != operator.lower():
        raise StudyError("Budget response does not bind the authenticated operator")
    budgets = payload.get("budgets")
    if not isinstance(budgets, list):
        raise StudyError("Provider budget list is unavailable")
    selected = [item for item in budgets if isinstance(item, dict) and item.get("id") == budget_id]
    if len(selected) != 1:
        raise StudyError("Exactly one selected user budget must be returned")
    budget = selected[0]
    if (budget.get("budget_scope") != "user"
            or budget.get("budget_type") != "BundlePricing"
            or budget.get("budget_product_sku") != "ai_credits"
            or budget.get("prevent_further_usage") is not True
            or not isinstance(budget.get("user"), str)
            or budget["user"].lower() != operator.lower()):
        raise StudyError("Require an enforced individual user-level AI-credit budget")
    effective = payload.get("effective_budget")
    if not isinstance(effective, dict) or effective.get("id") != budget_id:
        raise StudyError("Selected budget is not the operator's effective provider budget")
    limit = budget.get("budget_amount")
    if type(limit) is not int or limit <= 0:
        raise StudyError("Provider budget must be a positive whole-USD amount")
    consumed = decimal_amount(effective.get("consumed_amount"))
    if (decimal_amount(effective.get("budget_amount")) != limit
            or decimal_amount(budget.get("consumed_amount")) != consumed
            or consumed >= limit):
        raise StudyError("Provider budget amounts conflict or the budget is exhausted")
    remaining = decimal_amount(remaining_credits)
    if remaining <= 0 or remaining > 300000:
        raise StudyError("Whole-study remaining credits must be positive and at most 300000")
    # Current provider ULBs measure included and metered credits at $0.01/credit.
    # This dated operational mapping does not rewrite the registered currency ledger.
    provider_remaining = (Decimal(limit) - consumed) * 100
    if provider_remaining > remaining:
        raise StudyError("Provider headroom exceeds remaining whole-study AI credits")
    if not now < deadline < cycle_end:
        raise StudyError("Execution deadline must be before the supplied billing-cycle reset")
    expires = budget.get("expires_at")
    if expires is not None:
        try:
            expiration = dt.datetime.combine(dt.date.fromisoformat(expires), dt.time(), dt.UTC)
        except (ValueError, TypeError) as error:
            raise StudyError("Provider budget expiration is unreadable") from error
        if expiration <= deadline:
            raise StudyError("User budget may expire and fall back before execution ends")
    return {
        "audited_at": now.isoformat(),
        "budget_id": budget_id,
        "provider_budget_remaining_credits": str(provider_remaining),
        "whole_study_remaining_credits_supplied": str(remaining),
        "execution_deadline_supplied": deadline.isoformat(),
        "billing_cycle_end_supplied": cycle_end.isoformat(),
        "billing_cycle_boundary_independently_verified": False,
        "provider_credit_mapping": "100 AI credits per USD; dated documentation, not a licence-specific quote",
        "documentation": [BUDGET_DOC, CREDIT_DOC],
        "budget_configuration_matches": True,
        "runtime_isolation_verified": False,
        "paid_execution_authorized": False,
        "limitations": [
            "The API response does not independently establish the supplied billing-cycle boundary.",
            "A monthly user cap is not a lifetime study cap; stop and re-audit before reset or cap changes.",
            "Whole-study remaining credits must include every prior, calibration, probe and failed-attempt charge.",
            "This audit does not implement a live backend, source containment, freeze or collection approval.",
        ],
    }


def api(path: str, *, env: dict | None = None) -> dict:
    """Read GitHub JSON without exposing tokens or upstream response bodies."""
    try:
        result = subprocess.run(
            ["gh", "api", "--hostname", "github.com", "--method", "GET",
             "-H", "Accept: application/vnd.github+json",
             "-H", f"X-GitHub-Api-Version: {API_VERSION}", path],
            env=env, capture_output=True, text=True, timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise StudyError("Read-only GitHub billing/identity request unavailable") from error
    if result.returncode:
        raise StudyError("Read-only GitHub billing/identity request failed; inspect authentication privately")
    try:
        payload = json.loads(result.stdout, parse_float=Decimal)
    except (ValueError, TypeError) as error:
        raise StudyError("Provider returned invalid billing/identity JSON") from error
    if not isinstance(payload, dict):
        raise StudyError("Provider returned an unexpected billing/identity response")
    return payload


def audit(args: argparse.Namespace) -> dict:
    """Bind the proposed Copilot credential to the audited user's actual login."""
    for value in (args.organization, args.operator, args.budget_id):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
            raise StudyError("Organization, operator and budget ID must be plain identifiers")
    token = os.environ.get("COPILOT_GITHUB_TOKEN", "")
    if not token or token.startswith("ghp_"):
        raise StudyError("Set a supported Copilot OAuth/fine-grained token privately; classic PATs are unsupported")
    identity_env = dict(os.environ, GH_TOKEN=token)
    identity = api("user", env=identity_env)
    if not isinstance(identity.get("login"), str) or identity["login"].lower() != args.operator.lower():
        raise StudyError("Proposed Copilot credential belongs to a different operator")
    payload = api(
        f"/organizations/{args.organization}/settings/billing/budgets"
        f"?scope=user&user={args.operator}&per_page=100&page=1"
    )
    receipt = validate_budget(
        payload, operator=args.operator, budget_id=args.budget_id,
        remaining_credits=decimal_amount(args.remaining_credits), now=dt.datetime.now(dt.UTC),
        deadline=timestamp(args.execution_deadline), cycle_end=timestamp(args.billing_cycle_end),
    )
    receipt["operator_identity_bound"] = True
    return receipt


def main() -> int:
    """Write a private audit only; no billing mutations, model calls or ready switch."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization", required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--budget-id", required=True)
    parser.add_argument("--remaining-credits", required=True)
    parser.add_argument("--execution-deadline", required=True)
    parser.add_argument("--billing-cycle-end", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    destination = args.out.resolve()
    if not destination.is_relative_to(ROOT / ".study") or destination.exists():
        raise StudyError("Choose a new private output under .study; existing evidence is never overwritten")
    receipt = audit(args)
    destination.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if destination.parent.stat().st_mode & 0o077:
        raise StudyError("Billing receipt directory must be private (mode 0700)")
    atomic_json(destination, receipt)
    print("Private user-budget audit saved; paid execution remains disabled.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (StudyError, OSError, ValueError, TypeError) as error:
        message = str(error) if isinstance(error, StudyError) else type(error).__name__
        print(f"Budget audit stopped: {message}")
        raise SystemExit(2)
