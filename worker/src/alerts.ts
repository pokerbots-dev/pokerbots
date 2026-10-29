import { EmailMessage } from "cloudflare:email";
import type { Env } from "./env";
import { chain, hotBalances } from "./solana";

const LOW_SOL = 0.05;
const FAILED_GAMES_PER_HOUR = 5;
const REPEAT_SECONDS = 6 * 3600;
const FROM = "alerts@pokerbots.dev";

const usd = (micro: number) => `$${(micro / 1e6).toFixed(2)}`;

async function problems(env: Env): Promise<[string, string][]> {
  const one = (sql: string) => env.DB.prepare(sql).first<number>("n").then((n) => n ?? 0);
  const [owed, pending, failedGames, failedWithdrawals, hot] = await Promise.all([
    one("SELECT COALESCE(SUM(amount), 0) AS n FROM ledger WHERE user_id IS NOT NULL"),
    one("SELECT COUNT(*) AS n FROM withdrawals WHERE status = 'pending'"),
    one("SELECT COUNT(*) AS n FROM games WHERE status = 'failed' AND created_at >= datetime('now', '-1 hour')"),
    one("SELECT COUNT(*) AS n FROM withdrawals WHERE status = 'failed' AND created_at >= datetime('now', '-1 day')"),
    chain(env).then(hotBalances),
  ]);
  const found: [string, string][] = [];
  if (hot.sol < LOW_SOL) found.push(["low-sol", `Hot wallet has ${hot.sol} SOL. Deposits and withdrawals fail without SOL for fees.`]);
  if (hot.usdc < owed) found.push(["short-usdc", `Hot wallet holds ${usd(hot.usdc)} USDC but users are owed ${usd(owed)}.`]);
  if (pending) found.push(["pending-withdrawals", `${pending} withdrawal(s) over the daily caps wait for: pb admin withdrawals`]);
  if (failedGames >= FAILED_GAMES_PER_HOUR) found.push(["failed-games", `${failedGames} games failed in the last hour; check the runner logs.`]);
  if (failedWithdrawals) found.push(["failed-withdrawals", `${failedWithdrawals} withdrawal(s) failed on-chain in the last day and were refunded.`]);
  return found;
}

// Emails each problem at most once per REPEAT_SECONDS.
export async function checkAlerts(env: Env) {
  const now = Math.floor(Date.now() / 1000);
  for (const [key, text] of await problems(env)) {
    const due = await env.DB.prepare(
      "INSERT INTO alerts VALUES (?1, ?2) ON CONFLICT (key) DO UPDATE SET sent_at = ?2 WHERE sent_at < ?2 - ?3 RETURNING key",
    ).bind(key, now, REPEAT_SECONDS).first();
    if (due) await send(env, `${key} (${env.SOLANA_CLUSTER})`, text);
  }
}

async function send(env: Env, subject: string, text: string) {
  console.error("alert", subject, text);
  if (!env.EMAIL || !env.ALERT_EMAIL) return;
  const raw = [
    `From: pokerbots <${FROM}>`,
    `To: ${env.ALERT_EMAIL}`,
    `Subject: pokerbots alert: ${subject}`,
    `Message-ID: <${crypto.randomUUID()}@pokerbots.dev>`,
    `Date: ${new Date().toUTCString()}`,
    "Content-Type: text/plain; charset=utf-8",
    "",
    text,
  ].join("\r\n");
  await env.EMAIL.send(new EmailMessage(FROM, env.ALERT_EMAIL, raw));
}
