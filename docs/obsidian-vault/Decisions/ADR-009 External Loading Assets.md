---
type: adr
status: accepted
decision: external-loading-assets
reviewed: 2026-07-10
tags:
  - decision/assets
  - ux/loading
  - distribution
---

# ADR-009: External Loading Assets

## Context

The preferred 30-minute highlight source video is roughly 380 MB, exceeding GitHub's 100 MB normal-file limit. Friends should still be able to install the complete loading experience without manually configuring paths.

## Decision

Keep source code and small metadata/caches in the repository, distribute the large loading-video/archive separately (for example through a GitHub Release), and provide an installer command. Animation remains optional and falls back gracefully.

## Why

- normal Git clones stay manageable;
- pushes are not rejected;
- users who do not want the asset are not forced to download it;
- asset versions can be replaced independently;
- tests can use small fixture videos/caches.

## Alternatives

### Git LFS

Purpose-built for large files and valid, but every clone/user needs LFS behavior and bandwidth/storage management. It may be appropriate if asset versioning becomes central.

### Commit The Video Directly

Not possible under normal GitHub limits and harmful to repository size/history.

### Stream A Remote Video

Avoids local storage but adds network dependence, decoding latency, availability, and likely rights concerns.

### Remove The Highlight Animation

Simplifies distribution but loses a distinctive loading experience. The optional fallback already covers constrained installs.

## Consequences

Positive:

- friend-friendly opt-in installation;
- repository remains source-focused;
- gameplay is not blocked by assets.

Negative:

- release/install workflow must be maintained;
- checksums/version compatibility are needed;
- public distribution requires a licensing audit;
- missing assets can make first-run experience less polished.

## Evidence

The repository includes loading-asset install tests and `animation.py` cache/source selection. GitHub rejected the original 380 MB file with GH001.

## Revisit When

- public release requires fully licensed assets;
- app-store packaging has a better on-demand resource mechanism;
- Git LFS becomes easier than release archives for the target audience.

## Related

- [[Systems/Loading Animation]]
- [[Product/External Software and Packages]]

