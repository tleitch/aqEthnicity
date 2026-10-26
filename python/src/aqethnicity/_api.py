"""The public functions.

Two families:

* **pyethnicity-compatible** (``bisg``, ``bisg6``, ``bifsg``, ``bifsg6``, ``predict_race``,
  ``predict_race_fl``, ``predict_race_flg``): run **locally** by pyethnicity
  (``pip install 'aqethnicity[local]'``), same names and signatures, identical results, no key and
  nothing leaves your machine. Pass ``address``/``city``/``state``/``zip5`` instead of a GEOID and the
  call goes to the hosted service (key required), which resolves the address for you.
  ``predict_sex_f`` and ``predict_sex_ssa`` are hosted: pyethnicity 0.0.27's own versions fail
  (``TypeError`` for every input; a removed polars method). Results come back in YOUR row order,
  which pyethnicity 0.0.27 does not guarantee.
* **hosted**: ``strata()`` and its tier variants (aqEthnicity STRATA: 5-class probabilities, an
  uncertainty index, address input) and ``geocode()``. These need an API key
  (``aqethnicity.set_api_key(...)`` or the ``AEQUUM_API_KEY`` environment variable).

Unknown keyword arguments such as ``mname=`` are refused here, because the service would otherwise
ignore them and score without the data.
"""

from __future__ import annotations

from typing import Any

from . import _local
from ._frames import build_columns, check_passthrough, reject_unknown, to_frame
from ._transport import Client, default_client

_ADDRESS_KEYS = ("address", "city", "state", "zip5")


def _has_address(*vals: Any) -> bool:
    return any(v is not None for v in vals)


def _call(
    path: str,
    columns: dict[str, list[Any]],
    options: dict[str, Any],
    output: str,
    client: Client | None,
    chunksize: int | None,
):
    cl = client or default_client()
    result = cl.predict(path, columns, options, chunksize=chunksize)
    return to_frame(result, output)


def geocode(
    address: Any,
    city: Any = None,
    state: Any = None,
    zip5: Any = None,
    *,
    output: str = "polars",
    client: Client | None = None,
    chunksize: int | None = None,
    **unknown: Any,
):
    """Resolve US addresses to census geography (hosted; needs a key).

    Returns ``lookup_level`` (BG / TRACT / ZIP / NONE) and ``lookup_conf`` for every row.
    The GEOIDs themselves are a premium feature; without that entitlement the level tells
    you how precisely the address matched but not which tract it landed in.

    >>> aq.geocode("9644 N 10TH AVE", "PHOENIX", "AZ", "85021")
    """
    reject_unknown("geocode", unknown)
    columns, _ = build_columns(address=address, city=city, state=state, zip5=zip5)
    return _call("/v1/geocode", columns, {}, output, client, chunksize)


_TIER_RANK = {"NONE": 0, "ZIP": 1, "TRACT": 2, "BG": 3}
_TIER_FOR = {"bgt": "BG", "tract": "TRACT", "zcta": "ZIP", "name": "NONE"}


def tier_coverage(
    address: Any,
    city: Any = None,
    state: Any = None,
    zip5: Any = None,
    *,
    output: str = "polars",
    client: Client | None = None,
    chunksize: int | None = None,
    **unknown: Any,
):
    """Per-row: the finest STRATA tier each address can reach, and which tiers it can serve (hosted).

    Resolves geography once, scores nothing, and returns a full picture (``lookup_level``,
    ``lookup_conf`` and a ``can_*`` flag per tier), for measuring rejection rates without the
    exception a forced-tier call raises on its first short chunk.
    """
    reject_unknown("tier_coverage", unknown)
    frame = geocode(
        address, city, state, zip5, output="polars", client=client, chunksize=chunksize
    )
    import polars as pl

    rank = pl.col("lookup_level").replace_strict(_TIER_RANK, default=0)
    frame = frame.with_columns(
        can_bgt=rank >= _TIER_RANK["BG"],
        can_tract=rank >= _TIER_RANK["TRACT"],
        can_zcta=rank >= _TIER_RANK["ZIP"],
        can_name=pl.lit(True),  # name-only needs no geography
    )
    return to_frame({c: frame[c].to_list() for c in frame.columns}, output)


