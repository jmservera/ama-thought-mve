from workbench import NotAllowed, NotFoundError, ValidationError, Workbench

KEYS = {"id", "uprn", "address", "postcode", "measure", "stage", "owner", "vulnerability", "contact"}


def raises(exc, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc:
        return True
    return False


def make():
    wb = Workbench()
    wb.add_home("1", "1 A Road", "ls1 1aa")
    wb.add_home("2", "2 B Road", "YO1 7HH")
    return wb, wb.open_case("1", "windows").id, wb.open_case("2", "solar pv").id


def test_h08_homes_start_without_sensitive_data():
    wb, _, _ = make()
    home = wb.get_home("2")
    assert home.vulnerability is None and home.contact is None
    assert (home.uprn, home.address, home.postcode) == ("2", "2 B Road", "YO1 7HH")


def test_h08_setters_validate():
    wb, _, _ = make()
    assert raises(NotFoundError, wb.set_vulnerability, "99", "frail")
    assert raises(ValidationError, wb.set_vulnerability, "1", "  ")
    assert raises(NotFoundError, wb.set_resident_contact, "99", "0113")
    assert raises(ValidationError, wb.set_resident_contact, "1", "")
    assert wb.get_home("1").vulnerability is None and wb.get_home("1").contact is None


def test_h08_case_details_on_the_workbench():
    wb, a, _ = make()
    wb.set_vulnerability("1", "frail")
    wb.set_resident_contact("1", "0113 496 0000")
    wb.assign(a, "ana", by="lead")
    d = wb.case_details(a)
    assert set(d) == KEYS
    assert d == {"id": a, "uprn": "1", "address": "1 A Road", "postcode": "LS1 1AA", "measure": "windows",
                 "stage": "candidate", "owner": "ana", "vulnerability": "frail", "contact": "0113 496 0000"}


def test_h08_contractor_details_hide_only_sensitive_fields():
    wb, a, _ = make()
    wb.set_vulnerability("1", "frail")
    wb.set_resident_contact("1", "0113 496 0000")
    d = wb.view_as("contractor").case_details(a)
    assert set(d) == KEYS
    assert d["vulnerability"] is None and d["contact"] is None
    assert (d["address"], d["postcode"], d["measure"], d["stage"]) == ("1 A Road", "LS1 1AA", "windows", "candidate")


def test_h08_other_roles_see_everything():
    wb, a, _ = make()
    wb.set_vulnerability("1", "frail")
    for role in ("officer", "building_safety", "manager"):
        assert wb.view_as(role).case_details(a)["vulnerability"] == "frail"
        assert wb.view_as(role).get_home("1").vulnerability == "frail"


def test_h08_contractor_view_does_not_change_the_data():
    wb, _, _ = make()
    wb.set_vulnerability("1", "frail")
    wb.set_resident_contact("1", "0113")
    wb.view_as("contractor").get_home("1")
    assert wb.get_home("1").vulnerability == "frail" and wb.get_home("1").contact == "0113"
    assert wb.view_as("officer").get_home("1").vulnerability == "frail"


def test_h08_views_reflect_the_current_state():
    wb, a, _ = make()
    view = wb.view_as("contractor")
    wb.move(a, "surveyed", by="ana")
    assert view.get_case(a).stage == "surveyed"
    assert view.stage_counts()["surveyed"] == 1
    assert view.history(a) == [("candidate", "surveyed", "ana")]


def test_h08_view_lists_support_filters():
    wb, a, b = make()
    view = wb.view_as("contractor")
    assert [c.id for c in view.list_cases()] == [a, b]
    assert [c.id for c in view.list_cases(postcode_prefix="YO")] == [b]
    assert [c.id for c in view.list_cases(measure="windows")] == [a]


def test_h08_view_notes_are_available():
    wb, a, _ = make()
    wb.move(a, "surveyed", by="ana")
    wb.return_to(a, "candidate", reason="access refused", by="sam")
    assert wb.view_as("manager").notes(a) == ["access refused"]


def test_h08_every_write_is_refused_on_a_view():
    wb, a, _ = make()
    view = wb.view_as("manager")
    assert raises(NotAllowed, lambda: view.assign(a, "ana", by="lead"))
    assert raises(NotAllowed, lambda: view.place_hold(a, reason="x", by="bea"))
    assert raises(NotAllowed, lambda: view.set_vulnerability("1", "frail"))
    assert raises(NotAllowed, lambda: view.open_case("1", "solar pv"))
    assert wb.get_case(a).owner is None and wb.get_home("1").vulnerability is None
    assert len(wb.list_cases()) == 2
    for role in ("officer", "contractor", "building_safety", "manager"):
        view = wb.view_as(role)
        history = wb.history(a)
        for case in (view.get_case(a), view.list_cases()[0]):
            for name, value in (("stage", "installed"), ("owner", "intruder")):
                try:
                    setattr(case, name, value)
                except (AttributeError, TypeError, NotAllowed):
                    pass
        assert wb.get_case(a).stage == "candidate" and wb.get_case(a).owner is None
        assert view.get_case(a).stage == "candidate" and view.list_cases()[0].owner is None
        assert wb.history(a) == history
        wb.move(a, "surveyed", by="ana")
        assert view.get_case(a).stage == "surveyed" and view.list_cases()[0].stage == "surveyed"
        wb.return_to(a, "candidate", reason="repeat read check", by="ana")


def test_h08_unknown_ids_on_views():
    wb, _, _ = make()
    view = wb.view_as("officer")
    assert raises(NotFoundError, view.get_home, "99")
    assert raises(NotFoundError, view.case_details, "C-0042")
    assert raises(NotFoundError, wb.get_home, "99")
    assert raises(NotFoundError, wb.case_details, "C-0042")


def test_h08_role_names_are_exact():
    wb, _, _ = make()
    for role in ("officer", "contractor", "building_safety", "manager"):
        wb.view_as(role)
    assert raises(ValidationError, wb.view_as, "Contractor")
    assert raises(ValidationError, wb.view_as, "")
