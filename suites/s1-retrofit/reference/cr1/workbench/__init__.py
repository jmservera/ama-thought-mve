"""Reference implementation of suite S1 at snapshot cr1. Generated from source.py; never shown to agents."""
import csv

import dataclasses

import datetime
import hashlib
import io
import json
from dataclasses import dataclass

MEASURES = frozenset({"loft insulation", "cavity wall insulation", "external wall insulation",
                      "air source heat pump", "solar pv", "windows"})
STAGES = ("candidate", "surveyed", "designed", "ready", "installed", "handed_over")
ROLES = frozenset({"officer", "contractor", "building_safety", "manager"})
EXPORT_COLUMNS = ("id", "uprn", "address", "postcode", "measure", "stage", "owner", "vulnerability", "contact")


class ValidationError(Exception):
    pass


class NotFoundError(Exception):
    pass


class InvalidTransition(ValidationError):
    pass


class NotAllowed(ValidationError):
    pass


class OnHold(ValidationError):
    pass


class ConsentRequired(ValidationError):
    pass


class Paused(ValidationError):
    pass


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{name} is required")
    return value


def _entry_hash(entry):
    payload = json.dumps([entry.get("seq"), entry.get("action"), entry.get("target"), entry.get("by"),
                          entry.get("prev_hash")])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class Home:
    uprn: str
    address: str
    postcode: str
    vulnerability: object = None
    contact: object = None


@dataclass
class Case:
    id: str
    uprn: str
    measure: str
    stage: str = "candidate"
    owner: object = None
    on_hold: bool = False
    consent: str = "not_required"
    paused: bool = False


