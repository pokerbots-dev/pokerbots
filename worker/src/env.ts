import type { Runner } from "./runner";

export interface Env {
  DB: D1Database;
  BOTS: R2Bucket;
  GAMES: Queue<string>;
  RUNNER: DurableObjectNamespace<Runner>;
  SOLANA_CLUSTER: "devnet" | "mainnet-beta";
  SOLANA_RPC_URL: string; // secret: contains the Helius API key
  HOT_WALLET_KEY: string; // secret: JSON array of 64 bytes
  USDC_MINT: string;
  WITHDRAW_USER_DAILY_CAP: string; // dollars
  WITHDRAW_TOTAL_DAILY_CAP: string; // dollars
  ACCESS_TEAM: string;
  ACCESS_AUD: string;
  EMAIL?: SendEmail;
  ALERT_EMAIL?: string; // secret: where alerts go (a verified Email Routing destination)
}

export const SEATS = 6;
export const BUY_IN = 100_000; // USDC micro-units: 10¢
export const PRIZES = [370_000, 200_000];
export const RAKE = SEATS * BUY_IN - PRIZES.reduce((a, b) => a + b);
export const PAPER_GAMES_PER_DAY = 1000;
export const GAMES_PER_MINUTE = 5;
export const ATTEST_VERSION = 1; // bump when the 18+/location wording changes; everyone is asked again
export const MAX_BOT_BYTES = 1 << 20;
export const RUNNERS = 10;

export const dollars = (text: string) => Math.round(Number(text) * 1_000_000);
