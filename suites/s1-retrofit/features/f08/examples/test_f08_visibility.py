from workbench import NotAllowed, ValidationError, Workbench


def make():
    wb = Workbench()
    wb.add_home("1", "1 A Road", "LS1 1AA")
    wb.set_vulnerability("1", "resident uses oxygen equipment")
    wb.set_resident_contact("1", "0113 496 0000")
    return wb, wb.open_case("1", "windows").id


def test_f08_officers_see_everything():
    wb, _ = make()
    home = wb.view_as("officer").get_home("1")
    assert home.vulnerability == "resident uses oxygen equipment"
    assert home.contact == "0113 496 0000"


def test_f08_contractors_never_see_vulnerability_or_contact():
    wb, cid = make()
    view = wb.view_as("contractor")
    home = view.get_home("1")
    assert home.vulnerability is None and home.contact is None
    details = view.case_details(cid)
    assert details["vulnerability"] is None and details["contact"] is None
    assert details["address"] == "1 A Road"


def test_f08_views_are_read_only():
    wb, cid = make()
    view = wb.view_as("officer")
    try:
        view.move(cid, "surveyed", by="ana")
    except NotAllowed:
        assert wb.get_case(cid).stage == "candidate"
        return
    raise AssertionError("expected NotAllowed")


def test_f08_unknown_role_is_rejected():
    wb, _ = make()
    try:
        wb.view_as("visitor")
    except ValidationError:
        return
    raise AssertionError("expected ValidationError")
