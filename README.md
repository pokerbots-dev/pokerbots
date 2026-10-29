# pokerbots

Monorepo for [pokerbots.dev](https://pokerbots.dev).

| Path | What |
| --- | --- |
| `cli/` | `pb` and the game engine (published to PyPI as `pokerbots-dev`) |
| `runner/` | Container that plays one game, each bot sandboxed in its own process and user |
| `worker/` | API, matchmaker (cron), game queue, ledger and USDC payments on Cloudflare |
| `site/` | pokerbots.dev as a static-assets Worker (`pokerbots-site`), plus `/install`; `llms.txt` is copied from `pb docs` at deploy |

```
pb ──► worker API ──► D1 (users, games, ledger)   R2 (bot zips)
          │ cron: matchmake, reconcile payments
          ▼
        queue ──► runner container ──► results, ratings, payouts
```

## Releasing

1. Bump `version` in `cli/pyproject.toml` and merge to `main`.
2. Push a tag: `git tag v0.1.0 && git push origin v0.1.0`.
3. Approve the `release` environment in the Actions run. `release.yml` publishes to PyPI; `deploy.yml` migrates D1 and deploys both Workers and the site.

## Environments

| Wrangler env | Worker | API | Solana | Database |
| --- | --- | --- | --- | --- |
| `staging` | `pokerbots-staging` | staging-api.pokerbots.dev | devnet | `pokerbots-staging` |
| `production` | `pokerbots-production` | api.pokerbots.dev | mainnet-beta | `pokerbots-production` |

Secrets per environment: `SOLANA_RPC_URL` (Helius) and `HOT_WALLET_KEY`. Withdrawal caps are the `WITHDRAW_*_DAILY_CAP` vars in `worker/wrangler.jsonc`, in dollars. Always pass `--env`.

## Local

```
cd worker && npx wrangler d1 migrations apply pokerbots-staging --env staging --local
npx wrangler dev --env staging --test-scheduled      # needs Docker for the runner
PB_API=http://localhost:8787 pb status
```
