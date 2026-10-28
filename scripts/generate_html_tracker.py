#!/usr/bin/env python3
"""
Generate or update the HTML job tracker.

Each run appends only new job rows identified by data-id attribute.
Existing rows and their localStorage-backed status buttons are preserved.

Usage:
    python generate_html_tracker.py --scored /tmp/scored.json --output "path/to/Job Tracker.html"
    python generate_html_tracker.py --scored /tmp/scored.json --output "..." --min-score 60
"""

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

US_STATES = {
    'Alabama','Alaska','Arizona','Arkansas','California','Colorado','Connecticut',
    'Delaware','Florida','Georgia','Hawaii','Idaho','Illinois','Indiana','Iowa',
    'Kansas','Kentucky','Louisiana','Maine','Maryland','Massachusetts','Michigan',
    'Minnesota','Mississippi','Missouri','Montana','Nebraska','Nevada',
    'New Hampshire','New Jersey','New Mexico','New York','North Carolina',
    'North Dakota','Ohio','Oklahoma','Oregon','Pennsylvania','Rhode Island',
    'South Carolina','South Dakota','Tennessee','Texas','Utah','Vermont',
    'Virginia','Washington','West Virginia','Wisconsin','Wyoming',
    'District of Columbia',
}
_US_ABBR = re.compile(r',\s*([A-Z]{2})$')


def is_us(location: str) -> bool:
    if not location or location == '-':
        return False
    loc = location.strip()
    if any(x in loc for x in ('United States', ', US', ', U.S.', 'USA')):
        return True
    if _US_ABBR.search(loc):
        return True
    return any(st in loc for st in US_STATES)


def esc(s) -> str:
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def format_post_date(posted_str: str) -> str:
    if not posted_str:
        return '-'
    try:
        clean = posted_str.split('+')[0].rstrip('Z')
        d = (datetime.fromisoformat(clean).date() if 'T' in clean
             else date.fromisoformat(clean[:10]))
        delta = (date.today() - d).days
        label = 'Today' if delta == 0 else ('1d ago' if delta == 1 else f'{delta}d ago')
        return f'{d.strftime("%Y-%m-%d")} ({label})'
    except Exception:
        return posted_str[:10] if posted_str else '-'


def phd_prefer(desc: str) -> bool:
    text = (desc or '').lower()
    patterns = [
        'phd preferred', 'ph.d. preferred', 'phd required', 'ph.d. required',
        'phd or equivalent', 'doctorate preferred', 'doctoral preferred',
        'phd is preferred', 'candidates with phd', 'phd in ', 'ph.d. in ',
        'doctoral degree preferred', 'phd degree preferred',
    ]
    return any(p in text for p in patterns)


def score_class(score: int) -> str:
    if score >= 75:
        return 'score-high'
    if score >= 60:
        return 'score-mid'
    return 'score-low'


def extract_existing_ids(html_content: str) -> set[str]:
    return set(re.findall(r'<tr[^>]+data-id="([^"]+)"', html_content))


def count_existing_rows(html_content: str) -> int:
    return len(re.findall(r'<tr[^>]+data-id="', html_content))


