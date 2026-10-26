import json
import logging

import httpx
import pytest

import aqethnicity as aq
from conftest import SENTINEL_KEY, ok_columns

REC = dict(first_name=["MARIA"], last_name=["GARCIA"])


def err(status, code, message="x", headers=None):
    return httpx.Response(status, json={"error": {"code": code, "message": message}}, headers=headers or {})


def test_missing_key_is_friendly_and_makes_no_request(make_client):
    calls = []
    cl = aq.Client(api_key=None, _transport=httpx.MockTransport(lambda r: calls.append(r) or ok_columns(r)))
    with pytest.raises(aq.AuthenticationError) as e:
        aq.strataname(**REC, client=cl)
    assert "set_api_key" in str(e.value) and "AEQUUM_API_KEY" in str(e.value) and "Email terry@aequum.ai" in str(e.value)
    assert calls == []


def test_401_friendly(make_client):
    cl = make_client(lambda r: err(401, "invalid_api_key"))
    with pytest.raises(aq.AuthenticationError, match=r"didn't accept your key \(HTTP 401\).*pasted in full"):
        aq.strataname(**REC, client=cl)


def test_429_quota_is_friendly_and_not_retried(make_client):
    n = []
    cl = make_client(lambda r: n.append(1) or err(429, "quota_exceeded"))
    with pytest.raises(aq.QuotaExceeded, match=r"today's free limit \(HTTP 429\).*resets tomorrow"):
        aq.strataname(**REC, client=cl)
    assert len(n) == 1


def test_429_rate_limited_retries_then_succeeds(make_client):
    state = {"n": 0}
    def h(r):
        state["n"] += 1
        return err(429, "rate_limited", headers={"retry-after": "1"}) if state["n"] < 3 else ok_columns(r)
    out = aq.strataname(**REC, client=make_client(h))
    assert out["p_white"].to_list() == [0.5] and state["n"] == 3


def test_422_friendly(make_client):
    cl = make_client(lambda r: err(422, "bad_request", "1 of 1 records lack the geography"))
    with pytest.raises(aq.BadRequest, match=r"couldn't read the input \(HTTP 422\)"):
        aq.strataname(**REC, client=cl)


def test_503_warmup_retries_then_succeeds(make_client, capsys):
    state = {"n": 0}
    def h(r):
        state["n"] += 1
        return err(503, "backend_unavailable") if state["n"] <= 4 else ok_columns(r)
    out = aq.strataname(**REC, client=make_client(h))
    assert state["n"] == 5 and out.height == 1
    assert "starting up" in capsys.readouterr().err


def test_503_gives_up_with_friendly_message(make_client):
    cl = make_client(lambda r: err(503, "backend_unavailable"), warmup_retries=3)
    with pytest.raises(aq.ServiceUnavailable, match=r"still starting up \(HTTP 503\)"):
        aq.strataname(**REC, client=cl)


def test_key_is_sent_but_never_leaks(make_client, caplog, capsys):
    seen = {}
    def h(r):
        seen["auth"] = r.headers.get("authorization")
        return ok_columns(r)
    cl = make_client(h)
    caplog.set_level(logging.DEBUG)
    for name in ("httpx", "httpcore", "aqethnicity"):
        logging.getLogger(name).setLevel(logging.DEBUG)
    aq.set_api_key(SENTINEL_KEY)
    aq.strataname(**REC, client=cl)
    assert seen["auth"] == "Bearer " + SENTINEL_KEY            # it IS used on the wire
    texts = [caplog.text, repr(cl), str(cl), repr(aq.default_client()), repr(cl._key), f"{cl._key}", f"{cl._key!s:>20}"]
    cap = capsys.readouterr(); texts += [cap.out, cap.err]
    assert not any(SENTINEL_KEY in t for t in texts)
    assert "set" in repr(cl) and "***" in repr(cl._key)


@pytest.mark.parametrize("status,code", [(401, "invalid_api_key"), (429, "quota_exceeded"), (422, "bad_request"), (503, "backend_unavailable"), (500, "internal")])
def test_errors_and_tracebacks_never_contain_the_key(make_client, status, code):
    import traceback
    cl = make_client(lambda r: err(status, code), warmup_retries=1, max_retries=1)
    with pytest.raises(aq.AequumError) as e:
        aq.strataname(**REC, client=cl)
    blob = str(e.value) + repr(e.value) + "".join(traceback.format_exception(e.value))
    assert SENTINEL_KEY not in blob


def test_network_failure_message_has_no_url_or_key(make_client):
    def h(r):
        raise httpx.ConnectError("boom " + SENTINEL_KEY)     # even a hostile message must not be echoed
    cl = make_client(h, max_retries=1)
    with pytest.raises(aq.ServiceUnavailable) as e:
        aq.strataname(**REC, client=cl)
    assert SENTINEL_KEY not in str(e.value) and "ConnectError" in str(e.value)


def test_set_api_key_rejects_empty():
    with pytest.raises(aq.AuthenticationError):
        aq.set_api_key("  ")
