"""Typed exceptions.

Every error the service returns carries a machine-readable ``code``; the client maps
it to one of these so callers can branch on billing/quota conditions without parsing
prose. Unknown codes fall back to :class:`AequumError`.
"""

from __future__ import annotations


class AequumError(Exception):
    """Base class for all aequum errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        request_id: str | None = None,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.request_id = request_id
        # Structured facts from the service. For a forced-tier shortfall this carries
        # shortfall_rows and request_records, which the transport rewrites into the
        # caller's row numbers before anyone sees the message.
        self.details = details or {}

    def _render_traceback_(self):  # IPython/Jupyter: show the plain message, not a traceback
        return ["", "aqEthnicity: " + str(self), ""]

    def __str__(self) -> str:  # pragma: no cover - trivial
        base = super().__str__()
        if self.request_id:
            return f"{base} (request_id={self.request_id})"
        return base


class BadRequest(AequumError):
    """Input was rejected: mismatched lengths, unknown geo_type, missing geography."""


class AuthenticationError(AequumError):
    """Missing or invalid API key."""


class PlanRequired(AequumError):
    """The key is valid but the plan does not include this function or option."""


class RateLimited(AequumError):
    """Too many requests per second. ``retry_after`` is seconds, when the server says."""

    def __init__(self, message: str, *, retry_after: float | None = None, **kw):
        super().__init__(message, **kw)
        self.retry_after = retry_after


class QuotaExceeded(AequumError):
    """Monthly record quota is used up."""


class ServiceUnavailable(AequumError):
    """Upstream model backend is down or still loading."""


class NotImplementedYet(AequumError):
    """A documented capability that this deployment does not serve yet."""


_CODE_MAP: dict[str, type[AequumError]] = {
    "bad_request": BadRequest,
    "missing_required_field": BadRequest,
    "invalid_api_key": AuthenticationError,
    "missing_api_key": AuthenticationError,
    "plan_required": PlanRequired,
    "rate_limited": RateLimited,
    "quota_exceeded": QuotaExceeded,
    "backend_unavailable": ServiceUnavailable,
    "not_implemented": NotImplementedYet,
}


KEY_HELP = "No key yet? Email terry@aequum.ai for a free one."


class MissingDependency(AequumError, ImportError):
    """An optional extra is not installed (for example the ``local`` extra)."""


def friendly_message(status: int, code: str | None, server_message: str) -> str:
    """The plain-language text for the conditions a user can act on."""
    if status == 401 or code in ("invalid_api_key", "missing_api_key"):
        return ("the API didn't accept your key (HTTP 401). Check it was pasted in full, with no "
                "extra spaces. " + KEY_HELP)
    if status == 429:
        if code == "rate_limited":
            return ("too many requests too quickly (HTTP 429). Slow down and try again in a moment.")
        return ("you've reached today's free limit (HTTP 429). It resets tomorrow; email "
                "terry@aequum.ai if you need more.")
    if status == 422:
        return f"the API couldn't read the input (HTTP 422): {server_message[:300]}"
    if status == 503:
        return ("the service is still starting up (HTTP 503). After a restart the address routes "
                "can take about five minutes to load; try again shortly.")
    return server_message


def from_response(status: int, payload: dict, request_id: str | None = None) -> AequumError:
    """Build the right exception from an error response body."""
    err = payload.get("error", payload) if isinstance(payload, dict) else {}
    code = err.get("code") if isinstance(err, dict) else None
    message = (err.get("message") if isinstance(err, dict) else None) or f"HTTP {status}"
    message = friendly_message(status, code, message)
    details = err.get("details") if isinstance(err, dict) else None
    cls = _CODE_MAP.get(code or "", AequumError)
    if status == 401 and cls is AequumError:
        cls = AuthenticationError
    if status == 429 and cls is AequumError:
        cls = QuotaExceeded
    if cls is RateLimited:
        return RateLimited(
            message, code=code, request_id=request_id, retry_after=err.get("retry_after") if isinstance(err, dict) else None,
            details=details,
        )
    return cls(message, code=code, request_id=request_id, details=details)
