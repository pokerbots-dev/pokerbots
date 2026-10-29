# pokerbots

Monorepo for [pokerbots.dev](https://pokerbots.dev).

| Path | What |
| --- | --- |
| `cli/` | `pb`, the command-line client (published to PyPI as `pokerbots-dev`) |
| `worker/` | Cloudflare Workers backend (deployed by `.github/workflows/deploy.yml`) |

## Releasing

1. Bump `version` in `cli/pyproject.toml` and merge to `main`.
2. Push a tag: `git tag v0.1.0 && git push origin v0.1.0`.
3. Approve the `release` environment in the Actions run. `release.yml` publishes to PyPI via trusted publishing; `deploy.yml` deploys to Cloudflare.
