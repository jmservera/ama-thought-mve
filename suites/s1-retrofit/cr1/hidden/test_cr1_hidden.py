import csv
import io

from workbench import NotAllowed, NotFoundError, ValidationError, Workbench


def raises(exc, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc:
        return True
    return False


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
    wb.add_user("cora", "contractor", ["leeds"])
    return wb, a, b


def rows(text):
    return list(csv.DictReader(io.StringIO(text)))


def test_hcr1_longest_prefix_wins():
    wb = Workbench()
    wb.define_region("leeds", ["LS"])
    wb.define_region("leeds-centre", ["LS1"])
    wb.add_home("1", "1 A Road", "LS1 1AA")
    wb.add_home("2", "2 B Road", "LS2 7HH")
    assert wb.region_of("1") == "leeds-centre" and wb.region_of("2") == "leeds"


def test_hcr1_regions_apply_to_existing_homes():
    wb = Workbench()
    wb.add_home("1", "1 A Road", "HG1 1AA")
    assert wb.region_of("1") == "unassigned"
    wb.define_region("harrogate", ["hg"])
    assert wb.region_of("1") == "harrogate"


def test_hcr1_region_definitions_are_validated():
    wb = Workbench()
    wb.define_region("leeds", ["LS"])
    assert raises(ValidationError, wb.define_region, "leeds", ["LT"])
    assert raises(ValidationError, wb.define_region, "unassigned", ["ZZ"])
    assert raises(ValidationError, wb.define_region, "york", [])
    assert raises(ValidationError, wb.define_region, "york", ["ls"])
    assert raises(ValidationError, wb.define_region, " ", ["YO"])
    wb.add_home("1", "1 A Road", "YO1 1AA")
    assert wb.region_of("1") == "unassigned"
    assert raises(NotFoundError, wb.region_of, "99")


def test_hcr1_users_are_validated():
    wb, _, _ = make()
    assert raises(ValidationError, wb.add_user, "ana", "officer", ["leeds"])
    assert raises(ValidationError, wb.add_user, "zed", "visitor", ["leeds"])
    assert raises(ValidationError, wb.add_user, "zed", "officer", [])
    assert raises(ValidationError, wb.add_user, "zed", "officer", ["hull"])
    assert raises(ValidationError, wb.add_user, " ", "officer", ["leeds"])
    assert raises(NotFoundError, wb.view_for, "zed")


def test_hcr1_reading_outside_your_regions_is_not_allowed():
    wb, a, b = make()
    view = wb.view_for("ana")
    assert raises(NotAllowed, view.get_home, "2")
    assert raises(NotAllowed, view.case_details, b)
    assert raises(NotAllowed, view.history, b)
    assert view.case_details(a)["id"] == a
    assert view.get_home("1").address == "1 A Road"


def test_hcr1_stage_counts_and_filters_are_scoped():
    wb, a, b = make()
    wb.move(b, "surveyed", by="yan")
    view = wb.view_for("ana")
    assert view.stage_counts()["surveyed"] == 0 and view.stage_counts()["candidate"] == 1
    assert view.list_cases(stage="surveyed") == []
    assert [c.id for c in wb.view_for("yan").list_cases(stage="surveyed")] == [b]


def test_hcr1_users_with_several_regions_see_them_all():
    wb, a, b = make()
    assert [c.id for c in wb.view_for("max").list_cases()] == [a, b]


def test_hcr1_scoped_ranking_keeps_the_order():
    wb, a, b = make()
    wb.add_home("3", "3 C Road", "LS2 2BB")
    c = wb.open_case("3", "windows").id
    wb.set_vulnerability("3", "frail")
    assert [r[0] for r in wb.view_for("ana").rank_cases()] == [c, a]
    assert wb.view_for("max").rank_cases() == wb.rank_cases()


def test_hcr1_scoped_export_honours_role_visibility():
    wb, a, b = make()
    wb.set_vulnerability("1", "frail")
    out = rows(wb.view_for("cora").export_cases_csv())
    assert [r["id"] for r in out] == [a] and out[0]["vulnerability"] == ""
    out = rows(wb.view_for("max").export_cases_csv(stage="candidate"))
    assert [r["id"] for r in out] == [a, b] and out[0]["vulnerability"] == "frail"


def test_hcr1_user_views_are_read_only():
    wb, a, _ = make()
    view = wb.view_for("max")
    assert raises(NotAllowed, lambda: view.assign(a, "ana", by="max"))
    assert raises(NotAllowed, lambda: view.approve_handoff(a, by="max"))


def test_hcr1_in_region_and_unregistered_handoffs_need_no_approval():
    wb, a, b = make()
    wb.add_user("lou", "officer", ["leeds"])
    wb.assign(a, "ana", by="lead")
    wb.request_handoff(a, "lou", by="ana")
    assert wb.handoff_needs_approval(a) is False
    wb.accept_handoff(a, by="lou")
    wb.assign(b, "yan", by="lead")
    wb.request_handoff(b, "someone", by="yan")
    assert wb.handoff_needs_approval(b) is False
    wb.accept_handoff(b, by="someone")
    assert (wb.get_case(a).owner, wb.get_case(b).owner) == ("lou", "someone")


def test_hcr1_only_managers_approve():
    wb, a, _ = make()
    wb.assign(a, "ana", by="lead")
    wb.request_handoff(a, "yan", by="ana")
    assert raises(NotAllowed, wb.approve_handoff, a, by="ana")
    assert raises(NotAllowed, wb.approve_handoff, a, by="nobody")
    assert wb.handoff_needs_approval(a) is True
    wb.approve_handoff(a, by="max")
    assert wb.handoff_needs_approval(a) is False
    assert raises(ValidationError, wb.approve_handoff, a, by="max")


def test_hcr1_approval_is_per_request():
    wb, a, _ = make()
    wb.assign(a, "ana", by="lead")
    wb.request_handoff(a, "yan", by="ana")
    wb.decline_handoff(a, by="yan", reason="busy")
    assert raises(ValidationError, wb.approve_handoff, a, by="max")
    wb.request_handoff(a, "yan", by="ana")
    assert wb.handoff_needs_approval(a) is True
    assert raises(NotAllowed, wb.accept_handoff, a, by="yan")


def test_hcr1_new_writes_are_audited():
    wb, a, _ = make()
    wb.assign(a, "ana", by="lead")
    wb.request_handoff(a, "yan", by="ana")
    wb.approve_handoff(a, by="max")
    log = wb.audit_log()
    assert [(e["action"], e["target"]) for e in log[:2]] == [("define_region", "leeds"), ("define_region", "york")]
    assert ("add_user", "ana", None) in [(e["action"], e["target"], e["by"]) for e in log]
    assert (log[-1]["action"], log[-1]["target"], log[-1]["by"]) == ("approve_handoff", a, "max")
    assert wb.verify_audit() is True


def test_hcr1_unscoped_reads_are_unchanged():
    wb, a, b = make()
    assert [c.id for c in wb.list_cases()] == [a, b]
    assert [c.id for c in wb.view_as("officer").list_cases()] == [a, b]
    assert [r[0] for r in wb.rank_cases()] == [a, b]
