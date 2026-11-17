# Downloadable beta local HTTP API

The ordinary GUI launch remains `127.0.0.1:8765`. IPv6 loopback (`--host ::1`) is also supported. No static asset contains an API secret.

## Request boundary

All served GET requests validate one Host header. Direct requests must name localhost/a loopback address on a loopback listener, or the explicitly bound host/destination interface on a network listener, using the listener's actual port. Other hostnames, wrong ports, malformed authorities, credentials, and duplicate Host headers are rejected. IPv6 authorities use brackets.

An Origin header, when present, must identify the same scheme, hostname, and effective port as the accepted request authority. `null`, unrelated origins, a different localhost port, and duplicate Origins are rejected. Browser fetch metadata must be `same-origin` or `none` when supplied; cross-site and same-site requests from a different origin are rejected. Forwarded headers never expand this boundary. No permissive CORS headers are emitted.

`GET /api/session` returns a cryptographically random token issued separately for each server instance. Its response is not cached, uses `nosniff`, and has a same-origin resource policy. The frontend fetches it once, keeps it in memory, and adds `X-NBA-GM-Token` to `GET /api/status` and both POST API routes. Failed bootstrap attempts can be retried; actions rejected after a server restart require reloading the GUI and are not replayed automatically. Static pages deny framing and use `nosniff`.

Non-browser HTTP clients may omit Origin/fetch metadata, but must fetch the session and supply its token too. This preserves CLI scripting through an explicit handshake while removing unauthenticated HTTP dispatch. The supported `nba-gm-data` CLI commands call the engine directly and require no HTTP token.

## JSON and backup limits

POST requests require a single `application/json` Content-Type with UTF-8 encoding and one non-negative decimal Content-Length. Chunked or content-encoded bodies are unsupported. Missing/duplicate/invalid lengths, malformed UTF-8/JSON, non-object envelopes or payloads, non-string/missing actions, non-finite JSON constants, and incomplete/timed-out bodies are rejected before dispatch. Connections have a 30-second socket inactivity timeout.

Ordinary bodies are limited to 1 MiB. An explicit `X-NBA-GM-Backup-Upload: 1` header on `/api/action` permits at most `4 * ceil(MAX_ARCHIVE_BYTES / 3) + 1 MiB` (180,005,548 bytes), allowing a legitimate 128 MiB compressed backup to fit after base64 expansion and its JSON envelope. Requests above these wire limits are rejected from their headers before waiting for body data. Bodies above the ordinary limit can dispatch only `restore_save`; multiplayer and ordinary game actions cannot use the larger allowance. The GUI adds the upload header only for restore. Existing recovery validation still enforces 128 MiB compressed, 512 MiB expanded, member inventory, checksums, and save/history integrity.

## Save paths

HTTP path checks run before local action dispatch, including both `save_path` and `path` when supplied together. The action layer also uses the canonical resolver. Absolute paths within the configured directory, filenames relative to it, `saves/name.json`-style directory prefixes, and supported save-name/ID forms remain usable. Canonically resolved external absolute paths, traversal beyond the boundary, and symlink escapes are rejected, including missing destinations through symlinked parents.

Recovery/pending archives, retained lock files, and migration backup companions are checked for external symlink escapes too. Unsafe symlinked manifests/archives are skipped during listing without reading their targets. Existing history validation rejects symlinked history components. Creation and restore retain their filename normalization and collision behavior, including an existing destination that escapes through a symlink.

The configured save-directory path is canonicalized at server startup. An intentionally configured directory symlink selects its resolved directory as the boundary. Core CLI `new-save`, `save-status`, and `play --save` still accept explicitly chosen paths outside the GUI directory. To use such a save in the GUI, launch with an appropriate `--save-dir` or import its exported backup.

## Explicit network tests

`--host` still supports explicitly requested LAN/network listeners. Clients using the actual bound address and port need no extra origin option. A DNS/proxy/tunnel address requires a repeatable exact `--allowed-origin http(s)://HOST[:PORT]`; wildcards, credentials, and URL paths are rejected. A proxy must preserve the public Host header. The public-test launcher discovers and permits only its one generated tunnel origin, runs the API on loopback, and stops both processes on exit.

