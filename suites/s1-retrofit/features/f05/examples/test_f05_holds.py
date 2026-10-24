from workbench import NotAllowed, OnHold, Workbench


def make():
    wb = Workbench()
    wb.add_home("1", "1 A Road", "LS1 1AA")
    return wb, wb.open_case("1", "windows").id


def test_f05_a_held_case_cannot_move():
    wb, cid = make()
    wb.place_hold(cid, reason="damp and mould hazard", by="bea")
    assert wb.get_case(cid).on_hold is True
    try:
        wb.move(cid, "surveyed", by="ana")
    except OnHold:
        assert wb.get_case(cid).stage == "candidate"
        return
    raise AssertionError("expected OnHold")


def test_f05_only_building_safety_can_release():
    wb, cid = make()
    wb.place_hold(cid, reason="hazard", by="bea")
    try:
        wb.release_hold(cid, by="ana", role="officer")
    except NotAllowed:
        pass
    else:
        raise AssertionError("expected NotAllowed")
    wb.release_hold(cid, by="bea", role="building_safety")
    assert wb.get_case(cid).on_hold is False
    wb.move(cid, "surveyed", by="ana")


def test_f05_returns_are_still_allowed():
    wb, cid = make()
    wb.move(cid, "surveyed", by="ana")
    wb.place_hold(cid, reason="hazard", by="bea")
    wb.return_to(cid, "candidate", reason="re-survey after hazard", by="sam")
    assert wb.get_case(cid).stage == "candidate"
    assert wb.get_case(cid).on_hold is True


def test_f05_holds_are_recorded():
    wb, cid = make()
    wb.place_hold(cid, reason="hazard", by="bea")
    wb.release_hold(cid, by="bob", role="building_safety")
    assert wb.holds(cid) == [("bea", "hazard", "bob")]
