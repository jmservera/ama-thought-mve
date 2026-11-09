"""Fixed S1 API workflows, executed only in the isolated evaluator."""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import csv
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    """A workflow becomes eligible when all its feature dependencies exist."""

    id: str
    features: tuple[str, ...]
    title: str
    function: str

    @property
    def introduced(self) -> int:
        return max(int(feature[1:]) for feature in self.features if feature != "cr1")


SCENARIOS = (
    Scenario("registration", ("f01",), "Register, filter and atomically import homes", "registration"),
    Scenario("lifecycle", ("f01", "f02"), "Advance and recover from an invalid transition", "lifecycle"),
    Scenario("handoff", ("f01", "f03"), "Transfer responsibility only on acceptance", "handoff"),
    Scenario("rework", ("f01", "f02", "f03", "f04"), "Return work without losing ownership", "rework"),
    Scenario("safety", ("f01", "f02", "f03", "f04", "f05"), "Hold work, permit rework, release safely", "safety"),
    Scenario("consent", ("f01", "f02", "f05", "f06"), "Withdraw and restore consent with safety precedence", "consent"),
    Scenario("appointments", ("f01", "f02", "f04", "f07"), "Confirm visits and reset escalation on reopening", "appointments"),
    Scenario("privacy", ("f01", "f08"), "Read live contractor views without exposing protected fields", "privacy"),
    Scenario("ranking", ("f01", "f05", "f06", "f07", "f08", "f09"), "Rank interacting states with stable reasons", "ranking"),
    Scenario("audit-export", ("f01", "f02", "f08", "f10"), "Audit writes, reject tampering, export safely", "audit_export"),
    Scenario("delivery-journey", tuple(f"f{k:02d}" for k in range(1, 11)),
             "Deliver, reopen and audit a consent-controlled retrofit case", "delivery_journey"),
    Scenario("regions", ("f01", "f03", "f08", "f09", "f10", "cr1"),
             "Apply region scope and approve a cross-region handoff", "regions"),
)
DIMENSIONS = ("functional_completeness", "workflow_coherence", "error_recovery", "api_usability")


def eligible(k: int, cr: bool = False) -> list[Scenario]:
    return [scenario for scenario in SCENARIOS
            if scenario.introduced <= k and ("cr1" not in scenario.features or cr)]


class Trace:
    """Record bounded JSON facts; never use candidate repr or traceback text."""

    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.observations: list[dict] = []

    def check(self, action: str, actual: object, expected: object) -> None:
        encoded = json.dumps(actual, sort_keys=True, allow_nan=False)
        if len(encoded) > 8192:
            raise ValueError("Candidate observation exceeds limit")
        self.observations.append({
            "id": f"{self.scenario.id}:{len(self.observations) + 1}",
            "action": action, "expected": expected, "actual": actual,
            "outcome": "passed" if encoded == json.dumps(expected, sort_keys=True, allow_nan=False) else "failed",
        })

    def rejects(self, action: str, expected: str, function, *args, **kwargs) -> None:
        try:
            function(*args, **kwargs)
        except Exception as error:  # Candidate exceptions are measured, not suppressed.
            import workbench

            declared = getattr(workbench, expected, None)
            actual = expected if isinstance(declared, type) and isinstance(error, declared) else type(error).__name__
        else:
            actual = "no_exception"
        self.check(action, actual, expected)


def make():
    from workbench import Workbench

    wb = Workbench()
    wb.add_home("101", "101 Example Road", " ab1 1aa ")
    return wb, wb.open_case("101", "windows").id


def advance(wb, cid, stages=("surveyed", "designed", "ready", "installed", "handed_over")):
    for stage in stages:
        wb.move(cid, stage, by="officer")