# --------------------------------------------------------------------------
# pyethnicity-compatible: local by default, hosted only when an address is given
# --------------------------------------------------------------------------
def _bayes(fn, names, geo, extra, output, client, address, city, state, zip5, unknown, hosted_opts):
    reject_unknown(fn, unknown)
    if _has_address(address, city, state, zip5):
        columns, _ = build_columns(**names, **geo, address=address, city=city, state=state, zip5=zip5)
        return _call(f"/v1/predict/{fn}", columns, hosted_opts, output, client, None)
    return _local.run_bayes(fn, output, names, geo, extra)


def bisg(last_name: Any, zcta: Any = None, tract: Any = None, block_group: Any = None,
         drop_intermediate: bool = True, *, address: Any = None, city: Any = None,
         state: Any = None, zip5: Any = None, output: str = "polars",
         client: Client | None = None, **unknown: Any):
    """Bayesian Improved Surname Geocoding (4-class: Asian, Black, Hispanic, White). Local.

    >>> aq.bisg("GARCIA", zcta="11201")
    """
    return _bayes("bisg", {"last_name": last_name},
                  {"zcta": zcta, "tract": tract, "block_group": block_group},
                  {"drop_intermediate": drop_intermediate}, output, client,
                  address, city, state, zip5, unknown, {"drop_intermediate": drop_intermediate})


def bisg6(last_name: Any, zcta: Any = None, tract: Any = None, block_group: Any = None,
          drop_intermediate: bool = True, *, address: Any = None, city: Any = None,
          state: Any = None, zip5: Any = None, output: str = "polars",
          client: Client | None = None, **unknown: Any):
    """BISG, 6-class variant (adds AIAN and multiracial). Local."""
    return _bayes("bisg6", {"last_name": last_name},
                  {"zcta": zcta, "tract": tract, "block_group": block_group},
                  {"drop_intermediate": drop_intermediate}, output, client,
                  address, city, state, zip5, unknown, {"drop_intermediate": drop_intermediate})


def bifsg(first_name: Any, last_name: Any, zcta: Any = None, tract: Any = None,
          block_group: Any = None, drop_intermediate: bool = True, *, address: Any = None,
          city: Any = None, state: Any = None, zip5: Any = None, output: str = "polars",
          client: Client | None = None, **unknown: Any):
    """Bayesian Improved First Name Surname Geocoding (4-class). Local."""
    return _bayes("bifsg", {"first_name": first_name, "last_name": last_name},
                  {"zcta": zcta, "tract": tract, "block_group": block_group},
                  {"drop_intermediate": drop_intermediate}, output, client,
                  address, city, state, zip5, unknown, {"drop_intermediate": drop_intermediate})


def bifsg6(first_name: Any, last_name: Any, zcta: Any = None, tract: Any = None,
           block_group: Any = None, drop_intermediate: bool = True, *, address: Any = None,
           city: Any = None, state: Any = None, zip5: Any = None, output: str = "polars",
           client: Client | None = None, **unknown: Any):
    """BIFSG, 6-class variant. Local."""
    return _bayes("bifsg6", {"first_name": first_name, "last_name": last_name},
                  {"zcta": zcta, "tract": tract, "block_group": block_group},
                  {"drop_intermediate": drop_intermediate}, output, client,
                  address, city, state, zip5, unknown, {"drop_intermediate": drop_intermediate})


def predict_sex_ssa(first_name: Any, min_year: int = 1880, max_year: int = 2022,
                    correct_skew: bool = True, *, output: str = "polars",
                    client: Client | None = None, **unknown: Any):
    """Sex from first name using SSA birth-name frequencies over a year range. HOSTED (needs a key).

    pyethnicity 0.0.27's own ``predict_sex_ssa`` fails on current polars (it calls the removed
    ``LazyFrame.groupby``), so this runs on the service.
    """
    reject_unknown("predict_sex_ssa", unknown)
    columns, _ = build_columns(first_name=first_name)
    options = {"min_year": min_year, "max_year": max_year, "correct_skew": correct_skew}
    return _call("/v1/predict/predict_sex_ssa", columns, options, output, client, None)


def predict_race_fl(first_name: Any, last_name: Any, chunksize: int | None = None, *,
                    output: str = "polars", **unknown: Any):
    """Name-only race prediction (bidirectional LSTM, 4-class). Local."""
    reject_unknown("predict_race_fl", unknown)
    kw = {"chunksize": chunksize} if chunksize else {}
    return _local.run("predict_race_fl", output, first_name, last_name,
                      keys={"first_name": first_name, "last_name": last_name}, **kw)


