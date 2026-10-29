// Operator controls: pause switches and account suspension.
import type { User } from "./auth";
import type { Env } from "./env";
import { HttpError } from "./http";

export const SWITCHES = ["live", "deposits", "withdrawals"] as const;
export type Switch = (typeof SWITCHES)[number];

export async function paused(env: Env): Promise<Switch[]> {
  const { results } = await env.DB.prepare("SELECT key FROM settings WHERE key LIKE 'pause:%' AND value = '1'").all<{ key: string }>();
  return results.map((r) => r.key.slice("pause:".length) as Switch);
}

export async function setPaused(env: Env, what: Switch, on: boolean) {
  await env.DB.prepare("INSERT INTO settings VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value")
    .bind(`pause:${what}`, on ? "1" : "0").run();
}

export async function requireRunning(env: Env, what: Switch) {
  if ((await paused(env)).includes(what)) throw new HttpError(503, `${what} paused for maintenance`);
}

// Suspended users can still log in, see their games and withdraw; nothing else.
export function requireActive(user: User & { suspended_at?: string | null }) {
  if (user.suspended_at) throw new HttpError(403, "account suspended: hello@pokerbots.dev");
}