def registration(t):
    wb, cid = make()
    t.check("canonical home fields", [wb.get_case(cid).uprn, cid], ["101", "C-0001"])
    t.check("combined filters", [case.id for case in wb.list_cases(postcode_prefix="AB", measure="windows")], [cid])
    t.rejects("duplicate measure rejected", "ValidationError", wb.open_case, "101", "windows")
    t.rejects("atomic CSV rejects invalid row", "ValidationError", wb.import_homes_csv,
              "uprn,address,postcode\n102,102 Example Road,AB1\nbad,103 Example Road,AB2\n")
    t.rejects("invalid import left no home", "NotFoundError", wb.open_case, "102", "windows")
    t.check("valid import works after rejection",
            wb.import_homes_csv("uprn,address,postcode\n102,102 Example Road,AB1\n"), 1)
    t.check("next case id", wb.open_case("102", "windows").id, "C-0002")


def lifecycle(t):
    wb, cid = make()
    t.rejects("cannot skip a stage", "InvalidTransition", wb.move, cid, "ready", by="officer")
    t.check("failed move preserved stage", wb.get_case(cid).stage, "candidate")
    advance(wb, cid, ("surveyed", "designed"))
    t.check("history follows successful moves", [list(row) for row in wb.history(cid)],
            [["candidate", "surveyed", "officer"], ["surveyed", "designed", "officer"]])
    t.check("stage counts include zeros", wb.stage_counts(),
            {"candidate": 0, "surveyed": 0, "designed": 1, "ready": 0, "installed": 0, "handed_over": 0})


def handoff(t):
    wb, cid = make()
    wb.assign(cid, "officer", by="lead")
    wb.request_handoff(cid, "surveyor", by="officer")
    t.check("pending request preserves owner", [wb.get_case(cid).owner, wb.pending_handoff(cid)],
            ["officer", "surveyor"])
    t.rejects("wrong recipient cannot accept", "NotAllowed", wb.accept_handoff, cid, by="outsider")
    wb.decline_handoff(cid, by="surveyor", reason="busy")
    t.check("decline preserves owner", [wb.get_case(cid).owner, wb.pending_handoff(cid)], ["officer", None])
    wb.request_handoff(cid, "surveyor", by="officer")
    wb.accept_handoff(cid, by="surveyor")
    t.check("accept changes ownership", [case.id for case in wb.list_cases(owner="surveyor")], [cid])


def rework(t):
    wb, cid = make()
    t.rejects("cannot reopen before handover", "InvalidTransition", wb.reopen, cid, reason="defect", by="officer")
    wb.assign(cid, "officer", by="lead")
    advance(wb, cid, ("surveyed", "designed", "ready"))
    wb.request_handoff(cid, "surveyor", by="officer")
    wb.return_to(cid, "surveyed", reason="revise plan", by="officer")
    t.check("return cancels handoff but keeps owner",
            [wb.get_case(cid).stage, wb.get_case(cid).owner, wb.pending_handoff(cid)],
            ["surveyed", "officer", None])
    advance(wb, cid, ("designed", "ready", "installed", "handed_over"))
    wb.reopen(cid, reason="defect", by="officer")
    t.check("reopening retains reasons", [wb.get_case(cid).stage, wb.notes(cid)],
            ["installed", ["revise plan", "defect"]])


def safety(t):
    wb, cid = make()
    advance(wb, cid, ("surveyed",))
    wb.assign(cid, "officer", by="lead")
    wb.place_hold(cid, reason="hazard", by="safety")
    t.rejects("held transition blocked", "OnHold", wb.move, cid, "designed", by="officer")
    t.rejects("held handoff blocked", "OnHold", wb.request_handoff, cid, "surveyor", by="officer")
    wb.return_to(cid, "candidate", reason="resurvey", by="officer")
    t.check("rework does not clear hold", wb.get_case(cid).on_hold, True)
    t.rejects("only safety role releases", "NotAllowed", wb.release_hold, cid, by="officer", role="officer")
    wb.release_hold(cid, by="safety", role="building_safety")
    wb.move(cid, "surveyed", by="officer")
    t.check("release restores progress", [wb.get_case(cid).stage, wb.get_case(cid).on_hold], ["surveyed", False])


