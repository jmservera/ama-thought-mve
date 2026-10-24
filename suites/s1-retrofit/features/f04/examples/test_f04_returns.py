from workbench import InvalidTransition, Workbench

STAGES = ["candidate", "surveyed", "designed", "ready", "installed", "handed_over"]


def make(stage="candidate"):
    wb = Workbench()
    wb.add_home("1", "1 A Road", "LS1 1AA")
    cid = wb.open_case("1", "windows").id
    for s in STAGES[1:STAGES.index(stage) + 1]:
        wb.move(cid, s, by="ana")
    return wb, cid


def test_f04_return_to_an_earlier_stage_with_a_reason():
    wb, cid = make("designed")
    wb.return_to(cid, "surveyed", reason="survey incomplete", by="sam")
    assert wb.get_case(cid).stage == "surveyed"
    assert wb.history(cid)[-1] == ("designed", "surveyed", "sam")
    assert wb.notes(cid) == ["survey incomplete"]


def test_f04_cannot_return_to_the_same_or_a_later_stage():
    wb, cid = make("designed")
    for target in ("designed", "ready"):
        try:
            wb.return_to(cid, target, reason="x", by="sam")
        except InvalidTransition:
            continue
        raise AssertionError("expected InvalidTransition")


def test_f04_reopen_a_handed_over_case():
    wb, cid = make("handed_over")
    wb.reopen(cid, reason="defect reported", by="sam")
    assert wb.get_case(cid).stage == "installed"


def test_f04_only_handed_over_cases_can_be_reopened():
    wb, cid = make("installed")
    try:
        wb.reopen(cid, reason="defect", by="sam")
    except InvalidTransition:
        return
    raise AssertionError("expected InvalidTransition")
