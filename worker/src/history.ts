// Finished games for analysis. Games appear 10 minutes after they end; hole cards are shown
// only for the requester's own seat and for hands that reached showdown, as at a real table.
import type { User } from "./auth";
import type { Env } from "./env";
import { HttpError } from "./http";
import { historyKey } from "./match";

const PAGE = 50;
const DELAY = "-10 minutes";
const DATE = /^\d{4}-\d{2}-\d{2}$/;

interface GameRow {
  id: string;
  mode: string;
  finished_at: string;
  hands: number;
}

interface SeatRow {
  game_id: string;
  seat: number;
  user_id: number | null;
  login: string | null;
  version: number | null;
  place: number;
  rating_delta: number | null;
  late: number | null;
  errors: number | null;
  decisions: number | null;
}

interface Hand {
  shown: (string[] | null)[];
  hole: (string[] | null)[];
}

export async function history(req: Request, env: Env, user: User) {
  const q = new URL(req.url).searchParams;
  const mode = q.get("mode");
  const since = q.get("since") ?? "2000-01-01";
  const until = q.get("until") ?? "2999-12-31";
  if ((mode && mode !== "paper" && mode !== "live") || !DATE.test(since) || !DATE.test(until)) {
    throw new HttpError(400, "mode is paper or live; dates are YYYY-MM-DD");
  }
  const [afterAt, afterId] = (q.get("after") ?? "|").split("|");
  const { results: games } = await env.DB.prepare(
    `SELECT id, mode, finished_at, hands FROM games g
     WHERE status = 'done' AND finished_at <= datetime('now', ?1)
       AND finished_at >= ?2 AND finished_at < date(?3, '+1 day')
       AND (?4 IS NULL OR mode = ?4)
       AND (?5 OR EXISTS (SELECT 1 FROM seats WHERE game_id = g.id AND user_id = ?6))
       AND (finished_at, id) > (?7, ?8)
     ORDER BY finished_at, id LIMIT ?9`,
  ).bind(DELAY, since, until, mode, q.get("all") === "1" ? 1 : 0, user.id, afterAt, afterId, PAGE).all<GameRow>();
  if (!games.length) return { games: [], next: null };

  const { results: seats } = await env.DB.prepare(
    `SELECT s.game_id, s.seat, s.user_id, u.login, s.version, s.place, s.rating_delta, s.late, s.errors, s.decisions
     FROM seats s LEFT JOIN users u ON u.id = s.user_id
     WHERE s.game_id IN (${games.map(() => "?").join()}) ORDER BY s.seat`,
  ).bind(...games.map((g) => g.id)).all<SeatRow>();
  // What each live seat actually netted (buy-in, prize, refund), whatever the prizes were then.
  const { results: nets } = await env.DB.prepare(
    `SELECT s.game_id || ':' || s.seat AS ref, SUM(l.amount) AS net FROM seats s
     JOIN ledger l ON l.ref = s.game_id || ':' || s.seat AND l.kind IN ('buyin', 'payout', 'refund')
     WHERE s.game_id IN (${games.map(() => "?").join()}) GROUP BY s.game_id, s.seat`,
  ).bind(...games.map((g) => g.id)).all<{ ref: string; net: number }>();
  const net = new Map(nets.map((n) => [n.ref, n.net]));

  const out = await Promise.all(games.map(async (g) => {
    const table = seats.filter((s) => s.game_id === g.id);
    const mine = table.filter((s) => s.user_id === user.id).map((s) => s.seat);
    return {
      id: g.id,
      mode: g.mode,
      finished_at: g.finished_at,
      hands_played: g.hands,
      you: mine[0] ?? null,
      players: table.map((s) => ({
        seat: s.seat,
        user: s.login ?? "house",
        ...(s.user_id === user.id ? { version: s.version, decisions: s.decisions, late: s.late, errors: s.errors } : {}),
        place: s.place,
        rating_change: s.rating_delta === null ? null : Math.round(s.rating_delta * 10) / 10,
        won: g.mode === "live" && s.user_id ? (net.get(`${g.id}:${s.seat}`) ?? 0) / 1e6 : null,
      })),
      hands: await hands(env, g.id, mine),
    };
  }));
  const last = games[games.length - 1];
  return { games: out, next: games.length === PAGE ? `${last.finished_at}|${last.id}` : null };
}

async function hands(env: Env, gameId: string, mine: number[]) {
  const object = await env.BOTS.get(historyKey(gameId));
  if (!object) return null;
  const { hands } = await new Response(object.body.pipeThrough(new DecompressionStream("gzip"))).json<{ hands: Hand[] }>();
  return hands.map((h) => ({ ...h, hole: h.hole.map((cards, seat) => (mine.includes(seat) || h.shown[seat] ? cards : null)) }));
}
