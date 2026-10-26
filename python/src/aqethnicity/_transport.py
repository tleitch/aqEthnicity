"""HTTP transport: batching, retries, error mapping.

The service address is a package default; the only override is the ``AEQUUM_BASE_URL``
environment variable, meant for testing. The API key comes from :func:`set_api_key` or
``AEQUUM_API_KEY`` and is never logged, printed or stored in a header object between calls.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any

import httpx

from ._errors import (
    KEY_HELP,
    AequumError,
    AuthenticationError,
    ServiceUnavailable,
    from_response,
)
from ._secret import Secret

DEFAULT_BASE_URL = "https://api.aequum.ai"
DEFAULT_CHUNKSIZE = 1028  # pyethnicity's default, kept for parity
_RETRY_STATUS = {429, 500, 502, 504}  # 503 has its own, longer, warm-up wait
log = logging.getLogger("aqethnicity")
_sleep = time.sleep  # tests replace this so retries are instant


def _resolve_base_url() -> str:
    return (os.environ.get("AEQUUM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


class Client:
    """Thin HTTP client for the hosted STRATA and geocoding service."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 300.0,
        max_retries: int = 3,
        chunksize: int = DEFAULT_CHUNKSIZE,
        warmup_retries: int = 12,
        warmup_wait: float = 30.0,
        _transport: httpx.BaseTransport | None = None,
    ):
        key = api_key or os.environ.get("AEQUUM_API_KEY")
        self._key: Secret | None = Secret(key.strip()) if key and key.strip() else None
        self.base_url = _resolve_base_url()
        self.timeout = timeout
        self.max_retries = max_retries
        self.chunksize = chunksize
        self.warmup_retries = warmup_retries
        self.warmup_wait = warmup_wait
        self._mock_transport = _transport
        self._http: httpx.Client | None = None

    def __repr__(self) -> str:
        return f"Client(base_url={self.base_url!r}, api_key={'set' if self._key else 'not set'})"

    @property
    def has_key(self) -> bool:
        return self._key is not None

    # -- lifecycle ---------------------------------------------------------
    @property
    def http(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(
                base_url=self.base_url,
                headers={"user-agent": _user_agent()},   # the key is added per request, never stored here
                timeout=self.timeout,
                transport=self._mock_transport,
            )
        return self._http

    def close(self) -> None:
        if self._http is not None:
            self._http.close()
            self._http = None

    def __enter__(self) -> Client:  # noqa: PYI034
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- calls -------------------------------------------------------------
    def health(self) -> dict[str, Any]:
        return self._request("GET", "/v1/health", needs_key=False)

    def predict(
        self,
        path: str,
        columns: dict[str, list[Any]],
        options: dict[str, Any] | None = None,
        *,
        chunksize: int | None = None,
    ) -> dict[str, list[Any]]:
        """POST records to ``path`` in chunks and stitch the answers back in input order."""
        n = len(next(iter(columns.values())))
        size = chunksize or self.chunksize
        out: dict[str, list[Any]] = {}
        for start in range(0, n, size):
            stop = min(start + size, n)
            body = {"records": {k: v[start:stop] for k, v in columns.items()},
                    "options": options or {}}
            try:
                payload = self._request("POST", path, json=body)
            except AequumError as exc:
                raise _rewrite_row_indices(exc, start, n) from None
            got = payload.get("columns") or {}
            # Height guard (the P1 class of bug): an answer with a different number of rows than
            # the chunk would silently misalign every later row, so refuse it.
            heights = {len(v) for v in got.values()}
            if got and heights != {stop - start}:
                raise AequumError(
                    f"the service returned {sorted(heights)} rows for {stop - start} submitted "
                    "records; refusing to return misaligned results. Retry with a smaller "
                    "chunksize (for example chunksize=250) and report this if it persists.",
                    code="response_height_mismatch")
            for key, values in got.items():
                out.setdefault(key, []).extend(values)
        return out

    # -- internals ---------------------------------------------------------
    def _headers(self, needs_key: bool) -> dict[str, str]:
        if not needs_key:
            return {}
        if self._key is None:
            raise AuthenticationError(
                "no API key is set. Call aqethnicity.set_api_key(...) or set the AEQUUM_API_KEY "
                "environment variable. " + KEY_HELP, code="missing_api_key")
        return {"authorization": "Bearer " + self._key.reveal()}

    def _request(self, method: str, path: str, *, needs_key: bool = True, **kw: Any) -> dict[str, Any]:
        headers = self._headers(needs_key)            # raises before any network call when no key
        last_exc: Exception | None = None
        attempt = warm = 0
        while True:
            try:
                resp = self.http.request(method, path, headers=headers, **kw)
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    _sleep(_backoff(attempt)); attempt += 1; continue
                raise ServiceUnavailable(
                    f"could not reach the service: {type(exc).__name__}. Check your network "
                    "connection and try again.", code="backend_unavailable") from None
            request_id = resp.headers.get("x-request-id")
            if resp.status_code < 300:
                return resp.json()
            if resp.status_code == 503 and warm < self.warmup_retries:
                if warm == 0:
                    print("aqethnicity: the service is starting up (HTTP 503); waiting and "
                          "retrying (this can take a few minutes after a restart)...",
                          file=sys.stderr)
                warm += 1; _sleep(self.warmup_wait); continue
            if resp.status_code in _RETRY_STATUS and attempt < self.max_retries \
                    and not _is_quota(resp):
                _sleep(_retry_after(resp) or _backoff(attempt)); attempt += 1; continue
            raise from_response(resp.status_code, _error_payload(resp), request_id)


def _is_quota(resp: httpx.Response) -> bool:
    """A 429 that is the daily limit (not a transient rate limit) must not be retried."""
    if resp.status_code != 429:
        return False
    try:
        code = (resp.json().get("error") or {}).get("code")
    except ValueError:
        return False
    return code != "rate_limited"


def _error_payload(resp: httpx.Response) -> dict:
    try:
        return resp.json()
    except ValueError:
        body = resp.text or ""
        head = body[:400].lower()
        if "<html" in head or "<!doctype" in head:
            if resp.status_code in (502, 503, 504):
                msg = (f"the gateway returned {resp.status_code} before the API responded. The "
                       "request was most likely too large for a single round trip; retry with a "
                       "smaller chunksize (for example chunksize=250).")
            else:
                msg = f"HTTP {resp.status_code} from the gateway rather than the API."
            return {"error": {"code": "backend_unavailable", "message": msg}}
        return {"error": {"message": body[:500] or f"HTTP {resp.status_code}"}}


def _rewrite_row_indices(exc: AequumError, offset: int, total: int) -> AequumError:
    """Restate a chunk-relative error in the caller's own row numbers."""
    rows = exc.details.get("shortfall_rows")
    if not rows or offset is None:
        return exc
    shifted = [r + offset for r in rows]
    tier = exc.details.get("tier", "requested")
    shown = shifted[:10]
    more = "..." if len(shifted) > 10 else ""
    chunk_note = (
        "" if offset == 0 and exc.details.get("request_records", total) >= total
        else " Rows beyond this point were not checked, because the call stops at the first "
             "chunk containing a shortfall."
    )
    message = (
        f"the API couldn't read the input (HTTP 422): {len(shifted)} of {total} submitted records "
        f"lack the geography for the {tier} tier (rows {shown}{more} of your input).{chunk_note} "
        "Use strata() for the waterfall, or tier_coverage() to measure reachability across the "
        "whole input without an exception."
    )
    return type(exc)(message, code=exc.code, request_id=exc.request_id,
                     details={**exc.details, "shortfall_rows": shifted,
                              "submitted_records": total, "chunk_offset": offset})


def _backoff(attempt: int) -> float:
    return min(2.0**attempt * 0.25, 4.0)


def _retry_after(resp: httpx.Response) -> float | None:
    raw = resp.headers.get("retry-after")
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def _user_agent() -> str:
    from . import __version__
    return f"aqethnicity-python/{__version__}"


_default: Client | None = None


def default_client() -> Client:
    """Process-wide client, built from AEQUUM_API_KEY (and AEQUUM_BASE_URL for testing)."""
    global _default
    if _default is None:
        _default = Client()
    return _default


def set_api_key(key: str) -> None:
    """Set the API key for this process. Nothing is printed or logged."""
    global _default
    if not isinstance(key, str) or not key.strip():
        raise AuthenticationError("set_api_key needs a non-empty key string. " + KEY_HELP,
                                  code="missing_api_key")
    if _default is not None:
        _default.close()
    _default = Client(api_key=key)


def configure(api_key: str | None = None, **kw: Any) -> Client:
    """Replace the process-wide client (advanced: timeouts, retries, chunksize)."""
    global _default
    if _default is not None:
        _default.close()
    _default = Client(api_key=api_key, **kw)
    return _default
