# AI-TRADES-SENSE: every AI trade, before and after

One hands-off 2026-27 season per run (`scripts/season_almanac_run.py`, Brooklyn the empty user chair), on Azure.
Before = `096ad81f` (main). After = this branch. Ratings in brackets are (overall at the start, age). Flags after `<<<` come from
`output/trades-sense/tools/trades_compare.py`: FIRST_FOR_BENCH (a first-round pick or right spent, best incoming player then under 15
minutes a night), GIVEAWAY, INJURED (incoming player out 30+ days), CONTENDER_SENDS (a team that won 2+ playoff rounds sends players
out after the Finals), PICK_BOUNCE (a pick moved again within 90 days).

## Seed 20261126, before

```
52 trades; by month [('2026-12', 1), ('2027-01', 9), ('2027-02', 18), ('2027-06', 11), ('2027-07', 9), ('2027-08', 3), ('2027-09', 1)]
2026-12-19 | CHA gets Jae'Sean Tate (71.1, 30.0), Clint Capela (73.1, 32.0), Steven Adams (75.7, 33.0), 2029 R1: HOU receives the second least favourable of DAL/HOU || HOU gets Grayson Allen (77.2, 31.0)
2027-01-02 | IND gets Marcus Smart (76.7, 32.0) || HOU gets T.J. McConnell (78.0, 34.0)
2027-01-07 | PHI gets 2030 R1: WAS receives the more favourable of WAS/PHX; PHX re || WAS gets Adem Bona (75.8, 23.0)   <<< FIRST_FOR_BENCH WAS (13.0 min over 33 games)
2027-01-17 | SAS gets Tim Hardaway Jr. (70.5, 34.0) || MIA gets Carter Bryant (74.1, 20.0)
2027-01-19 | DET gets Micah Potter (73.6, 28.0), 2027 R2 MIN (owned by POR) || POR gets Paul Reed (80.6, 27.0)
2027-01-20 | CHI gets Klay Thompson (69.2, 36.0), Simone Fontecchio (71.3, 30.0), 2030 R1 MIA (own pick); 2030 R1 connected allocation — apply || MIA gets Tre Jones (75.9, 26.0)
2027-01-20 | MEM gets Luke Kennard (72.6, 30.0), Haywood Highsmith (73.6, 29.0), 2027 R2: PHX receives the less favourable of BOS/ORL. || PHX gets Isaiah Stewart (76.5, 25.0)
2027-01-30 | BOS gets Taurean Prince (67.7, 32.0), Daniss Jenkins (73.0, 25.0), 2027 R2 DET (own pick) || DET gets Mitchell Robinson (81.1, 28.0), Luka Garza (76.5, 27.0)
2027-01-31 | MEM gets Jay Huff (75.1, 29.0), Obi Toppin (77.9, 28.0), 2030 R2 IND (own pick); 2030 R2: CHI receives the more favou || IND gets Quinten Post (77.6, 26.0)   <<< INJURED Quinten Post out to 2027-04-22
2027-01-31 | OKC gets Olivier-Maxence Prosper (73.9, 24.0) || MEM gets Kenrich Williams (75.4, 31.0)
2027-02-02 | CLE gets 2028 R1: WAS receives the more favourable of the pick alloca || WAS gets Tyrese Proctor (74.9, 22.0)   <<< FIRST_FOR_BENCH WAS (14.9 min over 33 games)
2027-02-02 | UTA gets Jaden Hardy (69.1, 24.0), 2033 R2 LAL (own pick) || LAL gets Jaxson Hayes (76.5, 26.0)
2027-02-02 | LAL gets Dru Smith (74.1, 28.0) || MIA gets Adou Thiero (73.9, 22.0)
2027-02-02 | LAC gets Jarred Vanderbilt (75.0, 27.0) || LAL gets Max Strus (76.0, 30.0)
2027-02-02 | CLE gets Jabari Walker (72.6, 24.0) || PHI gets Rashaun Agee (73.0, 25.0)
2027-02-03 | GSW gets Orlando Robinson (73.6, 26.0) || CHI gets Draymond Green (75.9, 36.0)
2027-02-03 | HOU gets Ben Simmons (73.8, 30.0) || SAC gets Russell Westbrook (72.9, 37.0)   <<< INJURED Ben Simmons out to 2027-04-10
2027-02-04 | CHI gets Zeke Nnaji (71.3, 25.0), Julian Strawther (71.5, 24.0), 2028 R2 MIN (owned by DEN), 2032 R2 SAC (owned by DEN) || DEN gets Jalen Smith (77.6, 26.0)
2027-02-04 | LAL gets Thomas Bryant (75.8, 29.0) || CLE gets Matisse Thybulle (74.5, 29.0), 2032 R2 WAS (owned by LAL)
2027-02-04 | MIA gets Jericho Sims (68.8, 27.0) || MIL gets Bobby Portis (74.8, 31.0)
2027-02-05 | GSW gets 2028 R1: CHA receives the more favourable of CHA/MIN; MIN re || CHA gets Gary Payton II (78.3, 33.0)   <<< FIRST_FOR_BENCH CHA (8.3 min over 29 games)
2027-02-05 | NOP gets Grant Williams (72.7, 27.0), 2027 R2: CHA receives the more favourable of NOP/POR., 2032 R1: NOP receives the more favourable of CHA/NOP; CHA re || CHA gets Dejounte Murray (77.4, 30.0)
2027-02-05 | UTA gets Dean Wade (75.4, 29.0) || PHI gets Josh Okogie (74.8, 28.0)
2027-02-05 | NYK gets Sion James (71.6, 23.0) || CHA gets Landry Shamet (72.3, 29.0), 2028 R2 BOS (owned by NYK); picks 31-45 protected; BOS keeps
2027-02-05 | PHI gets Kobe Sanders (71.7, 24.0) || LAC gets Anfernee Simons (75.9, 27.0)
2027-02-05 | OKC gets DeAndre Jordan (69.7, 38.0), 2027 R1: If NOP or ATL holds no pick in this pool after prot || NOP gets Nikola Topić (74.0, 21.0)   <<< FIRST_FOR_BENCH NOP (9.7 min over 28 games)
2027-02-05 | TOR gets Tacko Fall (72.9, 30.0), 2028 R2 DET (owned by PHI); picks 31-55 protected; DET keeps || PHI gets Trayce Jackson-Davis (75.7, 26.0)
2027-02-05 | CHA gets Brook Lopez (76.3, 38.0), 2030 R2: LAC receives the less favourable of LAC/UTA. || LAC gets Moussa Diabaté (75.9, 24.0)
2027-06-22 | CHI gets 2027 R1 DEN (owned by OKC); top-5 protected, 2027 R2 CHI (owned by OKC), 2032 R2 LAC (own pick), 2031 R2 LAC (own pick) || LAC gets 2027 R1 CHI (own pick) || OKC gets 2027 R1 TOR (owned by LAC)
2027-06-22 | SAS gets 2031 R1 SAC (own pick); 2031 R1: SAS receives the more favou, 2034 R2 SAC (own pick) || SAC gets 2027 R1 ATL (owned by SAS)
2027-06-22 | GSW gets 2027 R1 PHI (own pick), 2028 R2: PHI receives the second least favourable of GSW/MIL, 2029 R2: IND receives the more favourable of IND/WAS., 2028 R2: IND receives the second least favourable of CHI/IND || IND gets 2027 R1 GSW (own pick) || PHI gets 2027 R1 IND (own pick)
2027-06-22 | PHX gets 2027 R1 MIN (owned by UTA) || TOR gets 2027 R1 CLE (owned by PHX) || UTA gets 2027 R1 OKC (owned by TOR), 2029 R2 TOR (own pick), 2034 R2 PHX (own pick), 2032 R2: PHX receives the less favourable of HOU/PHX.
2027-06-22 | POR gets 2027 R2 LAC (owned by UTA), 2031 R2: UTA receives the more favourable of BOS/CLE., 2031 R2 MIA (owned by WAS); 2031 R2: WAS receives the more f, 2028 R2: WAS receives the less favourable of LAL/WAS. || UTA gets 2027 R2 BKN (owned by WAS) || WAS gets 2027 R1 POR (own pick)
2027-06-22 | BOS gets 2027 R2 WAS (owned by NYK), 2032 R2 DAL (owned by NYK), 2031 R2 TOR (owned by NOP), 2027 R2 HOU (owned by NOP) || NOP gets 2027 R1 BOS (own pick) || NYK gets 2027 R2 NOP (own pick)
2027-06-22 | OKC gets 2030 R2 ORL (own pick); 2030 R2: ORL receives the more favou, 2029 R2 ORL (own pick) || ORL gets 2027 R2 CHA (owned by OKC)
2027-06-22 | CHA gets 2027 R2 POR (own pick), 2031 R2 POR (own pick) || POR gets 2027 R2 MEM (owned by CHA)
2027-06-30 | SAS gets 2030 R1: PHI receives the more favourable of WAS/PHX; If the || PHI gets Luke Kornet (77.9, 31.0), 2034 R2 SAS (own pick)
2027-06-30 | ATL gets LJ Cryer (73.4, 25.0), 2029 R1 GSW (own pick); top-4 protected; GSW keeps this pick || GSW gets Nickeil Alexander-Walker (77.5, 28.0)
2027-06-30 | CHA gets 2029 R1: If a compared pick falls in its protected range (LA || PHI gets Cameron Williams (None, None)
2027-07-01 | CHI gets Tobias Harris (74.4, 34.0), David Jones Garcia (73.8, 24.0), 2029 R2 LAC (owned by SAS), 2029 R2 NOP (owned by SAS) || SAS gets Zach Collins (77.7, 28.0)
2027-07-01 | MIA gets Nate Bittle (73.0, 23.0) || TOR gets Keshad Johnson (74.1, 25.0)
2027-07-01 | DAL gets James Harden (80.0, 37.0), 2032 R2 WAS (owned by CLE), 2033 R2 CLE (own pick) || CLE gets P.J. Washington (74.5, 28.0)   <<< CONTENDER_SENDS CLE (3 rounds): James Harden (80.0, 37.0)
2027-07-01 | MEM gets 2030 R2 GSW (own pick) || GSW gets Scotty Pippen Jr. (76.9, 25.0)
2027-07-02 | TOR gets Karlo Matković (76.0, 25.0), pick_nop-2030-2 || NOP gets RJ Barrett (76.9, 26.0)
2027-07-03 | PHX gets 2034 R2 CHI (own pick) || CHI gets Ryan Dunn (76.0, 23.0)
2027-07-03 | MIN gets Cameron Carr (71.6, 21.0), pick_future-lal-2034-2-own || LAL gets Jonathan Kuminga (76.0, 24.0)
2027-07-03 | ATL gets Rudy Gobert (79.2, 34.0), 2030 R2 MEM (owned by MIN); picks 31-50 protected; MEM keeps, 2034 R2 LAL (owned by MIN), 2034 R2 MIN (own pick) || MIN gets Onyeka Okongwu (79.6, 25.0)
2027-07-03 | PHX gets Tari Eason (76.5, 25.0), 2030 R1 HOU (own pick); top-10 protected; HOU keeps this pic || HOU gets Collin Gillespie (78.7, 27.0)   <<< CONTENDER_SENDS HOU (2 rounds): Tari Eason (76.5, 25.0)
2027-08-01 | DAL gets 2029 R1: If a compared pick falls in its protected range (OR || MEM gets Daniel Gafford (79.3, 28.0)
2027-08-01 | DEN gets Nikola Topić (74.0, 21.0), 2034 R2 POR (own pick) || MEM gets Jahmyl Telfort (73.4, 25.0), Spencer Jones (71.8, 25.0), 2034 R2 DEN (own pick) || POR gets Gradey Dick (71.6, 22.0), 2031 R2 SAC (owned by DEN)
2027-08-01 | ORL gets Jalon Moore (73.0, 23.0) || MIN gets Brandon Clarke (74.8, 29.0)
2027-09-15 | UTA gets Chris Mañon (73.7, 24.0) || LAL gets Jonathan Isaac (79.7, 29.0)
PICK_BOUNCE pick_future-lal-2034-2-own: MIN 2027-07-03 -> ATL 2027-07-03
flags {'first_for_bench': 4, 'injured': 2, 'contender_sends': 2, 'pick_bounce': 1}
per team [('PHI', 8), ('CHA', 7), ('CHI', 6), ('MEM', 6), ('LAL', 6), ('MIA', 5), ('UTA', 5), ('GSW', 5), ('HOU', 4), ('SAS', 4), ('POR', 4), ('PHX', 4), ('OKC', 4), ('CLE', 4), ('LAC', 4), ('NOP', 4), ('TOR', 4), ('IND', 3), ('WAS', 3), ('MIN', 3), ('DET', 2), ('BOS', 2), ('SAC', 2), ('DEN', 2), ('NYK', 2), ('ORL', 2), ('ATL', 2), ('DAL', 2), ('MIL', 1)]
```

