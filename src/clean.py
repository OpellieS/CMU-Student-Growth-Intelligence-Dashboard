from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    import pycountry
except Exception:  # pragma: no cover - optional convenience for map rendering
    pycountry = None

from src.scrape import PROJECT_ROOT, RAW_DIR, TARGET_STATS


PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
THAI_OR_ADMIN_NATIONALITY_CODES = {"TH", "XX", "XY", "XZ", "ZX", "ZY", "ZZ"}


def ensure_dirs() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def c_sort_key(col: str) -> int:
    match = re.fullmatch(r"c(\d+)", str(col))
    return int(match.group(1)) if match else 10_000


def c_columns(df: pd.DataFrame) -> list[str]:
    return sorted([c for c in df.columns if re.fullmatch(r"c\d+", str(c))], key=c_sort_key)


def normalize_text(value: Any) -> Any:
    if pd.isna(value):
        return value
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    return value


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def iter_raw_stat_files() -> list[Path]:
    return sorted(RAW_DIR.glob("data_s*.json"))


def parse_faculty(value: Any) -> tuple[str | None, str | None]:
    if pd.isna(value):
        return None, None
    text = str(value).strip()
    match = re.match(r"^(?P<code>\d{1,3})\s*:\s*(?P<name>.+)$", text)
    if match:
        return match.group("code"), match.group("name").strip()
    return None, text


def parse_code_label(value: Any) -> tuple[str | None, str | None]:
    if pd.isna(value):
        return None, None
    text = str(value).strip()
    match = re.match(r"^(?P<code>[^:]+)\s*:\s*(?P<label>.+)$", text)
    if match:
        return match.group("code").strip(), match.group("label").strip()
    return None, text


def iso2_to_iso3(code: Any) -> str | None:
    if pd.isna(code):
        return None
    code = str(code).upper()
    if pycountry is None:
        return code
    country = pycountry.countries.get(alpha_2=code)
    return country.alpha_3 if country else code


def stat_id_from_wrapper(wrapper: dict[str, Any], path: Path) -> str:
    endpoint = str(wrapper.get("endpoint") or "")
    if endpoint.startswith("data/"):
        return endpoint.split("/", 1)[1]
    match = re.search(r"(s\d{6})", path.name)
    if match:
        return match.group(1)
    return "unknown"


def header_label_map(payload: dict[str, Any], df: pd.DataFrame) -> dict[str, str]:
    """Best-effort c-column labels from the API header definition."""
    cols = c_columns(df)
    if not cols:
        return {}

    header = payload.get("header") or []
    if not header:
        return {}

    first_data = payload.get("data") or []
    non_c_count = 0
    if first_data:
        non_c_count = len([k for k in first_data[0].keys() if not re.fullmatch(r"c\d+", str(k))])

    if len(header) == 1:
        fields: list[str] = []
        row = header[0]
        for _ in range(int(row.get("iterate") or 1)):
            fields.extend([str(f.get("name", "")).strip() for f in row.get("field") or []])
        labels = fields[non_c_count : non_c_count + len(cols)]
        if len(labels) == len(cols):
            return dict(zip(cols, labels))

    last = header[-1]
    leaf: list[str] = []
    for _ in range(int(last.get("iterate") or 1)):
        leaf.extend([str(f.get("name", "")).strip() for f in last.get("field") or []])
    if len(leaf) == len(cols):
        return dict(zip(cols, leaf))

    return {col: col for col in cols}


