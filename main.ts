// BTC cent price estimator (deterministic; no randomness or clock).
// Reads each *.in JSON case and writes a rounded 1-minute-ahead price guess.
import { readdirSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const inputDir = process.env.MAKEFUN_INPUT_DIR ?? "/input";
const outputDir = process.env.MAKEFUN_OUTPUT_DIR ?? "/output";

function round5(x: number): number {
  return Math.round(x * 100000) / 100000;
}

function clampPositive(x: number): number {
  if (x <= 0) return 0.00001;
  if (x >= 10000000) return 9999999.99999;
  return x;
}

mkdirSync(outputDir, { recursive: true });

const inFiles = readdirSync(inputDir)
  .filter((name) => name.endsWith(".in"))
  .sort();

for (const name of inFiles) {
  const data = JSON.parse(readFileSync(join(inputDir, name), "utf8"));
  const id: string = data.case;
  const prices: number[] = data.markets[0].prices;

  const last = prices[prices.length - 1];
  const recent = prices.slice(-90);
  const mean90 = recent.reduce((sum, price) => sum + price, 0) / recent.length;
  const close45 = prices.length >= 45 ? prices[prices.length - 45] : prices[0];
  const drift = ((last - close45) / 45) * 240;

  const guess = clampPositive(round5(0.9 * last + 0.1 * mean90 + 0.07 * drift));

  writeFileSync(
    join(outputDir, `${id}.out`),
    JSON.stringify({ forecasts: [{ case: id, price: guess }] })
  );
}
