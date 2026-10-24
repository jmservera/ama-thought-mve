from workbench import NotFoundError, ValidationError, Workbench


def raises(exc, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc:
        return True
    return False


def wb2():
    wb = Workbench()
    wb.add_home("1", "1 A Road", "LS1 1AA")
    wb.add_home("2", "2 B Road", "YO1 7HH")
    return wb


def test_h01_ids_are_sequential():
    wb = wb2()
    ids = [wb.open_case("1", "windows").id, wb.open_case("2", "windows").id, wb.open_case("1", "solar pv").id]
    assert ids == ["C-0001", "C-0002", "C-0003"]


def test_h01_unknown_case_not_found():
    assert raises(NotFoundError, wb2().get_case, "C-9999")


def test_h01_open_case_for_unknown_home():
    assert raises(NotFoundError, wb2().open_case, "999", "windows")


def test_h01_unknown_measure_rejected():
    assert raises(ValidationError, wb2().open_case, "1", "magic paint")


def test_h01_non_digit_uprn_rejected():
    assert raises(ValidationError, Workbench().add_home, "AB12", "1 A Road", "LS1 1AA")


def test_h01_blank_address_rejected():
    assert raises(ValidationError, Workbench().add_home, "5", "   ", "LS1 1AA")


def test_h01_postcode_prefix_is_case_insensitive():
    wb = wb2()
    a = wb.open_case("1", "windows")
    wb.open_case("2", "windows")
    assert [c.id for c in wb.list_cases(postcode_prefix="ls1")] == [a.id]


def test_h01_filter_by_measure_and_combined():
    wb = wb2()
    a = wb.open_case("1", "windows")
    b = wb.open_case("1", "solar pv")
    wb.open_case("2", "solar pv")
    assert [c.id for c in wb.list_cases(measure="windows")] == [a.id]
    assert [c.id for c in wb.list_cases(postcode_prefix="LS", measure="solar pv")] == [b.id]


def test_h01_duplicate_case_for_same_measure_rejected():
    wb = wb2()
    wb.open_case("1", "windows")
    assert raises(ValidationError, wb.open_case, "1", "windows")
    assert len(wb.list_cases()) == 1


def test_h01_csv_import_is_atomic():
    wb = Workbench()
    bad = "uprn,address,postcode\n10,10 A St,LS1 1AA\nXX,11 A St,LS1 1AB\n"
    assert raises(ValidationError, wb.import_homes_csv, bad)
    assert raises(NotFoundError, wb.open_case, "10", "windows")


def test_h01_csv_duplicates_rejected():
    wb = Workbench()
    wb.add_home("10", "10 A St", "LS1 1AA")
    assert raises(ValidationError, wb.import_homes_csv, "uprn,address,postcode\n10,10 A St,LS1 1AA\n")
    assert raises(ValidationError, wb.import_homes_csv, "uprn,address,postcode\n20,A,LS1\n20,B,LS2\n")


def test_h01_list_is_ordered_by_id():
    wb = wb2()
    wb.open_case("2", "windows")
    wb.open_case("1", "windows")
    assert [c.id for c in wb.list_cases()] == ["C-0001", "C-0002"]