def clean_one(path: Path) -> pd.DataFrame:
    wrapper = read_json(path)
    payload = wrapper.get("payload") or {}
    rows = payload.get("data") or []
    stat_id = stat_id_from_wrapper(wrapper, path)
    df = pd.DataFrame(rows)

    if df.empty:
        return pd.DataFrame(
            [
                {
                    "stat_id": stat_id,
                    "stat_label": TARGET_STATS.get(stat_id, {}).get("label", stat_id),
                    "source_file": path.name,
                    "error": payload.get("error", ""),
                    "row_count": 0,
                }
            ]
        )

    for col in df.columns:
        df[col] = df[col].map(normalize_text)

    for col in c_columns(df):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["stat_id"] = stat_id
    df["stat_label"] = TARGET_STATS.get(stat_id, {}).get("label", stat_id)
    df["source_file"] = path.name
    df["source_url"] = wrapper.get("source_url")
    df["fetched_at_utc"] = wrapper.get("fetched_at_utc")
    df["error"] = payload.get("error", "")
    df["order"] = payload.get("order", "")

    params = wrapper.get("params") or {}
    for key, value in params.items():
        df[f"param_{key}"] = value

    cols = c_columns(df)
    if cols:
        df["total_col"] = cols[-1]
        df["total_count"] = df[cols[-1]]
    else:
        df["total_col"] = None
        df["total_count"] = np.nan

    if "faculty" in df.columns:
        parsed = df["faculty"].apply(parse_faculty)
        df["faculty_code"] = parsed.apply(lambda x: x[0])
        df["faculty_name"] = parsed.apply(lambda x: x[1])
    elif "faculty_name" in df.columns:
        parsed = df["faculty_name"].apply(parse_faculty)
        parsed_code = parsed.apply(lambda x: x[0])
        parsed_name = parsed.apply(lambda x: x[1])
        if parsed_code.notna().any():
            df["faculty_code"] = parsed_code
            df["faculty_name"] = parsed_name

    if "major" in df.columns:
        parsed = df["major"].apply(parse_code_label)
        df["program_code"] = parsed.apply(lambda x: x[0])
        df["program_name"] = parsed.apply(lambda x: x[1])

    if "curriculum" in df.columns:
        df["program_name"] = df["curriculum"].astype("string")

    if "nationality_id_for_check" in df.columns:
        df["nationality_id"] = df["nationality_id_for_check"].astype("string")
        df["iso_alpha3"] = df["nationality_id"].apply(iso2_to_iso3)
        df["is_international"] = ~df["nationality_id"].str.upper().isin(THAI_OR_ADMIN_NATIONALITY_CODES)

    labels = header_label_map(payload, df)
    for col, label in labels.items():
        df[f"{col}_label"] = label

    return df


def latest_admission_year(df: pd.DataFrame) -> pd.DataFrame:
    if "param_admityear" not in df.columns:
        return df
    work = df.copy()
    work["_admityear_num"] = pd.to_numeric(work["param_admityear"], errors="coerce")
    if work["_admityear_num"].notna().any():
        latest = work["_admityear_num"].max()
        work = work.loc[work["_admityear_num"] == latest].drop(columns="_admityear_num")
    return work


def build_current_faculty(all_stats: pd.DataFrame) -> pd.DataFrame:
    df = all_stats.loc[all_stats["stat_id"].eq("s001001")].copy()
    if df.empty:
        return df
    df["current_students"] = df["total_count"].fillna(0)
    for col in ["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9", "c10"]:
        if col not in df.columns:
            df[col] = 0
    df["male_students"] = df[["c1", "c4", "c7"]].sum(axis=1, skipna=True)
    df["female_students"] = df[["c2", "c5", "c8"]].sum(axis=1, skipna=True)
    df["regular_program_students"] = df["c3"].fillna(0)
    df["special_program_students"] = df["c6"].fillna(0)
    df["international_program_students"] = df["c9"].fillna(0)
    df["international_program_share"] = np.where(df["current_students"] > 0, df["international_program_students"] / df["current_students"], np.nan)
    return df[
        [
            "faculty_code",
            "faculty_name",
            "current_students",
            "male_students",
            "female_students",
            "regular_program_students",
            "special_program_students",
            "international_program_students",
            "international_program_share",
            "param_year",
            "param_semester",
            "source_file",
        ]
    ].sort_values("current_students", ascending=False)


