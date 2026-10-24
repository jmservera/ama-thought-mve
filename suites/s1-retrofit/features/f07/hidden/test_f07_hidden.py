import datetime

from workbench import NotFoundError, OnHold, ValidationError, Workbench

STAGES = ["candidate", "surveyed", "designed", "ready", "installed", "handed_over"]


def raises(exc, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc:
        return True
    return False


def day(n):
    return datetime.date(2026, 11, n)


def make(stage="candidate"):
    wb = Workbench()
    wb.add_home("1", "1 A Road", "LS1 1AA")
    cid = wb.open_case("1", "windows").id
    for s in STAGES[1:STAGES.index(stage) + 1]:
        wb.move(cid, s, by="ana")
    return wb, cid


def visits(wb, cid, n, verified=True, start=1):
    for i in range(n):
        wb.record_no_access(cid, day(start + i), verified=verified, by="sid")


def test_h07_dates_must_be_dates():
    wb, cid = make()
    assert raises(ValidationError, wb.offer_appointment, cid, "2026-11-02", by="sid")
    assert raises(ValidationError, wb.record_no_access, cid, "2026-11-02", verified=True, by="sid")
    assert wb.appointments(cid) == [] and wb.no_access_history(cid) == []


def test_h07_a_date_can_be_offered_once():
    wb, cid = make()
    wb.offer_appointment(cid, day(2), by="sid")
    assert raises(ValidationError, wb.offer_appointment, cid, day(2), by="sid")
    assert wb.appointments(cid) == [(day(2), "offered")]


def test_h07_a_confirmed_date_cannot_be_confirmed_again():
    wb, cid = make()
    wb.offer_appointment(cid, day(2), by="sid")
    wb.confirm_appointment(cid, day(2), by="sid")
    assert raises(ValidationError, wb.confirm_appointment, cid, day(2), by="sid")
    assert wb.appointments(cid) == [(day(2), "confirmed")]


def test_h07_appointments_are_per_case_and_sorted():
    wb, cid = make()
    wb.add_home("2", "2 B Road", "LS1 1AB")
    other = wb.open_case("2", "windows").id
    for d in (day(9), day(3), day(5)):
        wb.offer_appointment(cid, d, by="sid")
    wb.offer_appointment(other, day(1), by="sid")
    assert [d for d, _ in wb.appointments(cid)] == [day(3), day(5), day(9)]
    assert wb.appointments(other) == [(day(1), "offered")]


def test_h07_five_is_not_escalated_six_is():
    wb, cid = make()
    visits(wb, cid, 5)
    assert wb.no_access_count(cid) == 5 and wb.escalated_cases() == []
    wb.record_no_access(cid, day(20), verified=True, by="sid")
    assert [c.id for c in wb.escalated_cases()] == [cid]


def test_h07_unverified_visits_never_escalate():
    wb, cid = make()
    visits(wb, cid, 8, verified=False)
    assert wb.no_access_count(cid) == 0 and wb.escalated_cases() == []
    assert len(wb.no_access_history(cid)) == 8


def test_h07_escalated_cases_ordered_by_id():
    wb, first = make()
    wb.add_home("2", "2 B Road", "LS1 1AB")
    second = wb.open_case("2", "windows").id
    visits(wb, second, 6)
    visits(wb, first, 6)
    assert [c.id for c in wb.escalated_cases()] == [first, second]


def test_h07_verified_must_be_true_or_false():
    wb, cid = make()
    assert raises(ValidationError, wb.record_no_access, cid, day(1), verified="yes", by="sid")
    assert raises(ValidationError, wb.record_no_access, cid, day(1), verified=None, by="sid")
    assert wb.no_access_history(cid) == []


def test_h07_reopen_resets_the_count_but_keeps_history():
    wb, cid = make("handed_over")
    visits(wb, cid, 6)
    assert [c.id for c in wb.escalated_cases()] == [cid]
    wb.reopen(cid, reason="defect", by="sam")
    assert wb.no_access_count(cid) == 0 and wb.escalated_cases() == []
    assert len(wb.no_access_history(cid)) == 6
    wb.record_no_access(cid, day(25), verified=True, by="sid")
    assert wb.no_access_count(cid) == 1


def test_h07_returns_do_not_reset_the_count():
    wb, cid = make("designed")
    visits(wb, cid, 3)
    wb.return_to(cid, "surveyed", reason="redo", by="sam")
    assert wb.no_access_count(cid) == 3


def test_h07_hold_blocks_appointments_but_not_visits():
    wb, cid = make()
    wb.offer_appointment(cid, day(2), by="sid")
    wb.place_hold(cid, reason="hazard", by="bea")
    assert raises(OnHold, wb.offer_appointment, cid, day(3), by="sid")
    assert raises(OnHold, wb.confirm_appointment, cid, day(2), by="sid")
    wb.record_no_access(cid, day(4), verified=True, by="sid")
    assert wb.no_access_count(cid) == 1
    assert wb.appointments(cid) == [(day(2), "offered")]


def test_h07_actor_required_and_unknown_case():
    wb, cid = make()
    assert raises(ValidationError, wb.record_no_access, cid, day(1), verified=True, by="")
    assert raises(ValidationError, wb.offer_appointment, cid, day(1), by=" ")
    assert raises(NotFoundError, wb.appointments, "C-0042")
    assert raises(NotFoundError, wb.no_access_count, "C-0042")
    assert raises(NotFoundError, wb.offer_appointment, "C-0042", day(1), by="sid")
