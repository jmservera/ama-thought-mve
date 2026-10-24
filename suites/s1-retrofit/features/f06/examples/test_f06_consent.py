from workbench import ConsentRequired, Paused, Workbench

STAGES = ["candidate", "surveyed", "designed", "ready", "installed", "handed_over"]


def make(stage="candidate"):
    wb = Workbench()
    wb.add_home("1", "1 A Road", "LS1 1AA")
    cid = wb.open_case("1", "windows").id
    for s in STAGES[1:STAGES.index(stage) + 1]:
        wb.move(cid, s, by="ana")
    return wb, cid


def test_f06_new_cases_do_not_need_consent():
    wb, cid = make("ready")
    assert wb.get_case(cid).consent == "not_required"
    wb.move(cid, "installed", by="ana")
    assert wb.get_case(cid).stage == "installed"


def test_f06_required_consent_blocks_installation_until_given():
    wb, cid = make("ready")
    wb.require_consent(cid, by="ola")
    try:
        wb.move(cid, "installed", by="ana")
    except ConsentRequired:
        pass
    else:
        raise AssertionError("expected ConsentRequired")
    wb.record_consent(cid, by="ola")
    wb.move(cid, "installed", by="ana")
    assert wb.get_case(cid).stage == "installed"


def test_f06_withdrawal_pauses_the_case():
    wb, cid = make()
    wb.record_consent(cid, by="ola")
    wb.withdraw_consent(cid, by="ola", reason="resident in hospital")
    case = wb.get_case(cid)
    assert case.consent == "withdrawn" and case.paused is True
    try:
        wb.move(cid, "surveyed", by="ana")
    except Paused:
        pass
    else:
        raise AssertionError("expected Paused")
    wb.record_consent(cid, by="ola")
    assert wb.get_case(cid).paused is False
    wb.move(cid, "surveyed", by="ana")
