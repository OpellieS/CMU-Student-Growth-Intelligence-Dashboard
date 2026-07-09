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

## Deployment Options

### A. Local run

The repository includes cached raw and processed data, so a fresh clone can open the dashboard immediately.

```bash
python -m venv .venv
source .venv/bin/activate    # macOS/Linux
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit, usually:

```text
http://localhost:8501
```

`localhost` means the current machine only. A URL such as `http://localhost:8502/` works only on the computer that is running the Streamlit server. Other people cannot open your localhost link from their own computers. If your computer is off, sleeping, disconnected from Wi-Fi, or Streamlit is stopped, the dashboard is not accessible. For that reason, localhost is not suitable as the final link to send to an instructor.

Playwright is only needed if the API fallback renderer is used:

```bash
python -m playwright install chromium
```

### B. Run on a specific port

Use this when you specifically want port `8502`:

```bash
streamlit run app.py --server.port 8502
```

Then open:

```text
http://localhost:8502
```

If port `8502` is already occupied, stop the process using that port or choose another port such as `8501`.

### C. Temporary local network sharing

For short testing on another device connected to the same Wi-Fi:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8502
```

On the other device, open:

```text
http://HOST_MACHINE_IP:8502
```

Notes:

- Both devices must be on the same network.
- The host computer must stay on.
- Streamlit must keep running.
- The host firewall may need to allow inbound traffic on port `8502`.
- This method is only for temporary testing, not final submission.

### D. Recommended: Streamlit Community Cloud

Use Streamlit Community Cloud for the instructor link because the app stays accessible without your local computer running.

1. Push this repository to GitHub.
2. Go to `https://streamlit.io/cloud`.
3. Create a new app.
4. Select the GitHub repository.
5. Set the main file path to `app.py`.
6. Deploy.
7. Share the generated public Streamlit URL with the instructor.

Deployment checklist:

- `app.py` exists at the repository root.
- `requirements.txt` exists and includes the Python dependencies.
- `runtime.txt` requests Python 3.11 for hosted deployment.
- `data/raw/` and `data/processed/` include cached official data, or the scraper can regenerate it.
- `.streamlit/config.toml` is included for the CMU-inspired theme.
- No local-only absolute paths are required.
- No secrets are committed.

If deployed publicly, avoid repeatedly scraping the official CMU API from the hosted app. Keep the cached data in the repo for classroom submission, and rerun the scraper locally only when refreshing the dataset.

### Other hosting options

Streamlit Community Cloud is the simplest option for this project. Alternatives include Render, Railway, Hugging Face Spaces, or a Docker/VPS deployment.

## Reproducible Data Pipeline

Run the scraper first. It is cache-first, sequential, and waits between uncached requests.

```bash
python -m src.scrape --years-back 5 --delay 1.2
python -m src.clean
```

If the official API is unavailable and you need the JavaScript-rendered fallback:

```bash
python -m src.scrape --years-back 5 --delay 1.2 --playwright-fallback
python -m src.clean
```

The app reads relative project paths only:

- `data/raw/`
- `data/processed/`
- `.streamlit/config.toml`

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
.streamlit/config.toml
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

## Troubleshooting

- **Missing processed tables**: run `python -m src.scrape --years-back 5 --delay 1.2`, then `python -m src.clean`.
- **Dashboard opens but charts are empty**: check that `data/processed/*.csv` exists.
- **`http://localhost:8502/` does not open**: confirm Streamlit is running with `streamlit run app.py --server.port 8502`. If no process is listening on port `8502`, the browser has nothing to connect to.
- **Another device cannot open the app**: confirm both devices are on the same Wi-Fi, use the host machine IP address, keep Streamlit running, and allow firewall access to port `8502`.