## Seed 20261126, after

```
50 trades; by month [('2026-12', 1), ('2027-01', 9), ('2027-02', 14), ('2027-06', 12), ('2027-07', 10), ('2027-08', 3), ('2027-09', 1)]
2026-12-19 | CHA gets Jae'Sean Tate (71.1, 30.0), Clint Capela (73.1, 32.0), Steven Adams (75.7, 33.0), 2029 R1: HOU receives the second least favourable of DAL/HOU || HOU gets Grayson Allen (77.2, 31.0)
2027-01-02 | IND gets Marcus Smart (76.7, 32.0) || HOU gets T.J. McConnell (78.0, 34.0)
2027-01-07 | PHI gets 2032 R2 NOP (own pick) || NOP gets Adem Bona (75.8, 23.0)
2027-01-17 | SAS gets Tim Hardaway Jr. (70.5, 34.0) || MIA gets Carter Bryant (74.1, 20.0)
2027-01-19 | OKC gets 2028 R1: WAS receives the more favourable of the pick alloca || WAS gets Nikola Topić (74.0, 21.0), 2032 R2 OKC (own pick)
2027-01-20 | DET gets Micah Potter (73.6, 28.0), 2027 R2 MIN (owned by POR) || POR gets Paul Reed (80.6, 27.0)
2027-01-20 | CHI gets Klay Thompson (69.2, 36.0), Simone Fontecchio (71.3, 30.0), 2030 R1 MIA (own pick); 2030 R1 connected allocation — apply || MIA gets Tre Jones (75.9, 26.0)
2027-01-30 | MEM gets Kyle Kuzma (70.1, 31.0), 2027 R2 MIL (own pick) || MIL gets Isaiah Stewart (76.5, 25.0), Quinten Post (77.6, 26.0)   <<< INJURED Quinten Post out to 2027-04-22
2027-01-31 | OKC gets Olivier-Maxence Prosper (73.9, 24.0) || MEM gets Kenrich Williams (75.4, 31.0)
2027-01-31 | UTA gets Deandre Ayton (73.1, 28.0) || WAS gets Josh Okogie (74.8, 28.0)
2027-02-02 | CHI gets Jay Huff (75.1, 29.0), Obi Toppin (77.9, 28.0), 2030 R2 IND (own pick); 2030 R2: CHI receives the more favou || IND gets Zach Collins (77.7, 28.0)
2027-02-02 | LAC gets Jarred Vanderbilt (75.0, 27.0) || LAL gets Max Strus (76.0, 30.0)
2027-02-02 | CLE gets Orlando Robinson (73.6, 26.0) || CHI gets Tyrese Proctor (74.9, 22.0)
2027-02-02 | BOS gets Taurean Prince (67.7, 32.0), Daniss Jenkins (73.0, 25.0), 2027 R2 DET (own pick) || DET gets Mitchell Robinson (81.1, 28.0), Luka Garza (76.5, 27.0)
2027-02-02 | UTA gets Jaden Hardy (69.1, 24.0), 2033 R2 LAL (own pick) || LAL gets Jaxson Hayes (76.5, 26.0)
2027-02-03 | HOU gets Ben Simmons (73.8, 30.0) || SAC gets Russell Westbrook (72.9, 37.0)   <<< INJURED Ben Simmons out to 2027-04-10
2027-02-03 | MIA gets Drew Peterson (73.2, 26.0) || CHI gets Bobby Portis (74.8, 31.0)
2027-02-04 | TOR gets Jabari Walker (72.6, 24.0) || PHI gets Nimari Burnett (73.0, 24.0)   <<< INJURED Nimari Burnett out to 2027-04-10
2027-02-04 | PHI gets Kobe Sanders (71.7, 24.0) || LAC gets Anfernee Simons (75.9, 27.0)
2027-02-05 | GSW gets 2028 R2: CHA receives the more favourable of CHA/LAC. || CHA gets De'Anthony Melton (76.4, 28.0)
2027-02-05 | BOS gets Gary Payton II (78.3, 33.0), Al Horford (77.4, 40.0), Georges Niang (67.9, 33.0), 2030 R2 GSW (own pick) || GSW gets Neemias Queta (79.7, 27.0)
2027-02-05 | PHI gets Dwight Powell (72.6, 35.0) || DAL gets Dean Wade (75.4, 29.0)
2027-02-05 | NYK gets Daeqwon Plowden (72.3, 28.0) || SAC gets Landry Shamet (72.3, 29.0)
2027-02-05 | NOP gets Grant Williams (72.7, 27.0), 2027 R2: CHA receives the more favourable of NOP/POR., 2031 R1: NOP receives the more favourable of CHA/NOP; CHA re || CHA gets Dejounte Murray (77.4, 30.0)
2027-06-22 | CHI gets 2027 R1 PHI (own pick), 2028 R2: PHI receives the second least favourable of GSW/MIL, 2031 R2 LAC (own pick), 2030 R2: LAC receives the less favourable of LAC/UTA. || LAC gets 2027 R1 CHI (own pick) || PHI gets 2027 R1 TOR (owned by LAC)
2027-06-22 | GSW gets 2034 R1 NYK (own pick), 2029 R2 PHX (owned by NYK), 2029 R2 SAC (owned by NYK) || NYK gets 2027 R1 GSW (own pick)
2027-06-22 | SAS gets 2031 R1 SAC (own pick); 2031 R1: SAS receives the more favou, 2034 R2 SAC (own pick) || SAC gets 2027 R1 ATL (owned by SAS)
2027-06-22 | OKC gets 2027 R2 BKN (owned by WAS), 2031 R2 MIA (owned by WAS); 2031 R2: WAS receives the more f, 2028 R2: WAS receives the less favourable of LAL/WAS., 2028 R2 POR (own pick) || POR gets 2027 R1 DEN (owned by OKC); top-5 protected || WAS gets 2027 R1 POR (own pick)
2027-06-22 | IND gets 2027 R2 MIL (owned by MEM), 2029 R2 HOU (owned by MEM), 2027 R2 CHA (owned by OKC), 2027 R2 CHI (owned by OKC) || MEM gets 2027 R2 SAC (owned by OKC) || OKC gets 2027 R1 IND (own pick)
2027-06-22 | ATL gets 2027 R2 NOP (own pick) || NOP gets 2027 R1 CLE (owned by PHX) || PHX gets 2027 R2 ATL (own pick), 2034 R2 ATL (own pick), 2031 R2 TOR (owned by NOP), 2027 R2 HOU (owned by NOP)
2027-06-22 | PHI gets 2027 R2 LAC (owned by UTA), 2031 R2 UTA (own pick) || UTA gets 2027 R2 PHX (owned by PHI)
2027-06-22 | NYK gets 2034 R2 HOU (own pick), 2031 R2: HOU receives the less favourable of ATL/HOU. || HOU gets 2027 R2 WAS (owned by NYK)
2027-06-22 | PHI gets 2034 R2 LAL (own pick), 2032 R2 WAS (owned by LAL) || LAL gets 2027 R2 MIA (owned by PHI)
2027-06-30 | UTA gets David Jones Garcia (73.8, 24.0), Tobias Harris (74.4, 34.0), 2028 R2 NOP (owned by SAS) || SAS gets Jusuf Nurkić (77.8, 32.0)
2027-06-30 | SAS gets 2028 R2: PHI receives the least favourable of GSW/MIL/OKC. || PHI gets Luke Kornet (77.9, 31.0), 2034 R2 SAS (own pick)
2027-06-30 | PHX gets Will Richard (74.3, 23.0), 2028 R1 GSW (own pick); top-10 protected; GSW keeps this pic || GSW gets Collin Gillespie (78.7, 27.0)
2027-07-01 | DAL gets Aaron Wiggins (75.5, 27.0) || ATL gets Max Christie (71.6, 23.0)
2027-07-01 | MIA gets Jusuf Nurkić (77.8, 32.0), pick_sas-2028-2 || SAS gets Davion Mitchell (74.0, 28.0)
2027-07-01 | CHI gets Tari Eason (76.5, 25.0) || HOU gets Obi Toppin (77.9, 28.0)   <<< CONTENDER_SENDS HOU (2 rounds): Tari Eason (76.5, 25.0)
2027-07-01 | CHA gets 2030 R2 PHI (owned by NYK) || NYK gets Cameron Williams (None, None)
2027-07-01 | MEM gets 2029 R2: IND receives the more favourable of IND/WAS. || IND gets Scotty Pippen Jr. (76.9, 25.0)
2027-07-01 | CHA gets Khris Middleton (73.9, 35.0), 2034 R2 WAS (own pick) || UTA gets 2028 R2 DEN (owned by WAS); picks 31-33 protected; DEN keeps, 2030 R2: WAS receives the least favourable of PHX/POR/WAS., 2032 R2 UTA (owned by WAS); 2032 R2: MEM receives the more f || WAS gets Amari Allen (None, None), Brady Koehler (None, None)
2027-07-02 | TOR gets Karlo Matković (76.0, 25.0), pick_nop-2030-2 || NOP gets RJ Barrett (76.9, 26.0)
2027-07-03 | MEM gets 2030 R2 MEM (owned by MIN); picks 31-50 protected; MEM keeps || MIN gets Obinna Ekezie Jr. (None, None)
2027-07-03 | LAL gets Rudy Gobert (79.2, 34.0), 2034 R2 MIN (own pick), 2034 R1: LAL receives the more favourable of MIN/LAL; MIN re || MIN gets Walker Kessler (81.7, 25.0)
2027-07-04 | NYK gets Julian Champagnie (75.4, 25.0), pick_sas-2029-2 || SAS gets Josh Hart (78.0, 31.0)
2027-08-01 | MEM gets E.J. Liddell (73.2, 25.0), Branden Carlson (74.6, 27.0), 2030 R1: WAS receives the more favourable of WAS/PHX; PHX re || WAS gets Javon Small (75.2, 23.0)
2027-08-01 | CHI gets Nate Bittle (73.0, 23.0) || TOR gets Jay Huff (75.1, 29.0)
2027-08-01 | CLE gets Anthony Pritchard (73.0, 23.0) || POR gets Josh Okogie (74.8, 28.0)   <<< CONTENDER_SENDS CLE (2 rounds): Josh Okogie (74.8, 28.0)
2027-09-15 | PHX gets nothing || MEM gets Jonathan Isaac (79.7, 29.0)   <<< GIVEAWAY PHX gets nothing
flags {'injured': 3, 'contender_sends': 2, 'giveaway': 1}
per team [('PHI', 8), ('CHI', 7), ('MEM', 7), ('SAS', 6), ('CHA', 5), ('HOU', 5), ('WAS', 5), ('UTA', 5), ('NYK', 5), ('IND', 4), ('NOP', 4), ('MIA', 4), ('OKC', 4), ('LAL', 4), ('GSW', 4), ('POR', 3), ('LAC', 3), ('SAC', 3), ('TOR', 3), ('PHX', 3), ('DET', 2), ('CLE', 2), ('BOS', 2), ('DAL', 2), ('ATL', 2), ('MIN', 2), ('MIL', 1)]
```

