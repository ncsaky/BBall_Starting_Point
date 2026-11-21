"""BIDWAR-PRICE: a bidding war is fought on the seller's textbook price and the winner pays at least the second-best
bid; a slightly lower bid wins only for a strong stated reason of the seller's; the user's offers compete the same way
and the words say why (docs/agents/tasks/bidwar-price.md)."""
import unittest
import unittest.mock
from unittest.mock import patch

from nba_gm_data import front_office as fo
from nba_gm_data import trade_counters as tc
from nba_gm_data import trade_market as tm
from nba_gm_data import transactions as tx

from test_trade_market import league, office_row


def term(key, points, text):
    return {"key": key, "points": points, "text": text}


def bid(buyer, price, *terms_, accepted=True, to_assets=None, buyer_accepted=True):
    """A bid for b1: the seller's evaluation with its personality terms on top of the textbook price."""
    total = sum(t["points"] for t in terms_)
    return {"proposal": {"from_team_id": "b", "to_team_id": buyer, "from_assets": [{"kind": "player", "id": "b1"}],
                         "to_assets": list(to_assets or [])},
            "evaluations": [{"perspective_team_id": "b", "net_value": price + total, "acceptance_threshold": 0.0,
                             "accepted": accepted, "decision": "accept",
                             "personality_adjustments": {"total": total, "terms": list(terms_)}},
                            {"perspective_team_id": buyer, "net_value": 2.0, "acceptance_threshold": 0.0,
                             "accepted": buyer_accepted, "decision": "accept"}]}


def pairing(buyer):
    return {"buyer_id": buyer, "row": {"id": "b1", "team_id": "b", "name": "B1", "value": 55.0, "market": 55.0,
                                       "on_court": 60.0}, "reasons": ["gm_listed"], "rank": 0,
            "target": {"id": f"t:{buyer}"}}


def war_league(**kwargs):
    canonical = league(office_row("A"), office_row("B", patience=0.0), date="2027-02-05", **kwargs)
    canonical["teams"].append({"id": "c", "abbrev": "C"})
    return canonical


def run_war(canonical, bids, raises=None, evaluate=None):
    if not isinstance(tm.SearchMarket.raise_to_floor, unittest.mock.Mock):
        # No asset additions in these toy leagues unless a test sets them (raise_to_floor has its own test).
        with patch.object(tm.SearchMarket, "raise_to_floor", return_value=None):
            return run_war(canonical, bids, raises, evaluate)
    market = tm.SearchMarket(canonical, "2027-02-05", 2)
    market.filter_pairings([pairing(b) for b in bids], {})
    for order, (buyer, candidate) in enumerate(bids.items()):
        market.add_bid(pairing(buyer), candidate, [{"assets": []}], canonical, order)
    raises = raises or {}
    winners = market.resolve_bidding(evaluate or (lambda entry, option: option),
                                     lambda entry: raises.get(entry["pairing"]["buyer_id"], []))
    return market, winners


class PriceTests(unittest.TestCase):
    def test_the_price_leaves_out_personality_and_concessions(self):
        evaluation = bid("a", 4.0, term("opinion", 3.0, "B has always liked A1"),
                         term("concession", 2.0, "B gives a little ground"))["evaluations"][0]
        self.assertEqual(tm.evaluation_price(evaluation), 4.0)

    def test_the_war_goes_to_the_best_price_not_the_seller_s_concession(self):
        # 'a' looks better to B only because B has been conceding to it in long talks: not a reason to prefer it.
        canonical = war_league()
        _, winners = run_war(canonical, {"a": bid("a", 3.0, term("concession", 4.0, "B gives a little ground")),
                                         "c": bid("c", 5.0)})
        war = winners[0]["war"]
        self.assertEqual(war["winner"], "c")
        self.assertEqual(war["decision"]["rule"], "best_price")
        self.assertGreaterEqual(war["winning_price"], war["second_price"])

    def test_raises_are_on_the_price_and_the_winner_pays_at_least_the_second_best_bid(self):
        canonical = war_league()
        _, winners = run_war(canonical, {"a": bid("a", 3.0), "c": bid("c", 2.0)}, raises={"c": [bid("c", 8.0)]})
        war = winners[0]["war"]
        self.assertEqual(war["winner"], "c")
        self.assertEqual(war["winning_price"], 8.0)
        self.assertEqual(war["second_price"], 3.0)
        self.assertEqual(war["prices"], {"a": 3.0, "c": 8.0})


    def test_a_losing_bidder_adds_an_asset_of_its_own_to_stay_in(self):
        # Its built packages do not beat the leader, so it adds a pick (within its own limit); the leader, now
        # behind, cannot add more: the price rises to what the runner-up was willing to pay.
        canonical = war_league()
        asked = []

        def raise_to_floor(entry, seller, floor, evaluate):
            asked.append((entry["pairing"]["buyer_id"], floor))
            return bid("a", 7.0) if entry["pairing"]["buyer_id"] == "a" else None
        with patch.object(tm.SearchMarket, "raise_to_floor", side_effect=raise_to_floor):
            _, winners = run_war(canonical, {"a": bid("a", 3.0), "c": bid("c", 5.0)})
        war = winners[0]["war"]
        self.assertEqual(asked, [("a", 6.0), ("c", 8.0)])
        self.assertEqual((war["winner"], war["winning_price"], war["second_price"]), ("a", 7.0, 5.0))