def consent(t):
    wb, cid = make()
    advance(wb, cid, ("surveyed", "designed", "ready"))
    wb.require_consent(cid, by="liaison")
    t.rejects("installation requires consent", "ConsentRequired", wb.move, cid, "installed", by="officer")
    wb.record_consent(cid, by="liaison")
    wb.withdraw_consent(cid, by="liaison", reason="reconsider")
    t.rejects("withdrawal pauses progress", "Paused", wb.move, cid, "installed", by="officer")
    wb.place_hold(cid, reason="hazard", by="safety")
    t.rejects("hold takes precedence over pause", "OnHold", wb.move, cid, "installed", by="officer")
    wb.release_hold(cid, by="safety", role="building_safety")
    wb.record_consent(cid, by="liaison")
    wb.move(cid, "installed", by="officer")
    t.check("restored consent clears pause", [wb.get_case(cid).consent, wb.get_case(cid).paused,
                                            wb.get_case(cid).stage], ["given", False, "installed"])


def appointments(t):
    wb, cid = make()
    day = dt.date(2026, 1, 5)
    t.rejects("unoffered confirmation rejected", "ValidationError", wb.confirm_appointment, cid, day, by="scheduler")
    wb.offer_appointment(cid, day, by="scheduler")
    wb.confirm_appointment(cid, day, by="scheduler")
    t.check("confirmed appointment", [[date.isoformat(), status] for date, status in wb.appointments(cid)],
            [[day.isoformat(), "confirmed"]])
    wb.record_no_access(cid, day, verified=False, by="scheduler")
    for _ in range(6):
        wb.record_no_access(cid, day, verified=True, by="scheduler")
    t.check("only verified visits escalate", [wb.no_access_count(cid), [case.id for case in wb.escalated_cases()]],
            [6, [cid]])
    advance(wb, cid)
    wb.reopen(cid, reason="follow up", by="officer")
    t.check("reopening resets active count, not history",
            [wb.no_access_count(cid), len(wb.no_access_history(cid)), [case.id for case in wb.escalated_cases()]],
            [0, 7, []])


def privacy(t):
    wb, cid = make()
    view = wb.view_as("contractor")
    wb.set_vulnerability("101", "synthetic protected reason")
    wb.set_resident_contact("101", "synthetic contact")
    home = view.get_home("101")
    details = view.case_details(cid)
    t.check("live view hides protected fields",
            [home.vulnerability, home.contact, details["vulnerability"], details["contact"]],
            [None, None, None, None])
    t.check("view leaves canonical data intact", wb.get_home("101").contact, "synthetic contact")
    t.rejects("view cannot write", "NotAllowed", lambda: view.open_case("101", "windows"))
    t.check("view still lists cases", [case.id for case in view.list_cases()], [cid])


def ranking(t):
    wb, cid = make()
    wb.set_vulnerability("101", "synthetic protected reason")
    wb.record_consent(cid, by="liaison")
    wb.place_hold(cid, reason="hazard", by="safety")
    wb.add_home("102", "102 Example Road", "AB1")
    second = wb.open_case("102", "windows").id
    expected = [[cid, 70, ["HELD", "VULNERABLE", "CONSENT_GIVEN"]], [second, 0, []]]
    t.check("held cases lead and accumulate reasons", [[cid, score, codes] for cid, score, codes in wb.rank_cases()],
            expected)
    t.check("ranking is stable and available on views",
            [[cid, score, codes] for cid, score, codes in wb.view_as("contractor").rank_cases()], expected)
    t.rejects("unsupported policy rejected", "ValidationError", wb.rank_cases, policy_version="v2")


