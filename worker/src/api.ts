import type { User } from "./auth";
import { ATTEST_VERSION, BUY_IN, MAX_BOT_BYTES, type Env } from "./env";
import { history } from "./history";
import { HttpError, body, type Routes } from "./http";
import { balance, balanceOf } from "./ledger";
import { botKey } from "./match";
import { prepareDeposit, requestWithdrawal, submitDeposit, withdrawalAddress } from "./payments";
import { address } from "@solana/kit";
import { balances, chain, isAddress } from "./solana";

interface Ctx {
  req: Request;
  env: Env;
  user: User;
}

const ZIP_MAGIC = 0x04034b50;
const RECENT_GAMES = 10;
const BOARD_SIZE = 20;
const BOARD_MIN_GAMES = 20;

const attested = (env: Env, userId: number) =>
  env.DB.prepare("SELECT 1 FROM attestations WHERE user_id = ? AND version = ?").bind(userId, ATTEST_VERSION).first().then(Boolean);

function mode(value: unknown) {
  if (value !== "paper" && value !== "live") throw new HttpError(400, "mode is paper or live");
  return value;
}

export const userRoutes: Routes<Ctx> = {
  async "GET /me"({ env, user }) {
    const [versions, deployments, funds, withdrawTo, held, agreed, liveReady] = await Promise.all([
      env.DB.prepare("SELECT version FROM versions WHERE user_id = ? ORDER BY version").bind(user.id).all<{ version: number }>(),
      env.DB.prepare(
        `SELECT d.mode, d.version, r.rating, r.games,
           (SELECT COUNT(*) FROM seats s JOIN games g ON g.id = s.game_id
            WHERE s.user_id = d.user_id AND g.mode = d.mode AND g.status != 'failed' AND g.created_at >= date('now')) AS today
         FROM deployments d JOIN ratings r USING (user_id, mode) WHERE d.user_id = ?`,
      ).bind(user.id).all<{ mode: string }>(),
      balance(env, user.id),
      withdrawalAddress(env, user.id),
      user.wallet ? chain(env).then((c) => balances(c, address(user.wallet!))).catch(() => null) : null,
      attested(env, user.id),
      env.DB.prepare(`SELECT COUNT(*) AS n FROM deployments d WHERE d.mode = 'live' AND ${balanceOf("d.user_id")} >= ?`)
        .bind(BUY_IN).first<number>("n"),
    ]);
    return {
      login: user.login,
      wallet: user.wallet,
      withdraw_to: withdrawTo,
      attested: agreed,
      live_ready: liveReady,
      buy_in: BUY_IN,
      balance: funds,
      wallet_usdc: held?.usdc ?? null,
      wallet_sol: held?.sol ?? null,
      versions: versions.results.map((v) => v.version),
      deployments: Object.fromEntries(deployments.results.map((d) => [d.mode, d])),
    };
  },

  async "POST /versions"({ req, env, user }) {
    const data = await req.arrayBuffer();
    if (data.byteLength > MAX_BOT_BYTES) throw new HttpError(413, "bot is over 1 MB zipped");
    if (data.byteLength < 4 || new DataView(data).getUint32(0, true) !== ZIP_MAGIC) throw new HttpError(400, "not a zip");
    const version = (await env.DB.prepare(
      "INSERT INTO versions (user_id, version, size) SELECT ?1, COALESCE(MAX(version), 0) + 1, ?2 FROM versions WHERE user_id = ?1 RETURNING version",
    ).bind(user.id, data.byteLength).first<number>("version"))!;
    try {
      await env.BOTS.put(botKey(user.id, version), data);
    } catch (e) {
      await env.DB.prepare("DELETE FROM versions WHERE user_id = ? AND version = ?").bind(user.id, version).run();
      throw e;
    }
    return { version };
  },

  async "POST /deployments"({ req, env, user }) {
    const input = await body<{ mode: unknown; version: unknown }>(req);
    const m = mode(input.mode);
    if (m === "live" && !(await attested(env, user.id))) throw new HttpError(403, "live play needs the 18+ and location confirmation");
    const exists = await env.DB.prepare("SELECT 1 FROM versions WHERE user_id = ? AND version = ?").bind(user.id, input.version).first();
    if (!exists) throw new HttpError(404, `no version v${input.version}`);
    await env.DB.batch([
      env.DB.prepare("INSERT INTO deployments VALUES (?, ?, ?) ON CONFLICT (user_id, mode) DO UPDATE SET version = excluded.version")
        .bind(user.id, m, input.version),
      env.DB.prepare("INSERT OR IGNORE INTO ratings (user_id, mode) VALUES (?, ?)").bind(user.id, m),
    ]);
    return { mode: m, version: input.version };
  },

  async "DELETE /deployments/:mode"({ env, user }, [m]) {
    await env.DB.prepare("DELETE FROM deployments WHERE user_id = ? AND mode = ?").bind(user.id, mode(m)).run();
    return { mode: m };
  },

  async "POST /attest"({ req, env, user }) {
    const cf = req.cf as { country?: string; region?: string } | undefined;
    await env.DB.batch([
      env.DB.prepare("INSERT INTO attestations (user_id, version, ip, country, region) VALUES (?, ?, ?, ?, ?)")
        .bind(user.id, ATTEST_VERSION, req.headers.get("cf-connecting-ip"), cf?.country ?? null, cf?.region ?? null),
      env.DB.prepare("UPDATE users SET attested_at = CURRENT_TIMESTAMP WHERE id = ?").bind(user.id),
    ]);
    return { attested: true };
  },

  async "PUT /wallet"({ req, env, user }) {
    const { address } = await body<{ address: string }>(req);
    if (typeof address !== "string" || !isAddress(address)) throw new HttpError(400, "invalid Solana address");
    await env.DB.prepare("UPDATE users SET wallet = ? WHERE id = ?").bind(address, user.id).run();
    return { wallet: address };
  },

  async "GET /games"({ env, user }) {
    const { results } = await env.DB.prepare(
      `SELECT g.id, g.mode, g.status, g.hands, g.created_at, s.place, s.rating_delta,
         CASE WHEN g.mode = 'live' THEN (SELECT COALESCE(SUM(amount), 0) FROM ledger
           WHERE user_id = s.user_id AND ref = g.id || ':' || s.seat AND kind IN ('buyin', 'payout', 'refund')) END AS net
       FROM seats s JOIN games g ON g.id = s.game_id
       WHERE s.user_id = ? ORDER BY g.created_at DESC LIMIT ?`,
    ).bind(user.id, RECENT_GAMES).all();
    return results;
  },

  // Ranked by rating; won is live table results only (buy-ins, payouts, game refunds).
  async "GET /leaderboard/:mode"({ env, user }, [m]) {
    const { results } = await env.DB.prepare(
      `SELECT u.login, r.user_id, ROUND(r.rating) AS rating, r.games,
         CASE WHEN r.mode = 'live' THEN (SELECT COALESCE(SUM(amount), 0) FROM ledger l WHERE l.user_id = r.user_id
           AND (l.kind IN ('buyin', 'payout') OR (l.kind = 'refund' AND l.ref NOT LIKE 'w:%'))) END AS won
       FROM ratings r JOIN users u ON u.id = r.user_id
       WHERE r.mode = ? AND r.games >= ? ORDER BY r.rating DESC`,
    ).bind(mode(m), BOARD_MIN_GAMES).all<{ user_id: number }>();
    const rank = results.findIndex((r) => r.user_id === user.id) + 1;
    return {
      min_games: BOARD_MIN_GAMES,
      ranked: results.length,
      you: rank || null,
      rows: results.slice(0, BOARD_SIZE).map(({ user_id, ...row }) => row),
    };
  },

  async "GET /history"({ req, env, user }) {
    return history(req, env, user);
  },

  async "POST /deposits"({ req, env, user }) {
    return prepareDeposit(env, user, (await body<{ amount: unknown }>(req)).amount);
  },

  async "POST /deposits/:signature"({ req, env, user }, [signature]) {
    return submitDeposit(env, user, signature, (await body<{ transaction: string }>(req)).transaction);
  },

  async "POST /withdrawals"({ req, env, user }) {
    return requestWithdrawal(env, user, (await body<{ amount: unknown }>(req)).amount);
  },
};