class LowerBidTests(unittest.TestCase):
    liked = term("opinion", 4.0, "B has always liked A1 (its scouts weigh shooting and like his game)")
    picks = term("values_picks", 4.0, "B prizes draft picks")

    def test_a_slightly_lower_bid_wins_for_a_strong_stated_reason(self):
        canonical = war_league()
        with patch.object(tm.SearchMarket, "raise_to_floor", return_value=None):
            market, winners = run_war(canonical, {"a": bid("a", 6.0, self.liked), "c": bid("c", 8.0)})
        war = winners[0]["war"]
        self.assertEqual(war["winner"], "a")
        self.assertEqual(war["decision"]["rule"], "lower_bid")
        self.assertEqual(war["decision"]["gap"], 2.0)
        self.assertEqual(war["decision"]["reasons"][0]["key"], "opinion")
        text = tm.decision_text(canonical, war)
        self.assertIn("B took A's offer although C's was worth slightly more", text)
        self.assertIn("always liked A1", text)
        save = {}
        tm.apply_market_updates(save, market.updates(), canonical)
        stats = save["trade_market"]["stats"]["2026-27"]
        self.assertEqual(stats["wars_won_by_lower_bid"], 1)
        self.assertIn("always liked A1", save["trade_market"]["shopping"]["b1"]["sale_note"])

    def test_more_than_a_slight_gap_is_never_overcome(self):
        canonical = war_league()
        with patch.object(tm.SearchMarket, "raise_to_floor", return_value=None):
            _, winners = run_war(canonical, {"a": bid("a", 2.0, self.liked, self.picks), "c": bid("c", 8.0)})
        war = winners[0]["war"]
        self.assertEqual(war["winner"], "c")
        self.assertEqual(war["decision"]["passed_over"], "a")
        self.assertIn("could not match the price", tm.decision_text(canonical, war))

    def test_a_weak_reason_is_not_enough(self):
        canonical = war_league()
        mild = term("opinion", 1.5, "B has always liked A1")
        with patch.object(tm.SearchMarket, "raise_to_floor", return_value=None):
            _, winners = run_war(canonical, {"a": bid("a", 7.8, mild, term("values_picks", 1.5, "B prizes draft picks")),
                                             "c": bid("c", 8.0)})
        self.assertEqual(winners[0]["war"]["winner"], "c")
        self.assertFalse(tm.lower_bid_allowed(0.2, [{"points": 1.5}, {"points": 1.5}]))

    def test_the_preferred_bidder_raises_to_the_best_price_when_it_can(self):
        canonical = war_league()
        raised = bid("a", 8.5, self.liked)
        floors = []

        def raise_to_floor(entry, seller, floor, evaluate):
            floors.append(floor)
            return raised if floor == 8.0 else None  # it cannot outbid C in the rounds, but can match its price
        with patch.object(tm.SearchMarket, "raise_to_floor", side_effect=raise_to_floor, autospec=False):
            _, winners = run_war(canonical, {"a": bid("a", 2.0, self.liked, self.picks), "c": bid("c", 8.0)})
        war = winners[0]["war"]
        self.assertEqual(floors, [9.0, 8.0])  # a round raise to beat C by a point, then the floor: C's price
        self.assertEqual(war["winner"], "a")
        self.assertEqual(war["decision"]["rule"], "matched")
        self.assertGreaterEqual(war["winning_price"], war["second_price"])
        self.assertIn("raised it to match C's", tm.decision_text(canonical, war))

    def test_raise_to_floor_adds_an_asset_within_the_buyer_s_own_limit(self):
        canonical = war_league()
        market = tm.SearchMarket(canonical, "2027-02-05", 2)
        entry = {"pairing": pairing("a"), "candidate": bid("a", 2.0, to_assets=[{"kind": "pick", "id": "p1"}])}
        options = [("pick", [{"kind": "player", "id": "b1"}], [{"kind": "pick", "id": "p1"}, {"kind": "pick", "id": "p2"}], None),
                   ("pick", [{"kind": "player", "id": "b1"}], [{"kind": "pick", "id": "p1"}, {"kind": "pick", "id": "p3"}], None),
                   ("keep_own", [], [{"kind": "pick", "id": "p1"}], None)]
        quick = {("b", ("p1",)): 2.0, ("b", ("p1", "p2")): 7.0, ("b", ("p1", "p3")): 12.0}

        def quick_net(canonical, team, incoming, outgoing, config):
            if team == "b":
                return quick[(team, tuple(a["id"] for a in incoming))]
            return 0.0
        checked = []

        def evaluate(entry, option):
            ids = [a["value"] for a in option["assets"]]
            checked.append(ids)
            if ids == ["p1", "p2"]:
                return bid("a", 6.0, buyer_accepted=True)   # not enough
            return bid("a", 9.0, buyer_accepted=True)
        with patch.object(tc, "counter_options", return_value=options), \
                patch("nba_gm_data.trade_targets.quick_net", side_effect=quick_net):
            result = market.raise_to_floor(entry, "b", 8.0, evaluate)
        self.assertEqual(checked, [["p1", "p2"], ["p1", "p3"]])  # the smallest addition first
        self.assertEqual(market.seller_price(result, "b"), 9.0)
        with patch.object(tc, "counter_options", return_value=options), \
                patch("nba_gm_data.trade_targets.quick_net", side_effect=quick_net):
            refused = market.raise_to_floor(entry, "b", 8.0, lambda e, o: bid("a", 9.0, buyer_accepted=False))
        self.assertIsNone(refused)  # beyond the buyer's own price limit


