# Starting data audit — October 13, 2026

## Scope

This update applies to new saves only. Existing saves use the archived July 28 universe and retain their roster, contract, and pick overlays. The offseason start date remains July 28, 2026.

## Coverage

- All 30 official NBA team rosters: 616 listed players, each mapped once.
- All 420 underlying first- and second-round picks, 2027–2033: one asset for every team/year/round.
- 232 baseline owner entries changed; conditional assets use 17 native protection terms and 68 comparison terms.
- Returning player trait values preserved exactly.
- Five Clippers-controlled firsts are forfeited; they cannot be traded or selected. Incoming Toronto firsts remain valid.
- Four frozen firsts remain unavailable for ordinary trades.

## Brooklyn findings

The old owner-side prose importer could assign an originating pick to a team mentioned in a swap clause and collapse overlapping rights. The new importer consumes a reviewed underlying-pick ledger rather than guessing the originating team from the first abbreviation in a description.

- Brooklyn retains its own 2027–2033 firsts before conditional settlement.
- New York 2027, 2029, and 2031 firsts and Denver 2032 first are assigned Brooklyn.
- Philadelphia 2028 first is top-8 protected; Brooklyn has modeled Phoenix and New York swap rights.
- Houston holds the 2027 swap with Brooklyn. This is a conditional right, not an additional unconditional Houston pick for Brooklyn.
- Brooklyn receives the worst of Houston/Dallas/Phoenix 2029 firsts; Houston receives the other two. All six possible relative orderings were audited.
- Incoming Atlanta/Memphis/Golden State/Dallas/Boston/Lakers/Denver/Miami/Toronto seconds are restored where the published ledger assigns them.

## Roster changes from the previous released snapshot

Listed changes include current camp and supplemental memberships. A removed name means absent from the current official roster, not necessarily retirement.

