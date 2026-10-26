"""Runs only when AQ_LIVE=1 and AEQUUM_API_KEY (+ AEQUUM_BASE_URL for a scratch instance) are set.
Never run in CI; uses made-up people at public landmark addresses."""
import os

import pytest

import aqethnicity as aq

pytestmark = pytest.mark.skipif(os.environ.get("AQ_LIVE") != "1", reason="set AQ_LIVE=1 to run against a real service")

PLACES = [("233 S Wacker Dr", "Chicago", "IL", "60606"), ("20 W 34th St", "New York", "NY", "10001"),
          ("400 Broad St", "Seattle", "WA", "98109"), ("300 Alamo Plaza", "San Antonio", "TX", "78205")]


def test_strata_over_the_chunk_boundary_keeps_row_alignment():
    n = 1500                                    # > one 1028-row chunk: the P1 class of bug lived here
    first = [f"MARIA" if i % 2 else "JAMES" for i in range(n)]
    last = ["GARCIA" if i % 3 else "SMITH" for i in range(n)]
    pl = [PLACES[i % 4] for i in range(n)]
    out = aq.strata(first, last, address=[p[0] for p in pl], city=[p[1] for p in pl],
                    state=[p[2] for p in pl], zip5=[p[3] for p in pl],
                    passthrough={"row": [str(i) for i in range(n)]})
    assert out.height == n and out["row"].to_list() == [str(i) for i in range(n)]
    s = out.select(["p_white", "p_black", "p_hispanic", "p_asian", "p_other"]).sum_horizontal()
    assert ((s - 1).abs() < 1e-3).all()


def test_middle_name_is_used():
    a = aq.strataname(["MARIA"], ["GARCIA"], middle_name=["JOSE"])
    assert a["mname"].to_list() == ["JOSE"]


def test_bad_key_is_a_friendly_401():
    cl = aq.Client(api_key="aq_test_not_a_real_key_0000000000000000")
    with pytest.raises(aq.AuthenticationError, match="HTTP 401"):
        aq.strataname(["MARIA"], ["GARCIA"], client=cl)
