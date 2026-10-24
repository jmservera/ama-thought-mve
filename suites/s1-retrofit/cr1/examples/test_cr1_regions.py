from workbench import NotAllowed, Workbench


def make():
    wb = Workbench()
    wb.define_region("leeds", ["LS"])
    wb.define_region("york", ["YO"])
    wb.add_home("1", "1 A Road", "LS1 1AA")
    wb.add_home("2", "2 B Road", "YO1 7HH")
    a = wb.open_case("1", "windows").id
    b = wb.open_case("2", "windows").id
    wb.add_user("ana", "officer", ["leeds"])
    wb.add_user("yan", "officer", ["york"])
    wb.add_user("max", "manager", ["leeds", "york"])
    return wb, a, b


def test_cr1_every_home_has_a_region():
    wb, _, _ = make()
    wb.add_home("3", "3 C Road", "M1 1AA")
    assert [wb.region_of(u) for u in ("1", "2", "3")] == ["leeds", "york", "unassigned"]


def test_cr1_users_only_see_their_regions():
    wb, a, b = make()
    view = wb.view_for("ana")
    assert [c.id for c in view.list_cases()] == [a]
    assert [r[0] for r in view.rank_cases()] == [a]
    try:
        view.get_case(b)
    except NotAllowed:
        return
    raise AssertionError("expected NotAllowed")


def test_cr1_cross_region_handoff_needs_a_manager():
    wb, a, _ = make()
    wb.assign(a, "ana", by="lead")
    wb.request_handoff(a, "yan", by="ana")
    assert wb.handoff_needs_approval(a) is True
    try:
        wb.accept_handoff(a, by="yan")
    except NotAllowed:
        pass
    else:
        raise AssertionError("expected NotAllowed")
    wb.approve_handoff(a, by="max")
    wb.accept_handoff(a, by="yan")
    assert wb.get_case(a).owner == "yan"