| Team | Listed players | Added to official roster | Removed from official roster |
| --- | ---: | --- | --- |
| ATL | 21 | Cameron Corhen, Dorian Finney-Smith, Isaac McKneely, Kobe Johnson | Buddy Hield, Devin Carter, Gabe Vincent, Jonathan Kuminga, Keaton Wallace, Ryan Nembhard, Tony Bradley |
| BKN | 19 | Ben Humrichous, Grant Nelson, Moritz Wagner | E.J. Liddell, Tyson Etienne |
| BOS | 21 | Devin Carter, Gabe McGlothan, Hayden Gray | Max Shulga |
| CHA | 21 | Dennis Schröder, Jarkel Joiner, Wyatt Fricks | Antonio Reeves, Dorian Finney-Smith, Mouhamadou Gueye, Tre Mann, Xavier Tillman |
| CHI | 21 | Brandon Boston, Buddy Hield, Drew Peterson, Jalen Bridges, Jordan Hawkins, Orlando Robinson | Rob Dillingham |
| CLE | 21 | Jaxson Robinson, Khalifa Diop, Mario Hezonja, Noam Yaacov, Peyton Watson, Rashaun Agee, Zack Austin | Dennis Schröder, Max Strus, Olivier Sarr |
| DAL | 21 | Matt Cross, Seth Lundy | Brandon Williams, Klay Thompson, Vsevolod Ishchenko |
| DEN | 20 | Cam Whitmore, Coleman Hawkins, Dane Goodwin, DeMar DeRozan, Emanuel Miller, Ryan Nembhard | Bruce Brown, Curtis Jones, David Roddy, Jalen Pickett, KJ Simpson, Peyton Watson |
| DET | 20 | Brice Williams, John Ukomadu | Gary Harris, Wendell Moore Jr. |
| GSW | 21 | Alex Toohey, Brandon Williams, Dalen Terry, Georges Niang, Graham Ike, Tyler Burton | Lajae Jones, Nate Williams, Seth Curry |
| HOU | 18 | Sean Pedulla | Aaron Holiday, JD Davison, Jeff Green, Tristen Newton |
| IND | 20 | James Johnson, Keba Keita, Rienk Mast | Ethan Thompson |
| LAC | 21 | Blake Wesley, Brandon Ingram, Gradey Dick, Jahmyl Telfort, Jalen Pickett, Max Strus, Yuki Kawamura | Bennedict Mathurin, Kawhi Leonard, Narcisse Ngoy, Nicolas Batum, Norchad Omier, Sean Pedulla, TyTy Washington Jr. |
| LAL | 21 | Cole Swider, Rafael Castro | — |
| MEM | 20 | Carson Cooper, Micah Peavy | AJ Johnson, D'Angelo Russell, Richie Saunders, Taj Gibson |
| MIA | 21 | Bez Mbeng, Gabe Madsen, Ian Schieffelin, Klay Thompson, Kylor Kelley, Nick Richards | Jahmir Young, Trevor Keels |
| MIL | 21 | Jake Stephens, Johni Broome | Alex Antetokounmpo, Andre Jackson Jr., Malique Lewis, Thanasis Antetokounmpo |
| MIN | 21 | Antonio Reeves, Cody Williams, Drew Timme, Jonathan Kuminga, KJ Martin, Norchad Omier | Joe Ingles, Josh Green, Trey Kaufman-Renn |
| NOP | 20 | AJ Johnson, Bennedict Mathurin, Jalon Moore, Julian Reese, Malik Dia, Trendon Watford | Christian Koloko, Hunter Dickinson, Jordan Hawkins, Josh Oduro, Micah Peavy |
| NYK | 21 | Bruce Brown, Drew Eubanks, Jaden Akins, James Wiseman, Ochai Agbaji, Tony Bradley | Dillon Jones, Jack Kayil, Jeremy Sochan, Trey Jemison III |
| OKC | 21 | Andrew Holifield, Anthony Pritchard, Christoph Tilly, Zhaire Smith | — |
| ORL | 20 | JD Davison, Kevin Knox II, Malaki Branham | Moritz Wagner |
| PHI | 21 | Dillon Jones, Jameer Nelson Jr., Kentavious Caldwell-Pope, Saint Thomas, Tacko Fall | Johni Broome, Kyle Lowry, MarJon Beauchamp, Trendon Watford, Tyrese Martin |
| PHX | 21 | Duop Reath, Kennedy Chandler, Phillip Wheeler | Amir Coffey, Isaiah Livers |
| POR | 18 | Jeremy Sochan | Blake Wesley |
| SAC | 21 | Aaron Nkrumah, Ben Simmons, Damari Monsanto, Elfrid Payton, Leaky Black, Tristen Newton | Doug McDermott, Drew Eubanks, Killian Hayes, Patrick Baldwin Jr., Russell Westbrook |
| SAS | 21 | Jon Elmore, Malik Williams, R.J. Davis, Taelon Peter | Bismack Biyombo, Kelly Olynyk, Lindy Waters III, Mason Plumlee |
| TOR | 21 | Jamarion Sharp, Kawhi Leonard, Malachi Smith, Nimari Burnett, Trey Jemison III, Tyreke Key, Tyson Degenhart | A.J. Lawson, Brandon Ingram, Chucky Hepburn, Gradey Dick |
| UTA | 21 | Jonas Aidoo, Josh Green, Mohamed Wague, Taylor Funk | Bez Mbeng, Cody Williams, Hayden Gray, John Konchar, Kevin Love |
| WAS | 21 | Alondes Williams, Chris Livingston, Reece Beekman, Tre Mann, Trevor Keels | Cam Whitmore, Julian Reese, Sharife Cooper |

## Pick owner changes

These are starting allocation slots. Conditional comparisons can change which originating pick ultimately fills a slot. The game uses supported swap/protection wording; published nested exceptions are normalized below.

