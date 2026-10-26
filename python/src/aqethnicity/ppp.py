"""Pull SBA PPP loan data and reduce it to scorable individual-owner records.

This is the front half of the *Sorted Out* pipeline, packaged so a user can do it
themselves: download the public SBA files, decide which records belong to a natural
person, and split names into the fields the models need.

Everything here runs **locally**. No names or addresses leave the machine, nothing is
metered, and no API key is required — you only need the API for scoring and geocoding.
That is deliberate: entity screening is the step where you are handling the rawest data,
and it is also the step that needs no model.

Note on the source: PPP is **SBA** (FOIA release), not CFPB. CFPB publishes HMDA, which
contains no borrower names at all — so name-based inference is impossible on HMDA and only
the geography tiers apply there.

    import aqethnicity as aq
    aqethnicity.ppp.download("~/ppp")                       # ~5.3 GB, 13 files
    df  = aqethnicity.ppp.load("~/ppp")
    ind = aqethnicity.ppp.individual_owners(df)             # the paper's universe
    ind = aqethnicity.ppp.split_names(ind)                  # -> fname / mname / lname
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

# SBA serves these as plain static files under a distribution directory — there are no
# per-file resource IDs, which is what an earlier version of this module wrongly assumed.
# Verified 2026-08-17: all 13 return 200 with Content-Type text/csv.
RELEASE = "240930"
DATASET_PAGE = "https://data.sba.gov/dataset/ppp-foia"
DISTRIBUTION = "https://data.sba.gov/sites/default/files/distribution/SBA-OCA-2022-07-001"
FILENAMES: tuple[str, ...] = (
    f"public_150k_plus_{RELEASE}.csv",
) + tuple(f"public_up_to_150k_{i}_{RELEASE}.csv" for i in range(1, 13))

# First line of every PPP file. Used to reject an HTML error page saved as .csv — SBA
# returns a styled 404 body, and a naive download writes it out with a .csv name.
EXPECTED_HEADER_PREFIX = "LoanNumber,DateApproved,SBAOfficeCode,ProcessingMethod,BorrowerName"

# Legal forms that can plausibly be a natural person. Stage 1 of the paper's filter; this
# alone removes most corporations, non-profits and partnerships.
INDIVIDUAL_BUSINESS_TYPES = (
    "Sole Proprietorship",
    "Self-Employed Individuals",
    "Independent Contractors",
    "Single Member LLC",
)

NAME_COL = "BorrowerName"
ADDRESS_COLS = ("BorrowerAddress", "BorrowerCity", "BorrowerState", "BorrowerZip")


def urls(*, discover: bool = True) -> list[str]:
    """Download URLs for the pinned release.

    By default this reads SBA's dataset page and takes the links it advertises, because
    that page is the only authoritative index — SBA re-cuts releases and moves files, and
    a hardcoded list silently rots. ``discover=False`` uses the verified static paths
    without a network call (useful offline, and for tests).

    If discovery finds nothing recognizable, it falls back to the static paths rather than
    returning an empty list, and never invents a URL.
    """
    if discover:
        try:
            import re

            import httpx

            html = httpx.get(DATASET_PAGE, follow_redirects=True, timeout=60).text
            found = sorted(
                set(
                    re.findall(
                        r"https?://[^\s\"'<>]+public_(?:150k_plus|up_to_150k)[^\s\"'<>]*\.csv",
                        html,
                    )
                )
            )
            if found:
                return found
        except Exception as exc:  # noqa: BLE001 — a network problem must not mean "no files"
            import logging

            logging.getLogger("aqethnicity.ppp").warning(
                "could not read %s (%s); using the pinned file list", DATASET_PAGE, exc
            )
    return [f"{DISTRIBUTION}/{name}" for name in FILENAMES]


def _looks_like_ppp_csv(path: Path) -> bool:
    with path.open("rb") as fh:
        head = fh.read(256).decode("utf-8", "replace").lstrip("\ufeff").lstrip()
    return head.startswith(EXPECTED_HEADER_PREFIX)


def download(dest: str | os.PathLike, *, overwrite: bool = False) -> list[Path]:
    """Fetch the public PPP files (~5.3 GB total). Resumes by skipping complete files.

    Every file is validated before it is accepted: the response must not be HTML and the
    first line must be the PPP header. A server that answers a bad path with a styled 404
    page and HTTP 200 would otherwise leave a plausible-looking .csv full of markup, and
    the corruption would only surface much later as a parse error.
    """
    import httpx

    out = Path(os.path.expanduser(str(dest)))
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for url in urls():
        target = out / url.rsplit("/", 1)[-1]
        if target.exists() and target.stat().st_size > 0 and not overwrite:
            if not _looks_like_ppp_csv(target):
                raise OSError(
                    f"{target} exists but is not a PPP CSV (likely a saved error page). "
                    "Delete it and re-run, or pass overwrite=True."
                )
            written.append(target)
            continue

        tmp = target.with_suffix(target.suffix + ".part")
        with httpx.stream("GET", url, follow_redirects=True, timeout=None) as resp:
            resp.raise_for_status()
            ctype = resp.headers.get("content-type", "")
            if "html" in ctype.lower():
                raise OSError(
                    f"{url} returned {ctype} instead of CSV — the release was probably "
                    "re-cut. Check {DATASET_PAGE} for the current file list."
                )
            with tmp.open("wb") as fh:
                for chunk in resp.iter_bytes(1 << 20):
                    fh.write(chunk)

        if not _looks_like_ppp_csv(tmp):
            tmp.unlink(missing_ok=True)
            raise OSError(
                f"{url} did not begin with the PPP header; refusing to keep it. "
                f"Check {DATASET_PAGE} for the current file list."
            )
        tmp.rename(target)
        written.append(target)
    return written


def load(source: str | os.PathLike, columns: Iterable[str] | None = None):
    """Read the downloaded CSVs as one polars DataFrame.

    The files do not all carry identical columns across releases, so this unions by name
    rather than assuming a fixed schema — the same thing the study's DuckDB loader did with
    ``union_by_name=true``.
    """
    import polars as pl

    src = Path(os.path.expanduser(str(source)))
    paths = sorted(src.glob("public_*.csv")) if src.is_dir() else [src]
    if not paths:
        raise FileNotFoundError(f"no public_*.csv under {src} — run aqethnicity.ppp.download first")

    frames = []
    for path in paths:
        # The SBA files are NOT valid UTF-8 — they carry latin-1 bytes in names and
        # addresses, and a strict read dies with "invalid utf-8 sequence" on the very first
        # file. Lossy decoding replaces those bytes; the model's name encoder maps any
        # character it does not know to a single "unknown" symbol anyway, so this costs
        # nothing at scoring time, but it does mean an accented name is not byte-faithful
        # if you re-export it.
        frame = pl.read_csv(
            path, infer_schema_length=10_000, ignore_errors=True, encoding="utf8-lossy",
            schema_overrides={"BorrowerZip": pl.String, "NAICSCode": pl.String},
        )
        if columns:
            keep = [c for c in columns if c in frame.columns]
            frame = frame.select(keep)
        frames.append(frame)
    return pl.concat(frames, how="diagonal_relaxed")


def individual_owners(
    df, *, business_type_col: str = "BusinessType", strict: bool = True,
    max_name_tokens: int | None = 2,
):
    """Reduce to loan records held by a natural person — the paper's analytic universe.

    Two stages, in this order:

    1. **Legal form.** Keep only ``INDIVIDUAL_BUSINESS_TYPES``. An administrative field
       removes most non-individuals cheaply and without judgement.
    2. **Name screening.** What survives stage 1 still includes trade names filed under an
       individual legal form ("SUNRISE LANDSCAPING" as a sole proprietorship), which carry
       no personal name to infer from. :mod:`aqethnicity.names` flags those.

    ``strict=True`` also drops names that do not parse to a first and last name. That is
    what the published analysis did (it required exactly two alpha tokens), and it is the
    conservative choice: a record with no usable name cannot be scored honestly.

    The screening rules are deliberately biased against false positives — a wrongly
    flagged business removes a *real person* from the sample. Measured on 1,072 confirmed
    real people: zero false positives. The cost is recall: it catches roughly 15% of true
    non-persons, so residual trade names remain. See ``aqethnicity/names/AUDIT.md``.
    """
    import polars as pl

    from .names import parse_name

    if business_type_col in df.columns:
        df = df.filter(pl.col(business_type_col).is_in(INDIVIDUAL_BUSINESS_TYPES))

    # include_entity=True is required here, not optional. Stage 1 deliberately KEEPS
    # "Single Member LLC" as a legal form, so entity suffixes are expected in these names
    # and must be caught by the name screen — otherwise "CINCY GM LLC" is scored as a
    # person with the surname "LLC".
    parsed = [parse_name(v, include_entity=True) for v in df[NAME_COL].to_list()]

    df = df.with_columns(
        pl.Series("np_is_business", [p.is_business for p in parsed]),
        pl.Series("np_business_term", [p.business_term for p in parsed]),
        pl.Series("np_first", [p.first for p in parsed]),
        pl.Series("np_last", [p.last for p in parsed]),
        pl.Series("np_tokens", [p.n_tokens for p in parsed]),
    ).filter(~pl.col("np_is_business"))

    if strict:
        df = df.filter(pl.col("np_first").is_not_null() & pl.col("np_last").is_not_null())
    if max_name_tokens is not None:
        # The published analysis required exactly two alpha tokens. Without it,
        # "DR. KENNETH LEBOW, OPTOMETRIST" parses to first=DR last=OPTOMETRIST — a
        # confident answer about a string that carries a title and an occupation, not a
        # clean personal name. Pass max_name_tokens=None to keep those and handle them
        # yourself.
        df = df.filter(pl.col("np_tokens") <= max_name_tokens)
    return df


def split_names(df, *, name_col: str = NAME_COL):
    """Add ``fname`` / ``mname`` / ``lname`` in the shape the models expect.

    All three are required: the heads read fname/mname/lname, and a missing ``mname``
    column is a hard error rather than an empty string.
    """
    import polars as pl

    from .names import parse_name

    parsed = [parse_name(v) for v in df[name_col].to_list()]
    return df.with_columns(
        pl.Series("fname", [(p.first or "") for p in parsed]),
        pl.Series("mname", [(p.middle or "") for p in parsed]),
        pl.Series("lname", [(p.last or "") for p in parsed]),
    )


def screening_report(
    df, *, business_type_col: str = "BusinessType", max_name_tokens: int | None = 2
) -> dict[str, Any]:
    """Counts at each screening stage, so a shrinking sample is explainable.

    Mirrors :func:`individual_owners` exactly — if the two drift, the report stops being
    an explanation and becomes a second opinion.
    """
    import polars as pl

    from .names import parse_name

    total = df.height
    subset = (
        df.filter(pl.col(business_type_col).is_in(INDIVIDUAL_BUSINESS_TYPES))
        if business_type_col in df.columns
        else df
    )
    stage1 = subset.height
    parsed = [parse_name(v, include_entity=True) for v in subset[NAME_COL].to_list()]
    flagged = sum(p.is_business for p in parsed)
    rest = [p for p in parsed if not p.is_business]
    unparsed = sum(1 for p in rest if not (p.first and p.last))
    too_many = (
        sum(1 for p in rest if p.first and p.last and p.n_tokens > max_name_tokens)
        if max_name_tokens is not None
        else 0
    )
    return {
        "records": total,
        "individual_legal_form": stage1,
        "flagged_as_business_name": flagged,
        "no_usable_name": unparsed,
        "too_many_name_tokens": too_many,
        "scorable": stage1 - flagged - unparsed - too_many,
    }
