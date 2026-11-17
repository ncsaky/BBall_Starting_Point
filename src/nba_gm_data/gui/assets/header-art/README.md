# Header Artwork Sources

The game loads only the lossless WebP files in `../game-art`. This folder retains
the source photographs, reviewed transparent cutouts, and 1024-pixel dot-press
masters for later adjustments. See `../game-art/CREDITS.md` for source links,
attribution, derivative licenses, and photographs still requiring clearance
before public distribution.

The photo-matting pipeline is offline. It neither contacts an image service
during gameplay nor synthesizes photographs. The six fictional coach portraits
are original generated artwork stored in `sources/coach-portraits-sheet.png`;
they do not depict real people. The matting model produces a foreground mask;
closed-form matting follows the source edges. Object illustrations are original
Pillow drawings converted through the same dot-press function.

## Rebuild

In a separate image-processing environment with Pillow, NumPy, SciPy, PyMatting,
and `rembg[cpu]==2.0.85` installed:

```sh
python scripts/build_header_artwork.py --fetch
U2NET_HOME=/path/to/cached/models python scripts/build_header_artwork.py --segment
python scripts/build_header_artwork.py
python scripts/build_game_artwork.py
```

The segmentation step needs the BiRefNet general-lite weights, downloaded by
rembg on its first run unless already cached. Review `artifacts/header-art` on
both light and dark backgrounds before repackaging any modified cutouts.

The original Curry, Chicago Rodman and trade-tool exports are read unchanged
from `../dot-press/exports`. Their reviewed masks are not regenerated here.
