"""Fixed alert rules. The LLM never decides whether to alert or at what level.

- Alert when the model's level is at or above `min_level` (default high) for a
  lead day up to `max_lead` (default 2), or when the GloFAS river flag is set.
- One alert per tehsil, level and valid date. A later run sends again for the
  same tehsil and date only if the level rose; the same or a lower level is skipped.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from backend.app.contracts import RiskLevel, TehsilRiskForecast


@dataclass(frozen=True)
class AlertCandidate:
    forecast: TehsilRiskForecast
    reason_codes: tuple[str, ...]

    @property
    def key(self) -> tuple[str, str, dt.date]:
        return (self.forecast.tehsil_id, self.forecast.level.value, self.forecast.valid_date)


def select_candidates(forecasts: list[TehsilRiskForecast], min_level: RiskLevel = RiskLevel.HIGH,
                      max_lead: int = 2, in_scope: set[str] | None = None) -> list[AlertCandidate]:
    """The highest qualifying forecast per tehsil and valid date."""

    best: dict[tuple[str, dt.date], AlertCandidate] = {}
    for f in forecasts:
        if f.lead_days > max_lead or (in_scope is not None and f.tehsil_id not in in_scope):
            continue
        reasons = []
        if f.level.rank >= min_level.rank:
            reasons.append(f"model_{f.level.value}")
        if f.glofas_flag:
            reasons.append("river_flag")
        if not reasons:
            continue
        reasons += [f"driver:{d.feature}" for d in f.drivers[:3]]
        candidate = AlertCandidate(f, tuple(reasons))
        key = (f.tehsil_id, f.valid_date)
        current = best.get(key)
        # Prefer the higher level; for equal levels, the shorter lead (newer forecast).
        if current is None or (f.level.rank, -f.lead_days) > (current.forecast.level.rank, -current.forecast.lead_days):
            best[key] = candidate
    return sorted(best.values(), key=lambda c: (c.forecast.valid_date, -c.forecast.level.rank, c.forecast.tehsil_id))


def should_send(candidate: AlertCandidate, previous_levels: list[str]) -> bool:
    """Send unless an alert at the same or a higher level already went out for this tehsil and date."""

    if not previous_levels:
        return True
    highest = max(RiskLevel(level).rank for level in previous_levels)
    return candidate.forecast.level.rank > highest
