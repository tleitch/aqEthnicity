"""The pyethnicity-compatible surface, run LOCALLY by pyethnicity itself (the ``local`` extra).

aqEthnicity does not re-bundle pyethnicity's tables or models: it calls the installed pyethnicity
and returns its result unchanged, so results are identical by construction (tests check 10,000
rows exactly). Nothing leaves your machine and no key is needed.
"""

from __future__ import annotations

from typing import Any

from ._errors import MissingDependency


def _pyethnicity():
    try:
        import pyethnicity
    except ImportError as exc:  # pragma: no cover - exercised via monkeypatch in tests
        raise MissingDependency(
            "this function runs locally and needs the 'local' extra: "
            "pip install 'aqethnicity[local]'", code="missing_dependency") from exc
    return pyethnicity


def run_bayes(fn: str, output: str, names: dict[str, Any], geo: dict[str, Any], extra: dict[str, Any]):
    """BISG/BIFSG through pyethnicity with one result row per INPUT row, in input order.

    pyethnicity 0.0.27 returns one row per DISTINCT (name, geography) key (300 inputs with 42 distinct
    keys came back as 42 rows) and in an arbitrary order. Each distinct key is therefore scored once and
    mapped back to every input row, which is exact because the Bayesian result depends only on the key.
    """
    import warnings

    import polars as pl

    from ._frames import build_columns

    given = {**names, **{k: v for k, v in geo.items() if v is not None}}
    cols, n = build_columns(**given)
    order = list(cols)
    keys = list(zip(*(cols[c] for c in order)))
    uniq = [k for k in dict.fromkeys(keys) if None not in k]   # a row with a missing name/geography cannot be scored
    if not uniq:
        from ._errors import BadRequest
        raise BadRequest("every row is missing a name or geography; nothing to score.", code="bad_request")
    ucols = {c: [k[j] for k in uniq] for j, c in enumerate(order)}
    pe_args = [ucols[c] for c in names]
    pe_geo = {c: ucols[c] for c in order if c not in names}
    result = getattr(_pyethnicity(), fn)(*pe_args, **pe_geo, **extra)
    null = "\x00NULL"
    keyed = result.select([pl.col(c).cast(pl.Utf8).fill_null(null).alias(f"_k_{c}") for c in order] +
                          [pl.all()])
    if result.height != len(uniq) or keyed.select([f"_k_{c}" for c in order]).unique().height != len(uniq):
        warnings.warn(f"pyethnicity returned {result.height} rows for {len(uniq)} distinct inputs; "
                      "falling back to its own output", stacklevel=3)
        return convert(result, output)
    inp = pl.DataFrame({f"_k_{c}": [null if v is None else v for v in cols[c]] for c in order}
                       ).with_row_index("_i")
    joined = inp.join(keyed, on=[f"_k_{c}" for c in order], how="left").sort("_i")
    # rows that were not scored (missing input) keep their inputs and get empty probabilities
    fills = [pl.coalesce([pl.col(c), pl.Series(cols[c], dtype=pl.Utf8)]).alias(c) for c in order if c in result.columns]
    joined = joined.with_columns(fills).drop(["_i", *[f"_k_{c}" for c in order]])
    return convert(joined.select(result.columns), output)


def _plain(v: Any) -> Any:
    """pandas/numpy/polars inputs -> plain lists (pyethnicity 0.0.27 rejects pandas Series); NaN -> None."""
    if v is None or isinstance(v, (str, int, float, bool, bytes)) and not (isinstance(v, float) and v != v):
        return v
    from ._frames import _as_list
    vals, _ = _as_list(v)
    return [None if isinstance(x, float) and x != x else x for x in vals]


def run(fn: str, output: str, *args: Any, keys: dict[str, Any] | None = None, **kwargs: Any):
    """Call pyethnicity and return its result, in the caller's row order.

    pyethnicity 0.0.27 returns the same rows but NOT in input order (the order also varies from run
    to run), on every polars version tried. Rows are matched back to the input through the key
    columns pyethnicity echoes (names, geography); identical keys give identical values, so this is
    exact. If the rows cannot be matched the frame is returned unchanged with a warning.
    """
    args = [_plain(a) for a in args]
    kwargs = {k: _plain(v) for k, v in kwargs.items()}
    result = getattr(_pyethnicity(), fn)(*args, **kwargs)
    if keys:
        result = _restore_order(result, keys)
    return convert(result, output)


def _restore_order(frame, keys: dict[str, Any]):
    import warnings

    import polars as pl

    from ._frames import build_columns

    given = {k: v for k, v in keys.items() if v is not None and k in frame.columns}
    if not given:
        return frame
    cols, n = build_columns(**given)
    if frame.height != n:
        warnings.warn(f"pyethnicity returned {frame.height} rows for {n} inputs; order not restored",
                      stacklevel=3)
        return frame
    names = list(cols)
    null = "\x00NULL"
    inp = pl.DataFrame({c: [null if v is None else v for v in cols[c]] for c in names}).with_row_index("_i")
    out = frame.select([pl.col(c).cast(pl.Utf8).fill_null(null).alias(c) for c in names]).with_row_index("_j")
    inp = inp.with_columns(_r=pl.int_range(pl.len()).over(names))
    out = out.with_columns(_r=pl.int_range(pl.len()).over(names))
    joined = inp.join(out, on=[*names, "_r"], how="left").sort("_i")
    if joined["_j"].null_count():
        warnings.warn("could not match pyethnicity's rows back to the input; returning its order",
                      stacklevel=3)
        return frame
    return frame[joined["_j"].to_list()]


def convert(frame, output: str):
    """pyethnicity returns a polars DataFrame; hand it back in the requested type."""
    from ._frames import to_frame
    if output == "polars":
        return frame
    return to_frame(frame.to_dict(as_series=False), output)
