from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests


API_BASE = "https://api-statistic.reg.cmu.ac.th/v1"
SITE_BASE = "https://statistic.reg.cmu.ac.th"
USER_AGENT = "CMUStudentGrowthDashboard/1.0 educational project; slow cache-first requests"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"


TARGET_STATS: dict[str, dict[str, str]] = {
    "s001001": {"page": "/stat/s001/001", "group": "current", "label": "current_active_students"},
    "s001004": {"page": "/stat/s001/004", "group": "current", "label": "current_undergraduate_programs"},
    "s001007": {"page": "/stat/s001/007", "group": "current", "label": "current_graduate_programs_by_admit_year"},
    "s001012": {"page": "/stat/s001/012", "group": "international", "label": "current_students_by_nationality"},
    "s001016": {"page": "/stat/s001/016", "group": "international", "label": "current_students_by_nationality_faculty"},
    "s001010": {"page": "/stat/s001/010", "group": "risk", "label": "over_program_length_students"},
    "s001017": {"page": "/stat/s001/017", "group": "risk", "label": "transfer_students"},
    "s002001": {"page": "/stat/s002/001", "group": "admission", "label": "admission_issued_waived_remaining"},
    "s002002": {"page": "/stat/s002/002", "group": "admission", "label": "first_generation_admission_issued_waived_remaining"},
    "s003001": {"page": "/stat/s003/001", "group": "graduates", "label": "graduates_by_admission_year"},
    "s003002": {"page": "/stat/s003/002", "group": "graduates", "label": "graduates_by_graduation_semester"},
    "s003003": {"page": "/stat/s003/003", "group": "graduates", "label": "graduates_by_admission_year_program"},
    "s004001": {"page": "/stat/s004/001", "group": "history", "label": "historical_students_by_semester"},
    "s004005": {"page": "/stat/s004/005", "group": "history", "label": "historical_graduate_students_by_program"},
}


@dataclass(frozen=True)
class ScrapeJob:
    stat_id: str
    params: dict[str, str]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def clean_token(value: Any) -> str:
    value = "" if value is None else str(value)
    value = re.sub(r"[^A-Za-z0-9ก-๙_.-]+", "-", value).strip("-")
    return value or "blank"


