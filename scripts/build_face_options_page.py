"""Builds output/headshots/options.html: sample sheets of the face styles (scripts/build_face_library.mjs --sample) plus the real photos. Usage: python3 scripts/build_face_options_page.py <repo root>"""
import html
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
samples = root / "output" / "headshots" / "samples"
real = root / "src" / "nba_gm_data" / "gui" / "assets" / "headshots" / "real"
NOTES = {
    "open-peeps": ("Option A: Open Peeps (built in as the default)",
                   "Hand-drawn ink line art with flat colour. Public domain (CC0), so no credit line and no conditions. "
                   "The black ink outline matches the game's newspaper and ink look. 2,000 faces built: 640 men and 260 women "
                   "for staff (about a quarter with grey hair, given to older staff), 1,100 young men for prospects."),
    "avataaars": ("Option B: Avataaars",
                  "Smooth flat cartoon faces; staff wear blazers and sweaters, prospects hoodies and tees. Free for personal "
                  "and commercial use under its own licence (not a Creative Commons licence). The most 'app avatar' looking."),
    "personas": ("Option C: Personas",
                 "Simple rounded flat faces with soft colours. CC BY 4.0: allowed, but the game must show a credit to "
                 "Draftbit somewhere (for example an About or Credits screen). Fewest hair and face variations of the three."),
}
sections = []
for style in ("open-peeps", "avataaars", "personas"):
    meta = json.loads((samples / style / "sample.json").read_text())
    cards = []
    for face in meta["faces"]:
        svg = (samples / style / face["file"]).read_text()
        role = "Prospect" if face["id"].startswith("prospect") else "Staff"
        label = f"{role} · {'woman' if face['gender'] == 'female' else 'man'}{' · grey hair' if face.get('senior') else ''}"
        cards.append(f'<figure><div class="face">{svg}</div><figcaption>{html.escape(label)}</figcaption></figure>')
    title, note = NOTES[style]
    lic = meta["licence"]
    sections.append(
        f'<section><h2>{html.escape(title)}</h2><p>{html.escape(note)}</p>'
        f'<p class="lic">Licence: <a href="{html.escape(lic["url"])}">{html.escape(lic["name"])}</a> · {html.escape(lic["source"])}</p>'
        f'<div class="grid">{"".join(cards)}</div></section>'
    )

manifest = json.loads((real / "manifest.json").read_text()) if (real / "manifest.json").exists() else {}
coach_cards = []
for entry in sorted((manifest.get("coaches") or {}).values(), key=lambda e: e["name"]):
    if entry.get("status") != "real_photo":
        continue
    rel = "../../src/nba_gm_data/gui" + entry["file"]
    coach_cards.append(f'<figure><div class="photo"><img src="{rel}" alt="" loading="lazy"></div><figcaption>{html.escape(entry["name"])}<br><small>{html.escape(str(entry.get("licence") or ""))}</small></figcaption></figure>')
prospect_cards = []
for entry in list((manifest.get("prospects") or {}).values()):
    if entry.get("status") == "real_photo" and len(prospect_cards) < 24:
        rel = "../../src/nba_gm_data/gui" + entry["file"]
        prospect_cards.append(f'<figure><div class="photo"><img src="{rel}" alt="" loading="lazy"></div><figcaption>{html.escape(entry["name"])}</figcaption></figure>')

page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Face Library Options</title>
<style>
:root {{ --bg:#f4f5f7; --ink:#1d2430; --muted:#5b6472; --card:#fff; --line:#d9dde3; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#14181f; --ink:#e8ebf0; --muted:#9aa3b2; --card:#1d232c; --line:#2c3440; }} }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 -apple-system,Helvetica,Arial,sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:24px 16px 60px; }}
h1 {{ font-size:24px; margin:0 0 6px; }} h2 {{ font-size:18px; margin:28px 0 4px; }}
p {{ margin:4px 0; max-width:70ch; }} .lic {{ color:var(--muted); font-size:13px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(120px,1fr)); gap:10px; margin-top:12px; }}
figure {{ margin:0; background:var(--card); border:1px solid var(--line); border-radius:8px; padding:8px; text-align:center; }}
.face svg {{ width:100%; height:auto; display:block; }}
.photo {{ aspect-ratio:3/4; overflow:hidden; border-radius:4px; background:#e4e8eb; }}
.photo img {{ width:100%; height:100%; object-fit:cover; object-position:top; }}
figcaption {{ font-size:12px; color:var(--muted); margin-top:4px; }}
.tldr {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 16px; margin:12px 0; }}
</style></head><body><main>
<h1>Face library options for made-up staff and prospects</h1>
<div class="tldr"><p><strong>Pick one style.</strong> Option A (Open Peeps) is built into the game now; switching to B or C is one
command (<code>node scripts/build_face_library.mjs --style avataaars</code>, then set <code>LIBRARY</code> in
<code>src/nba_gm_data/faces.py</code>). Every face has one gender, and made-up staff get a name from the same gender's list.
Real coaches and real college prospects use their real photos (below); everyone else gets a face from the chosen style.</p></div>
{''.join(sections)}
<section><h2>Real head coaches (Wikimedia Commons, free licences)</h2><p>{len(coach_cards)} of 30 found; the rest use a made-up face until a freely licensed photo turns up.</p><div class="grid">{''.join(coach_cards)}</div></section>
<section><h2>Real prospects (ESPN college rosters, sample)</h2><div class="grid">{''.join(prospect_cards)}</div></section>
<p class="lic">No AI-generated photo set is offered: the well-known ones (NVIDIA StyleGAN faces, Generated Photos) are, as far as I know, non-commercial or attribution-restricted, and they were not re-checked online for this pass. Photos of real people are never used for made-up characters.</p>
</main></body></html>"""
(root / "output" / "headshots" / "options.html").write_text(page)
print("wrote options.html", len(page) // 1024, "KB")