def render_row(i: int, job: dict, batch: str = '') -> str:
    title   = esc(job.get('title', 'N/A'))[:80]
    company = esc(job.get('company') or '-')[:45]
    score   = job.get('match_score', 0)
    desc    = job.get('description') or ''
    phd     = phd_prefer(desc)
    remote  = 'Yes' if job.get('remote') else 'No'
    source  = esc((job.get('source') or '-').capitalize())
    raw_url = job.get('url') or '#'
    url = esc(raw_url if re.match(r'^https?://', raw_url, re.I) else '#')
    location = esc(job.get('location') or '-')[:55]
    post_date = format_post_date(job.get('posted_date', ''))
    job_id  = esc(job.get('id', ''))
    row_cls = 'us-job' if is_us(job.get('location', '')) else ''
    sc      = score_class(score)

    phd_html = ('<span class="phd-yes">PhD+</span>' if phd
                else '<span class="phd-no">-</span>')

    btns = ''.join(
        f'<button class="status-btn" data-s="{s}" '
        f'onclick="setStatus(\'{job_id}\',\'{s}\',this)">{label}</button>'
        for s, label in [
            ('applied',  'Applied ✅'),
            ('interview', 'Got Interview 🎉'),
            ('interview_rejected', 'Rejected After Interview 💔'),
            ('rejected', 'Rejected ❌'),
            ('dislike',  'Not Interested 👎'),
        ]
    )

    return (
        f'<tr data-id="{job_id}" data-batch="{batch}" class="{row_cls}">'
        f'<td>{i}</td>'
        f'<td><div class="status-btns">{btns}</div></td>'
        f'<td><span class="score {sc}">{score}</span></td>'
        f'<td>{title}</td>'
        f'<td>{company}</td>'
        f'<td>{location}</td>'
        f'<td class="nowrap">{post_date}</td>'
        f'<td>{phd_html}</td>'
        f'<td>{remote}</td>'
        f'<td>{source}</td>'
        f'<td><a href="{url}" target="_blank" rel="noopener noreferrer">Apply</a></td>'
        f'</tr>'
    )


_HTML_HEAD = '''\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Job Tracker</title>
<style>
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  margin:16px;font-size:13px;color:#222;background:#fafafa}
h1{margin:0 0 4px;font-size:20px}
.summary{color:#666;margin-bottom:10px;font-size:12px}
.controls{margin-bottom:10px;display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.filter-btn{padding:3px 10px;border:1px solid #ccc;border-radius:4px;
  cursor:pointer;font-size:12px;background:#fff}
.filter-btn.active{background:#1565c0;color:#fff;border-color:#1565c0}
input[type=text]{padding:4px 8px;border:1px solid #ccc;border-radius:4px;
  width:220px;font-size:12px;background:#fff}
.legend{color:#888;font-size:11px;margin-left:4px}
table{border-collapse:collapse;width:100%;background:#fff;
  box-shadow:0 1px 3px rgba(0,0,0,.1);border-radius:4px;overflow:hidden}
th{background:#f0f0f0;padding:6px 8px;text-align:left;
  border-bottom:2px solid #ddd;white-space:nowrap;
  cursor:pointer;user-select:none;font-size:12px}
th:hover{background:#e4e4e4}
td{padding:4px 8px;border-bottom:1px solid #eee;vertical-align:middle}
tr:last-child td{border-bottom:none}
tr.us-job>td{background-color:#f0f0f0}
tr[data-status=applied]>td{background-color:#c8e6c9!important}
tr[data-status=interview]>td{background-color:#b2dfdb!important}
tr[data-status=interview_rejected]>td{background-color:#e1bee7!important}
tr[data-status=rejected]>td{background-color:#ffcdd2!important}
tr[data-status=dislike]>td{opacity:.35}
tr[data-status=rejected],tr[data-status=interview_rejected]{text-decoration:line-through;
  text-decoration-color:#aaa}
.status-btns{display:flex;gap:2px;flex-wrap:nowrap}
.status-btn{padding:2px 5px;font-size:10px;border:1px solid #ccc;
  border-radius:3px;cursor:pointer;background:#fff;white-space:nowrap;
  transition:all .15s}
.status-btn:hover{filter:brightness(.92)}
.status-btn[data-s=applied].active{background:#4caf50;color:#fff;border-color:#4caf50}
.status-btn[data-s=interview].active{background:#009688;color:#fff;border-color:#009688}
.status-btn[data-s=interview_rejected].active{background:#8e24aa;color:#fff;border-color:#8e24aa}
.status-btn[data-s=rejected].active{background:#e53935;color:#fff;border-color:#e53935}
.status-btn[data-s=dislike].active{background:#9e9e9e;color:#fff;border-color:#9e9e9e}
.phd-yes{background:#e3f2fd;padding:1px 5px;border-radius:3px;
  font-size:11px;color:#1565c0;font-weight:bold}
.phd-no{color:#ccc;font-size:11px}
a{color:#1565c0;text-decoration:none}
a:hover{text-decoration:underline}
.score{font-weight:bold}
.score-high{color:#2e7d32}
.score-mid{color:#e65100}
.score-low{color:#9e9e9e}
.nowrap{white-space:nowrap;font-size:12px}
.footer{color:#aaa;font-size:11px;margin-top:8px}
</style>
</head>
<body>
<h1>Job Tracker</h1>
<p class="summary" id="summary">Loading…</p>
<div class="controls">
  <input type="text" id="search" placeholder="Search title / company / location…">
  <button class="filter-btn active" onclick="setFilter('active',this)">Active</button>
  <button class="filter-btn" onclick="setFilter('all',this)">All</button>
  <button class="filter-btn" onclick="setFilter('none',this)">Unreviewed</button>
  <button class="filter-btn" onclick="setFilter('applied',this)">Applied ✅</button>
  <button class="filter-btn" onclick="setFilter('rejected',this)">Rejected ❌</button>
  <button class="filter-btn" onclick="setFilter('dislike',this)">Not Interested 👎</button>
  <button class="filter-btn" onclick="setFilter('interview',this)">Got Interview 🎉</button>
  <button class="filter-btn" onclick="setFilter('interview_rejected',this)">Rejected After Interview 💔</button>
  <button class="filter-btn" onclick="setFilter('newest',this)">Newest ✨</button>
  <span class="legend">🇺🇸 US = light grey</span>
</div>
<table id="job-table">
<thead><tr>
  <th onclick="sortTable(0)">#</th>
  <th>Status</th>
  <th onclick="sortTable(2)">Score</th>
  <th onclick="sortTable(3)">Title</th>
  <th onclick="sortTable(4)">Company</th>
  <th onclick="sortTable(5)">Location</th>
  <th onclick="sortTable(6)">Post Date</th>
  <th>PhD Prefer</th>
  <th>Remote</th>
  <th onclick="sortTable(9)">Source</th>
  <th>Link</th>
</tr></thead>
<tbody id="job-tbody">
<!-- JOB_ROWS_START -->
'''