class ReasonTests(unittest.TestCase):
    def test_a_competing_seller_will_not_strengthen_a_conference_contender(self):
        canonical = league(office_row("A"), office_row("B"), phase_a="peak", phase_b="peak")
        canonical["teams"] = [{"id": "a", "abbrev": "A", "conference": "West"},
                              {"id": "b", "abbrev": "B", "conference": "West"},
                              {"id": "c", "abbrev": "C", "conference": "East"}]
        canonical["team_strategic_states"].append({"team_id": "c", "window_phase": "peak"})
        rival = tm.seller_preferences(canonical, "b", "a", bid("a", 5.0))
        self.assertEqual(rival["rival"]["points"], -tm.RIVAL_POINTS)
        self.assertEqual(tm.seller_preferences(canonical, "b", "c", bid("c", 5.0)), {})
        reasons = tm.favoring_reasons(canonical, "b", "c", {}, "a", rival)
        self.assertIn("would rather not strengthen A, a contender in its own West conference", reasons[0]["text"])

    def test_a_rebuilding_seller_prefers_young_players_and_picks(self):
        canonical = league(office_row("A"), office_row("B"))
        young = bid("a", 5.0, to_assets=[{"kind": "pick", "id": "pick_a1"}, {"kind": "player", "id": "a3"}])
        old = bid("a", 5.0, to_assets=[{"kind": "player", "id": "a1"}])
        with patch.object(tx, "package_value_for_team", return_value=10.0):
            prefs = tm.seller_preferences(canonical, "b", "a", young)
            self.assertAlmostEqual(prefs["timeline"]["points"], tm.TIMELINE_POINTS)
            self.assertNotIn("timeline", tm.seller_preferences(canonical, "b", "a", old))
        text = tm.favoring_reasons(canonical, "b", "a", prefs, "c", {})[0]["text"]
        self.assertIn("young players and picks that fit its timeline", text)

    def test_no_traits_no_preferences(self):
        canonical = league()
        canonical["front_office_traits"] = {}
        self.assertEqual(tm.seller_preferences(canonical, "b", "a", bid("a", 5.0)), {})


