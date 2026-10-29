import type { User } from "./auth";
import { MAX_BOT_BYTES, type Env } from "./env";
import { HttpError, body, type Routes } from "./http";
import { balance } from "./ledger";
import { botKey } from "./match";
import { prepareDeposit, requestWithdrawal, submitDeposit } from "./payments";
import { isAddress } from "./solana";

interface Ctx {
  req: Request;
  env: Env;
  user: User;
}

const ZIP_MAGIC = 0x04034b50;
const RECENT_GAMES = 10;

function mode(value: unknown) {
  if (value !== "paper" && value !== "live") throw new HttpError(400, "mode is paper or live");
  return value;
}

export const userRoutes: Routes<Ctx> = {
  async "GET /me"({ env, user }) {
    const [versions, deployments, funds] = await Promise.all([
      env.DB.prepare("SELECT version FROM versions WHERE user_id = ? ORDER BY version").bind(user.id).all<{ version: number }>(),
      env.DB.prepare(
        `SELECT d.mode, d.version, r.rating, r.games,
           (SELECT COUNT(*) FROM seats s JOIN games g ON g.id = s.game_id
            WHERE s.user_id = d.user_id AND g.mode = d.mode AND g.created_at >= date('now')) AS today
         FROM deployments d JOIN ratings r USING (user_id, mode) WHERE d.user_id = ?`,
      ).bind(user.id).all<{ mode: string }>(),
      balance(env, user.id),
    ]);
    return {
      login: user.login,
      wallet: user.wallet,
      attested: Boolean(user.attested_at),
      balance: funds,
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
    if (m === "live" && !user.attested_at) throw new HttpError(403, "live play needs the 18+ and location confirmation");
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

  async "POST /attest"({ env, user }) {
    await env.DB.prepare("UPDATE users SET attested_at = CURRENT_TIMESTAMP WHERE id = ? AND attested_at IS NULL").bind(user.id).run();
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
      `SELECT g.id, g.mode, g.status, g.hands, g.created_at, s.place FROM seats s JOIN games g ON g.id = s.game_id
       WHERE s.user_id = ? ORDER BY g.created_at DESC LIMIT ?`,
    ).bind(user.id, RECENT_GAMES).all();
    return results;
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
