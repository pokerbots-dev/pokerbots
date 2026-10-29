// Every balance is the sum of its ledger rows (USDC micro-units). Rows are unique by
// (kind, ref), so every write is idempotent and safe to retry.
import type { Env } from "./env";

export type Kind = "deposit" | "buyin" | "payout" | "rake" | "refund" | "withdrawal";

export const balanceOf = (column: string) => `(SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE user_id = ${column})`;

export async function balance(env: Env, userId: number): Promise<number> {
  return (await env.DB.prepare(`SELECT ${balanceOf("?")} AS b`).bind(userId).first<number>("b"))!;
}

export function credit(env: Env, userId: number | null, kind: Kind, amount: number, ref: string) {
  return env.DB.prepare("INSERT OR IGNORE INTO ledger (user_id, kind, amount, ref) VALUES (?, ?, ?, ?)").bind(userId, kind, amount, ref);
}

export function debit(env: Env, userId: number, kind: Kind, amount: number, ref: string) {
  return env.DB.prepare(
    `INSERT OR IGNORE INTO ledger (user_id, kind, amount, ref) SELECT ?1, ?2, -?3, ?4 WHERE ${balanceOf("?1")} >= ?3`,
  ).bind(userId, kind, amount, ref);
}
