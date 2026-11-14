#!/usr/bin/env python3
"""Forecast BTC's price `horizon_minutes` ahead from 72h of 1-minute closes.

Model: last price plus a damped drift. The per-minute log returns are fit as an
AR(1), r_t = c + phi*r_{t-1}; the expected cumulative log return over the next
`horizon_minutes` is projected, shrunk by DAMPING, and compounded onto the last
close. Everything is deterministic (no randomness), stdlib only, no network.
"""

import json
import math
import os

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

MIN_PRICE = 0.00001
MAX_PRICE = 9_999_999.99999
# Damped drift: keep 90% of the fitted per-minute drift when projecting ahead.
DAMPING = 0.9


def price5(x):
    """Clamp to the scorer's (0, 10,000,000) and round to the grid's 5 decimals."""
    x = min(MAX_PRICE, max(MIN_PRICE, x))
    return math.floor(x * 1e5 + 0.5) / 1e5


def forecast(prices, horizon):
    n = len(prices)
    last = prices[-1]
    if n < 2:
        return price5(last)

    returns = [math.log(prices[i] / prices[i - 1]) for i in range(1, n)]
    if len(returns) < 2:
        return price5(last)

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

    # Expected cumulative log return over the next `horizon` minutes.
    if abs(1.0 - phi) < 1e-12:
        total = c * horizon + r0 * horizon
    else:
        g = phi * (1.0 - phi ** horizon) / (1.0 - phi)
        total = (c / (1.0 - phi)) * (horizon - g) + r0 * g

    return price5(last * math.exp(total * DAMPING))


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
