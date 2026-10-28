"""Offline behavior checks using fictional CV and job data only."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common.dedup import deduplicate_jobs
from common.job_scoring import score_jobs
from generate_html_tracker import count_existing_rows, render_row
from setup_config import validate_profile

class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.cv = self.base / 'cv.txt'
        self.cv.write_text('Fictional candidate: Python and SQL reporting.', encoding='utf-8')
        self.config = self.base / 'config.json'
        self.proposal = self.base / 'proposal.json'
        self.plan = {'keywords': ['data analyst'], 'scoring': {
            'title_terms': ['analyst'], 'skills': [
                {'label': 'Python', 'terms': ['Python'], 'weight': 6, 'evidence': 'Python'},
                {'label': 'SQL', 'terms': ['SQL'], 'weight': 4, 'evidence': 'SQL'}],
            'min_score': 55, 'required_any': [], 'excluded_title_terms': []}}
        self.proposal.write_text(json.dumps(self.plan), encoding='utf-8')

    def run_script(self, name, *args, ok=True):
        proc = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts' / name),
                               *map(str, args)], capture_output=True, text=True, encoding='utf-8')
        if ok:
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        else:
            self.assertNotEqual(proc.returncode, 0)
        return proc

    def profile(self):
        self.run_script('setup_config.py', '--config', self.config, 'profile', '--resume', self.cv,
                        '--proposal', self.proposal, '--confirmed')

    def ready(self):
        self.profile()
        self.run_script('setup_config.py', '--config', self.config, 'countries', '--countries',
                        'Belgium', 'United Kingdom', '--tracker', self.base / 'Job Tracker.html', '--confirmed')

    def test_confirmation_gates_and_preservation(self):
        self.run_script('setup_config.py', '--config', self.config, 'profile', '--resume', self.cv,
                        '--proposal', self.proposal, ok=False)
        self.assertFalse(self.config.exists())
        self.profile()
        self.run_script('daily_job_hunt.py', '--config', self.config, '--check', ok=False)
        self.ready()
        c = json.loads(self.config.read_text())
        c['jsearch_api_key'] = 'fictional-test-value'
        self.config.write_text(json.dumps(c))
        self.profile()
        c = json.loads(self.config.read_text())
        self.assertEqual(c['jsearch_api_key'], 'fictional-test-value')
        self.assertEqual(c['onboarding']['stage'], 'countries_pending')
        self.run_script('setup_config.py', '--config', self.config, 'countries', '--countries',
                        'Atlantis', '--tracker', self.base / 'tracker.html', '--confirmed', ok=False)

    def test_evidence_and_generic_scoring(self):
        self.plan['scoring']['skills'][0]['evidence'] = 'Invented experience'
        with self.assertRaises(ValueError):
            validate_profile(self.plan, self.cv.read_text())
        self.plan['scoring']['skills'][0]['evidence'] = 'Python'
        jobs = [{'title': 'Data Analyst', 'description': 'Python SQL, no degree required'},
                {'title': 'Optical Engineer', 'description': 'Optical metrology PhD'}]
        scored = score_jobs(jobs, resume_path=str(self.cv), profile=self.plan['scoring'])
        self.assertEqual([j['match_score'] for j in scored], [100, 0])

    def test_persistent_pipeline(self):
        self.ready()
        job = {'title': 'Data Analyst', 'company': 'Fictional A', 'location': 'Belgium',
               'description': 'Python SQL reporting.', 'url': 'https://example.com/a', 'source': 'linkedin'}
        other = dict(job, company='Fictional B', url='https://example.com/b')
        raw = self.base / 'jobs.json'
        raw.write_text(json.dumps([job, job, other]))
        out = self.base / 'out'
        self.run_script('daily_job_hunt.py', '--config', self.config, '--input', raw, '--output-dir', out)
        selection = out / '.job-hunter-last-selection.json'
        self.assertEqual(len(json.loads(selection.read_text())), 2)
        report = next((out / 'JD Reports').glob('*.md'))
        self.assertIn('Fictional candidate', report.read_text(encoding='utf-8'))
        self.run_script('generate_cover_letters.py', '--config', self.config, '--jobs', selection,
                        '--indices', '2', '--output-dir', self.base / 'letters')
        self.assertEqual(len(list((self.base / 'letters').rglob('*.md'))), 1)
        self.run_script('daily_job_hunt.py', '--config', self.config, '--input', raw, '--output-dir', out)
        self.assertEqual(count_existing_rows((out / 'Job Tracker.html').read_text(encoding='utf-8')), 2)
        self.assertEqual(json.loads(selection.read_text()), [])
        self.assertIn('Fictional A', report.read_text(encoding='utf-8'))
        raw.write_text(json.dumps([dict(job, company='Fictional C', url='https://example.com/c')]))
        self.run_script('daily_job_hunt.py', '--config', self.config, '--input', raw, '--output-dir', out)
        self.assertEqual(len(json.loads(selection.read_text())), 1)
        report_text = report.read_text(encoding='utf-8')
        self.assertTrue(all(name in report_text for name in ('Fictional A', 'Fictional B', 'Fictional C')))

    def test_dedup_without_urls_and_safe_links(self):
        jobs = [{'title': 'Analyst', 'company': name, 'location': 'Belgium'} for name in ('A', 'B')]
        self.assertEqual(len(deduplicate_jobs(jobs)), 2)
        self.assertNotIn('javascript:', render_row(1, {'title': '<script>', 'url': 'javascript:alert(1)'}))
        self.assertIn('&lt;script&gt;', render_row(1, {'title': '<script>'}))

    def test_jsearch_failure_propagates(self):
        import jsearch_scraper
        class Response:
            status_code = 503
        with patch('httpx.Client.get', return_value=Response()):
            with self.assertRaises(RuntimeError):
                jsearch_scraper.search_jobs('fictional', 'analyst')

if __name__ == '__main__':
    unittest.main()