def predict_race_flg(first_name: Any, last_name: Any, zcta: Any = None, tract: Any = None,
                     block_group: Any = None, chunksize: int | None = None, *,
                     address: Any = None, city: Any = None, state: Any = None, zip5: Any = None,
                     output: str = "polars", client: Client | None = None, **unknown: Any):
    """Name + geography race prediction (4-class). Local; hosted when an address is given."""
    reject_unknown("predict_race_flg", unknown)
    if _has_address(address, city, state, zip5):
        columns, _ = build_columns(first_name=first_name, last_name=last_name, zcta=zcta,
                                   tract=tract, block_group=block_group, address=address,
                                   city=city, state=state, zip5=zip5)
        return _call("/v1/predict/predict_race_flg", columns, {}, output, client, chunksize)
    kw = {"chunksize": chunksize} if chunksize else {}
    return _local.run("predict_race_flg", output, first_name, last_name, zcta=zcta, tract=tract,
                      block_group=block_group, **kw,
                      keys={"first_name": first_name, "last_name": last_name, "zcta": zcta,
                            "tract": tract, "block_group": block_group})


def predict_race(first_name: Any, last_name: Any, zcta: Any = None, tract: Any = None,
                 block_group: Any = None, weights: list[float] | None = None,
                 chunksize: int | None = None, *, address: Any = None, city: Any = None,
                 state: Any = None, zip5: Any = None, output: str = "polars",
                 client: Client | None = None, **unknown: Any):
    """Ensemble of BISG, BIFSG and the name+geo LSTM (4-class). Local; hosted when an address is given.

    ``weights`` is the 3-element ensemble weighting; pyethnicity's default is ``[1, 1, 1]``.
    """
    reject_unknown("predict_race", unknown)
    if _has_address(address, city, state, zip5):
        columns, _ = build_columns(first_name=first_name, last_name=last_name, zcta=zcta,
                                   tract=tract, block_group=block_group, address=address,
                                   city=city, state=state, zip5=zip5)
        opts = {"weights": list(weights)} if weights is not None else {}
        return _call("/v1/predict/predict_race", columns, opts, output, client, chunksize)
    kw: dict[str, Any] = {}
    if weights is not None:
        kw["weights"] = list(weights)
    if chunksize:
        kw["chunksize"] = chunksize
    return _local.run("predict_race", output, first_name, last_name, zcta=zcta, tract=tract,
                      block_group=block_group, **kw,
                      keys={"first_name": first_name, "last_name": last_name, "zcta": zcta,
                            "tract": tract, "block_group": block_group})


def predict_sex_f(first_name: Any, chunksize: int | None = None, *, output: str = "polars",
                  client: Client | None = None, **unknown: Any):
    """Sex from first name (character-level model). HOSTED (needs a key).

    pyethnicity 0.0.27's own ``predict_sex_f`` raises ``TypeError`` for every input (it iterates a
    polars expression); the service runs the same ONNX model with that step corrected.
    """
    reject_unknown("predict_sex_f", unknown)
    columns, _ = build_columns(first_name=first_name)
    return _call("/v1/predict/predict_sex_f", columns, {}, output, client, chunksize)


# --------------------------------------------------------------------------
# STRATA (Aequum, 5-class + uncertainty index)
# --------------------------------------------------------------------------
def _strata(
    tier: str,
    first_name: Any,
    last_name: Any,
    middle_name: Any,
    zcta: Any,
    tract: Any,
    block_group: Any,
    address: Any,
    city: Any,
    state: Any,
    zip5: Any,
    passthrough: dict[str, Any] | None,
    output: str,
    client: Client | None,
    chunksize: int | None,
    model: str | None = None,
):
    check_passthrough(passthrough)
    columns, _ = build_columns(
        first_name=first_name, middle_name=middle_name, last_name=last_name,
        zcta=zcta, tract=tract, block_group=block_group,
        address=address, city=city, state=state, zip5=zip5,
        **(passthrough or {}),
    )
    options: dict[str, Any] = {}
    if passthrough:
        options["passthrough"] = list(passthrough.keys())
    if model:
        options["model"] = model
    return _call(f"/v1/strata/{tier}", columns, options, output, client, chunksize)


