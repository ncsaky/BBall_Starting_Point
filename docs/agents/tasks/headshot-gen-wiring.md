# HEADSHOT-GEN-WIRING: generated faces in the game, aging with the career

Owner: Claude (Opus agent), branch `worktree-agent-a133e49518fcb03f4`. Board row: HEADSHOT-GEN-WIRING. Status: **review**.

## TL;DR
- Made-up coaches, staff and draft prospects now get the AI-generated faces first. Stock photos are used only once every generated face of that gender and kind is taken. Real coaches, real prospects and NBA players keep their real photos.
- Faces age: every made-up person shows the image for their current age. A drafted made-up player starts on his rookie photo and moves to his prime, veteran and late-career photos as the seasons pass.
- Settings > Photo credits now says these faces are AI-generated fictional people (no real person depicted), made with OpenAI's image tool, as one group.

## What changed
**Images.** `scripts/build_generated_faces.py` copies Codex's game JPEGs into `gui/assets/headshots/generated/<group>/NNNN-sK.avif`.
- 222 images of 66 people, as 260 px AVIF: 1.05 MB in total, against 6.1 MB of JPEG. Side by side at game size there is no visible difference.
- It also writes `generated/manifest.json` in the format `faces.py` reads (groups with gender and count; faces with stages and `min_age`).
- Game face ids get a "gen-" prefix (`gen-staff-m/0001`), so they never clash with stock ids.
- For later batches, re-run it. It converts only new or changed images and drops images that are no longer listed:
  `python3 scripts/build_generated_faces.py --source <Codex worktree>/output/headshots-gen-library/game`.
- A test fails if Codex's manifest lists people the game does not have yet. That is the reminder to re-run.

**Who gets which face** (`faces.py`):
- Staff men draw generated men, then stock men. Staff women draw generated women, then stock women.
- Made-up prospects, and real prospects with no photo, draw generated player faces, then stock prospect faces.
- The existing rules still hold: no repeated face in a draft class, none among the league's employed staff while unused faces remain, and names always match the face's gender. Stock photos still pick older-looking faces for older staff. Generated faces don't need that, because they age.
- In a new league, employed staff are given faces in this order: the user's own staff first, then the rest of the league in a fixed shuffled order. So with only 42 generated staff faces, they spread across teams instead of filling the first teams in the list.
- In a new Celtics save, all 5 made-up Celtics staff have generated faces. 42 generated faces are spread over 24 teams, and the other 108 made-up staff have stock photos.
- **Draft classes with real prospects** (`draft.py`): the made-up prospects in those slots used to keep the face from an all-made-up draw. That put the lower slots on stock photos while generated faces sat unused. Their faces are now picked again within the real class. In a new save, all 9 made-up prospects on the board have generated faces (they had stock photos before).

**Aging.**
- When a save's player ages are worked out (`save.py`, `canonical_with_save`, straight after `apply_effective_player_ages`), each made-up player's stored face is moved to the image for his age.
- Every display reads from there: player rows, the player card, rosters, box scores, awards, trades and the league wire.
- NBA headshots and real photos are left alone. Nothing is written into the save, and no game value reads the picture.
- Staff already re-stage when their faces are refreshed (save creation, load, the season roll). Prospects re-stage when shown.

**Credits.** The view fetches the generated manifest and adds one line that counts people and portraits. There are no per-image rows. If the manifest is missing, the view still works.

**Other.**
- `pyproject.toml` package data now includes the generated folder (needed for the beta ZIPs).
- `index.html` loads `app.js?v=headshot-gen-1`.

## Game outcomes
Face picks use stable hashes of each person's key and never touch a game random stream. Only display fields change (`face_id`, `headshot_url`, `headshot_source`). No names change in a new save: the names are already unique, so no renames happen. The core suite passes.

## Tests
- `tests/test_headshots.py`: 23 OK (5 new, 6 updated). The new tests check that:
  - every listed fictional person is in the game with all stages;
  - each stage shows from its `min_age` exactly, and a stored face moves forward and back with age;
  - generated faces are used before stock for both genders, and genders still match;
  - a new league spreads generated staff faces, with the user's staff first;
  - a drafted made-up player built by the real rookie-record code shows every career stage from 2031 to 2050, ending on the late-career image, while an NBA player's headshot stays unchanged. The test also checks that the save's player-building code applies the stage right after the ages.
  - The draft-class test also checks that generated faces fill before stock, for 2027 real classes (seeds 7 and 9) and a 2031 made-up class.
- `tests/photo_credits.test.cjs`: 4 OK, including the new group line and a check that the view works without the manifest.
- `tests/test_real_prospects.py`: one assertion now ignores `headshot_url`, because the face is picked again within the real class.
- **All JS tests:** 325 OK (after linking the git-ignored startup movie into the worktree).
- **Focused tests:** staff lifecycle, real prospects, draft boards, prospect identifiers, GUI concept 71/74: OK.
- **Core suite** (`run_core_tests.sh`): 338 OK, 2 skipped. It ran before the draft change, and again after it (result in "Resume state").

## Live check (not done as asked)
- The preview tool reads only the main checkout's `.claude/launch.json`. Its "gui-preview" entry would run the main checkout's code, not this branch.
- Starting this worktree's server from the shell was refused by the permission system.
- So there are no screenshots of the staff window or draft board.
- Instead, `output/headshots-gen-wiring/` holds:
  - `new_save_faces.json`: an in-process new Celtics save (staff faces and draft board faces, as above);
  - `drafted_player_career_stages.png`: one player at 20, 26, 31 and 35;
  - `staff_stages.png`.
- The coordinator can take the screenshots after merging, with the normal preview.

## Notes and what's left
- **Sizes:** 24 generated player faces cover the made-up prospects of one class (a fully made-up class has 60). The faces repeat from class to class, as the stock ones already did. More Codex batches (batch 2 is players first) shrink this.
- **Looks:** in the staff window every face is shown in greyscale (existing CSS), so generated and real photos match there. On draft boards and rosters the generated faces show in colour, with their light-grey studio background. The real prospect photos there are greyscale cut-outs, and NBA headshots are colour cut-outs. If the mix looks off, the build script could cut out the background, or turn the faces greyscale, the way the stock photos were made (`scripts/stock_headshot.swift`).
- Old saves are not migrated (as agreed). Their made-up staff keep their stock faces, because a valid face is never replaced.

## Resume state
- [x] Board row, worktree symlinks
- [x] Build script and generated library
- [x] `faces.py`, `save.py` hook, `draft.py` real-class re-pick
- [x] Credits line, cache version, package data
- [x] Tests: headshots 23 OK, credits JS 4 OK, all JS 325 OK, focused OK, core 338 OK (pre-draft-change run)
- [x] Core rerun after the draft change: 338 OK, 2 skipped
- [x] Report; board to review; commit on branch
