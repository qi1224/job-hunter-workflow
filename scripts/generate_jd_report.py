#!/usr/bin/env python3
"""
Generate a Markdown JD report of the jobs added to the HTML tracker in one run.

The report is self-contained and meant to be handed directly to an AI for a
detailed, job-by-job fit analysis: it starts with analysis instructions, then the
candidate's CV text, then every new job with full metadata and the full JD.

"New jobs" = tracker rows whose data-batch equals --batch (default: today), which is
exactly what generate_html_tracker.py appended in that run.

Usage:
    python generate_jd_report.py --scored ~/.job-hunter-last-scored.json \
        --tracker ".../Job Tracker.html" --output-dir ".../JD Reports" --config config.json
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common.job_scoring import load_resume_text  # noqa: E402

ANALYSIS_PROMPT = """\
## Instructions for the AI reviewer

You are an experienced technical recruiter and career advisor. Below are (1) my CV and
(2) {n} job postings found by my automated job search on {batch}. Analyse **every job
in order, one by one**. For each job give:

1. **Fit score (0-100)** and a one-line verdict (Strong / Good / Partial / Poor fit).
2. **Requirement-by-requirement match**: list each key requirement in the JD
   (education, years of experience, technical skills, tools, domain, languages) and
   mark it as met / partially met / not met, citing the concrete CV evidence.
3. **Strengths** I should emphasise in the application.
4. **Gaps and risks** (missing skills, seniority mismatch, language or visa issues,
   location) and how to mitigate them.
5. **Recommendation**: Apply / Apply with tailoring / Skip, plus 2-3 specific tailoring
   tips for the CV or cover letter.

After all jobs, give a **ranked summary table** (rank, job #, title, company, fit
score, recommendation) and name the top 3 jobs to prioritise.

Note: the "Keyword score" in each job is an automated keyword-match score, not a
real fit assessment. Do your own independent judgement.
"""


def read_resume(resume_path: str) -> str:
    """CV text with line structure kept (the scoring loader flattens it to one line)."""
    path = Path(resume_path).expanduser()
    if path.suffix.lower() != '.docx' or not path.exists():
        return load_resume_text(resume_path)
    from docx import Document
    doc = Document(str(path))
    lines, seen_cells = [p.text for p in doc.paragraphs], set()
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell._tc in seen_cells:  # merged cells repeat across the row
                    continue
                seen_cells.add(cell._tc)
                lines.extend(p.text for p in cell.paragraphs)
    text = '\n'.join(l.strip() for l in lines)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def clean_description(text: str) -> str:
    """Undo JobSpy's markdown escaping and squeeze blank lines."""
    text = re.sub(r'\\([\\`*_{}\[\]()#+\-.!|>~&])', r'\1', text or '')
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def batch_ids(tracker_html: str, batch: str) -> list[str]:
    """Tracker row ids appended in the given batch, in tracker order."""
    return re.findall(rf'<tr[^>]+data-id="([^"]+)"[^>]*data-batch="{re.escape(batch)}"', tracker_html)


def render_job(i: int, job: dict) -> str:
    def field(v):
        s = str(v).strip() if v is not None else ''
        return s if s and s.lower() != 'nan' else '-'

    lines = [
        f'### Job {i}: {field(job.get("title"))} — {field(job.get("company"))}',
        '',
        '| Field | Value |',
        '|---|---|',
        f'| Job title | {field(job.get("title"))} |',
        f'| Company | {field(job.get("company"))} |',
        f'| Location | {field(job.get("location"))} |',
        f'| Remote | {"Yes" if job.get("remote") else "No"} |',
        f'| Employment type | {field(job.get("employment_type"))} |',
        f'| Experience level | {field(job.get("experience_level"))} |',
        f'| Salary | {field(job.get("salary"))} |',
        f'| Posted | {field(job.get("posted_date"))} |',
        f'| Source | {field(job.get("source")).capitalize()} |',
        f'| Link | {field(job.get("url"))} |',
        f'| Keyword score | {job.get("match_score", "-")} ({field(job.get("match_reason"))}) |',
        '',
        '#### Job description',
        '',
        clean_description(job.get('description')) or '_No description available._',
        '',
        '---',
        '',
    ]
    return '\n'.join(lines)


def build_report(jobs: list[dict], batch: str, resume_text: str) -> str:
    parts = [
        f'# Job Search Report — {batch}',
        '',
        f'{len(jobs)} new jobs added to the tracker in this run.',
        '',
        ANALYSIS_PROMPT.format(n=len(jobs), batch=batch),
        '## Candidate CV',
        '',
        resume_text.strip() if resume_text.strip() else '_CV text unavailable — attach the CV separately._',
        '',
        '---',
        '',
        '## Job overview',
        '',
        '| # | Title | Company | Location | Keyword score |',
        '|---|---|---|---|---|',
    ]
    for i, j in enumerate(jobs, 1):
        parts.append(f'| {i} | {j.get("title", "-")} | {j.get("company") or "-"} | '
                     f'{j.get("location") or "-"} | {j.get("match_score", "-")} |')
    parts += ['', '## Job postings', '']
    parts += [render_job(i, j) for i, j in enumerate(jobs, 1)]
    return '\n'.join(parts)


def main():
    parser = argparse.ArgumentParser(description='Generate a Markdown JD report for AI fit analysis')
    parser.add_argument('--scored', '-i', required=True, help='Scored jobs JSON from this run')
    parser.add_argument('--tracker', required=True, help='HTML tracker path (used to find this batch\'s new rows)')
    parser.add_argument('--output-dir', '-o', required=True, help='Folder to write the report into')
    parser.add_argument('--config', help='Job-hunter config.json (for resume_path)')
    parser.add_argument('--batch', default=date.today().isoformat(), help='Batch date (default: today)')
    parser.add_argument('--no-resume', action='store_true', help='Do not embed CV text in the report')
    args = parser.parse_args()

    jobs = json.loads(Path(args.scored).read_text(encoding='utf-8'))
    tracker = Path(args.tracker)
    if not tracker.exists():
        print(f'Tracker not found: {tracker}')
        return
    out_dir = Path(args.output_dir)
    out_path = out_dir / f'Job Report - {args.batch}.md'
    # Sidecar keeps the batch's job dicts so a second run on the same day (whose scored JSON
    # only holds that run's jobs) still reports everything added that day.
    sidecar = out_dir / f'Job Report - {args.batch}.jobs.json'

    ids = batch_ids(tracker.read_text(encoding='utf-8'), args.batch)
    by_id = {}
    if sidecar.exists():
        by_id.update({j.get('id'): j for j in json.loads(sidecar.read_text(encoding='utf-8'))})
    by_id.update({j.get('id'): j for j in jobs})
    selected = [by_id[i] for i in ids if i in by_id]
    selected.sort(key=lambda j: j.get('match_score', 0), reverse=True)
    missing = len(ids) - len(selected)

    if not selected:
        print(f'JD report: no new jobs in batch {args.batch}, nothing written')
        return

    resume_text = ''
    if args.config and not args.no_resume:
        cfg = json.loads(Path(args.config).read_text(encoding='utf-8'))
        resume_text = read_resume(cfg.get('resume_path', ''))

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_report(selected, args.batch, resume_text), encoding='utf-8')
    sidecar.write_text(json.dumps(selected, indent=1, default=str), encoding='utf-8')

    note = f' ({missing} batch rows not in scored JSON, skipped)' if missing else ''
    print(f'JD report: {len(selected)} jobs written{note}')
    print(f'Output: {out_path}')


if __name__ == '__main__':
    main()
