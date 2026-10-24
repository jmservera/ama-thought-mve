from workbench import InvalidTransition, Workbench


def make():
    wb = Workbench()
    wb.add_home("1", "1 A Road", "LS1 1AA")
    return wb


def test_f02_new_case_starts_as_candidate():
    assert make().open_case("1", "windows").stage == "candidate"


def test_f02_moving_forward_records_history():
    wb = make()
    c = wb.open_case("1", "windows")
    wb.move(c.id, "surveyed", by="ana")
    assert wb.get_case(c.id).stage == "surveyed"
    assert wb.history(c.id) == [("candidate", "surveyed", "ana")]


def test_f02_skipping_a_stage_is_rejected():
    wb = make()
    c = wb.open_case("1", "windows")
    try:
        wb.move(c.id, "designed", by="ana")
    except InvalidTransition:
        assert wb.get_case(c.id).stage == "candidate"
        return
    raise AssertionError("expected InvalidTransition")


def test_f02_filter_and_count_by_stage():
    wb = make()
    wb.add_home("2", "2 B Road", "LS1 1AB")
    wb.open_case("1", "windows")
    b = wb.open_case("2", "windows")
    wb.move(b.id, "surveyed", by="ana")
    assert [c.id for c in wb.list_cases(stage="surveyed")] == [b.id]
    assert wb.stage_counts()["candidate"] == 1
