// Renders pokerbots.dev/top and pokerbots.dev/<login> in the homepage's style. Files in this
// directory (index.html, install, llms.txt) are served before this code runs.
interface Env {
  API: Fetcher;
}

interface Mode {
  rating: number;
  games: number;
  rank: number | null;
  ranked: number;
  won: number | null;
  curve: number[];
}

interface Row {
  login: string;
  rating: number;
  games: number;
  won: number | null;
}

const SITE = "https://pokerbots.dev";
const CACHE_SECONDS = 60;
const BLOCKS = "▁▂▃▄▅▆▇█";
const INSTALL = "$ curl -fsSL https://pokerbots.dev/install | sh";

const STYLE = `:root{--paper:#F4F3EF;--ink:#111111}*{box-sizing:border-box}html,body{margin:0;background:var(--paper);color:var(--ink)}
body{font-family:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;font-size:15px;line-height:1.7}
main{max-width:720px;margin:0 auto;padding:72px 20px 80px;display:flex;flex-direction:column;gap:48px}
section{display:flex;flex-direction:column;gap:12px}.label{margin:0;font-weight:700}
pre{margin:0;font:inherit;white-space:pre;overflow-x:auto}pre.cmd{background:var(--ink);color:var(--paper);padding:14px 16px}
a{color:var(--ink);text-underline-offset:3px}a:hover{background:var(--ink);color:var(--paper)}
@media (max-width:600px){body{font-size:13px}main{padding-top:48px}}`;

const esc = (text: string) => text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

function money(micro: number) {
  const cents = Math.round(micro / 10_000);
  const sign = cents > 0 ? "+" : cents < 0 ? "-" : "";
  return Math.abs(cents) < 100 ? `${sign}${Math.abs(cents)}¢` : `${sign}$${(Math.abs(cents) / 100).toFixed(2)}`;
}

const SPARK_WIDTH = 60;

// One line of block characters; long histories are averaged into SPARK_WIDTH buckets.
function spark(all: number[]) {
  if (all.length < 2) return "";
  const n = Math.min(SPARK_WIDTH, all.length);
  const points = Array.from({ length: n }, (_, i) => {
    const part = all.slice(Math.floor((i * all.length) / n), Math.floor(((i + 1) * all.length) / n));
    return part.reduce((a, b) => a + b, 0) / part.length;
  });
  const low = Math.min(...points), span = Math.max(...points) - low || 1;
  return points.map((p) => BLOCKS[Math.round(((p - low) / span) * (BLOCKS.length - 1))]).join("");
}

const section = (label: string, body: string, cls = "") => `<section><p class="label">${label}</p><pre${cls}>${body}</pre></section>`;

function page(title: string, description: string, path: string, sections: string[], script = "") {
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)}</title><meta name="description" content="${esc(description)}">
<meta property="og:title" content="${esc(title)}"><meta property="og:description" content="${esc(description)}">
<meta property="og:url" content="${SITE}${esc(path)}"><meta property="og:type" content="website"><meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>${STYLE}</style></head><body><main>${sections.join("")}</main>${script}</body></html>`;
}

const rankText = (m: Mode, minGames: number) => (m.rank ? `#${m.rank} of ${m.ranked}` : `unranked until ${minGames} games`);

function profile(p: { login: string; min_games: number; paper: Mode | null; live: Mode | null }) {
  const url = `${SITE}/${p.login}`;
  const best = (["paper", "live"] as const).map((k) => p[k]).find((m) => m?.rank);
  const summary = best ? `${rankText(best, p.min_games)}, rating ${best.rating}` : "rated poker for bots";
  const modes = (["paper", "live"] as const).filter((k) => p[k]).map((k) => {
    const m = p[k]!;
    const won = k === "live" && m.won !== null ? `   won ${money(m.won)}` : "";
    return section(k, `${rankText(m, p.min_games)}   rating ${m.rating}   games ${m.games}${won}\n${spark(m.curve)}`);
  });
  const post = `https://x.com/intent/post?text=${encodeURIComponent(`My poker bot on pokerbots.dev: ${summary}`)}&url=${encodeURIComponent(url)}`;
  const login = esc(p.login);
  return page(`${p.login} on pokerbots.dev`, `${p.login}: ${summary}. Rated poker for bots.`, `/${p.login}`, [
    section(login, `<a href="https://github.com/${login}">github.com/${login}</a>`),
    ...(modes.length ? modes : [section("games", "no games yet")]),
    section("share", [
      `<a href="${esc(post)}">post on x</a>`,
      `<a href="https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}">post on linkedin</a>`,
      `<a href="${esc(url)}" id="copy">copy link</a>`,
    ].join("\n")),
    section("install", INSTALL, ' class="cmd"'),
    section("leaderboard", `<a href="/top">pokerbots.dev/top</a>`),
  ], `<script>document.getElementById("copy").onclick=e=>{e.preventDefault();navigator.clipboard.writeText(location.href);e.target.textContent="copied"}</script>`);
}

function boardTable(rows: Row[], live: boolean, minGames: number) {
  if (!rows.length) return `no bots with ${minGames} games yet`;
  const width = Math.max(4, ...rows.map((r) => r.login.length));
  const head = `rank  ${"user".padEnd(width)}  rating  games${live ? "  won" : ""}`;
  const lines = rows.map((r, i) => {
    const name = `<a href="/${esc(r.login)}">${esc(r.login)}</a>${" ".repeat(width - r.login.length)}`;
    return `${String(i + 1).padEnd(4)}  ${name}  ${String(r.rating).padEnd(6)}  ${String(r.games).padEnd(5)}${live && r.won !== null ? `  ${money(r.won)}` : ""}`;
  });
  return [head, ...lines].join("\n");
}

function top(t: { min_games: number; paper: Row[]; live: Row[] }) {
  return page("pokerbots.dev leaderboard", "Rated poker for bots: the top bots on paper and live.", "/top", [
    section("paper", boardTable(t.paper, false, t.min_games)),
    section("live", boardTable(t.live, true, t.min_games)),
    section("install", INSTALL, ' class="cmd"'),
  ]);
}

const missing = () =>
  new Response(page("pokerbots.dev", "Rated poker for bots.", "/", [section("not found", `<a href="/">pokerbots.dev</a>`)]), {
    status: 404,
    headers: { "content-type": "text/html; charset=utf-8" },
  });

async function render(req: Request, env: Env) {
  const path = new URL(req.url).pathname.replace(/\/+$/, "") || "/";
  const login = path.slice(1);
  if (path === "/top") return top(await (await env.API.fetch(`${SITE}/public/top`)).json());
  if (!/^[A-Za-z0-9-]{1,39}$/.test(login)) return null;
  const res = await env.API.fetch(`${SITE}/public/players/${login}`);
  return res.ok ? profile(await res.json()) : null;
}

export default {
  async fetch(req, env, ctx) {
    if (req.method !== "GET") return missing();
    const cache = caches.default;
    const hit = await cache.match(req);
    if (hit) return hit;
    const html = await render(req, env);
    if (!html) return missing();
    const res = new Response(html, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": `public, max-age=${CACHE_SECONDS}` } });
    ctx.waitUntil(cache.put(req, res.clone()));
    return res;
  },
} satisfies ExportedHandler<Env>;
