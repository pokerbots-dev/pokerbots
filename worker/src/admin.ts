import { send } from "./alerts";
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
    return { users, games_today: games, liabilities, withdrawn_today: withdrawn, hot_usdc: hot.usdc, hot_sol: hot.sol };
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