## Seed 20261127, before

```
52 trades; by month [('2026-11', 2), ('2026-12', 1), ('2027-01', 7), ('2027-02', 14), ('2027-06', 13), ('2027-07', 10), ('2027-08', 4), ('2027-09', 1)]
2026-11-04 | IND gets Svi Mykhailiuk (72.6, 29.0), Jusuf Nurkić (77.8, 32.0), 2027 R2 LAC (owned by UTA), 2033 R2 UTA (own pick) || UTA gets Ivica Zubac (79.0, 29.0)
2026-11-14 | OKC gets Anthony Gill (70.4, 33.0) || WAS gets Nikola Topić (74.0, 21.0)
2026-12-20 | SAS gets Khris Middleton (73.9, 35.0), 2028 R1: WAS receives the more favourable of the pick alloca || WAS gets Carter Bryant (74.1, 20.0)   <<< FIRST_FOR_BENCH WAS (10.8 min over 45 games)
2027-01-07 | PHI gets 2027 R2 ATL (owned by DAL); picks 31-55 protected; ATL keeps || DAL gets Adem Bona (75.8, 23.0), 2028 R2 DET (owned by PHI); picks 31-55 protected; DET keeps   <<< INJURED Adem Bona out to 2027-11-26
2027-01-08 | CHA gets Clint Capela (73.1, 32.0), 2031 R2: HOU receives the less favourable of ATL/HOU. || HOU gets Obi Toppin (77.9, 28.0), Sion James (71.6, 23.0) || IND gets Steven Adams (75.7, 33.0)
2027-01-08 | IND gets Jaden Hardy (69.1, 24.0), 2031 R2 WAS (owned by LAL), 2032 R2 WAS (owned by LAL) || LAL gets Kelly Oubre Jr. (75.8, 30.0)
2027-01-13 | CHI gets Dean Wade (75.4, 29.0), 2027 R2 ATL (owned by PHI); picks 31-55 protected; ATL keeps || LAL gets Jabari Walker (72.6, 24.0) || PHI gets Matisse Thybulle (74.5, 29.0), Orlando Robinson (73.6, 26.0)
2027-01-28 | DET gets Tim Hardaway Jr. (70.5, 34.0), 2027 R2: MIA receives the least favourable of HOU/IND/MIA/OK || MIA gets Ronald Holland II (74.8, 21.0)
2027-01-30 | CHA gets Jay Huff (75.1, 29.0) || IND gets Moussa Diabaté (75.9, 24.0)   <<< INJURED Moussa Diabaté out to 2028-01-13
2027-01-31 | GSW gets 2029 R2 TOR (own pick) || TOR gets Gary Payton II (78.3, 33.0)
2027-02-01 | PHX gets Jeremy Sochan (73.0, 23.0), Micah Potter (73.6, 28.0), 2027 R1 POR (own pick), 2027 R2: POR receives the less favourable of NOP/POR. || POR gets Collin Gillespie (78.7, 27.0), 2027 R2: PHX receives the less favourable of BOS/ORL.
2027-02-02 | CHI gets Julian Strawther (71.5, 24.0), 2028 R2 MIN (owned by DEN), 2031 R2 SAC (owned by DEN) || DEN gets Jalen Smith (77.6, 26.0), Jamaree Bouyea (74.5, 27.0) || PHX gets Zeke Nnaji (71.3, 25.0), 2032 R2 SAC (owned by DEN)
2027-02-02 | GSW gets John Collins (78.7, 29.0), 2028 R2: DET receives the less favourable of CHA/LAC., 2027 R2 DET (own pick), 2033 R2 DET (own pick) || DET gets Kristaps Porziņģis (85.7, 31.0)   <<< INJURED Kristaps Porziņģis out to 2027-06-30
2027-02-03 | UTA gets Kris Murray (72.7, 26.0) || MEM gets Josh Okogie (74.8, 28.0)
2027-02-03 | SAS gets Jarred Vanderbilt (75.0, 27.0), 2033 R2 LAL (own pick) || LAL gets Luke Kornet (77.9, 31.0)
2027-02-03 | BOS gets Henri Veesaar (72.7, 22.0) || ATL gets Ron Harper Jr. (74.2, 26.0)   <<< INJURED Henri Veesaar out to 2027-06-30
2027-02-04 | GSW gets Moussa Cisse (75.3, 24.0) || DAL gets Al Horford (77.4, 40.0)
2027-02-04 | OKC gets Drew Peterson (73.2, 26.0) || CHI gets Kenrich Williams (75.4, 31.0)
2027-02-04 | NYK gets Ben Simmons (73.8, 30.0) || SAC gets Landry Shamet (72.3, 29.0), 2028 R2 BOS (owned by NYK); picks 31-45 protected; BOS keeps   <<< INJURED Ben Simmons out to 2027-04-10
2027-02-05 | UTA gets LJ Cryer (73.4, 25.0), Draymond Green (75.9, 36.0), 2027 R2 DET (owned by GSW), 2029 R2 TOR (owned by GSW) || GSW gets Ivica Zubac (79.0, 29.0)
2027-02-05 | SAS gets Tolu Smith (73.1, 26.0) || DET gets Harrison Barnes (72.9, 34.0), 2033 R2 SAS (own pick)
2027-02-05 | MIN gets Kevon Looney (74.9, 30.0) || LAL gets Jaylen Clark (73.0, 24.0)
2027-02-05 | PHI gets Larry Nance Jr. (73.2, 33.0) || IND gets Kentavious Caldwell-Pope (74.0, 33.0)
2027-02-05 | GSW gets Chaz Lanier (72.6, 24.0) || DET gets De'Anthony Melton (76.4, 28.0)
2027-06-22 | HOU gets 2029 R1 CHA (owned by PHX); First resolve protections: If MI, 2032 R2: PHX receives the less favourable of HOU/PHX., 2027 R2 POR (owned by PHX) || PHX gets 2027 R1 PHX (owned by HOU)
2027-06-22 | LAC gets 2027 R1 MIA (own pick) || MIA gets 2027 R2 WAS (owned by NYK), 2029 R2 PHX (owned by NYK), 2028 R2: NYK receives the least favourable of CHI/IND/PHX., 2031 R2 LAC (own pick), 2030 R2: LAC receives the less favourable of LAC/UTA. || NYK gets 2027 R1 TOR (owned by LAC)
2027-06-22 | GSW gets 2034 R1 UTA (own pick), 2028 R2 NYK (owned by UTA), 2027 R2 ORL (owned by UTA) || UTA gets 2027 R1 GSW (own pick)
2027-06-22 | BOS gets 2027 R1 MEM (own pick) || MEM gets 2027 R1 SAS (owned by SAC), 2028 R2 BOS (owned by SAC); picks 31-45 protected; BOS keeps, 2034 R2 SAC (own pick), 2031 R2: BOS receives the less favourable of BOS/CLE., 2030 R2: BOS receives the most favourable of PHX/POR/WAS. || SAC gets 2027 R1 BOS (own pick)
2027-06-22 | IND gets 2027 R1 OKC (owned by TOR) || PHX gets 2027 R2 LAC (owned by IND), 2028 R2: IND receives the second least favourable of CHI/IND, 2034 R2 TOR (own pick), 2027 R2 TOR (own pick) || TOR gets 2027 R1 POR (owned by PHX)
2027-06-22 | DET gets 2034 R1 MIA (own pick) || MIA gets 2027 R1 DET (own pick)
2027-06-22 | IND gets 2027 R2 BOS (owned by POR), 2028 R2 POR (own pick) || POR gets 2027 R2 UTA (owned by IND)
2027-06-22 | PHI gets 2028 R2 DET (owned by DAL); picks 31-55 protected; DET keeps, 2034 R2 DAL (own pick) || DAL gets 2027 R2 IND (owned by PHI)
2027-06-30 | MEM gets 2032 R2 NYK (own pick) || NYK gets Quinten Post (77.6, 26.0)
2027-06-30 | MEM gets Myron Gardner (75.4, 25.0), 2028 R2: MIA receives the least favourable of CHI/IND/PHX. || MIA gets Jason Crowe Jr. (None, None)
2027-06-30 | OKC gets 2034 R2 MIL (own pick) || MIL gets Luigi Suigo (None, None)   <<< CONTENDER_SENDS OKC (4 rounds): Luigi Suigo (None, None)
2027-06-30 | SAS gets Daeqwon Plowden (72.3, 28.0) || SAC gets Jayden Quaintance (70.3, 19.0)   <<< CONTENDER_SENDS SAS (2 rounds): Jayden Quaintance (70.3, 19.0)
2027-06-30 | MEM gets 2032 R2: HOU receives the less favourable of HOU/PHX. || HOU gets Scotty Pippen Jr. (76.9, 25.0)
2027-07-01 | IND gets Klay Thompson (69.2, 36.0), pick_future-mia-2034-2-own || MIA gets Moussa Diabaté (75.9, 24.0)   <<< INJURED Moussa Diabaté out to 2028-01-13
2027-07-01 | LAC gets Saddiq Bey (72.3, 27.0), pick_nop-2030-2 || NOP gets Rui Hachimura (71.6, 28.0)
2027-07-01 | OKC gets 2029 R2 SAC (owned by NYK) || NYK gets Dylan Mingo (None, None)   <<< CONTENDER_SENDS OKC (4 rounds): Dylan Mingo (None, None)
2027-07-02 | ATL gets Tari Eason (76.5, 25.0), Isaiah Crawford (73.6, 24.0), Bruce Thornton (72.5, 23.0), 2028 R1 HOU (own pick); top-10 protected; HOU keeps this pic || HOU gets Nickeil Alexander-Walker (77.5, 28.0)
2027-07-02 | MEM gets Jarrett Allen (82.7, 28.0), 2034 R2 CLE (own pick) || CLE gets Cam Spencer (79.3, 26.0)   <<< CONTENDER_SENDS CLE (3 rounds): Jarrett Allen (82.7, 28.0)
2027-07-03 | CHI gets 2028 R2: PHI receives the least favourable of GSW/MIL/OKC. || PHI gets Zach Collins (77.7, 28.0)
2027-07-03 | BOS gets 2031 R2 TOR (owned by NOP) || NOP gets Mitchell Robinson (81.1, 28.0)   <<< INJURED Mitchell Robinson out to 2027-12-14
2027-07-03 | TOR gets Terrence Shannon Jr. (71.9, 26.0) || MIN gets Trayce Jackson-Davis (75.7, 26.0), 2028 R2 TOR (own pick)
2027-07-03 | BOS gets 2028 R1 GSW (own pick), 2030 R2 GSW (own pick) || GSW gets Payton Pritchard (80.2, 28.0), 2030 R2 CHA (owned by BOS); picks 31-55 protected; CHA keeps
2027-07-04 | CHI gets Khris Middleton (73.9, 35.0), Tobias Harris (74.4, 34.0), 2028 R2 NOP (owned by SAS), 2029 R2 LAC (owned by SAS), Najai Hines (None, None) || MEM gets 2034 R2 SAS (own pick) || SAS gets Norman Powell (77.8, 33.0)   <<< CONTENDER_SENDS SAS (2 rounds): Khris Middleton (73.9, 35.0), Tobias Harris (74.4, 34.0)
2027-08-01 | HOU gets Pete Nance (72.6, 26.0), 2034 R2 NYK (own pick) || NYK gets Taylor Hendricks (74.6, 22.0)
2027-08-01 | MIA gets Juke Harris (None, None) || CHA gets Thomas Bryant (75.8, 29.0), 2031 R2 LAC (owned by MIA)   <<< CONTENDER_SENDS CHA (2 rounds): Juke Harris (None, None)
2027-08-01 | IND gets Kobe Bufkin (74.0, 23.0) || CHI gets Steven Adams (75.7, 33.0), 2033 R2 UTA (owned by IND), 2034 R2 IND (own pick)
2027-08-01 | BOS gets Kobe Sanders (71.7, 24.0) || LAC gets Kenrich Williams (75.4, 31.0)
2027-09-15 | PHI gets Hunter Dickinson (73.3, 25.0), 2033 R2 NYK (own pick) || NYK gets Trentyn Flowers (74.2, 20.0)
PICK_BOUNCE pick_atl-2027-2: PHI 2027-01-07 -> CHI 2027-01-13
PICK_BOUNCE pick_tor-2029-2: GSW 2027-01-31 -> UTA 2027-02-05
PICK_BOUNCE pick_det-2027-2: GSW 2027-02-02 -> UTA 2027-02-05
PICK_BOUNCE pick_hou-2032-2: HOU 2027-06-22 -> MEM 2027-06-30
PICK_BOUNCE pick_phx-2028-2: MIA 2027-06-22 -> MEM 2027-06-30
PICK_BOUNCE pick_lac-2031-2: MIA 2027-06-22 -> CHA 2027-08-01
flags {'first_for_bench': 1, 'injured': 7, 'contender_sends': 6, 'pick_bounce': 6}
per team [('IND', 9), ('GSW', 7), ('MEM', 7), ('PHI', 6), ('CHI', 6), ('MIA', 6), ('NYK', 6), ('SAS', 5), ('HOU', 5), ('DET', 5), ('BOS', 5), ('UTA', 4), ('OKC', 4), ('LAL', 4), ('PHX', 4), ('DAL', 3), ('CHA', 3), ('TOR', 3), ('SAC', 3), ('LAC', 3), ('WAS', 2), ('POR', 2), ('ATL', 2), ('MIN', 2), ('NOP', 2), ('DEN', 1), ('MIL', 1), ('CLE', 1)]
```

