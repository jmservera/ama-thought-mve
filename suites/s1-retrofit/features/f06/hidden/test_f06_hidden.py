from workbench import ConsentRequired, NotFoundError, OnHold, Paused, ValidationError, Workbench

STAGES = ["candidate", "surveyed", "designed", "ready", "installed", "handed_over"]


def raises(exc, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc:
        return True
    return False


def make(stage="candidate"):
    wb = Workbench()
    wb.add_home("1", "1 A Road", "LS1 1AA")
    cid = wb.open_case("1", "windows").id
    for s in STAGES[1:STAGES.index(stage) + 1]:
        wb.move(cid, s, by="ana")
    return wb, cid


def test_h06_new_errors_are_validation_errors():
    assert issubclass(ConsentRequired, ValidationError) and issubclass(Paused, ValidationError)


def test_h06_new_case_defaults():
    wb, cid = make()
    case = wb.get_case(cid)
    assert case.consent == "not_required" and case.paused is False


def test_h06_consent_can_be_required_only_once():
    wb, cid = make()
    wb.require_consent(cid, by="ola")
    assert wb.get_case(cid).consent == "required"
    assert raises(ValidationError, wb.require_consent, cid, by="ola")
    wb.record_consent(cid, by="ola")
    assert raises(ValidationError, wb.require_consent, cid, by="ola")
    assert wb.get_case(cid).consent == "given"


def test_h06_consent_can_be_recorded_from_any_other_state():
    wb, cid = make()
    wb.record_consent(cid, by="ola")
    assert wb.get_case(cid).consent == "given"
    assert raises(ValidationError, wb.record_consent, cid, by="ola")


def test_h06_only_given_consent_can_be_withdrawn():
    wb, cid = make()
    assert raises(ValidationError, wb.withdraw_consent, cid, by="ola", reason="x")
    wb.require_consent(cid, by="ola")
    assert raises(ValidationError, wb.withdraw_consent, cid, by="ola", reason="x")
    assert wb.get_case(cid).paused is False and wb.get_case(cid).consent == "required"


def test_h06_withdrawal_needs_a_reason():
    wb, cid = make()
    wb.record_consent(cid, by="ola")
    assert raises(ValidationError, wb.withdraw_consent, cid, by="ola", reason=" ")
    assert wb.get_case(cid).consent == "given" and wb.get_case(cid).paused is False


def test_h06_consent_only_gates_installation():
    wb, cid = make()
    wb.require_consent(cid, by="ola")
    for s in ("surveyed", "designed", "ready"):
        wb.move(cid, s, by="ana")
    assert raises(ConsentRequired, wb.move, cid, "installed", by="ana")
    assert wb.get_case(cid).stage == "ready"
    assert wb.history(cid)[-1] == ("designed", "ready", "ana")


def test_h06_a_paused_case_cannot_move():
    wb, cid = make("surveyed")
    wb.record_consent(cid, by="ola")
    wb.withdraw_consent(cid, by="ola", reason="resident away")
    assert raises(Paused, wb.move, cid, "designed", by="ana")
    assert raises(Paused, wb.move, cid, "ready", by="ana")
    assert raises(Paused, wb.move, cid, "not-a-stage", by="ana")
    assert wb.get_case(cid).stage == "surveyed"


def test_h06_hold_takes_precedence_over_pause():
    wb, cid = make()
    wb.record_consent(cid, by="ola")
    wb.withdraw_consent(cid, by="ola", reason="away")
    wb.place_hold(cid, reason="hazard", by="bea")
    assert raises(OnHold, wb.move, cid, "surveyed", by="ana")
    assert raises(OnHold, wb.move, cid, "not-a-stage", by="ana")


def test_h06_returns_and_handoffs_allowed_while_paused():
    wb, cid = make("designed")
    wb.assign(cid, "ana", by="lead")
    wb.record_consent(cid, by="ola")
    wb.withdraw_consent(cid, by="ola", reason="away")
    wb.return_to(cid, "surveyed", reason="re-survey", by="sam")
    wb.request_handoff(cid, "ben", by="ana")
    wb.accept_handoff(cid, by="ben")
    case = wb.get_case(cid)
    assert case.stage == "surveyed" and case.owner == "ben" and case.paused is True


def test_h06_reopen_does_not_need_consent():
    wb, cid = make("ready")
    wb.record_consent(cid, by="ola")
    wb.move(cid, "installed", by="ana")
    wb.move(cid, "handed_over", by="ana")
    wb.withdraw_consent(cid, by="ola", reason="dispute")
    wb.reopen(cid, reason="defect", by="sam")
    case = wb.get_case(cid)
    assert case.stage == "installed" and case.paused is True


def test_h06_consent_given_again_allows_installation():
    wb, cid = make("ready")
    wb.require_consent(cid, by="ola")
    wb.record_consent(cid, by="ola")
    wb.withdraw_consent(cid, by="ola", reason="away")
    assert raises(Paused, wb.move, cid, "installed", by="ana")
    wb.record_consent(cid, by="ola")
    wb.move(cid, "installed", by="ana")
    assert wb.get_case(cid).stage == "installed"


def test_h06_unknown_case_and_blank_actor():
    wb, cid = make()
    assert raises(NotFoundError, wb.require_consent, "C-0042", by="ola")
    assert raises(NotFoundError, wb.record_consent, "C-0042", by="ola")
    assert raises(NotFoundError, wb.withdraw_consent, "C-0042", by="ola", reason="x")
    assert raises(ValidationError, wb.record_consent, cid, by=" ")
    assert wb.get_case(cid).consent == "not_required"
