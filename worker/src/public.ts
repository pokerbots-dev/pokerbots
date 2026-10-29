// Public, read-only stats for profile and leaderboard pages. No balances, wallets or game details.
import type { Env } from "./env";
import { HttpError, type Routes } from "./http";

export const BOARD_SIZE = 20;
export const BOARD_MIN_GAMES = 20;
const MODES = ["paper", "live"] as const;

export interface BoardRow {
  user_id: number;
  login: string;
  rating: number;
  games: number;
  won: number | null;
}

// Ranked by rating; won is live table results only (buy-ins, payouts, game refunds).
export async function board(env: Env, mode: string) {
  const { results } = await env.DB.prepare(
    `SELECT u.login, r.user_id, ROUND(r.rating) AS rating, r.games,
       CASE WHEN r.mode = 'live' THEN (SELECT COALESCE(SUM(amount), 0) FROM ledger l WHERE l.user_id = r.user_id
         AND (l.kind IN ('buyin', 'payout') OR (l.kind = 'refund' AND l.ref NOT LIKE 'w:%'))) END AS won
     FROM ratings r JOIN users u ON u.id = r.user_id
     WHERE r.mode = ? AND r.games >= ? ORDER BY r.rating DESC`,
  ).bind(mode, BOARD_MIN_GAMES).all<BoardRow>();
  return results;
}

const publicRow = ({ user_id, ...row }: BoardRow) => row;

export async function stats(env: Env, userId: number) {
  const out: Record<string, unknown> = {};
  for (const mode of MODES) {
    const r = await env.DB.prepare("SELECT rating, games, COALESCE(best, rating) AS best FROM ratings WHERE user_id = ? AND mode = ?")
      .bind(userId, mode).first<{ rating: number; games: number; best: number }>();
    if (!r) {
      out[mode] = null;
      continue;
    }
    const rows = await board(env, mode);
    const rank = rows.findIndex((row) => row.user_id === userId) + 1;
    out[mode] = {
      rating: Math.round(r.rating),
      games: r.games,
      rank: rank || null,
      ranked: rows.length,
      won: rank ? rows[rank - 1].won : null,
      best: Math.round(Math.max(r.best, r.rating)),
    };
  }
  return out;
}

export const publicRoutes: Routes<{ env: Env }> = {
  async "GET /public/top"({ env }) {
    const [paper, live] = await Promise.all(MODES.map((m) => board(env, m)));
    return { min_games: BOARD_MIN_GAMES, paper: paper.slice(0, BOARD_SIZE).map(publicRow), live: live.slice(0, BOARD_SIZE).map(publicRow) };
  },

  async "GET /public/players/:login"({ env }, [login]) {
    const user = await env.DB.prepare("SELECT id, login FROM users WHERE login = ? COLLATE NOCASE").bind(login)
      .first<{ id: number; login: string }>();
    if (!user) throw new HttpError(404, "no such player");
    return { login: user.login, min_games: BOARD_MIN_GAMES, ...(await stats(env, user.id)) };
  },
};
