"""Input normalization and output frame construction.

pyethnicity accepts a scalar *or* an array-like for every name/geography argument. We
reproduce that exactly: scalars broadcast against the longest array, and a length
mismatch between two arrays is a client-side error (no silent truncation).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

import polars as pl

from ._errors import BadRequest

_SCALARS = (str, int, float, bytes)

# Field names the service understands, and the spellings people reach for that it does NOT
# (the service ignores them silently and scores without the data, so they are refused here).
SERVICE_FIELDS = {"first_name", "middle_name", "last_name", "zcta", "tract", "block_group",
                  "address", "city", "state", "zip5"}
_ALIASES = {
    "fname": "first_name", "mname": "middle_name", "lname": "last_name",
    "first": "first_name", "middle": "middle_name", "last": "last_name",
    "firstname": "first_name", "middlename": "middle_name", "lastname": "last_name",
    "surname": "last_name", "given_name": "first_name", "zip": "zip5", "zipcode": "zip5",
    "zip_code": "zip5", "postal_code": "zip5", "bg": "block_group", "blockgroup": "block_group",
    "census_tract": "tract", "street": "address", "street_address": "address",
}


def unknown_field_message(name: str, where: str) -> str:
    hint = _ALIASES.get(name.lower())
    tail = (f" Did you mean {hint!r}?" if hint else
            f" Accepted fields: {', '.join(sorted(SERVICE_FIELDS))}.")
    return (f"unknown field {name!r} in {where}. The service would ignore it and score without "
            f"that data, so it is refused here.{tail}")


def reject_unknown(fn: str, kwargs: dict[str, Any]) -> None:
    """Raise a friendly BadRequest for unexpected keyword arguments (e.g. ``mname=``)."""
    if kwargs:
        name = next(iter(kwargs))
        raise BadRequest(unknown_field_message(name, f"{fn}()"), code="unknown_field")


def check_passthrough(passthrough: dict[str, Any] | None) -> None:
    """Passthrough columns are the caller's own, but a name the service reads as a field would be
    consumed as data rather than echoed: refuse the collision."""
    for key in passthrough or {}:
        if key.lower() in _ALIASES or key in SERVICE_FIELDS:
            raise BadRequest(unknown_field_message(key, "passthrough") +
                             " Passthrough names must not collide with field names.",
                             code="unknown_field")


def _as_list(value: Any) -> tuple[list[Any], bool] | None:
    """Coerce one argument to ``(values, was_scalar)``, or None when not supplied.

    ``was_scalar`` is the important half. A scalar is a promise that the same value
    applies to every row, so broadcasting it is what the caller asked for. A *sequence*
    of length one is not that promise — it is data, and if it does not line up with the
    other columns something is wrong with the call.
    """
    if value is None:
        return None
    if isinstance(value, _SCALARS):
        return [value], True
    if isinstance(value, pl.Series):
        return value.to_list(), False
    if hasattr(value, "tolist"):  # numpy array, pandas Series
        return list(value.tolist()), False
    if isinstance(value, Sequence):
        return list(value), False
    if isinstance(value, Iterable):
        return list(value), False
    raise BadRequest(f"unsupported argument type: {type(value).__name__}", code="bad_request")


def build_columns(**kwargs: Any) -> tuple[dict[str, list[Any]], int]:
    """Normalize keyword arguments into equal-length columns.

    Returns ``(columns, n_records)``. Arguments that are None are dropped, so the
    service sees only what the caller actually passed.

    Broadcasting rule — scalars only. ``aq.strata("JOHN", ["SMITH", "DOE"])``
    broadcasts the first name to both rows, because a bare string says "this value, every
    row". ``aq.strata(["JOHN"], ["SMITH", "DOE"])`` raises instead: two arrays of
    different lengths is a mistake in the call, and silently stretching the shorter one
    would pair JOHN with DOE and report nothing. Wrong output that looks right is the
    worst failure this library can have, so it is refused rather than guessed.
    """
    parsed = {k: _as_list(v) for k, v in kwargs.items() if v is not None}
    if not parsed:
        raise BadRequest("no input columns supplied", code="bad_request")

    raw = {k: v[0] for k, v in parsed.items()}
    scalar = {k: v[1] for k, v in parsed.items()}
    lengths = {k: len(v) for k, v in raw.items()}
    n = max(lengths.values())

    ragged = {
        k: length for k, length in lengths.items() if not scalar[k] and length != n
    }
    if ragged:
        longest = max((k for k in lengths if not scalar[k] or lengths[k] == n),
                      key=lambda k: lengths[k])
        detail = ", ".join(f"{k}={length}" for k, length in sorted(ragged.items()))
        raise BadRequest(
            f"length mismatch: {detail} but {longest}={n}. Sequences must all be the same "
            "length; pass a scalar (not a one-element list) for a value that repeats.",
            code="bad_request",
        )
    if n == 0:
        raise BadRequest("no input records supplied", code="bad_request")

    columns = {k: (v * n if scalar[k] and len(v) == 1 else v) for k, v in raw.items()}
    # Stringify geography-ish and name-ish values so a leading zero in a GEOID or ZCTA
    # survives the trip (11201 is fine as an int; 04013104501 is not).
    for key, values in columns.items():
        columns[key] = [None if (v is None or (isinstance(v, float) and v != v)) else str(v) for v in values]
    return columns, n


def to_frame(columns: dict[str, list[Any]], output: str = "polars"):
    """Build the requested output frame type from the service's columnar payload."""
    if output == "polars":
        return pl.DataFrame(columns)
    if output == "pandas":
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover
            raise BadRequest(
                "output='pandas' requires pandas — pip install 'aqethnicity[pandas]'",
                code="bad_request",
            ) from exc
        return pd.DataFrame(columns)
    if output == "dict":
        return columns
    raise BadRequest(
        f"output must be one of 'polars', 'pandas', 'dict' (got {output!r})", code="bad_request"
    )
