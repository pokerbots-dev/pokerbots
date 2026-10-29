import { adminRoutes } from "./admin";
import { checkAlerts } from "./alerts";
import { userRoutes } from "./api";
import { authenticate, authenticateAdmin } from "./auth";
import type { Env } from "./env";
import { HttpError, route } from "./http";
import { failGame, matchmake, runGame } from "./match";
import { reconcile } from "./payments";

export { Runner } from "./runner";

const MAX_ATTEMPTS = 3;
const ALERT_EVERY_MINUTES = 10;

async function handle(req: Request, env: Env): Promise<unknown> {
  const { pathname } = new URL(req.url);
  if (pathname === "/health") return { ok: true, cluster: env.SOLANA_CLUSTER };
  if (pathname.startsWith("/admin/")) {
    const match = route(adminRoutes, req.method, pathname);
    if (!match) throw new HttpError(404, "not found");
    await authenticateAdmin(req, env);
    return match[0]({ req, env }, match[1]);
  }
  const match = route(userRoutes, req.method, pathname);
  if (!match) throw new HttpError(404, "not found");
  return match[0]({ req, env, user: await authenticate(req, env) }, match[1]);
}

export default {
  async fetch(req, env) {
    try {
      return Response.json(await handle(req, env));
    } catch (e) {
      if (e instanceof HttpError) return Response.json({ error: e.message }, { status: e.status });
      console.error(e);
      return Response.json({ error: "internal error" }, { status: 500 });
    }
  },

  async scheduled(event, env) {
    const alerts = new Date(event.scheduledTime).getUTCMinutes() % ALERT_EVERY_MINUTES === 0 ? checkAlerts(env) : null;
    const jobs = await Promise.allSettled([matchmake(env), reconcile(env), alerts]);
    jobs.forEach((j) => j.status === "rejected" && console.error(j.reason));
  },

  async queue(batch, env) {
    await Promise.all(
      batch.messages.map(async (message) => {
        try {
          await runGame(env, message.body);
          message.ack();
        } catch (e) {
          console.error("game", message.body, e);
          if (message.attempts < MAX_ATTEMPTS) return message.retry({ delaySeconds: 10 });
          await failGame(env, message.body);
          message.ack();
        }
      }),
    );
  },
} satisfies ExportedHandler<Env, string>;
