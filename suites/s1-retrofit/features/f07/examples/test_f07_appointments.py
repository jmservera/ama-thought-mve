import datetime

from workbench import ValidationError, Workbench

D1 = datetime.date(2026, 11, 2)
D2 = datetime.date(2026, 11, 9)


def make():
    wb = Workbench()
    wb.add_home("1", "1 A Road", "LS1 1AA")
    return wb, wb.open_case("1", "windows").id


def test_f07_offer_then_confirm():
    wb, cid = make()
    wb.offer_appointment(cid, D2, by="sid")
    wb.offer_appointment(cid, D1, by="sid")
    wb.confirm_appointment(cid, D2, by="sid")
    assert wb.appointments(cid) == [(D1, "offered"), (D2, "confirmed")]


def test_f07_only_offered_dates_can_be_confirmed():
    wb, cid = make()
    try:
        wb.confirm_appointment(cid, D1, by="sid")
    except ValidationError:
        return
    raise AssertionError("expected ValidationError")


def test_f07_only_verified_visits_count():
    wb, cid = make()
    wb.record_no_access(cid, D1, verified=True, by="sid")
    wb.record_no_access(cid, D2, verified=False, by="sid")
    assert wb.no_access_count(cid) == 1
    assert wb.no_access_history(cid) == [(D1, True), (D2, False)]


def test_f07_escalation_after_more_than_five():
    wb, cid = make()
    for day in range(1, 7):
        wb.record_no_access(cid, datetime.date(2026, 11, day), verified=True, by="sid")
    assert [c.id for c in wb.escalated_cases()] == [cid]
