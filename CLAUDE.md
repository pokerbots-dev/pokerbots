# pokerbots.dev

- `SPEC.md` is the source of truth. Build only what it describes; if something is ambiguous, ask instead of guessing.
- `site/index.html` is the finished homepage. Deploy it as-is to Cloudflare Pages; change it only when asked.
- `site/STYLE.md` defines the visual and writing style for the homepage and the `pb` TUI.
- Start with build-order step 1 in `SPEC.md` (§23), and prototype the runner sandbox and 20 ms timing on Cloudflare Containers early.
- Never commit secrets, keys or `.env` files; Cloudflare secrets are set with `wrangler secret put`.
