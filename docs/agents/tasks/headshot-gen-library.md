# Fictional headshot library

## TL;DR

- Batch 1 has started with three fictional staff men. Nine portraits passed visual review.
- Each person has full-size PNGs and 320 × 320 game JPEGs. The contact sheet compares colour and greyscale.
- The next person is staff man 0004. The target is 30 staff men, 12 staff women and 20 players, in that order.

## Batch 1

First checkpoint on November 21, 2026. Three people, nine PNGs, nine JPEGs, zero image redos. Checked the full age row for identity, visible aging, framing and unwanted marks. Corrected the JPEG crop during setup and rechecked all six affected copies.

## Resume

Continue at staff man 0004. Save accepted portraits under `output/headshots-gen-library/`. The JSON manifest records accepted ages, cutover ages, changes and exact prompts. Use `python3 scripts/build_headshot_library_contact_sheet.py` to refresh the contact sheet. Commit every three accepted people. Use the built-in image tool with synthetic references only.