class UserSideTests(unittest.TestCase):
    def save(self, price=8.0, leader_preferences=None):
        return {"meta": {"user_team_id": "u", "user_team_abbrev": "U", "seed": 1}, "state": {"current_date": "2027-02-03"},
                "front_office_traits": {"teams": {"b": office_row("B", patience=20.0)}, "base_season": 2026},
                "trade_market": {"shopping": {"b1": {"player_id": "b1", "player_name": "B1", "seller_id": "b",
                                                     "status": "bidding", "decide_by": "2027-02-05",
                                                     "interested": ["a", "c"],
                                                     "bids": [{"margin": price + 3.0, "price": price, "leader": "a",
                                                               "price_leader": "a",
                                                               "leader_preferences": leader_preferences or {}}]}}}}

    def active(self):
        canonical = league(office_row("A"), office_row("B"))
        canonical["teams"].append({"id": "u", "abbrev": "U"})
        return canonical

    def user_offer(self, price, *terms_):
        candidate = bid("u", price, *terms_)
        return candidate

    def test_the_user_is_told_who_leads_and_about_how_much_more_it_takes(self):
        save = self.save(price=20.0)
        with patch("nba_gm_data.save.human_controlled_team_ids", return_value={"u"}):
            result = tm.user_offer_competition(self.active(), save, self.user_offer(10.0), "u", "2027-02-03")
        self.assertTrue(result["beaten"])
        self.assertEqual(result["required_price"], 21.0)
        self.assertIn("A's offer for B1 is worth more to B; you'd need to add about a second-round pick", result["text"])
        state, note = tm.user_bid_state(self.active(), save["trade_market"]["shopping"]["b1"])
        self.assertEqual(state, "outbid")
        self.assertIn("you'd need to add about a second-round pick", note)

    def test_the_users_personality_lead_does_not_count_as_price(self):
        # A seller concession toward the user is not a higher price.
        save = self.save(price=8.0)
        with patch("nba_gm_data.save.human_controlled_team_ids", return_value={"u"}):
            result = tm.user_offer_competition(self.active(), save,
                                               self.user_offer(6.0, term("concession", 5.0, "B gives ground")), "u",
                                               "2027-02-03")
        self.assertTrue(result["beaten"])

    def test_the_same_rare_exception_applies_to_the_user(self):
        save = self.save(price=8.0)
        liked = term("opinion", 4.5, "B has always liked U1 (its scouts weigh feel and like his game)")
        with patch("nba_gm_data.save.human_controlled_team_ids", return_value={"u"}):
            result = tm.user_offer_competition(self.active(), save, self.user_offer(7.0, liked), "u", "2027-02-03")
        self.assertFalse(result["beaten"])
        self.assertIn("Your offer is a little below A's, but B prefers it", result["text"])
        self.assertIn("always liked U1", result["text"])
        user_bid = save["trade_market"]["shopping"]["b1"]["user_bid"]
        self.assertTrue(tm.user_bid_leads(user_bid, 8.0, {}))
        self.assertFalse(tm.user_bid_leads(user_bid, 13.0, {}))  # never more than a slight gap

    def test_the_trade_states_why_the_winner_won(self):
        canonical = war_league()
        _, winners = run_war(canonical, {"a": bid("a", 3.0), "c": bid("c", 5.0)})
        candidate = {"trade_reasons": {"text": "C buys B1.", "bidding_war": winners[0]["war"]}, "evaluations": []}
        text = fo.with_market_reasons(canonical, candidate)["trade_reasons"]["text"]
        self.assertIn("C won a bidding war against A", text)
        self.assertIn("C's offer was worth the most to B, more than A's.", text)

    def test_value_words(self):
        self.assertEqual(tm.value_words(3.0), "a little more (less than a second-round pick)")
        self.assertEqual(tm.value_words(9.5), "about a second-round pick")
        self.assertEqual(tm.value_words(35.0), "about a late first-round pick")
        self.assertEqual(tm.value_words(80.0), "well over a first-round pick")


if __name__ == "__main__":
    unittest.main()
