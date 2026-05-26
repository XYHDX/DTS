"""Exponential moving average — for fuel level smoothing and similar.

Per §4.B of transit_architecture_guide.md, the recommended formula is:

    S_t = α * Y_t + (1 - α) * S_{t-1}

with α ≈ 0.1. This module also offers refuel + theft event detection by
watching for big positive / negative steps in the smoothed series.

The ideal place for fuel smoothing is **on the device** (the guide makes
this explicit: § "Fuel Level Smoothing (Edge)"). This module exists for
two cases:

  1. Legacy devices that don't smooth on-device. We apply EMA in the
     `mqtt_ingest.py` router before persisting the row.
  2. Server-side anomaly detection — sudden steps in the *smoothed* series
     are robust against tank sloshing and are the basis for the
     refuel / theft event types.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, Optional


DEFAULT_ALPHA = 0.10


def ema_step(previous: Optional[float], sample: float, alpha: float = DEFAULT_ALPHA) -> float:
    """One step of the EMA recurrence. Returns the sample itself when
    `previous` is None — i.e. the filter is seeded with the first reading."""
    if previous is None:
        return sample
    return alpha * sample + (1.0 - alpha) * previous


def ema_series(samples: Iterable[float], alpha: float = DEFAULT_ALPHA) -> Iterator[float]:
    """Yield the smoothed series in lockstep with an input iterable."""
    state: Optional[float] = None
    for s in samples:
        state = ema_step(state, s, alpha)
        yield state


# ── Stateful filter object for hot-path use ───────────────────────────────
@dataclass
class EMAFilter:
    """Stateful smoother — one instance per (vehicle_id, signal). Keep them
    in a small dict keyed on `(vehicle_id, "fuel")` inside the consumer."""
    alpha: float = DEFAULT_ALPHA
    state: Optional[float] = None

    def push(self, sample: float) -> float:
        self.state = ema_step(self.state, sample, self.alpha)
        return self.state

    def reset(self) -> None:
        self.state = None


# ── Refuel / theft detection ──────────────────────────────────────────────
@dataclass
class FuelEvent:
    kind: str           # 'refuel' | 'theft' | 'unknown_step'
    delta_pct: float    # +N for fill, -N for drain
    smoothed_before: float
    smoothed_after: float


def classify_fuel_step(
    smoothed_before: float,
    smoothed_after: float,
    *,
    engine_state: Optional[bool] = None,
    refuel_threshold_pct: float = 8.0,
    theft_threshold_pct: float = 5.0,
) -> Optional[FuelEvent]:
    """Detect a fuel event from two consecutive smoothed samples.

    Per the guide, the two events we care about are:
      * **Refuel** — large positive step. Usually with the engine off at a
        pump, but we don't require it.
      * **Theft**  — large negative step **with the engine off**.

    Returns None when the step is normal driving consumption.
    """
    delta = smoothed_after - smoothed_before
    if delta >= refuel_threshold_pct:
        return FuelEvent(
            kind="refuel",
            delta_pct=delta,
            smoothed_before=smoothed_before,
            smoothed_after=smoothed_after,
        )
    if delta <= -theft_threshold_pct and engine_state is False:
        return FuelEvent(
            kind="theft",
            delta_pct=delta,
            smoothed_before=smoothed_before,
            smoothed_after=smoothed_after,
        )
    if abs(delta) >= max(refuel_threshold_pct, theft_threshold_pct):
        # Big step but didn't match either rule — surface for ops review.
        return FuelEvent(
            kind="unknown_step",
            delta_pct=delta,
            smoothed_before=smoothed_before,
            smoothed_after=smoothed_after,
        )
    return None
