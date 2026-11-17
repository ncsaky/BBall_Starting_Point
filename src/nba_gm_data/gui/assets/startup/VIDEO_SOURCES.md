# Save-screen video sources

The save-screen background plays a bundled, silent, 93.933-second H.264
montage at `video/front-office.mp4` (1280×720, 30 fps; 188,378,704 bytes).
Playback needs no internet connection, remote player, or installed video tools.
Genuine photographic dot-press is baked into the frames: local tone controls
variable ink-dot area on a fine, fixed lattice, with gentle temporal smoothing
and retained fine facial, uniform, ball and net detail.

Chaotic analogue-TV interference is also baked into the movie. At each edit,
it builds over 500 ms of the advancing outgoing picture, passes through a
600 ms static burst, and settles over 500 ms of the advancing incoming picture.
The internal camera cut in the Kings GM interview and the final loop seam
receive the same treatment. The original montage needs no animated dot overlay. Franchise channel changes
use a small shared TV-interference movie rendered with the same effect; the
team loops have their own baked transitions.
Local artwork remains the fallback for missing/corrupt media, autoplay denial,
and reduced-motion preferences.

- NBA, [The Top Plays of the 2025-26 NBA Season | Pt. 1](https://www.youtube.com/watch?v=S6cSohNkms4). Six complete possessions/finishes, including their payoffs and landings/reactions.
- Sacramento Kings, [Inside the Kings Draft Room with Scott Perry](https://www.youtube.com/watch?v=OW-rtBy7RFo). Real draft-room applause, a GM interview, and a staff embrace.
- Denver Nuggets, [Behind the Scenes of an NBA Draft](https://www.youtube.com/watch?v=ErrVf5TFGzk). Real staff interview and draft-day room exchange from complete local cached excerpts.

These publisher links document provenance; they are not used for playback.
Six actions and five logical front-office moments form 12 physical shots
(the interview has two camera angles). Exact source/file boundaries, payoffs,
per-shot crops, source hashes, flash holds and transition timings/envelopes
are recorded in `video/manifest.json`. Important players, ball trajectories,
rims/nets, attribution marks and draft-room captions remain fully framed.
Corner/venue graphics remain where a crop would damage the composition.

The incomplete Nuggets full download was excluded after failed full decoding;
only two complete cached excerpts are used. The earlier Washington Capitals
cross-sport excerpt has been replaced with NBA front-office footage. Only the
edited montage and processed poster are included in the GUI.

`scripts/build_startup_video.py` and `scripts/startup_video_settings.json`
regenerate the exports from reviewed local files using ffmpeg, NumPy and Pillow.
No source search, download or generated people are involved. Authoring tools
and source footage are not needed by players. Review comparisons, exact build
instructions and verification results are in `output/startup-video-refresh/full/`.

Supplied footage is assumed authorized for private friends testing. This source
list is provenance documentation, not evidence of public-distribution rights.


## Reviewed franchise preview reels

All 30 franchises use a reviewed team or player compilation. Each reel contains
six selected-team plays from multiple games and three general front-office scenes.
Two plays alternate with a draft-room or staff scene, for nine shots in a full loop.
Chicago uses the Bulls' own Josh Giddey compilation; Atlanta uses the Hawks' own
Jalen Johnson compilation. The previous mixed-video selections are retired.

The shared office scenes come from the Kings draft room and Nuggets draft-day
footage credited above. They are general GM context rather than franchise-specific
claims. Original Random-team and non-team startup contexts keep the original montage.

Hovering a franchise previews it; clicking selects it. Hovering a compact startup
button only enlarges the button. Clicking opens its full panel, which remains open
until explicitly closed, switched, or dismissed with Escape.

Playback is local, silent, and uses the same dot-press and analogue-TV interference
renderer as the original. A six-scene playlist shares office files between teams.
Only the active video and one incoming scene are loaded, and both are released
when startup closes. No download or remote player runs in the game.

`scripts/startup_team_video_settings.json` records the source URLs, exact intervals,
opponents and reviewed actions. `video/teams/manifest.json` records the exported
playlist. Source-frame review sheets are retained in
`output/startup-team-correction/*-audit.jpg`; original selections and superseded
exports remain there for comparison. Broadcast framing and attribution are preserved.

| Team | Compilation | Selected source intervals (seconds) |
| --- | --- | --- |
| ATL | [Jalen Johnson is an NBA All Star 🌟 2025-26 Season Highlights](https://www.youtube.com/watch?v=wT-Hj5oWu1U) | 2.0–10.5, 25.0–33.5, 68.0–78.0, 79.0–91.0, 99.0–109.0, 169.0–180.0 |
| BKN | [Michael Porter Jr. 2025-2026 Season Highlights](https://www.youtube.com/watch?v=zEgrNFMdXwg) | 2.0–11.0, 13.0–22.0, 58.0–66.0, 23.0–32.0, 139.0–145.5, 184.0–188.5 |
| BOS | [Jaylen Brown – Top Plays of the 2025-26 Season](https://www.youtube.com/watch?v=GVsjpWv5wLo) | 2.0–14.0, 23.0–33.0, 34.0–47.0, 119.0–132.0, 134.0–151.0, 169.0–178.0 |
| CHA | [The Charlotte Hornets Are BUZZING! 🐝 – Top Plays](https://www.youtube.com/watch?v=MwIh--NGGHU) | 0.0–9.0, 17.0–26.0, 59.0–72.0, 94.0–107.0, 119.0–130.0, 183.0–200.0 |
| CHI | [20 minutes of Josh Giddey dropping dimes & getting buckets](https://www.youtube.com/watch?v=yYtzjK0GAKE) | 8.5–17.0, 17.0–28.0, 28.0–38.0, 63.0–70.0, 82.0–92.0, 103.0–112.0 |
| CLE | [Harden & Mitchell Became an INSTANT DUO in Cleveland 🤯 – Top Plays – 2025-26 NBA Season](https://www.youtube.com/watch?v=TjTVx-QEbJA) | 1.0–16.0, 38.0–48.0, 64.0–76.0, 115.5–126.0, 155.0–166.0, 183.0–191.0 |
| DAL | [Cooper Flagg's Rookie Season Highlights Are MUST-SEE – 2025-26 NBA Season](https://www.youtube.com/watch?v=m6RU9K3ezec) | 1.0–11.0, 24.5–37.0, 83.0–96.0, 124.0–137.0, 155.0–165.0, 181.0–189.0 |
| DEN | [Nikola Jokić Makes Everything Look EASY 😮‍💨 – Top Plays – 2025-26 NBA Season](https://www.youtube.com/watch?v=SvoFvBq9jSg) | 0.0–16.0, 18.0–26.0, 54.0–66.0, 84.0–97.0, 109.0–121.0, 142.0–152.0 |
| DET | [Cade Cunningham Top Plays On The Season – 2025 - 2026](https://www.youtube.com/watch?v=p0G1IM3xuas) | 0.0–16.0, 39.0–51.0, 54.0–64.0, 67.0–81.0, 109.0–119.0, 160.0–172.0 |
| GSW | [Golden State Warriors Plays of the Year – 2025-26 NBA Season](https://www.youtube.com/watch?v=qJxK4Ki0XlY) | 2.0–12.0, 13.0–23.0, 38.0–44.0, 54.0–69.0, 92.0–105.0, 144.0–156.0 |
| HOU | [Kevin Durant's BEST PLAYS! – 2026 NBA All-Star Reserve](https://www.youtube.com/watch?v=4I_eosXkS98) | 0.0–17.0, 48.0–58.0, 69.0–86.0, 89.0–102.0, 109.0–122.0, 130.0–144.0 |
| IND | [Pascal Siakam's TOP PLAYS of the 2025-26 NBA Season](https://www.youtube.com/watch?v=nWKqAbI5rVo) | 11.0–20.5, 34.0–40.0, 44.0–51.0, 84.0–94.0, 108.0–115.5, 134.0–145.0 |
| LAC | [Kawhi Leonard Was LOCKED IN This Season 🥶 – Top Plays – 2025-26 NBA Season](https://www.youtube.com/watch?v=RivzZVtPds0) | 0.0–16.0, 58.0–76.0, 79.0–92.0, 104.5–116.0, 130.0–146.0, 173.0–188.0 |
| LAL | [Luka Dončić's BEST Plays from the 2025-2026 Season](https://www.youtube.com/watch?v=x5kjIwZ3-Kw) | 12.0–24.0, 44.0–54.5, 75.0–85.0, 93.0–115.0, 169.0–184.0, 183.0–197.0 |
| MEM | [Ja Morant – Top Plays of the 2025-26 season](https://www.youtube.com/watch?v=wMcxZPbo32E) | 29.0–46.0, 54.0–62.0, 65.0–70.5, 109.0–121.0, 132.0–140.0, 149.0–162.0 |
| MIA | [Bam Adebayo BEST HIGHLIGHTS 25-26 Season](https://www.youtube.com/watch?v=cDDz3lOgDMo) | 23.0–29.0, 168.0–181.0, 186.0–199.0, 201.0–212.0, 233.0–238.5, 292.0–301.5 |
| MIL | [Giannis Antetokounmpo's BEST PLAYS! – 2026 NBA All-Star Starter](https://www.youtube.com/watch?v=em9OfoguUiM) | 0.0–16.0, 65.0–87.0, 89.0–101.0, 147.0–160.0, 186.0–198.0, 123.0–134.0 |
| MIN | [Anthony Edwards Was a PROBLEM All Season 😤 – Top Plays – 2025-26 NBA Season](https://www.youtube.com/watch?v=T5I70wkGVLI) | 0.0–10.0, 24.0–41.0, 44.0–57.0, 69.0–78.0, 110.0–122.0, 140.0–152.0 |
| NOP | [Zion Williamson 2025-26 NBA Season Highlights – New Orleans Pelicans](https://www.youtube.com/watch?v=jpUlLlbhAX0) | 8.0–17.0, 29.0–39.0, 57.0–68.0, 74.0–86.0, 89.0–102.0, 143.0–152.0 |
| NYK | [Jalen Brunson's TOP PLAYS From The 2025 Emirates NBA Cup 🏆 – 2025-26 Season](https://www.youtube.com/watch?v=4Q5dZ400RHo) | 0.0–13.0, 49.0–59.0, 80.0–90.0, 64.0–75.0, 163.0–179.0, 109.0–127.0 |
| OKC | [Shai Gilgeous-Alexander Is The 2025-26 @kia NBA Most Valuable Player!](https://www.youtube.com/watch?v=BzKf9haIml0) | 0.0–16.0, 49.0–59.0, 65.0–82.0, 88.0–108.0, 110.0–124.0, 161.0–174.0 |
| ORL | [TOP 25 PLAYS FROM 25-26 SEASON: PAOLO BANCHERO](https://www.youtube.com/watch?v=ONzDHBUYNGc) | 0.0–12.0, 18.0–33.0, 56.0–65.0, 65.0–78.0, 81.0–101.0, 122.0–134.0 |
| PHI | [Tyrese Maxey Keeps On LEVELING UP – 2025-26 Season Highlights](https://www.youtube.com/watch?v=inpnEbumi2I) | 0.0–5.5, 60.0–68.0, 142.0–154.0, 98.0–107.0, 109.0–114.5, 130.0–141.0 |
| PHX | [Devin Booker Was UNSTOPPABLE This Season 🔥 – Top Plays – 2025-26 NBA Season](https://www.youtube.com/watch?v=nFK9_WsL2lM) | 0.0–17.0, 38.0–49.0, 54.0–65.0, 69.0–89.0, 113.0–128.0, 128.0–148.0 |
| POR | [Deni Avdija's Top Plays – 2025-26 Season – Portland Trail Blazers](https://www.youtube.com/watch?v=OBuu8x54uOQ) | 0.0–7.0, 27.0–38.0, 39.0–49.0, 64.0–71.0, 74.0–81.0, 134.0–143.0 |
| SAC | [DeMar DeRozan BEST HIGHLIGHTS 25-26 Season](https://www.youtube.com/watch?v=svfDl8gpUDE) | 24.0–37.0, 75.0–79.0, 80.0–87.5, 105.5–111.0, 123.0–131.0, 169.0–176.5 |
| SAS | [Victor Wembanyama's Season Highlights Are Simply UNREAL 🤯 – 2025-26 NBA Season](https://www.youtube.com/watch?v=-Q-KO1VBJAY) | 0.0–18.0, 42.0–52.0, 63.0–72.0, 108.0–120.0, 139.0–156.0, 159.0–177.0 |
| TOR | [Scottie Barnes' BEST PLAYS! – 2026 NBA All-Star Reserve](https://www.youtube.com/watch?v=5LAdiUKlgaQ) | 0.0–13.0, 19.0–33.0, 44.0–58.0, 74.0–83.0, 98.0–108.0, 155.0–175.0 |
| UTA | [TOP PLAYS of the 2025-26 Season 😱🤩 – UTAH JAZZ](https://www.youtube.com/watch?v=UDWy05T7a8g) | 4.0–16.5, 17.0–28.0, 28.0–42.0, 118.0–130.0, 130.0–145.0, 149.0–160.0 |
| WAS | [Alex Sarr Highlights from the 2025-26 Season](https://www.youtube.com/watch?v=KH8yplVJIsc) | 0.0–10.0, 16.0–25.0, 28.0–37.0, 84.0–91.0, 104.0–111.5, 114.0–126.0 |
## Reviewed franchise preview reels

All 30 franchises use a reviewed team or player compilation. Each reel contains
six selected-team plays from multiple games and three general front-office scenes.
Two plays alternate with a draft-room or staff scene, for nine shots in a full loop.
Chicago uses the Bulls' own Josh Giddey compilation; Atlanta uses the Hawks' own
Jalen Johnson compilation. The previous mixed-video selections are retired.

The shared office scenes come from the Kings draft room and Nuggets draft-day
footage credited above. They are general GM context rather than franchise-specific
claims. Original Random-team and non-team startup contexts keep the original montage.

Hovering a franchise previews it; clicking selects it. Hovering a compact startup
button only enlarges the button. Clicking opens its full panel, which remains open
until explicitly closed, switched, or dismissed with Escape.

Playback is local, silent, and uses the same dot-press and analogue-TV interference
renderer as the original. A six-scene playlist shares office files between teams.
Only the active video and one incoming scene are loaded, and both are released
when startup closes. No download or remote player runs in the game.

`scripts/startup_team_video_settings.json` records the source URLs, exact intervals,
opponents and reviewed actions. `video/teams/manifest.json` records the exported
playlist. Source-frame review sheets are retained in
`output/startup-team-correction/*-audit.jpg`; original selections and superseded
exports remain there for comparison. Broadcast framing and attribution are preserved.

| Team | Compilation | Selected source intervals (seconds) |
| --- | --- | --- |
| ATL | [Jalen Johnson is an NBA All Star 🌟 2025-26 Season Highlights](https://www.youtube.com/watch?v=wT-Hj5oWu1U) | 2.0–10.5, 25.0–33.5, 68.0–78.0, 79.0–91.0, 99.0–109.0, 169.0–180.0 |
| BKN | [Michael Porter Jr. 2025-2026 Season Highlights](https://www.youtube.com/watch?v=zEgrNFMdXwg) | 2.0–11.0, 13.0–22.0, 58.0–66.0, 23.0–32.0, 139.0–145.5, 178.0–184.0 |
| BOS | [Jaylen Brown – Top Plays of the 2025-26 Season](https://www.youtube.com/watch?v=GVsjpWv5wLo) | 2.0–14.0, 23.0–33.0, 34.0–47.0, 119.0–132.0, 134.0–151.0, 169.0–178.0 |
| CHA | [The Charlotte Hornets Are BUZZING! 🐝 – Top Plays](https://www.youtube.com/watch?v=MwIh--NGGHU) | 0.0–9.0, 17.0–26.0, 59.0–72.0, 94.0–107.0, 119.0–130.0, 183.0–200.0 |
| CHI | [20 minutes of Josh Giddey dropping dimes & getting buckets](https://www.youtube.com/watch?v=yYtzjK0GAKE) | 8.5–17.0, 17.0–28.0, 28.0–38.0, 63.0–70.0, 82.0–92.0, 103.0–112.0 |
| CLE | [Harden & Mitchell Became an INSTANT DUO in Cleveland 🤯 – Top Plays – 2025-26 NBA Season](https://www.youtube.com/watch?v=TjTVx-QEbJA) | 1.0–16.0, 38.0–48.0, 64.0–76.0, 115.5–126.0, 155.0–166.0, 183.0–191.0 |
| DAL | [Cooper Flagg's Rookie Season Highlights Are MUST-SEE – 2025-26 NBA Season](https://www.youtube.com/watch?v=m6RU9K3ezec) | 1.0–11.0, 24.5–37.0, 83.0–96.0, 124.0–137.0, 155.0–165.0, 181.0–189.0 |
| DEN | [Nikola Jokić Makes Everything Look EASY 😮‍💨 – Top Plays – 2025-26 NBA Season](https://www.youtube.com/watch?v=SvoFvBq9jSg) | 0.0–16.0, 18.0–26.0, 54.0–66.0, 84.0–97.0, 109.0–121.0, 142.0–152.0 |
| DET | [Cade Cunningham Top Plays On The Season – 2025 - 2026](https://www.youtube.com/watch?v=p0G1IM3xuas) | 0.0–16.0, 39.0–51.0, 54.0–64.0, 67.0–81.0, 109.0–119.0, 160.0–172.0 |
| GSW | [Golden State Warriors Plays of the Year – 2025-26 NBA Season](https://www.youtube.com/watch?v=qJxK4Ki0XlY) | 2.0–12.0, 13.0–23.0, 38.0–44.0, 54.0–69.0, 92.0–105.0, 144.0–156.0 |
| HOU | [Kevin Durant's BEST PLAYS! – 2026 NBA All-Star Reserve](https://www.youtube.com/watch?v=4I_eosXkS98) | 0.0–17.0, 48.0–58.0, 69.0–86.0, 89.0–102.0, 109.0–122.0, 130.0–144.0 |
| IND | [Pascal Siakam's TOP PLAYS of the 2025-26 NBA Season](https://www.youtube.com/watch?v=nWKqAbI5rVo) | 11.0–20.5, 34.0–40.0, 44.0–51.0, 84.0–94.0, 108.0–115.5, 134.0–145.0 |
| LAC | [Kawhi Leonard Was LOCKED IN This Season 🥶 – Top Plays – 2025-26 NBA Season](https://www.youtube.com/watch?v=RivzZVtPds0) | 0.0–16.0, 58.0–76.0, 79.0–92.0, 104.5–116.0, 130.0–146.0, 173.0–188.0 |
| LAL | [Luka Dončić's BEST Plays from the 2025-2026 Season](https://www.youtube.com/watch?v=x5kjIwZ3-Kw) | 12.0–24.0, 44.0–54.5, 75.0–85.0, 93.0–115.0, 169.0–184.0, 183.0–197.0 |
| MEM | [Ja Morant – Top Plays of the 2025-26 season](https://www.youtube.com/watch?v=wMcxZPbo32E) | 29.0–46.0, 54.0–62.0, 65.0–70.5, 109.0–121.0, 132.0–140.0, 149.0–162.0 |
| MIA | [Bam Adebayo BEST HIGHLIGHTS 25-26 Season](https://www.youtube.com/watch?v=cDDz3lOgDMo) | 23.0–29.0, 168.0–181.0, 186.0–199.0, 201.0–212.0, 233.0–238.5, 292.0–301.5 |
| MIL | [Giannis Antetokounmpo's BEST PLAYS! – 2026 NBA All-Star Starter](https://www.youtube.com/watch?v=em9OfoguUiM) | 0.0–16.0, 65.0–87.0, 89.0–101.0, 147.0–160.0, 186.0–198.0, 123.0–134.0 |
| MIN | [Anthony Edwards Was a PROBLEM All Season 😤 – Top Plays – 2025-26 NBA Season](https://www.youtube.com/watch?v=T5I70wkGVLI) | 0.0–10.0, 24.0–41.0, 44.0–57.0, 69.0–78.0, 110.0–122.0, 140.0–152.0 |
| NOP | [Zion Williamson 2025-26 NBA Season Highlights – New Orleans Pelicans](https://www.youtube.com/watch?v=jpUlLlbhAX0) | 8.0–17.0, 29.0–39.0, 57.0–68.0, 74.0–86.0, 89.0–102.0, 143.0–152.0 |
| NYK | [Jalen Brunson's TOP PLAYS From The 2025 Emirates NBA Cup 🏆 – 2025-26 Season](https://www.youtube.com/watch?v=4Q5dZ400RHo) | 0.0–13.0, 49.0–59.0, 80.0–90.0, 64.0–75.0, 163.0–179.0, 109.0–127.0 |
| OKC | [Shai Gilgeous-Alexander Is The 2025-26 @kia NBA Most Valuable Player!](https://www.youtube.com/watch?v=BzKf9haIml0) | 0.0–16.0, 49.0–59.0, 65.0–82.0, 88.0–108.0, 110.0–124.0, 161.0–174.0 |
| ORL | [TOP 25 PLAYS FROM 25-26 SEASON: PAOLO BANCHERO](https://www.youtube.com/watch?v=ONzDHBUYNGc) | 0.0–12.0, 18.0–33.0, 56.0–65.0, 65.0–78.0, 81.0–101.0, 122.0–134.0 |
| PHI | [Tyrese Maxey Keeps On LEVELING UP – 2025-26 Season Highlights](https://www.youtube.com/watch?v=inpnEbumi2I) | 0.0–5.5, 60.0–68.0, 142.0–154.0, 98.0–107.0, 109.0–114.5, 130.0–141.0 |
| PHX | [Devin Booker Was UNSTOPPABLE This Season 🔥 – Top Plays – 2025-26 NBA Season](https://www.youtube.com/watch?v=nFK9_WsL2lM) | 0.0–17.0, 38.0–49.0, 54.0–65.0, 69.0–89.0, 113.0–128.0, 128.0–148.0 |
| POR | [Deni Avdija's Top Plays – 2025-26 Season – Portland Trail Blazers](https://www.youtube.com/watch?v=OBuu8x54uOQ) | 0.0–7.0, 27.0–38.0, 39.0–49.0, 64.0–71.0, 74.0–81.0, 134.0–143.0 |
| SAC | [DeMar DeRozan BEST HIGHLIGHTS 25-26 Season](https://www.youtube.com/watch?v=svfDl8gpUDE) | 24.0–37.0, 75.0–79.0, 80.0–87.5, 105.5–111.0, 123.0–131.0, 169.0–176.5 |
| SAS | [Victor Wembanyama's Season Highlights Are Simply UNREAL 🤯 – 2025-26 NBA Season](https://www.youtube.com/watch?v=-Q-KO1VBJAY) | 0.0–18.0, 42.0–52.0, 63.0–72.0, 108.0–120.0, 139.0–156.0, 159.0–177.0 |
| TOR | [Scottie Barnes' BEST PLAYS! – 2026 NBA All-Star Reserve](https://www.youtube.com/watch?v=5LAdiUKlgaQ) | 0.0–13.0, 19.0–33.0, 44.0–58.0, 74.0–83.0, 98.0–108.0, 155.0–175.0 |
| UTA | [TOP PLAYS of the 2025-26 Season 😱🤩 – UTAH JAZZ](https://www.youtube.com/watch?v=UDWy05T7a8g) | 4.0–16.5, 17.0–28.0, 28.0–42.0, 118.0–130.0, 130.0–145.0, 149.0–160.0 |
| WAS | [Alex Sarr Highlights from the 2025-26 Season](https://www.youtube.com/watch?v=KH8yplVJIsc) | 0.0–10.0, 16.0–25.0, 28.0–37.0, 84.0–91.0, 104.0–111.5, 114.0–126.0 |
## Reviewed franchise preview reels

All 30 franchises use a reviewed team or player compilation. Each reel contains
six selected-team plays from multiple games and three general front-office scenes.
Two plays alternate with a draft-room or staff scene, for nine shots in a full loop.
Chicago uses the Bulls' own Josh Giddey compilation; Atlanta uses the Hawks' own
Jalen Johnson compilation. The previous mixed-video selections are retired.

The shared office scenes come from the Kings draft room and Nuggets draft-day
footage credited above. They are general GM context rather than franchise-specific
claims. Original Random-team and non-team startup contexts keep the original montage.

Hovering a franchise previews it; clicking selects it. Hovering a compact startup
button only enlarges the button. Clicking opens its full panel, which remains open
until explicitly closed, switched, or dismissed with Escape.

Playback is local, silent, and uses the same dot-press and analogue-TV interference
renderer as the original. A six-scene playlist shares office files between teams.
Only the active video and one incoming scene are loaded, and both are released
when startup closes. No download or remote player runs in the game.

`scripts/startup_team_video_settings.json` records the source URLs, exact intervals,
opponents and reviewed actions. `video/teams/manifest.json` records the exported
playlist. Source-frame review sheets are retained in
`output/startup-team-correction/*-audit.jpg`; original selections and superseded
exports remain there for comparison. Broadcast framing and attribution are preserved.

| Team | Compilation | Selected source intervals (seconds) |
| --- | --- | --- |
| ATL | [Jalen Johnson is an NBA All Star 🌟 2025-26 Season Highlights](https://www.youtube.com/watch?v=wT-Hj5oWu1U) | 2.0–10.5, 25.0–33.5, 68.0–78.0, 79.0–91.0, 99.0–109.0, 169.0–180.0 |
| BKN | [Michael Porter Jr. 2025-2026 Season Highlights](https://www.youtube.com/watch?v=zEgrNFMdXwg) | 2.0–11.0, 13.0–22.0, 58.0–66.0, 23.0–32.0, 139.0–145.5, 178.0–184.0 |
| BOS | [Jaylen Brown – Top Plays of the 2025-26 Season](https://www.youtube.com/watch?v=GVsjpWv5wLo) | 2.0–14.0, 23.0–33.0, 34.0–47.0, 119.0–132.0, 134.0–151.0, 169.0–178.0 |
| CHA | [The Charlotte Hornets Are BUZZING! 🐝 – Top Plays](https://www.youtube.com/watch?v=MwIh--NGGHU) | 0.0–9.0, 17.0–26.0, 59.0–72.0, 94.0–107.0, 119.0–130.0, 183.0–200.0 |
| CHI | [20 minutes of Josh Giddey dropping dimes & getting buckets](https://www.youtube.com/watch?v=yYtzjK0GAKE) | 8.5–17.0, 17.0–28.0, 28.0–38.0, 63.0–70.0, 82.0–92.0, 103.0–112.0 |
| CLE | [Harden & Mitchell Became an INSTANT DUO in Cleveland 🤯 – Top Plays – 2025-26 NBA Season](https://www.youtube.com/watch?v=TjTVx-QEbJA) | 1.0–16.0, 38.0–48.0, 64.0–76.0, 115.5–126.0, 155.0–166.0, 183.0–191.0 |
| DAL | [Cooper Flagg's Rookie Season Highlights Are MUST-SEE – 2025-26 NBA Season](https://www.youtube.com/watch?v=m6RU9K3ezec) | 1.0–11.0, 24.5–37.0, 83.0–96.0, 124.0–137.0, 155.0–165.0, 181.0–189.0 |
| DEN | [Nikola Jokić Makes Everything Look EASY 😮‍💨 – Top Plays – 2025-26 NBA Season](https://www.youtube.com/watch?v=SvoFvBq9jSg) | 0.0–16.0, 18.0–26.0, 54.0–66.0, 84.0–97.0, 109.0–121.0, 142.0–152.0 |
| DET | [Cade Cunningham Top Plays On The Season – 2025 - 2026](https://www.youtube.com/watch?v=p0G1IM3xuas) | 0.0–16.0, 39.0–51.0, 54.0–64.0, 67.0–81.0, 109.0–119.0, 160.0–172.0 |
| GSW | [Golden State Warriors Plays of the Year – 2025-26 NBA Season](https://www.youtube.com/watch?v=qJxK4Ki0XlY) | 2.0–12.0, 13.0–23.0, 38.0–44.0, 54.0–69.0, 92.0–105.0, 144.0–156.0 |
| HOU | [Kevin Durant's BEST PLAYS! – 2026 NBA All-Star Reserve](https://www.youtube.com/watch?v=4I_eosXkS98) | 0.0–17.0, 48.0–58.0, 69.0–86.0, 89.0–102.0, 109.0–122.0, 130.0–144.0 |
| IND | [Pascal Siakam's TOP PLAYS of the 2025-26 NBA Season](https://www.youtube.com/watch?v=nWKqAbI5rVo) | 11.0–20.5, 34.0–40.0, 44.0–51.0, 84.0–94.0, 108.0–115.5, 134.0–145.0 |
| LAC | [Kawhi Leonard Was LOCKED IN This Season 🥶 – Top Plays – 2025-26 NBA Season](https://www.youtube.com/watch?v=RivzZVtPds0) | 0.0–16.0, 58.0–76.0, 79.0–92.0, 104.5–116.0, 130.0–146.0, 173.0–188.0 |
| LAL | [Luka Dončić's BEST Plays from the 2025-2026 Season](https://www.youtube.com/watch?v=x5kjIwZ3-Kw) | 12.0–24.0, 44.0–54.5, 75.0–85.0, 93.0–115.0, 169.0–184.0, 183.0–197.0 |
| MEM | [Ja Morant – Top Plays of the 2025-26 season](https://www.youtube.com/watch?v=wMcxZPbo32E) | 29.0–46.0, 54.0–62.0, 65.0–70.5, 109.0–121.0, 132.0–140.0, 149.0–162.0 |
| MIA | [Bam Adebayo BEST HIGHLIGHTS 25-26 Season](https://www.youtube.com/watch?v=cDDz3lOgDMo) | 23.0–29.0, 168.0–181.0, 186.0–199.0, 201.0–212.0, 233.0–238.5, 292.0–301.5 |
| MIL | [Giannis Antetokounmpo's BEST PLAYS! – 2026 NBA All-Star Starter](https://www.youtube.com/watch?v=em9OfoguUiM) | 0.0–16.0, 65.0–87.0, 89.0–101.0, 147.0–160.0, 186.0–198.0, 123.0–134.0 |
| MIN | [Anthony Edwards Was a PROBLEM All Season 😤 – Top Plays – 2025-26 NBA Season](https://www.youtube.com/watch?v=T5I70wkGVLI) | 0.0–10.0, 24.0–41.0, 44.0–57.0, 69.0–78.0, 110.0–122.0, 140.0–152.0 |
| NOP | [Zion Williamson 2025-26 NBA Season Highlights – New Orleans Pelicans](https://www.youtube.com/watch?v=jpUlLlbhAX0) | 8.0–17.0, 29.0–39.0, 57.0–68.0, 74.0–86.0, 89.0–102.0, 143.0–152.0 |
| NYK | [Jalen Brunson's TOP PLAYS From The 2025 Emirates NBA Cup 🏆 – 2025-26 Season](https://www.youtube.com/watch?v=4Q5dZ400RHo) | 0.0–13.0, 49.0–59.0, 80.0–90.0, 64.0–75.0, 163.0–179.0, 109.0–127.0 |
| OKC | [Shai Gilgeous-Alexander Is The 2025-26 @kia NBA Most Valuable Player!](https://www.youtube.com/watch?v=BzKf9haIml0) | 0.0–16.0, 49.0–59.0, 65.0–82.0, 88.0–108.0, 110.0–124.0, 161.0–174.0 |
| ORL | [TOP 25 PLAYS FROM 25-26 SEASON: PAOLO BANCHERO](https://www.youtube.com/watch?v=ONzDHBUYNGc) | 0.0–12.0, 18.0–33.0, 56.0–65.0, 65.0–78.0, 81.0–101.0, 122.0–134.0 |
| PHI | [Tyrese Maxey Keeps On LEVELING UP – 2025-26 Season Highlights](https://www.youtube.com/watch?v=inpnEbumi2I) | 0.0–5.5, 60.0–68.0, 142.0–154.0, 98.0–107.0, 109.0–114.5, 130.0–141.0 |
| PHX | [Devin Booker Was UNSTOPPABLE This Season 🔥 – Top Plays – 2025-26 NBA Season](https://www.youtube.com/watch?v=nFK9_WsL2lM) | 0.0–17.0, 38.0–49.0, 54.0–65.0, 69.0–89.0, 113.0–128.0, 128.0–148.0 |
| POR | [Deni Avdija's Top Plays – 2025-26 Season – Portland Trail Blazers](https://www.youtube.com/watch?v=OBuu8x54uOQ) | 0.0–7.0, 27.0–38.0, 39.0–49.0, 64.0–71.0, 74.0–81.0, 134.0–143.0 |
| SAC | [DeMar DeRozan BEST HIGHLIGHTS 25-26 Season](https://www.youtube.com/watch?v=svfDl8gpUDE) | 24.0–37.0, 75.0–79.0, 80.0–87.5, 105.5–111.0, 123.0–131.0, 169.0–176.5 |
| SAS | [Victor Wembanyama's Season Highlights Are Simply UNREAL 🤯 – 2025-26 NBA Season](https://www.youtube.com/watch?v=-Q-KO1VBJAY) | 0.0–18.0, 42.0–52.0, 63.0–72.0, 108.0–120.0, 139.0–156.0, 159.0–177.0 |
| TOR | [Scottie Barnes' BEST PLAYS! – 2026 NBA All-Star Reserve](https://www.youtube.com/watch?v=5LAdiUKlgaQ) | 0.0–13.0, 19.0–33.0, 44.0–58.0, 74.0–83.0, 98.0–108.0, 155.0–175.0 |
| UTA | [TOP PLAYS of the 2025-26 Season 😱🤩 – UTAH JAZZ](https://www.youtube.com/watch?v=UDWy05T7a8g) | 4.0–16.5, 17.0–28.0, 28.0–42.0, 118.0–130.0, 130.0–145.0, 149.0–160.0 |
| WAS | [Alex Sarr Highlights from the 2025-26 Season](https://www.youtube.com/watch?v=KH8yplVJIsc) | 0.0–10.0, 16.0–25.0, 28.0–37.0, 84.0–91.0, 104.0–111.5, 114.0–126.0 |
