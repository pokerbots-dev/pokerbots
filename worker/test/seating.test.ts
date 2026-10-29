import { expect, test } from "vitest";
import { tables } from "../src/seating";
import { elo } from "../src/rating";

test("tables seat everyone once and fill only when asked", () => {
  const bots = [...Array(8).keys()];
  const filled = tables(bots, true);
  expect(filled.map((t) => t.length)).toEqual([6, 6]);
  expect(filled.flat().filter((b) => b !== null).sort((a, b) => a! - b!)).toEqual(bots);
  expect(tables(bots, false)).toHaveLength(1);
  expect(tables([1], false)).toHaveLength(0);
});

test("elo is zero-sum and rewards places", () => {
  const deltas = elo([1500, 1500, 1500, 1500, 1500, 1500]);
  expect(deltas.reduce((a, b) => a + b)).toBeCloseTo(0);
  expect(deltas[0]).toBeGreaterThan(0);
  expect(deltas[5]).toBeLessThan(0);
  expect(elo([1400, 1600])[0]).toBeGreaterThan(elo([1600, 1400])[0]);
});
