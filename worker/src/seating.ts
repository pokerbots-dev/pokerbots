import { SEATS } from "./env";

function shuffle<T>(items: T[], random: () => number): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

// Random tables of SEATS; a short last table is dropped, or filled with house seats (null).
export function tables<T>(bots: T[], fill: boolean, random = Math.random): (T | null)[][] {
  const order = shuffle(bots, random);
  const out: (T | null)[][] = [];
  for (let i = 0; i < order.length; i += SEATS) {
    const table: (T | null)[] = order.slice(i, i + SEATS);
    if (table.length < SEATS && !fill) break;
    while (table.length < SEATS) table.push(null);
    out.push(shuffle(table, random));
  }
  return out;
}
