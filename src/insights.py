from __future__ import annotations

import numpy as np
import pandas as pd

from src.metrics import compute_kpis, faculty_metrics, fmt_number, fmt_pct, scenario_increase_international, scenario_reduce_waive


def action_for_row(row: pd.Series) -> str:
    actions: list[str] = []
    if pd.notna(row.get("waive_rate")) and row.get("waive_rate") >= row.get("_median_waive", np.inf):
        actions.append("reduce waive rate")
    if pd.notna(row.get("growth_rate")) and row.get("growth_rate") > row.get("_median_growth", -np.inf):
        actions.append("increase quota")
    if pd.notna(row.get("over_program_rate")) and row.get("over_program_rate") >= row.get("_median_over", np.inf):
        actions.append("improve student advising")
    if pd.notna(row.get("international_program_share")) and row.get("international_program_share") < row.get("_median_intl", 0):
        actions.append("target international recruitment")
    if not actions:
        actions.append("improve onboarding")
    return "; ".join(dict.fromkeys(actions))


def priority_faculties(data: dict[str, pd.DataFrame], top_n: int = 10) -> pd.DataFrame:
    fm = faculty_metrics(data)
    if fm.empty:
        return fm
    work = fm.copy()
    for col in ["waive_rate", "over_program_rate", "international_program_share", "growth_rate", "risk_score"]:
        if col not in work.columns:
            work[col] = np.nan
    work["_median_waive"] = work["waive_rate"].median(skipna=True)
    work["_median_over"] = work["over_program_rate"].median(skipna=True)
    work["_median_intl"] = work["international_program_share"].median(skipna=True)
    work["_median_growth"] = work["growth_rate"].median(skipna=True)
    work["recommended_action"] = work.apply(action_for_row, axis=1)
    work["priority_score"] = (
        work["risk_score"].fillna(0)
        + work["waive_rate"].fillna(work["waive_rate"].median(skipna=True)).rank(pct=True)
        + work["over_program_rate"].fillna(work["over_program_rate"].median(skipna=True)).rank(pct=True)
        - work["growth_rate"].fillna(work["growth_rate"].median(skipna=True)).rank(pct=True) * 0.25
    )
    cols = [
        "faculty_name",
        "current_students",
        "growth_rate",
        "waive_rate",
        "over_program_rate",
        "graduation_output_ratio",
        "international_program_share",
        "risk_score",
        "recommended_action",
        "priority_score",
    ]
    return work[[c for c in cols if c in work.columns]].sort_values("priority_score", ascending=False).head(top_n)


def generate_insights(data: dict[str, pd.DataFrame], waive_reduction_pp: float = 5.0, international_increase_pp: float = 1.0) -> list[str]:
    kpis = compute_kpis(data)
    admission = data.get("admission", pd.DataFrame())
    scenario = scenario_reduce_waive(admission, waive_reduction_pp, scope="all")
    intl = scenario_increase_international(data, international_increase_pp)
    priorities = priority_faculties(data, top_n=5)

    insights: list[str] = []
    insights.append(
        "CMU currently has "
        f"{fmt_number(kpis.get('total_current_students'))} active students; the latest intake remainder is "
        f"{fmt_number(kpis.get('new_student_remaining'))} after a waive rate of {fmt_pct(kpis.get('waive_rate'))}."
    )
    insights.append(
        "Estimated net growth is "
        f"{fmt_number(kpis.get('estimated_net_growth'))}: new remaining students minus the latest observed graduates. "
        "This is a simple accounting estimate, not a causal forecast."
    )
    if not scenario.empty:
        add = scenario["additional_students"].sum()
        insights.append(
            f"Reducing the waive rate by {waive_reduction_pp:.1f} percentage points would add about "
            f"{fmt_number(add)} students if every prevented waiver becomes an enrolled student."
        )
    if pd.notna(intl.get("additional_international_students")):
        insights.append(
            f"Raising the international share by {international_increase_pp:.1f} percentage points implies roughly "
            f"{fmt_number(intl['additional_international_students'])} additional international students."
        )
    if not priorities.empty:
        names = ", ".join(priorities["faculty_name"].head(3).astype(str))
        insights.append(f"Top priority faculties/program areas by combined leakage and progress risk: {names}.")
    insights.append(
        "Blunt truth: the fastest controllable lever is usually not marketing. It is reducing accepted-student leakage "
        "and fixing slow progress in programs that already have demand."
    )
    return insights


def scenario_summary(data: dict[str, pd.DataFrame], waive_pp_values: list[float], intl_pp_values: list[float]) -> pd.DataFrame:
    rows = []
    admission = data.get("admission", pd.DataFrame())
    for pp in waive_pp_values:
        result = scenario_reduce_waive(admission, pp, scope="all")
        rows.append({"scenario": f"Reduce waive rate by {pp:g} pp", "additional_students": result["additional_students"].sum() if not result.empty else np.nan})
    for pp in intl_pp_values:
        result = scenario_increase_international(data, pp)
        rows.append({"scenario": f"Increase international share by {pp:g} pp", "additional_students": result.get("additional_international_students", np.nan)})
    return pd.DataFrame(rows)
