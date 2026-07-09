from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.scrape import PROJECT_ROOT


PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


TABLES = {
    "all_stats": "all_stats_long.csv",
    "current_faculty": "current_faculty.csv",
    "undergraduate_programs": "undergraduate_programs.csv",
    "graduate_programs": "graduate_programs.csv",
    "admission": "admission_funnel.csv",
    "graduates": "graduates.csv",
    "history": "historical_students.csv",
    "history_grad_programs": "historical_graduate_programs.csv",
    "nationality": "nationality.csv",
    "nationality_faculty": "nationality_faculty.csv",
    "over_program": "over_program_students.csv",
    "transfer": "transfer_students.csv",
    "quality": "data_quality.csv",
    "dictionary": "data_dictionary.csv",
}


def faculty_match_key(value: object) -> str:
    """Normalize official faculty names across tables with/without Thai prefixes."""
    if pd.isna(value):
        return ""
    text = str(value).strip()
    for prefix in ("คณะ", "วิทยาลัย", "สถาบัน"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return "".join(text.split())


def read_table(name: str) -> pd.DataFrame:
    path = PROCESSED_DIR / TABLES[name]
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as exc:
        df = pd.DataFrame()
        df.attrs["load_error"] = f"{path.relative_to(PROJECT_ROOT)} could not be loaded: {exc}"
        return df


def load_data() -> dict[str, pd.DataFrame]:
    data = {name: read_table(name) for name in TABLES}
    critical = ["current_faculty", "admission", "graduates", "history"]
    missing_critical = any(data[name].empty for name in critical)
    raw_dir = PROJECT_ROOT / "data" / "raw"

    if missing_critical and any(raw_dir.glob("data_s*.json")):
        try:
            from src.clean import clean

            clean(raw_dir)
            data = {name: read_table(name) for name in TABLES}
        except Exception as exc:  # pragma: no cover - surfaced in Streamlit UI
            for df in data.values():
                df.attrs["load_error"] = (
                    "Processed data is missing and automatic regeneration from "
                    f"`data/raw/` failed: {exc}"
                )

    return data


def merge_by_faculty_key(base: pd.DataFrame, other: pd.DataFrame) -> pd.DataFrame:
    if other.empty or "_faculty_key" not in base.columns:
        return base
    work = other.copy()
    if "faculty_name" not in work.columns:
        return base
    work["_faculty_key"] = work["faculty_name"].map(faculty_match_key)
    work = work.drop(columns=["faculty_name"], errors="ignore")
    return base.merge(work, on="_faculty_key", how="left")


def numeric(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").fillna(default)


def latest_by_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    work = df.copy()
    for col in columns:
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce")
    existing = [c for c in columns if c in work.columns and work[c].notna().any()]
    if not existing:
        return work
    mask = pd.Series(True, index=work.index)
    for col in existing:
        max_value = work.loc[mask, col].max()
        mask &= work[col].eq(max_value)
    return work.loc[mask].copy()


def latest_admission(admission: pd.DataFrame, scope: str = "all") -> pd.DataFrame:
    if admission.empty:
        return admission
    work = admission.copy()
    if "admission_scope" in work.columns:
        work = work.loc[work["admission_scope"].eq(scope)]
    return latest_by_columns(work, ["admit_year"])


def current_period(current: pd.DataFrame) -> tuple[float | None, str | None]:
    if current.empty or "param_year" not in current.columns or "param_semester" not in current.columns:
        return None, None
    year = pd.to_numeric(current["param_year"], errors="coerce").dropna()
    semester = current["param_semester"].dropna().astype(str)
    if year.empty or semester.empty:
        return None, None
    return float(year.max()), str(semester.iloc[0])


def latest_graduates(graduates: pd.DataFrame, *, exclude_year: float | None = None, exclude_semester: str | None = None) -> pd.DataFrame:
    if graduates.empty:
        return graduates
    work = graduates.copy()
    if "stat_id" in work.columns and work["stat_id"].eq("s003002").any():
        work = work.loc[work["stat_id"].eq("s003002")]
    if exclude_year is not None and exclude_semester is not None and {"graduation_year", "graduation_semester"}.issubset(work.columns):
        year = pd.to_numeric(work["graduation_year"], errors="coerce")
        sem = pd.to_numeric(work["graduation_semester"], errors="coerce")
        exclude_semester_num = pd.to_numeric(pd.Series([exclude_semester]), errors="coerce").iloc[0]
        completed = work.loc[~(year.eq(exclude_year) & sem.eq(exclude_semester_num))]
        if not completed.empty:
            work = completed
    return latest_by_columns(work, ["graduation_year", "graduation_semester"])


def time_trend(history: pd.DataFrame, current: pd.DataFrame | None = None) -> pd.DataFrame:
    if history.empty:
        if current is None or current.empty:
            return pd.DataFrame(columns=["academic_year", "semester", "student_count", "period"])
        return pd.DataFrame(
            {
                "academic_year": [pd.to_numeric(current.get("param_year"), errors="coerce").max()],
                "semester": [str(current.get("param_semester", pd.Series(["current"])).iloc[0])],
                "student_count": [numeric(current, "current_students").sum()],
                "period": ["current"],
            }
        )
    trend = (
        history.assign(
            academic_year=pd.to_numeric(history["academic_year"], errors="coerce"),
            semester_num=pd.to_numeric(history["semester"], errors="coerce"),
            student_count=numeric(history, "student_count"),
        )
        .groupby(["academic_year", "semester", "semester_num"], dropna=False, as_index=False)["student_count"]
        .sum()
        .sort_values(["academic_year", "semester_num"])
    )
    trend["period"] = trend["academic_year"].astype("Int64").astype(str) + "/" + trend["semester"].astype(str)
    trend["yoy_growth"] = trend["student_count"].pct_change()
    return trend


def faculty_growth(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty or "faculty_name" not in history.columns:
        return pd.DataFrame(columns=["faculty_name", "growth_rate", "cagr", "first_count", "last_count"])
    work = history.copy()
    work["academic_year"] = pd.to_numeric(work["academic_year"], errors="coerce")
    work["semester_num"] = pd.to_numeric(work["semester"], errors="coerce")
    work["student_count"] = numeric(work, "student_count")
    work["period_index"] = work["academic_year"] * 10 + work["semester_num"].fillna(0)
    grouped = work.groupby(["faculty_name", "period_index", "academic_year"], as_index=False)["student_count"].sum()

    rows: list[dict[str, Any]] = []
    for faculty, part in grouped.groupby("faculty_name"):
        part = part.sort_values("period_index")
        first = part.iloc[0]
        last = part.iloc[-1]
        first_count = float(first["student_count"])
        last_count = float(last["student_count"])
        years = max(float(last["academic_year"] - first["academic_year"]), 1.0)
        growth = (last_count - first_count) / first_count if first_count > 0 else np.nan
        cagr = (last_count / first_count) ** (1 / years) - 1 if first_count > 0 and last_count > 0 else np.nan
        rows.append(
            {
                "faculty_name": faculty,
                "first_count": first_count,
                "last_count": last_count,
                "growth_rate": growth,
                "cagr": cagr,
            }
        )
    return pd.DataFrame(rows)


def compute_kpis(data: dict[str, pd.DataFrame]) -> dict[str, float]:
    current = data.get("current_faculty", pd.DataFrame())
    admission = latest_admission(data.get("admission", pd.DataFrame()), "all")
    current_year, current_semester = current_period(current)
    graduates = latest_graduates(data.get("graduates", pd.DataFrame()), exclude_year=current_year, exclude_semester=current_semester)
    nationality = data.get("nationality", pd.DataFrame())

    total_current = numeric(current, "current_students").sum() if not current.empty else np.nan
    issued = numeric(admission, "issued_total").sum() if not admission.empty else np.nan
    waived = numeric(admission, "waived_total").sum() if not admission.empty else np.nan
    remaining = numeric(admission, "remaining_total").sum() if not admission.empty else np.nan
    graduate_count = numeric(graduates, "graduate_count").sum() if not graduates.empty else np.nan

    if not nationality.empty and "is_international" in nationality.columns:
        intl_mask = nationality["is_international"].astype(str).str.lower().isin(["true", "1"])
        intl_students = numeric(nationality.loc[intl_mask], "student_count").sum()
        nat_total = numeric(nationality, "student_count").sum()
        international_share = intl_students / nat_total if nat_total > 0 else np.nan
    else:
        international_share = numeric(current, "international_program_students").sum() / total_current if total_current else np.nan

    return {
        "total_current_students": float(total_current) if pd.notna(total_current) else np.nan,
        "new_student_remaining": float(remaining) if pd.notna(remaining) else np.nan,
        "waive_rate": float(waived / issued) if issued and issued > 0 else np.nan,
        "yield_rate": float(remaining / issued) if issued and issued > 0 else np.nan,
        "graduate_count": float(graduate_count) if pd.notna(graduate_count) else np.nan,
        "estimated_net_growth": float(remaining - graduate_count) if pd.notna(remaining) and pd.notna(graduate_count) else np.nan,
        "international_student_share": float(international_share) if pd.notna(international_share) else np.nan,
    }


def faculty_metrics(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    current = data.get("current_faculty", pd.DataFrame()).copy()
    if current.empty:
        return pd.DataFrame()

    base = (
        current.groupby("faculty_name", as_index=False)
        .agg(
            faculty_code=("faculty_code", "first"),
            current_students=("current_students", "sum"),
            international_program_students=("international_program_students", "sum"),
        )
        .assign(
            international_program_share=lambda d: np.where(
                d["current_students"] > 0,
                d["international_program_students"] / d["current_students"],
                np.nan,
            )
        )
    )
    base["_faculty_key"] = base["faculty_name"].map(faculty_match_key)

    adm = latest_admission(data.get("admission", pd.DataFrame()), "all")
    if not adm.empty:
        adm_summary = (
            adm.groupby("faculty_name", as_index=False)
            .agg(issued_total=("issued_total", "sum"), waived_total=("waived_total", "sum"), remaining_total=("remaining_total", "sum"))
            .assign(
                waive_rate=lambda d: np.where(d["issued_total"] > 0, d["waived_total"] / d["issued_total"], np.nan),
                yield_rate=lambda d: np.where(d["issued_total"] > 0, d["remaining_total"] / d["issued_total"], np.nan),
            )
        )
        base = merge_by_faculty_key(base, adm_summary)

    growth = faculty_growth(data.get("history", pd.DataFrame()))
    if not growth.empty:
        base = merge_by_faculty_key(base, growth[["faculty_name", "growth_rate", "cagr"]])

    over = data.get("over_program", pd.DataFrame())
    if not over.empty:
        over_summary = (
            over.groupby("faculty_name", as_index=False)
            .agg(over_program_students=("over_program_students", "sum"), over_current_students=("current_students", "sum"))
            .assign(over_program_rate=lambda d: np.where(d["over_current_students"] > 0, d["over_program_students"] / d["over_current_students"], np.nan))
        )
        base = merge_by_faculty_key(base, over_summary[["faculty_name", "over_program_students", "over_program_rate"]])

    transfer = data.get("transfer", pd.DataFrame())
    if not transfer.empty:
        transfer_summary = (
            transfer.groupby("faculty_name", as_index=False)
            .agg(transfer_in=("transfer_in", "sum"), transfer_out=("transfer_out", "sum"), net_transfer=("net_transfer", "sum"))
        )
        base = merge_by_faculty_key(base, transfer_summary)
        base["transfer_out_rate"] = np.where(base["current_students"] > 0, base["transfer_out"] / base["current_students"], np.nan)
        base["transfer_in_rate"] = np.where(base["current_students"] > 0, base["transfer_in"] / base["current_students"], np.nan)
        base["transfer_movement_rate"] = np.where(
            base["current_students"] > 0,
            (base["transfer_in"].fillna(0) + base["transfer_out"].fillna(0)) / base["current_students"],
            np.nan,
        )

    current_year, current_semester = current_period(current)
    grads = latest_graduates(data.get("graduates", pd.DataFrame()), exclude_year=current_year, exclude_semester=current_semester)
    if not grads.empty:
        grad_summary = grads.groupby("faculty_name", as_index=False).agg(graduate_count=("graduate_count", "sum"))
        base = merge_by_faculty_key(base, grad_summary)
        base["graduation_output_ratio"] = np.where(base["current_students"] > 0, base["graduate_count"].fillna(0) / base["current_students"], np.nan)

    for col in [
        "issued_total",
        "waived_total",
        "remaining_total",
        "waive_rate",
        "yield_rate",
        "growth_rate",
        "cagr",
        "over_program_students",
        "over_program_rate",
        "transfer_in",
        "transfer_out",
        "net_transfer",
        "transfer_in_rate",
        "transfer_out_rate",
        "transfer_movement_rate",
        "graduate_count",
        "graduation_output_ratio",
    ]:
        if col not in base.columns:
            base[col] = np.nan

    risk_components = pd.DataFrame(
        {
            "waive_rate": base["waive_rate"],
            "over_program_rate": base["over_program_rate"],
            "transfer_out_rate": base["transfer_out_rate"],
            "negative_growth": -base["growth_rate"],
        }
    )
    z = risk_components.apply(lambda s: (s - s.mean(skipna=True)) / s.std(skipna=True) if s.std(skipna=True) else 0)
    base["risk_score"] = z.mean(axis=1, skipna=True)
    base["risk_zscore"] = (base["risk_score"] - base["risk_score"].mean(skipna=True)) / base["risk_score"].std(skipna=True) if base["risk_score"].std(skipna=True) else 0
    base["risk_flag"] = base["risk_zscore"].abs() >= 1.5
    base["quadrant"] = quadrant(base)
    return base.drop(columns=["_faculty_key"], errors="ignore").sort_values("current_students", ascending=False)


def quadrant(df: pd.DataFrame) -> pd.Series:
    growth_mid = df["growth_rate"].median(skipna=True)
    waive_mid = df["waive_rate"].median(skipna=True)
    labels = []
    for _, row in df.iterrows():
        high_growth = pd.notna(row.get("growth_rate")) and row.get("growth_rate") >= growth_mid
        high_waive = pd.notna(row.get("waive_rate")) and row.get("waive_rate") >= waive_mid
        if high_growth and not high_waive:
            labels.append("High growth / Low waive")
        elif high_growth and high_waive:
            labels.append("High growth / High waive")
        elif not high_growth and not high_waive:
            labels.append("Low growth / Low waive")
        else:
            labels.append("Low growth / High waive")
    return pd.Series(labels, index=df.index)


def scenario_reduce_waive(admission: pd.DataFrame, reduction_pp: float = 5.0, scope: str | None = None) -> pd.DataFrame:
    latest = latest_admission(admission, scope).copy() if scope else latest_by_columns(admission, ["admit_year"]).copy()
    if latest.empty:
        return latest
    reduction = max(float(reduction_pp), 0.0) / 100.0
    latest["additional_students"] = np.minimum(numeric(latest, "waived_total"), numeric(latest, "issued_total") * reduction)
    latest["new_remaining_total"] = numeric(latest, "remaining_total") + latest["additional_students"]
    latest["new_waive_rate"] = np.maximum(numeric(latest, "waive_rate") - reduction, 0)
    return latest.sort_values("additional_students", ascending=False)


def scenario_increase_international(data: dict[str, pd.DataFrame], increase_pp: float = 1.0) -> dict[str, float]:
    current = data.get("current_faculty", pd.DataFrame())
    total_current = numeric(current, "current_students").sum()
    additional = total_current * max(float(increase_pp), 0.0) / 100.0 if total_current else np.nan
    return {"additional_international_students": float(additional) if pd.notna(additional) else np.nan}


def faculty_filter(df: pd.DataFrame, faculties: list[str] | None = None) -> pd.DataFrame:
    if df.empty or not faculties or "faculty_name" not in df.columns:
        return df
    return df.loc[df["faculty_name"].isin(faculties)].copy()


def fmt_number(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:,.0f}"


def fmt_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:.1%}"