| Origin | Year | Round | Previous slot owner | New slot owner |
| --- | --- | --- | --- | --- |
| ATL | 2027 | 1 | MIL | SAS |
| ATL | 2027 | 2 | ATL | DAL |
| ATL | 2028 | 2 | ATL | BKN |
| ATL | 2029 | 2 | CLE | CHA |
| ATL | 2030 | 2 | NYK | OKC |
| ATL | 2031 | 2 | ATL | OKC |
| ATL | 2032 | 2 | ATL | OKC |
| BKN | 2027 | 1 | NYK | BKN |
| BKN | 2027 | 2 | BKN | WAS |
| BKN | 2028 | 2 | ATL | BKN |
| BKN | 2029 | 1 | NYK | BKN |
| BKN | 2029 | 2 | DAL | BKN |
| BKN | 2030 | 2 | BOS | BKN |
| BKN | 2031 | 1 | NYK | BKN |
| BKN | 2031 | 2 | LAL | BKN |
| BKN | 2032 | 1 | DEN | BKN |
| BKN | 2032 | 2 | DEN | BKN |
| BOS | 2027 | 2 | BOS | UTA |
| BOS | 2028 | 1 | LAC | BOS |
| BOS | 2028 | 2 | MIL | NYK |
| BOS | 2029 | 1 | BOS | POR |
| BOS | 2029 | 2 | BOS | OKC |
| BOS | 2030 | 2 | WAS | BKN |
| BOS | 2031 | 1 | PHI | BOS |
| BOS | 2031 | 2 | BOS | UTA |
| CHA | 2027 | 2 | MEM | OKC |
| CHA | 2028 | 1 | MIN | CHA |
| CHA | 2028 | 2 | HOU | CHA |
| CHA | 2029 | 1 | CLE | PHX |
| CHA | 2029 | 2 | DEN | CHA |
| CHA | 2031 | 2 | MIL | CHA |
| CHA | 2032 | 2 | MIL | CHA |
| CHA | 2033 | 1 | MIN | CHA |
| CHI | 2027 | 2 | CLE | OKC |
| CHI | 2029 | 2 | NYK | CHI |
| CHI | 2030 | 2 | IND | CHI |
| CHI | 2031 | 2 | DEN | CHI |
| CHI | 2032 | 2 | HOU | CHI |
| CLE | 2027 | 1 | CLE | MEM |
| CLE | 2027 | 2 | CLE | CHI |
| CLE | 2028 | 2 | CLE | UTA |
| CLE | 2029 | 1 | CLE | CHA |
| CLE | 2029 | 2 | CLE | ATL |
| CLE | 2030 | 2 | CLE | SAS |
| CLE | 2031 | 1 | CLE | DEN |
| CLE | 2031 | 2 | CLE | BOS |
| CLE | 2032 | 2 | SAC | UTA |
| DAL | 2027 | 2 | DAL | MIL |
| DAL | 2028 | 1 | OKC | DAL |
| DAL | 2028 | 2 | DAL | LAC |
| DAL | 2029 | 1 | LAL | BKN |
| DAL | 2029 | 2 | HOU | BKN |
| DAL | 2030 | 2 | DAL | BKN |
| DAL | 2031 | 2 | DAL | DET |
| DAL | 2032 | 2 | DAL | NYK |
| DAL | 2033 | 2 | DAL | WAS |
| DEN | 2027 | 2 | DEN | UTA |
| DEN | 2028 | 1 | OKC | DEN |
| DEN | 2029 | 2 | DEN | CHA |
| DEN | 2030 | 1 | OKC | DEN |
| DEN | 2030 | 2 | DEN | MEM |
| DEN | 2031 | 2 | SAC | CHI |
| DEN | 2032 | 1 | DEN | BKN |
| DEN | 2032 | 2 | DEN | BKN |
| DET | 2028 | 2 | MIA | PHI |
| DET | 2029 | 2 | MIL | DET |
| DET | 2031 | 2 | DAL | OKC |
| GSW | 2027 | 2 | GSW | PHI |
| GSW | 2028 | 2 | GSW | BOS |
| GSW | 2029 | 2 | GSW | BKN |
| GSW | 2030 | 2 | WAS | GSW |
| GSW | 2031 | 2 | GSW | DET |
| HOU | 2027 | 1 | PHX | HOU |
| HOU | 2027 | 2 | POR | PHI |
| HOU | 2028 | 2 | HOU | CHA |
| HOU | 2029 | 1 | DAL | HOU |
| HOU | 2029 | 2 | HOU | MEM |
| HOU | 2030 | 2 | HOU | OKC |
| HOU | 2031 | 2 | BOS | HOU |
| HOU | 2032 | 2 | HOU | PHX |
| HOU | 2033 | 2 | HOU | CHA |
| IND | 2027 | 2 | UTA | NOP |
| IND | 2029 | 2 | WAS | IND |
| LAC | 2027 | 1 | OKC | LAC |
| LAC | 2027 | 2 | LAC | UTA |
| LAC | 2028 | 1 | LAC | BOS |
| LAC | 2028 | 2 | DAL | DET |
| LAC | 2029 | 1 | IND | LAC |
| LAC | 2029 | 2 | LAC | SAS |
| LAC | 2030 | 2 | LAC | CHA |
| LAL | 2027 | 2 | LAL | BKN |
| LAL | 2028 | 2 | LAL | ORL |
| LAL | 2029 | 1 | LAL | DAL |
| LAL | 2029 | 2 | LAL | MEM |
| LAL | 2030 | 1 | UTA | LAL |
| LAL | 2030 | 2 | LAL | BKN |
| LAL | 2031 | 1 | LAL | UTA |
| LAL | 2031 | 2 | WAS | BKN |
| LAL | 2032 | 2 | WAS | OKC |
| LAL | 2033 | 1 | LAL | UTA |
| MEM | 2027 | 1 | UTA | MEM |
| MEM | 2027 | 2 | MEM | CHA |
| MEM | 2028 | 2 | MEM | BKN |
| MEM | 2029 | 1 | ORL | MEM |
| MEM | 2029 | 2 | POR | BKN |
| MEM | 2030 | 1 | ORL | MEM |
| MEM | 2031 | 1 | PHX | MEM |
| MEM | 2032 | 2 | PHI | MEM |
| MIA | 2027 | 2 | OKC | NYK |
| MIA | 2028 | 1 | CHA | MIA |
| MIA | 2028 | 2 | MIA | DET |
| MIA | 2029 | 2 | MIA | OKC |
| MIA | 2030 | 2 | MIA | OKC |
| MIA | 2031 | 1 | MIA | MIL |
| MIA | 2031 | 2 | MIA | WAS |
| MIA | 2032 | 2 | MIA | BKN |
| MIA | 2033 | 1 | MIA | MIL |
| MIA | 2033 | 2 | MIA | MIL |
| MIL | 2027 | 1 | MIL | NOP |
| MIL | 2027 | 2 | DAL | MIL |
| MIL | 2028 | 1 | POR | MIL |
| MIL | 2028 | 2 | MIL | PHI |
| MIL | 2029 | 1 | MIL | WAS |
| MIL | 2029 | 2 | MIL | DET |
| MIL | 2030 | 2 | MIL | ORL |
| MIL | 2031 | 1 | MIA | MIL |
| MIL | 2031 | 2 | MIL | CHA |
| MIL | 2032 | 2 | MIL | CHA |
| MIL | 2033 | 1 | MIA | MIL |
| MIN | 2027 | 1 | MIN | PHX |
| MIN | 2027 | 2 | MIN | POR |
| MIN | 2028 | 1 | CHA | MIN |
| MIN | 2028 | 2 | MIN | DEN |
| MIN | 2029 | 2 | MIN | CHA |
| MIN | 2030 | 2 | MIN | OKC |
| MIN | 2031 | 1 | MIN | SAC |
| MIN | 2031 | 2 | MIN | CHI |
| MIN | 2032 | 2 | MIN | CHA |
| MIN | 2033 | 1 | MIN | CHA |
| MIN | 2033 | 2 | MIN | CHA |
| NOP | 2027 | 1 | NOP | ATL |
| NOP | 2027 | 2 | HOU | CHA |
| NOP | 2028 | 2 | NOP | SAS |
| NOP | 2029 | 2 | NOP | SAS |
| NOP | 2030 | 2 | ORL | NOP |
| NOP | 2031 | 2 | TOR | ORL |
| NYK | 2027 | 1 | NYK | BKN |
| NYK | 2027 | 2 | WAS | NYK |
| NYK | 2028 | 1 | BKN | NYK |
| NYK | 2028 | 2 | BOS | UTA |
| NYK | 2029 | 1 | NYK | BKN |
| NYK | 2029 | 2 | PHX | CHI |
| NYK | 2030 | 2 | PHI | ATL |
| NYK | 2031 | 1 | NYK | BKN |
| NYK | 2031 | 2 | NYK | CHI |
| NYK | 2032 | 2 | DAL | NYK |
| OKC | 2027 | 1 | SAC | OKC |
| OKC | 2027 | 2 | CHA | MIA |
| OKC | 2028 | 1 | DAL | OKC |
| OKC | 2028 | 2 | UTA | PHI |
| OKC | 2029 | 2 | BOS | OKC |
| OKC | 2030 | 2 | ATL | OKC |
| OKC | 2031 | 2 | ATL | OKC |
| OKC | 2032 | 2 | LAL | OKC |
| OKC | 2033 | 2 | OKC | MEM |
| ORL | 2027 | 2 | ORL | PHX |
| ORL | 2028 | 1 | ORL | POR |
| ORL | 2028 | 2 | WAS | CHA |
| ORL | 2029 | 1 | MEM | ORL |
| ORL | 2029 | 2 | MEM | ORL |
| ORL | 2030 | 1 | ORL | MEM |
| ORL | 2030 | 2 | MIL | ORL |
| ORL | 2031 | 2 | NOP | OKC |
| PHI | 2027 | 2 | MIA | WAS |
| PHI | 2028 | 2 | BKN | PHI |
| PHI | 2029 | 1 | LAC | PHI |
| PHI | 2030 | 2 | POR | NYK |
| PHI | 2031 | 1 | PHI | BOS |
| PHX | 2027 | 1 | CLE | HOU |
| PHX | 2027 | 2 | PHX | WAS |
| PHX | 2028 | 2 | PHX | NYK |
| PHX | 2029 | 1 | CHA | HOU |
| PHX | 2029 | 2 | PHX | NYK |
| PHX | 2030 | 2 | PHX | BOS |
| PHX | 2031 | 1 | PHX | MEM |
| PHX | 2031 | 2 | PHX | CHA |
| PHX | 2032 | 2 | PHX | CHI |
| PHX | 2033 | 1 | PHX | CHA |
| PHX | 2033 | 2 | PHX | NYK |
| POR | 2027 | 2 | MIN | POR |
| POR | 2028 | 1 | ORL | POR |
| POR | 2028 | 2 | CHI | POR |
| POR | 2029 | 1 | BOS | POR |
| POR | 2029 | 2 | IND | MEM |
| POR | 2030 | 1 | MIL | POR |
| POR | 2030 | 2 | POR | PHI |
| SAC | 2027 | 2 | SAC | OKC |
| SAC | 2028 | 2 | SAC | POR |
| SAC | 2029 | 2 | SAC | NYK |
| SAC | 2030 | 2 | SAC | SAS |
| SAC | 2031 | 1 | MIN | SAC |
| SAC | 2031 | 2 | SAC | DEN |
| SAC | 2032 | 2 | SAC | DEN |
| SAC | 2033 | 2 | SAC | ATL |
| SAS | 2027 | 1 | ATL | SAC |
| SAS | 2028 | 1 | BOS | SAS |
| SAS | 2028 | 2 | NOP | SAS |
| SAS | 2029 | 2 | LAC | SAS |
| SAS | 2030 | 2 | CLE | SAS |
| SAS | 2031 | 1 | SAC | SAS |
| TOR | 2030 | 2 | TOR | LAC |
| TOR | 2031 | 1 | TOR | LAC |
| TOR | 2031 | 2 | TOR | NOP |
| TOR | 2032 | 2 | TOR | BKN |
| TOR | 2033 | 1 | TOR | LAC |
| TOR | 2033 | 2 | TOR | LAC |
| UTA | 2027 | 1 | MIN | UTA |
| UTA | 2027 | 2 | LAL | IND |
| UTA | 2028 | 2 | CLE | OKC |
| UTA | 2030 | 1 | LAL | UTA |
| UTA | 2031 | 1 | LAL | UTA |
| UTA | 2031 | 2 | CLE | UTA |
| UTA | 2032 | 2 | CLE | WAS |
| UTA | 2033 | 1 | LAL | UTA |
| WAS | 2027 | 2 | BOS | NYK |
| WAS | 2028 | 2 | LAL | WAS |
| WAS | 2029 | 1 | POR | WAS |
| WAS | 2029 | 2 | LAL | POR |
| WAS | 2030 | 2 | PHX | WAS |
| WAS | 2031 | 2 | MIA | LAL |
| WAS | 2032 | 2 | UTA | LAL |
| WAS | 2033 | 2 | WAS | MEM |