## Seed 20261127, after

```
52 trades; by month [('2026-11', 2), ('2026-12', 1), ('2027-01', 7), ('2027-02', 13), ('2027-06', 11), ('2027-07', 13), ('2027-08', 4), ('2027-09', 1)]
2026-11-04 | OKC gets Jericho Sims (68.8, 27.0) || MIL gets Nikola Topić (74.0, 21.0)
2026-11-14 | MEM gets Jarred Vanderbilt (75.0, 27.0), 2032 R2 WAS (owned by LAL) || LAL gets Quinten Post (77.6, 26.0)
2026-12-20 | SAS gets 2030 R1: WAS receives the more favourable of WAS/PHX; PHX re || WAS gets Carter Bryant (74.1, 20.0)   <<< FIRST_FOR_BENCH WAS (10.9 min over 49 games)
2027-01-07 | SAS gets Dean Wade (75.4, 29.0) || PHI gets Luke Kornet (77.9, 31.0)
2027-01-08 | PHI gets 2029 R1: If CHA or PHX holds no pick in this pool after prot || CHA gets Adem Bona (75.8, 23.0), 2028 R2: PHI receives the least favourable of GSW/MIL/OKC.   <<< INJURED Adem Bona out to 2027-11-26
2027-01-08 | PHX gets Johnny Furphy (70.2, 21.0), Larry Nance Jr. (73.2, 33.0), T.J. McConnell (78.0, 34.0), 2028 R1 IND (own pick); top-10 protected; IND keeps this pic || IND gets Collin Gillespie (78.7, 27.0)
2027-01-13 | CHI gets Jay Huff (75.1, 29.0), Obi Toppin (77.9, 28.0), 2027 R2 UTA (owned by IND) || IND gets Jalen Smith (77.6, 26.0)
2027-01-28 | LAL gets Dominick Barlow (73.1, 23.0) || PHI gets Matisse Thybulle (74.5, 29.0)
2027-01-30 | DET gets Tim Hardaway Jr. (70.5, 34.0), 2027 R2: MIA receives the least favourable of HOU/IND/MIA/OK || MIA gets Ronald Holland II (74.8, 21.0)
2027-01-31 | GSW gets 2029 R2 TOR (own pick), 2030 R1: If a compared pick falls in its protected range (MI || SAS gets Gui Santos (75.8, 24.0), 2030 R2 GSW (own pick) || TOR gets Gary Payton II (78.3, 33.0)   <<< FIRST_FOR_BENCH SAS (14.5 min over 34 games)
2027-02-01 | DEN gets Steven Adams (75.7, 33.0), Sean Pedulla (73.6, 24.0), Jae'Sean Tate (71.1, 30.0) || HOU gets Cameron Johnson (77.4, 30.0)
2027-02-02 | UTA gets 2027 R2 DET (own pick) || DET gets Jusuf Nurkić (77.8, 32.0)
2027-02-02 | CHI gets Marcus Smart (76.7, 32.0), Clint Capela (73.1, 32.0) || HOU gets Zach Collins (77.7, 28.0)
2027-02-03 | IND gets Cody Williams (68.3, 21.0), 2028 R1 MIN (own pick); 2028 R1: CHA receives the more favou, 2030 R2 MEM (owned by MIN); picks 31-50 protected; MEM keeps || MIN gets Kelly Oubre Jr. (75.8, 30.0)
2027-02-03 | BOS gets Henri Veesaar (72.7, 22.0) || ATL gets Ron Harper Jr. (74.2, 26.0)   <<< INJURED Henri Veesaar out to 2027-06-30
2027-02-04 | CHI gets Harrison Barnes (72.9, 34.0), Tobias Harris (74.4, 34.0), 2028 R1 SAS (own pick); 2028 R1: If a compared pick falls in || SAS gets Norman Powell (77.8, 33.0)
2027-02-04 | OKC gets Dwight Powell (72.6, 35.0) || DAL gets Kenrich Williams (75.4, 31.0)
2027-02-04 | MIN gets Sion James (71.6, 23.0) || CHA gets Jaylen Clark (73.0, 24.0)
2027-02-04 | NYK gets Ben Simmons (73.8, 30.0) || SAC gets Landry Shamet (72.3, 29.0), 2028 R2 BOS (owned by NYK); picks 31-45 protected; BOS keeps   <<< INJURED Ben Simmons out to 2027-04-10
2027-02-05 | MIN gets Moussa Cisse (75.3, 24.0) || DAL gets Jonathan Kuminga (76.0, 24.0)
2027-02-05 | GSW gets Micah Potter (73.6, 28.0) || POR gets Al Horford (77.4, 40.0)
2027-02-05 | PHI gets Kevon Looney (74.9, 30.0) || LAL gets Kentavious Caldwell-Pope (74.0, 33.0)
2027-02-05 | UTA gets Jaden Hardy (69.1, 24.0) || LAL gets Josh Okogie (74.8, 28.0)
2027-06-22 | LAC gets 2027 R1 DEN (owned by OKC); top-5 protected || MIA gets 2027 R1 TOR (owned by LAC), 2031 R2 LAC (own pick), 2028 R2 UTA (owned by OKC), 2027 R2 CHI (owned by OKC) || OKC gets 2027 R1 MIA (own pick)
2027-06-22 | GSW gets 2031 R1 CLE (owned by DEN), 2028 R2 MIN (owned by DEN), 2032 R2 SAC (owned by DEN) || DEN gets 2027 R1 GSW (own pick)
2027-06-22 | PHI gets 2027 R1 SAS (owned by SAC), 2031 R1 MIN (owned by SAC), 2027 R2 POR (own pick), 2029 R2: POR receives the less favourable of IND/WAS. || POR gets 2027 R1 PHI (own pick) || SAC gets 2027 R1 POR (own pick)
2027-06-22 | MEM gets 2027 R1 OKC (owned by TOR), 2034 R2 TOR (own pick), 2027 R2 BOS (owned by PHX), 2034 R2 PHX (own pick) || PHX gets 2027 R1 MEM (own pick) || TOR gets 2027 R1 CLE (owned by PHX)
2027-06-22 | MEM gets 2034 R1 PHI (own pick) || PHI gets 2027 R1 LAL (owned by MEM); top-4 protected
2027-06-22 | BOS gets 2027 R1 DET (own pick) || DET gets 2027 R2 WAS (owned by NYK), 2028 R2: NYK receives the least favourable of CHI/IND/PHX., 2033 R2 BOS (own pick) || NYK gets 2027 R1 BOS (own pick)
2027-06-30 | MIA gets Andrew Nembhard (75.1, 26.0) || IND gets Andrew Wiggins (76.9, 31.0)   <<< CONTENDER_SENDS IND (2 rounds): Andrew Nembhard (75.1, 26.0)
2027-06-30 | CHA gets Myron Gardner (75.4, 25.0), 2034 R2 MIA (own pick) || MIA gets Dylan Mingo (None, None)
2027-06-30 | CHA gets 2030 R2 TOR (owned by LAC) || LAC gets Jason Crowe Jr. (None, None)
2027-06-30 | SAS gets 2033 R2 ATL (owned by DAL) || DAL gets Amari Allen (None, None)
2027-06-30 | ATL gets Ayo Dosunmu (74.6, 26.0), 2030 R1 MIN (own pick); 2030 R1 connected allocation — apply, 2034 R1 MIN (own pick) || MIN gets Onyeka Okongwu (79.6, 25.0)
2027-07-01 | CHA gets Klay Thompson (69.2, 36.0) || MIA gets Moussa Diabaté (75.9, 24.0)   <<< INJURED Moussa Diabaté out to 2028-01-13
2027-07-01 | LAC gets Saddiq Bey (72.3, 27.0), pick_nop-2030-2 || NOP gets Rui Hachimura (71.6, 28.0)
2027-07-01 | CHI gets Trayce Jackson-Davis (75.7, 26.0) || LAL gets Ja'Kobe Walter (74.9, 22.0), 2028 R2 TOR (own pick) || TOR gets Buddy Hield (74.3, 33.0), 2034 R2 LAL (own pick)
2027-07-02 | DEN gets LJ Cryer (73.4, 25.0), pick_future-gsw-2034-2-own || GSW gets Marvin Bagley III (74.1, 27.0)
2027-07-02 | DAL gets Dorian Finney-Smith (69.4, 33.0), 2033 R2 SAC (owned by ATL) || ATL gets Daniel Gafford (79.3, 28.0)
2027-07-02 | SAS gets Scotty Pippen Jr. (76.9, 25.0), Elijah Crawford (None, None) || MEM gets Julian Champagnie (75.4, 25.0)
2027-07-03 | HOU gets Kevin Huerter (73.3, 28.0), pick_det-2029-2 || DET gets Fred VanVleet (76.6, 32.0)   <<< CONTENDER_SENDS DET (3 rounds): Kevin Huerter (73.3, 28.0)
2027-07-03 | NYK gets Bennedict Mathurin (72.7, 24.0), pick_nop-2032-2 || NOP gets Miles McBride (75.2, 26.0)
2027-07-03 | CHA gets Vít Krejčí (72.8, 26.0), 2028 R2 POR (own pick), Robert Williams III (79.6, 28.0) || POR gets Ryan Kalkbrenner (79.2, 24.0)
2027-07-03 | ATL gets Tari Eason (76.5, 25.0), Isaiah Crawford (73.6, 24.0), 2028 R1 HOU (own pick); top-4 protected; HOU keeps this pick || HOU gets Nickeil Alexander-Walker (77.5, 28.0)
2027-07-03 | TOR gets 2029 R2 SAC (owned by NYK) || NYK gets Luigi Suigo (None, None)
2027-07-03 | GSW gets Ivica Zubac (79.0, 29.0), 2032 R1 IND (own pick) || IND gets Kristaps Porziņģis (85.7, 31.0)   <<< CONTENDER_SENDS IND (2 rounds): Ivica Zubac (79.0, 29.0)
2027-07-04 | MEM gets James Harden (80.0, 37.0), 2034 R2 CLE (own pick) || CLE gets Cam Spencer (79.3, 26.0)
2027-08-01 | CHI gets Quinten Post (77.6, 26.0), Dalton Knecht (71.8, 25.0), 2031 R2 WAS (owned by LAL) || LAL gets Marcus Smart (76.7, 32.0)   <<< INJURED Marcus Smart out to 2028-05-28; CONTENDER_SENDS LAL (2 rounds): Quinten Post (77.6, 26.0), Dalton Knecht (71.8, 25.0)
2027-08-01 | HOU gets Hunter Dickinson (73.3, 25.0), 2032 R2 DAL (owned by NYK) || NYK gets Lonzo Ball (77.6, 28.0)
2027-08-01 | UTA gets Ochai Agbaji (72.1, 26.0) || PHX gets Jaxson Hayes (76.5, 26.0), 2034 R2 UTA (own pick)
2027-08-01 | NYK gets Alondes Williams (73.5, 27.0) || IND gets Matisse Thybulle (74.5, 29.0)   <<< CONTENDER_SENDS IND (2 rounds): Alondes Williams (73.5, 27.0)
2027-09-15 | NOP gets Tolu Smith (73.1, 26.0) || DAL gets Yves Missi (75.7, 22.0)
flags {'first_for_bench': 2, 'injured': 5, 'contender_sends': 5}
per team [('LAL', 6), ('SAS', 6), ('PHI', 6), ('CHA', 6), ('IND', 6), ('NYK', 6), ('MEM', 5), ('CHI', 5), ('MIA', 5), ('GSW', 5), ('HOU', 5), ('DAL', 5), ('DET', 4), ('TOR', 4), ('MIN', 4), ('ATL', 4), ('OKC', 3), ('PHX', 3), ('DEN', 3), ('UTA', 3), ('POR', 3), ('LAC', 3), ('NOP', 3), ('BOS', 2), ('SAC', 2), ('MIL', 1), ('WAS', 1), ('CLE', 1)]
```
