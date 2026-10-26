"""aqEthnicity's local functions must return EXACTLY what pyethnicity returns (10,000 rows)."""
import pathlib
import random

import polars as pl
import pyethnicity as pe
import pytest

import aqethnicity as aq

DATA = pathlib.Path(pe.__file__).parent / "data" / "distributions"
N = 10_000


def _col(path, name):
    return pl.read_parquet(DATA / path)[name].unique(maintain_order=True).to_list()


@pytest.fixture(scope="module")
def rows():
    rnd = random.Random(2026)
    last = _col("prob_race_given_last_name.parquet", "name")
    first = _col("prob_race_given_first_name.parquet", "name")
    zcta = _col("prob_race_given_zcta_2020.parquet", "zcta5")
    pick = lambda xs: [rnd.choice(xs) for _ in range(N)]  # noqa: E731
    lasts, firsts, zctas = pick(last), pick(first), pick(zcta)
    for i in range(0, N, 97):                    # names/places the tables don't know: nulls must match too
        lasts[i] = "XQZZFAKENAME"
        zctas[i + 1 if i + 1 < N else i] = "00000"
    return lasts, firsts, zctas


def same(a, b, keys=None):
    """aq's frame must hold EXACTLY the rows pyethnicity returns (bitwise-equal values).

    pyethnicity 0.0.27 does not return rows in input order (and the order varies between runs),
    so equality is checked on both frames sorted by every column; aq's frame must additionally be
    in the caller's row order (``keys`` = the input columns it echoes)."""
    assert a.columns == b.columns and a.shape == b.shape
    srt = lambda f: f.sort(f.columns, nulls_last=True)  # noqa: E731
    assert srt(a).equals(srt(b)), "frames differ"       # exact: polars equals treats nulls as equal
    for col, vals in (keys or {}).items():
        assert a[col].to_list() == [None if v is None else str(v) for v in vals], f"{col} not in input order"


def test_bisg_10k_exact(rows):
    lasts, _, z = rows
    same(aq.bisg(lasts, zcta=z), pe.bisg(lasts, zcta=z), {"last_name": lasts, "zcta": z})


def test_bisg6_10k_exact(rows):
    lasts, _, z = rows
    same(aq.bisg6(lasts, zcta=z), pe.bisg6(lasts, zcta=z), {"last_name": lasts, "zcta": z})


def test_bifsg_10k_exact(rows):
    lasts, firsts, z = rows
    same(aq.bifsg(firsts, lasts, zcta=z), pe.bifsg(firsts, lasts, zcta=z), {"first_name": firsts, "last_name": lasts, "zcta": z})


def test_bifsg6_10k_exact(rows):
    lasts, firsts, z = rows
    same(aq.bifsg6(firsts, lasts, zcta=z), pe.bifsg6(firsts, lasts, zcta=z), {"first_name": firsts, "last_name": lasts, "zcta": z})


def test_drop_intermediate_false_exact(rows):
    lasts, _, z = rows
    same(aq.bisg(lasts[:2000], zcta=z[:2000], drop_intermediate=False),
         pe.bisg(lasts[:2000], zcta=z[:2000], drop_intermediate=False))


def test_scalar_broadcast_matches(rows):
    same(aq.bisg("GARCIA", zcta="11201"), pe.bisg("GARCIA", zcta="11201"))


def close(a, b, keys, atol=2e-5):
    """The ONNX models are not bitwise-repeatable across batch compositions (pyethnicity's own two
    consecutive calls differ in the last float32 bits, and its row order varies), so the ML functions
    are compared to a 2e-5 tolerance on frames sorted by key then value (measured difference between aq and pyethnicity: 6e-8, the same as between two pyethnicity calls)."""
    import numpy as np
    assert a.columns == b.columns and a.shape == b.shape
    num = [c for c in a.columns if a[c].dtype.is_float()]
    srt = lambda f: f.sort([*[c for c in a.columns if c not in num], *num])  # noqa: E731
    sa, sb = srt(a), srt(b)
    for c in a.columns:
        if c in num:
            assert np.allclose(sa[c].to_numpy(), sb[c].to_numpy(), atol=atol, equal_nan=True), c
        else:
            assert sa[c].to_list() == sb[c].to_list(), c
    for col, vals in keys.items():
        assert a[col].to_list() == [str(v) for v in vals], f"{col} not in input order"


