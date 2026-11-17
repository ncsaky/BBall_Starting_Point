from copy import deepcopy
import unittest

from scripts.audit_replacement_calibration import profile_rows, stamina_diagnostic, position_standardized


class ReplacementCalibrationAuditTests(unittest.TestCase):
    def trait(self, pieces, value):
        return {"trait_key":"stamina_cardio","value":value,"components":{"components":pieces}}

    def test_zero_role_bonus_is_an_observation_in_old_arithmetic(self):
        trait = self.trait([60,30,0],30)
        self.assertEqual(stamina_diagnostic(trait),45)

    def test_bonus_is_additive_in_diagnostic_and_missing_workload_is_not_zero(self):
        self.assertEqual(stamina_diagnostic(self.trait([60,None,8],34)),68)
        self.assertIsNone(stamina_diagnostic(self.trait([None,None,0],0)))

    def test_reviewed_values_and_unreconciled_components_are_not_rewritten(self):
        for key in ('manual_calibration','roster_alignment','imported_rookie_prior','league_trait_rating_calibration'):
            trait = self.trait([60,30,0],30)
            trait['components'][key] = {}
            self.assertIsNone(stamina_diagnostic(trait))
        self.assertIsNone(stamina_diagnostic(self.trait([60,30,0],50)))

    def test_position_standardization_uses_reference_mix(self):
        reference = [{'position':'C','overall':60},{'position':'C','overall':70},{'position':'PG','overall':80}]
        comparison = [{'position':'C','overall':60},{'position':'PG','overall':90}]
        result = position_standardized(reference,comparison)
        self.assertEqual(result['reference_mean'],70)
        self.assertEqual(result['comparison_mean_at_reference_position_mix'],70)

    def test_fixed_minutes_comparison_preserves_inputs_and_ignores_source_workload(self):
        context = {'meta':{'talent_model_version':2},'players':[
            {'id':'a','name':'A','position':'C','minutes_projection':0},
            {'id':'b','name':'B','position':'C','minutes_projection':36}],
            'traits':[{'player_id':pid,'trait_key':key,'value':50} for pid in ('a','b')
                      for key in ('stamina_cardio','shooting_range','rim_deterrence','shot_versatility')]}
        before = deepcopy(context)
        rows = profile_rows(context)
        self.assertEqual(rows[0]['overall'],rows[1]['overall'])
        self.assertEqual(rows[0]['impact'],rows[1]['impact'])
        self.assertEqual(context,before)


if __name__ == '__main__':
    unittest.main()
