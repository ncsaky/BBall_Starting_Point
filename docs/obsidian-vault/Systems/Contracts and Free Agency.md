---
type: system
status: current
reviewed: 2026-07-10
tags:
  - system/contracts
  - gameplay/free-agency
  - project/nba-gm
---

# Contracts And Free Agency

## Responsibility

[contract_ai.py](../../../src/nba_gm_data/contract_ai.py) estimates contract markets, player asks, walkaway prices, preferences, offers, negotiation outcomes, and legality. [save.py](../../../src/nba_gm_data/save.py) coordinates extension windows, AI extension timing, free-agency days, signings, released-player markets, and season transitions.

## Contract Market Model

The model combines:

- player role tier;
- on-court and asset valuation;
- comparable contracts;
- age and expected future production;
- team role and fit;
- winning, market, continuity, and player preference;
- salary cap and hard-cap room;
- negotiation leverage and deterministic personality.

It intentionally models a practical v1 market rather than every exception in the NBA collective bargaining agreement.

## Role Tiers

Role tiers prevent low-minute players with one inflated feature from receiving star asks. Broad categories distinguish franchise/star talent, high-end starters, regular starters, rotation players, depth, prospects, and replacement players. Market comps are filtered through role and current context rather than copied blindly.

## Extensions

An extension has three distinct states:

1. **Exploration:** the user chooses years and offer amount while cap room updates.
2. **Negotiation:** player interest, leverage, and threshold determine response.
3. **Application:** only explicit confirmation writes the future contract, transaction log, league event, and news.

Canceling at any point should leave no pending negotiation, contract override, event, or log behind.

The extension override must append future seasons while preserving the current season. An earlier bug replaced the whole salary table and erased the active year's value. This is a textbook distinction between updating one temporal slice and replacing an aggregate.

## Retirement Safety

Retirement risk must be considered before an accepted-looking negotiation result. A player expected to retire before or during the proposed years should have the offer blocked or capped with an explicit explanation. Offseason retirements should occur before re-signing/free agency opportunities that would otherwise create impossible contracts.

## AI Extensions

AI teams prioritize extension-eligible players by team role, ability, minutes, future importance, age, price, production, fit, team direction, and player willingness.

- Core players are usually protected as assets unless the player refuses.
- Replaceable depth is usually allowed to reach the market.
- Important middle-tier players depend more on price, age, fit, development, and record.
- Older players receive more caution on term and timing.
- Not every extension should happen on opening day; lower-priority talks can respond to in-season production and team direction.
- A valuable veteran who will not extend on a struggling team can request a trade, creating a factual league event and a rational AI trade motive.

Volume matters, but the target should emerge from decision rules rather than forced random signings.

## Free Agency

Teams submit and resolve offers over days. The system considers ask, role, cap legality, roster need, team quality, timeline, market, and preference. AI activity may include:

- clearing cap space before resolving a priority target;
- signing a market player;
- pursuing a similar trade target after losing a bidding war;
- signing a strong player released in-season by the user.

Free-agency movement lists should show each signing coherently without stale duplicate recaps. The final period can show the complete movement history.

## Released Players

A manually cut player enters the save's free-agent pool with release metadata. On the next pre-deadline advancement, a meaningful player can sign a one-year current-season deal with the best legal AI destination based on role, cap, quality, age timeline, position, and deterministic preference noise. Fringe cuts do not force transactions.

Unrostered players keep historical season totals but cannot accumulate new game logs while unsigned. See [[History/Failure Museum]].

## Cap Model

The game displays payroll, cap room, tax room, and hard-cap room for relevant seasons. Contract legality updates after every signing, extension, and trade. Narrative packets use these exact modeled concepts and must not invent real-world apron claims the engine does not represent.

Configuration is versioned in [contract_market_config.json](../../../data/overrides/contract_market_config.json).

## Invariants

- A contract application preserves active-season salary unless the transaction explicitly changes it.
- A player cannot sign while retired or under an incompatible active contract.
- A recently signed player remains visible but trade-ineligible until the modeled December date.
- User cancellation causes no save mutation.
- Every applied contract stays under modeled cap/hard-cap rules or an explicit configured exception.
- Free agents cannot record games until rostered.
- AI extensions and signings create one transaction/event representation, not duplicate press/news spam.

## Alternatives

### Exact CBA Engine

This would improve legal fidelity but requires exception, bird-rights, cap-hold, option, guarantee, apron, and trade-matching detail far beyond the current product's central loop. The current configuration explicitly documents the simplification so it can be replaced deliberately later.

### Fixed Salary By Overall

Simple and fast, but destroys role, age, contract leverage, team context, and market personality.

### Auction-Only Free Agency

Could create clear bidding mechanics but would miss fit, team preference, timing, and user-facing negotiation.

## Related Notes

- [[Systems/Transactions and Asset Valuation]]
- [[Architecture/Season State Machine]]
- [[Data/Overrides and Model Configuration]]
