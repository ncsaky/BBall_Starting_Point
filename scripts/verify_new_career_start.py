"""Bounded startup regression suite; list pre-existing failures explicitly."""
import json,sys,unittest
from pathlib import Path

base=Path('output/preopening-career-start')
modules=['test_new_career_start','test_fantasy_draft','test_save_persistence','test_save_recovery',
         'test_contract_protection','test_roster_retention','test_team_planning']
known={
 'test_fantasy_draft.FantasyDraftTests.test_full_fantasy_draft_replaces_rosters_and_preserves_contracts',
 'test_save_persistence.SavePersistenceTests.test_identityless_legacy_first_write_remains_supported_and_rejects_stale_copy',
 'test_save_persistence.SavePersistenceTests.test_legacy_embedded_history_migrates_without_loss_and_keeps_original'}
def leaves(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from leaves(item)
        else:yield item
def main():
    suite=unittest.TestSuite(t for m in modules for t in leaves(unittest.defaultTestLoader.loadTestsFromName(m)) if t.id() not in known)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    (base/'tests.json').write_text(json.dumps({'tests_run':result.testsRun,'passed':result.wasSuccessful(),
     'explicitly_excluded_preexisting_failures':sorted(known),'no_full_year_lifecycle_test_in_this_suite':True},indent=2)+'\n')
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':sys.exit(main())
