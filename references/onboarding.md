# CV onboarding protocol

The AI reading this skill makes recommendations; no extra model API account is required. `scan` only extracts text, not recommendations. CV text is exposed to the AI session; local extraction does not mean the AI itself is offline. Do not send CVs to JobSpy or JSearch: those receive search phrases and locations only.

Default config: `~/.config/job-hunter/config.json`. For a side-by-side install use another `--config` path on every command. Keep CV, proposal, config and generated outputs outside the repository.

## Proposal

Create a JSON proposal after reviewing the supplied CV. Example shape (fictional data, replace with actual CV evidence):

```json
{
  "keywords": ["data analyst", "business intelligence analyst"],
  "scoring": {
    "min_score": 55,
    "title_terms": ["analyst", "business intelligence"],
    "skills": [
      {"label": "SQL", "terms": ["SQL", "PostgreSQL"], "weight": 6, "evidence": "SQL"},
      {"label": "Reporting", "terms": ["Power BI", "dashboard"], "weight": 4, "evidence": "Power BI"}
    ],
    "excluded_title_terms": [],
    "required_any": []
  }
}
```

Use exact CV excerpts for `evidence`. Terms are literal case-insensitive phrases, with word boundaries, not regex. Group related synonyms in one skill so they do not double-count. Explain any expanded synonym. Skill weights are 0 < weight <= 10. Weighted CV-supported skill coverage contributes 75 points; a matching title term adds 25; an excluded title phrase subtracts 35. The threshold defaults to 55. This replaces the original author's specialized rules; it is not numerically comparable to historical scores.

`required_any` is an optional hard filter: at least one listed phrase must appear in title/JD. Default empty; do not require Master's/PhD merely because the CV has one. Do not insert education, career-stage, employer, language or seniority restrictions without discussing them with the user. Keywords and title terms may describe transferable adjacent roles; distinguish these recommendations from CV facts.

After keyword/profile confirmation, save via `profile`. The config then has `countries_pending`; no search is allowed. Present the country list, get the second confirmation, then run `countries`. A renewed profile confirmation resets this gate even if the old countries remain stored. The AI must recover the pending step when resuming rather than silently finishing it.

## Available country mappings

These are the adapter's configured mappings, not a guarantee of current provider coverage. Coverage varies by board; report errors rather than silently substituting the USA.

United States, Canada, Mexico, United Kingdom, Germany, Netherlands, Belgium, France, Austria, Ireland, Italy, Spain, Switzerland, Czech Republic, Poland, Hungary, Slovakia, Malta, Finland, Sweden, Denmark, Norway, Estonia, Latvia, Lithuania, Romania, Bulgaria, Portugal, Greece, Japan, South Korea, Singapore, China.

Country arguments containing spaces must be quoted. Store `search.remote: true` only for remote-only results; false includes on-site, hybrid and remote jobs. This is a filter, not an application eligibility check.

## Optional JSearch

Leave disabled by default (no key). To enable after the user requests it, store their key locally as `jsearch_api_key`; never echo it or commit it. The user checks their own RapidAPI plan. `search.jsearch_keywords` can shorten supplemental searches. Existing configuration keys are preserved by onboarding. Never overwrite a key with a masked placeholder.