def test_ml_models_close_on_2k(rows):
    lasts, firsts, z = rows
    f, l, zz = firsts[:2000], lasts[:2000], z[:2000]
    k = {"first_name": f, "last_name": l}
    close(aq.predict_race_fl(f, l), pe.predict_race_fl(f, l), k)
    close(aq.predict_race_flg(f, l, zcta=zz), pe.predict_race_flg(f, l, zcta=zz), k)
    close(aq.predict_race(f, l, zcta=zz), pe.predict_race(f, l, zcta=zz), k)


def test_output_pandas_and_dict(rows):
    lasts, _, z = rows
    pdf = aq.bisg(lasts[:50], zcta=z[:50], output="pandas")
    assert list(pdf.columns) == pe.bisg(lasts[:50], zcta=z[:50]).columns
    d = aq.bisg(lasts[:50], zcta=z[:50], output="dict")
    assert set(d) == set(pdf.columns) and len(d["last_name"]) == 50


def test_surface_is_a_superset_of_pyethnicity():
    import inspect
    for name in [n for n in dir(pe) if not n.startswith("_") and callable(getattr(pe, n)) and n != "utils"]:
        mine = inspect.signature(getattr(aq, name)).parameters
        theirs = [p for p in inspect.signature(getattr(pe, name)).parameters if not p.startswith("_")]
        missing = [p for p in theirs if p not in mine]
        # chunksize is not exposed on the pure-Bayesian functions in either library
        assert not missing, f"{name} lacks pyethnicity parameters {missing}"


# ---- pyethnicity 0.0.27 collapses repeated keys and rejects pandas; aqEthnicity must not
def test_repeated_keys_give_one_row_per_input_row_in_order():
    last = ["GARCIA", "CHEN", "SMITH", "OKAFOR", "RODRIGUEZ", "PATEL"]
    zc = ["60606", "10001", "98109", "78205", "33132", "30313", "02109"]
    rnd = random.Random(1)
    L = [rnd.choice(last) for _ in range(300)]
    Z = [rnd.choice(zc) for _ in range(300)]
    out = aq.bisg(L, zcta=Z)
    assert out.height == 300                                              # stock pyethnicity returns the distinct keys only
    assert out["last_name"].to_list() == L and out["zcta"].to_list() == Z  # in the caller's order
    raw = pe.bisg(sorted(set(zip(L, Z)))[0:0] or list(dict.fromkeys(zip(L, Z))) and [k[0] for k in dict.fromkeys(zip(L, Z))],
                  zcta=[k[1] for k in dict.fromkeys(zip(L, Z))])
    by_key = {(r["last_name"], r["zcta"]): r for r in raw.to_dicts()}
    for r in out.to_dicts():                                              # every row carries ITS key's pyethnicity values
        assert r == by_key[(r["last_name"], r["zcta"])]


def test_pandas_numpy_and_nan_inputs_work():
    import numpy as np
    import pandas as pd
    s = pd.Series(["GARCIA", "CHEN", None, "SMITH"])
    z = pd.Series(["11201", "94110", "10001", np.nan])
    out = aq.bisg(s, zcta=z)
    assert out.height == 4
    assert out["last_name"].to_list() == ["GARCIA", "CHEN", None, "SMITH"]
    assert aq.bifsg(np.array(["MARIA", "WEI"]), np.array(["GARCIA", "CHEN"]), zcta=np.array(["11201", "94110"])).height == 2


def test_ml_functions_accept_pandas_and_keep_order():
    import pandas as pd
    f = pd.Series(["MARIA", "WEI", "JAMES", "AISHA"]); l = pd.Series(["GARCIA", "CHEN", "SMITH", "OKAFOR"])
    out = aq.predict_race_fl(f, l)
    assert out["first_name"].to_list() == f.tolist() and out["last_name"].to_list() == l.tolist()