def strata(
    first_name: Any,
    last_name: Any,
    zcta: Any = None,
    tract: Any = None,
    block_group: Any = None,
    *,
    middle_name: Any = None,
    address: Any = None,
    city: Any = None,
    state: Any = None,
    zip5: Any = None,
    passthrough: dict[str, Any] | None = None,
    model: str | None = None,
    output: str = "polars",
    client: Client | None = None,
    chunksize: int | None = None,
    **unknown: Any,
):
    """STRATA waterfall: scores each record at the highest tier its geography supports.

    Returns 5-class posteriors (``p_white``, ``p_black``, ``p_hispanic``, ``p_asian``,
    ``p_other``), ``dominant_race``, the uncertainty index ``iu``, ``lookup_level``, and
    anonymous cohort tokens.

    ``model`` selects the family. The default ``"M8"`` is trained on voter registration
    **and PPP**; ``"M2"`` is trained on FL/GA/NC voter registration only with no PPP
    anywhere in training, which is what the *Sorted Out* paper uses and the only
    non-circular choice when scoring PPP records. Columns passed via ``passthrough`` are echoed back so
    downstream joins (e.g. CREST simulation over loan amounts) line up row-for-row.

    Examples
    --------
    >>> aq.strata("MARIA", "GARCIA", address="9644 N 10TH AVE",
    ...               city="PHOENIX", state="AZ", zip5="85021",
    ...               passthrough={"loan_id": ["L-1"]})
    """
    reject_unknown("strata", unknown)
    return _strata(
        "auto", first_name, last_name, middle_name, zcta, tract, block_group,
        address, city, state, zip5, passthrough, output, client, chunksize, model,
    )


def stratabgt(
    first_name: Any,
    last_name: Any,
    block_group: Any = None,
    tract: Any = None,
    *,
    middle_name: Any = None,
    address: Any = None,
    city: Any = None,
    state: Any = None,
    zip5: Any = None,
    passthrough: dict[str, Any] | None = None,
    model: str | None = None,
    output: str = "polars",
    client: Client | None = None,
    chunksize: int | None = None,
    **unknown: Any,
):
    """STRATA block-group + tract tier (highest resolution).

    Records that cannot reach block-group resolution are reported as unscored rather
    than silently demoted — use :func:`strata` when you want graceful degradation.
    """
    reject_unknown("stratabgt", unknown)
    return _strata(
        "bgt", first_name, last_name, middle_name, None, tract, block_group,
        address, city, state, zip5, passthrough, output, client, chunksize, model,
    )


def stratatract(
    first_name: Any,
    last_name: Any,
    tract: Any = None,
    *,
    middle_name: Any = None,
    address: Any = None,
    city: Any = None,
    state: Any = None,
    zip5: Any = None,
    passthrough: dict[str, Any] | None = None,
    model: str | None = None,
    output: str = "polars",
    client: Client | None = None,
    chunksize: int | None = None,
    **unknown: Any,
):
    """STRATA census-tract tier."""
    reject_unknown("stratatract", unknown)
    return _strata(
        "tract", first_name, last_name, middle_name, None, tract, None,
        address, city, state, zip5, passthrough, output, client, chunksize, model,
    )


def stratazcta(
    first_name: Any,
    last_name: Any,
    zcta: Any = None,
    *,
    middle_name: Any = None,
    address: Any = None,
    city: Any = None,
    state: Any = None,
    zip5: Any = None,
    passthrough: dict[str, Any] | None = None,
    model: str | None = None,
    output: str = "polars",
    client: Client | None = None,
    chunksize: int | None = None,
    **unknown: Any,
):
    """STRATA ZCTA tier."""
    reject_unknown("stratazcta", unknown)
    return _strata(
        "zcta", first_name, last_name, middle_name, zcta, None, None,
        address, city, state, zip5, passthrough, output, client, chunksize, model,
    )


def strataname(
    first_name: Any,
    last_name: Any,
    *,
    middle_name: Any = None,
    passthrough: dict[str, Any] | None = None,
    model: str | None = None,
    output: str = "polars",
    client: Client | None = None,
    chunksize: int | None = None,
    **unknown: Any,
):
    """STRATA name-only tier (no geography)."""
    reject_unknown("strataname", unknown)
    return _strata(
        "name", first_name, last_name, middle_name, None, None, None,
        None, None, None, None, passthrough, output, client, chunksize, model,
    )
