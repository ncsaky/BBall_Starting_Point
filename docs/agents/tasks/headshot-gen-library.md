# Fictional headshot library

## TL;DR

- Batch 1 has reached a checkpoint with 42 fictional people and 126 approved portraits.
- Each approved portrait has a full-size PNG and a 320 × 320 game JPEG.
- The next person is player-m/0001.

## Batch 1 · November 21, 2026

| Staff men | Staff women | Players | Accepted portraits | Redone stages | Elapsed wall time |
|---:|---:|---:|---:|---:|---:|
| 30 / 30 | 12 / 12 | 0 / 20 | 126 | 1 | About 62 min |

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
- staff-m/0016. Consistent glasses, nose and shaved scalp. Beard graying and relaxed lower cheeks distinguish the later stages.
- staff-m/0017. Bent smile and strong cheekbones stay distinct. The loose curls, deeper lines and grey shadow mark the oldest stage.
- staff-m/0018. Recognizable cheekbones and chin through all stages. Hair and glasses change more than facial structure.
- staff-m/0019. Distinct cheekbones, chin and brows are steady. Grey ponytail and moustache distinguish the last age.
- staff-m/0020. Smile and eye shape carry through. Beard length changes at each stage, with grey across the top at 62.
- staff-m/0021. The wide blue eyes and mouth stay steady. Greying and clearly stronger age lines distinguish the last portrait.
- staff-m/0022. Eyes, chin and brows carry the likeness through the final shave. Hair recession and deeper eyelid folds show aging.
- staff-m/0023. Smile, cheeks and nose match. Later shorter hair and a silver moustache show the changes.
- staff-m/0024. Freckles, chin and eye spacing hold through a changing side part and heavier glasses.
- staff-m/0025. Wide nose, brow and chin remain recognizable through three hair and beard styles.
- staff-m/0026. Low eyes and nose shape hold steady as the hair recedes and the moustache greys.
- staff-m/0027. Eyes and cheekbones keep the face recognizable through a cut and later glasses.
- staff-m/0028. Eyes, lips and round outline keep the likeness clear through a shave and round glasses.
- staff-m/0029. Narrow profile and chin notch stay the same. Kept the short cut throughout and let grey and age lines do most of the work.
- staff-m/0030. Same smile and facial proportions; strong greying and deeper eye lines by the last stage.
- staff-f/0001. Eyes, cheekbones and smile hold through a modest change in curls. Grey and eye lines read most strongly at 62.
- staff-f/0002. Eyes, freckles and smile are consistent through shorter hair, greying and visible cheek and neck lines.
- staff-f/0003. Chin and eye spacing are consistent. Strong silvering, lines and glasses distinguish the last stage.
- staff-f/0004. The face stays recognizable through bob and longer silver-streaked hair. Later smile lines are visible.
- staff-f/0005. Eyebrow shape, nose and unusual eye spacing still read clearly after the release of shoulder-length silver hair.
- staff-f/0006. The big smile, eyes and cheeks stay distinctive. Greyer twists, glasses and neck creases make the late stage clear.
- staff-f/0007. Bent nose, brows and face shape remain distinct as the short hair and glasses change.
- staff-f/0008. Nose, chin and smile carry the likeness from loose hair to an updo and then a short silver cut.
- staff-f/0009. The mouth, eyes and cheek structure carry across a high updo and short grey curls.
- staff-f/0010. Wide-set eyes, cheekbones and lower lip are steady. The braid gives way to a loose silver-grey style.
- staff-f/0011. Chin dimple, freckles and eye shape stay stable. Eyes and lower face show visible age lines beyond the hair and glasses.
- staff-f/0012. Same curved nose, eye spacing and arched brows. The older face has visible lines and a shorter silver crop.

## Resume

Continue at `player-m/0001`. Work in order through 30 staff men, 12 staff women and 20 male players. Review each person before starting the next. Commit every three accepted people. The manifest records the exact accepted prompts and cutover ages. Rebuild the contact sheet with `python3 scripts/build_headshot_library_contact_sheet.py`. PNGs, JPEGs and the HTML stay in the ignored output directory.
