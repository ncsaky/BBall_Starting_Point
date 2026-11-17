import unittest

from review_rotation_comparison import floor_decomposition, retained_cohort, roster_metrics, season_metrics


class RotationComparisonReviewTests(unittest.TestCase):
    def row(self,pid,rating=50,rostered=True,age=28):
        return {'id':pid,'name':pid,'fixed24_engine':rating,'rostered':rostered,'age':age}

    def snap(self,rows):
        return {'date':'2028-04-12','players':rows,'regular_games':1230,'retired_count':0,
                'league_exit_count':0,'roster_counts_by_team':{'team_a':len(rows)}}

    def test_retention_uses_initial_rostered_cohort_not_all_records(self):
        a=self.snap([self.row('a'),self.row('b'),self.row('c',rostered=False)])
        b=self.snap([self.row('a',55),self.row('b',rostered=False),self.row('c')])
        r=retained_cohort(a,b,{'a','b','c'})
        self.assertEqual((r['initial_count'],r['retained_count'],r['retained_fraction']),(2,1,.5))
        self.assertEqual(r['lost_names'],['b'])

    def test_mean_identity_distinguishes_composition_from_continuing_growth(self):
        a=self.snap([self.row('a',40),self.row('b',60)])
        b=self.snap([self.row('a',45),self.row('c',70),self.row('d',55)])
        r=floor_decomposition(a,b)
        self.assertAlmostEqual(r['mean_change'],r['continuing_player_rating_component']+r['composition_residual'],places=3)
        self.assertEqual((r['entry_count'],r['departure_count']),(2,1))

    def test_roster_groups_do_not_count_free_agents_and_report_age_years(self):
        r=roster_metrics(self.snap([self.row('old'),self.row('new',age=21),self.row('fa',rostered=False)]),{'old','fa'})
        self.assertEqual((r['count'],r['imported_count'],r['generated_count']),(2,1,1))
        self.assertEqual(set(r['by_age']),{'21','28'})

    def test_season_minutes_use_actual_stats_and_keep_late_pick_without_rotation(self):
        snapshot=self.snap([self.row('old'),self.row('rookie')])
        stats={'old':{'games':40,'minutes':1200},'rookie':{'games':10,'minutes':50}}
        history={'season':'2027-28','player_season_stats':stats}
        metadata={'old':{'name':'old'},'rookie':{'name':'rookie','draft_position':40}}
        r=season_metrics(snapshot,history,metadata,{'old'},{'old'})
        self.assertEqual(r['groups']['generated_31+']['players_with_games'],1)
        self.assertEqual(r['groups']['generated_31+']['qualifying_rotation_count'],0)
        self.assertAlmostEqual(r['groups']['generated']['share_of_league_minutes'],.04)
        self.assertEqual(r['groups']['corrected_profiles']['qualifying_rotation_count'],1)

    def test_unknown_metadata_is_reported_not_silently_classified_as_generated(self):
        r=season_metrics(self.snap([]),{'season':'2027-28','player_season_stats':{'missing':{'games':2,'minutes':20}}},{},set(),set())
        self.assertEqual(r['unknown_player_metadata'],['missing'])


if __name__=='__main__':
    unittest.main()
