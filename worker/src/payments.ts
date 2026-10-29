// Deposits: we build a USDC transfer from the user's wallet, sign as fee payer, the user
// co-signs locally, and we credit once confirmed. Our fee-payer signature is the
// transaction id, so the user cannot alter what we built.
// Withdrawals: debited on request, sent within daily caps (else held for an admin), and
// refunded if the transfer fails. A signature is stored before broadcast so nothing is
// ever sent twice.
import { address } from "@solana/kit";
import type { User } from "./auth";
import { BUY_IN, dollars, type Env } from "./env";
import { HttpError, amount as checkAmount } from "./http";
import { credit } from "./ledger";
import { chain, send, signatureOf, status, transfer, type Chain } from "./solana";

interface Deposit {
  signature: string;
  user_id: number;
  amount: number;
  last_valid: number;
}

interface Withdrawal extends Deposit {
  id: string;
  address: string;
  status: string;
}

const CONFIRM_POLLS = 20;
const POLL_MS = 1500;

function wallet(user: User) {
  if (!user.wallet) throw new HttpError(400, "no wallet: pb wallet");
  return address(user.wallet);
}

export async function prepareDeposit(env: Env, user: User, value: unknown) {
  const amount = checkAmount(value, BUY_IN);
  const c = await chain(env);
  const tx = await transfer(c, wallet(user), c.hot.address, amount);
  await env.DB.prepare("INSERT INTO deposits (signature, user_id, amount, last_valid, status) VALUES (?, ?, ?, ?, 'prepared')")
    .bind(tx.signature, user.id, amount, tx.lastValid).run();
  return { signature: tx.signature, transaction: tx.wire };
}

export async function submitDeposit(env: Env, user: User, signature: string, wire: string) {
  if (signatureOf(wire) !== signature) throw new HttpError(400, "transaction does not match");
  const deposit = await env.DB.prepare(
    "UPDATE deposits SET status = 'sent' WHERE signature = ? AND user_id = ? AND status = 'prepared' RETURNING *",
  ).bind(signature, user.id).first<Deposit>();
  if (!deposit) throw new HttpError(404, "unknown deposit");
  const c = await chain(env);
  await send(c, wire).catch(async (e) => {
    await env.DB.prepare("UPDATE deposits SET status = 'failed' WHERE signature = ?").bind(signature).run();
    throw new HttpError(400, `rejected by Solana: ${e.cause?.message ?? e.message}`);
  });
  for (let i = 0; i < CONFIRM_POLLS; i++) {
    const result = await settleDeposit(env, c, deposit);
    if (result !== "sent") return { status: result, amount: deposit.amount };
    await new Promise((r) => setTimeout(r, POLL_MS));
  }
  return { status: "sent", amount: deposit.amount };
}

async function settleDeposit(env: Env, c: Chain, d: Deposit) {
  const s = await status(c, d.signature, d.last_valid);
  if (s === "pending") return "sent";
  const next = s === "confirmed" ? "credited" : "failed";
  const update = env.DB.prepare("UPDATE deposits SET status = ? WHERE signature = ?").bind(next, d.signature);
  await env.DB.batch(s === "confirmed" ? [credit(env, d.user_id, "deposit", d.amount, d.signature), update] : [update]);
  return next;
}

export async function requestWithdrawal(env: Env, user: User, value: unknown) {
  const amount = checkAmount(value, BUY_IN);
  const to = wallet(user);
  const id = crypto.randomUUID();
  const counted = "status IN ('approved', 'sent', 'done') AND created_at >= date('now')";
  const [inserted] = await env.DB.batch([
    env.DB.prepare(
      `INSERT INTO withdrawals (id, user_id, amount, address, status)
       SELECT ?1, ?2, ?3, ?4, CASE WHEN
         (SELECT COALESCE(SUM(amount), 0) FROM withdrawals WHERE user_id = ?2 AND ${counted}) + ?3 <= ?5 AND
         (SELECT COALESCE(SUM(amount), 0) FROM withdrawals WHERE ${counted}) + ?3 <= ?6
       THEN 'approved' ELSE 'pending' END
       WHERE (SELECT COALESCE(SUM(amount), 0) FROM ledger WHERE user_id = ?2) >= ?3`,
    ).bind(id, user.id, amount, to, dollars(env.WITHDRAW_USER_DAILY_CAP), dollars(env.WITHDRAW_TOTAL_DAILY_CAP)),
    env.DB.prepare("INSERT INTO ledger (user_id, kind, amount, ref) SELECT user_id, 'withdrawal', -amount, id FROM withdrawals WHERE id = ?").bind(id),
  ]);
  if (!inserted.meta.changes) throw new HttpError(400, "insufficient balance");
  return { id, amount, status: await sendWithdrawal(env, id) };
}

export async function sendWithdrawal(env: Env, id: string, c?: Chain) {
  const w = await env.DB.prepare("SELECT * FROM withdrawals WHERE id = ?").bind(id).first<Withdrawal>();
  if (!w || w.status !== "approved") return w?.status;
  c ??= await chain(env);
  const tx = await transfer(c, c.hot.address, address(w.address), w.amount);
  const claimed = await env.DB.prepare(
    "UPDATE withdrawals SET status = 'sent', signature = ?, last_valid = ? WHERE id = ? AND status = 'approved'",
  ).bind(tx.signature, tx.lastValid, id).run();
  if (claimed.meta.changes) await send(c, tx.wire).catch((e) => console.error("withdrawal send", id, e));
  return "sent";
}

export function refundWithdrawal(env: Env, id: string, from: string, to: string) {
  return env.DB.batch([
    env.DB.prepare("UPDATE withdrawals SET status = ? WHERE id = ? AND status = ?").bind(to, id, from),
    env.DB.prepare(
      "INSERT OR IGNORE INTO ledger (user_id, kind, amount, ref) SELECT user_id, 'refund', amount, 'w:' || id FROM withdrawals WHERE id = ? AND status = ?",
    ).bind(id, to),
  ]);
}

export async function reconcile(env: Env) {
  const c = await chain(env);
  const rows = async <T>(sql: string) => (await env.DB.prepare(sql).all<T>()).results;
  for (const d of await rows<Deposit>("SELECT * FROM deposits WHERE status = 'sent'")) await settleDeposit(env, c, d);
  await env.DB.prepare("UPDATE deposits SET status = 'failed' WHERE status = 'prepared' AND created_at < datetime('now', '-10 minutes')").run();
  for (const w of await rows<Withdrawal>("SELECT * FROM withdrawals WHERE status = 'approved'")) await sendWithdrawal(env, w.id, c);
  for (const w of await rows<Withdrawal>("SELECT * FROM withdrawals WHERE status = 'sent'")) {
    const s = await status(c, w.signature, w.last_valid);
    if (s === "confirmed") await env.DB.prepare("UPDATE withdrawals SET status = 'done' WHERE id = ?").bind(w.id).run();
    if (s === "failed") await refundWithdrawal(env, w.id, "sent", "failed");
  }
}
