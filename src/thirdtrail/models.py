"""Typed views over the response payloads.

Deliberately thin. The API is the source of truth and its responses carry
fields these classes do not model, so every object keeps the raw dict in
``.raw`` — a new server field is reachable immediately rather than after a
client release. The typed attributes cover what callers reach for most and,
more usefully, hand back ``datetime`` objects instead of strings.

That parsing is the main thing being bought here. Every caller otherwise
writes the same ``datetime.fromisoformat`` loop, and the careless version
drops the offset and silently computes in UTC.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any


def _dt(value: Any) -> dt.datetime | None:
    """Parse an ISO 8601 timestamp, preserving its offset."""
    if not value or not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value)
    except ValueError:
        return None


def _date(value: Any) -> dt.date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class Interval:
    """A start/end pair, such as golden hour."""
    start: dt.datetime | None
    end: dt.datetime | None


@dataclass(frozen=True)
class GoldenBlueHour:
    morning_start: dt.datetime | None
    morning_end: dt.datetime | None
    evening_start: dt.datetime | None
    evening_end: dt.datetime | None

    @classmethod
    def from_api(cls, d: dict[str, Any] | None) -> GoldenBlueHour:
        d = d or {}
        return cls(_dt(d.get("morning_start")), _dt(d.get("morning_end")),
                   _dt(d.get("evening_start")), _dt(d.get("evening_end")))

    @property
    def morning(self) -> Interval:
        return Interval(self.morning_start, self.morning_end)

    @property
    def evening(self) -> Interval:
        return Interval(self.evening_start, self.evening_end)


@dataclass(frozen=True)
class Sun:
    rise: dt.datetime | None
    set: dt.datetime | None
    transit: dt.datetime | None
    golden_hour: GoldenBlueHour
    blue_hour: GoldenBlueHour
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @classmethod
    def from_api(cls, d: dict[str, Any] | None) -> Sun:
        d = d or {}
        return cls(_dt(d.get("rise")), _dt(d.get("set")), _dt(d.get("transit")),
                   GoldenBlueHour.from_api(d.get("golden_hour")),
                   GoldenBlueHour.from_api(d.get("blue_hour")), d)


@dataclass(frozen=True)
class MoonPhase:
    name: str | None
    illumination: float | None


@dataclass(frozen=True)
class Moon:
    rise: dt.datetime | None
    set: dt.datetime | None
    phase: MoonPhase
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @classmethod
    def from_api(cls, d: dict[str, Any] | None) -> Moon:
        d = d or {}
        p = d.get("phase") or {}
        return cls(_dt(d.get("rise")), _dt(d.get("set")),
                   MoonPhase(p.get("name"), p.get("illumination")), d)


@dataclass(frozen=True)
class TideExtreme:
    type: str            # "high" or "low"
    time: dt.datetime | None
    height_m: float | None
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> TideExtreme:
        return cls(d.get("type", ""), _dt(d.get("time")), d.get("height_m"), d)

    @property
    def is_high(self) -> bool:
        return self.type == "high"


@dataclass(frozen=True)
class SolarSample:
    time: dt.datetime | None
    azimuth: float | None
    altitude: float | None
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> SolarSample:
        return cls(_dt(d.get("time")), d.get("azimuth"), d.get("altitude"), d)


@dataclass(frozen=True)
class Day:
    """One day of results.

    Carries tides only when they were asked for — ``tide_window`` returns them,
    ``ephemerides`` does not — so ``tides`` is simply empty for the latter.
    """
    date: dt.date | None
    sun: Sun
    moon: Moon
    tides: list[TideExtreme]
    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    @classmethod
    def from_api(cls, d: dict[str, Any]) -> Day:
        return cls(
            _date(d.get("date")),
            Sun.from_api(d.get("sun")),
            Moon.from_api(d.get("moon")),
            [TideExtreme.from_api(t) for t in d.get("tides") or []],
            d,
        )

    @property
    def high_waters(self) -> list[TideExtreme]:
        return [t for t in self.tides if t.type == "high"]

    @property
    def low_waters(self) -> list[TideExtreme]:
        return [t for t in self.tides if t.type == "low"]


def parse_days(payload: dict[str, Any]) -> list[Day]:
    """Pull the ``days`` array out of a response, keeping the envelope on each.

    The envelope (``notice``, ``request``, ``resolved``) stays reachable at
    ``day.response`` — ``resolved.elevation_source`` in particular tells you
    whether elevation came from you, a lookup, or the sea-level default.
    """
    days = [Day.from_api(d) for d in payload.get("days") or []]
    for day in days:
        object.__setattr__(day, "response", payload)
    return days