def build_programs(all_stats: pd.DataFrame, stat_id: str, output_total_col: str = "current_students") -> pd.DataFrame:
    df = all_stats.loc[all_stats["stat_id"].eq(stat_id)].copy()
    if df.empty:
        return df
    df[output_total_col] = df["total_count"].fillna(0)
    keep = [
        c
        for c in [
            "stat_id",
            "faculty_code",
            "faculty_name",
            "program_code",
            "program_name",
            "level",
            "curriculum_type",
            output_total_col,
            "param_year",
            "param_semester",
            "param_admityear",
            "source_file",
        ]
        if c in df.columns
    ]
    return df[keep].sort_values(output_total_col, ascending=False)


def build_admission(all_stats: pd.DataFrame) -> pd.DataFrame:
    df = all_stats.loc[all_stats["stat_id"].isin(["s002001", "s002002"])].copy()
    if df.empty:
        return df
    for col in [f"c{i}" for i in range(1, 10)]:
        if col not in df.columns:
            df[col] = 0
    df["admission_scope"] = np.where(df["stat_id"].eq("s002002"), "first_generation", "all")
    df["admit_year"] = pd.to_numeric(df["param_admityear"], errors="coerce") + 2500
    df["issued_male"] = df["c1"].fillna(0)
    df["issued_female"] = df["c2"].fillna(0)
    df["issued_total"] = df["c3"].fillna(0)
    df["waived_male"] = df["c4"].fillna(0)
    df["waived_female"] = df["c5"].fillna(0)
    df["waived_total"] = df["c6"].fillna(0)
    df["remaining_male"] = df["c7"].fillna(0)
    df["remaining_female"] = df["c8"].fillna(0)
    df["remaining_total"] = df["c9"].fillna(0)
    df["waive_rate"] = np.where(df["issued_total"] > 0, df["waived_total"] / df["issued_total"], np.nan)
    df["yield_rate"] = np.where(df["issued_total"] > 0, df["remaining_total"] / df["issued_total"], np.nan)
    keep = [
        "admission_scope",
        "admit_year",
        "faculty_code",
        "faculty_name",
        "issued_male",
        "issued_female",
        "issued_total",
        "waived_male",
        "waived_female",
        "waived_total",
        "remaining_male",
        "remaining_female",
        "remaining_total",
        "waive_rate",
        "yield_rate",
        "source_file",
    ]
    return df[keep].sort_values(["admission_scope", "admit_year", "remaining_total"], ascending=[True, False, False])


def build_graduates(all_stats: pd.DataFrame) -> pd.DataFrame:
    df = all_stats.loc[all_stats["stat_id"].isin(["s003001", "s003002", "s003003"])].copy()
    if df.empty:
        return df
    df["graduate_count"] = df["total_count"].fillna(0)
    df["admit_year"] = pd.to_numeric(df.get("param_admityear"), errors="coerce") + 2500
    df["graduation_year"] = pd.to_numeric(df.get("param_year"), errors="coerce")
    df["graduation_semester"] = df.get("param_semester")
    keep = [
        c
        for c in [
            "stat_id",
            "faculty_code",
            "faculty_name",
            "program_code",
            "program_name",
            "admit_year",
            "graduation_year",
            "graduation_semester",
            "graduate_count",
            "source_file",
        ]
        if c in df.columns
    ]
    return df[keep].sort_values(["graduation_year", "graduation_semester", "graduate_count"], ascending=[False, False, False])


def build_historical_students(all_stats: pd.DataFrame) -> pd.DataFrame:
    df = all_stats.loc[all_stats["stat_id"].eq("s004001")].copy()
    if df.empty:
        return df
    df["student_count"] = df["total_count"].fillna(0)
    df["academic_year"] = pd.to_numeric(df["param_year"], errors="coerce")
    df["semester"] = df["param_semester"].astype("string")
    keep = [
        "academic_year",
        "semester",
        "faculty_code",
        "faculty_name",
        "student_count",
        "source_file",
    ]
    return df[keep].sort_values(["academic_year", "semester", "student_count"], ascending=[False, False, False])


