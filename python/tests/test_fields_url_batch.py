import json

import httpx
import pytest

import aqethnicity as aq
from aqethnicity import _transport
from conftest import SENTINEL_KEY, ok_columns


# ---- unknown fields are refused client-side (closes the silent-ignore gap)
@pytest.mark.parametrize("bad,hint", [("mname", "middle_name"), ("fname", "first_name"), ("lname", "last_name"), ("zip", "zip5")])
def test_unknown_kwarg_refused_before_any_request(make_client, bad, hint):
    calls = []
    cl = make_client(lambda r: calls.append(r) or ok_columns(r))
    with pytest.raises(aq.BadRequest) as e:
        aq.strata(["A"], ["B"], client=cl, **{bad: ["C"]})
    assert hint in str(e.value) and bad in str(e.value) and e.value.code == "unknown_field"
    assert calls == []


def test_unknown_kwarg_refused_on_every_public_function():
    for fn in ("strata", "strataname", "stratabgt", "stratatract", "stratazcta", "geocode", "tier_coverage",
               "predict_sex_f", "bisg", "bifsg", "predict_race_fl", "predict_sex_ssa"):  # all 12 incl. hosted sex
        f = getattr(aq, fn)
        args = ["X"] if fn in ("geocode", "tier_coverage", "predict_sex_f", "bisg", "predict_sex_ssa") else ["X", "Y"]
        with pytest.raises(aq.BadRequest, match="unknown field 'mname'"):
            f(*args, mname="Z")


def test_middle_name_is_the_accepted_spelling(make_client):
    seen = {}
    def h(r):
        seen.update(json.loads(r.content)["records"]); return ok_columns(r)
    aq.strataname(["MARIA"], ["GARCIA"], middle_name=["L"], client=make_client(h))
    assert seen["middle_name"] == ["L"] and "mname" not in seen


def test_passthrough_cannot_shadow_a_field(make_client):
    cl = make_client(lambda r: ok_columns(r))
    with pytest.raises(aq.BadRequest, match="mname"):
        aq.strataname(["A"], ["B"], passthrough={"mname": ["C"]}, client=cl)
    aq.strataname(["A"], ["B"], passthrough={"loan_id": ["L-1"]}, client=cl)      # ordinary names are fine


# ---- the service address is a package default, overridable only by AEQUUM_BASE_URL
def test_default_base_url():
    assert _transport.DEFAULT_BASE_URL == "https://api.aequum.ai"
    assert aq.Client(api_key="k").base_url == "https://api.aequum.ai"


def test_env_override_only(monkeypatch):
    monkeypatch.setenv("AEQUUM_BASE_URL", "http://127.0.0.1:18088/")
    assert aq.Client(api_key="k").base_url == "http://127.0.0.1:18088"


def test_no_base_url_argument_anywhere():
    with pytest.raises(TypeError):
        aq.Client(api_key="k", base_url="https://elsewhere.example")
    with pytest.raises(TypeError):
        aq.configure(api_key="k", base_url="https://elsewhere.example")


# ---- P1 large-batch regression: 2,500 rows across 1028-row chunks stay aligned; a height mismatch is refused
def test_large_batch_stays_aligned(make_client):
    sizes = []
    def h(r):
        body = json.loads(r.content); n = len(body["records"]["last_name"]); sizes.append(n)
        return ok_columns(r, {"echo": body["records"]["last_name"]})
    n = 2500
    out = aq.strataname([f"F{i}" for i in range(n)], [f"L{i}" for i in range(n)], client=make_client(h))
    assert out.height == n and sizes == [1028, 1028, 444]
    assert out["echo"].to_list() == [f"L{i}" for i in range(n)]          # row-for-row, in order


def test_service_returning_wrong_height_is_refused(make_client):
    def h(r):                                    # the P1 failure shape: fewer rows back than sent
        return httpx.Response(200, json={"columns": {"p_white": [0.5] * 999}})
    with pytest.raises(aq.AequumError, match="misaligned"):
        aq.strataname(["A"] * 1000, ["B"] * 1000, client=make_client(h))


def test_forced_tier_shortfall_rows_are_restated_in_callers_numbers(make_client):
    def h(r):
        body = json.loads(r.content)
        if len(body["records"]["last_name"]) == 1028 and body["records"]["first_name"][0] == "A":
            return ok_columns(r)
        return httpx.Response(422, json={"error": {"code": "bad_request", "message": "lack the geography",
                              "details": {"shortfall_rows": [3], "tier": "bgt", "request_records": 472}}})
    first = ["A"] * 1028 + ["B"] * 472
    with pytest.raises(aq.BadRequest, match=r"rows \[1031\] of your input"):
        aq.strataname(first, ["L"] * 1500, client=make_client(h))
