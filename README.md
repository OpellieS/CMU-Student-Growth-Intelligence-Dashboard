# CMU Student Growth Intelligence Dashboard

Streamlit dashboard for analyzing official Chiang Mai University registry statistics from `https://statistic.reg.cmu.ac.th/` to answer:

> How can CMU improve the number of students?

## Data Source

The public site is JavaScript-rendered, but its Vue app calls the official JSON API:

- API base: `https://api-statistic.reg.cmu.ac.th/v1`
- Options endpoint: `/Getoption`
- Student menu metadata: `/StatStudentList`
- Table endpoint pattern: `/data/{menuid}{statid}`

Example:

```bash
https://api-statistic.reg.cmu.ac.th/v1/data/s001001?year=2569&semester=1&semestercurrent=1&admityear=999&fac=999&level=999&sex=999&student_type=999&nat=999
```

Playwright is included only as a fallback if the official API becomes unavailable.

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Reproducible Pipeline

Run the scraper first. It is cache-first, sequential, and waits between uncached requests.

```bash
python -m src.scrape --years-back 5 --delay 1.2
python -m src.clean
```

Then start the dashboard:

```bash
streamlit run app.py
```

## Project Structure

```text
app.py
pages/
src/
  scrape.py
  clean.py
  metrics.py
  models.py
  insights.py
data/
  raw/
  processed/
requirements.txt
README.md
```

## Dashboard Pages

- Overview: KPI cards, total-student trend, faculty ranking, data quality.
- Admission Funnel: issued ID -> waived -> remaining, rates by faculty, gender breakdown, waiver scenario, chi-square and logistic regression.
- Faculty and Program Growth: faculty-year heatmap, growth/leakage bubble, quadrant interpretation, clustering, count regression.
- Retention and Progress Risk: over-program-length, transfer, graduate-output ratio, risk ranking and z-score flags.
- International Opportunity: nationality choropleth, top nationalities, nationality-faculty heatmap, opportunity score.
- Recommendation: auto-generated insights, priority faculties, action list, scenario estimates.

## Notes and Caveats

- Final numbers are not hard-coded. The dashboard computes them from `data/raw/` and `data/processed/`.
- Some official tables expose generic columns such as `c1`, `c2`, etc. `src.clean` derives common totals and preserves `all_stats_long.csv` for audit.
- Logistic regression uses aggregated faculty-gender admission counts because individual student-level records are not public.
- International faculty opportunity uses nationality data where available and international-program share as a faculty-level proxy.
- Scenario estimates are deterministic accounting estimates, not causal forecasts.
