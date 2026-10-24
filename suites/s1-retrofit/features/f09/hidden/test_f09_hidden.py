import datetime

from workbench import Workbench

STAGES = ["candidate", "surveyed", "designed", "ready", "installed", "handed_over"]


def make(n=3):
    wb = Workbench()
    for i in range(1, n + 1):
        wb.add_home(str(i), f"{i} A Road", "LS1 1AA")
    return wb, [wb.open_case(str(i), "windows").id for i in range(1, n + 1)]


def to_stage(wb, cid, stage):
    for s in STAGES[1:STAGES.index(stage) + 1]:
        wb.move(cid, s, by="ana")


def escalate(wb, cid):
    for d in range(1, 7):
        wb.record_no_access(cid, datetime.date(2026, 11, d), verified=True, by="sid")


def test_h09_empty_workbench():
    assert Workbench().rank_cases() == []


def test_h09_ties_break_by_case_id():
    wb, ids = make(3)
    assert wb.rank_cases() == [(i, 0, []) for i in ids]


def test_h09_handed_over_cases_are_excluded():
    wb, (a, b, c) = make(3)
    to_stage(wb, b, "handed_over")
    assert [r[0] for r in wb.rank_cases()] == [a, c]


def test_h09_all_codes_in_order_and_points_add_up():
    wb, (a,) = make(1)
    to_stage(wb, a, "ready")
    wb.set_vulnerability("1", "frail")
    escalate(wb, a)
    wb.record_consent(a, by="ola")
    assert wb.rank_cases() == [(a, 110, ["VULNERABLE", "ESCALATED", "CONSENT_GIVEN", "READY"])]


def test_h09_paused_cases_lose_points():
    wb, (a, b) = make(2)
    wb.record_consent(a, by="ola")
    wb.withdraw_consent(a, by="ola", reason="away")
    assert wb.rank_cases() == [(b, 0, []), (a, -40, ["PAUSED"])]


def test_h09_escalated_cases_gain_points():
    wb, (a, b) = make(2)
    escalate(wb, b)
    assert wb.rank_cases()[0] == (b, 30, ["ESCALATED"])


def test_h09_ready_only_at_stage_ready():
    wb, (a, b) = make(2)
    to_stage(wb, a, "installed")
    to_stage(wb, b, "ready")
    assert wb.rank_cases() == [(b, 10, ["READY"]), (a, 0, [])]


def test_h09_held_cases_first_then_by_score():
    wb, (a, b, c, d) = make(4)
    wb.set_vulnerability("4", "frail")
    wb.place_hold(a, reason="hazard", by="bea")
    wb.place_hold(c, reason="hazard", by="bea")
    wb.set_vulnerability("3", "frail")
    assert wb.rank_cases() == [(c, 50, ["HELD", "VULNERABLE"]), (a, 0, ["HELD"]),
                               (d, 50, ["VULNERABLE"]), (b, 0, [])]


def test_h09_ranking_follows_state_changes():
    wb, (a, b) = make(2)
    assert [r[0] for r in wb.rank_cases()] == [a, b]
    wb.set_vulnerability("2", "frail")
    assert [r[0] for r in wb.rank_cases()] == [b, a]
    wb.place_hold(a, reason="hazard", by="bea")
    assert [r[0] for r in wb.rank_cases()] == [a, b]
    wb.release_hold(a, by="bob", role="building_safety")
    assert [r[0] for r in wb.rank_cases()] == [b, a]


def test_h09_same_state_same_ranking():
    wb, (a, b, c) = make(3)
    wb.set_vulnerability("1", "frail")
    wb.set_vulnerability("3", "frail")
    first = wb.rank_cases()
    assert wb.rank_cases() == first == wb.rank_cases(policy_version="v1")
    assert [r[0] for r in first] == [a, c, b]


def test_h09_views_rank_the_same():
    wb, (a, b) = make(2)
    wb.set_vulnerability("2", "frail")
    assert wb.view_as("contractor").rank_cases() == wb.rank_cases()
    assert wb.view_as("officer").rank_cases() == wb.rank_cases()


def test_h09_reopened_case_is_ranked_again():
    wb, (a, b) = make(2)
    to_stage(wb, a, "handed_over")
    assert [r[0] for r in wb.rank_cases()] == [b]
    wb.reopen(a, reason="defect", by="sam")
    assert [r[0] for r in wb.rank_cases()] == [a, b]


def test_h09_result_types():
    wb, (a,) = make(1)
    wb.set_vulnerability("1", "frail")
    row = wb.rank_cases()[0]
    assert isinstance(row, tuple) and len(row) == 3
    case_id, score, codes = row
    assert case_id == a and isinstance(score, int) and isinstance(codes, list)
    assert all(isinstance(x, str) for x in codes)
