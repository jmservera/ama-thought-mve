"""Reference implementation of suite S1 at snapshot f04. Generated from source.py; never shown to agents."""
import csv

import datetime
import hashlib
import io
import json
from dataclasses import dataclass

MEASURES = frozenset({"loft insulation", "cavity wall insulation", "external wall insulation",
                      "air source heat pump", "solar pv", "windows"})
STAGES = ("candidate", "surveyed", "designed", "ready", "installed", "handed_over")


class ValidationError(Exception):
    pass


class NotFoundError(Exception):
    pass


class InvalidTransition(ValidationError):
    pass


class NotAllowed(ValidationError):
    pass


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{name} is required")
    return value


@dataclass
class Home:
    uprn: str
    address: str
    postcode: str


@dataclass
class Case:
    id: str
    uprn: str
    measure: str
    stage: str = "candidate"
    owner: object = None


class Workbench:
    def __init__(self):
        self._homes = {}
        self._cases = {}
        self._seq = 0
        self._history = {}
        self._pending = {}
        self._notes = {}

    def _log(self, action, target, by=None):
        return None

    # ------------------------------------------------------------------ F1
    def _check_home(self, uprn, address, postcode, pending=()):
        if not isinstance(uprn, str) or not uprn.isdigit():
            raise ValidationError("uprn must be a string of digits")
        if uprn in self._homes or uprn in pending:
            raise ValidationError("duplicate uprn")
        if not isinstance(address, str) or not address.strip():
            raise ValidationError("address is required")
        if not isinstance(postcode, str) or not postcode.strip():
            raise ValidationError("postcode is required")

    def add_home(self, uprn, address, postcode):
        self._check_home(uprn, address, postcode)
        home = Home(uprn, address.strip(), postcode.strip().upper())
        self._homes[uprn] = home
        self._log("add_home", uprn)
        return home

    def import_homes_csv(self, text):
        rows = list(csv.DictReader(io.StringIO(text)))
        seen = set()
        for r in rows:
            self._check_home(r.get("uprn"), r.get("address"), r.get("postcode"), seen)
            seen.add(r["uprn"])
        for r in rows:
            self.add_home(r["uprn"], r["address"], r["postcode"])
        return len(rows)

    def open_case(self, uprn, measure):
        if uprn not in self._homes:
            raise NotFoundError(uprn)
        if measure not in MEASURES:
            raise ValidationError("unknown measure")
        if any(c.uprn == uprn and c.measure == measure for c in self._cases.values()):
            raise ValidationError("a case for this measure already exists")
        self._seq += 1
        case = Case(f"C-{self._seq:04d}", uprn, measure)
        self._cases[case.id] = case
        self._history[case.id] = []
        self._log("open_case", case.id)
        return case

    def get_case(self, case_id):
        try:
            return self._cases[case_id]
        except KeyError:
            raise NotFoundError(case_id) from None

    def list_cases(self, postcode_prefix=None, measure=None, stage=None, owner=None):
        out = []
        for c in sorted(self._cases.values(), key=lambda c: c.id):
            if postcode_prefix and not self._homes[c.uprn].postcode.startswith(postcode_prefix.strip().upper()):
                continue
            if measure and c.measure != measure:
                continue
            if stage and c.stage != stage:
                continue
            if owner and c.owner != owner:
                continue
            out.append(c)
        return out

    # ------------------------------------------------------------------ F2
    def move(self, case_id, to, by):
        case = self.get_case(case_id)
        _text(by, "by")
        if to not in STAGES:
            raise ValidationError("unknown stage")
        if STAGES.index(to) != STAGES.index(case.stage) + 1:
            raise InvalidTransition(f"{case.stage} -> {to}")
        self._history[case_id].append((case.stage, to, by))
        case.stage = to
        self._log("move", case_id, by)
        return case

    def history(self, case_id):
        self.get_case(case_id)
        return list(self._history[case_id])

    def stage_counts(self):
        counts = {s: 0 for s in STAGES}
        for c in self._cases.values():
            counts[c.stage] += 1
        return counts

    # ------------------------------------------------------------------ F3
    def assign(self, case_id, owner, by):
        case = self.get_case(case_id)
        _text(owner, "owner")
        _text(by, "by")
        if case.owner is not None:
            raise NotAllowed("case already has an owner; use a handoff")
        case.owner = owner
        self._log("assign", case_id, by)
        return case

    def request_handoff(self, case_id, to, by):
        case = self.get_case(case_id)
        _text(to, "to")
        _text(by, "by")
        if case.owner is None or by != case.owner:
            raise NotAllowed("only the current owner can hand off a case")
        if case.stage == "handed_over":
            raise NotAllowed("handed-over cases cannot be handed off")
        if to == case.owner:
            raise ValidationError("cannot hand off to the current owner")
        if case_id in self._pending:
            raise ValidationError("a handoff is already pending")
        self._pending[case_id] = to
        self._log("request_handoff", case_id, by)
        return case

    def accept_handoff(self, case_id, by):
        case = self.get_case(case_id)
        _text(by, "by")
        to = self._pending.get(case_id)
        if to is None:
            raise ValidationError("no pending handoff")
        if by != to:
            raise NotAllowed("only the recipient can accept")
        case.owner = to
        del self._pending[case_id]
        self._log("accept_handoff", case_id, by)
        return case

    def decline_handoff(self, case_id, by, reason):
        case = self.get_case(case_id)
        _text(by, "by")
        _text(reason, "reason")
        to = self._pending.get(case_id)
        if to is None:
            raise ValidationError("no pending handoff")
        if by != to:
            raise NotAllowed("only the recipient can decline")
        del self._pending[case_id]
        self._log("decline_handoff", case_id, by)
        return case

    def pending_handoff(self, case_id):
        self.get_case(case_id)
        return self._pending.get(case_id)

    # ------------------------------------------------------------------ F4
    def _cancel_handoff(self, case_id):
        self._pending.pop(case_id, None)

    def return_to(self, case_id, stage, reason, by):
        case = self.get_case(case_id)
        _text(reason, "reason")
        _text(by, "by")
        if stage not in STAGES:
            raise ValidationError("unknown stage")
        if STAGES.index(stage) >= STAGES.index(case.stage):
            raise InvalidTransition(f"{case.stage} -> {stage}")
        self._history[case_id].append((case.stage, stage, by))
        case.stage = stage
        self._notes.setdefault(case_id, []).append(reason)
        self._cancel_handoff(case_id)
        self._log("return_to", case_id, by)
        return case

    def reopen(self, case_id, reason, by):
        case = self.get_case(case_id)
        _text(reason, "reason")
        _text(by, "by")
        if case.stage != "handed_over":
            raise InvalidTransition("only handed-over cases can be reopened")
        self._history[case_id].append((case.stage, "installed", by))
        case.stage = "installed"
        self._notes.setdefault(case_id, []).append(reason)
        self._cancel_handoff(case_id)
        self._log("reopen", case_id, by)
        return case

    def notes(self, case_id):
        self.get_case(case_id)
        return list(self._notes.get(case_id, []))
