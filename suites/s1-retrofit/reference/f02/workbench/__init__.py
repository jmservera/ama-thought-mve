"""Reference implementation after F2. Used only to validate the hidden tests and for dry runs."""
import csv
import io
from dataclasses import dataclass

MEASURES = frozenset({"loft insulation", "cavity wall insulation", "external wall insulation",
                      "air source heat pump", "solar pv", "windows"})


class ValidationError(Exception):
    pass


class NotFoundError(Exception):
    pass


class InvalidTransition(ValidationError):
    pass


STAGES = ("candidate", "surveyed", "designed", "ready", "installed", "handed_over")


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


class Workbench:
    def __init__(self):
        self._homes = {}
        self._cases = {}
        self._seq = 0
        self._history = {}

    def _check_home(self, uprn, address, postcode, pending=()):
        if not isinstance(uprn, str) or not uprn.isdigit():
            raise ValidationError("uprn must be a string of digits")
        if uprn in self._homes or uprn in pending:
            raise ValidationError("duplicate uprn")
        if not address or not address.strip():
            raise ValidationError("address is required")
        if not postcode or not postcode.strip():
            raise ValidationError("postcode is required")

    def add_home(self, uprn, address, postcode):
        self._check_home(uprn, address, postcode)
        home = Home(uprn, address.strip(), postcode.strip().upper())
        self._homes[uprn] = home
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
        return case

    def get_case(self, case_id):
        try:
            return self._cases[case_id]
        except KeyError:
            raise NotFoundError(case_id) from None

    def list_cases(self, postcode_prefix=None, measure=None, stage=None):
        out = []
        for c in sorted(self._cases.values(), key=lambda c: c.id):
            if postcode_prefix and not self._homes[c.uprn].postcode.startswith(postcode_prefix.strip().upper()):
                continue
            if measure and c.measure != measure:
                continue
            if stage and c.stage != stage:
                continue
            out.append(c)
        return out

    def move(self, case_id, to, by):
        case = self.get_case(case_id)
        if not isinstance(by, str) or not by.strip():
            raise ValidationError("by is required")
        if to not in STAGES:
            raise ValidationError("unknown stage")
        if STAGES.index(to) != STAGES.index(case.stage) + 1:
            raise InvalidTransition(f"{case.stage} -> {to}")
        self._history[case_id].append((case.stage, to, by))
        case.stage = to
        return case

    def history(self, case_id):
        self.get_case(case_id)
        return list(self._history[case_id])

    def stage_counts(self):
        counts = {s: 0 for s in STAGES}
        for c in self._cases.values():
            counts[c.stage] += 1
        return counts
