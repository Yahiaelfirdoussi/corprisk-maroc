"""Fuzzy name matching for sanctions / PEP screening.

Simple and explainable: accents removed, legal suffixes dropped, tokens sorted,
then a similarity ratio. Production systems use dedicated screening engines
(transliteration Arabic/Latin, phonetic keys, aliases, DOB matching).
"""
import re
import unicodedata
from difflib import SequenceMatcher

LEGAL_SUFFIXES = {"sarl", "sarlau", "sa", "sas", "ltd", "llc", "l l c", "sl", "bv", "fze", "inc", "co", "gmbh", "plc"}


def normalize(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\bl l c\b", " ", s)
    tokens = [t for t in s.split() if t not in LEGAL_SUFFIXES and t not in {"&", "and", "et"}]
    return " ".join(sorted(tokens))


def similarity(a: str, b: str) -> float:
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    return round(SequenceMatcher(None, na, nb).ratio(), 3)
