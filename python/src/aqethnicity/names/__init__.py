"""Personal-name extraction and entity screening for administrative borrower records.

VENDORED, deliberately byte-identical apart from this note: this is the in-house
``nameparse`` v1.0.0 from the *Sorted Out* study (SSRN 7262782), so the package screens
entities exactly as the published analysis did. Do not restyle or "improve" it without
re-running the audit — its value is the validation record, not the code.

Runs entirely locally: no API key, nothing leaves the machine, nothing metered. Entity
screening is where you handle the rawest data and it needs no model, so it should not
require a network call.

Built for the PPP forgiveness study and generalised for reuse. The rules here
were derived from a stratified manual audit of 1,136 PPP borrower records; see
AUDIT.md for what that audit found and what it did not.

Typical use:

    from nameparse import parse_name, is_business, screen_frame

    parse_name("MARIA GONZALEZ JR")   -> ParsedName(first='MARIA', last='GONZALEZ', suffix='JR')
    is_business("SUNRISE LANDSCAPING") -> True

    df = screen_frame(df, name_col="BorrowerName")
"""
from .business import BUSINESS_TERMS, business_term, is_business
from .parse import ParsedName, parse_frame, parse_name, screen_frame
from .suffixes import SUFFIXES, split_suffix

__version__ = "1.0.0"
__all__ = [
           "BUSINESS_TERMS",
           "SUFFIXES",
           "ParsedName",
           "__version__",
           "business_term",
           "is_business",
           "parse_frame",
           "parse_name",
           "screen_frame",
           "split_suffix",
]
