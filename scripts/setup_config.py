"""Staged local onboarding. AI recommends; the user confirms each stage."""
import argparse
import json
import os
from pathlib import Path
from common.job_scoring import load_resume_text, contains

def strings(value):
    return isinstance(value, list) and bool(value) and all(isinstance(s, str) and s.strip() for s in value)

def validate_profile(plan, cv):
    if not strings(plan.get('keywords')):
        raise ValueError('keywords must be a nonempty string list')
    p = plan.get('scoring', {})
    if not strings(p.get('title_terms')) or not isinstance(p.get('skills'), list) or not p['skills']:
        raise ValueError('scoring needs title_terms and skills')
    for s in p['skills']:
        if not isinstance(s.get('label'), str) or not s['label'].strip() or not strings(s.get('terms')):
            raise ValueError('Each skill needs label and terms')
        if type(s.get('weight')) not in (int, float) or not 0 < s['weight'] <= 10:
            raise ValueError('Skill weight must be in (0, 10]')
        if not isinstance(s.get('evidence'), str) or not s['evidence'].strip() or not contains(s['evidence'], cv):
            raise ValueError('Every skill needs an exact evidence excerpt from the CV')
    for key in ('required_any', 'excluded_title_terms'):
        if key in p and p[key] != [] and not strings(p[key]):
            raise ValueError(f'{key} must be a string list')
    if type(p.get('min_score', 55)) is not int or not 0 <= p.get('min_score', 55) <= 100:
        raise ValueError('min_score must be an integer from 0 to 100')

def validate_config(c):
    cv = load_resume_text(c['resume_path'])
    if not cv.strip():
        raise ValueError('CV has no text; OCR scanned PDFs first')
    validate_profile({'keywords': c['search']['keywords'], 'scoring': c['scoring']}, cv)
    if c.get('onboarding', {}).get('stage') != 'ready':
        raise ValueError('Confirm countries before searching')
    if not strings(c.get('preferred_countries')) or not c.get('html_tracker'):
        raise ValueError('Missing countries or html_tracker')

def save(path, config):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8') as f:
        if os.name != 'nt':
            os.chmod(temp, 0o600)
        json.dump(config, f, ensure_ascii=False, indent=2)
    temp.replace(path)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='~/.config/job-hunter/config.json')
    commands = parser.add_subparsers(dest='command', required=True)
    scan = commands.add_parser('scan')
    scan.add_argument('--resume', required=True)
    profile = commands.add_parser('profile')
    profile.add_argument('--resume', required=True)
    profile.add_argument('--proposal', required=True)
    profile.add_argument('--confirmed', action='store_true', required=True)
    countries = commands.add_parser('countries')
    countries.add_argument('--countries', nargs='+', required=True)
    countries.add_argument('--tracker', required=True)
    countries.add_argument('--confirmed', action='store_true', required=True)
    commands.add_parser('validate')
    args = parser.parse_args()
    path = Path(args.config).expanduser().resolve()
    try:
        if args.command == 'scan':
            text = load_resume_text(args.resume)
            if not text.strip():
                raise ValueError('CV has no text; OCR scanned PDFs first')
            print(text)
            return
        c = json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
        if args.command == 'profile':
            cv = load_resume_text(args.resume)
            plan = json.loads(Path(args.proposal).expanduser().read_text(encoding='utf-8-sig'))
            validate_profile(plan, cv)
            c['resume_path'] = str(Path(args.resume).expanduser().resolve())
            c['scoring'] = plan['scoring']
            c.setdefault('search', {})['keywords'] = plan['keywords']
            for k, v in dict(time_range='week', remote=False, max_results_per_query=20,
                             job_domains=['linkedin.com', 'indeed.com']).items():
                c['search'].setdefault(k, v)
            c['onboarding'] = {'stage': 'countries_pending'}
            save(path, c)
            print('Keywords saved. Present countries and obtain user confirmation next.')
        elif args.command == 'countries':
            if c.get('onboarding', {}).get('stage') not in ('countries_pending', 'ready'):
                raise ValueError('Confirm CV keyword proposal first')
            from jobspy_scraper import LOCATION_TO_COUNTRY_INDEED
            names = {n.casefold(): n.title() for n in LOCATION_TO_COUNTRY_INDEED}
            selected = []
            for name in args.countries:
                if name.casefold() not in names:
                    raise ValueError(f'Country not mapped: {name}. Choose from documented country list.')
                if names[name.casefold()] not in selected:
                    selected.append(names[name.casefold()])
            c['preferred_countries'] = selected
            c['html_tracker'] = str(Path(args.tracker).expanduser().resolve())
            c['search']['location'] = selected[0]
            c['onboarding'] = {'stage': 'ready'}
            validate_config(c)
            save(path, c)
            print(f'Ready. Configuration: {path}')
        else:
            validate_config(c)
            print('Configuration valid')
    except (ValueError, KeyError, OSError, TypeError) as exc:
        parser.error(str(exc))

if __name__ == '__main__':
    main()
