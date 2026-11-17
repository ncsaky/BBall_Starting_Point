# Pick label ledger

This is a regex-style catalogue of the current game's label templates, not a proposed change to the wording. Examples are illustrative unless identified as a current starting-data example.

## 1. Notation and shared fields

| Notation | Meaning |
| --- | --- |
| `{FIELD}` | Substitute a value. Braces do not appear in the displayed label. |
| `[text]` | Optional text. Brackets do not appear in the displayed label. |
| `(A\|B)` | Choose A or B. The parentheses and pipe are notation. |
| `{TEAM_LIST}` | Originating team abbreviations separated by `/`, e.g. `BKN/PHX/NYK`. |
| `{PREFIX}` | `{YEAR} R{ROUND}`, e.g. `2028 R1`. |
| `{YEAR}` | Four-digit draft year; normal token pattern `\d{4}`. |
| `{ROUND}` | `1` or `2`; normal token pattern `[12]`. |
| `{ORIGIN}` | Team whose original draft pick determines the selection's position. |
| `{OWNER}` | Current holder of the physical pick, before pending conditions resolve. |
| `{HOLDER}` | Team entitled to the specified outcome under a swap right. |
| `{COUNTERPARTY}` | Named recipient of the remaining compared pick. This can differ from the originating team. |
| `{N}`, `{LOW}`, `{HIGH}`, `{K}`, `{FIRST}`, `{LAST}` | Positive integers; `\d+` is the token shape. Legal limits depend on the round and the rule. |

**More favourable means the earlier selection: #3 is more favourable than #15.** Less favourable means the later selection. These comparisons use draft order, not the eventual player's quality.

`more/less` describes a comparison between two picks. `most/least` describes the extreme of a larger pool.

## 2. Physical pick label

```text
{YEAR} R{ROUND} {ORIGIN} ({OWNERSHIP})[; {CONDITIONS}]

OWNERSHIP := own pick | owned by {OWNER}
CONDITIONS := protection details | swap entitlement | fallback details
              | protection details; swap entitlement
```

| Option | Example | Meaning |
| --- | --- | --- |
| Own, unconditional | `2028 R1 BKN (own pick)` | BKN currently owns its original first. |
| Acquired, unconditional | `2027 R1 NYK (owned by BKN)` | The selection originates with NYK but belongs to BKN. |
| Conditional | `2028 R1 PHI (owned by BKN); top-8 protected; …` | Current ownership is followed by the condition that determines conveyance. |

A standalone swap entitlement can begin directly with `{PREFIX}: …`, without the physical-pick ownership wrapper. The combined card uses an existing physical-pick wrapper when it can attach the entitlement to one owned pick.

`unprotected` is omitted from the pick-icon tooltip. No condition suffix is needed for an ordinary unconditional pick.

## 3. Protection and fallback options

Every protection must have explicit numeric selection bounds. Labels, valuation and ownership resolution use those same bounds. A missing or invalid range is a data error, never a permitted protection type.

| ID | Pattern | Explanation |
| --- | --- | --- |
| P1 | `top-{N} protected` | Selections 1 through N remain with the protected pick's sender. |
| P2 | `picks {LOW}-{HIGH} protected` | Only the stated inclusive selection range is protected. |
| P4 | `{SENDER} keeps this pick if it lands in the protected range` | Explains the retained-pick branch after the short protection label. |
| P5 | `{RECEIVER} instead receives {FALLBACK_PREFIX} {FALLBACK_ORIGIN}` | Names the replacement asset if the primary is protected. The normal full-label path can omit this clause when fallback detail is disabled. |
| P6 | `Fallback for {PRIMARY_PREFIX} {PRIMARY_ORIGIN} ({PROTECTION}); {RECEIVER} receives this pick if the primary lands in its protected range` | Label on the reserved fallback asset itself. It is conditional collateral, not another unconditional incoming pick. |

Illustrative full protected-pick label:

```text
2028 R1 PHI (owned by BKN); top-8 protected;
PHI keeps this pick if it lands in the protected range;
BKN instead receives 2029 R1 PHI
```

