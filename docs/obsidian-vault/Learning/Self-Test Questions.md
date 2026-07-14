---
type: learning
status: current
reviewed: 2026-07-10
tags:
  - learning/self-test
  - project/nba-gm
---

# Self-Test Questions

Answer aloud or in a new note without reading the linked answer first. A strong answer names state authority, ordering, tradeoffs, and tests.

## Architecture

1. What is the difference among raw evidence, canonical data, save state, save-aware canonical data, and a GUI view model?
2. Why does `canonical_with_save` copy/enrich instead of mutating the loaded canonical dictionary?
3. Which inputs should invalidate transaction pick projections?
4. Why is `advance_save` an application transaction rather than a date assignment?
5. What would need to change before two games could safely simulate in separate processes?
6. Why is per-save locking sufficient for the local GUI but insufficient for hosted multi-user play?
7. What are the failure modes of opportunistic save defaults compared with explicit migrations?

## Simulation And Ratings

8. How can a simulation be random and reproducible at the same time?
9. Why are stable IDs and sorted iteration necessary even with fixed seeds?
10. Why is a rotation-weighted team average insufficient to model star power?
11. Why can realistic standings coexist with absurd player ratings?
12. Define quantile mapping and explain why it was used for the human ratings prior.
13. Why are current injury and full-health rating separate?
14. What assertions belong in a multi-seed calibration test versus a deterministic replay test?

## Transactions And Picks

15. Why can one asset show different values in an asset list and trade response?
16. Distinguish legality, AI acceptance, user consent, and advisor recommendation.
17. Why must Trade Finder terms be chosen before searching?
18. Why did a finder offer once become rejected at application, and what state contract fixes it?
19. List every state collection that a player trade may affect.
20. Why is a pick swap not worth a full pick?
21. Describe protected-pick resolution when the right has been retraded.
22. Why must fallback collateral be hidden/locked?
23. What exact IDs and order must agree between lottery reveal and live draft?

## Contracts, Health, Staff, And Draft

24. Why must an extension merge future salary years?
25. How should AI distinguish a core extension candidate from replaceable depth?
26. How does an in-season released-player signing differ from offseason free agency?
27. Why do historical stats remain while an unsigned player stops accumulating new stats?
28. What signals should excuse a coach from a poor record?
29. How do support-staff firing reasons differ by role?
30. Why should pre-draft scouted ratings differ from post-draft dashboard ratings?
31. How can draft selection preserve BPA while avoiding nonsensical roster redundancy?

## Narrative

32. Why is prompt text alone insufficient to prevent stale real-world claims?
33. Which facts belong in an extension context packet?
34. Why does the model not receive authority to choose morale deltas?
35. What belongs in a narrative cache key?
36. Why is lazy social generation preferable to sim-time generation?
37. Give one valid opinion that is factually skeptical and one invalid factual claim.

## GUI And Product

38. What does GUI parity mean beyond “there is a button”?
39. Why should team inspection disable front-office controls but still render data?
40. What caused repeated card overlap, and what structural CSS solution replaces pixel adjustments?
41. When should an action be a modal versus a separate room?
42. Why is the current GUI not evidence that a standalone iPhone app exists?

## Quality And Performance

43. What four properties must every cache document?
44. Why is shortening a simulation by skipping intermediate AI checkpoints not an optimization?
45. What is a characterization test, and when should one be written?
46. Design a lifecycle test for a protected pick from creation through fallback resolution.
47. Design a five-season soak invariant report.
48. Why should the full suite not be terminated just because rollover takes a long time?
49. What evidence would justify a Rust/C native kernel?
50. What are the first three controls needed before public network hosting?

## Synthesis Challenges

51. A team trades a protected current-year pick, then reacquires the right before the lottery. Trace ownership, collateral, value, labels, and resolution.
52. A star is injured on opening day, gets traded after recovery, then suffers another injury. Trace rating, availability, value penalty, rust, roster, and narrative context.
53. A month sim crosses a development checkpoint and trade deadline. Describe the safe order and every UI card that must refresh.
54. An Ollama post says a team has cap trouble despite +$60M hard-cap room. Where should the error be prevented, detected, repaired, cached, and displayed?
55. The GUI and CLI disagree after applying a contract. How do you determine whether the bug is domain state, action mapping, or rendering?

## Answer Map

- Questions 1-7: [[Maps/Architecture MOC]]
- Questions 8-14: [[Systems/Simulation Engine]] and [[Systems/Ratings and Traits]]
- Questions 15-23: [[Systems/Transactions and Asset Valuation]] and [[Systems/Pick Obligations and Swaps]]
- Questions 24-31: relevant notes in [[Maps/Gameplay Systems MOC]]
- Questions 32-37: [[Systems/Narrative Engine]]
- Questions 38-42: [[Product/CLI to GUI Evolution]] and [[Product/Dashboard Design]]
- Questions 43-50: [[Maps/Quality and Operations MOC]]
- Questions 51-55: combine multiple notes and inspect source/tests.