class Workbench:
    def __init__(self):
        self._homes = {}
        self._cases = {}
        self._seq = 0
        self._history = {}
        self._pending = {}
        self._notes = {}
        self._holds = {}
        self._appointments = {}
        self._visits = {}
        self._active_no_access = {}
        self._audit = []
        self._regions = {}
        self._users = {}
        self._needs_approval = {}

    def _log(self, action, target, by=None):
        prev = self._audit[-1]["hash"] if self._audit else ""
        entry = {"seq": len(self._audit) + 1, "action": action, "target": target, "by": by, "prev_hash": prev}
        entry["hash"] = _entry_hash(entry)
        self._audit.append(entry)
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
        if case.on_hold:
            raise OnHold(case_id)
        if case.paused:
            raise Paused(case_id)
        if to not in STAGES:
            raise ValidationError("unknown stage")
        if STAGES.index(to) != STAGES.index(case.stage) + 1:
            raise InvalidTransition(f"{case.stage} -> {to}")
        if to == "installed" and case.consent == "required":
            raise ConsentRequired(case_id)
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
        if case.on_hold:
            raise OnHold(case_id)
        if to == case.owner:
            raise ValidationError("cannot hand off to the current owner")
        if case_id in self._pending:
            raise ValidationError("a handoff is already pending")
        self._pending[case_id] = to
        self._needs_approval[case_id] = self._crosses_region(case, to)
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
        if case.on_hold:
            raise OnHold(case_id)
        if self._needs_approval.get(case_id):
            raise NotAllowed("this handoff needs a manager's approval")
        self._needs_approval.pop(case_id, None)
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
        self._needs_approval.pop(case_id, None)
        self._log("decline_handoff", case_id, by)
        return case

    def pending_handoff(self, case_id):
        self.get_case(case_id)
        return self._pending.get(case_id)

    # ------------------------------------------------------------------ F4
    def _cancel_handoff(self, case_id):
        self._pending.pop(case_id, None)
        self._needs_approval.pop(case_id, None)

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
        self._active_no_access[case_id] = 0
        self._log("reopen", case_id, by)
        return case

    def notes(self, case_id):
        self.get_case(case_id)
        return list(self._notes.get(case_id, []))

    # ------------------------------------------------------------------ F5
    def place_hold(self, case_id, reason, by):
        case = self.get_case(case_id)
        _text(reason, "reason")
        _text(by, "by")
        if case.on_hold:
            raise ValidationError("case is already on hold")
        case.on_hold = True
        self._holds.setdefault(case_id, []).append([by, reason, None])
        self._log("place_hold", case_id, by)
        return case

    def release_hold(self, case_id, by, role):
        case = self.get_case(case_id)
        _text(by, "by")
        if role != "building_safety":
            raise NotAllowed("only building safety can release a hold")
        if not case.on_hold:
            raise ValidationError("case is not on hold")
        case.on_hold = False
        self._holds[case_id][-1][2] = by
        self._log("release_hold", case_id, by)
        return case

    def holds(self, case_id):
        self.get_case(case_id)
        return [tuple(h) for h in self._holds.get(case_id, [])]

    # ------------------------------------------------------------------ F6
    def require_consent(self, case_id, by):
        case = self.get_case(case_id)
        _text(by, "by")
        if case.consent != "not_required":
            raise ValidationError("consent is already tracked for this case")
        case.consent = "required"
        self._log("require_consent", case_id, by)
        return case

    def record_consent(self, case_id, by):
        case = self.get_case(case_id)
        _text(by, "by")
        if case.consent == "given":
            raise ValidationError("consent already given")
        case.consent = "given"
        case.paused = False
        self._log("record_consent", case_id, by)
        return case

    def withdraw_consent(self, case_id, by, reason):
        case = self.get_case(case_id)
        _text(by, "by")
        _text(reason, "reason")
        if case.consent != "given":
            raise ValidationError("consent has not been given")
        case.consent = "withdrawn"
        case.paused = True
        self._log("withdraw_consent", case_id, by)
        return case

    # ------------------------------------------------------------------ F7
    @staticmethod
    def _date(value):
        if not isinstance(value, datetime.date):
            raise ValidationError("date must be a datetime.date")
        return value

    def offer_appointment(self, case_id, date, by):
        case = self.get_case(case_id)
        _text(by, "by")
        self._date(date)
        if case.on_hold:
            raise OnHold(case_id)
        slots = self._appointments.setdefault(case_id, {})
        if date in slots:
            raise ValidationError("date already offered")
        slots[date] = "offered"
        self._log("offer_appointment", case_id, by)
        return case

    def confirm_appointment(self, case_id, date, by):
        case = self.get_case(case_id)
        _text(by, "by")
        self._date(date)
        if case.on_hold:
            raise OnHold(case_id)
        slots = self._appointments.get(case_id, {})
        if slots.get(date) != "offered":
            raise ValidationError("only an offered date can be confirmed")
        slots[date] = "confirmed"
        self._log("confirm_appointment", case_id, by)
        return case

    def appointments(self, case_id):
        self.get_case(case_id)
        return sorted(self._appointments.get(case_id, {}).items())

    def record_no_access(self, case_id, date, verified, by):
        case = self.get_case(case_id)
        _text(by, "by")
        self._date(date)
        if not isinstance(verified, bool):
            raise ValidationError("verified must be True or False")
        self._visits.setdefault(case_id, []).append((date, verified))
        if verified:
            self._active_no_access[case_id] = self._active_no_access.get(case_id, 0) + 1
        self._log("record_no_access", case_id, by)
        return case

    def no_access_count(self, case_id):
        self.get_case(case_id)
        return self._active_no_access.get(case_id, 0)

    def no_access_history(self, case_id):
        self.get_case(case_id)
        return list(self._visits.get(case_id, []))

    def escalated_cases(self):
        return [c for c in sorted(self._cases.values(), key=lambda c: c.id)
                if self._active_no_access.get(c.id, 0) > 5]

    # ------------------------------------------------------------------ F8
    def get_home(self, uprn):
        try:
            return self._homes[uprn]
        except KeyError:
            raise NotFoundError(uprn) from None

    def set_vulnerability(self, uprn, reason):
        home = self.get_home(uprn)
        _text(reason, "reason")
        home.vulnerability = reason
        self._log("set_vulnerability", uprn)
        return home

    def set_resident_contact(self, uprn, phone):
        home = self.get_home(uprn)
        _text(phone, "phone")
        home.contact = phone
        self._log("set_resident_contact", uprn)
        return home

    def case_details(self, case_id):
        case = self.get_case(case_id)
        home = self._homes[case.uprn]
        return {"id": case.id, "uprn": case.uprn, "address": home.address, "postcode": home.postcode,
                "measure": case.measure, "stage": case.stage, "owner": case.owner,
                "vulnerability": home.vulnerability, "contact": home.contact}

    def view_as(self, role):
        if role not in ROLES:
            raise ValidationError("unknown role")
        return _View(self, role)

    # ------------------------------------------------------------------ F9
    def rank_cases(self, policy_version="v1"):
        if policy_version != "v1":
            raise ValidationError("unknown policy version")
        ranked = []
        for c in sorted(self._cases.values(), key=lambda c: c.id):
            if c.stage == "handed_over":
                continue
            codes, score = [], 0
            if c.on_hold:
                codes.append("HELD")
            if self._homes[c.uprn].vulnerability:
                codes.append("VULNERABLE")
                score += 50
            if self._active_no_access.get(c.id, 0) > 5:
                codes.append("ESCALATED")
                score += 30
            if c.consent == "given":
                codes.append("CONSENT_GIVEN")
                score += 20
            if c.stage == "ready":
                codes.append("READY")
                score += 10
            if c.paused:
                codes.append("PAUSED")
                score -= 40
            ranked.append((not c.on_hold, -score, c.id, codes, score))
        ranked.sort(key=lambda r: (r[0], r[1], r[2]))
        return [(cid, score, codes) for _, _, cid, codes, score in ranked]

    # ------------------------------------------------------------------ F10
    def audit_log(self):
        return [dict(e) for e in self._audit]

    def verify_audit(self, entries=None):
        entries = self._audit if entries is None else entries
        prev = ""
        for position, entry in enumerate(entries, 1):
            if entry.get("seq") != position or entry.get("prev_hash") != prev or entry.get("hash") != _entry_hash(entry):
                return False
            prev = entry["hash"]
        return True

    def export_cases_csv(self, role, **filters):
        if role not in ROLES:
            raise ValidationError("unknown role")
        return self._export(self.list_cases(**filters), role)

    def _export(self, cases, role):
        out = io.StringIO()
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(EXPORT_COLUMNS)
        for c in cases:
            d = self.case_details(c.id)
            if role == "contractor":
                d["vulnerability"] = d["contact"] = None
            writer.writerow(["" if d[k] is None else d[k] for k in EXPORT_COLUMNS])
        return out.getvalue()

    # ------------------------------------------------------------------ CR1
    def define_region(self, name, postcode_prefixes):
        _text(name, "name")
        if name in self._regions or name == "unassigned":
            raise ValidationError("region already defined")
        if not isinstance(postcode_prefixes, (list, tuple)) or not postcode_prefixes:
            raise ValidationError("at least one postcode prefix is required")
        prefixes = []
        for p in postcode_prefixes:
            _text(p, "postcode prefix")
            p = p.strip().upper()
            if p in prefixes or any(p in used for used in self._regions.values()):
                raise ValidationError("postcode prefix already used")
            prefixes.append(p)
        self._regions[name] = tuple(prefixes)
        self._log("define_region", name)

    def region_of(self, uprn):
        home = self.get_home(uprn)
        best, best_len = "unassigned", 0
        for name, prefixes in self._regions.items():
            for p in prefixes:
                if home.postcode.startswith(p) and len(p) > best_len:
                    best, best_len = name, len(p)
        return best

    def add_user(self, name, role, regions):
        _text(name, "name")
        if name in self._users:
            raise ValidationError("user already exists")
        if role not in ROLES:
            raise ValidationError("unknown role")
        if not isinstance(regions, (list, tuple)) or not regions or any(r not in self._regions for r in regions):
            raise ValidationError("regions must be defined region names")
        self._users[name] = (role, frozenset(regions))
        self._log("add_user", name)

    def view_for(self, name):
        if name not in self._users:
            raise NotFoundError(name)
        role, regions = self._users[name]
        return _View(self, role, regions)

    def _crosses_region(self, case, to):
        user = self._users.get(to)
        return user is not None and self.region_of(case.uprn) not in user[1]

    def handoff_needs_approval(self, case_id):
        self.get_case(case_id)
        return bool(self._needs_approval.get(case_id))

    def approve_handoff(self, case_id, by):
        self.get_case(case_id)
        _text(by, "by")
        user = self._users.get(by)
        if user is None or user[0] != "manager":
            raise NotAllowed("only a manager can approve a cross-region handoff")
        if not self._needs_approval.get(case_id):
            raise ValidationError("no handoff awaiting approval")
        self._needs_approval[case_id] = False
        self._log("approve_handoff", case_id, by)


