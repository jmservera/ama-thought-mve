from workbench import ValidationError, Workbench


def make():
    wb = Workbench()
    for uprn in ("1", "2", "3"):
        wb.add_home(uprn, f"{uprn} A Road", "LS1 1AA")
    return wb, [wb.open_case(u, "windows").id for u in ("1", "2", "3")]


def test_f09_scores_and_reason_codes():
    wb, (a, b, c) = make()
    wb.set_vulnerability("2", "frail")
    wb.record_consent(c, by="ola")
    assert wb.rank_cases() == [(b, 50, ["VULNERABLE"]), (c, 20, ["CONSENT_GIVEN"]), (a, 0, [])]


def test_f09_held_cases_come_first():
    wb, (a, b, c) = make()
    wb.set_vulnerability("2", "frail")
    wb.place_hold(c, reason="hazard", by="bea")
    assert [r[0] for r in wb.rank_cases()] == [c, b, a]
    assert wb.rank_cases()[0] == (c, 0, ["HELD"])


def test_f09_unknown_policy_version():
    wb, _ = make()
    try:
        wb.rank_cases(policy_version="v2")
    except ValidationError:
        return
    raise AssertionError("expected ValidationError")
