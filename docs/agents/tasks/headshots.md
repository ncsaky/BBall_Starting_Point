# HEADSHOTS: staff and prospect faces

Owner: Claude (Opus agent), branch `worktree-agent-abab0f5b961e89d94`. Board row: HEADSHOTS. Status: **review**.

## TL;DR
- Every made-up staff member now has their own face and a name of the same gender (2,000 faces, about 470 first names, 375 last names); no face or name repeats in a league, and about 1 in 8 staff are women, mostly in medical, scouting and development jobs.
- 22 of the 30 real head coaches show their real photo (free Wikimedia licences), and 528 of the 535 real college prospects show their ESPN headshot; everyone else (8 coaches, high-school and international prospects, made-up prospects) gets a generated face.
- Style samples to choose from: `output/headshots/options.html` (Open Peeps is built in; Avataaars or Personas is one command away).

## Audit (before this change)
- **Where staff names came from.** Two separate lists, both men only:
  - Starting staff: `data/overrides/gameplay_staff_seed.json` `name_pool` (30 names), baked into the universe file by `ingest.py:2393` `build_gameplay_staff_slots` / `deterministic_pick` (2439). 150 made-up starting staff shared 30 names (e.g. "Nolan Pierce" 11 times).
  - Market candidates and interims: `staff.py` `FIRST_NAMES` / `LAST_NAMES`, 12 x 12 = 144 combinations (`generated_staff_candidates`, `interim_staff`), so "Reid Coleman", "Reid Wallace", "Reid Hayes" sat side by side.
  - Real head coaches: `save.py:6932` `align_real_head_coach_names` puts the real name on each team's head-coach slot.
- **Where staff faces came from.** Six drawings (`gui/assets/game-art/coaches/coach-01..06`, silver and ink versions). `gui/app.js` `coachPortraitAssignments` (about line 4026) handed the six out per table, rotating so a team's six staff used all six. Nothing knew the person's gender.
- **Why repeats and wrong genders.** Six pictures for 180 people means every team shows the same six. One of the six (`coach-04`) is a woman, and every name was a man's, so every team had a man's name next to a woman's face. Gender was never stored anywhere.
- **Prospects.** No headshots at all. `playerHeadshotMarkup` (app.js about line 12528) drew a blank silhouette for anything with `is_prospect`; the draft boards (`draftBoardRows` consumers at about lines 3970 and 5696) had only a college logo or flag. Real prospects (`data/canonical/real_prospects.json`, 655 players) and generated classes (`draft.py` `_generated_class_records`) had no picture field. Drafted rookies (`rookie_player_record`) had none either.
- **Players.** NBA players use ESPN headshot links (`headshot_url`, hot-linked from `a.espncdn.com`, marked `reference_only_not_cleared` by `ingest.py`). The game shows every headshot in greyscale.

## Real photos
Fetched once by `scripts/fetch_real_headshots.py` (standard library; one request at a time, 1-3 s apart, every response cached in `output/headshots/cache/`, backing off on "too many requests"). Stored in `src/nba_gm_data/gui/assets/headshots/real/` with `manifest.json` (person, source page, image URL, date, rights, licence/author for coaches).
- **Head coaches: 22 of 30.** The lead photo of the coach's Wikipedia article, used only when it is a freely licensed Wikimedia Commons file (CC0, CC BY, CC BY-SA, public domain; licence and author recorded). Cropped around the face with macOS's built-in face detection (`scripts/crop_headshot.swift`), 260 px JPEG, about 25 KB each.
  - No usable photo (fall back to a generated man's face): Charles Lee, David Adelman, Taylor Jenkins, Jamahl Mosley, Sean Sweeney, Jordan Ott (no Wikipedia lead photo), Kenny Atkinson and Nick Nurse (their lead photos are not free Commons files, so not used).
  - JJ Redick's only free photo is from his playing days (76ers uniform).
  - A Commons file-name search was tried for the missing ones and dropped: it returned a gravestone for "Charles Lee".
- **Prospects: 528 of 655.** ESPN's men's college basketball team rosters (123 team rosters, one request each), the player's ESPN headshot (`a.espncdn.com/i/headshots/`, allowed by ESPN's robots.txt), 260 px AVIF with transparency, about 7 KB each.
  - College: 528 of 535. Missing: 4 with no ESPN headshot, 3 not on their ESPN roster.
  - 8 matched on a nickname spelling (Cam/Cameron Ward, Kam/Kameron Taylor, JoJo/Joseph Tugler, Vince/Vincent Iwuchukwu...); all checked as the same person.
  - High school (90) and international (30): no consistent public source; deliberate fallback to a generated face, recorded in the manifest with the reason.
  - ESPN photos are marked `reference_only_not_cleared`, the same status as the NBA player headshots the game already shows. Fine for the private beta; worth a look before any public release.