def audit_export(t):
    wb, cid = make()
    wb.set_vulnerability("101", "synthetic protected reason")
    wb.set_resident_contact("101", "synthetic contact")
    before = len(wb.audit_log())
    t.rejects("invalid transition rejected", "InvalidTransition", wb.move, cid, "ready", by="officer")
    wb.list_cases()
    t.check("failed calls and reads append nothing", len(wb.audit_log()), before)
    log = wb.audit_log()
    valid = True
    for index, entry in enumerate(log):
        payload = json.dumps([entry[key] for key in ("seq", "action", "target", "by", "prev_hash")],
                             ensure_ascii=True, separators=(", ", ": "))
        valid = valid and entry["hash"] == hashlib.sha256(payload.encode()).hexdigest()
        valid = valid and entry["seq"] == index + 1 and entry["prev_hash"] == (log[index - 1]["hash"] if index else "")
    t.check("audit has independently verified chain", valid, True)
    log[0]["action"] = "tampered"
    t.check("tampering detected without modifying stored audit", [wb.verify_audit(log), wb.verify_audit()], [False, True])
    rows = list(csv.DictReader(io.StringIO(wb.export_cases_csv("contractor", postcode_prefix="AB"))))
    t.check("filtered export hides protected fields",
            [[row["id"], row["contact"], row["vulnerability"]] for row in rows], [[cid, "", ""]])


def delivery_journey(t):
    wb, cid = make()
    wb.assign(cid, "officer", by="lead")
    wb.require_consent(cid, by="liaison")
    day = dt.date(2026, 1, 5)
    wb.offer_appointment(cid, day, by="scheduler")
    wb.confirm_appointment(cid, day, by="scheduler")
    advance(wb, cid, ("surveyed", "designed", "ready"))
    t.rejects("end-to-end installation guard", "ConsentRequired", wb.move, cid, "installed", by="officer")
    wb.record_consent(cid, by="liaison")
    wb.request_handoff(cid, "installer", by="officer")
    wb.accept_handoff(cid, by="installer")
    advance(wb, cid, ("installed", "handed_over"))
    t.check("completed cases excluded from priority list", wb.rank_cases(), [])
    wb.reopen(cid, reason="defect", by="officer")
    t.check("reopened case retains coherent state",
            [wb.get_case(cid).stage, wb.get_case(cid).owner, wb.get_case(cid).consent,
             wb.no_access_count(cid), wb.verify_audit()], ["installed", "installer", "given", 0, True])
    t.check("reopened case returns to ranking", [row[0] for row in wb.rank_cases()], [cid])


def regions(t):
    wb, cid = make()
    wb.define_region("north", ["AB"])
    wb.define_region("south", ["CD"])
    wb.add_home("102", "102 Example Road", "CD1")
    second = wb.open_case("102", "windows").id
    wb.add_user("officer", "officer", ["north"])
    wb.add_user("installer", "contractor", ["south"])
    wb.add_user("manager", "manager", ["north", "south"])
    view = wb.view_for("officer")
    t.check("region applies to previously added home", wb.region_of("101"), "north")
    t.check("lists and ranking respect scope", [[case.id for case in view.list_cases()],
                                             [row[0] for row in view.rank_cases()]], [[cid], [cid]])
    t.rejects("out-of-region read rejected", "NotAllowed", view.get_case, second)
    t.check("export respects scope",
            [row["id"] for row in csv.DictReader(io.StringIO(view.export_cases_csv()))], [cid])
    wb.assign(cid, "officer", by="lead")
    wb.request_handoff(cid, "installer", by="officer")
    t.rejects("cross-region acceptance requires approval", "NotAllowed", wb.accept_handoff, cid, by="installer")
    t.check("unapproved acceptance preserves owner", wb.get_case(cid).owner, "officer")
    wb.approve_handoff(cid, by="manager")
    wb.accept_handoff(cid, by="installer")
    t.check("approved handoff and audit", [wb.get_case(cid).owner, wb.verify_audit()], ["installer", True])


def execute(scenario: Scenario) -> dict:
    """Capture an ordinary candidate failure with the completed partial trace."""
    trace = Trace(scenario)
    error_type = None
    try:
        globals()[scenario.function](trace)
    except Exception as error:  # This is the bounded candidate-execution boundary.
        error_type = type(error).__name__
    status = "failed" if error_type or any(row["outcome"] == "failed" for row in trace.observations) else "passed"
    return {"scenario_id": scenario.id, "status": status, "error_type": error_type,
            "observations": trace.observations}
