"""Generational and professional suffixes.

Why this exists: a tokenizer that takes the last whitespace-delimited token as
the surname will assign "JR" or "MD" as a family name. In the PPP audit this
affected 1.38 percent of records overall, and 7.87 percent of records assigned
to the Asian category -- a differential large enough to distort a
name-based classifier's inputs for that group.
"""
import re

GENERATIONAL = ["JR","SR","I","II","III","IV","V","VI","VII","VIII","IX","X"]
PROFESSIONAL = ["MD","DO","DDS","DMD","DVM","PHD","ESQ","CPA","RN","LPN","NP","PA",
                "JD","LLM","MBA","CFA","PE","RA","AIA","LCSW","PSYD","EDD","OD","PHARMD"]
# I and V are also plausible initials; require a preceding surname token before
# treating them as suffixes (handled in split_suffix).
AMBIGUOUS = {"I","V","X","PA","PE","RA","DO"}

SUFFIXES = set(GENERATIONAL) | set(PROFESSIONAL)
_CLEAN = re.compile(r"[.,]+$")

def _norm(tok: str) -> str:
    return _CLEAN.sub("", str(tok).strip().upper())

def is_suffix(tok: str, *, allow_ambiguous: bool = False) -> bool:
    """True if the token is a name suffix rather than a name part."""
    t = _norm(tok)
    if t not in SUFFIXES:
        return False
    if t in AMBIGUOUS and not allow_ambiguous:
        return False
    return True

def split_suffix(tokens):
    """Strip trailing suffix tokens from a token list.

    Returns (name_tokens, suffixes). Never strips so far that fewer than two
    name tokens remain, so "JOHN JR" keeps JR as a surname rather than
    returning a one-token name -- we would rather be visibly wrong than
    silently drop the only surname candidate.

    Ambiguous tokens (I, V, PA, DO ...) are treated as suffixes only when at
    least three name tokens precede them, since "JOHN V SMITH" is an initial
    and "JOHN SMITH V" is a suffix.
    """
    toks = [str(t) for t in tokens if str(t).strip()]
    sufs = []
    while len(toks) > 2:
        last = toks[-1]
        if is_suffix(last, allow_ambiguous=(len(toks) > 3)):
            sufs.insert(0, _norm(toks.pop()))
        else:
            break
    return toks, sufs
