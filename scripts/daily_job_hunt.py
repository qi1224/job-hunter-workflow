#!/usr/bin/env python3
"""Cross-platform search, scoring, persistent tracker and JD report pipeline."""
import argparse
import json
import os
from datetime import date
from pathlib import Path
import subprocess
import sys

from common.config import load_config
from common.dedup import deduplicate_jobs
from common.job_scoring import load_resume_text, score_jobs
from generate_html_tracker import update_html_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='~/.config/job-hunter/config.json')
    parser.add_argument('--keywords', nargs='+')
    parser.add_argument('--location', help='Limit both providers to one location')
    parser.add_argument('--skip-jsearch', action='store_true')
    parser.add_argument('--input', help='Offline jobs JSON; makes no search requests')
    parser.add_argument('--output-dir', help='Isolate tracker, report, cache and state here')
    parser.add_argument('--check', action='store_true', help='Validate configuration/dependencies without searching')
    args = parser.parse_args()
    config_path = Path(args.config).expanduser().resolve()
    config = load_config(str(config_path))
    from setup_config import validate_config
    validate_config(config)
    resume = config.get('resume_path', '')
    if not resume or not load_resume_text(resume).strip():
        parser.error('Configured resume is missing, empty or unreadable')
    if not args.output_dir and not config.get('html_tracker'):
        parser.error('Configure html_tracker or pass --output-dir')
    tracker = (Path(args.output_dir).expanduser().resolve() / 'Job Tracker.html'
               if args.output_dir else Path(config['html_tracker']).expanduser().resolve())
    state_dir = tracker.parent if args.output_dir else Path.home()
    cache = state_dir / '.job-hunter-last-scored.json'
    selection = state_dir / '.job-hunter-last-selection.json'
    state = state_dir / '.job-hunter-jsearch-last-run'
    if args.check:
        import jobspy, httpx, dateutil  # noqa: F401
        print(f'Configuration, dependencies and resume OK. Tracker: {tracker}')
        return
    if args.input:
        jobs = json.loads(Path(args.input).expanduser().read_text(encoding='utf-8-sig'))
    else:
        from jobspy_scraper import scrape_jobs
        from jsearch_scraper import scrape_jobs as jsearch
        # Use the actual output tracker for seen-job suppression during isolated runs.
        config['html_tracker'] = str(tracker)
        countries = ([args.location] if args.location else
                     config.get('preferred_countries') or [config.get('search', {}).get('location', '')])
        jobs = []
        for country in countries:
            jobs.extend(scrape_jobs(config, keywords=args.keywords, location=country))
        elapsed = 999
        if state.exists():
            try:
                elapsed = (date.today() - date.fromisoformat(state.read_text(encoding='utf-8').strip())).days
            except ValueError:
                pass
        if not args.skip_jsearch and config.get('jsearch_api_key') and elapsed >= 14:
            # A failed supplemental provider must not discard completed JobSpy results.
            try:
                extra = jsearch(config, keywords=args.keywords, location=args.location)
            except (Exception, SystemExit) as exc:
                print(f'WARNING: JSearch failed; keeping JobSpy results ({exc})', file=sys.stderr)
            else:
                jobs.extend(extra)
                state.parent.mkdir(parents=True, exist_ok=True)
                state.write_text(date.today().isoformat(), encoding='utf-8')
        else:
            print('JSearch skipped (disabled, no key, or 14-day interval not reached)')
    scored = score_jobs(deduplicate_jobs(jobs), resume_path=resume,
                        preferred_countries=config.get('preferred_countries', []), profile=config['scoring'])
    tracker.parent.mkdir(parents=True, exist_ok=True)
    existing = tracker.read_text(encoding='utf-8') if tracker.exists() else ''
    from generate_html_tracker import extract_existing_ids
    seen = extract_existing_ids(existing)
    threshold = config['scoring'].get('min_score', 55)
    added, total = update_html_file(tracker, scored, min_score=threshold)
    selected = sorted((j for j in scored if j.get('match_score', 0) >= threshold and j.get('id') not in seen),
                      key=lambda j: j['match_score'], reverse=True)
    cache.write_text(json.dumps(scored, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    selection.write_text(json.dumps(selected, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    report_dir = tracker.parent / 'JD Reports'
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__).with_name('generate_jd_report.py')),
                    '--scored', str(cache), '--tracker', str(tracker), '--output-dir', str(report_dir),
                    '--config', str(config_path)], check=True, env=env)
    print(f'Added {added} new jobs ({total} total). Tracker: {tracker}')
    print(f'JD report directory: {report_dir}')
    print(f'Numbered selection JSON: {selection}')
    for i, job in enumerate(selected, 1):
        print(f"{i}. [{job['match_score']}] {job.get('title')} | {job.get('company')} | {job.get('location')}")


if __name__ == '__main__':
    main()
