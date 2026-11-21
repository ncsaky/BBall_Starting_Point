#!/usr/bin/env python3
"""Build the local colour and greyscale comparison from the library manifest."""

import json
from html import escape
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/research/headshot_gen_library_manifest.json"
OUTPUT = ROOT / "output/headshots-gen-library"
PLAYER_STAGES = ("Rookie", "Prime", "Veteran", "Late career")
STAFF_STAGES = ("Early career", "Mid-career", "Late career")


def portrait(person_id, stage_number, stage, label):
    caption = f"{label} · {stage['age']} (from age {stage['min_age']})"
    if stage_number == 1:
        caption = f"{label} · {stage['age']}"
    game_file = Path("game") / stage["file"]
    original_file = Path(person_id) / f"stage{stage_number}.png"
    for path in (game_file, original_file):
        if not (OUTPUT / path).is_file():
            raise FileNotFoundError(OUTPUT / path)
    game_url = quote(game_file.as_posix())
    original_url = quote(original_file.as_posix())
    description = escape(stage["changes"], quote=True)
    return (
        f'<figure title="{description}"><a href="{original_url}">'
        f'<img src="{game_url}" alt="{escape(caption)} headshot"'
        ' width="320" height="320" loading="lazy"></a>'
        f"<figcaption>{escape(caption)}</figcaption></figure>"
    )


def build_contact_sheet():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    sections = []
    for person in manifest["people"]:
        labels = PLAYER_STAGES if person["role"] == "player" else STAFF_STAGES
        cards = "".join(
            portrait(person["id"], number, stage, label)
            for number, (stage, label) in enumerate(
                zip(person["stages"], labels, strict=True), start=1
            )
        )
        title = escape(person["id"])
        sections.append(
            f'<section><h2>{title}</h2><div class="row" aria-label="Colour">{cards}</div>'
            f'<div class="row grey" aria-label="Greyscale">{cards}</div></section>'
        )

    page = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Headshot library contact sheet</title>
<style>
  body { max-width: 50rem; margin: auto; padding: 1.25rem; color: #171c24;
         background: #f8fafc; font: 1rem system-ui, sans-serif; }
  h1 { margin: .5rem 0; }
  h2 { margin: 0 0 .55rem; font-size: 1.1rem; }
  section { border-top: 1px solid #d0d6df; padding: 1rem 0; }
  .row { display: flex; gap: .55rem; margin-bottom: .6rem; }
  figure { flex: 0 1 11.25rem; min-width: 0; margin: 0; }
  img { display: block; width: 100%; height: auto; aspect-ratio: 1;
                  border-radius: .3rem; background: #e3e7ec; }
  .grey img { filter: grayscale(1); }
  figcaption { font-size: .8rem; margin: .25rem 0; }
</style>
<h1>Fictional headshots</h1>
<p>Game-size portraits in colour and greyscale. Select a portrait to open the original.</p>
"""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "contact_sheet.html").write_text(
        page + "\n".join(sections) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    build_contact_sheet()