- **Real staff gender** comes from the real person (all 30 current head coaches are men; recorded per coach in the manifest).

## Generated faces: options and licences
Sample sheet: `output/headshots/options.html` (12 faces per style, mixed gender and skin tone, plus the real photos). Built with DiceBear 9.2.4 (MIT) as a build-time tool only (installed in git-ignored `output/headshots/tooling/`, not shipped).
- **A. Open Peeps (built in).** Hand-drawn ink line art. **CC0 / public domain**: no credit or conditions. Best licence, and the ink outline suits the game's newspaper look.
- **B. Avataaars.** Smooth flat cartoon; staff in blazers, prospects in hoodies. "Free for personal and commercial use" under its own licence (not Creative Commons).
- **C. Personas.** Simple rounded flat faces. CC BY 4.0: needs a visible credit to Draftbit.
- **Not offered:**
  - AI-generated photo sets (StyleGAN faces, Generated Photos). As far as I know they are non-commercial or attribution-restricted; not re-checked online tonight.
  - Photos of real people for made-up characters.

**How the library works** (`scripts/build_face_library.mjs`). We pick every face part ourselves from a seeded stream, so:
- each face uses only hair and beard parts that read as one gender (unisex or odd parts like hats and silly moustaches are left out);
- no two faces in a group share a combination of parts;
- a rebuild gives the same faces.

Groups:
- `staff-m`: 640 faces, 173 with grey hair;
- `staff-f`: 260 faces, 67 with grey hair;
- `prospect-m`: 1,100 young players' faces.

Size: 2,000 SVGs, 18.8 MB. With the real photos, about 24 MB in all (29 MB on disk), under the 60 MB target.

**To switch style:** run `node scripts/build_face_library.mjs --style avataaars` (same group sizes), then set `LIBRARY` in `src/nba_gm_data/faces.py`. New saves then use it.

## What was implemented
- **`src/nba_gm_data/faces.py` (new).** One place for faces:
  - library and manifest loading;
  - `pick_face`: a stable start from the person's id, then the next unused face of the same gender group, matching the age band first (grey hair for staff 57 and older);
  - `draw_staff_identity`: gender by role share, then a name from that gender's list, never a real head coach's name;
  - `apply_staff_face` / `ensure_staff_faces` / `ensure_save_staff_faces`: faces for everyone in the save. A newly faced person whose name is taken gets a fresh same-gender name;
  - prospect helpers: `prospect_headshot_url`, and `assign_class_faces` (no repeat inside a draft class).
- **`src/nba_gm_data/staff_names.py` (new).** The name lists (below).
- **Staff (`staff.py`, `staff_lifecycle.py`, `save.py`).**
  - New saves: made-up staff get a gender and a unique same-gender name (`initialize_save_staff_slots`). Faces are handed out right after the real head coaches are named (`_create_league_save`, and the load-repair path).
  - Market candidates (`generated_staff_candidates`) and interims (`interim_staff`) draw gender-matched names.
  - The old 12 x 12 grid's two random draws are kept only to key each candidate's id, so contracts, ages and grades are unchanged. All new draws use their own random streams; no other outcome moves.
  - `apply_market_faces` (called from `generate_staff_market`): before the first offseason, faces go out in one fixed order over the whole generated market, avoiding faces already held. A candidate shows the same face whether the list is filtered by role or not, and keeps it when hired. Cached per face set; about 10 ms for the full market.
  - Firing (`fire_staff_from_save`) and the season roll (`roll_staff_lifecycle`) give new interims and the new market intake faces.
