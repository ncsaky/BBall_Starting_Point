# Staff lifecycle

Staff now age and build experience from season to season. Younger staff usually improve, older staff usually decline, and time on the job helps with decisions such as rotations and matchup adjustments. Each person keeps a record of their rating changes. Staff can retire, and each offseason brings new candidates into the hiring pool.

Wins above or below the preseason forecast and playoff series wins move reputation and job security. The season review gives a departing coach credit for their time on the job. An offseason replacement starts with their own reputation. The existing simulation formulas for coaching, player development, injuries and scouting are untouched.

## Implementation

- New saves use the local coaching sources by name, including when an NBA team page supplied the coach's name and ESPN supplied their experience and record. The save marks reported fields and seeded estimates separately. The ESPN figure is the experience reported by the source, and its record is retained as historical context.
- Rating history records the completed season, role, age, experience and actual changes for each skill and personality trait. Traits ease toward the ends of the 20–96 scale. The initial real-coach calibration yields to saved career progression.
- The preseason baseline uses the league's roster-strength estimates centered at a .500 record. The opening forecast uses the fixed canonical snapshot. Rollover stores the following season's forecast using its roster after offseason moves. The season review weighs results by time on the job, and gives team results more weight for head coaches than for support roles.
- The lifecycle runs once per completed season from the contract rollover. Retirees remain in the save's career records, and vacant jobs get an interim. A former coordinator can become a head coach candidate while keeping the same person ID and history. The opening generated market stays in place until the first rollover. Annual intake then keeps at least 20 head coach candidates and 16 candidates in each other role, with a strong option when the pool lacks one.
- The career model is seeded from the save and uses independent draws from the game random number stream. The curve, entry ages, retirement odds and candidate quality targets are gameplay estimates.

## Verification

- The core script ran 330 tests successfully with two skips. All 22 staff, coaching and retention tests selected from the foundation suite passed.
- The full Python suite ran in five parallel groups. All groups passed, with 1,764 tests run and 28 skipped. The end-to-end season rollover test advanced into the next regular season.
- Eight lifecycle tests passed, including 12 consecutive offseason refills, rating drift, recruitment depth, retirement, stale offers, promotion, reputation and save round-trip.
- A scratch save with seed 17 and synthetic standings had 180 staff positions before and after contract rollover. Twenty-seven head coaches had ESPN experience data. The head coach market went from an opening top grade of 81.07 to 86.69 after rollover. Its post-rollover median was 59.50 across 23 candidates. Each other role had 17–18 candidates. The rollover produced a preseason forecast for all 30 teams.
- Across 200 seeded first rollovers of the opening market, the top head coach candidate scored 84.01–92.42, with a median top grade of 87.50. The typical median candidate scored 56.94. The pools held 21–23 head coach candidates and each included a coordinator who moved up.

- Across all six roles and five seeds, the opening market matched the previous candidate identities, ratings, grades, salaries and ordering.
- A separate hire-and-fire check confirmed that an aged candidate kept their identity and rating history through a hire and later returned to the market once.

## Resume state

Implementation and verification are complete. Ready for coordinator review. Changes are uncommitted.
