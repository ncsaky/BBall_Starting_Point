# Fictional headshot library

## TL;DR

- Batch 1 has reached a checkpoint with 9 fictional people and 27 approved portraits.
- Each approved portrait has a full-size PNG and a 320 × 320 game JPEG.
- The next person is staff-m/0010.

## Batch 1 · November 21, 2026

| Staff men | Staff women | Players | Accepted portraits | Redone stages | Elapsed wall time |
|---:|---:|---:|---:|---:|---:|
| 9 / 30 | 0 / 12 | 0 / 20 | 27 | 1 | About 16 min |

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

## Resume

Continue at `staff-m/0010`. Work in order through 30 staff men, 12 staff women and 20 male players. Review each person before starting the next. Commit every three accepted people. The manifest records the exact accepted prompts and cutover ages. Rebuild the contact sheet with `python3 scripts/build_headshot_library_contact_sheet.py`. PNGs, JPEGs and the HTML stay in the ignored output directory.
