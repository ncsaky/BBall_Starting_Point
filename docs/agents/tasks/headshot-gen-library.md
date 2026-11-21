# Fictional headshot library

## TL;DR

- Batch 1 has reached a checkpoint with 15 fictional people and 45 approved portraits.
- Each approved portrait has a full-size PNG and a 320 × 320 game JPEG.
- The next person is staff-m/0016.

## Batch 1 · November 21, 2026

| Staff men | Staff women | Players | Accepted portraits | Redone stages | Elapsed wall time |
|---:|---:|---:|---:|---:|---:|
| 15 / 30 | 0 / 12 | 0 / 20 | 45 | 1 | About 24 min |

The approved portraits use the built-in Codex image tool and fictional reference images only. The JPEG conversion initially cropped too tightly. The six affected files were rebuilt and visually rechecked. The game-size contact sheet shows each age in colour and greyscale and links to the full-size original.

### Visual review

- staff-m/0001. Tooth gap and cheekbones stay recognizable. Clear greying and lines at both steps.
- staff-m/0002. Freckles, crooked smile and round face stay clear. The age-50 step is quieter than the age-62 step.
- staff-m/0003. Chin and eyes stay stable with new glasses and greying. Plain clothing and a consistent crop.
- staff-m/0004. Brows, freckles and face shape remain clear. Mid-career aging is mainly eye lines. Late-career beard and forehead lines read well.
- staff-m/0005. Same glasses, smile and brows. Greying moustache, shorter hair and softer jaw distinguish the last stage.
- staff-m/0006. Redid stage 3 for clearer early-sixties aging. Nose and cheekbones stay consistent.
- staff-m/0007. Kept the shaved scalp. Facial-hair greying and creases show the age changes.
- staff-m/0008. Blue eyes and wide jaw carry through as his hair recedes. Relaxed expression varies across ages.
- staff-m/0009. Dimple and cheek shape stay recognizable. Grey side part and moustache make the oldest stage read distinctly.
- staff-m/0010. Nose, eyes, freckles and ear shape remain recognizable through a haircut and shave. The moustache returns in the oldest stage.
- staff-m/0011. Eyes and cheekbones stay consistent through loose locs, fuller then shorter beard, and distinct lines.
- staff-m/0012. Frame, nose and brows make for a clear match. Stage 2 adds forehead folds and the moustache. Stage 3 has more age lines and silver hair.
- staff-m/0013. Same eye shape, chin and small smile. The late stage has visibly deeper lines and longer silver curls.
- staff-m/0014. Recognizable nose and eyes across a beard trim and later regrowth. Visible deeper lines at 62.
- staff-m/0015. Square chin, glasses and eye shape carry through. Stage 2 kept the moustache as a subtle bridge to the older face.

## Resume

Continue at `staff-m/0016`. Work in order through 30 staff men, 12 staff women and 20 male players. Review each person before starting the next. Commit every three accepted people. The manifest records the exact accepted prompts and cutover ages. Rebuild the contact sheet with `python3 scripts/build_headshot_library_contact_sheet.py`. PNGs, JPEGs and the HTML stay in the ignored output directory.
