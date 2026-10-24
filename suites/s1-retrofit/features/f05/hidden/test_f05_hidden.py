from workbench import InvalidTransition, NotAllowed, NotFoundError, OnHold, ValidationError, Workbench

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


def test_h05_onhold_is_a_validation_error():
    assert issubclass(OnHold, ValidationError)


def test_h05_hold_needs_reason_and_actor():
    wb, cid = make()
    assert raises(ValidationError, wb.place_hold, cid, reason=" ", by="bea")
    assert raises(ValidationError, wb.place_hold, cid, reason="hazard", by="")
    assert wb.get_case(cid).on_hold is False


def test_h05_cannot_hold_twice():
    wb, cid = make()
    wb.place_hold(cid, reason="hazard", by="bea")
    assert raises(ValidationError, wb.place_hold, cid, reason="again", by="bea")
    assert wb.holds(cid) == [("bea", "hazard", None)]


def test_h05_release_needs_an_active_hold():
    wb, cid = make()
    assert raises(ValidationError, wb.release_hold, cid, by="bob", role="building_safety")


def test_h05_every_move_raises_onhold():
    wb, cid = make("surveyed")
    wb.place_hold(cid, reason="hazard", by="bea")
    assert raises(OnHold, wb.move, cid, "designed", by="ana")
    assert raises(OnHold, wb.move, cid, "ready", by="ana")
    assert wb.history(cid) == [("candidate", "surveyed", "ana")]


def test_h05_wrong_role_leaves_the_hold():
    wb, cid = make()
    wb.place_hold(cid, reason="hazard", by="bea")
    for role in ("officer", "manager", "contractor", "safety"):
        assert raises(NotAllowed, wb.release_hold, cid, by="x", role=role)
    assert wb.get_case(cid).on_hold is True
    assert wb.holds(cid) == [("bea", "hazard", None)]


def test_h05_hold_history_over_several_cycles():
    wb, cid = make()
    wb.place_hold(cid, reason="damp", by="bea")
    wb.release_hold(cid, by="bob", role="building_safety")
    wb.place_hold(cid, reason="asbestos", by="cy")
    assert wb.holds(cid) == [("bea", "damp", "bob"), ("cy", "asbestos", None)]
    assert wb.get_case(cid).on_hold is True


def test_h05_held_case_cannot_be_handed_off():
    wb, cid = make()
    wb.assign(cid, "ana", by="lead")
    wb.place_hold(cid, reason="hazard", by="bea")
    assert raises(OnHold, wb.request_handoff, cid, "ben", by="ana")
    assert wb.pending_handoff(cid) is None


def test_h05_pending_handoff_waits_for_release():
    wb, cid = make()
    wb.assign(cid, "ana", by="lead")
    wb.request_handoff(cid, "ben", by="ana")
    wb.place_hold(cid, reason="hazard", by="bea")
    assert raises(OnHold, wb.accept_handoff, cid, by="ben")
    assert wb.get_case(cid).owner == "ana"
    wb.release_hold(cid, by="bob", role="building_safety")
    wb.accept_handoff(cid, by="ben")
    assert wb.get_case(cid).owner == "ben"


def test_h05_decline_allowed_while_on_hold():
    wb, cid = make()
    wb.assign(cid, "ana", by="lead")
    wb.request_handoff(cid, "ben", by="ana")
    wb.place_hold(cid, reason="hazard", by="bea")
    wb.decline_handoff(cid, by="ben", reason="on hold anyway")
    assert wb.pending_handoff(cid) is None


def test_h05_reopen_allowed_while_on_hold():
    wb, cid = make("handed_over")
    wb.place_hold(cid, reason="hazard found after handover", by="bea")
    wb.reopen(cid, reason="hazard", by="sam")
    assert wb.get_case(cid).stage == "installed"
    assert wb.get_case(cid).on_hold is True
    assert raises(OnHold, wb.move, cid, "handed_over", by="ana")


def test_h05_moves_resume_after_release():
    wb, cid = make("ready")
    wb.place_hold(cid, reason="hazard", by="bea")
    wb.release_hold(cid, by="bob", role="building_safety")
    wb.move(cid, "installed", by="ana")
    assert raises(InvalidTransition, wb.move, cid, "ready", by="ana")


def test_h05_unknown_case():
    wb, _ = make()
    assert raises(NotFoundError, wb.place_hold, "C-0042", reason="x", by="bea")
    assert raises(NotFoundError, wb.release_hold, "C-0042", by="bob", role="building_safety")
    assert raises(NotFoundError, wb.holds, "C-0042")
