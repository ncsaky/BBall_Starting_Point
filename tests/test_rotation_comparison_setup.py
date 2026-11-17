import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from compare_rotation_profiles import VERSION, candidate_archive, read_gzip, sha
from nba_gm_data.baselines import baseline_for_save


class RotationComparisonSetupTests(unittest.TestCase):
    def setup_runtime(self, root):
        directory=root/'data/canonical/baselines'
        directory.mkdir(parents=True)
        (directory/'registry.json').write_text(json.dumps({'legacy_version':'v7','versions':{'v7':'v7.json.gz'}}))
        with gzip.open(directory/'v7.json.gz','wt') as handle:
            json.dump({'meta':{'starting_data_version':'v7'}},handle)
        return directory

    def test_candidate_registration_is_local_repeatable_and_preserves_previous_archive(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);directory=self.setup_runtime(root)
            before=sha(directory/'v7.json.gz')
            candidate={'meta':{'starting_data_version':VERSION},'draft_picks':[]}
            first=candidate_archive(root,candidate)
            self.assertEqual(first,candidate_archive(root,candidate))
            self.assertEqual(before,sha(directory/'v7.json.gz'))
            self.assertEqual(candidate,read_gzip(directory/f'{VERSION}.json.gz'))
            self.assertEqual(json.loads((directory/'registry.json').read_text())['versions']['v7'],'v7.json.gz')

    def test_nested_default_canonical_can_resolve_the_unpublished_candidate(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);directory=self.setup_runtime(root)
            candidate={'meta':{'starting_data_version':VERSION},'draft_picks':[],'players':[]}
            candidate_archive(root,candidate)
            default={'meta':{'starting_data_version':'v7'},'_baseline_directory':str(directory)}
            saved={'version':'league_save_v1','meta':{'starting_data_version':VERSION}}
            resolved=baseline_for_save(default,saved)
            self.assertEqual(resolved['meta']['starting_data_version'],VERSION)


if __name__=='__main__':
    unittest.main()