def params_cache_key(params: dict[str, Any] | None) -> str:
    if not params:
        return "default"
    readable = "_".join(f"{clean_token(k)}-{clean_token(v)}" for k, v in sorted(params.items()))
    digest = hashlib.sha1(json.dumps(params, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:8]
    return f"{readable}__{digest}"


def raw_path(endpoint_id: str, params: dict[str, Any] | None = None) -> Path:
    return RAW_DIR / f"{endpoint_id}__{params_cache_key(params)}.json"


def load_cached(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"})
    return s


def fetch_api(
    client: requests.Session,
    endpoint: str,
    params: dict[str, str] | None = None,
    *,
    force: bool = False,
    delay_seconds: float = 1.2,
    timeout: int = 45,
) -> dict[str, Any]:
    endpoint_id = endpoint.strip("/").replace("/", "_")
    path = raw_path(endpoint_id, params)
    cached = load_cached(path)
    if cached and not force:
        return cached

    if delay_seconds > 0:
        time.sleep(delay_seconds)

    url = f"{API_BASE}/{endpoint.strip('/')}"
    response = client.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    wrapped = {
        "source": "official_json_api",
        "source_url": response.url,
        "endpoint": endpoint,
        "params": params or {},
        "fetched_at_utc": now_utc(),
        "payload": payload,
    }
    save_json(path, wrapped)
    return wrapped


def default_params(options: dict[str, Any], *, admityear: str = "999", year: str | None = None, semester: str | None = None) -> dict[str, str]:
    app_sem = (options.get("app_semester") or [{}])[0]
    current_year = str(year or app_sem.get("year") or "")
    current_sem = str(semester or app_sem.get("semester") or "1")
    return {
        "year": current_year,
        "semester": current_sem,
        "semestercurrent": current_sem,
        "admityear": str(admityear),
        "fac": "999",
        "level": "999",
        "sex": "999",
        "student_type": "999",
        "nat": "999",
    }


def current_be_year(options: dict[str, Any]) -> int:
    app_sem = (options.get("app_semester") or [{}])[0]
    return int(app_sem.get("year"))


def current_admit_year_short(options: dict[str, Any]) -> int:
    return current_be_year(options) - 2500


def top_international_nationalities(payload: dict[str, Any], limit: int = 12) -> list[str]:
    rows = payload.get("data") or []
    if not rows:
        return []
    df = pd.DataFrame(rows)
    if "nationality_id_for_check" not in df.columns:
        return []
    total_col = sorted([c for c in df.columns if re.fullmatch(r"c\d+", str(c))], key=lambda c: int(c[1:]))[-1]
    excluded = {"TH", "XX", "XY", "XZ", "ZX", "ZY", "ZZ"}
    df["student_count"] = pd.to_numeric(df[total_col], errors="coerce").fillna(0)
    df["nationality_id_for_check"] = df["nationality_id_for_check"].astype(str).str.upper()
    return (
        df.loc[~df["nationality_id_for_check"].isin(excluded)]
        .sort_values("student_count", ascending=False)["nationality_id_for_check"]
        .head(limit)
        .tolist()
    )


def build_jobs(options: dict[str, Any], years_back: int = 5, nationality_ids: list[str] | None = None) -> list[ScrapeJob]:
    jobs: list[ScrapeJob] = []
    be_year = current_be_year(options)
    admit_short = current_admit_year_short(options)

    current_stats = ["s001001", "s001004", "s001007", "s001012", "s001016", "s001010", "s001017"]
    for stat_id in current_stats:
        jobs.append(ScrapeJob(stat_id, default_params(options)))

    for nationality_id in nationality_ids or []:
        params = default_params(options)
        params["nat"] = nationality_id
        jobs.append(ScrapeJob("s001016", params))

    for yy in range(admit_short, admit_short - years_back, -1):
        params = default_params(options, admityear=str(yy))
        jobs.append(ScrapeJob("s002001", params))
        jobs.append(ScrapeJob("s002002", params))
        jobs.append(ScrapeJob("s003001", params))
        jobs.append(ScrapeJob("s003003", params))

    for year in range(be_year, be_year - years_back, -1):
        for semester in ("1", "2", "3"):
            params = default_params(options, year=str(year), semester=semester)
            jobs.append(ScrapeJob("s003002", params))

    for year in range(be_year, be_year - years_back, -1):
        for semester in ("1", "2"):
            params = default_params(options, year=str(year), semester=semester)
            jobs.append(ScrapeJob("s004001", params))
            jobs.append(ScrapeJob("s004005", params))

    seen: set[tuple[str, str]] = set()
    deduped: list[ScrapeJob] = []
    for job in jobs:
        key = (job.stat_id, json.dumps(job.params, sort_keys=True))
        if key not in seen:
            deduped.append(job)
            seen.add(key)
    return deduped


def fetch_rendered_table_with_playwright(page_path: str) -> pd.DataFrame:
    """Fallback only: render a JS page and extract the first HTML table."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(f"{SITE_BASE}{page_path}", wait_until="networkidle", timeout=90_000)
        page.wait_for_selector("table", timeout=90_000)
        html = page.content()
        browser.close()
    tables = pd.read_html(html)
    if not tables:
        raise RuntimeError(f"No table found after rendering {page_path}")
    return tables[0]


def scrape(
    *,
    years_back: int = 5,
    force: bool = False,
    delay_seconds: float = 1.2,
    playwright_fallback: bool = False,
) -> list[Path]:
    ensure_dirs()
    client = session()

    getoption = fetch_api(client, "Getoption", force=force, delay_seconds=delay_seconds)
    fetch_api(client, "StatStudentList", force=force, delay_seconds=delay_seconds)
    options = getoption["payload"]
    nationality_payload = fetch_api(client, "data/s001012", default_params(options), force=force, delay_seconds=delay_seconds)
    nationality_ids = top_international_nationalities(nationality_payload["payload"])
    jobs = build_jobs(options, years_back=years_back, nationality_ids=nationality_ids)

    saved: list[Path] = []
    failures: list[dict[str, Any]] = []
    for idx, job in enumerate(jobs, start=1):
        endpoint = f"data/{job.stat_id}"
        try:
            wrapped = fetch_api(client, endpoint, job.params, force=force, delay_seconds=delay_seconds)
            path = raw_path(endpoint.replace("/", "_"), job.params)
            saved.append(path)
            print(f"[{idx:03d}/{len(jobs):03d}] cached {job.stat_id} rows={len(wrapped.get('payload', {}).get('data') or [])}")
        except Exception as exc:
            failures.append({"stat_id": job.stat_id, "params": job.params, "error": repr(exc)})
            print(f"[{idx:03d}/{len(jobs):03d}] failed {job.stat_id}: {exc}")
            if playwright_fallback and job.stat_id in TARGET_STATS:
                table = fetch_rendered_table_with_playwright(TARGET_STATS[job.stat_id]["page"])
                fallback_path = RAW_DIR / f"{job.stat_id}__playwright_table.csv"
                table.to_csv(fallback_path, index=False)
                saved.append(fallback_path)

    manifest = {
        "source": "official_json_api",
        "api_base": API_BASE,
        "site_base": SITE_BASE,
        "target_stats": TARGET_STATS,
        "years_back": years_back,
        "delay_seconds": delay_seconds,
        "force": force,
        "fetched_at_utc": now_utc(),
        "saved_files": [str(p.relative_to(PROJECT_ROOT)) for p in saved],
        "failures": failures,
    }
    manifest_path = RAW_DIR / "manifest.json"
    save_json(manifest_path, manifest)
    saved.append(manifest_path)
    return saved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cache official CMU registry statistic JSON tables.")
    parser.add_argument("--years-back", type=int, default=5, help="Recent academic/admission years to cache.")
    parser.add_argument("--force", action="store_true", help="Re-download even when a raw cache file exists.")
    parser.add_argument("--delay", type=float, default=1.2, help="Seconds to wait before each uncached request.")
    parser.add_argument("--playwright-fallback", action="store_true", help="Render pages only if the API request fails.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    saved = scrape(
        years_back=args.years_back,
        force=args.force,
        delay_seconds=args.delay,
        playwright_fallback=args.playwright_fallback,
    )
    print(f"Saved or reused {len(saved)} raw artifacts in {RAW_DIR}")


if __name__ == "__main__":
    main()
