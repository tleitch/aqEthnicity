"""Parse an administrative name string into first and last name."""
import re
from dataclasses import asdict, dataclass

from .business import business_term
from .suffixes import split_suffix

_PUNCT = re.compile(r"[^\w\s'\-]")
_WS = re.compile(r"\s+")

@dataclass
class ParsedName:
    first: str | None = None
    last: str | None = None
    middle: str | None = None
    suffix: str | None = None
    is_business: bool = False
    business_term: str | None = None
    n_tokens: int = 0
    flag: str | None = None      # why parsing is uncertain, if it is
    def as_dict(self): return asdict(self)

def parse_name(raw, *, screen_business=True, include_entity=False) -> ParsedName:
    """Parse one name string.

    Order matters: business screening runs first, because a trade name has no
    correct first/last and forcing one produces confident nonsense.
    """
    s = _WS.sub(" ", str(raw or "").strip())
    if not s:
        return ParsedName(flag="empty")
    if screen_business:
        term = business_term(s, include_entity=include_entity)
        if term:
            return ParsedName(is_business=True, business_term=term,
                              n_tokens=len(s.split()), flag="business")
    toks = [t for t in _PUNCT.sub(" ", s).split() if t]
    n = len(toks)
    if n == 0: return ParsedName(flag="empty")
    if n == 1: return ParsedName(first=toks[0].upper(), n_tokens=1, flag="single_token")
    name_toks, sufs = split_suffix(toks)
    first = name_toks[0].upper()
    last = name_toks[-1].upper()
    middle = " ".join(t.upper() for t in name_toks[1:-1]) or None
    flag = None
    if len(last) == 1: flag = "single_letter_surname"
    elif sufs and len(name_toks) == 2: flag = "suffix_stripped_to_minimum"
    return ParsedName(first=first, last=last, middle=middle,
                      suffix=" ".join(sufs) or None, n_tokens=n, flag=flag)

def parse_frame(df, name_col="BorrowerName", prefix="np_", **kw):
    """Parse a whole DataFrame column; returns df with prefixed columns added."""
    import pandas as pd
    out = df[name_col].map(lambda x: parse_name(x, **kw).as_dict())
    parsed = pd.DataFrame(list(out), index=df.index).add_prefix(prefix)
    return df.join(parsed)

def screen_frame(df, name_col="BorrowerName", **kw):
    """Convenience: parse, then return (individuals, businesses)."""
    d = parse_frame(df, name_col=name_col, **kw)
    biz = d[d["np_is_business"]]
    ind = d[~d["np_is_business"]]
    return ind, biz
