"""The thirdtrail API client.

A typed front door, nothing more. Every computation stays server-side; this
parses timestamps, maps errors to exceptions, retries what is worth retrying,
and — the part that is not discoverable from the wire — only offers each
endpoint the parameters it actually reads.

That last point is load-bearing. The tide height endpoints ignore `elevation`
entirely, so it is absent from those method signatures: passing it is a
TypeError before a request is made, rather than a silently discarded value and
an answer the caller believes was elevation-corrected.
"""
from __future__ import annotations

import datetime as dt
import time
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from typing_extensions import Self
from urllib.parse import urljoin

import requests

from . import errors
from .models import Day, SolarSample, TideExtreme, parse_days

__all__ = ["Client"]

DEFAULT_BASE_URL = "https://thirdtrail.life"
DEFAULT_TIMEOUT = 30.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


def _date(value: dt.date | str | None) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, dt.date) else str(value)


def _instant(value: dt.datetime | str | None) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, dt.datetime) else str(value)


class Client:
    """Talks to the thirdtrail API.

        from thirdtrail import Client

        tt = Client(api_key="tt_live_…")
        for day in tt.ephemerides(lat=53.3498, lon=-6.2603, elevation=20):
            print(day.date, day.sun.rise)

    An API key belongs to one subscription, and therefore one product. A key
    for Tides cannot call the solar endpoints — that is a 403, surfaced as
    ``PermissionDenied``, not a client-side check, because only the server
    knows what a key is for.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        session: requests.Session | None = None,
    ) -> None:
        if not api_key or not isinstance(api_key, str):
            raise ValueError("api_key is required")
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = session or requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": f"thirdtrail-python/{_version()}",
        })

    # -- transport ---------------------------------------------------------
    def _get(self, path: str, params: Mapping[str, Any]) -> dict[str, Any]:
        clean = {k: _wire(v) for k, v in params.items() if v is not None}
        url = urljoin(self.base_url, path.lstrip("/"))

        last: errors.ThirdtrailError | None = None
        for attempt in range(self.max_retries + 1):
            try:
                r = self._session.get(url, params=clean, timeout=self.timeout)
            except requests.RequestException as exc:
                last = errors.ThirdtrailError(f"request failed: {exc}")
                if attempt == self.max_retries:
                    raise last from exc
                time.sleep(_backoff(attempt))
                continue

            if r.status_code < 400:
                body = r.json()
                return body if isinstance(body, dict) else {"data": body}

            payload = _json_or_empty(r)
            err = errors.from_response(r.status_code, payload, r.text)
            if isinstance(err, errors.RateLimited):
                err.retry_after = _retry_after(r)

            # A plan ceiling or a bad coordinate will fail identically on
            # retry; only transient statuses are worth another call.
            if r.status_code not in RETRY_STATUSES or attempt == self.max_retries:
                raise err
            time.sleep(_retry_after(r) or _backoff(attempt))
            last = err

        raise last or errors.ThirdtrailError("request failed")

    # -- ephemerides -------------------------------------------------------
    def ephemerides(
        self, *, lat: float, lon: float,
        elevation: float | None = None, auto_elevation: bool | None = None,
        days: int | None = None, start_date: dt.date | str | None = None,
        tz: str | None = None, utc_offset: str | None = None,
        lang: str | None = None,
    ) -> list[Day]:
        """Sun and moon rise, set, transit, twilight and phase.

        Pass ``elevation`` whenever you know it. A sea-level sunrise is simply
        wrong at altitude — about three minutes out at 200 m — and this is the
        difference the API exists for.
        """
        return parse_days(self._get("/v1/ephemerides/", {
            "lat": lat, "lon": lon, "elevation": elevation,
            "auto_elevation": auto_elevation, "days": days,
            "start_date": _date(start_date), "tz": tz,
            "utc_offset": utc_offset, "lang": lang,
        }))

    def prayer_times(
        self, *, lat: float, lon: float,
        elevation: float | None = None, auto_elevation: bool | None = None,
        days: int | None = None, start_date: dt.date | str | None = None,
        school: str | None = None, asr_method: Literal["standard", "hanafi"] | None = None,
        tz: str | None = None, utc_offset: str | None = None, lang: str | None = None,
    ) -> dict[str, Any]:
        """The five daily prayer times, elevation-corrected.

        ``school`` is one of mwl, isna, egypt, makkah, karachi.
        """
        return self._get("/v1/ephemerides/prayer-times/", {
            "lat": lat, "lon": lon, "elevation": elevation,
            "auto_elevation": auto_elevation, "days": days,
            "start_date": _date(start_date), "school": school,
            "asr_method": asr_method, "tz": tz, "utc_offset": utc_offset,
            "lang": lang,
        })

    # -- solar -------------------------------------------------------------
    def solar(
        self, *, lat: float, lon: float,
        timestamp: dt.datetime | str | None = None,
        elevation: float | None = None, auto_elevation: bool | None = None,
        include: str | None = None, tz: str | None = None,
    ) -> dict[str, Any]:
        """Solar position and clear-sky irradiance at an instant."""
        return self._get("/v1/solar/", {
            "lat": lat, "lon": lon, "timestamp": _instant(timestamp),
            "elevation": elevation, "auto_elevation": auto_elevation,
            "include": include, "tz": tz,
        })

    def solar_range(
        self, *, lat: float, lon: float,
        from_date: dt.date | str, to_date: dt.date | str,
        elevation: float | None = None, auto_elevation: bool | None = None,
        include: str | None = None, tz: str | None = None,
    ) -> dict[str, Any]:
        """Solar values across a date range."""
        return self._get("/v1/solar/range/", {
            "lat": lat, "lon": lon, "from": _date(from_date), "to": _date(to_date),
            "elevation": elevation, "auto_elevation": auto_elevation,
            "include": include, "tz": tz,
        })

    def solar_path(
        self, *, lat: float, lon: float,
        start_date: dt.date | str | None = None, interval: str | None = None,
        elevation: float | None = None, auto_elevation: bool | None = None,
        tz: str | None = None,
    ) -> list[SolarSample]:
        """The sun's track across one day, sampled at ``interval`` (e.g. "5m")."""
        raw = self._get("/v1/solar/path/", {
            "lat": lat, "lon": lon, "start_date": _date(start_date),
            "interval": interval, "elevation": elevation,
            "auto_elevation": auto_elevation, "tz": tz,
        })
        return [SolarSample.from_api(s) for s in raw.get("path", raw.get("samples", []))]

    def solar_dli(
        self, *, lat: float, lon: float,
        from_date: dt.date | str, to_date: dt.date | str,
        elevation: float | None = None, auto_elevation: bool | None = None,
        tz: str | None = None,
    ) -> dict[str, Any]:
        """Daily Light Integral — integrated PAR per day, for growing."""
        return self._get("/v1/solar/dli/", {
            "lat": lat, "lon": lon, "from": _date(from_date), "to": _date(to_date),
            "elevation": elevation, "auto_elevation": auto_elevation, "tz": tz,
        })

    # -- tides -------------------------------------------------------------
    # No `elevation` on the height endpoints: the API does not read it there.
    # How high the observer stands does not change the ocean surface, and
    # offering the parameter would invite a caller to believe otherwise.
    def tide_heights(
        self, *, lat: float, lon: float,
        days: int | None = None, start_date: dt.date | str | None = None,
        step: str | None = None, tz: str | None = None,
    ) -> dict[str, Any]:
        """Water-height time series. Metres relative to MEAN SEA LEVEL, not
        chart datum — not for navigation."""
        return self._get("/v1/tides/heights/", {
            "lat": lat, "lon": lon, "days": days,
            "start_date": _date(start_date), "step": step, "tz": tz,
        })

    def tide_extremes(
        self, *, lat: float, lon: float,
        days: int | None = None, start_date: dt.date | str | None = None,
        tz: str | None = None,
    ) -> list[TideExtreme]:
        """High and low waters. Relative to mean sea level, not chart datum."""
        raw = self._get("/v1/tides/extremes/", {
            "lat": lat, "lon": lon, "days": days,
            "start_date": _date(start_date), "tz": tz,
        })
        return [TideExtreme.from_api(e) for e in raw.get("extremes", [])]

    def tide_constituents(self, *, lat: float, lon: float) -> dict[str, Any]:
        """Harmonic constants at a point. Pro and above."""
        return self._get("/v1/tides/constituents/", {"lat": lat, "lon": lon})

    def tide_window(
        self, *, lat: float, lon: float,
        days: int | None = None, start_date: dt.date | str | None = None,
        elevation: float | None = None, auto_elevation: bool | None = None,
        tz: str | None = None,
    ) -> list[Day]:
        """Tides together with sun and moon, per day. Starter and above.

        The one tide endpoint that takes ``elevation``, because half its
        response comes from the ephemerides engine. It shifts the sun and moon
        times — roughly three minutes at clifftop height — and never the tide
        heights.
        """
        return parse_days(self._get("/v1/tides/window/", {
            "lat": lat, "lon": lon, "days": days,
            "start_date": _date(start_date), "elevation": elevation,
            "auto_elevation": auto_elevation, "tz": tz,
        }))

    # -- misc --------------------------------------------------------------
    def echo(self, **params: Any) -> dict[str, Any]:
        """Verify a key and connectivity without spending a computation."""
        return self._get("/v1/echo/", params)

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# -- helpers ---------------------------------------------------------------
def _wire(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _backoff(attempt: int) -> float:
    return min(2.0 ** attempt, 8.0)


def _retry_after(response: requests.Response) -> float | None:
    raw = response.headers.get("Retry-After")
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def _json_or_empty(response: requests.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _version() -> str:
    from . import __version__
    return __version__