_SCRIPT_TEMPLATE = '''\n<script>
var KEY='jh-status';
function loadSt(){try{return JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){return{}}}
function saveSt(s){localStorage.setItem(KEY,JSON.stringify(s))}
function setStatus(id,s,btn){
  var st=loadSt();
  if(st[id]===s){delete st[id]}else{st[id]=s}
  saveSt(st);applyStatuses();applyVisibility();
}
function applyStatuses(){
  var st=loadSt();
  document.querySelectorAll('tr[data-id]').forEach(function(row){
    var s=st[row.dataset.id]||(row.dataset.defaultStatus||'');
    if(s){row.dataset.status=s}else{delete row.dataset.status}
    row.querySelectorAll('.status-btn').forEach(function(b){
      b.classList.toggle('active',b.dataset.s===s);
    });
  });
  updateSummary();
}
var curFilter='active',curSearch='';
var LATEST_BATCH='__BATCH__';
function setFilter(f,btn){
  curFilter=f;
  document.querySelectorAll('.filter-btn').forEach(function(b){b.classList.remove('active')});
  btn.classList.add('active');applyVisibility();
}
document.getElementById('search').addEventListener('input',function(e){
  curSearch=e.target.value.toLowerCase();applyVisibility();
});
function applyVisibility(){
  var st=loadSt();
  document.querySelectorAll('tr[data-id]').forEach(function(row){
    var id=row.dataset.id,s=st[id]||'';
    var txt=row.textContent.toLowerCase();
    var show=true;
    if(curFilter==='none')show=!s;
    else if(curFilter==='active')show=(s!=='dislike'&&s!=='expired'&&s!=='rejected'&&s!=='interview_rejected');
    else if(curFilter==='newest')show=(LATEST_BATCH!==''&&row.dataset.batch===LATEST_BATCH);
    else if(curFilter!=='all')show=s===curFilter;
    if(curSearch&&!txt.includes(curSearch))show=false;
    row.style.display=show?'':'none';
  });
}
function updateSummary(){
  var st=loadSt();
  var rows=document.querySelectorAll('tr[data-id]');
  var total=rows.length;
  var counts={applied:0,interview:0,interview_rejected:0,rejected:0,dislike:0};
  Object.values(st).forEach(function(s){if(counts[s]!==undefined)counts[s]++});
  var reviewed=Object.keys(st).filter(function(id){
    return document.querySelector('tr[data-id="'+id+'"]');
  }).length;
  document.getElementById('summary').textContent=
    'Total: '+total+' jobs | Applied: '+counts.applied+
    ' | Got Interview: '+counts.interview+
    ' | Rejected After Interview: '+counts.interview_rejected+
    ' | Rejected: '+counts.rejected+
    ' | Not Interested: '+counts.dislike+
    ' | Unreviewed: '+(total-reviewed);
}
var sortDir={};
function sortTable(col){
  var tbody=document.getElementById('job-tbody');
  var rows=Array.from(tbody.querySelectorAll('tr[data-id]'));
  var dir=(sortDir[col]=-(sortDir[col]||1));
  rows.sort(function(a,b){
    var va=a.cells[col]?a.cells[col].textContent.trim():'';
    var vb=b.cells[col]?b.cells[col].textContent.trim():'';
    var na=parseFloat(va),nb=parseFloat(vb);
    if(!isNaN(na)&&!isNaN(nb))return dir*(na-nb);
    return dir*va.localeCompare(vb);
  });
  rows.forEach(function(r){tbody.appendChild(r)});
}
function migrateExpiredToDislike(){
  var st=loadSt();var changed=false;
  Object.keys(st).forEach(function(id){if(st[id]==='expired'){st[id]='dislike';changed=true;}});
  if(changed)saveSt(st);
}
function upgradeLegacyRows(){
  var NEW_STATUSES=[['interview','Got Interview 🎉'],['interview_rejected','Rejected After Interview 💔']];
  document.querySelectorAll('tr[data-id]').forEach(function(row){
    var id=row.dataset.id;
    var btnDiv=row.querySelector('.status-btns');
    if(!btnDiv)return;
    var expBtn=btnDiv.querySelector('[data-s="expired"]');
    if(expBtn)expBtn.remove();
    NEW_STATUSES.forEach(function(pair){
      var s=pair[0],label=pair[1];
      if(!btnDiv.querySelector('[data-s="'+s+'"]')){
        var btn=document.createElement('button');
        btn.className='status-btn';
        btn.dataset.s=s;
        btn.setAttribute('onclick',"setStatus('"+id+"','"+s+"',this)");
        btn.textContent=label;
        btnDiv.appendChild(btn);
      }
    });
  });
}
migrateExpiredToDislike();
upgradeLegacyRows();
applyStatuses();
applyVisibility();
</script>
'''

