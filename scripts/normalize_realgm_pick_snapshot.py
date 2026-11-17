#!/usr/bin/env python3
"""Compile the reviewed 30-team pick snapshot into native game assets/terms.

Every originating team/year/round remains a single asset. Shared favorable-pick
allocations become ordered comparisons using the existing pick_swap term. IRL
conversion/rollover clauses are documented, never passed to the prose parser.
"""
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nba_gm_data.utils import stable_id
from update_2026_offseason_snapshot import TEAM_NAME_TO_ABBREV, TEAMS

SOURCE = "src_realgm_future_pick_pages"
URL = "https://basketball.realgm.com/nba/draft/future_drafts/team"
ALIASES = {"BRK": "BKN", "GOS": "GSW", "PHL": "PHI", "SAN": "SAS", "UTH": "UTA"}

def read_source():
    lines = {}
    for path in sorted((ROOT / "data/research").glob("realgm_future_picks_2026_10_13_source*.txt")):
        for line in path.read_text().splitlines():
            match = re.match(r"L(\d+): (.*)", line)
            if match:
                lines[int(match[1])] = match[2]
    names = {**TEAM_NAME_TO_ABBREV, "Philadelphia Sixers": "PHI"}
    records = []
    current = None
    for _, line in sorted(lines.items()):
        heading = re.match(r"## (.+) Future NBA Draft Picks", line)
        if heading:
            current = names[heading[1]]
            continue
        year = re.match(r"^(20\d{2})\s+\|", line)
        if year and current:
            records.append({"team": current, "season": int(year[1]), "text": line})
        elif current and records and line and not line.startswith(("Year", "---", "##", "[Input", "All content", "")):
            records[-1]["text"] += " " + line
    output = {}
    for record in records:
        parts = record["text"].split(" | ")
        assert len(parts) == 3, record
        for round_no, text in enumerate(parts[1:], 1):
            for a, b in ALIASES.items():
                text = re.sub(rf"\b{a}\b", b, text)
            output[(record["team"], record["season"], round_no)] = text.strip()
    assert len(output) == 420, len(output)
    return output

