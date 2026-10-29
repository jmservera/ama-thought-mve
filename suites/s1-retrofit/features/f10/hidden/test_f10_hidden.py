import csv
import datetime
import hashlib
import io
import json

from workbench import NotFoundError, ValidationError, Workbench

KEYS = {"seq", "action", "target", "by", "prev_hash", "hash"}
HEADER = "id,uprn,address,postcode,measure,stage,owner,vulnerability,contact"


def raises(exc, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc:
        return True
    return False


def make():
    wb = Workbench()
    wb.add_home("1", "1 A Road", "LS1 1AA")
    return wb, wb.open_case("1", "windows").id


def rows(text):
    return list(csv.DictReader(io.StringIO(text)))


def test_h10_entry_shape_and_chain():
    wb, cid = make()
    wb.assign(cid, "ana", by="lead\u00e9")
    log = wb.audit_log()
    assert all(set(e) == KEYS for e in log)
    assert [e["seq"] for e in log] == [1, 2, 3]
    assert log[0]["prev_hash"] == ""
    for prev, cur in zip(log, log[1:]):
        assert cur["prev_hash"] == prev["hash"]
    assert all(len(e["hash"]) == 64 and int(e["hash"], 16) >= 0 for e in log)
    assert len({e["hash"] for e in log}) == 3
    for entry in log:
        payload = json.dumps(
            [entry[key] for key in ("seq", "action", "target", "by", "prev_hash")],
            ensure_ascii=True, separators=(", ", ": "),
        )
        assert entry["hash"] == hashlib.sha256(payload.encode("utf-8")).hexdigest()


def test_h10_targets_and_actors():
    wb, cid = make()
    wb.set_vulnerability("1", "frail")
    wb.place_hold(cid, reason="hazard", by="bea")
    log = wb.audit_log()
    assert [(e["action"], e["target"], e["by"]) for e in log] == [
        ("add_home", "1", None), ("open_case", cid, None), ("set_vulnerability", "1", None),
        ("place_hold", cid, "bea")]


def test_h10_every_kind_of_write_is_audited():
    wb, cid = make()
    d = datetime.date(2026, 11, 2)
    wb.assign(cid, "ana", by="lead")
    wb.request_handoff(cid, "ben", by="ana")
    wb.decline_handoff(cid, by="ben", reason="busy")
    wb.request_handoff(cid, "ben", by="ana")
    wb.accept_handoff(cid, by="ben")
    wb.move(cid, "surveyed", by="ben")
    wb.return_to(cid, "candidate", reason="redo", by="sam")
    wb.place_hold(cid, reason="hazard", by="bea")
    wb.release_hold(cid, by="bob", role="building_safety")
    wb.require_consent(cid, by="ola")
    wb.record_consent(cid, by="ola")
    wb.withdraw_consent(cid, by="ola", reason="away")
    wb.offer_appointment(cid, d, by="sid")
    wb.confirm_appointment(cid, d, by="sid")
    wb.record_no_access(cid, d, verified=True, by="sid")
    wb.set_resident_contact("1", "0113")
    assert [e["action"] for e in wb.audit_log()] == [
        "add_home", "open_case", "assign", "request_handoff", "decline_handoff", "request_handoff",
        "accept_handoff", "move", "return_to", "place_hold", "release_hold", "require_consent", "record_consent",
        "withdraw_consent", "offer_appointment", "confirm_appointment", "record_no_access", "set_resident_contact"]
    assert wb.verify_audit() is True


def test_h10_reopen_is_audited():
    wb, cid = make()
    for s in ("surveyed", "designed", "ready", "installed", "handed_over"):
        wb.move(cid, s, by="ana")
    wb.reopen(cid, reason="defect", by="sam")
    last = wb.audit_log()[-1]
    assert (last["action"], last["target"], last["by"]) == ("reopen", cid, "sam")


def test_h10_failed_writes_and_reads_add_nothing():
    wb, cid = make()
    before = len(wb.audit_log())
    for call in (lambda: wb.move(cid, "ready", by="ana"), lambda: wb.add_home("1", "dup", "LS1"),
                 lambda: wb.open_case("99", "windows"), lambda: wb.assign(cid, "", by="lead"),
                 lambda: wb.release_hold(cid, by="bob", role="building_safety")):
        try:
            call()
        except (ValidationError, NotFoundError):
            pass
    wb.get_case(cid)
    wb.list_cases()
    wb.case_details(cid)
    wb.rank_cases()
    wb.export_cases_csv("officer")
    wb.verify_audit()
    assert len(wb.audit_log()) == before


def test_h10_import_appends_one_entry_per_home():
    wb = Workbench()
    wb.import_homes_csv("uprn,address,postcode\n10,10 A St,LS1 1AA\n11,11 A St,LS1 1AB\n")
    assert [(e["action"], e["target"]) for e in wb.audit_log()] == [("add_home", "10"), ("add_home", "11")]
    assert raises(ValidationError, wb.import_homes_csv, "uprn,address,postcode\n12,12 A St,LS1 1AA\nXX,bad,LS1\n")
    assert len(wb.audit_log()) == 2


def test_h10_removed_or_reordered_entries_are_detected():
    wb, cid = make()
    wb.move(cid, "surveyed", by="ana")
    log = wb.audit_log()
    assert wb.verify_audit(log[1:]) is False
    assert wb.verify_audit([log[1], log[0], log[2]]) is False


def test_h10_changed_actor_or_hash_is_detected():
    wb, cid = make()
    wb.move(cid, "surveyed", by="ana")
    for field, value in (("action", "assign"), ("by", "mallory"), ("hash", "0" * 64)):
        log = wb.audit_log()
        log[2][field] = value
        assert wb.verify_audit(log) is False


def test_h10_audit_log_returns_copies():
    wb, _ = make()
    wb.audit_log()[0]["action"] = "tampered"
    assert wb.audit_log()[0]["action"] == "add_home"
    assert wb.verify_audit() is True


def test_h10_export_header_and_order():
    wb, cid = make()
    wb.add_home("2", "2, Mill Lane", "YO1 7HH")
    second = wb.open_case("2", "solar pv").id
    text = wb.export_cases_csv("officer")
    assert text.splitlines()[0] == HEADER
    out = rows(text)
    assert [r["id"] for r in out] == [cid, second]
    assert out[1]["address"] == "2, Mill Lane" and out[1]["owner"] == "" and out[1]["vulnerability"] == ""


def test_h10_export_filters_match_list_cases():
    wb, cid = make()
    wb.add_home("2", "2 B Road", "YO1 7HH")
    other = wb.open_case("2", "windows").id
    wb.assign(other, "ana", by="lead")
    assert [r["id"] for r in rows(wb.export_cases_csv("officer", owner="ana"))] == [other]
    assert [r["id"] for r in rows(wb.export_cases_csv("officer", postcode_prefix="LS"))] == [cid]
    assert rows(wb.export_cases_csv("officer", measure="solar pv")) == []


def test_h10_export_visibility_by_role():
    wb, _ = make()
    wb.set_vulnerability("1", "frail")
    wb.set_resident_contact("1", "0113 496 0000")
    officer = rows(wb.export_cases_csv("officer"))[0]
    contractor = rows(wb.export_cases_csv("contractor"))[0]
    assert (officer["vulnerability"], officer["contact"]) == ("frail", "0113 496 0000")
    assert (contractor["vulnerability"], contractor["contact"]) == ("", "")
    assert contractor["stage"] == "candidate" and contractor["measure"] == "windows"


def test_h10_export_needs_a_known_role():
    wb, _ = make()
    assert raises(ValidationError, wb.export_cases_csv, "visitor")