_HTML_TAIL = '''\n<!-- JOB_ROWS_END -->
</tbody>
</table>
<p class="footer" id="footer"></p>
''' + _SCRIPT_TEMPLATE + '''
</body>
</html>
'''


def _make_script(batch_str: str) -> str:
    return _SCRIPT_TEMPLATE.replace("'__BATCH__'", f"'{batch_str}'")


def _patch_existing(content: str, batch_str: str) -> str:
    """Update script block, filter buttons, and CSS in an existing HTML file."""
    new_script = _make_script(batch_str)
    content = re.sub(r'<script>.*?</script>', new_script, content, flags=re.DOTALL)
    if "setFilter('newest'" not in content:
        content = content.replace(
            '  <span class="legend">',
            "  <button class=\"filter-btn\" onclick=\"setFilter('newest',this)\">Newest ✨</button>\n  <span class=\"legend\">"
        )
    if "setFilter('interview'" not in content:
        content = content.replace(
            "  <button class=\"filter-btn\" onclick=\"setFilter('newest',this)\">Newest ✨</button>",
            "  <button class=\"filter-btn\" onclick=\"setFilter('interview',this)\">Got Interview \U0001f389</button>\n"
            "  <button class=\"filter-btn\" onclick=\"setFilter('interview_rejected',this)\">Rejected After Interview \U0001f494</button>\n"
            "  <button class=\"filter-btn\" onclick=\"setFilter('newest',this)\">Newest ✨</button>",
        )
    if 'data-status=interview' not in content:
        new_css = (
            'tr[data-status=interview]>td{background-color:#b2dfdb!important}\n'
            'tr[data-status=interview_rejected]>td{background-color:#e1bee7!important}\n'
            '.status-btn[data-s=interview].active{background:#009688;color:#fff;border-color:#009688}\n'
            '.status-btn[data-s=interview_rejected].active{background:#8e24aa;color:#fff;border-color:#8e24aa}\n'
        )
        content = content.replace('</style>', new_css + '</style>', 1)
    # Remove expired filter button from controls
    content = content.replace(
        "  <button class=\"filter-btn\" onclick=\"setFilter('expired',this)\">Expired ⏰</button>\n",
        '',
    )
    return content


