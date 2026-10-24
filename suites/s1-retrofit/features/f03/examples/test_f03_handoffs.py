from workbench import NotAllowed, Workbench


def make():
    wb = Workbench()
    wb.add_home("1", "1 A Road", "LS1 1AA")
    return wb, wb.open_case("1", "windows").id


def test_f03_assign_sets_the_first_owner():
    wb, cid = make()
    assert wb.get_case(cid).owner is None
    wb.assign(cid, "ana", by="lead")
    assert wb.get_case(cid).owner == "ana"


def test_f03_owner_changes_only_when_the_recipient_accepts():
    wb, cid = make()
    wb.assign(cid, "ana", by="lead")
    wb.request_handoff(cid, "ben", by="ana")
    assert wb.pending_handoff(cid) == "ben"
    assert wb.get_case(cid).owner == "ana"
    wb.accept_handoff(cid, by="ben")
    assert wb.get_case(cid).owner == "ben"
    assert wb.pending_handoff(cid) is None


def test_f03_only_the_owner_can_request_a_handoff():
    wb, cid = make()
    wb.assign(cid, "ana", by="lead")
    try:
        wb.request_handoff(cid, "ben", by="carl")
    except NotAllowed:
        return
    raise AssertionError("expected NotAllowed")


def test_f03_filter_by_owner():
    wb, cid = make()
    wb.add_home("2", "2 B Road", "LS1 1AB")
    other = wb.open_case("2", "windows").id
    wb.assign(cid, "ana", by="lead")
    wb.assign(other, "ben", by="lead")
    assert [c.id for c in wb.list_cases(owner="ben")] == [other]
