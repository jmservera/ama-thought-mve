from workbench import InvalidTransition, NotFoundError, ValidationError, Workbench

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


def test_h04_return_can_skip_stages():
    wb, cid = make("ready")
    wb.return_to(cid, "candidate", reason="restart", by="sam")
    assert wb.get_case(cid).stage == "candidate"


def test_h04_return_needs_reason_and_actor():
    wb, cid = make("designed")
    assert raises(ValidationError, wb.return_to, cid, "surveyed", reason="  ", by="sam")
    assert raises(ValidationError, wb.return_to, cid, "surveyed", reason="x", by="")
    assert wb.get_case(cid).stage == "designed"
    assert wb.notes(cid) == []


def test_h04_return_to_an_unknown_stage():
    wb, cid = make("designed")
    assert raises(ValidationError, wb.return_to, cid, "demolished", reason="x", by="sam")
    assert wb.get_case(cid).stage == "designed"


def test_h04_nothing_is_earlier_than_candidate():
    wb, cid = make()
    assert raises(InvalidTransition, wb.return_to, cid, "candidate", reason="x", by="sam")


def test_h04_history_records_returns_and_later_moves():
    wb, cid = make("designed")
    wb.return_to(cid, "candidate", reason="restart", by="sam")
    wb.move(cid, "surveyed", by="ana")
    assert wb.history(cid) == [("candidate", "surveyed", "ana"), ("surveyed", "designed", "ana"),
                               ("designed", "candidate", "sam"), ("candidate", "surveyed", "ana")]


def test_h04_forward_moves_stay_one_step_after_a_return():
    wb, cid = make("ready")
    wb.return_to(cid, "surveyed", reason="redesign", by="sam")
    assert raises(InvalidTransition, wb.move, cid, "ready", by="ana")
    wb.move(cid, "designed", by="ana")
    assert wb.get_case(cid).stage == "designed"


def test_h04_notes_keep_reasons_oldest_first():
    wb, cid = make("handed_over")
    wb.reopen(cid, reason="defect reported", by="sam")
    wb.return_to(cid, "designed", reason="new design needed", by="sam")
    assert wb.notes(cid) == ["defect reported", "new design needed"]


def test_h04_notes_empty_and_unknown_case():
    wb, cid = make()
    assert wb.notes(cid) == []
    assert raises(NotFoundError, wb.notes, "C-0042")
    assert raises(NotFoundError, wb.return_to, "C-0042", "candidate", reason="x", by="sam")
    assert raises(NotFoundError, wb.reopen, "C-0042", reason="x", by="sam")


def test_h04_reopen_needs_a_reason_and_is_recorded():
    wb, cid = make("handed_over")
    assert raises(ValidationError, wb.reopen, cid, reason="", by="sam")
    assert wb.get_case(cid).stage == "handed_over"
    wb.reopen(cid, reason="leak", by="sam")
    assert wb.history(cid)[-1] == ("handed_over", "installed", "sam")


def test_h04_reopened_case_can_be_handed_over_again():
    wb, cid = make("handed_over")
    wb.reopen(cid, reason="leak", by="sam")
    wb.move(cid, "handed_over", by="ana")
    assert wb.get_case(cid).stage == "handed_over"


def test_h04_return_cancels_a_pending_handoff():
    wb, cid = make("designed")
    wb.assign(cid, "ana", by="lead")
    wb.request_handoff(cid, "ben", by="ana")
    wb.return_to(cid, "surveyed", reason="redo", by="sam")
    assert wb.pending_handoff(cid) is None
    assert wb.get_case(cid).owner == "ana"
    assert raises(ValidationError, wb.accept_handoff, cid, by="ben")


def test_h04_stage_counts_follow_returns():
    wb, cid = make("ready")
    wb.return_to(cid, "candidate", reason="restart", by="sam")
    counts = wb.stage_counts()
    assert counts["candidate"] == 1 and counts["ready"] == 0
