from __future__ import annotations

import os
import warnings
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy.stats import chi2_contingency

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.metrics import faculty_metrics, latest_admission, numeric


def model_message(message: str) -> dict[str, Any]:
    return {"ok": False, "message": message, "table": pd.DataFrame()}


def safe_exp(values: np.ndarray | pd.Series) -> np.ndarray:
    coefs = np.asarray(values, dtype=float)
    result = np.exp(np.clip(coefs, -709, 709))
    return np.where(coefs > 709, np.inf, result)


def chi_square_waive_by_faculty(admission: pd.DataFrame, scope: str | None = None) -> dict[str, Any]:
    latest = latest_admission(admission, scope) if scope else admission.copy()
    if latest.empty:
        return model_message("Admission data is missing.")
    work = latest.groupby("faculty_name", as_index=False).agg(waived=("waived_total", "sum"), remained=("remaining_total", "sum"))
    work = work.loc[(work["waived"] + work["remained"]) > 0]
    if len(work) < 2:
        return model_message("Need at least two faculties with admission outcomes for chi-square.")
    table = work[["waived", "remained"]].to_numpy()
    chi2, p_value, dof, expected = chi2_contingency(table)
    expected_df = pd.DataFrame(expected, columns=["expected_waived", "expected_remained"])
    result = pd.concat([work.reset_index(drop=True), expected_df], axis=1)
    result["waive_rate"] = np.where(result["waived"] + result["remained"] > 0, result["waived"] / (result["waived"] + result["remained"]), np.nan)
    return {
        "ok": True,
        "chi2": float(chi2),
        "p_value": float(p_value),
        "dof": int(dof),
        "table": result.sort_values("waive_rate", ascending=False),
        "message": "Reject equal waive rates across faculties if p-value is below the selected alpha.",
    }


