"""Document catalogue and the rules that decide which documents a customer file needs.

Every requirement cites the (mock) policy section that imposes it. Document codes are
plain strings stored in company["documents_on_file"]:

  statuts, modele_J, attestation_fiscale, declaration_ubo   one per file
  bilan_<year>                                               e.g. bilan_2025
  id:<holder name>                                           CNIE or passport of a person
  registre:<entity name>                                     shareholder register of a company
"""
from dataclasses import asdict, dataclass
from datetime import date

from .config import HIGH_SECRECY, LARGE_REQUEST_MAD, UBO_THRESHOLD_PCT
from .name_matching import similarity

DOC_TYPES = {
    "statuts": "Statuts (articles of association)",
    "modele_J": "Modèle J (commercial register extract)",
    "attestation_fiscale": "Attestation de régularité fiscale (tax certificate)",
    "bilan": "Bilan / états de synthèse (financial statements)",
    "id_document": "CNIE or passport",
    "declaration_ubo": "Déclaration des bénéficiaires effectifs (UBO declaration)",
    "registre_actionnaires": "Shareholder register of a corporate shareholder",
    "other": "Other document",
}
NAME_MATCH = 0.85  # how close a name on an ID / register must be to the person or entity


@dataclass
class Requirement:
    code: str
    label: str
    reason: str
    policy: str

    def as_dict(self) -> dict:
        return asdict(self)


def document_code(doc_type: str, year: int | None = None, holder: str = "") -> str:
    """Code stored in documents_on_file for a classified document."""
    if doc_type == "bilan":
        return f"bilan_{year}" if year else "bilan_unknown_year"
    if doc_type == "id_document":
        return f"id:{holder}"
    if doc_type == "registre_actionnaires":
        return f"registre:{holder}"
    return doc_type


def required_bilan_years(company: dict, as_of: date) -> list[int]:
    """Last two closed financial years, skipping years before the company existed."""
    inc = date.fromisoformat(company["incorporation_date"]) if company.get("incorporation_date") else None
    years = [as_of.year - 2, as_of.year - 1]
    return [y for y in years if inc is None or inc <= date(y, 6, 30)]


def required_documents(company: dict, as_of: date, strict: bool = True) -> list[Requirement]:
    """Documents the file must contain.

    strict=False is the short list the KYC agent has always checked (demo files).
    strict=True adds identity documents and offshore registers; it is used by the
    document gate that stops the pipeline for uploaded files.
    """
    reqs = [
        Requirement("statuts", DOC_TYPES["statuts"], "Identification of the legal entity.", "POL-KYC-01 §1"),
        Requirement("modele_J", DOC_TYPES["modele_J"], "Recent commercial register extract.", "POL-KYC-01 §1"),
        Requirement("attestation_fiscale", DOC_TYPES["attestation_fiscale"], "Tax compliance of the entity.",
                    "POL-KYC-01 §1"),
    ]
    amount = company.get("requested_amount_mad", 0)
    if amount > LARGE_REQUEST_MAD:
        for y in required_bilan_years(company, as_of):
            reqs.append(Requirement(f"bilan_{y}", f"Bilan {y} (financial statements)",
                                    f"Two years of statements are required above {LARGE_REQUEST_MAD:,} MAD.",
                                    "POL-CRD-04 §5"))

    shareholders = company.get("shareholders", [])
    corporate = [s for s in shareholders if s.get("type") == "company"]
    foreign_ubo = any(s.get("type") == "person" and s.get("country") != "MA" and s.get("pct", 0) >= UBO_THRESHOLD_PCT
                      for s in shareholders)
    foreign_ubo = foreign_ubo or any(u.get("country") != "MA" for s in corporate for u in s.get("ubos", []))
    if corporate or foreign_ubo:
        why = "a shareholder is a legal entity" if corporate else "a beneficial owner is non-resident"
        reqs.append(Requirement("declaration_ubo", DOC_TYPES["declaration_ubo"],
                                f"Beneficial owners must be identified because {why}.", "POL-KYC-01 §2"))

    if strict:
        for d in company.get("directors", []):
            reqs.append(Requirement(f"id:{d['name']}", f"CNIE or passport of {d['name']}",
                                    f"Identity document of {d.get('role') or 'director'}.", "POL-KYC-01 §1"))
        for s in corporate:
            if s.get("country") in HIGH_SECRECY:
                reqs.append(Requirement(f"registre:{s['name']}", f"Shareholder register of {s['name']}",
                                        f"{s['name']} is incorporated in {HIGH_SECRECY[s['country']]}.",
                                        "POL-KYC-01 §3"))
    return reqs


def _is_present(code: str, on_file: list[str]) -> bool:
    if ":" not in code:
        return code in on_file
    kind, name = code.split(":", 1)
    return any(d.startswith(kind + ":") and similarity(d.split(":", 1)[1], name) >= NAME_MATCH for d in on_file)


def missing_documents(company: dict, as_of: date, strict: bool = True) -> list[Requirement]:
    on_file = company.get("documents_on_file", [])
    return [r for r in required_documents(company, as_of, strict) if not _is_present(r.code, on_file)]
