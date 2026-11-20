"""Writes the trade_personality section of data/overrides/front_office_overrides.json from the
reputation research (data/research/front_office_reputations_2026_11.json). Only findings the research marked widely held
(two or more outlets, or a ranking plus corroboration) set a trait; everything else is drawn from the measured spread
by the game (front_office.py)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
research = json.loads((ROOT / "data/research/front_office_reputations_2026_11.json").read_text())


def t(value, why, *sources):
    return {"value": value, "why": why, "sources": list(sources)}


def b(key, why, *sources):
    return {"key": key, "why": why, "sources": list(sources)}


TEAMS = {
    "ATL": {"savvy": t(55, "Mid-table in the CBS 2026 rankings (13th); steady roster work per ESPN.", "src_cbs_p1", "src_espn_fpr")},
    "BKN": {"patience": t(75, "Clean books and a pick surplus; sold veterans at peak value rather than forcing moves.", "src_cbs_p2", "src_espn_fpr"),
            "biases": [b("values_picks", "Near the top of the league in draft assets.", "src_cbs_p2", "src_espn_fpr")]},
    "BOS": {"savvy": t(80, "Third in CBS 2026 (second in 2025) and second in The Athletic's executive poll, dented by the Jaylen Brown trade.", "src_cbs_p1", "src_cbs_2025", "src_athletic_poll"),
            "biases": [b("tax_averse", "Built its moves around staying under the second apron.", "src_cbs_2025", "src_espn_fpr")]},
    "CHA": {"savvy": t(68, "Ninth in CBS 2026; ESPN's management rank rose from 22nd to 6th.", "src_cbs_p1", "src_espn_fpr"),
            "urgency": t(64, "Moved LaMelo Ball to build a real contender quickly.", "src_cbs_p1", "src_espn_fpr", "src_trades"),
            "biases": [b("values_picks", "Built a large pick collection from the Ball and Bridges trades.", "src_cbs_p1", "src_espn_fpr")]},
    "CLE": {"savvy": t(74, "Twelfth in CBS 2026 (fifth in 2025), sixth in the executive poll; creative roster turnover.", "src_cbs_p1", "src_cbs_2025", "src_athletic_poll"),
            "urgency": t(76, "Bold win-now trades (Mitchell, Harden) and few picks left.", "src_cbs_2025", "src_espn_fpr", "src_cbs_p1"),
            "biases": [b("spends_tax", "Ownership pays deep into the second apron.", "src_cbs_2025", "src_cbs_p1", "src_espn_fpr")]},
    "DEN": {"biases": [b("overrates_own", "Paid its own players heavily (Braun) and is the only team in the second apron.", "src_cbs_p2", "src_espn_fpr")]},
    "DET": {"patience": t(78, "No major moves and no first-round pick traded; owns all its firsts for seven years.", "src_cbs_p1", "src_espn_fpr")},
    "GSW": {"loyalty": t(85, "Core-first approach, the league's oldest roster; kept Kuminga too long.", "src_cbs_p2", "src_espn_fpr", "src_espn_kuminga"),
            "savvy": t(58, "Eighteenth in CBS 2026, tenth in the executive poll.", "src_cbs_p2", "src_athletic_poll")},
    "HOU": {"savvy": t(74, "Third in the executive poll and eighth in CBS 2026; strong on contracts, 13th in ESPN management.", "src_cbs_p1", "src_athletic_poll", "src_roundtable_stone")},
    "IND": {"savvy": t(77, "Sixth in CBS 2026 (seventh in 2025), fifth in the executive poll; talent evaluation praised.", "src_cbs_p1", "src_cbs_2025", "src_athletic_poll"),
            "loyalty": t(74, "Re-signs and extends its own players early.", "src_cbs_p1", "src_cbs_2025"),
            "biases": [b("tax_averse", "Cautious about the luxury tax.", "src_cbs_p1", "src_espn_fpr")]},
    "LAL": {"savvy": t(35, "24th in CBS 2026 and low in 2025; heavy criticism of the front office.", "src_cbs_p2", "src_cbs_2025", "src_cbs_pelinka"),
            "biases": [b("underrates_picks", "Paid two unprotected firsts and two swaps for Walker Kessler; 29th in draft assets.", "src_cbs_p2", "src_espn_fpr", "src_trades")]},
    "MEM": {"patience": t(30, "Moved Bane, Jaren Jackson Jr. and Morant rather than wait for a turnaround.", "src_cbs_p1", "src_espn_fpr")},
    "MIA": {"urgency": t(80, "Star-hunting approach; never tanks; the Giannis deal cost most of its picks.", "src_cbs_p1", "src_cbs_riley", "src_espn_fpr"),
            "savvy": t(75, "Fourth in the executive poll; ESPN calls it the most consistent management over seven years.", "src_athletic_poll", "src_cbs_p1", "src_espn_fpr"),
            "patience": t(35, "Resists rebuilding; CBS calls that a flaw.", "src_cbs_p1", "src_cbs_riley")},
    "MIN": {"urgency": t(80, "Aggressive Gobert, Towns and LaMelo Ball trades; last in draft assets.", "src_cbs_p1", "src_espn_fpr"),
            "savvy": t(50, "Tenth in CBS 2026 and seventh in the executive poll, but the Dillingham and Ball trades drew poor grades.", "src_cbs_p1", "src_athletic_poll", "src_trades")},
    "NOP": {"savvy": t(25, "29th in CBS 2026; ESPN management tied for worst.", "src_cbs_p2", "src_espn_fpr"),
            "biases": [b("underrates_picks", "Traded an unprotected first to move up for Derik Queen.", "src_cbs_p2", "src_hr_dumars")]},
    "NYK": {"savvy": t(78, "Second in CBS 2026, eighth in the executive poll, fourth in ESPN management.", "src_cbs_p1", "src_athletic_poll", "src_espn_fpr"),
            "urgency": t(80, "Gave five firsts for Mikal Bridges; fearless win-now moves.", "src_cbs_p1", "src_cbs_bridges", "src_defector"),
            "connections": [
                {"player": "Jalen Brunson", "why": "Villanova ties run through the front office's biggest moves.", "sources": ["src_cbs_2025", "src_cbs_bridges", "src_defector"]},
                {"player": "Josh Hart", "why": "Villanova ties run through the front office's biggest moves.", "sources": ["src_cbs_2025", "src_cbs_bridges", "src_defector"]},
                {"player": "Mikal Bridges", "why": "Villanova ties: paid five firsts to reunite him with his college teammates.", "sources": ["src_cbs_bridges", "src_defector"]},
                {"player": "Donte DiVincenzo", "why": "Villanova ties run through the front office's biggest moves.", "sources": ["src_cbs_2025", "src_defector"]}]},
    "OKC": {"savvy": t(95, "First in every CBS edition; 31 of 36 executives voted it the league's best.", "src_cbs_p1", "src_cbs_2025", "src_athletic_poll"),
            "biases": [b("values_picks", "Stockpiles picks and uses them every way (trades, swaps, drafting).", "src_cbs_p1", "src_espn_fpr", "src_trades")]},
    "ORL": {"urgency": t(70, "The Desmond Bane trade cost several picks.", "src_cbs_p2", "src_espn_fpr")},
    "PHX": {"urgency": t(88, "Repeated pick-for-win-now trades; its owner says picks exist to get stars.", "src_si_suns_picks", "src_si_ishbia", "src_cbs_p2", "src_espn_fpr"),
            "savvy": t(25, "27th in CBS 2026; graded D+ on the Bridges deal.", "src_cbs_p2", "src_trades"),
            "biases": [b("underrates_picks", "Its tradable picks are nearly gone after star trades.", "src_espn_fpr", "src_cbs_p2", "src_si_suns_picks"),
                       b("spends_tax", "About $270M of luxury tax in four seasons.", "src_espn_fpr", "src_cbs_p2")]},
    "POR": {"biases": [b("tax_averse", "New ownership is cutting costs.", "src_cbs_p2", "src_espn_fpr")]},
    "SAC": {"savvy": t(20, "30th in CBS 2026; the Clifford trade made it a front-office loser in analysts' grades.", "src_cbs_p2", "src_trades"),
            "biases": [b("overpays_veterans", "Big deals for Sabonis and LaVine and a costly draft trade-up.", "src_cbs_p2", "src_trades")]},
    "SAS": {"savvy": t(86, "Fourth in CBS 2026 (third in 2025), ninth in the executive poll; sold Dejounte Murray at peak value.", "src_cbs_p1", "src_cbs_2025", "src_athletic_poll"),
            "patience": t(85, "Patient long-term core building; patient on Kevin Durant.", "src_cbs_p1", "src_cbs_2025"),
            "biases": [b("values_picks", "Gathered first-round swaps for extra lottery chances.", "src_cbs_p1", "src_cbs_2025")]},
    "UTA": {"patience": t(85, "Never changes course under pressure; held firm on its price for Walker Kessler.", "src_cbs_p1", "src_espn_fpr"),
            "savvy": t(80, "Fifth in CBS 2026; its Lakers sign-and-trade return was graded A+.", "src_cbs_p1", "src_trades"),
            "biases": [b("values_picks", "Holds one of the league's biggest pick collections.", "src_cbs_p1", "src_espn_fpr")]},
    "WAS": {"biases": [b("overpays_veterans", "A max deal for Trae Young and a heavy spend on Young and Davis during a rebuild.", "src_cbs_p2", "src_espn_fpr")]},
}

used = sorted({s for team in TEAMS.values() for v in team.values()
               for s in ([x for item in v for x in item["sources"]] if isinstance(v, list) else v["sources"])})
sources = [s for s in research["sources"] if s["id"] in used]
section = {
    "notes": ("Front-office trade personality (TRADE-MARKET). Starting traits for real front offices from widely held "
              "public reputations only (two or more outlets, or a ranking with corroboration), each with its sources. "
              "Traits are 0-100 with 50 the league middle. Any trait not listed here (and every team whose regime is "
              "too new for a reputation) is drawn from the measured spread of the listed values, seeded by the save, "
              "in src/nba_gm_data/front_office.py. Research: data/research/front_office_reputations_2026_11.json, "
              "retrieved 2026-11-20."),
    "regimes_too_new": {abbrev: research["teams"][abbrev]["decision_maker"]
                        for abbrev in sorted(research["teams"]) if research["teams"][abbrev].get("regime_new")},
    "sources": sources,
    "teams": TEAMS,
}
path = ROOT / "data/overrides/front_office_overrides.json"
data = json.loads(path.read_text())
data["trade_personality"] = section
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print(len(TEAMS), "teams,", len(sources), "sources")