def main():
    sources = read_source()
    ledger = {}
    terms = []
    approximations = []
    def key(team, year, round_no=1): return (team, year, round_no)
    def pid(team, year, round_no=1): return stable_id("pick", team, str(year), round_no)
    def tid(team): return stable_id("team", team)
    for identity, text in sources.items():
        team, year, round_no = identity
        owner = team
        plain_to = re.match(r"To ([A-Z]{3})\b", text)
        protected_to = re.match(r"1-(\d+) Own;\s*\d+-30 to ([A-Z]{3})", text)
        if plain_to and "if not already settled" not in text:
            owner = plain_to[1]
        if protected_to:
            owner = protected_to[2]
        ledger[identity] = {"original_team_abbrev": team, "owner_team_abbrev": owner,
            "season": str(year), "round": round_no, "protections": None,
            "status": "verified_realgm_underlying_pick", "confidence": .9,
            "source_ids": [SOURCE], "source_summary": text, "notes": "Reviewed originating-team ledger. " + text}

    def own(team, year, owner, round_no=1):
        ledger[key(team, year, round_no)]["owner_team_abbrev"] = owner

    def note(label, policy, identities):
        approximations.append({"case": label, "gameplay_policy": policy,
            "picks": [pid(*identity) for identity in identities],
            "source_summaries": [sources[identity] for identity in identities], "source_url": URL})
        for identity in identities:
            ledger[identity]["notes"] += " Gameplay normalization: " + policy
            ledger[identity]["confidence"] = min(ledger[identity]["confidence"], .75)

    def swap(year, a, b, holder, round_no=1, *, benefit="better", pool=None, counterparty=None, top_n=0):
        term = {"id": stable_id("pick_obligation", "realgm", year, round_no, a, b, holder, len(terms)),
            "type": "pick_swap", "season": str(year), "round": round_no, "team_a_pick_id": pid(a, year, round_no),
            "team_b_pick_id": pid(b, year, round_no), "original_rights_holder_team_id": tid(holder),
            "current_rights_holder_team_id": tid(holder), "receiver_team_id": tid(holder),
            "benefit": benefit, "status": "active", "source": SOURCE}
        if pool:
            term["comparison_pool_pick_ids"] = [pid(t, year, round_no) for t in pool]
            term["comparison_holder_team_id"] = tid(holder)
            term["comparison_counterparty_team_id"] = tid(counterparty)
        if top_n:
            term["subject_protected_top_n"] = {pid(b, year, round_no): top_n}
        terms.append(term)

    def allocate(year, originals, owners, round_no=1):
        """Sort shared ownership into ranked slots through native comparisons.

        Current owners identify each comparison's subjects after earlier swaps;
        underlying pick IDs never change and the number owned by each club is
        conserved. Repeated compare passes handle clubs receiving several picks.
        """
        assert len(originals) == len(owners)
        if len(originals) > 2:
            note(f"{year} R{round_no} ranked pool {'/'.join(originals)}",
                "Shared allocation normalized to ranked slots " + "/".join(owners) +
                ". Native two-pick comparisons preserve allocation counts; nested source exceptions are removed.",
                [key(t,year,round_no) for t in originals])
        for origin, owner in zip(originals, owners): own(origin, year, owner, round_no)
        rank = list(dict.fromkeys(owners))
        passes = [range(len(rank) - 1 - step) for step in range(len(rank) - 1)]
        if len(rank) == 2:
            passes = [range(1)] * min(Counter(owners).values())
        for comparisons in passes:
            for i in comparisons:
                holder, other = rank[i:i + 2]
                a = originals[owners.index(holder)]
                b = originals[owners.index(other)]
                swap(year, a, b, holder, round_no, pool=originals, counterparty=other)
                terms[-1]["allocation_comparison"] = True

    # Plain transfers not discoverable from the first clause of an originating
    # row (the remainder describes incoming assets rather than the own pick).
    for origin, year, owner in [
        ("BOS",2029,"POR"),("CLE",2027,"MEM"),("CLE",2029,"UTA"),
        ("DEN",2027,"OKC"),("DEN",2029,"OKC"),("LAC",2028,"BOS"),
        ("MIL",2027,"NOP"),("MIL",2029,"POR"),("MIN",2027,"PHX"),
        ("MIN",2029,"UTA"),("PHI",2028,"BKN"),("PHX",2029,"HOU"),
        ("DAL",2029,"BKN"),("SAS",2027,"SAC")]: own(origin,year,owner)
    # Rollover picks are collateral, not additional unconditional conveyances.
    for origin, year in [("MIA",2028),("DEN",2028),("DEN",2030)]: own(origin,year,origin)
    for origin, year, owner in [
        ("ATL",2027,"DAL"),("BKN",2027,"MIL"),("DAL",2027,"WAS"),
        ("BOS",2027,"UTA"),("ORL",2027,"PHX"),
        ("GSW",2027,"PHI"),("PHX",2027,"WAS"),
        ("HOU",2027,"PHI"),("IND",2027,"NOP"),("MIA",2027,"NYK"),("OKC",2027,"MIA"),
        ("NOP",2027,"POR"),("POR",2027,"CHA"),("PHI",2027,"WAS"),
        ("CHI",2028,"CHI"),("IND",2028,"IND"),("PHX",2028,"NYK"),
        ("CHA",2028,"CHA"),("LAC",2028,"DET"),("MIA",2028,"DET"),
        ("BOS",2028,"NYK"),("DEN",2028,"WAS"),("DET",2028,"DET"),
        ("GSW",2028,"BOS"),("MIL",2028,"PHI"),("OKC",2028,"PHI"),
        ("PHI",2028,"PHI"),("NYK",2028,"UTA"),
        ("ATL",2029,"CHA"),("MIA",2029,"OKC"),("DEN",2029,"CHA"),
        ("DET",2029,"DET"),("MIL",2029,"DET"),("NYK",2029,"CHI"),
        ("IND",2029,"IND"),("WAS",2029,"POR"),("MIN",2029,"CHA"),("ORL",2029,"ORL"),
        ("DEN",2030,"MEM"),("HOU",2030,"OKC"),("MIA",2030,"OKC"),
        ("LAC",2030,"CHA"),("UTA",2030,"LAC"),("MEM",2030,"MIN"),
        ("GSW",2030,"GSW"),("PHX",2030,"BOS"),("POR",2030,"WAS"),("WAS",2030,"PHI"),
        ("CHA",2030,"BOS"),("ATL",2031,"OKC"),("HOU",2031,"HOU"),
        ("BOS",2031,"BOS"),("CLE",2031,"UTA"),("MIN",2031,"CHI"),("GSW",2031,"DET"),
        ("IND",2031,"IND"),("MIA",2031,"WAS"),("MEM",2031,"MEM"),
        ("NOP",2031,"OKC"),("ORL",2031,"ORL"),
        ("PHX",2032,"PHX"),("HOU",2032,"CHI"),
        ("MEM",2032,"MEM"),("PHI",2032,"PHI"),("UTA",2032,"WAS"),
        ("GSW",2032,"MEM")]: own(origin,year,owner,2)

    # "Via LAC" in August's trade is PHI's acquired median-pool right,
    # not the Clippers' underlying own second (already owed to UTA).
    own("LAC",2027,"UTA",2)
    note("2027 second via LAC", "LAC own second remains owed to UTA. WAS receives the PHI median-pool entitlement acquired via LAC; normalized to PHI own second as documented below.", [key("LAC",2027,2),key("PHI",2027,2)])

    # Favorability pools. These all reduce to the engine's same-year,
    # same-round comparisons, retaining each recipient's allocation count.
    for year, origins, owners, round_no in [
        (2027,["CLE","UTA","MIN"],["MEM","UTA","PHX"],1),
        (2029,["HOU","PHX","DAL"],["HOU","HOU","BKN"],1),
        (2029,["BOS","MIL","POR"],["POR","WAS","POR"],1),
        (2027,["BOS","ORL"],["UTA","PHX"],2),
        (2027,["BKN","DAL"],["WAS","MIL"],2),
        (2027,["GSW","PHX"],["PHI","WAS"],2),
        (2027,["HOU","IND","MIA","OKC"],["PHI","NOP","NYK","MIA"],2),
        (2027,["NOP","POR"],["CHA","POR"],2),
        (2028,["GSW","MIL","OKC"],["BOS","PHI","PHI"],2),
        (2028,["CHI","IND","PHX"],["CHI","IND","NYK"],2),
        (2028,["CHA","LAC"],["CHA","DET"],2),
        (2028,["LAL","WAS"],["ORL","WAS"],2),
        (2029,["ATL","MIA"],["CHA","OKC"],2),
        (2029,["DET","MIL","NYK"],["DET","DET","CHI"],2),
        (2029,["IND","WAS"],["IND","POR"],2),
        (2030,["DEN","HOU","MIA"],["MEM","OKC","OKC"],2),
        (2030,["LAC","UTA"],["CHA","LAC"],2),
        (2030,["PHX","POR","WAS"],["BOS","PHI","WAS"],2),
        (2031,["ATL","HOU"],["OKC","HOU"],2),
        (2031,["BOS","CLE"],["UTA","BOS"],2),
        (2031,["MIN","GSW"],["CHI","DET"],2),
        (2031,["NOP","ORL"],["ORL","OKC"],2),
        (2032,["PHX","HOU"],["CHI","PHX"],2),
    ]:
        # Most-and-least recipient POR is a noncontiguous allocation: use
        # a dedicated median comparison model below, rather than sorting POR
        # into a fictitious contiguous quota.
        if origins == ["BOS","MIL","POR"]:
            own("BOS",year,"POR");own("MIL",year,"WAS");own("POR",year,"POR")
            note("2029 POR/BOS/MIL median right", "WAS receives the less favorable of BOS/MIL; POR retains its own and the better of BOS/MIL. The IRL median-of-three clause is simplified to a two-pick comparison.", [key(t,year) for t in origins])
            swap(year,"MIL","BOS","WAS",benefit="worse")
        else: allocate(year, origins, owners, round_no)

    # Ordinary two-team swaps; transferred underlying picks stay with their
    # actual owner until the swap is exercised.
    for year,a,b,holder,round_no,protected in [
        (2027,"HOU","BKN","HOU",1,0),
        (2028,"OKC","DAL","OKC",1,0),
        (2028,"CHA","MIN","CHA",1,0),
        (2028,"SAS","BOS","SAS",1,1),
        (2029,"PHI","LAC","PHI",1,3),
        (2029,"MEM","ORL","MEM",1,2),
        (2030,"SAS","DAL","SAS",1,0),
        (2030,"UTA","LAL","UTA",1,0),
        (2031,"SAS","SAC","SAS",1,0),
        (2030,"CHI","IND","CHI",2,0),
        (2030,"ORL","NOP","ORL",2,0),
    ]: swap(year,a,b,holder,round_no,top_n=protected)

    # Nested/repeated third-party clauses are deliberately reduced to native
    # pair comparisons. The rejected IRL clauses remain in the audit below.
    for year, origins, owners in [
        (2027,["OKC","DEN","LAC","TOR"],["OKC","OKC","LAC","TOR"]),
        (2028,["BKN","PHX","NYK"],["BKN","PHX","NYK"]),
        (2028,["UTA","CLE","LAL","ATL"],["UTA","CLE","LAL","ATL"]),
        (2029,["UTA","CLE","CHA"],["UTA","CHA","PHX"]),
        (2030,["SAS","MIN","CHA"],["SAS","MIN","CHA"]),
        (2030,["WAS","PHX","MEM"],["WAS","PHX","MEM"]),
        (2030,["POR","MIL","MIA"],["POR","MIL","MIA"]),
    ]:
        for origin,owner in zip(origins,owners): own(origin,year,owner)
    swap(2027,"OKC","LAC","OKC")
    swap(2027,"LAC","TOR","LAC",pool=["OKC","DEN","LAC","TOR"],counterparty="TOR")
    swap(2028,"BKN","PHX","BKN")
    swap(2028,"BKN","NYK","BKN",pool=["BKN","PHX","NYK"],counterparty="NYK")
    swap(2028,"WAS","PHX","WAS",pool=["BKN","PHX","NYK","WAS"],counterparty="PHX")
    swap(2028,"POR","MIL","POR")
    swap(2028,"WAS","MIL","WAS",pool=["WAS","PHX","MIL","POR"],counterparty="MIL")
    swap(2028,"UTA","CLE","UTA")
    swap(2028,"UTA","LAL","UTA",pool=["UTA","CLE","LAL"],counterparty="LAL")
    swap(2028,"ATL","CLE","ATL",pool=["UTA","CLE","LAL","ATL"],counterparty="CLE")
    allocate(2029,["UTA","CLE","MIN"],["UTA","CHA","UTA"])
    swap(2029,"CLE","CHA","CHA",pool=["UTA","CLE","MIN","CHA"],counterparty="PHX")
    swap(2030,"SAS","MIN","SAS",pool=["SAS","DAL","MIN"],counterparty="MIN",top_n=1)
    swap(2030,"CHA","MIN","CHA",pool=["SAS","DAL","MIN","CHA"],counterparty="MIN")
    swap(2030,"WAS","PHX","WAS")
    swap(2030,"MEM","PHX","MEM",pool=["WAS","PHX","MEM"],counterparty="PHX")
    swap(2030,"POR","MIL","POR")
    swap(2030,"MIL","MIA","MIL",pool=["POR","MIL","MIA"],counterparty="MIA")
    swap(2031,"MIA","IND","WAS",2)
    swap(2031,"MEM","IND","MEM",2,pool=["MIA","IND","MEM"],counterparty="IND")
    swap(2032,"MEM","PHI","MEM",2)
    swap(2032,"MEM","UTA","MEM",2,pool=["MEM","PHI","UTA"],counterparty="WAS")
    for year, teams, round_no, policy in [
        (2027,["UTA","CLE","MIN"],1,"Rank the three picks MEM/UTA/PHX; the UTA top-five exclusion is simplified to the ranked allocation."),
        (2027,["OKC","DEN","LAC","TOR"],1,"OKC retains two picks; compare its weaker held pick with LAC, then LAC with TOR. DEN protection resolves first."),
        (2027,["PHI","GSW","HOU"],2,"WAS receives PHI own second as simplified second-best-of-three collateral; PHI retains the other two pool rights. Do not create an extra second."),
        (2027,["SAS","CHA","SAC"],2,"SAN first split is modeled as an unconditional SAC first; the conditional CHA/SAC seconds are assigned SAC/OKC without cross-round contingencies."),
        (2027,["LAL"],2,"LAL second assigned BKN; the alternative MEM recipient tied to LAL first conveyance is removed."),
        (2027,["NOP","POR"],2,"CHA receives the better second, POR the worse. Conditional 56-60 HOU transfer is removed."),
        (2028,["BKN","PHX","NYK","PHI","WAS","MIL","POR"],1,"BKN keeps its own pick, PHI top-8 protected incoming first, and sequential PHX/NYK swaps. WAS/PHX and WAS/MIL comparisons follow. Remove the PHI-third-best exception and substitute same-round PHI fallback for IRL first-to-second conversion."),
        (2028,["BOS","LAC","PHI"],1,"LAC top-16 protected first goes to BOS with same-round LAC fallback. Remove the nested BOS/PHI/LAC top-8 crossover; SAN/BOS swap remains top-1 protected."),
        (2028,["UTA","CLE","LAL","ATL"],1,"Sequential UTA/CLE, UTA/LAL and ATL/CLE comparisons; each later comparison follows the current held pick."),
        (2028,["DET","MIA","NYK","CHA","LAC"],2,"DET top-55 protected second to PHI; assign NYK second to UTA as simplified least-favorable collateral, preserve CHA/LAC comparison. Remove DAL first contingency and extra DET pool allocation."),
        (2028,["BOS"],2,"BOS second top-45 protected to NYK with same-round fallback; remove SAN first-overall contingency."),
        (2029,["MIN","UTA","CLE","CHA","PHX"],1,"UTA holds CLE and MIN top-5 protected firsts. PHX owns CHA first and can compare with MIN; CHA retains subsequent swap right. Remove the nested residual and conveyance-dependent branches."),
        (2029,["DEN"],2,"DEN second assigned CHA; remove the alternative OKC recipient based on earlier DEN first conveyance."),
        (2029,["MIN"],2,"MIN second assigned CHA; remove the alternative UTA recipient tied to first conveyance."),
        (2029,["ORL"],2,"ORL retains its second; remove MEM second-only compensation when the first swap is top-2 protected."),
        (2030,["SAS","DAL","MIN","CHA"],1,"SAN/DAL, SAN/MIN top-1 protected, then CHA/MIN comparisons; preserve MIN own first until a swap resolves."),
        (2030,["GSW"],2,"GSW retains its second; top-20 first protection uses same-round first collateral instead of conversion to second."),
        (2031,["HOU","ATL"],2,"OKC receives the better ATL/HOU second, HOU the worse; remove HOU 56-60 BOS carve-out."),
        (2031,["MIA","IND","MEM"],2,"WAS gets better MIA/IND; MEM compares with the remaining IND-held second; IND keeps remainder."),
        (2032,["MEM","PHI","UTA"],2,"MEM/PHI comparison followed by MEM/WAS comparison for UTA second; PHI and WAS retain residuals."),
        (2033,["DET","NOP"],2,"Unspecified DET second to LAC and NOP second/swap to MEM have no published year. Do not invent additional assets; leave these out until identifiable.")
    ]: note(f"{year} R{round_no}: {'/'.join(teams)}",policy,[key(t,year,round_no) for t in teams])

    # Same-round fallback collateral is an established gameplay requirement.
    # Reserve distinct underlying picks, never the primary or another backup.
    forfeited = {key("IND",2029), *(key("LAC",y) for y in range(2030,2034))}
    swap_subjects = {pick_id for t in terms for pick_id in
        [t.get("team_a_pick_id"), t.get("team_b_pick_id"), *(t.get("comparison_pool_pick_ids") or [])] if pick_id}
    used = set()
    def protect(origin,year,owner,through,round_no=1,low=1,fallback_year=None):
        own(origin,year,owner,round_no)
        candidates = [i for i,r in ledger.items() if i[2] == round_no and i[1] >= year and i != key(origin,year,round_no)
            and r["owner_team_abbrev"] == origin and i not in used and i not in forfeited
            and pid(*i) not in swap_subjects]
        candidates.sort(key=lambda i:(i[1] != fallback_year if fallback_year else False,i[0] != origin,i[1],i[0]))
        assert candidates, (origin,year,round_no)
        fallback = candidates[0];used.add(fallback)
        label = f"top-{through} protected" if low == 1 else f"picks {low}-{through} protected"
        ledger[key(origin,year,round_no)]["protections"] = label
        terms.append({"id":stable_id("pick_obligation","realgm_protected",pid(origin,year,round_no)),
            "type":"protected_pick","season":str(year),"primary_pick_id":pid(origin,year,round_no),
            "sender_team_id":tid(origin),"receiver_team_id":tid(owner),
            "protected_range":{"from":low,"through":through},"protected_top_n":through,
            "fallback_pick_ids":[pid(*fallback)],"label":label,"status":"active","source":SOURCE,
            "notes":"IRL conditions normalized to native same-round fallback: original retains protected primary; receiver gets reserved fallback."})
        note(f"{year} R{round_no} {origin} protection",f"{label}; reserved {fallback[1]} R{round_no} {fallback[0]} fallback. Rollover and conversion branches replaced by this single native obligation.",[key(origin,year,round_no),fallback])
    for a,y,o,n,f in [("DAL",2027,"CHA",2,None),("MIA",2027,"CHA",14,2028),
        ("DEN",2027,"OKC",5,2028),("DEN",2029,"OKC",5,2030),
        ("LAL",2027,"MEM",4,None),("PHI",2028,"BKN",8,None),
        ("LAC",2028,"BOS",16,None),("MIN",2029,"UTA",5,None),
        ("GSW",2030,"MEM",20,None)]: protect(a,y,o,n,fallback_year=f)
    for a,y,o,low,high in [("ATL",2027,"DAL",31,55),("BOS",2028,"NYK",31,45),
        ("DEN",2028,"WAS",31,33),("DET",2028,"PHI",31,55),
        ("CHA",2030,"BOS",31,55),("MEM",2030,"MIN",31,50),("GSW",2032,"MEM",31,50)]: protect(a,y,o,high,2,low)
    # MIL/NOP pool is owned NOP+ATL; lower first is top-four protected.
    own("MIL",2027,"NOP");own("NOP",2027,"ATL")
    protect("NOP",2027,"ATL",4)
    swap(2027,"MIL","NOP","NOP",pool=["MIL","NOP"],counterparty="ATL")
    note("MIL/NOP 2027", "NOP receives better of MIL/NOP; ATL receives worse, protected top-4 with NOP same-round fallback. Resolve protection then comparison; a protected pick stays NOP.",[key(t,2027) for t in ["MIL","NOP"]])
    for t,y in [("BOS",2032),("MIN",2032),("PHX",2032),("CLE",2033)]:
        ledger[key(t,y)]["protections"] = "Frozen pick"
    # The 2029 IND first held by LAC, followed by LAC own firsts 2030-33,
    # is forfeited. TOR incoming firsts remain valid assets for LAC.
    for origin,y in [("IND",2029),*( ("LAC",y) for y in range(2030,2034))]:
        ledger[key(origin,y)]["status"] = "forfeited"
        ledger[key(origin,y)]["protections"] = None
        ledger[key(origin,y)]["notes"] += " Forfeited under official NBA Clippers penalty; never tradeable or selectable."

    output = {"format":"underlying_pick_ledger_v1","snapshot_date":"2026-10-13",
        "source":{"id":SOURCE,"url":URL,"team_count":30},
        "picks":[ledger[k] for k in sorted(ledger)], "normalization_audit":approximations,
        "counts":{"underlying_picks":len(ledger),"teams":30,"protected_terms":sum(t['type']=='protected_pick' for t in terms),"swap_terms":sum(t['type']=='pick_swap' for t in terms)}}
    (ROOT / "data/research/future_picks_realgm_2026_10_13.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n")
    # Resolve protections before comparisons, in source priority order.
    terms.sort(key=lambda t:t["type"] != "protected_pick")
    (ROOT / "data/overrides/pick_obligations_overrides.json").write_text(json.dumps({"version":"realgm_2026_10_13_native_terms","starting_data_version":"2026-10-13","notes":"Reviewed league snapshot. Native protected_pick and pick_swap terms; see normalization_audit in research ledger.","pick_obligations":terms},ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(output["counts"]))

if __name__ == "__main__": main()