class _View:
    """Read-only view for a role and, from the change request on, a set of regions."""

    def __init__(self, wb, role, regions=None):
        self._wb = wb
        self._role = role
        self._regions = regions

    def __getattr__(self, name):
        raise NotAllowed(f"{name} is not available on a read-only view")

    def _in_scope(self, uprn):
        return self._regions is None or self._wb.region_of(uprn) in self._regions

    def _case(self, case_id):
        case = self._wb.get_case(case_id)
        if not self._in_scope(case.uprn):
            raise NotAllowed("case outside your regions")
        return case

    def _redact(self, values):
        if self._role == "contractor":
            values["vulnerability"] = None
            values["contact"] = None
        return values

    def get_home(self, uprn):
        home = self._wb.get_home(uprn)
        if not self._in_scope(uprn):
            raise NotAllowed("home outside your regions")
        v = self._redact({"vulnerability": home.vulnerability, "contact": home.contact})
        return Home(home.uprn, home.address, home.postcode, v["vulnerability"], v["contact"])

    def get_case(self, case_id):
        return dataclasses.replace(self._case(case_id))

    def list_cases(self, **filters):
        return [dataclasses.replace(c) for c in self._wb.list_cases(**filters) if self._in_scope(c.uprn)]

    def case_details(self, case_id):
        self._case(case_id)
        return self._redact(self._wb.case_details(case_id))

    def history(self, case_id):
        self._case(case_id)
        return self._wb.history(case_id)

    def notes(self, case_id):
        self._case(case_id)
        return self._wb.notes(case_id)

    def stage_counts(self):
        counts = {s: 0 for s in STAGES}
        for c in self.list_cases():
            counts[c.stage] += 1
        return counts

    def rank_cases(self, policy_version="v1"):
        return [r for r in self._wb.rank_cases(policy_version) if self._in_scope(self._wb.get_case(r[0]).uprn)]

    def export_cases_csv(self, **filters):
        return self._wb._export(self.list_cases(**filters), self._role)