Use `--public-multiplayer-only` for friend tests. It blocks direct local game/save-management actions, hides local save lists, and removes local filesystem details from both GET and POST runtime status. Multiplayer's nested game-action route cannot invoke local save management or runtime status, even in ordinary mode. Multiplayer manager sessions, revision checks, and ownership rules remain in force.

A network listener without public-only mode deliberately exposes the ordinary game API to reachable clients. The issued token protects against hostile browser origins; it is not a user-account credential. Authorized local programs and clients able to access an explicitly exposed server can acquire it. Use private networks or an authenticated HTTPS proxy when stronger access control is required.

## Validation and remaining limits

All mutable fixtures are temporary. Regression coverage uses real HTTP requests and dispatch spies to prove hostile hosts/origins, absent/invalid tokens, malformed/framing/size failures, and escaped paths never reach action dispatch. It also exercises valid localhost authorities, IPv6, fresh sessions, startup, real save creation/loading, full-history export/restore/recovery, CLI external paths, multiplayer isolation, and an exact-origin tunnel launcher using a temporary fake tunnel process. The threaded recovery test now scopes its creation mocks around the whole pool so they cannot leak into later game tests.

Frontend checks execute transport/picker behavior in a mocked environment and retain the existing source checks. They do not replace a manual browser walkthrough. The tunnel-launch test checks orchestration with a fake tunnel and a real local server; it does not contact Cloudflare. No long season soak or real user-save mutation is part of this task.

Canonical containment assumes the local filesystem is not being maliciously changed between validation and file access. Descriptor-relative, race-resistant filesystem operations and protection against local malware are outside this boundary. Request limits apply per connection, not as a global memory/thread quota; the Python development server is still unsuitable as an unprotected public production service.

## Exact acceptance results — October 3, 2026

```sh
PYTHONPATH=src:tests python3 -m unittest test_api_security test_save_recovery test_save_persistence test_multiplayer test_fantasy_draft test_rollover_history test_foundation.DataFoundationTests.test_local_gui_server_serves_static_assets_and_json_actions test_foundation.DataFoundationTests.test_app_action_layer_creates_local_save_and_serves_core_payloads test_foundation.DataFoundationTests.test_random_team_default_creates_seeded_team_filename test_foundation.DataFoundationTests.test_gui_starting_five_auto_saves_real_slots_and_blocks_empty_manual_lineup test_foundation.DataFoundationTests.test_gui_roster_cutdown_can_be_completed_through_app_actions test_foundation.DataFoundationTests.test_gui_milestone_advance_uses_intermediate_ai_checkpoints test_foundation.DataFoundationTests.test_gui_advance_reuses_core_ai_result_without_duplicate_processing test_foundation.DataFoundationTests.test_cli_save_paths_remain_explicit_outside_gui_save_directory
```

**98 tests passed in 121.251 seconds; no failures, errors, or skips.** The new security suite accounts for 20 of these tests. Python 3.14.4 emitted SQLite ResourceWarnings from existing multiplayer connection handling; those warnings were not promoted to failures or changed in this focused task.

After the final malformed-authority parsing adjustment (rejecting empty query/fragment delimiters and junk after IPv6 brackets), the HTTP boundary suite was rerun:

```sh
PYTHONPATH=src:tests python3 -m unittest test_api_security
```

**20 tests passed in 12.784 seconds; no failures, errors, or skips.**

```sh
node --test tests/*.test.cjs
```

**80 tests passed; 0 failed, cancelled, skipped, or todo** (183.165209 ms). This includes 5 new transport behavior tests and the existing recovery-picker/frontend tests.

```sh
node --check src/nba_gm_data/gui/app.js
bash -n scripts/run_public_multiplayer_test.sh
python3 -m py_compile src/nba_gm_data/app_server.py src/nba_gm_data/app_actions.py src/nba_gm_data/multiplayer.py
```

Syntax checks passed. Repository whitespace validation with the bundled fallback Git's `diff --check` passed. The system Git could not run because the machine's Xcode license had not been accepted; no system configuration was changed.
