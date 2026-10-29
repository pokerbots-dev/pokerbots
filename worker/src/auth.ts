import type { Env } from "./env";
import { HttpError } from "./http";

export interface User {
  id: number;
  login: string;
  wallet: string | null;
  attested_at: string | null;
}

const SESSION_SECONDS = 3600;

const bytes = (b64url: string) =>
  Uint8Array.from(atob(b64url.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));

async function sha256(text: string) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function authenticate(req: Request, env: Env): Promise<User> {
  const token = req.headers.get("authorization")?.match(/^Bearer (.+)$/)?.[1];
  if (!token) throw new HttpError(401, "not logged in: pb login");
  const hash = await sha256(token);
  const now = Math.floor(Date.now() / 1000);
  const cached = await env.DB.prepare(
    "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ?",
  ).bind(hash, now).first<User>();
  if (cached) return cached;

  const res = await fetch("https://api.github.com/user", {
    headers: { authorization: `Bearer ${token}`, "user-agent": "pokerbots.dev", accept: "application/vnd.github+json" },
  });
  if (!res.ok) throw new HttpError(401, "login expired: pb login");
  const github = await res.json<{ id: number; login: string }>();
  const user = (await env.DB.prepare(
    "INSERT INTO users (github_id, login) VALUES (?, ?) ON CONFLICT (github_id) DO UPDATE SET login = excluded.login RETURNING *",
  ).bind(github.id, github.login).first<User>())!;
  await env.DB.prepare("INSERT OR REPLACE INTO sessions VALUES (?, ?, ?)").bind(hash, user.id, now + SESSION_SECONDS).run();
  return user;
}

// Admin routes sit behind a Cloudflare Access application; verify the JWT it adds.
export async function authenticateAdmin(req: Request, env: Env): Promise<void> {
  const [header, payload, signature] = (req.headers.get("cf-access-jwt-assertion") ?? "").split(".");
  if (!signature) throw new HttpError(403, "forbidden");
  const { kid } = JSON.parse(new TextDecoder().decode(bytes(header)));
  const claims = JSON.parse(new TextDecoder().decode(bytes(payload)));
  const certs = await fetch(`https://${env.ACCESS_TEAM}.cloudflareaccess.com/cdn-cgi/access/certs`);
  const { keys } = await certs.json<{ keys: (JsonWebKey & { kid: string })[] }>();
  const jwk = keys.find((k) => k.kid === kid);
  const algorithm = { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" };
  const valid =
    jwk &&
    (await crypto.subtle.verify(
      algorithm.name,
      await crypto.subtle.importKey("jwk", jwk, algorithm, false, ["verify"]),
      bytes(signature),
      new TextEncoder().encode(`${header}.${payload}`),
    ));
  if (!valid || ![claims.aud].flat().includes(env.ACCESS_AUD) || claims.exp < Date.now() / 1000) {
    throw new HttpError(403, "forbidden");
  }
}
