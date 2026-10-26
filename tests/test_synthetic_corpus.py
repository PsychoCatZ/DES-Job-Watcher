from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from des_job_watcher.evaluation_run import prepare_cases
from des_job_watcher.prompting import ROOT
from examples import prepare_analysis


MANIFEST = ROOT / 'examples/fixtures/evaluation/cases.json'
DEMO_PROFILES = ROOT / 'config/profile_examples'


class SyntheticCorpusTests(unittest.TestCase):
    def test_corpus_sources_and_explicit_profiles_prepare_without_private_data(self):
        # Отсутствие личной папки не должно мешать явно выбранным учебным профилям.
        with patch.object(prepare_analysis, 'PROFILE_DIR', ROOT / 'tmp/nonexistent-private-profiles'):
            dataset, jobs = prepare_cases(MANIFEST, profile_dir=DEMO_PROFILES)
        self.assertEqual(len(jobs), 9)
        self.assertEqual({job['payload']['profile']['profile_id'] for job in jobs},
                         {'support', 'developer', 'ai_data'})
        for job in jobs:
            self.assertIn('DEMO', job['payload']['profile']['label'])
            self.assertEqual(job['payload']['profile']['version'], 1)
            self.assertNotIn('checks', job['payload'])

    def test_explicit_missing_profile_directory_does_not_fall_back_to_personal_profile(self):
        (ROOT / 'tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / 'tmp') as temporary:
            with self.assertRaisesRegex(ValueError, 'профиль отсутствует'):
                prepare_cases(MANIFEST, ['demo_developer'], profile_dir=Path(temporary))

    def test_selected_case_prepares_only_one_call(self):
        _, jobs = prepare_cases(MANIFEST, ['demo_video'], profile_dir=DEMO_PROFILES)
        self.assertEqual([job['case']['id'] for job in jobs], ['demo_video'])


if __name__ == '__main__':
    unittest.main()
