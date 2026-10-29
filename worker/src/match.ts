import { BUY_IN, GAMES_PER_MINUTE, PAPER_GAMES_PER_DAY, PRIZES, RAKE, RUNNERS, SEATS, type Env } from "./env";
import { balanceOf, credit, debit } from "./ledger";
import { elo } from "./rating";
import { tables } from "./seating";

type Mode = "paper" | "live";

interface Bot {
  user_id: number;
  version: number;
  today: number;
  queued: number;
  balance: number;
}

interface Game {
  id: string;
  mode: Mode;
  seed: number;
}

interface Seat {
  seat: number;
  user_id: number | null;
  version: number | null;
  house: string | null;
}

interface Outcome {
  places: number[];
  hands: number;
  stats: { late: number; errors: number }[];
}

const HOUSE = ["caller", "raiser"];
const INITIAL_RATING = 1500;

export const botKey = (userId: number, version: number) => `bots/${userId}/v${version}.zip`;

export async function matchmake(env: Env) {
  for (const mode of ["paper", "live"] as const) {
    const { results: bots } = await env.DB.prepare(
      `SELECT d.user_id, d.version,
         COUNT(g.id) FILTER (WHERE g.created_at >= date('now')) AS today,
         COUNT(g.id) FILTER (WHERE g.status = 'queued') AS queued,
         ${balanceOf("d.user_id")} AS balance
       FROM deployments d
       LEFT JOIN seats s ON s.user_id = d.user_id
       LEFT JOIN games g ON g.id = s.game_id AND g.mode = d.mode AND (g.created_at >= date('now') OR g.status = 'queued')
       WHERE d.mode = ? GROUP BY d.user_id`,
    ).bind(mode).all<Bot>();
    for (let round = 0; round < GAMES_PER_MINUTE; round++) {
      const eligible = bots.filter(
        (b) =>
          b.queued + round < GAMES_PER_MINUTE &&
          (mode === "paper" ? b.today + round < PAPER_GAMES_PER_DAY : b.balance >= BUY_IN * (round + 1)),
      );
      for (const table of tables(eligible, mode === "paper")) await createGame(env, mode, table);
    }
  }
}

async function createGame(env: Env, mode: Mode, table: (Bot | null)[]) {
  const id = crypto.randomUUID();
  const seed = crypto.getRandomValues(new Uint32Array(1))[0];
  const statements = [env.DB.prepare("INSERT INTO games (id, mode, status, seed) VALUES (?, ?, 'queued', ?)").bind(id, mode, seed)];
  table.forEach((b, seat) =>
    statements.push(
      env.DB.prepare("INSERT INTO seats (game_id, seat, user_id, version, house) VALUES (?, ?, ?, ?, ?)")
        .bind(id, seat, b?.user_id ?? null, b?.version ?? null, b ? null : HOUSE[seat % HOUSE.length]),
    ),
  );
  if (mode === "live") table.forEach((b, seat) => statements.push(debit(env, b!.user_id, "buyin", BUY_IN, `${id}:${seat}`)));
  const results = await env.DB.batch(statements);
  if (mode === "live" && results.slice(-SEATS).some((r) => !r.meta.changes)) return failGame(env, id);
  await env.GAMES.send(id);
}

export async function failGame(env: Env, id: string) {
  await env.DB.batch([
    env.DB.prepare("UPDATE games SET status = 'failed' WHERE id = ? AND status = 'queued'").bind(id),
    env.DB.prepare(
      `INSERT OR IGNORE INTO ledger (user_id, kind, amount, ref)
       SELECT user_id, 'refund', -amount, ref FROM ledger
       WHERE kind = 'buyin' AND ref LIKE ?1 || ':%' AND EXISTS (SELECT 1 FROM games WHERE id = ?1 AND status = 'failed')`,
    ).bind(id),
  ]);
}

export async function runGame(env: Env, id: string) {
  const game = await env.DB.prepare("SELECT * FROM games WHERE id = ? AND status = 'queued'").bind(id).first<Game>();
  if (!game) return;
  const { results: seats } = await env.DB.prepare("SELECT * FROM seats WHERE game_id = ? ORDER BY seat").bind(id).all<Seat>();
  const bots = await Promise.all(
    seats.map(async (s) => (s.house ? { house: s.house } : { code: await code(env, s.user_id!, s.version!) })),
  );
  const runner = env.RUNNER.get(env.RUNNER.idFromName(`runner-${Math.floor(Math.random() * RUNNERS)}`));
  const res = await runner.fetch("http://runner/run", { method: "POST", body: JSON.stringify({ seed: game.seed, bots }) });
  if (!res.ok) throw new Error(`runner ${res.status}`);
  await record(env, game, seats, await res.json<Outcome>());
}

async function code(env: Env, userId: number, version: number) {
  const object = await env.BOTS.get(botKey(userId, version));
  if (!object) throw new Error(`missing ${botKey(userId, version)}`);
  const data = new Uint8Array(await object.arrayBuffer());
  let binary = "";
  for (let i = 0; i < data.length; i += 0x8000) binary += String.fromCharCode(...data.subarray(i, i + 0x8000));
  return btoa(binary);
}

// One transaction; guarded by status = 'queued' so a retried game is never counted twice.
async function record(env: Env, game: Game, seats: Seat[], outcome: Outcome) {
  const users = seats.filter((s) => s.user_id).map((s) => s.user_id!);
  const { results } = await env.DB.prepare(
    `SELECT user_id, rating FROM ratings WHERE mode = ? AND user_id IN (${users.map(() => "?").join()})`,
  ).bind(game.mode, ...users).all<{ user_id: number; rating: number }>();
  const rating = new Map(results.map((r) => [r.user_id, r.rating]));
  const deltas = elo(outcome.places.map((seat) => rating.get(seats[seat].user_id!) ?? INITIAL_RATING));
  const queued = "EXISTS (SELECT 1 FROM games WHERE id = ? AND status = 'queued')";

  const statements = outcome.places.flatMap((seat, i) => {
    const { user_id } = seats[seat];
    const { late, errors } = outcome.stats[seat];
    const out = [
      env.DB.prepare("UPDATE seats SET place = ?, late = ?, errors = ? WHERE game_id = ? AND seat = ?").bind(i + 1, late, errors, game.id, seat),
    ];
    if (user_id) {
      out.push(
        env.DB.prepare(`UPDATE ratings SET rating = rating + ?, games = games + 1 WHERE user_id = ? AND mode = ? AND ${queued}`)
          .bind(deltas[i], user_id, game.mode, game.id),
      );
      if (game.mode === "live" && i < PRIZES.length) out.push(credit(env, user_id, "payout", PRIZES[i], `${game.id}:${seat}`));
    }
    return out;
  });
  if (game.mode === "live") statements.push(credit(env, null, "rake", RAKE, game.id));
  statements.push(env.DB.prepare("UPDATE games SET status = 'done', hands = ? WHERE id = ? AND status = 'queued'").bind(outcome.hands, game.id));
  await env.DB.batch(statements);
}
