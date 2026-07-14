---
type: quality
status: current
reviewed: 2026-07-10
tags:
  - quality/security
  - quality/privacy
  - project/nba-gm
---

# Security And Privacy Boundaries

## Current Threat Model

The game is designed for local, single-user execution on a trusted machine. The GUI server binds to loopback by default and has no authentication. Save files and optional Ollama prompts remain local.

This is acceptable only while the service remains local and trusted. It is not a secure hosted multi-user architecture.

## Local HTTP Server

[app_server.py](../../../src/nba_gm_data/app_server.py) uses Python's `ThreadingHTTPServer` to serve static assets and dispatch actions. It includes path handling to prevent static traversal and sends development-friendly no-store headers.

Python explicitly warns that `http.server` is not recommended for production hosting; see [http.server documentation](https://docs.python.org/3.11/library/http.server.html).

Before any remote/network exposure:

- add authentication and authorization;
- use a production HTTP server and TLS;
- validate request size/type;
- restrict file paths and save IDs;
- add CSRF/origin controls;
- avoid returning local filesystem paths;
- isolate users and saves;
- rate-limit expensive simulation/narrative actions;
- audit logs without leaking personal paths.

## Save Files

Saves can contain user team choice, settings, and local narrative content but no account credentials. Risks are integrity and accidental overwrite more than confidentiality. Use atomic writes, backups, schema validation, and import sanitization before broad sharing.

Never let imported JSON select arbitrary output paths or commands.

## Ollama

The default Ollama URL is local. Context packets include simulated player/team data and event history. They should not include unrelated filesystem content or personal information. If users configure a remote Ollama-compatible endpoint, the UI should warn that packets leave the machine.

Generated model output is untrusted input. Strict JSON parsing, length limits, allowed enums, fact validation, and escaped text rendering are security as well as quality controls.

## Subprocesses And ffmpeg

ffmpeg paths and arguments should be passed as argument arrays without a shell. User-controlled video paths must not become shell fragments. Cache output stays inside expected app directories.

## Frontend Rendering

Generated narrative and imported save text must use safe text nodes/escaping rather than raw `innerHTML` unless explicitly sanitized. An LLM can emit HTML-like text even when not asked.

## Dependencies And Supply Chain

The dependency-light runtime reduces package supply-chain surface, but optional external binaries/models and downloaded loading assets still need integrity and source documentation. A release should publish checksums for large asset archives.

## Data And Licensing

Security is not the same as licensing. Public player data, team logos, and highlight footage may have terms or rights restrictions even in a private alpha. A public release should audit every distributed asset and source.

## Platform Packaging

An embedded iOS/macOS app needs app sandbox-compliant storage, no arbitrary executable downloads, and a clear policy for Ollama (which cannot simply run as an iPhone background service). The standalone iPhone product may need narrative fallback or an embedded on-device model strategy separate from desktop Ollama.

## Related Notes

- [[Architecture/Action Boundary and Local GUI]]
- [[Product/External Software and Packages]]
- [[Roadmap/Release Readiness]]

