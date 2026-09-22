# thirdtrail

Python client for the [thirdtrail](https://thirdtrail.life) APIs — sun, moon,
twilight, solar irradiance and tides for any point on Earth, **with elevation
as a first-class input**.

```bash
pip install thirdtrail
```

```python
from thirdtrail import Client

tt = Client(api_key="tt_live_…")

for day in tt.ephemerides(lat=53.3498, lon=-6.2603, elevation=20):
    print(day.date, day.sun.rise, day.sun.set)
```

## Why elevation

Most sunrise APIs answer for an observer standing at sea level. The higher you
are, the further you see, and the earlier the sun clears the horizon.

At the Cliffs of Moher (214 m) the difference is about **three minutes** — on
sunrise, sunset, and every golden- and blue-hour boundary with them:

| | sea level | at 214 m |
|---|---|---|
| sunrise | 07:23:33 | **07:20:25** |
| golden hour, morning start | 06:56:51 | **06:53:42** |
| moonrise | 18:03:48 | **17:59:40** |

Golden hour lasts 20–40 minutes, so three minutes is a real slice of it. Pass
`elevation` whenever you know it.

## What you get

```python
day.sun.rise                        # datetime, with its timezone offset intact
day.sun.golden_hour.morning.start
day.moon.phase.name                 # "Waxing Gibbous"
day.moon.phase.illumination         # 0.7376
```

Timestamps arrive as aware `datetime` objects, not strings. Anything the
client does not model is still there on `day.raw` and `day.response`, so a new
server-side field never has to wait for a client release.

## Endpoints

```python
tt.ephemerides(lat=…, lon=…, elevation=…, days=7)     # sun + moon + twilight
tt.prayer_times(lat=…, lon=…, school="mwl")           # five daily prayers
tt.solar(lat=…, lon=…, timestamp=…)                   # position + irradiance
tt.solar_path(lat=…, lon=…, interval="5m")            # the sun's arc, sampled
tt.solar_dli(lat=…, lon=…, from_date=…, to_date=…)    # Daily Light Integral
tt.tide_heights(lat=…, lon=…, step="10m")             # water height series
tt.tide_extremes(lat=…, lon=…)                        # high and low waters
tt.tide_window(lat=…, lon=…, elevation=…)             # tides + sun + moon
tt.tide_constituents(lat=…, lon=…)                    # harmonic constants
```

### Tides take no elevation — except one

`tide_heights` and `tide_extremes` have no `elevation` parameter, and that is
deliberate: how high *you* stand does not change the ocean surface. Passing it
raises `TypeError` rather than being silently ignored.

`tide_window` is the exception, because half of what it returns is sun and
moon data:

```python
for day in tt.tide_window(lat=52.9715, lon=-9.4309, elevation=214, days=3):
    print(day.date, day.sun.golden_hour.morning.start)
    for t in day.low_waters:
        print("  low water", t.time, t.height_m)
```

Tide heights are metres relative to **mean sea level, not chart datum**, and
exclude weather-driven surge. Not for navigation.

## Errors

Catch a type, not a sentence:

```python
from thirdtrail import PlanLimitExceeded

try:
    tt.tide_extremes(lat=51.5, lon=-2.7, days=90)
except PlanLimitExceeded as e:
    tt.tide_extremes(lat=51.5, lon=-2.7, days=e.limit)   # e.limit == 31
```

`AuthenticationError` (401), `PermissionDenied` (403, a tier you are not on),
`PlanLimitExceeded` and `InvalidRequest` (400), `RateLimited` (429),
`DataUnavailable` (503), `ServerError` (5xx). All subclass `ThirdtrailError`.

Transient failures and 429s are retried with backoff. A plan ceiling is not —
it will fail identically every time.

## Keys

Mint one at [thirdtrail.life/apis/keys/](https://thirdtrail.life/apis/keys/).
A key belongs to one subscription, so it works with one API; a Tides key
calling a solar endpoint gets `PermissionDenied`.

There is a free tier on every API.

## Not covered yet

Bulk (`POST`) endpoints, iCalendar feeds and webhook management. Use the REST
API directly for those — the full contract is published as
[OpenAPI 3.1](https://thirdtrail.life/openapi.json).

Using an AI agent? There is an [MCP server](https://thirdtrail.life/docs/mcp/)
that exposes the same data as tools.

## Licence

MIT
