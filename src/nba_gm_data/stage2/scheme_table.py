"""Each 2025-26 head coach's ball-screen scheme on top of his personnel (S2-SCHEMES), as log-odds tilts on the
Stage 2 coverage call: aggression (drop less, trap more) from Basketball Index coverage aggression, switching
from guards' assigned time on centers (NBA matchups). Leftover after personnel (spread-matched scale) x
reliability (.53 aggression, .26 switching), fitted on the engine's own replayed 2025-26 screens.
Written by scripts/research/s2_scheme_fit.py --write (2026-11-24); stage2.schemes reads it."""

COACHES = {
    'billy donovan': {"coach": 'Billy Donovan', "team": 'CHI', "aggression": -0.058, "switching": 0.008},
    'brian keefe': {"coach": 'Brian Keefe', "team": 'WAS', "aggression": -0.075, "switching": 0.047},
    'charles lee': {"coach": 'Charles Lee', "team": 'CHA', "aggression": -0.064, "switching": -0.019},
    'chauncey billups': {"coach": 'Chauncey Billups', "team": 'POR', "aggression": -0.09, "switching": 0.006},
    'chris finch': {"coach": 'Chris Finch', "team": 'MIN', "aggression": -0.042, "switching": -0.044},
    'darko rajakovic': {"coach": 'Darko Rajakovic', "team": 'TOR', "aggression": -0.077, "switching": -0.095},
    'david adelman': {"coach": 'David Adelman', "team": 'DEN', "aggression": -0.089, "switching": 0.015},
    'doc rivers': {"coach": 'Doc Rivers', "team": 'MIL', "aggression": 0.177, "switching": 0.047},
    'doug christie': {"coach": 'Doug Christie', "team": 'SAC', "aggression": -0.049, "switching": 0.031},
    'erik spoelstra': {"coach": 'Erik Spoelstra', "team": 'MIA', "aggression": -0.212, "switching": 0.012},
    'ime udoka': {"coach": 'Ime Udoka', "team": 'HOU', "aggression": 0.094, "switching": -0.015},
    'j.b. bickerstaff': {"coach": 'J.B. Bickerstaff', "team": 'DET', "aggression": 0.071, "switching": -0.073},
    'jamahl mosley': {"coach": 'Jamahl Mosley', "team": 'ORL', "aggression": -0.045, "switching": -0.053},
    'james borrego': {"coach": 'James Borrego', "team": 'NOP', "aggression": 0.049, "switching": -0.028},
    'jason kidd': {"coach": 'Jason Kidd', "team": 'DAL', "aggression": -0.086, "switching": -0.06},
    'jj redick': {"coach": 'JJ Redick', "team": 'LAL', "aggression": -0.042, "switching": 0.078},
    'joe mazzulla': {"coach": 'Joe Mazzulla', "team": 'BOS', "aggression": -0.002, "switching": 0.051},
    'jordan ott': {"coach": 'Jordan Ott', "team": 'PHX', "aggression": 0.009, "switching": 0.079},
    'jordi fernandez': {"coach": 'Jordi Fernandez', "team": 'BKN', "aggression": 0.239, "switching": -0.061},
    'kenny atkinson': {"coach": 'Kenny Atkinson', "team": 'CLE', "aggression": 0.118, "switching": -0.086},
    'mark daigneault': {"coach": 'Mark Daigneault', "team": 'OKC', "aggression": 0.137, "switching": 0.026},
    'mike brown': {"coach": 'Mike Brown', "team": 'NYK', "aggression": -0.014, "switching": -0.051},
    'mitch johnson': {"coach": 'Mitch Johnson', "team": 'SAS', "aggression": -0.051, "switching": 0.106},
    'nick nurse': {"coach": 'Nick Nurse', "team": 'PHI', "aggression": 0.03, "switching": -0.019},
    'quin snyder': {"coach": 'Quin Snyder', "team": 'ATL', "aggression": 0.006, "switching": -0.033},
    'rick carlisle': {"coach": 'Rick Carlisle', "team": 'IND', "aggression": 0.175, "switching": -0.062},
    'steve kerr': {"coach": 'Steve Kerr', "team": 'GSW', "aggression": -0.026, "switching": 0.021},
    'tiago splitter': {"coach": 'Tiago Splitter', "team": 'POR', "aggression": -0.09, "switching": 0.006},
    'tuomas iisalo': {"coach": 'Tuomas Iisalo', "team": 'MEM', "aggression": -0.145, "switching": 0.045},
    'tyronn lue': {"coach": 'Tyronn Lue', "team": 'LAC', "aggression": 0.202, "switching": 0.091},
    'will hardy': {"coach": 'Will Hardy', "team": 'UTA', "aggression": -0.094, "switching": 0.126},
    'willie green': {"coach": 'Willie Green', "team": 'NOP', "aggression": 0.049, "switching": -0.028},
}