## Conditional-rule normalization

The game continues to use `protected_pick` and `pick_swap` terms. Protection collateral must be a distinct same-round pick in the same or a later year. Fallbacks do not use a forfeited asset or an asset already participating in a modeled swap. Shared favorability pools settle through ordinary same-year, same-round comparisons; their comparison steps are not extra assets that can be sold separately.

Some published clauses cannot be represented exactly in that language: first-to-second conversions, historical-conveyance tests, median-of-three rights, nested exceptions, and unspecified future years. The specific substitutions are recorded here and in the research ledger.

| Case | Game rule |
| --- | --- |
| 2027 second via LAC | LAC own second remains owed to UTA. WAS receives the PHI median-pool entitlement acquired via LAC; normalized to PHI own second as documented below. |
| 2027 R1 ranked pool CLE/UTA/MIN | Shared allocation normalized to ranked slots MEM/UTA/PHX. Native two-pick comparisons preserve allocation counts; nested source exceptions are removed. |
| 2029 R1 ranked pool HOU/PHX/DAL | Shared allocation normalized to ranked slots HOU/HOU/BKN. Native two-pick comparisons preserve allocation counts; nested source exceptions are removed. |
| 2029 POR/BOS/MIL median right | WAS receives the less favorable of BOS/MIL; POR retains its own and the better of BOS/MIL. The IRL median-of-three clause is simplified to a two-pick comparison. |
| 2027 R2 ranked pool HOU/IND/MIA/OKC | Shared allocation normalized to ranked slots PHI/NOP/NYK/MIA. Native two-pick comparisons preserve allocation counts; nested source exceptions are removed. |
| 2028 R2 ranked pool GSW/MIL/OKC | Shared allocation normalized to ranked slots BOS/PHI/PHI. Native two-pick comparisons preserve allocation counts; nested source exceptions are removed. |
| 2028 R2 ranked pool CHI/IND/PHX | Shared allocation normalized to ranked slots CHI/IND/NYK. Native two-pick comparisons preserve allocation counts; nested source exceptions are removed. |
| 2029 R2 ranked pool DET/MIL/NYK | Shared allocation normalized to ranked slots DET/DET/CHI. Native two-pick comparisons preserve allocation counts; nested source exceptions are removed. |
| 2030 R2 ranked pool DEN/HOU/MIA | Shared allocation normalized to ranked slots MEM/OKC/OKC. Native two-pick comparisons preserve allocation counts; nested source exceptions are removed. |
| 2030 R2 ranked pool PHX/POR/WAS | Shared allocation normalized to ranked slots BOS/PHI/WAS. Native two-pick comparisons preserve allocation counts; nested source exceptions are removed. |
| 2029 R1 ranked pool UTA/CLE/MIN | Shared allocation normalized to ranked slots UTA/CHA/UTA. Native two-pick comparisons preserve allocation counts; nested source exceptions are removed. |
| 2027 R1: UTA/CLE/MIN | Rank the three picks MEM/UTA/PHX; the UTA top-five exclusion is simplified to the ranked allocation. |
| 2027 R1: OKC/DEN/LAC/TOR | OKC retains two picks; compare its weaker held pick with LAC, then LAC with TOR. DEN protection resolves first. |
| 2027 R2: PHI/GSW/HOU | WAS receives PHI own second as simplified second-best-of-three collateral; PHI retains the other two pool rights. Do not create an extra second. |
| 2027 R2: SAS/CHA/SAC | SAN first split is modeled as an unconditional SAC first; the conditional CHA/SAC seconds are assigned SAC/OKC without cross-round contingencies. |
| 2027 R2: LAL | LAL second assigned BKN; the alternative MEM recipient tied to LAL first conveyance is removed. |
| 2027 R2: NOP/POR | CHA receives the better second, POR the worse. Conditional 56-60 HOU transfer is removed. |
| 2028 R1: BKN/PHX/NYK/PHI/WAS/MIL/POR | BKN keeps its own pick, PHI top-8 protected incoming first, and sequential PHX/NYK swaps. WAS/PHX and WAS/MIL comparisons follow. Remove the PHI-third-best exception and substitute same-round PHI fallback for IRL first-to-second conversion. |
| 2028 R1: BOS/LAC/PHI | LAC top-16 protected first goes to BOS with same-round LAC fallback. Remove the nested BOS/PHI/LAC top-8 crossover; SAN/BOS swap remains top-1 protected. |
| 2028 R1: UTA/CLE/LAL/ATL | Sequential UTA/CLE, UTA/LAL and ATL/CLE comparisons; each later comparison follows the current held pick. |
| 2028 R2: DET/MIA/NYK/CHA/LAC | DET top-55 protected second to PHI; assign NYK second to UTA as simplified least-favorable collateral, preserve CHA/LAC comparison. Remove DAL first contingency and extra DET pool allocation. |
| 2028 R2: BOS | BOS second top-45 protected to NYK with same-round fallback; remove SAN first-overall contingency. |
| 2029 R1: MIN/UTA/CLE/CHA/PHX | UTA holds CLE and MIN top-5 protected firsts. PHX owns CHA first and can compare with MIN; CHA retains subsequent swap right. Remove the nested residual and conveyance-dependent branches. |
| 2029 R2: DEN | DEN second assigned CHA; remove the alternative OKC recipient based on earlier DEN first conveyance. |
| 2029 R2: MIN | MIN second assigned CHA; remove the alternative UTA recipient tied to first conveyance. |
| 2029 R2: ORL | ORL retains its second; remove MEM second-only compensation when the first swap is top-2 protected. |
| 2030 R1: SAS/DAL/MIN/CHA | SAN/DAL, SAN/MIN top-1 protected, then CHA/MIN comparisons; preserve MIN own first until a swap resolves. |
| 2030 R2: GSW | GSW retains its second; top-20 first protection uses same-round first collateral instead of conversion to second. |
| 2031 R2: HOU/ATL | OKC receives the better ATL/HOU second, HOU the worse; remove HOU 56-60 BOS carve-out. |
| 2031 R2: MIA/IND/MEM | WAS gets better MIA/IND; MEM compares with the remaining IND-held second; IND keeps remainder. |
| 2032 R2: MEM/PHI/UTA | MEM/PHI comparison followed by MEM/WAS comparison for UTA second; PHI and WAS retain residuals. |
| 2033 R2: DET/NOP | Unspecified DET second to LAC and NOP second/swap to MEM have no published year. Do not invent additional assets; leave these out until identifiable. |
| 2027 R1 DAL protection | top-2 protected; reserved 2031 R1 DAL fallback. Rollover and conversion branches replaced by this single native obligation. |
| 2027 R1 MIA protection | top-14 protected; reserved 2028 R1 MIA fallback. Rollover and conversion branches replaced by this single native obligation. |
| 2027 R1 DEN protection | top-5 protected; reserved 2028 R1 DEN fallback. Rollover and conversion branches replaced by this single native obligation. |
| 2029 R1 DEN protection | top-5 protected; reserved 2030 R1 DEN fallback. Rollover and conversion branches replaced by this single native obligation. |
| 2027 R1 LAL protection | top-4 protected; reserved 2032 R1 LAL fallback. Rollover and conversion branches replaced by this single native obligation. |
| 2028 R1 PHI protection | top-8 protected; reserved 2030 R1 PHI fallback. Rollover and conversion branches replaced by this single native obligation. |
| 2028 R1 LAC protection | top-16 protected; reserved 2031 R1 TOR fallback. Rollover and conversion branches replaced by this single native obligation. |
| 2029 R1 MIN protection | top-5 protected; reserved 2032 R1 MIN fallback. Rollover and conversion branches replaced by this single native obligation. |
| 2030 R1 GSW protection | top-20 protected; reserved 2031 R1 GSW fallback. Rollover and conversion branches replaced by this single native obligation. |
| 2027 R2 ATL protection | picks 31-55 protected; reserved 2033 R2 ATL fallback. Rollover and conversion branches replaced by this single native obligation. |
| 2028 R2 BOS protection | picks 31-45 protected; reserved 2032 R2 BOS fallback. Rollover and conversion branches replaced by this single native obligation. |
| 2028 R2 DEN protection | picks 31-33 protected; reserved 2033 R2 DEN fallback. Rollover and conversion branches replaced by this single native obligation. |
| 2028 R2 DET protection | picks 31-55 protected; reserved 2030 R2 DET fallback. Rollover and conversion branches replaced by this single native obligation. |
| 2030 R2 CHA protection | picks 31-55 protected; reserved 2031 R2 CHA fallback. Rollover and conversion branches replaced by this single native obligation. |
| 2030 R2 MEM protection | picks 31-50 protected; reserved 2033 R2 MEM fallback. Rollover and conversion branches replaced by this single native obligation. |
| 2032 R2 GSW protection | picks 31-50 protected; reserved 2033 R2 GSW fallback. Rollover and conversion branches replaced by this single native obligation. |
| 2027 R1 NOP protection | top-4 protected; reserved 2028 R1 NOP fallback. Rollover and conversion branches replaced by this single native obligation. |
| MIL/NOP 2027 | NOP receives better of MIL/NOP; ATL receives worse, protected top-4 with NOP same-round fallback. Resolve protection then comparison; a protected pick stays NOP. |

