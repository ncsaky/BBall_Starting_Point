# Dot press photographic study, refined cutouts

These are isolated review concepts, not production game artwork. All exports are
1024 x 1024 RGBA PNGs. Background removal uses non-generative BiRefNet foreground
segmentation, local manual separation at overlapping players, and closed-form
alpha matting. Edge colors are decontaminated against the original background;
opaque interiors remain from the source photographs. No generative
image model, invented faces, reconstructed limbs, or drawn human figures are used.
Cropping, resizing, tonal normalization and halftone conversion were performed
locally. Source photographs remain unmodified in `sources/`.

Reviewed source-resolution cutouts are retained in `cutouts/`. The export script
uses those cutouts; the old polygons now preserve framing only. The game has no
segmentation dependency and does not run any model. Offline processing uses
rembg (https://github.com/danielgatis/rembg) and PyMatting
(https://github.com/pymatting/pymatting). Original motion blur and source-photo
resolution still limit fine detail; no synthetic detail has been added.

## Stephen Curry: Finals jumper
- Source: https://www.nba.com/warriors/gallery/20170601
- Image: https://cdn.nba.com/teams/legacy/www.nba.com/warriors/sites/warriors/files/getty-images-691335036.jpg
- Source gallery: Golden State Warriors, Game 1 of the 2017 NBA Finals.
- Source credit: Getty Images; exact individual photographer not verified.
- Reuse license not established. Reference study only; obtain permission before
  shipping this image or its derivatives in the game. Halftoning does not remove
  that requirement.

## Dennis Rodman: Detroit rebound
- Source: https://www.sneakerfreaker.com/features/the-evolution-of-dennis-rodmans-sneaker-style
- Image: https://cdn.sanity.io/images/c1chvb1i/production/9f1d7f9100cc7bc0725f92ca8a3ee440f2423271-1100x735.jpg
- Photograph shows Rodman in Detroit uniform securing the ball in the air.
- Photographer and reuse license not verified. Reference study only; obtain
  rights-holder permission before production use.

## Dennis Rodman: Chicago rebound
- Source: https://www.sohu.com/a/723903184_121124692
- Image: https://p4.itc.cn/q_70/images03/20230927/69d699d4ca944e57bfdeed359111250b.png
- Photograph shows Rodman in Chicago uniform with the ball, airborne.
- Original photographer and reuse license not verified. Reference study only;
  obtain rights-holder permission before production use.

## Ray Allen: shooting-motion alternative
- Source: https://commons.wikimedia.org/wiki/File:Allen_jump_shot.jpg
- Image: https://upload.wikimedia.org/wikipedia/commons/7/75/Allen_jump_shot.jpg
- Photographer: orangetaki, 2 January 2009.
- License: Creative Commons Attribution-ShareAlike 2.0 Generic:
  https://creativecommons.org/licenses/by-sa/2.0/
- Source: https://www.flickr.com/photos/orangetaki/3283745241/
- This is a PRE-GAME warmup photograph, not an in-game attempt. Included as an
  explicitly labeled alternative for the clean, recognizable shooting motion.
- The Allen cutout and halftone derivatives retain CC BY-SA 2.0. Credit the
  photographer, link the source and license, and disclose these edits when used.
- The original ball has motion blur; it has not been redrawn or sharpened into
  an invented replacement.

## Trade builder and trade finder
- Original project SVG object illustrations from the first image study.
- Same approved compositions: exchange of jersey cards and magnified jersey card.
- Re-rendered on transparent square canvases and dot-pressed at three densities.
- No third-party photographic material in these two assets.

## Use across simulated seasons
The historical athletes are category illustrations, not portraits of fictional
players or claims that a legend is currently on a simulated roster. Their credits
should remain accessible wherever these assets are ultimately shipped.

## Variants
- `photo`: isolated photographic cutout, or original rendering for tool assets.
- `fine`: 3.2-pixel dot pitch.
- `press`: 5.2-pixel dot pitch.
- `coarse`: 8-pixel dot pitch.
- `silver`: dark ink for light surfaces.
- `ink`: light ink for dark surfaces.

Transparent pixels contain no crowd, court, opponents or rectangular matte.
The square canvas is constant; compact airborne poses are scaled down slightly
to avoid outsized heads and bodies relative to extended shooting poses.
