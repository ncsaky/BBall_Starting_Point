"""Evidence shared by the builder, finder and inbox must stay current and complete."""

from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from nba_gm_data.app_actions import (
    contract_summary,
    enhance_trade_candidate,
    load_app_canonical,
    trade_presentation_context,
    user_trade_offers_payload,
)
from nba_gm_data.save import player_display_attribute_summary, player_salary_table
from nba_gm_data.transactions import (
    current_salary,
    contract_for_player,
    find_trade_for_assets,
    pick_display_label,
    pick_obligation_context_note,
    with_transaction_context,
)


ROOT = Path(__file__).resolve().parents[1]


class TradePayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = with_transaction_context(load_app_canonical(ROOT))
        cls.user = next(row for row in cls.canonical["teams"] if row["abbrev"] == "GSW")
        cls.partner = next(row for row in cls.canonical["teams"] if row["abbrev"] == "LAL")
        cls.player = next(row for row in cls.canonical["players"] if row["team_id"] == cls.user["id"])
        cls.other = next(row for row in cls.canonical["players"] if row["team_id"] == cls.partner["id"])
        cls.save = {
            "meta": {"season": "2026-27", "user_team_id": cls.user["id"]},
            "state": {"current_date": "2026-12-29"},
            "health_states": [{"player_id": cls.player["id"], "availability_status": "out",
                               "injury_severity": "moderate", "return_date": "2027-01-20"}],
        }

    def candidate(self, from_assets=None, to_assets=None):
        return {
            "proposal": {"id": "presentation-test", "from_team_id": self.user["id"],
                         "to_team_id": self.partner["id"],
                         "from_assets": from_assets if from_assets is not None else [{"kind": "player", "id": self.player["id"], "label": "Old name"}],
                         "to_assets": to_assets if to_assets is not None else [{"kind": "player", "id": self.other["id"]}]},
            "accepted_by_all": False,
            "legality": {"status": "legal", "issues": [], "manual_review": []},
            "evaluations": [{"perspective_team_id": self.partner["id"], "accepted": True, "net_value": 3.0}],
        }

    def test_unresolved_locked_pick_can_be_displayed_without_becoming_tradeable(self):
        from nba_gm_data.app_actions import draft_asset_pick_payload
        from nba_gm_data.transactions import tradeable_picks_for_team
        data = {'meta': {'active_season': '2026-27'}, 'teams': [{'id': 'a', 'abbrev': 'A'}],
                'draft_picks': [{'id': 'p', 'season': '2030', 'round': 1, 'status': 'future',
                    'original_team_id': 'a', 'current_owner_team_id': 'a', '_obligation_locked': True,
                    'protection_summary': None}], 'pick_obligations': []}
        item = draft_asset_pick_payload(data, data['draft_picks'][0], 'balanced')
        self.assertIn('requires review', item['condition_summary'])
        self.assertFalse(item['terms_editable'])
        self.assertEqual(tradeable_picks_for_team(data, 'a'), [])

    def test_player_evidence_matches_current_identity_ratings_contract_and_risk(self):
        original = self.candidate()
        untouched = deepcopy(original)
        result = enhance_trade_candidate(self.canonical, original, save=self.save)
        asset = result["proposal"]["from_assets"][0]
        attrs = player_display_attribute_summary(self.canonical, self.player["id"])
        valuation = next(row for row in self.canonical["player_asset_valuations"] if row["player_id"] == self.player["id"])
        self.assertEqual(asset["name"], self.player["name"])
        self.assertEqual(asset["headshot_url"], self.player.get("headshot_url"))
        self.assertEqual(asset["age"], self.player.get("display_age", self.player.get("age")))
        self.assertEqual(asset["overall"], attrs["overall"])
        self.assertEqual(asset["ratings"], attrs)
        self.assertEqual(asset["upside_remaining"], round(max(0, min(5, valuation["development_upside"] / 22 * 5)), 1))
        self.assertEqual(asset["health_risk"], round(valuation["health_risk"], 1))
        self.assertEqual(asset["health"]["status"], "out")
        self.assertEqual(asset["salary_by_year"], player_salary_table(self.canonical, self.player["id"]))
        salary = current_salary(contract_for_player(self.canonical, self.player["id"]))
        self.assertEqual(asset["salary_millions"], round(salary / 1_000_000, 2) if salary is not None else None)
        self.assertEqual(result["legality"], original["legality"])
        self.assertEqual(result["evaluations"], original["evaluations"])
        self.assertEqual(original, untouched)

    def test_saved_receive_only_team_is_not_presented_as_a_legal_trade(self):
        original = self.candidate()
        third = next(t for t in self.canonical['teams'] if t['id'] not in {self.user['id'], self.partner['id']})
        extra = next(p for p in self.canonical['players'] if p['team_id'] == self.partner['id'] and p['id'] != self.other['id'])
        original['proposal']['transfers'] = [
            {'from_team_id': self.user['id'], 'to_team_id': self.partner['id'], 'assets': [{'kind': 'player', 'id': self.player['id']}]},
            {'from_team_id': self.partner['id'], 'to_team_id': self.user['id'], 'assets': [{'kind': 'player', 'id': self.other['id']}]},
            {'from_team_id': self.partner['id'], 'to_team_id': third['id'], 'assets': [{'kind': 'player', 'id': extra['id']}]},
        ]
        original['accepted_by_all'] = True
        before = deepcopy(original)
        result = enhance_trade_candidate(self.canonical, original, save=self.save)
        self.assertEqual(result['legality']['status'], 'illegal')
        self.assertTrue(any(f"{third['abbrev']} must send" in issue for issue in result['legality']['issues']))
        self.assertFalse(result['accepted_by_all'])
        self.assertEqual(original, before)

    def test_extension_terms_and_yearly_salaries_do_not_get_truncated(self):
        active = {**self.canonical, "contracts": deepcopy(self.canonical["contracts"])}
        active.pop("_contracts_by_player_id", None)
        contract = next(row for row in active["contracts"] if row["player_id"] == self.player["id"])
        contract["seasons"] = [{"season": "2026-27", "salary": 15_000_000},
                               {"season": "2027-28", "salary": 17_000_000},
                               *[{"season": f"{year}-{str(year + 1)[-2:]}", "salary": 22_000_000 + offset * 2_000_000,
                                  "guarantee_status": "extension"} for offset, year in enumerate(range(2028, 2032))]]
        contract["_active_season"] = "2026-27"
        result = enhance_trade_candidate(active, self.candidate(), save=self.save)
        asset = result["proposal"]["from_assets"][0]
        self.assertEqual([row["years"] for row in asset["contract_terms"]], [2, 4])
        self.assertEqual(len(asset["salary_by_year"]), 6)
        self.assertEqual(asset["salary_by_year"]["2031-32"], 28.0)
        self.assertEqual(asset["salary_millions"], 15.0)

    def test_batch_caches_evidence_and_returned_offers_have_independent_objects(self):
        context = trade_presentation_context(self.canonical, self.save)
        with patch("nba_gm_data.app_actions.player_display_attribute_summary", wraps=player_display_attribute_summary) as ratings:
            first = enhance_trade_candidate(self.canonical, self.candidate(), save=self.save, context=context)
            second = enhance_trade_candidate(self.canonical, self.candidate(), save=self.save, context=context)
        self.assertEqual(ratings.call_count, 2)
        self.assertEqual(len(context["team_caps"]), 2)
        first["proposal"]["from_assets"][0]["ratings"]["overall"] = 0
        self.assertGreater(second["proposal"]["from_assets"][0]["ratings"]["overall"], 0)

    def test_pick_conditions_and_original_team_identity_are_current(self):
        pick = next(row for row in self.canonical["draft_picks"] if pick_obligation_context_note(self.canonical, row))
        candidate = self.candidate([{"kind": "pick", "id": pick["id"], "label": "Stale label"}], [])
        result = enhance_trade_candidate(self.canonical, candidate, save=self.save)
        asset = result["proposal"]["from_assets"][0]
        self.assertEqual(asset["label"], pick_display_label(self.canonical, pick))
        self.assertEqual(asset["condition_summary"], pick_obligation_context_note(self.canonical, pick))
        self.assertEqual(asset["original_team_id"], pick["original_team_id"])
        self.assertEqual(asset["round"], pick["round"])
        self.assertTrue(asset["original_team_abbrev"])

    def test_empty_and_missing_assets_do_not_fabricate_financial_evidence(self):
        empty = enhance_trade_candidate(self.canonical, self.candidate([], []), save=self.save)
        self.assertFalse(empty["proposal"]["from_assets"])
        self.assertEqual(empty["team_finances"][self.user["id"]]["outgoing_salary_millions"], 0)
        missing = enhance_trade_candidate(self.canonical, self.candidate([{"kind": "player", "id": "missing"}], []), save=self.save)
        self.assertNotIn("headshot_url", missing["proposal"]["from_assets"][0])
        self.assertIsNone(missing["team_finances"][self.user["id"]]["outgoing_salary_millions"])
        self.assertIsNone(missing["team_finances"][self.user["id"]]["payroll_after_millions"])

    def test_crowded_packages_keep_all_assets_and_evidence(self):
        outgoing = [{"kind": "player", "id": row["id"]} for row in self.canonical["players"] if row["team_id"] == self.user["id"]]
        incoming = [{"kind": "player", "id": row["id"]} for row in self.canonical["players"] if row["team_id"] == self.partner["id"]]
        outgoing += [{"kind": "pick", "id": row["id"]} for row in self.canonical["draft_picks"] if row["current_owner_team_id"] == self.user["id"]][:3]
        result = enhance_trade_candidate(self.canonical, self.candidate(outgoing, incoming), save=self.save)
        self.assertGreater(len(outgoing), 15)
        self.assertEqual(len(result["proposal"]["from_assets"]), len(outgoing))
        self.assertEqual(len(result["proposal"]["to_assets"]), len(incoming))
        for asset in [*result["proposal"]["from_assets"], *result["proposal"]["to_assets"]]:
            self.assertIn("label", asset)
            if asset["kind"] == "player":
                self.assertIn("health_risk", asset)
                self.assertIn("salary_by_year", asset)
                self.assertIn("headshot_url", asset)

    def test_inbox_projects_only_pending_offers_without_mutating_saved_proposals(self):
        pending = self.candidate()
        pending["offer_context"] = {"status": "pending_user_review"}
        rejected = deepcopy(pending)
        rejected["offer_context"]["status"] = "rejected_by_user"
        save = {**self.save, "user_trade_offers": [pending, rejected]}
        before = deepcopy(save)
        result = user_trade_offers_payload(self.canonical, Path("unused.json"), prepared_save=save, prepared_active=self.canonical)
        self.assertEqual(result["offer_count"], 1)
        self.assertIn("ratings", result["offers"][0]["proposal"]["from_assets"][0])
        self.assertIn("team_finances", result["offers"][0])
        self.assertEqual(save, before)

    def test_finder_buyer_scope_applies_before_package_generation_and_result_limit(self):
        # Instrument package generation to prove a team scope avoids scanning
        # the rest of the league, even when the global result limit is one.
        player = next(row for row in self.canonical["players"] if row["name"] == "Seth Curry")
        calls = []

        def packages(active, buyer, seller, value, salary, seed, selected, *, intent):
            self.assertEqual(intent.buyer_id,buyer['id'])
            self.assertEqual(intent.seller_id,seller['id'])
            self.assertEqual({a['id'] for a in intent.target_assets},selected)
            calls.append(buyer["id"])
            return []

        with patch("nba_gm_data.transactions.buyer_teams_for_asset_package", return_value=[self.user, self.partner]), \
             patch("nba_gm_data.transactions.buyer_offer_packages_for_value", side_effect=packages):
            result = find_trade_for_assets(self.canonical, "GSW", [{"kind": "player", "id": player["id"]}], "GSW", limit=1, buyer_team="LAL")
        self.assertEqual(calls, [self.partner["id"]])
        self.assertEqual(result["buyer_team"]["id"], self.partner["id"])
        self.assertEqual(result["mode"], "shop_package")
        self.assertEqual(result["candidate_count"], 0)
        empty = find_trade_for_assets(self.canonical, "GSW", [], "GSW", buyer_team="LAL")
        self.assertEqual(empty["mode"], "empty_package")
        self.assertEqual(empty["buyer_team"]["id"], self.partner["id"])

    def test_scoped_finder_returns_executable_counterparty_approved_offers(self):
        player = next(row for row in self.canonical["players"] if row["name"] == "Moses Moody")
        assets = [{"kind": "player", "id": player["id"]}]
        league = find_trade_for_assets(self.canonical, "GSW", assets, "GSW", limit=1, seed=2)
        self.assertTrue(league["candidates"])
        buyer_id = league["candidates"][0]["proposal"]["to_team_id"]
        scoped = find_trade_for_assets(self.canonical, "GSW", assets, "GSW", limit=3, seed=2, buyer_team=buyer_id)
        self.assertTrue(scoped["candidates"])
        for candidate in scoped["candidates"]:
            self.assertEqual(candidate["proposal"]["to_team_id"], buyer_id)
            self.assertEqual(candidate["legality"]["status"], "legal")
            counterparty = next(row for row in candidate["evaluations"] if row["perspective_team_id"] == buyer_id)
            self.assertTrue(counterparty["accepted"])

    def test_finder_does_not_return_executable_offers_for_an_expired_contract(self):
        player = next(row for row in self.canonical['players'] if row['name'] == 'Moses Moody')
        active = {**self.canonical, 'contracts': deepcopy(self.canonical['contracts'])}
        active.pop('_contracts_by_player_id', None)
        contract = next(c for c in active['contracts'] if c['player_id'] == player['id'])
        contract['seasons'] = [{'season': '2025-26', 'salary': 1_000_000}]
        contract['_active_season'] = '2026-27'
        result = find_trade_for_assets(active, 'GSW', [{'kind': 'player', 'id': player['id']}], 'GSW', seed=2)
        self.assertEqual(result['candidates'], [])


if __name__ == "__main__":
    unittest.main()


class ContractSummaryTests(unittest.TestCase):
    def test_current_term_and_extension_use_compact_remaining_years(self):
        contract = {"seasons": [
            {"season": "2025-26", "salary": 7_000_000},
            {"season": "2026-27", "salary": 8_000_000},
            {"season": "2027-28", "salary": 30_000_000, "guarantee_status": "extension"},
            {"season": "2028-29", "salary": 32_000_000, "guarantee_status": "extension"},
        ]}
        self.assertEqual(contract_summary(contract, "2026-27"), "$8.0M x 1, $30.0M x 2")
        self.assertEqual(contract_summary(contract, "2028-29"), "$32.0M x 1")

    def test_ordinary_annual_raises_remain_one_contract_with_full_term(self):
        contract = {"seasons": [{"season": f"202{index}-2{index+1}", "salary": (10+index)*1_000_000} for index in range(6, 9)]}
        self.assertEqual(contract_summary(contract, "2026-27"), "$16.0M x 3")
        self.assertEqual(contract_summary(None), "")