## Contract corrections and uncertainty

The current public salary table was refreshed. Old buyout/dead-salary rows are not treated as the newly signed contract for Klay Thompson, Kentavious Caldwell-Pope, Cam Whitmore, Devin Carter, Jordan Hawkins, Ryan Nembhard, or Johni Broome. Reported amounts are distinguished from estimates. Klay’s reported two-year total is allocated evenly for gameplay; unpublished minimum/two-way terms remain explicitly estimated in contract status and notes.

## Audit evidence

- 700 disposable full-league synthetic draft orders settled with valid owners and no missing or duplicate underlying assets.
- All six Brooklyn 2029 Houston/Dallas/Phoenix relative orderings give Brooklyn the least favorable first.
- A disposable new Brooklyn save retained all 85 starting obligations and the refreshed star destinations.
- Every official roster entry matched exactly one canonical player/team membership.
- Existing-save baseline player, contract, and pick arrays match the archived release.
- No returning trait value changed.

## Sources

- [RealGM — all 30 team pick ledgers](https://basketball.realgm.com/nba/draft/future_drafts/team)
- [RealGM — Brooklyn detailed rights](https://basketball.realgm.com/nba/teams/Brooklyn-Nets/38/draft-picks)
- [NBA official team rosters](https://www.nba.com/teams) — individual page URLs are stored with each team in the dated roster snapshot.
- [NBA official offseason transaction tracker](https://www.nba.com/news/2026-offseason-trade-tracker)
- [NBA — August Clippers transaction](https://www.nba.com/clippers/news/clippers-acquire-strus-from-cleveland-in-five-team-trade) — “via LAC” refers to an acquired shared right, not the LAC own second owed Utah.
- [NBA — Clippers penalty](https://cdn-uat.nba.com/news/nba-investigation-findings-la-clippers)
- [NBA — Philadelphia roster](https://www.nba.com/team/1610612755/sixers/roster)
- [NBA — Minnesota roster](https://www.nba.com/team/1610612750/timberwolves)
- [Basketball Reference — current salary ledger](https://www.basketball-reference.com/contracts/players.html)
- [NBA — Klay Thompson new deal](https://www.nba.com/news/klay-thompson-heat-2026-free-agency)
- [NBA — Cam Whitmore two-way](https://gleague.nba.com/news/the-denver-nuggets-sign-cam-whitmore-to-a-two-way-contract)
- [NBA — Ryan Nembhard two-way](https://gleague.nba.com/news/nuggets-sign-ryan-nembhard-to-two-way-contract)
- [NBA — Jordan Hawkins two-way](https://www.nba.com/news/chicago-bulls-sign-jordan-hawkins-to-two-way-contract)
