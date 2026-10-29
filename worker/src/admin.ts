import { send } from "./alerts";
import { SWITCHES, paused, setPaused, type Switch } from "./ops";
import type { Env } from "./env";
import { HttpError, body, type Routes } from "./http";
import { refundWithdrawal, sendWithdrawal } from "./payments";
import { chain, hotBalances } from "./solana";

interface Ctx {
  req: Request;
  env: Env;
}

export const adminRoutes: Routes<Ctx> = {
  async "GET /admin/stats"({ env }) {
    const one = (sql: string) => env.DB.prepare(sql).first<number>("n");
    const [users, games, liabilities, withdrawn, hot] = await Promise.all([
      one("SELECT COUNT(*) AS n FROM users"),
      one("SELECT COUNT(*) AS n FROM games WHERE created_at >= date('now')"),
      one("SELECT COALESCE(SUM(amount), 0) AS n FROM ledger WHERE user_id IS NOT NULL"),
      one("SELECT COALESCE(SUM(amount), 0) AS n FROM withdrawals WHERE status IN ('approved', 'sent', 'done') AND created_at >= date('now')"),
      chain(env).then(hotBalances),
    ]);
    return { users, games_today: games, liabilities, withdrawn_today: withdrawn, hot_usdc: hot.usdc, hot_sol: hot.sol, paused: await paused(env) };
  },

  async "POST /admin/pause/:what"({ env }, [what]) {
    return toggle(env, what, true);
  },

  async "POST /admin/resume/:what"({ env }, [what]) {
    return toggle(env, what, false);
  },

  async "POST /admin/users/:login/suspend"({ env }, [login]) {
    await setSuspended(env, login, true);
    return { suspended: true };
  },

  async "POST /admin/users/:login/unsuspend"({ env }, [login]) {
    await setSuspended(env, login, false);
    return { suspended: false };
  },

  // Manual credit (+) or debit (-) with a reason, recorded in the ledger like any other movement.
  async "POST /admin/users/:login/adjust"({ req, env }, [login]) {
    const { amount, reason, force } = await body<{ amount: unknown; reason: unknown; force?: boolean }>(req);
    if (!Number.isSafeInteger(amount) || amount === 0 || typeof reason !== "string" || !reason.trim()) {
      throw new HttpError(400, "amount (non-zero micro-USDC) and reason are required");
    }
    const id = await userId(env, login);
    // A debit may not take a balance below zero unless forced (e.g. clawing back a payout made in error).
    const { meta } = await env.DB.prepare(
      `INSERT INTO ledger (user_id, kind, amount, ref, note)
       SELECT ?1, 'adjustment', ?2, ?3, ?4 WHERE ?5 OR ?2 > 0 OR (SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE user_id = ?1) + ?2 >= 0`,
    ).bind(id, amount, `adj:${crypto.randomUUID()}`, reason.trim(), force ? 1 : 0).run();
    if (!meta.changes) throw new HttpError(400, "that would make the balance negative; add --force if intended");
    return { balance: await env.DB.prepare("SELECT COALESCE(SUM(amount), 0) AS b FROM ledger WHERE user_id = ?").bind(id).first<number>("b") };
  },

  async "POST /admin/test-alert"({ env }) {
    await send(env, `test (${env.SOLANA_CLUSTER})`, "Alerts from pokerbots reach this inbox.");
    return { sent: Boolean(env.EMAIL && env.ALERT_EMAIL) };
  },

  async "GET /admin/withdrawals"({ env }) {
    const { results } = await env.DB.prepare(
      "SELECT w.id, u.login, w.amount, w.created_at FROM withdrawals w JOIN users u ON u.id = w.user_id WHERE w.status = 'pending' ORDER BY w.created_at",
    ).all();
    return results;
  },

  async "POST /admin/withdrawals/:id"({ req, env }, [id]) {
    const { action } = await body<{ action: string }>(req);
    if (action === "reject") {
      await refundWithdrawal(env, id, "pending", "rejected");
    } else if (action === "approve") {
      await env.DB.prepare("UPDATE withdrawals SET status = 'approved' WHERE id = ? AND status = 'pending'").bind(id).run();
      await sendWithdrawal(env, id);
    } else {
      throw new HttpError(400, "action is approve or reject");
    }
    return { status: await env.DB.prepare("SELECT status FROM withdrawals WHERE id = ?").bind(id).first<string>("status") };
  },
};

async function toggle(env: Env, what: string, on: boolean) {
  const targets = what === "all" ? [...SWITCHES] : [what];
  if (!targets.every((w) => (SWITCHES as readonly string[]).includes(w))) throw new HttpError(400, "live, deposits, withdrawals or all");
  for (const w of targets) await setPaused(env, w as Switch, on);
  return { paused: await paused(env) };
}

async function userId(env: Env, login: string) {
  const id = await env.DB.prepare("SELECT id FROM users WHERE login = ? COLLATE NOCASE").bind(login).first<number>("id");
  if (!id) throw new HttpError(404, "no such user");
  return id;
}

async function setSuspended(env: Env, login: string, on: boolean) {
  const id = await userId(env, login);
  await env.DB.prepare(`UPDATE users SET suspended_at = ${on ? "CURRENT_TIMESTAMP" : "NULL"} WHERE id = ?`).bind(id).run();
}
