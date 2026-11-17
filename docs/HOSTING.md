# Hosting The Multiplayer Alpha

## Fastest Friend Test: Cloudflare Quick Tunnel

For testing from different networks today, use the included public-test launcher. Cloudflare Quick Tunnels create a random HTTPS `trycloudflare.com` URL without requiring an account.

```bash
brew install cloudflared
./scripts/run_public_multiplayer_test.sh
```

The launcher:

1. Starts the game on an available loopback port (or `NBA_GM_PORT` when set).
2. Enables `--public-multiplayer-only`.
3. Hides the host's local save list.
4. Rejects direct single-player API mutations.
5. Exposes the multiplayer GUI through HTTPS.
6. Stops both processes when the host presses `Ctrl-C`.

The launcher discovers the exact tunnel URL before starting the API and passes
it as `--allowed-origin`. Other tunnel hostnames are rejected. The server stays
bound to loopback, and forwarded Host/Origin headers do not bypass validation.
The browser acquires its protection token from the running server automatically.

Quick Tunnels are explicitly a testing tool. They have no uptime guarantee, use a random URL, and currently impose a 200 concurrent in-flight request limit. The game uses ordinary HTTP polling rather than SSE, so that limitation is acceptable for a small test league.

- [Cloudflare Quick Tunnels](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/)
- [Cloudflare Tunnel setup](https://developers.cloudflare.com/tunnel/setup/)

## Recommendation

For a persistent private friend league, use **one always-on VM** or an always-on home Mac. Keep the Python server, SQLite coordination database, and JSON saves on one persistent disk. Put HTTPS in front of it and back up the `saves/` directory.

Best no-monthly-cost cloud candidate: **Oracle Cloud Always Free Compute**, if capacity is available. It provides a normal VM, which fits long simulations and persistent authoritative state better than serverless functions.

Best zero-infrastructure private test: run the server on an always-on Mac and expose it only to invited friends through a private-network tool such as Tailscale. This avoids making the development HTTP server publicly reachable.

## Why Not Vercel As The Whole Backend?

Vercel is attractive for the static frontend, and its current platform can expose Python functions and WebSockets. It is still a poor fit for this authoritative simulation backend:

- Hobby functions have bounded execution duration; a long season rollover or soak-like operation can exceed a serverless request window.
- Function instances are disposable and may run concurrently.
- SQLite and JSON saves require a persistent, single-authority storage/locking strategy that Vercel functions do not provide.
- A Vercel deployment would therefore still need an external Postgres/Redis/object-storage architecture and a careful job system.

Vercel can become a good frontend host after the API base URL is configurable, while the Python engine runs elsewhere.

References:

- [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)
- [Vercel function limits](https://vercel.com/docs/functions/limitations)
- [Vercel WebSocket guidance](https://vercel.com/kb/guide/do-vercel-serverless-functions-support-websocket-connections)

## Other Free Options

### Render Free Web Service

Useful for disposable previews. It supports Python and WebSockets, but free services spin down when idle and the filesystem is ephemeral. A free database also has lifecycle limits. Do not keep the only copy of a dynasty there.

- [Render free instances](https://render.com/docs/free)
- [Render WebSockets](https://render.com/docs/websocket)

### Supabase Free Database

Useful as a later Postgres/realtime backend. The free tier is enough for small lobby metadata and event feeds, but the current code would need a `MultiplayerStore` Postgres adapter and versioned save snapshot storage. Supabase does not remove the need for somewhere to run the Python simulation.

- [Supabase billing and free quotas](https://supabase.com/docs/guides/platform/billing-on-supabase)

### Oracle Cloud Always Free

Architecturally the best free cloud match because it is a conventional VM. Availability can be inconsistent, and operating the VM, HTTPS, updates, and backups becomes our responsibility.

- [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/)

## Private Alpha Deployment Checklist

1. Provision one Linux VM with persistent storage.
2. Clone the repo and install Python 3.11+.
3. Create a dedicated unprivileged service user.
4. Install the package in a virtual environment.
5. Run `nba-gm-data-gui --root /srv/nba-gm --host 127.0.0.1 --port 8765 --public-multiplayer-only --allowed-origin https://YOUR-EXACT-HOSTNAME`.
6. Put Caddy or nginx in front for HTTPS.
7. Restrict firewall access to ports 80/443.
8. Back up `/srv/nba-gm/saves` after every league window.
9. Use one app process for the SQLite alpha.
10. Test restore of the database and save files before inviting friends.

Preserve the original public `Host` header in the proxy. Allow only the exact
external origins you intend to serve; `--allowed-origin` accepts no wildcards.
See [local API security](LOCAL_API_SECURITY.md) for transport requirements and
the limits of the browser-protection token.

## Scale-Up Path

When the alpha proves fun enough to justify more engineering:

1. Add user accounts and recoverable sessions.
2. Implement a Postgres `MultiplayerStore`.
3. Store immutable, versioned save snapshots in object storage.
4. Add a job queue for long simulation windows.
5. Replace polling with WebSocket/SSE event delivery while preserving durable event cursors.
6. Run multiple API instances only after adding distributed per-league locking.
