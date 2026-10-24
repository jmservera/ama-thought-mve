"""Reference implementation after F1. Used only to validate the hidden tests and for dry runs."""
import csv
import io
from dataclasses import dataclass

MEASURES = frozenset({"loft insulation", "cavity wall insulation", "external wall insulation",
                      "air source heat pump", "solar pv", "windows"})


class ValidationError(Exception):
    pass


class NotFoundError(Exception):
    pass


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


class Workbench:
    def __init__(self):
        self._homes = {}
        self._cases = {}
        self._seq = 0

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
        return case

    def get_case(self, case_id):
        try:
            return self._cases[case_id]
        except KeyError:
            raise NotFoundError(case_id) from None

    def list_cases(self, postcode_prefix=None, measure=None):
        out = []
        for c in sorted(self._cases.values(), key=lambda c: c.id):
            if postcode_prefix and not self._homes[c.uprn].postcode.startswith(postcode_prefix.strip().upper()):
                continue
            if measure and c.measure != measure:
                continue
            out.append(c)
        return out