The primary and its fallback are separate underlying assets. The current model uses its existing normalized fallback terms; this example does not describe the exact real-world contract.

## 4. Two-pick swap options

```text
{PREFIX}: {HOLDER} receives the {FAVOURABILITY} favourable of {A}/{B};
{COUNTERPARTY} receives the {OPPOSITE} favourable of those two picks.

(FAVOURABILITY, OPPOSITE) := (more, less) | (less, more)
```

| Option | Example | Meaning |
| --- | --- | --- |
| More favourable | `2027 R1: HOU receives the more favourable of HOU/BKN; BKN receives the less favourable of those two picks.` | HOU gets the earlier selection and BKN gets the later one. |
| Less favourable | `2027 R2: MIL receives the less favourable of BKN/DAL; WAS receives the more favourable of those two picks.` | The named holder is entitled to the later selection. |

Both outcomes are definite. `may receive`, `Subject to`, and `other team receives` are not generated swap templates.

## 5. Combined entitlement options

```text
{PREFIX}: {HOLDER} receives the [{ORDINAL} ](most|least) favourable of {TEAM_LIST}.
```

| Option | Example | Meaning |
| --- | --- | --- |
| Most favourable | `2028 R1: BKN receives the more favourable of [the more favourable of BKN/PHX]/NYK.` | One resulting pick: the earliest of the three. This is the current starting-data model's combined Brooklyn 2028 entitlement. |
| Least favourable | `2030 R1: TEAM receives the least favourable of A/B/C.` | One resulting pick: the latest of the pool. This example illustrates the template. |
| Second least favourable | `2030 R1: TEAM receives the second least favourable of A/B/C.` | The middle pick of three. |
| Second most favourable | `2030 R1: TEAM receives the second most favourable of A/B/C/D.` | The second-earliest of four. |
| Third least favourable | `2030 R1: TEAM receives the third least favourable of A/B/C/D/E/F.` | The third-latest of six. |

This short form is used only when the connected comparisons can safely be reduced to that outcome. It does not mean one pick per team icon, and it does not create an extra tradeable asset. A separately protected incoming pick remains a separate entitlement.

## 6. Ranked-pool entitlement options

```text
{PREFIX}: {OWNER} receives {RANKED_OUTCOME} of {TEAM_LIST}.
```

| RANKED_OUTCOME | Example | Meaning |
| --- | --- | --- |
| `the more favourable` / `the less favourable` | `2027 R2: WAS receives the more favourable of BKN/DAL.` | One earlier/later pick from a two-pick comparison. |
| `the most favourable` / `the least favourable` | `2029 R1: BKN receives the least favourable of HOU/PHX/DAL.` | One earliest/latest pick from a larger pool. |
| `the {ORDINAL} most favourable` | `2030 R1: TEAM receives the second most favourable of A/B/C/D.` | One specific rank counted from the earliest selection. |
| `the {ORDINAL} least favourable` | `2030 R1: TEAM receives the second least favourable of A/B/C.` | One specific rank counted from the latest selection. |
| `the {N} most favourable` | `2029 R1: HOU receives the 2 most favourable of HOU/PHX/DAL.` | A combined entitlement to two picks: the earliest and the second-earliest. |
| `the {N} least favourable` | `2030 R2: TEAM receives the 2 least favourable of A/B/C/D.` | A combined entitlement to the latest and second-latest picks. |
| `the {ORDINAL} and {ORDINAL} most/least favourable` | `2030 R1: TEAM receives the second and third most favourable of A/B/C/D/E.` | Multiple interior ranks, each named explicitly. |

**Ordinal vocabulary:** second, third, fourth, fifth, sixth, and so on. Use the nearer end of the pool; ties use **least**. Thus the middle of three is consistently **second least favourable**. Do not change between two equivalent phrasings for the same entitlement.

The combined card displays a multi-pick entitlement once. Underlying pick IDs remain separate for ownership and individual trades; the aggregate sentence describes the team's complete pool allocation. It does not turn one selected physical pick into a two-pick trade package.