def update_html_file(output_path: Path, new_jobs: list[dict], min_score: int = 55) -> tuple[int, int]:
    """Update or create the HTML tracker. Returns (new_count, total_count)."""
    filtered = [j for j in new_jobs if j.get('match_score', 0) >= min_score]
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    batch_str = date.today().isoformat()

    if output_path.exists():
        content = output_path.read_text(encoding='utf-8')
        existing_ids = extract_existing_ids(content)
        existing_count = count_existing_rows(content)

        new_jobs_list = [j for j in filtered if j.get('id') not in existing_ids]

        if new_jobs_list:
            new_html = '\n'.join(
                render_row(existing_count + i + 1, j, batch=batch_str)
                for i, j in enumerate(new_jobs_list)
            )
            content = content.replace(
                '<!-- JOB_ROWS_END -->',
                new_html + '\n<!-- JOB_ROWS_END -->'
            )

        total = existing_count + len(new_jobs_list)

        # Always refresh script block + add Newest button
        updated = _patch_existing(content, batch_str)

        # Update footer
        footer_html = f'Last updated: {now} &nbsp;|&nbsp; {total} total jobs'
        if 'id="footer"' in updated:
            updated = re.sub(
                r'(<p class="footer" id="footer">)[^<]*(</p>)',
                r'\g<1>' + footer_html + r'\g<2>',
                updated,
            )
        output_path.write_text(updated, encoding='utf-8')
        if not new_jobs_list:
            print(f'No new jobs to add ({len(filtered)} filtered jobs already in tracker)')
        return len(new_jobs_list), total

    # Create fresh file
    rows_html = '\n'.join(render_row(i + 1, j, batch=batch_str) for i, j in enumerate(filtered))
    total = len(filtered)
    footer_html = f'Last updated: {now} &nbsp;|&nbsp; {total} total jobs'
    tail = _HTML_TAIL.replace(
        '<p class="footer" id="footer"></p>',
        f'<p class="footer" id="footer">{footer_html}</p>',
    ).replace("'__BATCH__'", f"'{batch_str}'")
    html = _HTML_HEAD + rows_html + '\n' + tail
    output_path.write_text(html, encoding='utf-8')
    return total, total


def main():
    parser = argparse.ArgumentParser(description='Generate/update HTML job tracker')
    parser.add_argument('--scored', '-i', required=True, help='Scored jobs JSON input')
    parser.add_argument('--output', '-o', required=True, help='HTML output file path')
    parser.add_argument('--min-score', type=int, default=55, help='Minimum score (default: 55)')
    args = parser.parse_args()

    with open(args.scored, encoding='utf-8') as f:
        jobs = json.load(f)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    new_count, total = update_html_file(output_path, jobs, args.min_score)
    phd_count = sum(
        1 for j in jobs
        if j.get('match_score', 0) >= args.min_score and phd_prefer(j.get('description') or '')
    )
    print(f'HTML tracker: +{new_count} new jobs added, {total} total | {phd_count} mention PhD preference')
    print(f'Output: {output_path}')


if __name__ == '__main__':
    main()
