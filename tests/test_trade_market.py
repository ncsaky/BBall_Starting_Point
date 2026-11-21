"""TRADE-MARKET: front-office traits from real reputations, bounded and stated personality terms (no dice), the
negotiation ledger across days, shopping only with a reason, bidding, final offers, the user's offers competing, and
front-office hints that describe the traits the engine uses (docs/agents/tasks/trade-market.md)."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from nba_gm_data import front_office as fo
from nba_gm_data import trade_counters as tc
from nba_gm_data import trade_market as tm
from nba_gm_data import transactions as tx

TEAMS = [{"id": f"team_{a.lower()}", "abbrev": a} for a in ("OKC", "PHX", "NOP", "CHI", "SAS", "UTA", "AAA", "BBB")]


def office_row(abbrev, *, savvy=50.0, urgency=50.0, patience=50.0, loyalty=50.0, biases=(), connections=()):
    return {"abbrev": abbrev, "savvy": savvy, "urgency": urgency, "patience": patience, "loyalty": loyalty,
            "biases": [{"key": key, "why": None, "sources": []} for key in biases],
            "connections": list(connections), "from_reputation": [], "sources": {}, "why": {}}


def league(a=None, b=None, *, phase_a="peak", phase_b="rebuilding", date="2027-01-20"):
    """Two AI teams, 'a' (the one under test) and 'b', with four players each and a draft pick."""
    players, values = [], []
    for team in ("a", "b"):
        for i, (age, value) in enumerate(((24, 60.0), (31, 55.0), (27, 35.0), (22, 20.0))):
            pid = f"{team}{i}"
            players.append({"id": pid, "team_id": team, "name": pid.upper(), "age": age})
            values.append({"player_id": pid, "player_value": value, "on_court_value": value})
    return {
        "meta": {"current_date": date, "active_season": "2026-27"},
        "teams": [{"id": "a", "abbrev": "A"}, {"id": "b", "abbrev": "B"}],
        "players": players, "player_asset_valuations": values,
        "team_strategic_states": [{"team_id": "a", "window_phase": phase_a}, {"team_id": "b", "window_phase": phase_b}],
        "front_office_traits": {"a": a or office_row("A"), "b": b or office_row("B")},
        "draft_picks": [{"id": "pick_a1", "round": 1, "current_owner_team_id": "a"}],
    }


def player(pid):
    return {"kind": "player", "id": pid}


def no_opinions():
    return patch.object(fo, "player_opinion", return_value=None)


class TraitsTests(unittest.TestCase):
    def test_real_offices_start_from_widely_held_reputations_with_sources(self):
        data = fo.reputation_data()
        source_ids = {s["id"] for s in data["sources"]}
        traits = fo.base_traits(TEAMS, seed=17)["teams"]
        okc = traits["team_okc"]
        self.assertEqual(okc["savvy"], 95.0)
        self.assertIn("savvy", okc["from_reputation"])
        self.assertTrue(okc["sources"]["savvy"])
        self.assertEqual([b["key"] for b in okc["biases"]], ["values_picks"])
        self.assertEqual(traits["team_phx"]["urgency"], 88.0)
        # Every documented trait, habit and connection names its sources, and every source is recorded.
        for abbrev, row in data["teams"].items():
            for key, value in row.items():
                items = value if isinstance(value, list) else [value]
                for item in items:
                    self.assertTrue(item["sources"], (abbrev, key))
                    self.assertTrue(set(item["sources"]) <= source_ids, (abbrev, key))
        # A regime too new for a reputation is drawn from the measured spread, inside the bounds.
        chi = traits["team_chi"]
        self.assertTrue(chi["regime_new"])
        self.assertEqual(chi["from_reputation"], [])
        for trait in fo.TRAITS:
            self.assertTrue(fo.TRAIT_FLOOR <= chi[trait] <= fo.TRAIT_CEILING)

    def test_generated_traits_are_seeded_and_persistent(self):
        one = fo.base_traits(TEAMS, seed=17)["teams"]
        again = fo.base_traits(TEAMS, seed=17)["teams"]
        other = fo.base_traits(TEAMS, seed=18)["teams"]
        self.assertEqual(one, again)
        self.assertNotEqual(one["team_aaa"]["patience"], other["team_aaa"]["patience"])
        self.assertEqual(one["team_okc"]["savvy"], other["team_okc"]["savvy"])  # reputations do not depend on seed

    def test_unknown_offices_centre_on_the_league_middle(self):
        spread = fo.measured_spread(fo.reputation_data())
        for trait, (centre, sd) in spread.items():
            self.assertEqual(centre, 50.0)
            self.assertTrue(8.0 <= sd <= 25.0, (trait, sd))

    def test_traits_drift_slowly_and_deterministically(self):
        base = fo.base_traits(TEAMS, seed=17)
        base["base_season"] = 2026
        later = fo.drifted(base, 2028)
        self.assertEqual(later, fo.drifted(base, 2028))
        self.assertEqual(fo.drifted(base, 2026), base["teams"])
        for tid, row in later.items():
            for trait in fo.TRAITS:
                self.assertLess(abs(row[trait] - base["teams"][tid][trait]), 4 * fo.DRIFT_PER_SEASON * 2)

    def test_save_keeps_its_traits(self):
        save = {"meta": {"seed": 17}, "state": {"current_date": "2026-07-01"}}
        stored = fo.ensure_save_traits(save, {"teams": TEAMS})
        self.assertEqual(stored["base_season"], 2026)
        self.assertIs(fo.ensure_save_traits(save, {"teams": TEAMS}), stored)
        self.assertEqual(fo.traits_view(save)["team_okc"]["savvy"], 95.0)


class PersonalityTermsTests(unittest.TestCase):
    def test_urgent_contender_pays_a_premium_with_its_reason(self):
        canonical = league(office_row("A", urgency=90.0))
        with no_opinions():
            result = fo.personality_terms(canonical, "a", [player("b1")], [player("a3")])
        urgency = next(t for t in result["terms"] if t["key"] == "urgency")
        self.assertGreater(urgency["points"], 0)
        self.assertLessEqual(urgency["points"], fo.URGENCY_CAP)
        self.assertIn("win-now urgency", urgency["text"])

    def test_no_urgency_premium_outside_an_open_window(self):
        canonical = league(office_row("A", urgency=90.0), phase_a="rebuilding")
        with no_opinions():
            result = fo.personality_terms(canonical, "a", [player("b1")], [])
        self.assertFalse([t for t in result["terms"] if t["key"] == "urgency"])

    def test_a_savvy_office_makes_no_systematic_mistake(self):
        canonical = league(office_row("A", savvy=80.0, biases=("overpays_veterans",)))
        with no_opinions():
            result = fo.personality_terms(canonical, "a", [player("b1")], [])
        self.assertFalse([t for t in result["terms"] if t["key"] == "overpays_veterans"])
        canonical = league(office_row("A", savvy=20.0, biases=("overpays_veterans",)))
        with no_opinions():
            result = fo.personality_terms(canonical, "a", [player("b1")], [])
        term = next(t for t in result["terms"] if t["key"] == "overpays_veterans")
        self.assertIn("B1", term["text"])
        self.assertLessEqual(term["points"], fo.VETERAN_CAP)

    def test_terms_are_bounded_and_in_plain_words(self):
        canonical = league(office_row("A", savvy=10.0, urgency=95.0, loyalty=95.0,
                                      biases=("overpays_veterans", "chases_stars", "underrates_picks")))
        opinion = {"points": 5.0, "kind": "scouting", "why": "its scouts weigh shooting and like his"}
        with patch.object(fo, "player_opinion", return_value=opinion), \
                patch.object(tx, "package_value_for_team", return_value=43.0):
            result = fo.personality_terms(canonical, "a", [player("b0"), player("b1")], [{"kind": "pick", "id": "pick_a1"}])
        self.assertLessEqual(abs(result["total"]), fo.PERSONALITY_CAP)
        self.assertGreater(result["uncapped"], fo.PERSONALITY_CAP)
        for term in result["terms"]:
            self.assertTrue(term["text"])
            self.assertNotIn("_", term["text"])

    def test_no_dice_the_same_deal_always_gets_the_same_adjustment(self):
        canonical = league(office_row("A", urgency=80.0, savvy=30.0, biases=("overrates_own",)))
        with no_opinions():
            one = tx.personality_trade_adjustment(canonical, "a", "proposal-1", 1, incoming=[player("b1")], outgoing=[player("a1")])
            two = tx.personality_trade_adjustment(canonical, "a", "proposal-2", 99, incoming=[player("b1")], outgoing=[player("a1")])
        self.assertEqual(one, two)

    def test_no_traits_no_personality(self):
        canonical = league()
        canonical.pop("front_office_traits")
        self.assertEqual(fo.personality_terms(canonical, "a", [player("b1")], [])["total"], 0.0)
        canonical = league()
        canonical["_human_team_ids"] = ["a"]
        self.assertEqual(fo.personality_terms(canonical, "a", [player("b1")], [])["terms"], [])

    def test_trade_reasons_state_the_personality(self):
        candidate = {"trade_reasons": {"text": "B moved him."}, "evaluations": [
            {"perspective_team_id": "a", "personality_adjustments": {"terms": [
                {"key": "urgency", "points": 3.2, "text": "A's win-now urgency: it pays a premium while its window is open"},
                {"key": "opinion", "points": 0.4, "text": "too small to state"}]}}]}
        out = fo.with_market_reasons(league(), candidate)
        self.assertIn("Personality: A's win-now urgency", out["trade_reasons"]["text"])
        self.assertNotIn("too small", out["trade_reasons"]["text"])
        self.assertEqual(len(out["trade_reasons"]["personality"]), 1)

    def test_urgency_and_free_spending_widen_the_pick_allowance(self):
        canonical = league(office_row("A", urgency=90.0, savvy=20.0, biases=("underrates_picks",)))
        extra, reason = fo.pick_allowance(canonical, "a")
        self.assertGreater(extra, fo.URGENCY_PICK_ALLOWANCE)
        self.assertIn("win-now urgency", reason)
        self.assertEqual(fo.pick_allowance(league(), "a"), (0.0, None))


class LedgerTests(unittest.TestCase):
    def update(self, day, gaps, key="a|b|b1"):
        return {"date": day, "negotiations": [{"key": key, "buyer_id": "a", "seller_id": "b", "player_id": "b1",
                                               "player_name": "B1", "gaps": gaps, "offer": None,
                                               "seller_reasons": ["gm_listed"], "seller_stance": "rebuild"}]}

    def test_a_negotiation_persists_across_days_and_concedes_more(self):
        active = league(office_row("A", patience=50.0), office_row("B", patience=50.0), date="2027-01-10")
        save = {}
        tm.apply_market_updates(save, self.update("2027-01-10", {"a": -2.0, "b": -3.0}), active)
        tm.apply_market_updates(save, self.update("2027-01-12", {"a": -1.5, "b": -2.0}), active)
        neg = save["trade_market"]["negotiations"]["a|b|b1"]
        self.assertEqual(neg["status"], "open")
        self.assertEqual([r["date"] for r in neg["rounds"]], ["2027-01-10", "2027-01-12"])
        canonical = {**active, "trade_market_ledger": tm.ledger_view(save)}
        first, _ = tm.concession_size({**canonical, "trade_market_ledger": {"negotiations": {
            "k": {**neg, "rounds": neg["rounds"][:1]}}}}, "b", {**neg, "rounds": neg["rounds"][:1]})
        second, _ = tm.concession_size(canonical, "b", neg)
        self.assertGreater(second, first)
        term = tm.concession_term(canonical, "b", {"from_team_id": "b", "to_team_id": "a"}, [], [player("b1")])
        self.assertEqual(term["key"], "concession")
        self.assertIn("talked about B1", term["text"])
        # The same day is never recorded twice.
        tm.apply_market_updates(save, self.update("2027-01-12", {"a": -1.0, "b": -1.0}), active)
        self.assertEqual(len(save["trade_market"]["negotiations"]["a|b|b1"]["rounds"]), 2)

    def test_patient_offices_concede_less(self):
        neg = {"rounds": [{"date": "2027-01-10"}, {"date": "2027-01-11"}], "buyer_id": "a", "seller_id": "b"}
        patient = league(office_row("A", patience=90.0))
        hasty = league(office_row("A", patience=20.0))
        self.assertLess(tm.concession_size(patient, "a", neg)[0], tm.concession_size(hasty, "a", neg)[0])
        self.assertLess(tm.max_rounds(20.0), tm.max_rounds(90.0))

    def test_a_refused_final_offer_ends_talks_with_a_cooldown(self):
        active = league(office_row("A", patience=0.0), office_row("B", patience=95.0), date="2027-01-10")
        save = {}
        for day in ("2027-01-10", "2027-01-11", "2027-01-12"):
            tm.apply_market_updates(save, self.update(day, {"a": -4.0, "b": -4.0}), active)
        neg = save["trade_market"]["negotiations"]["a|b|b1"]
        self.assertEqual(neg["status"], "dead")
        self.assertEqual(neg["death"]["final_by"], ["a"])
        self.assertEqual(neg["cooldown_until"], "2027-02-11")
        market = tm.SearchMarket({**active, "trade_market_ledger": tm.ledger_view(save)}, "2027-01-20", 1)
        pairing = {"buyer_id": "a", "row": {"id": "b1", "team_id": "b"}, "reasons": ["gm_listed"], "rank": 0}
        self.assertFalse(market.reopen(neg, pairing))  # inside the cooldown
        later = tm.SearchMarket({**active, "trade_market_ledger": tm.ledger_view(save)}, "2027-02-20", 1)
        with patch.object(fo, "player_opinion", return_value={"points": 3.0}):
            self.assertFalse(later.reopen(neg, pairing))  # keen, but nothing changed for the seller
            changed = {**pairing, "reasons": ["gm_listed", "over_tax_line"]}
            self.assertTrue(later.reopen(neg, changed))

    def test_deadline_day_makes_every_motivated_side_a_final_offer(self):
        canonical = league(office_row("A", patience=40.0), office_row("B"), date="2027-02-05")
        term = tm.concession_term(canonical, "a", None, [player("b1")], [])
        self.assertEqual(term["key"], "final_offer")
        self.assertIn("deadline day", term["text"])
        # A side giving a player it has no reason to move, getting no player back, makes no concession.
        with patch("nba_gm_data.trade_targets.team_sell_reasons", return_value={}), \
                patch("nba_gm_data.trade_targets.salary_filler", return_value={}):
            self.assertIsNone(tm.concession_term(canonical, "b", None, [{"kind": "pick", "id": "x"}], [player("b1")]))
            # Getting players back does not make a team that had no plan to move its player concede.
            self.assertIsNone(tm.concession_term(canonical, "b", None, [player("a2"), player("a3")], [player("b1")]))
        with patch("nba_gm_data.trade_targets.team_sell_reasons", return_value={"b1": ["gm_listed"]}), \
                patch("nba_gm_data.trade_targets.salary_filler", return_value={}):
            self.assertEqual(tm.concession_term(canonical, "b", None, [player("a2")], [player("b1")])["key"], "final_offer")
        self.assertIsNone(tm.concession_term(league(date="2027-02-04"), "a", None, [player("b1")], []))


class ShoppingTests(unittest.TestCase):
    def pairing(self, buyer, pid="b1", reasons=("gm_listed",), value=55.0):
        return {"buyer_id": buyer, "row": {"id": pid, "team_id": "b", "name": pid.upper(), "value": value, "market": value,
                                           "on_court": 60.0}, "reasons": list(reasons), "rank": 0,
                "target": {"id": f"t:{buyer}"}}

    def test_only_players_with_a_reason_to_move_are_shopped(self):
        canonical = league()
        market = tm.SearchMarket(canonical, "2027-01-20", 1)
        listed = market.filter_pairings([self.pairing("a"), self.pairing("c")], {})
        self.assertTrue(market.shopped(listed[0]))
        self.assertEqual(len(market.updates()["shopping"]), 1)
        market = tm.SearchMarket(canonical, "2027-01-20", 1)
        listed = market.filter_pairings([self.pairing("a", reasons=()), self.pairing("c", reasons=())], {})
        self.assertFalse(market.shopped(listed[0]))
        self.assertEqual(market.updates()["shopping"], [])

    def test_unsolicited_offers_for_a_contenders_star_are_rare(self):
        canonical = league(office_row("A", urgency=90.0), office_row("B", patience=80.0), phase_b="peak")
        star = self.pairing("a", reasons=(), value=80.0)
        diagnostics = {}
        with no_opinions():
            kept = tm.SearchMarket(canonical, "2027-01-20", 1).filter_pairings([star], diagnostics)
        self.assertEqual(kept, [])
        self.assertEqual(diagnostics["market_unsolicited_screened_out"], 1)
        market = tm.SearchMarket(canonical, "2027-01-20", 1)
        with patch.object(fo, "player_opinion", return_value={"points": 3.0}):
            kept = market.filter_pairings([star], {})
        self.assertEqual(kept, [])  # a patient owner refuses to engage
        self.assertEqual(len(market.unsolicited), 1)
        self.assertFalse(market.unsolicited[0]["engaged"])

    def test_bidding_war_goes_to_the_best_offer(self):
        canonical = league(office_row("A"), office_row("B", patience=0.0))
        market = tm.SearchMarket(canonical, "2027-02-05", 2)
        market.filter_pairings([self.pairing("a"), self.pairing("c")], {})

        def bid(buyer, margin):
            return {"evaluations": [{"perspective_team_id": "b", "net_value": margin, "acceptance_threshold": 0.0,
                                     "decision": "accept"}], "proposal": {"from_team_id": "b", "to_team_id": buyer}}
        market.add_bid(self.pairing("a"), bid("a", 3.0), [{"assets": []}], canonical, 0)
        market.add_bid(self.pairing("c"), bid("c", 2.0), [{"assets": []}], canonical, 1)
        raises = {"c": [8.0], "a": []}

        def evaluate(entry, option):
            return bid(entry["pairing"]["buyer_id"], option)
        winners = market.resolve_bidding(evaluate, lambda entry: raises[entry["pairing"]["buyer_id"]])
        self.assertEqual(len(winners), 1)
        war = winners[0]["war"]
        self.assertEqual(war["winner"], "c")
        self.assertEqual(war["bidders"], ["a", "c"])
        self.assertEqual(len(war["rounds"]), 2)
        save = {}
        tm.apply_market_updates(save, market.updates(), canonical)
        self.assertEqual(save["trade_market"]["stats"]["2026-27"]["bidding_wars"], 1)


class UserSideTests(unittest.TestCase):
    def save(self, bid_margin=8.0):
        return {"meta": {"user_team_id": "u", "user_team_abbrev": "U", "seed": 1}, "state": {"current_date": "2027-02-03"},
                "front_office_traits": {"teams": {"b": office_row("B", patience=20.0)}, "base_season": 2026},
                "trade_market": {"shopping": {"b1": {"player_id": "b1", "player_name": "B1", "seller_id": "b",
                                                     "status": "bidding", "decide_by": "2027-02-05", "interested": ["a", "c"],
                                                     "bids": [{"margin": bid_margin}]}}}}

    def candidate(self, margin):
        return {"proposal": {"from_team_id": "b", "to_team_id": "u", "from_assets": [player("b1")], "to_assets": []},
                "evaluations": [{"perspective_team_id": "b", "accepted": True, "net_value": margin,
                                 "acceptance_threshold": 0.0}]}

    def test_the_users_offer_must_beat_the_best_bid(self):
        save = self.save()
        with patch("nba_gm_data.save.human_controlled_team_ids", return_value={"u"}):
            beaten = tm.user_offer_competition({"teams": [{"id": "b", "abbrev": "B"}]}, save, self.candidate(5.0), "u", "2027-02-03")
            self.assertTrue(beaten["beaten"])
            self.assertEqual(beaten["required_margin"], 9.0)
            self.assertIn("worth more to B", beaten["text"])
            leading = tm.user_offer_competition({"teams": []}, save, self.candidate(12.0), "u", "2027-02-03")
        self.assertFalse(leading["beaten"])
        self.assertEqual(save["trade_market"]["shopping"]["b1"]["user_bid"]["margin"], 12.0)
        self.assertIn("u", save["trade_market"]["shopping"]["b1"]["interested"])

    def test_the_users_leading_offer_holds_off_the_ai_bidders(self):
        canonical = league(office_row("A"), office_row("B", patience=90.0))
        canonical["trade_market_ledger"] = {"shopping": {"b1": {"player_id": "b1", "status": "bidding",
                                                                "decide_by": "2027-02-05",
                                                                "user_bid": {"margin": 9.0, "accepted_by_seller": True}}}}
        market = tm.SearchMarket(canonical, "2027-02-04", 2)
        bid = {"evaluations": [{"perspective_team_id": "b", "net_value": 6.0, "acceptance_threshold": 0.0}],
               "proposal": {"from_team_id": "b", "to_team_id": "a"}}
        market.add_bid({"buyer_id": "a", "row": {"id": "b1", "team_id": "b"}}, bid, [], canonical, 0)
        self.assertEqual(market.resolve_bidding(lambda *a: None, lambda b: []), [])
        self.assertEqual(market.waiting[0]["status"], "user_leads")

    def test_an_impatient_office_makes_final_offers_that_lapse(self):
        save = self.save()
        offer = {"proposal": {"from_team_id": "b", "to_team_id": "u", "from_assets": [], "to_assets": []}}
        with patch("nba_gm_data.save.human_controlled_team_ids", return_value={"u"}):
            terms = tm.user_offer_terms(save, offer, "2027-01-20")
        self.assertEqual(terms["respond_by"], "2027-01-21")
        self.assertIn("take it or leave it", terms["text"])
        save["user_trade_offers"] = [{**offer, "offer_context": {"status": "pending_user_review", "final_offer": terms}}]
        self.assertEqual(tm.expire_final_offers(save, "2027-01-21"), 0)
        self.assertEqual(tm.expire_final_offers(save, "2027-01-22"), 1)
        self.assertEqual(save["user_trade_offers"][0]["offer_context"]["status"], "expired_final_offer")

    def test_counters_to_the_user_end_in_a_final_offer_by_patience(self):
        self.assertEqual(tc.counter_round_limit(league(office_row("A", patience=10.0)), "a"), 1)
        self.assertEqual(tc.counter_round_limit(league(office_row("A", patience=95.0)), "a"), tc.COUNTER_ROUNDS)
        deadline = league(office_row("A", patience=95.0), date="2027-02-05")
        self.assertEqual(tc.counter_round_limit(deadline, "a", previous=1), 2)

    def test_dealings_count_once_a_day(self):
        save = self.save()
        with patch("nba_gm_data.save.human_controlled_team_ids", return_value={"u"}):
            self.assertTrue(tm.record_dealing(save, "b", "2027-02-03", "offer"))
            self.assertFalse(tm.record_dealing(save, "b", "2027-02-03", "offer"))
            self.assertTrue(tm.record_dealing(save, "b", "2027-02-04", "reply"))
            self.assertFalse(tm.record_dealing(save, "u", "2027-02-04", "offer"))
        self.assertEqual(tm.dealings(save, "b"), 2)


class HintTests(unittest.TestCase):
    def test_hints_describe_the_traits_the_engine_uses_and_sharpen_with_dealings(self):
        row = {**office_row("A", savvy=95.0, patience=85.0, urgency=30.0, biases=("values_picks", "overpays_veterans")),
               "from_reputation": ["savvy"], "why": {"savvy": "Ranked first."}, "sources": {"savvy": ["src_x"]}}
        row["biases"][0]["sources"] = ["src_y"]
        canonical = league(row)
        with patch.object(fo, "_taste", return_value={"shooting": 1.5, "tools": 0.0}):
            cold = fo.office_hints(canonical, "a", 0)
            rough = fo.office_hints(canonical, "a", 1)
            sharp = fo.office_hints(canonical, "a", 4)
        self.assertEqual(cold["precision"], "reputation")
        texts = [line["text"] for line in cold["lines"]]
        self.assertEqual(texts[0], "Known to be one of the sharpest judges of value in the league.")
        self.assertIn("Known: it prizes draft picks.", texts)
        self.assertFalse(any("patient" in t for t in texts))  # patience is not a reputation here
        self.assertFalse(any("veterans" in t for t in texts))  # a savvy office's bias is inert, so it is not shown
        self.assertEqual(rough["precision"], "rough")
        self.assertIn("Seems patient in negotiations.", [line["text"] for line in rough["lines"]])
        sharp_texts = [line["text"] for line in sharp["lines"]]
        self.assertIn("Very patient: it holds out for its price, rarely makes a final offer before deadline day and "
                      "gives its core time.", sharp_texts)
        self.assertIn("Unwilling to pay up for help now.", sharp_texts)
        self.assertTrue(any("scouts lean toward shooting" in t for t in sharp_texts))
        for hint in (cold, rough, sharp):
            for line in hint["lines"]:
                self.assertFalse(any(ch.isdigit() for ch in line["text"]))  # exact numbers stay hidden

    def test_patience_words_match_the_round_limit(self):
        # "very patient" offices really do keep talking longest (the words follow the engine's numbers).
        self.assertEqual(tm.max_rounds(85.0), 6)
        self.assertEqual(tm.max_rounds(15.0), 3)


if __name__ == "__main__":
    unittest.main()