The compact rank description is used only for a recognized allocation sequence whose outcome can be established. Other sequences use the ordered form below.

## 7. Connected allocations — examples for review

Use explicit nesting for sequential swaps of one received outcome. Keep ordinal labels for ranked pool allocations. A nested entitlement is one trade asset and resolves to one physical pick.

### 7A. Simple three-team result

```text
2028 R1: BKN receives the more favourable of [the more favourable of BKN/PHX]/NYK.
```

One entitlement, one resulting pick. PHX is compared first, then that outcome is compared with NYK. The glyph shows the inner BKN/PHX swap beside NYK, with arrows below each comparison. Trading this entitlement transfers its base slot and both comparison rights together; the other teams’ picks are not transferred.

Trade valuation reuses ordinary projected pick values and the existing swap distance/uncertainty parameters. It prices one baseline pick with bounded, diminishing selection upside, never the sum of all candidate picks or separately priced child rights.

### 7B. Middle recipient

```text
2030 R1: TEAM receives the second least favourable of A/B/C.
```

The recipient gets the middle pick. This is the approved new pattern; the team placeholders are illustrative.

### 7C. A genuinely dependent chain

When a final rank alone would misstate the outcome, retain the named comparisons and their order. This illustrative example follows the current ordered-label structure:

```text
2030 R1 connected allocation — apply in this order:
1. A receives the more favourable of A/B; B receives the less favourable of those two picks.
2. C receives the more favourable of the pick allocated to C and the pick allocated to B from A/B/C; B receives the less favourable of those two picks.
```

B's final pick is the least favourable of all three. C compares its original pick with B's result from step 1. A has already received the better A/B pick. C cannot be described as receiving a fixed middle or top rank in every draft-order scenario.

This longer form remains for cases that cannot be reduced safely. It contains definite outcomes and named recipients.

## 8. Conditions — examples for review

Every condition must identify numeric selection bounds and the consequence in each branch. These examples are illustrative; they are not new trades or changes to pick ownership.

### 8A. Protected swap

```text
2030 R1: If a compared pick falls in its protected range (B: picks 1–3), both compared picks stay with their current owners. Otherwise, A receives the more favourable of A/B; B receives the less favourable of those two picks.
```

B lands at #1–#3: no exchange. B lands at #4 or later: compare the two picks and give A the earlier selection.

### 8B. Protection resolves before a connected entitlement

```text
First resolve protections: If B lands in picks 1–5, B retains that pick; otherwise, A receives it. In the protected branch, A instead receives 2031 R1 B.
Then 2030 R1: C receives the more favourable of the least favourable pick held by A and the pick allocated to C from A/B/C; A receives the less favourable of those two picks.
```

Resolve B's explicit top-five protection first. The subsequent comparison uses the actual picks A holds afterward. The fallback is named by year, round and origin.

### 8C. Protection leaves a required comparison without a pick

```text
If A or C holds no pick in this pool after protections resolve, this comparison is skipped and ownership stays unchanged. Otherwise, C receives the more favourable of the pick allocated to A and the pick allocated to C from A/B/C; A receives the less favourable of those two picks.
```

This is a conditional modifier attached to the explicit protection wording in 8B, not a standalone vague condition. It explains the existing skip rule when a comparison lacks one of its required subjects.

### 8D. A swap right has been traded to a third team

```text
2030 R1: C receives the more favourable of A/B; If the more favourable pick is transferred from A, A receives the less favourable of those two picks. If the more favourable pick is transferred from B, B receives the less favourable of those two picks.
```

C owns the swap right but neither compared pick. The remaining pick goes to the displaced owner. Both branches are stated by name rather than using an unspecified recipient.

## 9. Invalid data is blocked — examples for review

No generic protection, unspecified reservation or unknown-source condition is an approved pick-label option. Missing facts must be reported as a data error, not presented as a usable asset with guessed ownership or value.

