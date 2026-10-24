import csv
import io

from workbench import Workbench


def make():
    wb = Workbench()
    wb.add_home("1", "1 A Road", "LS1 1AA")
    cid = wb.open_case("1", "windows").id
    wb.move(cid, "surveyed", by="ana")
    return wb, cid


def test_f10_writes_are_chained_in_the_audit_trail():
    wb, cid = make()
    log = wb.audit_log()
    assert [e["action"] for e in log] == ["add_home", "open_case", "move"]
    assert log[2]["by"] == "ana" and log[2]["target"] == cid
    assert log[1]["prev_hash"] == log[0]["hash"]
    assert wb.verify_audit() is True


def test_f10_tampering_is_detected():
    wb, _ = make()
    log = wb.audit_log()
    assert wb.verify_audit(log) is True
    log[1]["target"] = "C-9999"
    assert wb.verify_audit(log) is False


def test_f10_export_honours_filters_and_visibility():
    wb, cid = make()
    wb.set_vulnerability("1", "frail")
    wb.add_home("2", "2 B Road", "YO1 7HH")
    wb.open_case("2", "solar pv")
    rows = list(csv.DictReader(io.StringIO(wb.export_cases_csv("contractor", stage="surveyed"))))
    assert len(rows) == 1 and rows[0]["id"] == cid
    assert rows[0]["vulnerability"] == "" and rows[0]["address"] == "1 A Road"
