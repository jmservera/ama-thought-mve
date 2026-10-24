from workbench import InvalidTransition, NotFoundError, ValidationError, Workbench

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
    return wb


def test_h02_full_path_to_handed_over():
    wb = make()
    c = wb.open_case("1", "windows")
    for s in STAGES[1:]:
        wb.move(c.id, s, by="ana")
    assert wb.get_case(c.id).stage == "handed_over"
    assert [h[1] for h in wb.history(c.id)] == STAGES[1:]


def test_h02_no_move_after_handed_over():
    wb = make()
    c = wb.open_case("1", "windows")
    for s in STAGES[1:]:
        wb.move(c.id, s, by="ana")
    assert raises(InvalidTransition, wb.move, c.id, "candidate", by="ana")


def test_h02_backwards_move_rejected():
    wb = make()
    c = wb.open_case("1", "windows")
    wb.move(c.id, "surveyed", by="ana")
    assert raises(InvalidTransition, wb.move, c.id, "candidate", by="ana")
    assert wb.get_case(c.id).stage == "surveyed"


def test_h02_same_stage_rejected():
    wb = make()
    c = wb.open_case("1", "windows")
    assert raises(InvalidTransition, wb.move, c.id, "candidate", by="ana")


def test_h02_unknown_stage_is_validation_error():
    wb = make()
    c = wb.open_case("1", "windows")
    assert raises(ValidationError, wb.move, c.id, "demolished", by="ana")


def test_h02_invalid_transition_is_a_validation_error():
    assert issubclass(InvalidTransition, ValidationError)


def test_h02_actor_required():
    wb = make()
    c = wb.open_case("1", "windows")
    assert raises(ValidationError, wb.move, c.id, "surveyed", by="  ")
    assert wb.get_case(c.id).stage == "candidate"


def test_h02_failed_move_leaves_history_unchanged():
    wb = make()
    c = wb.open_case("1", "windows")
    wb.move(c.id, "surveyed", by="ana")
    raises(InvalidTransition, wb.move, c.id, "ready", by="ben")
    assert wb.history(c.id) == [("candidate", "surveyed", "ana")]


def test_h02_history_of_unknown_case():
    assert raises(NotFoundError, make().history, "C-0042")


def test_h02_move_unknown_case():
    assert raises(NotFoundError, make().move, "C-0042", "surveyed", by="ana")


def test_h02_stage_counts_include_every_stage():
    wb = make()
    wb.open_case("1", "windows")
    counts = wb.stage_counts()
    assert set(counts) == set(STAGES)
    assert counts["candidate"] == 1 and sum(counts.values()) == 1


def test_h02_stage_filter_combines_with_f01_filters():
    wb = make()
    a = wb.open_case("1", "windows")
    b = wb.open_case("2", "windows")
    wb.open_case("1", "solar pv")
    wb.move(a.id, "surveyed", by="ana")
    wb.move(b.id, "surveyed", by="ana")
    assert [c.id for c in wb.list_cases(stage="surveyed", postcode_prefix="YO")] == [b.id]
    assert [c.id for c in wb.list_cases(stage="candidate", measure="solar pv")] == ["C-0003"]