- **Prospects (`schema.py`, `draft.py`, `app_actions.py`).**
  - `DraftProspect.headshot_url` (optional, display only).
  - Generated classes get faces with no repeat in the class. Real-plus-generated classes get real photos (matched by the real player's id) plus non-repeating generated faces.
  - `board_entry_payload` and the prospect card payload send the picture.
  - Drafted rookies keep their prospect picture (`rookie_player_record`).
  - The signing-wire staff entry carries the staff member's picture.
- **GUI (`gui/app.js`, `card-board.css`).**
  - `staffPortraitMarkup` shows each staff member's own face (real photos cropped to fill; generated faces bottom-aligned; greyscale like all game headshots) in the staff window, the market list, coach cards, hire negotiations and the signing wire.
  - Old saves without faces fall back to the old art.
  - `prospectFaceMarkup` puts a lazy-loaded, bottom-aligned headshot filling the row at the start of the name cell on Upcoming Prospects and the draft-night Prospect Board.
  - Prospect cards show the photo or face instead of the blank silhouette.
  - All images are lazy-loaded.
- **Not changed:**
  - The Assistant GM phone shows initials, not faces.
  - The six old coach drawings stay for old saves.
  - No changes to free agency, offseason, trade or Trade Market logic.

## Name lists
- **Size:** 295 men's first names, 178 women's first names, 375 last names (`staff_names.py`), up from 12 + 12 (and the 30-name starting pool).
- **Regional groups**, so first and last names fit together: United States 70%, Latin America and Spain 8%, southeast Europe 6%, northwest Europe 6%, Africa 5%, Asia-Pacific 5%. Each group also mixes in English first names.
- **No unisex names.** Names that can read as either gender are left out (Jordan, Taylor, Jamie, Quinn, Kelly, Morgan, Alex, Sam, Drew, Leslie...). A check fails if any first name is on both lists.
- **Share of women by role:**
  - head coach 3%;
  - coordinators 7% (close to the real share of women among NBA assistant coaches, roughly 1 in 20);
  - development and scouting 14%;
  - performance and medical 24%.
- **Result:** a new league has 22 women among 180 staff (all 30 real head coaches are men).

## Screenshots (`output/headshots/`, 1440-wide layout shown in the app's browser pane)
- `before_staff_window_1440.jpg`, `before_staff_window_zoom.png`: the six shared drawings, the "Reid ..." name grid.
- `after_staff_window_1440.jpg`, `after_staff_window_zoom.png`: Joe Mazzulla's real photo, a distinct face per staff member and per market candidate.
- `before_prospects_board_1440.jpg` / `_zoom.png` and `after_prospects_board_1440.jpg` / `_zoom.png`: real prospect photos on the Upcoming Prospects board.
- `after_prospect_card_1440.jpg`: Quentin Coleman's card with his photo.
- `after_coach_card_1440.jpg`: Nicole Nelson (development lead) with a woman's face.
- The "before" server ran the main checkout's current code (pre-headshots) against the same data.

## Tests
- **New: `tests/test_headshots.py` (12 tests, pass).** They check that:
  - names and faces always share a gender (staff, market, interims);
  - no face or name repeats in a full 180-person league, and the market avoids held faces;
  - the same candidate keeps the same face across market views;
  - older staff get grey-haired faces;
  - women stay a realistic minority;
  - real head coaches keep their name and get their photo or a same-gender face;
  - made-up staff never take a real coach's name;
  - every real photo has a source, date, rights and file (under 45 KB), and every coach photo has a licence;
  - every one of the 655 real prospects gets a photo or a recorded fallback, and the file exists;
  - draft classes give everyone a picture with no generated face twice;
  - the library manifest matches the files.
- **JS tests:** all 40 `tests/*.test.cjs` pass. `startup_video.test.cjs` needed the git-ignored startup movie symlinked into the worktree, an environment gap and not a code issue.
- **GUI and focused tests:** `tests.test_gui_concept71`, `tests.test_gui_concept74`, `test_staff_lifecycle`, `test_real_prospects`, `test_draft_boards`, `test_draft_fixes` and `test_prospect_identifiers` pass (73 tests).
- **Core suite:** `bash scripts/run_core_tests.sh`: 338 tests OK (2 skipped).
- **Speed:** save creation about 11 s as before. The market face pass adds about 10 ms.

## What's left
- **8 head coaches without free photos.** If the user accepts NBA.com or ESPN coach photos (not freely licensed), they can be added to the manifest the same way.
- **High-school and international prospects (120)** use generated faces. 247Sports, EuroLeague and FIBA pages have photos, but there is no single reliable source; this could be done by hand for the top 30 or so.
- **ESPN prospect photos** are reference-only, like the NBA headshots the game already links. Recheck before any public release.
- **Draft-night Prospect Board:** same helper and styles as the Upcoming Prospects board, but not seen live (it only opens on draft night).
- **Old saves** keep the old six drawings. By design: new saves get the new faces.
- **Face skin tone** is independent of the name's region. Names and faces always agree on gender, not on heritage.
- **`pyproject.toml` package data** does not list `gui/assets/headshots/` (the macOS beta bundles the whole GUI folder, so the beta is fine; a pip install would miss them).
- The **Assistant GM phone** has no faces (initials only); not changed.

## Resume state
- [x] Board row, worktree symlinks, audit
- [x] Real coach photos (22/30), real prospect photos (528/655), manifest
- [x] Face library (Open Peeps, 2,000), options.html (3 styles)
- [x] faces.py, staff_names.py, staff/save/lifecycle wiring, prospect faces, GUI
- [x] Tests, screenshots, report

---

# HEADSHOTS-V2: real photos only

Owner: Claude (Opus agent), branch `worktree-agent-a1049d23b312b874f` (merged the HEADSHOTS branch first). Board row: HEADSHOTS-V2. Status: **review**.

## TL;DR
- Every face in the game is now a photo of a real person: the cartoon library is gone. All 30 head coaches show their real photo, and 594 of 655 real prospects do (was 528).
- Made-up staff and made-up prospects use a stock library of 393 openly licensed photos of real, non-famous adults from Wikimedia Commons (192 men, 139 women, 62 young men for prospects), each one credited; Settings now has a Photo credits view.
- Faces can hold several images per person by age ("stages"), ready for the planned generated faces; the stock library is kept modest because it may be replaced.

## Coaches: 30 of 30 real photos
- 22 keep their freely licensed Wikimedia photo (unchanged).
- The other 8 (Charles Lee, David Adelman, Taylor Jenkins, Jamahl Mosley, Sean Sweeney, Jordan Ott, Kenny Atkinson, Nick Nurse) now use the official headshot on their page of the National Basketball Coaches Association (nbacoaches.com, the NBA coaches' association; robots.txt allows it). NBA.com shows no coach photos and refuses scripted access; ESPN's coach photos are 65x90 px.
- All 8 are head coaches in the game's 2026-27 staff list, and ESPN's 2027 coach list matches.
- Recorded in `real/manifest.json` with source page, image URL, date and `reference_only_not_cleared` (the same status as the NBA player headshots). `scripts/fetch_real_headshots.py --nbca-coaches`.
- Free Commons photos also exist for Adelman, Atkinson and Nurse, but they are game or event shots. The association's studio headshots match the other coaches better.

## Prospects: 594 of 655 real photos (was 528); 61 fall back to stock
| Kind | Before | After |
|---|---|---|
| College | 528 of 535 | 535 of 535 |
| High school | 0 of 90 | 37 of 90 |
| International | 0 of 30 | 22 of 30 |

- **Research:** three research agents, one page per player, with the identity checked against school, club or commitment. The records are in `data/overrides/prospect_photos/found_*.json`.
- **Sources:**
  - USA Basketball player pages: 31;
  - Wikimedia Commons, free licences, credited: 17;
  - MaxPreps: 6;
  - school athletics rosters (Temple, McNeese, UConn, Wright State, Houston, Illinois): 7;
  - ABA League: 2;
  - Paris Basketball, NKL / Zalgiris and South East Melbourne Phoenix: 1 each.
  - Removed in review: Diego Niebla's photo came from acb.com, whose robots.txt blocks Claude-User and ClaudeBot. He falls back to a stock face, with the reason in the manifest. `fetch_real_headshots.py` now skips robots-blocked hosts (`ROBOTS_BLOCKED_HOSTS`).
- **Look:** each photo is cut out from its background, greyscale, and framed like ESPN's headshots (`scripts/stock_headshot.swift`), so it matches the college photos.
- **Rights:** non-Commons photos are marked `reference_only_not_cleared`.
- **Not found (61):**
  - 53 high-school players, with no photo page that names them (On3, Rivals and 247Sports block scripted access);
  - 5 international players, plus Diego Niebla (photo dropped, see above);
  - 2 whose only photo had no usable face (Cheickh Niang, Marc-Owen Fodzo Dada).
  - All 61 fall back to the stock library, recorded as `fallback_stock` with the reason.
- **Notes:**
  - Some high-school players are minors. Their photos are public recruiting and USA Basketball headshots, used as the user asked.
  - A few photos are action shots: Spratt with a trophy, Karutasu and Djako with another player at the edge.

## Stock library (`gui/assets/headshots/stock/`)
- **Contents:** 393 photos, 2.5 MB, all from Wikimedia Commons.
  - staff, men: 192 (37 tagged older);
  - staff, women: 139 (8 tagged older);
  - prospects: 62 young men.
- **Format:** each photo is cut out, greyscale and 260 px AVIF in ESPN framing, about 6 KB.
- **Sources:** the Wikimedia Commons API: professional headshots, the "Portrait photographs of men / women" categories, and Unsplash / Pexels / Pixabay imports.
- **Licences:** CC BY-SA 270, CC0 59, CC BY 49, public domain 15. Author, licence, licence link and source page for each photo are in `credits.json`.
- **Openverse removed (robots.txt decision):** an earlier run also used the Openverse API.
  - Its robots.txt disallows `/v1/images/` for every user agent and the whole site for `anthropic-ai`, and the project rule is to respect robots.txt.
  - All 86 Openverse photos were removed: 42 staff men, 29 staff women and 15 prospects; their files, manifest entries and credits are gone.
  - The Openverse search code is gone from `scripts/build_stock_faces.py`, and publish skips any candidate found through it (`EXCLUDED_SOURCES`).
  - Wikimedia Commons stays: its API is meant for scripted use under its User-Agent policy.
  - After the removal the groups were renumbered (no gaps).
- **How the photos were chosen:**
  - Machine checks in `scripts/build_stock_faces.py`: exactly one clear face, head not turned or tilted, enough resolution, and a clean cut-out with the shoulders reaching the bottom edge.
  - Human review of numbered contact sheets: one code per face for gender and age band. Rejected were minors, famous people, costumes and glamour shots, watermarks, vintage photos, uniforms, and repeat photos of one person. The review is in `data/overrides/stock_face_review.json`.
  - Notable-person check: a name in the title with a person article on English Wikipedia, or a photo from a political or official account, is rejected.
  - Commons photos of named people that any Wikipedia article uses are skipped at search time.
- **Gender:** tagged by eye on the sheets. Names are drawn from the face's gender list, as before, and the tests check that names and faces always agree.
- **Prospect faces:** young athletes were scarce. The 62 prospect photos include 26 young adult men moved from the staff pool (in two passes) so that a 60-player generated class has no repeated face.
- **Size and repeats:** modest on purpose, per the coordinator (it may be replaced by generated faces).
  - In a new league the employed staff never share a face.
  - Women never repeat: 34 women in the league and market, against 139 photos.
  - With the staff market listed, there are 216 made-up men against 192 men's photos, so 22 photos appear twice (one three times). The repeats are between employed staff and market candidates. The coordinator accepted this until the generated faces arrive.
- **Fetching:** one request at a time per host, everything cached in `output/headshots-v2/`, Wikimedia's standard thumbnail sizes, every 2 s.

## Career stages (coordinator request)
- `stock/manifest.json` has `faces`: each face is one fictional person, `{"gender", "stages": [{"min_age", "file"}, ...]}`.
- `faces.face_url(face_id, age=...)` shows the last stage whose `min_age` is at or below the person's age; with no age, the first stage. A stock photo is one stage at `min_age` 0.
- Staff pictures refresh to the right stage whenever faces are ensured: save creation, load repair, firing and the season roll.
- `faces.stage_url(url, age)` moves any stored library URL to the right stage. Prospect pictures use it.
- Tested with a three-stage example (rookie 0, prime 26, veteran 36).
- **Not wired:** drafted players' pictures do not yet re-stage as they age. The player payloads would call `faces.stage_url(player["headshot_url"], player["age"])`. That is the hook for the generated-face trial.

## GUI
- **Settings > Photo credits:** a new view in the house table style (double-rule header, alternating rows, row hover, sorted-column shading, bottom-aligned headshot filling the row).
  - It lists all 393 stock photos and the freely licensed real photos (22 coaches, 17 prospects), each with photographer, licence and source links. It is sortable by use, photo, author and licence.
  - Reference-only real photos are counted by source in one line.
  - The CC BY / CC BY-SA "changes made" note (cut out, cropped, greyscale) is in `credits.json`.
- **Staff faces** use cover / bottom framing, so the landscape cut-outs fill the near-square portrait slots.
- **Cache:** `index.html` asset versions are bumped to `headshots-v2`.
- **Older saves:** a face pointing at the retired cartoon library is replaced by a stock photo of the same gender on load, keeping the name. Prospects with a stale picture get a new one when shown.

## Screenshots (`output/headshots-v2/`)
- Taken at a 1440-wide layout in the app's browser pane (it scales the page down, so detail is soft); new save, Celtics:
  - `screens/staff_window_1440.jpg` and `screens/staff_window_zoom.png`: Joe Mazzulla's real photo; made-up staff with matching names (Ebony Rice, Erin Murphy, Tamika Perry); the market list.
  - `screens/coach_card_1440.jpg`: Ebony Rice, performance lead.
  - `screens/draft_board_upcoming_prospects_1440.jpg` and `screens/draft_board_zoom.png`: the Upcoming Prospects board, with Stefan Joksimovic and Hugo Yimga-Moukouri on their new photos.
  - `screens/prospect_card_1440.jpg`: Hugo Yimga-Moukouri.
  - `screens/photo_credits_1440.jpg`.
  - These screenshots predate the Openverse removal: some faces shown there are no longer in the library.
- `contact_sheet.jpg`: 48 random library faces, labelled with their id.

## Tests
- **`tests/test_headshots.py`: 18 OK.** New and changed tests check that:
  - every face is a photo (only AVIF or JPEG under `headshots/`, no `generated/` folder, no cartoon build script);
  - names and faces always share a gender;
  - in a league's made-up staff plus market (the 30 head coaches are real, as in a new save), a face repeats only once every photo of that gender is in use;
  - every real coach has a real photo;
  - every stock photo has a credit with an allowed licence and its file;
  - the library manifest matches its files and stages;
  - career stages pick by age;
  - retired cartoon faces in old saves are replaced;
  - at least 580 real prospects have their own photo;
  - the library holds at least 300 staff photos (Commons only).
- **`tests/photo_credits.test.cjs` (new):** the credits view lists every stock photo and every freely licensed real photo, and uses the house table style.
- **JS:** all 44 `tests/*.test.cjs` pass. `startup_video.test.cjs` needs the git-ignored movie symlinked into the worktree.
- **Core suite:** `bash scripts/run_core_tests.sh`: 338 OK (2 skipped). **GUI and focused:** `test_gui_concept71`, `test_gui_concept74`, `test_staff_lifecycle`, `test_real_prospects`, `test_draft_boards`, `test_prospect_identifiers`, `test_headshots`: 87 OK.

## What's left
- **61 prospects without a real photo:**
  - 53 high-school players. 247Sports and On3 have photos but block scripted access; adding them by hand in a browser would cover most.
  - 8 international players.
- **Reference-only photos:** the 8 association coach photos and the non-Commons prospect photos are not cleared for redistribution. This is fine for the private beta; recheck before any public release.
- **Re-staging drafted players** by age (the hook is above).
- **Stock library size:** modest. A few made-up men repeat once the staff market is listed (192 men's photos against about 216 men). If the generated-face trial is not adopted, more photos can be added with `build_stock_faces.py` (download, process, sheet, review, notable, publish).
- **Old `scripts/fetch_real_headshots.py --coaches`:** a rerun would not undo the 8 association photos (it skips coaches that already have a real photo).

## Resume state
- [x] Merge HEADSHOTS branch, worktree symlinks
- [x] 8 coaches from the coaches' association -> 30 of 30
- [x] Prospects: 67 more real photos (595 of 655)
- [x] Stock library: 479 reviewed photos, credits, notable check
- [x] Career-stage manifest and faces.py
- [x] Open Peeps library and build scripts removed
- [x] Photo credits view, CSS, tests
- [x] Screenshots, contact sheet, report
