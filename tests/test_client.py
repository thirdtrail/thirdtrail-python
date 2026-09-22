"""Client behaviour, against mocked HTTP.

No network: these assert the translation layer, which is the only thing the
library is responsible for. Whether sunrise is correct is the API's problem
and is tested there.
"""
from __future__ import annotations

import datetime as dt

import pytest
import responses

from thirdtrail import (
    AuthenticationError,
    Client,
    DataUnavailable,
    PermissionDenied,
    PlanLimitExceeded,
    RateLimited,
)

BASE = "https://thirdtrail.life"
KEY = "tt_live_test"

EPHEM_BODY = {
    "notice": {"text": "Informational only."},
    "request": {"lat": 53.3498, "lon": -6.2603, "elevation_m": 20},
    "resolved": {"elevation_m": 20.0, "elevation_source": "user",
                 "timezone": "Europe/Dublin", "plan": "pro"},
    "days": [{
        "date": "2026-09-21",
        "sun": {"rise": "2026-09-21T07:09:48+01:00",
                "set": "2026-09-21T19:25:21+01:00",
                "transit": "2026-09-21T13:18:06+01:00",
                "golden_hour": {"morning_start": "2026-09-21T07:09:48+01:00",
                                "morning_end": "2026-09-21T07:49:00+01:00"}},
        "moon": {"rise": "2026-09-21T17:51:51+01:00",
                 "set": "2026-09-21T00:21:32+01:00",
                 "phase": {"name": "Waxing Gibbous", "illumination": 0.7376}},
    }],
}


@pytest.fixture
def client():
    return Client(api_key=KEY, max_retries=0)


# -- parsing ---------------------------------------------------------------
@responses.activate
def test_timestamps_become_aware_datetimes(client):
    """The main thing callers are buying: no fromisoformat loop, offset kept."""
    responses.get(f"{BASE}/v1/ephemerides/", json=EPHEM_BODY)
    day = client.ephemerides(lat=53.3498, lon=-6.2603, elevation=20)[0]

    assert day.date == dt.date(2026, 9, 21)
    assert isinstance(day.sun.rise, dt.datetime)
    assert day.sun.rise.utcoffset() == dt.timedelta(hours=1), "offset was dropped"
    assert day.moon.phase.name == "Waxing Gibbous"
    assert day.sun.golden_hour.morning.start == day.sun.rise


@responses.activate
def test_the_raw_payload_stays_reachable(client):
    """A field the client does not model must not be a blocker."""
    responses.get(f"{BASE}/v1/ephemerides/", json=EPHEM_BODY)
    day = client.ephemerides(lat=1, lon=1)[0]
    assert day.response["resolved"]["elevation_source"] == "user"
    assert day.raw["sun"]["rise"].startswith("2026-09-21")


# -- request shaping -------------------------------------------------------
@responses.activate
def test_booleans_are_sent_the_way_the_api_parses_them(client):
    responses.get(f"{BASE}/v1/tides/window/", json={"days": []})
    client.tide_window(lat=1, lon=2, auto_elevation=True)
    assert "auto_elevation=true" in responses.calls[0].request.url


@responses.activate
def test_dates_accept_objects_or_strings(client):
    responses.get(f"{BASE}/v1/ephemerides/", json={"days": []})
    client.ephemerides(lat=1, lon=2, start_date=dt.date(2026, 6, 21))
    assert "start_date=2026-06-21" in responses.calls[0].request.url


@responses.activate
def test_unset_parameters_are_omitted_entirely(client):
    """Sending elevation= empty would be a different request from not sending it."""
    responses.get(f"{BASE}/v1/ephemerides/", json={"days": []})
    client.ephemerides(lat=1, lon=2)
    assert "elevation" not in responses.calls[0].request.url


@responses.activate
def test_the_key_is_sent_as_a_bearer_token(client):
    responses.get(f"{BASE}/v1/echo/", json={})
    client.echo()
    assert responses.calls[0].request.headers["Authorization"] == f"Bearer {KEY}"


# -- the contract the wire cannot express ----------------------------------
def test_height_endpoints_do_not_accept_elevation(client):
    """The API ignores elevation there, so the method must not offer it —
    a TypeError before any request, rather than a discarded value and an
    answer the caller believes was corrected."""
    with pytest.raises(TypeError):
        client.tide_extremes(lat=1, lon=2, elevation=214)   # type: ignore[call-arg]
    with pytest.raises(TypeError):
        client.tide_heights(lat=1, lon=2, elevation=214)    # type: ignore[call-arg]


def test_the_window_endpoint_does_accept_elevation(client):
    """Half its response is ephemerides output, which IS elevation-corrected."""
    import inspect
    assert "elevation" in inspect.signature(client.tide_window).parameters


# -- errors ----------------------------------------------------------------
@responses.activate
def test_a_plan_ceiling_carries_the_limit(client):
    responses.get(f"{BASE}/v1/tides/extremes/", status=400,
                  json={"detail": "days=9999 exceeds your plan's limit of 31."})
    with pytest.raises(PlanLimitExceeded) as e:
        client.tide_extremes(lat=1, lon=2, days=9999)
    assert e.value.limit == 31, "callers should clamp without parsing prose"


@responses.activate
@pytest.mark.parametrize("status,exc", [
    (401, AuthenticationError),
    (403, PermissionDenied),
    (429, RateLimited),
    (503, DataUnavailable),
])
def test_statuses_map_to_types(client, status, exc):
    responses.get(f"{BASE}/v1/echo/", status=status, json={"detail": "nope"})
    with pytest.raises(exc):
        client.echo()


@responses.activate
def test_a_non_json_error_body_still_raises_cleanly(client):
    responses.get(f"{BASE}/v1/echo/", status=502, body="<html>gateway</html>")
    with pytest.raises(Exception) as e:
        client.echo()
    assert e.value.status == 502


# -- retries ---------------------------------------------------------------
@responses.activate
def test_transient_failures_are_retried():
    responses.get(f"{BASE}/v1/echo/", status=503, json={"detail": "warming up"})
    responses.get(f"{BASE}/v1/echo/", json={"ok": True})
    c = Client(api_key=KEY, max_retries=2)
    assert c.echo() == {"ok": True}
    assert len(responses.calls) == 2


@responses.activate
def test_a_plan_ceiling_is_not_retried():
    """It will fail identically every time; retrying just burns quota."""
    responses.get(f"{BASE}/v1/tides/extremes/", status=400,
                  json={"detail": "exceeds your plan's limit of 31."})
    c = Client(api_key=KEY, max_retries=3)
    with pytest.raises(PlanLimitExceeded):
        c.tide_extremes(lat=1, lon=2, days=99)
    assert len(responses.calls) == 1


# -- construction ----------------------------------------------------------
def test_an_empty_key_is_refused_immediately():
    with pytest.raises(ValueError):
        Client(api_key="")


@responses.activate
def test_the_base_url_can_be_overridden():
    responses.get("https://staging.example/v1/echo/", json={})
    Client(api_key=KEY, base_url="https://staging.example").echo()
    assert responses.calls[0].request.url.startswith("https://staging.example")