def admission_gender_long(admission: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in admission.iterrows():
        for gender, issued_col, waived_col, remaining_col in [
            ("male", "issued_male", "waived_male", "remaining_male"),
            ("female", "issued_female", "waived_female", "remaining_female"),
        ]:
            issued = row.get(issued_col, 0)
            waived = row.get(waived_col, 0)
            remained = row.get(remaining_col, 0)
            if pd.notna(issued) and issued > 0:
                rows.append(
                    {
                        "faculty_name": row.get("faculty_name"),
                        "gender": gender,
                        "admit_year": row.get("admit_year"),
                        "issued": float(issued),
                        "waived": float(waived),
                        "remained": float(remained),
                        "waived_rate": float(waived) / float(issued) if issued else np.nan,
                    }
                )
    return pd.DataFrame(rows)


def logistic_waiver_model(admission: pd.DataFrame, scope: str | None = None) -> dict[str, Any]:
    work = admission.copy()
    if scope and "admission_scope" in work.columns:
        work = work.loc[work["admission_scope"].eq(scope)]
    long = admission_gender_long(work)
    long = long.dropna(subset=["faculty_name", "gender", "admit_year", "waived_rate", "issued"])
    if len(long) < 12 or long["faculty_name"].nunique() < 2:
        return model_message("Not enough aggregated admission-by-gender rows for logistic regression.")

    formula = "waived_rate ~ C(gender) + admit_year"
    if len(long) > long["faculty_name"].nunique() + 6:
        formula = "waived_rate ~ C(faculty_name) + C(gender) + admit_year"

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fitted = smf.glm(
                formula=formula,
                data=long,
                family=sm.families.Binomial(),
                freq_weights=long["issued"],
            ).fit()
    except Exception as exc:
        return model_message(f"Logistic regression could not be fitted: {exc}")

    table = pd.DataFrame(
        {
            "term": fitted.params.index,
            "coef": fitted.params.values,
            "odds_ratio": safe_exp(fitted.params.values),
            "p_value": fitted.pvalues.values,
        }
    ).sort_values("p_value")
    return {
        "ok": True,
        "formula": formula,
        "n_rows": int(len(long)),
        "table": table,
        "message": "Model is fitted on aggregated counts, not individual student records.",
    }


def count_regression(history: pd.DataFrame) -> dict[str, Any]:
    if history.empty:
        return model_message("Historical student-count data is missing.")
    work = history.copy()
    work["student_count"] = numeric(work, "student_count")
    work["academic_year"] = pd.to_numeric(work["academic_year"], errors="coerce")
    work["semester"] = pd.to_numeric(work["semester"], errors="coerce")
    work = work.dropna(subset=["faculty_name", "academic_year", "student_count"])
    work = work.groupby(["faculty_name", "academic_year", "semester"], as_index=False)["student_count"].sum()
    if len(work) < 20 or work["faculty_name"].nunique() < 2:
        return model_message("Need more historical faculty-year rows for count regression.")

    formula = "student_count ~ academic_year + semester + C(faculty_name)"
    try:
        poisson = smf.glm(formula=formula, data=work, family=sm.families.Poisson()).fit()
        dispersion = float(poisson.pearson_chi2 / max(poisson.df_resid, 1))
        family = sm.families.NegativeBinomial(alpha=max(dispersion - 1, 0.1)) if dispersion > 1.5 else sm.families.Poisson()
        fitted = smf.glm(formula=formula, data=work, family=family).fit()
    except Exception as exc:
        return model_message(f"Count regression could not be fitted: {exc}")

    table = pd.DataFrame(
        {
            "term": fitted.params.index,
            "coef": fitted.params.values,
            "rate_ratio": safe_exp(fitted.params.values),
            "p_value": fitted.pvalues.values,
        }
    ).sort_values("p_value")
    return {
        "ok": True,
        "family": fitted.family.__class__.__name__,
        "dispersion": dispersion,
        "table": table,
        "message": "Negative Binomial is used when Poisson overdispersion is large.",
    }


def cluster_faculties(data: dict[str, pd.DataFrame], n_clusters: int = 4) -> pd.DataFrame:
    metrics = faculty_metrics(data)
    if metrics.empty:
        return metrics
    features = [
        "current_students",
        "growth_rate",
        "waive_rate",
        "over_program_rate",
        "graduation_output_ratio",
        "international_program_share",
    ]
    available = [f for f in features if f in metrics.columns]
    work = metrics[["faculty_name"] + available].copy()
    if len(work) < 3 or len(available) < 2:
        work["cluster"] = 0
        work["cluster_label"] = "Insufficient features"
        return work

    k = min(max(2, n_clusters), len(work))
    pipe = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("cluster", KMeans(n_clusters=k, random_state=42, n_init=20)),
        ]
    )
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Could not find the number of physical cores.*", category=UserWarning)
        work["cluster"] = pipe.fit_predict(work[available])
    centers = work.groupby("cluster")[available].mean(numeric_only=True)

    labels: dict[int, str] = {}
    for cluster_id, center in centers.iterrows():
        if center.get("waive_rate", 0) >= centers.get("waive_rate", pd.Series([0])).median() and center.get("growth_rate", 0) <= centers.get("growth_rate", pd.Series([0])).median():
            labels[cluster_id] = "Leakage priority"
        elif center.get("growth_rate", 0) >= centers.get("growth_rate", pd.Series([0])).median() and center.get("waive_rate", 0) <= centers.get("waive_rate", pd.Series([0])).median():
            labels[cluster_id] = "Growth engine"
        elif center.get("international_program_share", 0) >= centers.get("international_program_share", pd.Series([0])).median():
            labels[cluster_id] = "International opportunity"
        elif center.get("over_program_rate", 0) >= centers.get("over_program_rate", pd.Series([0])).median():
            labels[cluster_id] = "Progress-risk watch"
        else:
            labels[cluster_id] = "Stable base"

    work["cluster_label"] = work["cluster"].map(labels)
    return metrics.merge(work[["faculty_name", "cluster", "cluster_label"]], on="faculty_name", how="left")