def build_nationality(all_stats: pd.DataFrame) -> pd.DataFrame:
    df = all_stats.loc[all_stats["stat_id"].eq("s001012")].copy()
    if df.empty:
        return df
    df["student_count"] = df["total_count"].fillna(0)
    if "nationality_th" in df.columns:
        df["nationality_name"] = df["nationality_th"]
    keep = [
        "nationality_id",
        "iso_alpha3",
        "nationality_name",
        "is_international",
        "student_count",
        "param_year",
        "param_semester",
        "source_file",
    ]
    return df[[c for c in keep if c in df.columns]].sort_values("student_count", ascending=False)


def build_nationality_faculty(all_stats: pd.DataFrame) -> pd.DataFrame:
    df = all_stats.loc[all_stats["stat_id"].eq("s001016")].copy()
    if df.empty:
        return df
    if "param_nat" not in df.columns:
        return pd.DataFrame()
    df = df.loc[df["param_nat"].astype(str).ne("999")].copy()
    if df.empty:
        return pd.DataFrame()

    nat = all_stats.loc[all_stats["stat_id"].eq("s001012")].copy()
    if not nat.empty and {"nationality_id", "nationality_th"}.issubset(nat.columns):
        nat_lookup = nat[["nationality_id", "nationality_th", "iso_alpha3"]].drop_duplicates()
    else:
        nat_lookup = pd.DataFrame(columns=["nationality_id", "nationality_th", "iso_alpha3"])

    df["nationality_id"] = df["param_nat"].astype(str).str.upper()
    df["student_count"] = pd.to_numeric(df["total_count"], errors="coerce").fillna(0)
    df = df.drop(columns=[c for c in ["nationality_th", "iso_alpha3"] if c in df.columns])
    df = df.merge(nat_lookup, on="nationality_id", how="left")
    df["nationality_name"] = df["nationality_th"].fillna(df["nationality_id"])
    keep = [
        "nationality_id",
        "iso_alpha3",
        "nationality_name",
        "faculty_code",
        "faculty_name",
        "student_count",
        "param_year",
        "param_semester",
        "source_file",
    ]
    return df[[c for c in keep if c in df.columns]].loc[df["student_count"] > 0].sort_values("student_count", ascending=False)


def build_over_program(all_stats: pd.DataFrame) -> pd.DataFrame:
    df = all_stats.loc[all_stats["stat_id"].eq("s001010")].copy()
    if df.empty:
        return df
    df["current_students"] = pd.to_numeric(df.get("c1"), errors="coerce").fillna(0)
    df["over_program_students"] = pd.to_numeric(df.get("c2"), errors="coerce").fillna(0)
    df["over_program_rate"] = np.where(df["current_students"] > 0, df["over_program_students"] / df["current_students"], np.nan)
    keep = [
        c
        for c in [
            "faculty_code",
            "faculty_name",
            "level",
            "program_name",
            "curriculum_type",
            "current_students",
            "over_program_students",
            "over_program_rate",
            "source_file",
        ]
        if c in df.columns
    ]
    return df[keep].sort_values("over_program_rate", ascending=False)


def build_transfer(all_stats: pd.DataFrame) -> pd.DataFrame:
    df = all_stats.loc[all_stats["stat_id"].eq("s001017")].copy()
    if df.empty:
        return df
    df["transfer_in"] = pd.to_numeric(df.get("c1"), errors="coerce").fillna(0)
    df["transfer_out"] = pd.to_numeric(df.get("c2"), errors="coerce").fillna(0)
    df["net_transfer"] = df["transfer_in"] - df["transfer_out"]
    keep = [
        c
        for c in [
            "faculty_code",
            "faculty_name",
            "program_code",
            "program_name",
            "transfer_in",
            "transfer_out",
            "net_transfer",
            "source_file",
        ]
        if c in df.columns
    ]
    return df[keep].sort_values("transfer_out", ascending=False)


