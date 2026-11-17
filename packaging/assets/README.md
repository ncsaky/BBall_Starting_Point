# Application Icon

An original, hand-drawn vector basketball-and-suit mark for NBA GM Sandbox.
No generated imagery, photographs, stock artwork, or team logos are used.

- `app-icon.svg`: editable 1024-unit source, including fine print dots.
- `app-icon.png`: transparent 1024-pixel master.
- `app-icon.icns`: macOS standard and Retina icon representations.
- `app-icon.ico`: Windows 256-pixel PNG-backed icon, derived from the same master.
- `app-icon-preview.png`: size checks on light and dark backgrounds.

The macOS PyInstaller bundle uses the committed ICNS directly. Building the
game does not require graphics libraries or icon regeneration. The build
manifest includes the ICNS checksum.

To regenerate exports on a Mac, use Node.js with `sharp` available:

```sh
node scripts/build_app_icon.cjs
```

When using a separately installed tooling runtime, set `NODE_PATH` to its
`node_modules` directory. The script uses the system `iconutil` on macOS;
other systems regenerate only the PNG master and preview.

Regenerate the Windows ICO after changing the PNG master:

```sh
node scripts/build_windows_icon.cjs
```

The Windows builder uses the committed ICO and PNG; no image tooling is needed
on the build PC or a friend's PC.