| Situation | Example error / required correction |
| --- | --- |
| Protection has no numeric bounds | `Pick protection requires an explicit valid selection range; generic protection is not permitted.` Supply the actual inclusive selection range before the condition can be processed. |
| A pick has a generic protection summary | `Pick pick_example has no explicit protection range; it cannot be valued, traded or resolved.` Supply explicit supported terms. |
| A locked asset has no identifiable fallback condition | `Pick pick_example has an unspecified conditional obligation; explicit terms are required.` Identify the primary, its range and the fallback receiver. |

These are errors, not tradable pick labels. Existing protected obligations must pass the range check before save normalization can remove or repair unrelated issues; an unknown range is never silently converted to an unconditional pick. Numeric bounds take precedence over source prose when generating the displayed protection label.

The older placeholder paths for missing team/year/round information are not approved normal label examples. They require explicit identifiers to produce a meaningful asset description. They are separate from protection rules; this change does not invent missing identities.

## 10. Icons and complete labels — examples for review

| Example | Display and meaning |
| --- | --- |
| `2028 R1 BKN (own pick)` | BKN mark. One ordinary pick. |
| `2027 R1 NYK (owned by BKN)` | NYK mark identifies the originating pick; the text identifies BKN as owner. |
| `2028 R1 PHI (owned by BKN); top-8 protected; PHI keeps this pick if it lands in the protected range; BKN instead receives 2029 R1 PHI` | PHI mark with `*`. The range and fallback are explicit. |
| `2028 R1: BKN receives the more favourable of [the more favourable of BKN/PHX]/NYK.` | BKN, PHX and NYK marks with `⇄` only. One resulting pick, not three. |
| `2029 R1: HOU receives the 2 most favourable of HOU/PHX/DAL.` | HOU, PHX and DAL marks with `⇄` only. One combined entitlement containing two underlying picks. |
| A related PHX pick currently owned by WAS in the extended view | Faded PHX mark with a small WAS owner badge. This supplies ownership context; it is not another unconditional pick owned by the viewed team. |

`*` sits in a small 9px outlined bubble tight to the upper-right edge of its icon group and indicates an explicit protection only. An unprotected swap uses `⇄` without an asterisk; a protected swap uses both. An owner badge appears only when the owner differs from the originating team.

Every main draft icon has the same 20px opaque, outlined circular bubble. Each logo fits proportionally inside a 16px area, with transparent source padding excluded. Transparent portions cannot reveal the lower overlapping mark. Swap marks partially overlap like a Venn diagram. The recipient of the more favourable pick is drawn in front. Opposing arrows sit below the bubbles with a 3px gap, scaled to 70% of the original full-width size. Connected pools retain all participating marks, using the known top-ranked recipient when available.

All main bubbles have identical dimensions; the logos retain their proportions inside them. Owned picks and swap entitlements remain fully visible, including less-favourable outcomes and locked collateral. Extended-view comparisons are faded when the viewed team owns neither outcome. Ownership of either outcome, including the less-favourable pick, keeps the comparison fully visible. Main marks, their order, `⇄`, and `*` stay consistent between default and extended views for the same entitlement. A condition is appended to the tooltip only if its full label does not already contain it. Unconditional picks omit redundant unprotected wording.

## Implementation sources

- `src/nba_gm_data/pick_presentation.py`: swap steps, connected entitlements, ranked pools, and conditional branches.
- `src/nba_gm_data/transactions.py`: physical-pick ownership wrapper, protection labels, and condition composition.
- `src/nba_gm_data/app_actions.py`: reserved fallback-asset labels and presentation payloads.
- `src/nba_gm_data/gui/assets-desktop.js`: tooltip composition and icons.

### Original assets and outcome ownership

For the 2027 BKN/DAL second-round comparison, the main bubbles remain BKN and DAL. DAL is in front with a tight WAS ownership badge for the more-favourable entitlement; BKN carries a MIL badge for the less-favourable entitlement. The tooltip names both outcomes. These are presentation slots for the compared original assets; they do not change which originating selection ultimately conveys. WAS/MIL ownership and draft-resolution rules remain unchanged.