def build_quality(all_stats: pd.DataFrame) -> pd.DataFrame:
    if all_stats.empty:
        return pd.DataFrame(columns=["stat_id", "files", "rows", "errors"])
    return (
        all_stats.groupby("stat_id", dropna=False)
        .agg(files=("source_file", "nunique"), rows=("source_file", "size"), errors=("error", lambda s: ", ".join(sorted({str(x) for x in s if str(x)}))))
        .reset_index()
        .sort_values("stat_id")
    )


def write_csv(df: pd.DataFrame, name: str) -> Path:
    path = PROCESSED_DIR / name
    df.to_csv(path, index=False)
    return path


def write_data_dictionary() -> Path:
    rows = [
        ("current_faculty.csv", "current_students", "Active students by faculty from s001001 latest current semester."),
        ("admission_funnel.csv", "issued_total", "Students issued CMU student IDs from s002001/s002002."),
        ("admission_funnel.csv", "waived_total", "Issued-ID students who waived/surrendered admission rights."),
        ("admission_funnel.csv", "remaining_total", "Issued-ID students remaining after waivers; treated as realized intake."),
        ("admission_funnel.csv", "waive_rate", "waived_total / issued_total."),
        ("admission_funnel.csv", "yield_rate", "remaining_total / issued_total."),
        ("historical_students.csv", "student_count", "Historical enrolled/resting students by faculty, academic year, and semester from s004001."),
        ("graduates.csv", "graduate_count", "Graduated students from s003001/s003002/s003003."),
        ("nationality.csv", "is_international", "True for non-Thai non-administrative nationality codes."),
        ("over_program_students.csv", "over_program_rate", "over_program_students / current_students from s001010."),
        ("transfer_students.csv", "net_transfer", "transfer_in - transfer_out from s001017."),
        ("all_stats_long.csv", "total_count", "Best-effort row total; usually the highest cN column except special risk tables."),
    ]
    df = pd.DataFrame(rows, columns=["table", "field", "definition"])
    return write_csv(df, "data_dictionary.csv")


def clean(raw_dir: Path = RAW_DIR) -> dict[str, Path]:
    ensure_dirs()
    files = iter_raw_stat_files()
    if not files:
        raise FileNotFoundError(f"No raw API files found in {raw_dir}. Run `python -m src.scrape` first.")

    cleaned = [clean_one(path) for path in files]
    all_stats = pd.concat(cleaned, ignore_index=True, sort=False) if cleaned else pd.DataFrame()

    outputs: dict[str, Path] = {}
    outputs["all_stats_long"] = write_csv(all_stats, "all_stats_long.csv")
    outputs["current_faculty"] = write_csv(build_current_faculty(all_stats), "current_faculty.csv")
    outputs["undergraduate_programs"] = write_csv(build_programs(all_stats, "s001004"), "undergraduate_programs.csv")
    outputs["graduate_programs"] = write_csv(build_programs(all_stats, "s001007"), "graduate_programs.csv")
    outputs["admission_funnel"] = write_csv(build_admission(all_stats), "admission_funnel.csv")
    outputs["graduates"] = write_csv(build_graduates(all_stats), "graduates.csv")
    outputs["historical_students"] = write_csv(build_historical_students(all_stats), "historical_students.csv")
    outputs["historical_graduate_programs"] = write_csv(build_programs(all_stats, "s004005", "student_count"), "historical_graduate_programs.csv")
    outputs["nationality"] = write_csv(build_nationality(all_stats), "nationality.csv")
    outputs["nationality_faculty"] = write_csv(build_nationality_faculty(all_stats), "nationality_faculty.csv")
    outputs["over_program_students"] = write_csv(build_over_program(all_stats), "over_program_students.csv")
    outputs["transfer_students"] = write_csv(build_transfer(all_stats), "transfer_students.csv")
    outputs["data_quality"] = write_csv(build_quality(all_stats), "data_quality.csv")
    outputs["data_dictionary"] = write_data_dictionary()
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean cached CMU registry statistic JSON into analysis tables.")
    return parser.parse_args()


def main() -> None:
    parse_args()
    outputs = clean()
    print("Wrote processed tables:")
    for name, path in outputs.items():
        print(f"- {name}: {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
