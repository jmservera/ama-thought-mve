from workbench import NotAllowed, NotFoundError, ValidationError, Workbench

STAGES = ["candidate", "surveyed", "designed", "ready", "installed", "handed_over"]


def raises(exc, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc:
        return True
    return False


def make():
    wb = Workbench()
    wb.add_home("1", "1 A Road", "LS1 1AA")
    wb.add_home("2", "2 B Road", "YO1 7HH")
    return wb, wb.open_case("1", "windows").id, wb.open_case("2", "windows").id


def test_h03_notallowed_is_a_validation_error():
    assert issubclass(NotAllowed, ValidationError)


def test_h03_assigning_an_owned_case_is_not_allowed():
    wb, a, _ = make()
    wb.assign(a, "ana", by="lead")
    assert raises(NotAllowed, wb.assign, a, "ben", by="lead")
    assert wb.get_case(a).owner == "ana"


def test_h03_assign_needs_owner_and_actor():
    wb, a, _ = make()
    assert raises(ValidationError, wb.assign, a, "  ", by="lead")
    assert raises(ValidationError, wb.assign, a, "ana", by="")
    assert wb.get_case(a).owner is None


def test_h03_unowned_case_cannot_be_handed_off():
    wb, a, _ = make()
    assert raises(NotAllowed, wb.request_handoff, a, "ben", by="ana")
    assert wb.pending_handoff(a) is None


def test_h03_decline_keeps_the_owner():
    wb, a, _ = make()
    wb.assign(a, "ana", by="lead")
    wb.request_handoff(a, "ben", by="ana")
    wb.decline_handoff(a, by="ben", reason="no capacity")
    assert wb.get_case(a).owner == "ana"
    assert wb.pending_handoff(a) is None


def test_h03_decline_needs_a_reason():
    wb, a, _ = make()
    wb.assign(a, "ana", by="lead")
    wb.request_handoff(a, "ben", by="ana")
    assert raises(ValidationError, wb.decline_handoff, a, by="ben", reason=" ")
    assert wb.pending_handoff(a) == "ben"


def test_h03_only_the_recipient_can_accept_or_decline():
    wb, a, _ = make()
    wb.assign(a, "ana", by="lead")
    wb.request_handoff(a, "ben", by="ana")
    assert raises(NotAllowed, wb.accept_handoff, a, by="carl")
    assert raises(NotAllowed, wb.accept_handoff, a, by="ana")
    assert raises(NotAllowed, wb.decline_handoff, a, by="carl", reason="not mine")
    assert wb.pending_handoff(a) == "ben" and wb.get_case(a).owner == "ana"


def test_h03_accept_or_decline_without_a_pending_handoff():
    wb, a, _ = make()
    wb.assign(a, "ana", by="lead")
    assert raises(ValidationError, wb.accept_handoff, a, by="ben")
    assert raises(ValidationError, wb.decline_handoff, a, by="ben", reason="none")


def test_h03_only_one_pending_handoff():
    wb, a, _ = make()
    wb.assign(a, "ana", by="lead")
    wb.request_handoff(a, "ben", by="ana")
    assert raises(ValidationError, wb.request_handoff, a, "carl", by="ana")
    assert wb.pending_handoff(a) == "ben"


def test_h03_handoff_to_the_current_owner_is_rejected():
    wb, a, _ = make()
    wb.assign(a, "ana", by="lead")
    assert raises(ValidationError, wb.request_handoff, a, "ana", by="ana")
    assert wb.pending_handoff(a) is None


def test_h03_handed_over_case_cannot_be_handed_off():
    wb, a, _ = make()
    wb.assign(a, "ana", by="lead")
    for s in STAGES[1:]:
        wb.move(a, s, by="ana")
    assert raises(NotAllowed, wb.request_handoff, a, "ben", by="ana")
    assert wb.pending_handoff(a) is None


def test_h03_new_owner_can_hand_off_again():
    wb, a, _ = make()
    wb.assign(a, "ana", by="lead")
    wb.request_handoff(a, "ben", by="ana")
    wb.accept_handoff(a, by="ben")
    assert raises(NotAllowed, wb.request_handoff, a, "carl", by="ana")
    wb.request_handoff(a, "carl", by="ben")
    wb.accept_handoff(a, by="carl")
    assert wb.get_case(a).owner == "carl"


def test_h03_owner_filter_combines_with_other_filters():
    wb, a, b = make()
    c = wb.open_case("1", "solar pv").id
    wb.assign(a, "ana", by="lead")
    wb.assign(b, "ana", by="lead")
    wb.assign(c, "ben", by="lead")
    wb.move(b, "surveyed", by="ana")
    assert [x.id for x in wb.list_cases(owner="ana")] == [a, b]
    assert [x.id for x in wb.list_cases(owner="ana", stage="surveyed")] == [b]
    assert [x.id for x in wb.list_cases(owner="ana", postcode_prefix="LS")] == [a]
    assert wb.list_cases(owner="nobody") == []


def test_h03_handoffs_are_not_stage_history():
    wb, a, _ = make()
    wb.assign(a, "ana", by="lead")
    wb.move(a, "surveyed", by="ana")
    wb.request_handoff(a, "ben", by="ana")
    wb.accept_handoff(a, by="ben")
    assert wb.history(a) == [("candidate", "surveyed", "ana")]
    assert wb.get_case(a).stage == "surveyed"


def test_h03_unknown_case_not_found():
    wb, _, _ = make()
    assert raises(NotFoundError, wb.assign, "C-0099", "ana", by="lead")
    assert raises(NotFoundError, wb.request_handoff, "C-0099", "ben", by="ana")
    assert raises(NotFoundError, wb.pending_handoff, "C-0099")
