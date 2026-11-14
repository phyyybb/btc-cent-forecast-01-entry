Forecast formula in `main.ts`: `guess = 0.90 * last + 0.10 * mean(last 90 closes) + 0.07 * (last - close 45 min ago) / 45 * 240`.
Damped persistence anchored to a 90-close mean, plus 7% of the trailing 45-minute per-minute drift extrapolated over the 240-minute horizon.
Result is clamped to the 5-decimal grid inside `[0.00001, 9_999_999.99999]` via `price5`.
