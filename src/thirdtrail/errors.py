"""Exceptions, so callers catch a type instead of matching on message text.

The API returns its refusals as ``{"detail": "…"}`` with a status code. Without
these, handling a plan ceiling means string-matching "exceeds your plan's limit
of 31" — which quietly makes the wording of every error message part of the
public contract, and means the server can never reword one.

Mapping to types costs a little parsing here and buys the server back its
freedom to rewrite prose.
"""
from __future__ import annotations

import re
from typing import Any


class ThirdtrailError(Exception):
    """Base class. Catch this to catch anything the client raises."""

    def __init__(self, message: str, *, status: int | None = None,
                 response: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.response = response or {}


class AuthenticationError(ThirdtrailError):
    """401 — the key is missing, malformed, revoked or unknown."""


class PermissionDenied(ThirdtrailError):
    """403 — the key is valid but the plan does not include this.

    Raised for tier-gated endpoints (constituents is Pro+, the coastal window
    is Starter+) and for options a plan does not allow, such as a finer tide
    `step` than the tier permits.
    """


class PlanLimitExceeded(ThirdtrailError):
    """400 where the request exceeded a documented plan ceiling.

    ``limit`` carries the number the server named, so a caller can clamp and
    retry rather than parse the sentence:

        try:
            tt.tide_extremes(lat=51.5, lon=-2.7, days=90)
        except PlanLimitExceeded as e:
            tt.tide_extremes(lat=51.5, lon=-2.7, days=e.limit)
    """

    def __init__(self, message: str, **kw: Any) -> None:
        super().__init__(message, **kw)
        m = re.search(r"limit of (\d+)", message)
        self.limit: int | None = int(m.group(1)) if m else None


class InvalidRequest(ThirdtrailError):
    """400 for anything else — a bad coordinate, an unparseable date."""


class RateLimited(ThirdtrailError):
    """429 — too many calls. ``retry_after`` is seconds, when the server says."""

    def __init__(self, message: str, *, retry_after: float | None = None, **kw: Any) -> None:
        super().__init__(message, **kw)
        self.retry_after = retry_after


class DataUnavailable(ThirdtrailError):
    """503 — a dataset is not loaded on the server (e.g. the tide atlas).

    Transient and not the caller's fault. Worth retrying later rather than
    treating as a bad request.
    """


class ServerError(ThirdtrailError):
    """5xx other than 503."""


def from_response(status: int, payload: dict[str, Any], text: str) -> ThirdtrailError:
    """Pick the exception for a failed response."""
    detail = payload.get("detail") or text.strip() or f"HTTP {status}"

    if status == 401:
        return AuthenticationError(detail, status=status, response=payload)
    if status == 403:
        return PermissionDenied(detail, status=status, response=payload)
    if status == 429:
        return RateLimited(detail, status=status, response=payload)
    if status == 503:
        return DataUnavailable(detail, status=status, response=payload)
    if status == 400:
        if "exceeds your plan" in detail or "limit of" in detail:
            return PlanLimitExceeded(detail, status=status, response=payload)
        return InvalidRequest(detail, status=status, response=payload)
    if status >= 500:
        return ServerError(detail, status=status, response=payload)
    return ThirdtrailError(detail, status=status, response=payload)
