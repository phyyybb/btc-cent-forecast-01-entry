#!/usr/bin/env python3
"""Forecast BTC's price `horizon_minutes` ahead from 72h of 1-minute closes.

Model: last price plus the fitted drift. The per-minute log returns are fit as
an AR(1), r_t = c + phi*r_{t-1}; the expected cumulative log return over the
next `horizon_minutes` is projected (no extra shrink: the AR(1) already
mean-reverts through phi) and compounded onto the last close. The lookback
window feeding the fit is self-tuned over a small grid by walk-forward
validation on the case's own history, keeping the window with the smallest mean
absolute hold-out error. Everything is deterministic (no randomness), stdlib
only, no network.
"""

import json
import math
import os

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

MIN_PRICE = 0.00001
MAX_PRICE = 9_999_999.99999
# Candidate lookback windows (minutes of history feeding the AR(1) fit). The
# best one is chosen per case by walk-forward validation, so the model adapts to
# each case's own recent regime instead of pinning a fixed window.
LOOKBACK_GRID = (720, 1080, 1440, 1800, 2160, 2520, 2880, 3600, 4320)


def price5(x):
    """Clamp to the scorer's (0, 10,000,000) and round to the grid's 5 decimals."""
    x = min(MAX_PRICE, max(MIN_PRICE, x))
    return math.floor(x * 1e5 + 0.5) / 1e5


def _ar1_forecast(series, horizon):
    """Fit AR(1) on `series`'s minute log returns and project `horizon` ahead."""
    n = len(series)
    if n < 2:
        return None
    returns = [math.log(series[i] / series[i - 1]) for i in range(1, n)]
    if len(returns) < 2:
        return None

    # OLS fit of AR(1): r_t = c + phi * r_{t-1}
    y = returns[1:]
    x = returns[:-1]
    m = len(y)
    sx = sum(x)
    sy = sum(y)
    sxx = sum(v * v for v in x)
    sxy = sum(a * b for a, b in zip(x, y))
    den = m * sxx - sx * sx
    if abs(den) < 1e-30:
        phi = 0.0
        c = sy / m
    else:
        phi = (m * sxy - sx * sy) / den
        c = (sy - phi * sx) / m

    # Keep phi in a stable band; minute returns never estimate it far from 0.
    phi = max(-0.9, min(0.9, phi))
    r0 = returns[-1]

    # Expected cumulative log return over the next `horizon` minutes. The AR(1)
    # already mean-reverts through phi, so the projected drift is not shrunk
    # further (an extra damping factor double-counted that mean reversion).
    if abs(1.0 - phi) < 1e-12:
        total = c * horizon + r0 * horizon
    else:
        g = phi * (1.0 - phi ** horizon) / (1.0 - phi)
        total = (c / (1.0 - phi)) * (horizon - g) + r0 * g

    return series[-1] * math.exp(total)


def forecast(prices, horizon):
    n = len(prices)
    last = prices[-1]
    if n < 2:
        return price5(last)

    # Self-tune the lookback window: for each candidate, run a walk-forward
    # backtest over the case's own history (every non-overlapping `horizon`
    # block) and score it by mean absolute error; keep the best window.
    best_lookback = None
    best_err = None
    for lookback in LOOKBACK_GRID:
        total = 0.0
        count = 0
        end = n - horizon
        while end >= 2:
            start = max(0, end - lookback)
            pred = _ar1_forecast(prices[start:end], horizon)
            if pred is not None:
                actual = prices[end + horizon] if end + horizon < n else last
                total += abs(pred - actual)
                count += 1
            end -= horizon
        if count == 0:
            continue
        err = total / count
        if best_err is None or err < best_err:
            best_err = err
            best_lookback = lookback

    if best_lookback is None:
        return price5(last)

    start = max(0, n - best_lookback)
    pred = _ar1_forecast(prices[start:], horizon)
    if pred is None:
        return price5(last)
    return price5(pred)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    inputs = sorted(f for f in os.listdir(INPUT_DIR) if f.endswith(".in"))
    for name in inputs:
        stem = name[: -len(".in")]
        with open(os.path.join(INPUT_DIR, name), "r", encoding="utf-8") as fh:
            case = json.load(fh)
        case_id = case.get("case", stem)
        markets = case.get("markets", [])
        if not markets:
            raise ValueError(f"{name} holds no market")
        prices = markets[0].get("prices", [])
        if not prices:
            raise ValueError(f"{name} holds no prices")
        horizon = int(case.get("horizon_minutes", 240))
        price = forecast(prices, horizon)
        out = {"forecasts": [{"case": case_id, "price": price}]}
        with open(os.path.join(OUTPUT_DIR, stem + ".out"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(out, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
