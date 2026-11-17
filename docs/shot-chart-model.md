# Fifteen-Region Shot Charts

## Visual Contract

- A regular hexagonal lattice, mirrored for offense and defense.
- One color per region: below -8 pp, -8 to -3 pp, within +/-3 pp, +3 to +8 pp, above +8 pp.
- Five discrete hex sizes encode local attempt/contest share relative to the league's mean cell density, so common shooting locations stay visibly larger. Tooltips also report the local-to-local density ratio. No random size, opacity, position, or color noise.
- The palette uses the application's muted red, neutral gray, and blue. Courts use the existing cool gray panel family.
- Native hover titles report the region, projected FG%, league FG%, percentage-point difference, and estimated density ratio.

The reference follows StatMuse's fifteen regions: inside 8 feet; three 8-16-foot regions; five longer two-point regions; two corner threes; three above-break three regions; backcourt. Backcourt attempts remain in the fifteen-region probability vector but are not falsely plotted inside the half-court. Each side of the mirrored court therefore displays fourteen in-bounds regions.

## Reference Collection

`scripts/collect_shot_chart_reference.py` collects a bounded sample of publicly rendered shot-chart facts, including X/Y locations, make flags, zone IDs, and chart-provided league totals. It does not retain page markup, illustrations, proprietary chart code, or visual assets. Requests are sequential and spaced. The application never makes StatMuse requests.

The checked-in sample covers 32 players and 31,326 attempts in the completed 2024-25 regular season. Each profile retains its precise source URL in `data/research/shot_chart_reference.json`. For example: [Stephen Curry](https://www.statmuse.com/nba/ask/stephen-curry-shot-chart-in-2024-25), [Ivica Zubac](https://www.statmuse.com/nba/ask/ivica-zubac-shot-chart-in-2024-25), and [DeMar DeRozan](https://www.statmuse.com/nba/ask/demar-derozan-shot-chart-in-2024-25).

## Projection

`scripts/build_shot_chart_model.py` builds a small offline model from the sample and the project's calibrated ratings. NumPy is needed only for rebuilding, not for runtime.

Within each region, smoothed two-foot source bins produce stable cell-density templates. The chart-provided league FGA totals anchor regional frequencies, and league FG% anchors efficiency. Within-region league density is a sample-conditioned estimate, not an observed league-wide coordinate census.

Generated players blend five nearby real profiles using standardized shooting range, shot versatility, handle pressure, rim pressure, passing reads, portability, offensive rebounding, and height. Existing matched players retain an observed preference anchor, gradually giving more weight to new neighbors as ratings change. Sparse efficiency observations are shrunk toward the region's league average; semantic rating changes adjust the projected efficiency.

Team shot distributions respect minutes and availability. Offensive efficiency is additionally weighted by projected attempts within each region. Defensive suppression and contest density remain ratings-based estimates, not historical opponent shooting data.

## Validation And Limits

Centered-log-ratio PCA of the fifteen-region distributions gives six components explaining 93.2% of variation. PCA is diagnostic, not a fitted ratings-to-accuracy regression. Runtime uses transparent ratings neighbors.

Leave-one-player-out total variation error is 0.1991 for ratings neighbors versus 0.2677 for the sample mean, a 25.6% reduction. This is an internal small-sample check, not a claim of league-wide predictive accuracy. The archetype sample is deliberately diverse but not unbiased; the ratings and historical shots are not perfectly contemporaneous.

Current-season and generated charts are labeled as projections. Gameplay continues to consume its existing twelve-zone spatial grades; the new fifteen-region chart is a separate display layer. Missing references produce explicitly unavailable, neutral-color charts rather than invented FG percentages.

## Rebuild

```sh
python3 scripts/collect_shot_chart_reference.py
PYTHONPATH=src python3 scripts/build_shot_chart_model.py
PYTHONPATH=src:tests python3 -m unittest test_shot_chart test_spatial
node scripts/test_shot_chart.cjs
```

The compiled reference is loaded once per application process. Restart the preview after rebuilding it.
