from workbench import ValidationError, Workbench


def test_f01_add_home_and_open_case():
    wb = Workbench()
    home = wb.add_home("100001", "1 High Street, Leeds", "ls1 1aa")
    assert home.postcode == "LS1 1AA"
    case = wb.open_case("100001", "loft insulation")
    assert case.id == "C-0001"
    assert [c.id for c in wb.list_cases()] == ["C-0001"]


def test_f01_filter_by_postcode_prefix():
    wb = Workbench()
    wb.add_home("1", "1 A Road", "LS1 1AA")
    wb.add_home("2", "2 B Road", "YO1 7HH")
    a = wb.open_case("1", "windows")
    wb.open_case("2", "windows")
    assert [c.id for c in wb.list_cases(postcode_prefix="LS")] == [a.id]


def test_f01_duplicate_uprn_is_rejected():
    wb = Workbench()
    wb.add_home("1", "1 A Road", "LS1 1AA")
    try:
        wb.add_home("1", "Another address", "LS2 2BB")
    except ValidationError:
        return
    raise AssertionError("expected ValidationError")


def test_f01_import_homes_from_csv():
    wb = Workbench()
    n = wb.import_homes_csv("uprn,address,postcode\n10,10 A St,LS1 1AA\n11,11 A St,LS1 1AB\n")
    assert n == 2
    wb.open_case("11", "solar pv")
    assert wb.get_case("C-0001").uprn == "11"
