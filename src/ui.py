from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from src.metrics import fmt_number, fmt_pct


CMU_PURPLE = "#4B1D80"
CMU_GOLD = "#BFA14A"


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --cmu-purple: #4B1D80;
            --cmu-purple-2: #6E35A7;
            --cmu-gold: #BFA14A;
            --cmu-ink: #1F1830;
            --cmu-muted: #6B6675;
            --cmu-soft: #F5F1FA;
            --cmu-line: #E7DFF1;
        }
        .stApp {
            background: #FBFAFD;
            color: var(--cmu-ink);
        }
        .block-container {
            padding-top: 1.6rem;
            padding-bottom: 2.5rem;
        }
        section[data-testid="stSidebar"] {
            background: #F3EEF8;
        }
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p {
            color: var(--cmu-ink);
        }
        h1, h2, h3 {
            color: var(--cmu-purple);
            letter-spacing: 0;
        }
        h2, h3 {
            margin-top: 1.1rem;
        }
        div[data-testid="stMetric"] {
            background: white;
            border: 1px solid var(--cmu-line);
            border-left: 5px solid var(--cmu-purple);
            border-radius: 8px;
            padding: 0.9rem 1rem;
            box-shadow: 0 1px 8px rgba(75, 29, 128, 0.06);
            min-width: 0;
        }
        div[data-testid="stMetricLabel"] {
            color: var(--cmu-muted);
        }
        div[data-testid="stMetricValue"] {
            color: var(--cmu-ink);
            font-size: clamp(1.25rem, 1.8vw, 1.75rem) !important;
            line-height: 1.15;
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            font-variant-numeric: tabular-nums;
        }
        .cmu-kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
            gap: 0.85rem;
            margin: 0.75rem 0 1.1rem;
        }
        .cmu-kpi-card {
            min-width: 0;
            background: #FFFFFF;
            border: 1px solid var(--cmu-line);
            border-left: 5px solid var(--cmu-purple);
            border-radius: 8px;
            padding: 0.85rem 0.95rem;
            box-shadow: 0 1px 8px rgba(75, 29, 128, 0.06);
        }
        .cmu-kpi-label {
            color: var(--cmu-muted);
            font-size: 0.78rem;
            font-weight: 650;
            line-height: 1.25;
            margin-bottom: 0.35rem;
        }
        .cmu-kpi-value {
            color: var(--cmu-ink);
            font-size: clamp(1.35rem, 2vw, 1.85rem);
            line-height: 1.1;
            font-weight: 760;
            font-variant-numeric: tabular-nums;
            white-space: normal;
            overflow: visible;
            text-overflow: clip;
        }
        .cmu-kpi-caption {
            color: var(--cmu-muted);
            font-size: 0.74rem;
            line-height: 1.25;
            margin-top: 0.35rem;
        }
        .cmu-note {
            border-left: 4px solid var(--cmu-gold);
            background: #FFF9E8;
            padding: 0.75rem 1rem;
            border-radius: 6px;
            color: #3D3320;
        }
        .cmu-section-note {
            color: var(--cmu-muted);
            font-size: 0.95rem;
            line-height: 1.45;
            margin: -0.25rem 0 0.75rem;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid var(--cmu-line);
            border-radius: 8px;
            overflow: hidden;
        }
        @media (max-width: 900px) {
            .cmu-kpi-grid {
                grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
            }
            .cmu-kpi-card {
                padding: 0.75rem 0.8rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


LABELS = {
    "academic_year": "Academic Year / ปีการศึกษา",
    "admission_scope": "Admission Scope / กลุ่มรับเข้า",
    "admit_year": "Admission Year / ปีรหัสนักศึกษา",
    "additional_students": "Estimated Additional Students / จำนวนนักศึกษาที่คาดว่าจะเพิ่ม",
    "cagr": "CAGR / อัตราเติบโตเฉลี่ยต่อปี",
    "chi2": "Chi-Square Statistic",
    "cluster": "Cluster",
    "cluster_label": "Cluster Label / กลุ่มคณะ",
    "coef": "Coefficient",
    "current_rank": "Current-Student Scale Rank",
    "current_students": "Current Students / นักศึกษาปัจจุบัน",
    "curriculum_type": "Curriculum Type / ประเภทหลักสูตร",
    "dispersion": "Dispersion",
    "dof": "Degrees of Freedom",
    "expected_remained": "Expected Remained / คงเหลือที่คาดไว้",
    "expected_waived": "Expected Waived / สละสิทธิ์ที่คาดไว้",
    "faculties": "Number of Faculties / จำนวนคณะ",
    "faculty_code": "Faculty Code / รหัสคณะ",
    "faculty_name": "Faculty / คณะ",
    "female_students": "Female Students / นักศึกษาหญิง",
    "files": "Cached Files / ไฟล์แคช",
    "first_count": "First Observed Count",
    "gender": "Gender / เพศ",
    "graduate_count": "Graduates / ผู้สำเร็จการศึกษา",
    "graduation_output_ratio": "Graduation Output Ratio / อัตราผลผลิตบัณฑิต",
    "graduation_semester": "Graduation Semester / ภาคเรียนที่สำเร็จ",
    "graduation_year": "Graduation Year / ปีที่สำเร็จ",
    "growth_rate": "Student Growth Rate / อัตราเติบโตนักศึกษา",
    "international_opportunity_score": "International Opportunity Score / คะแนนโอกาสต่างชาติ",
    "international_program_share": "International Share / สัดส่วนนักศึกษาต่างชาติ",
    "international_program_students": "International-Program Students",
    "is_international": "International Nationality / เป็นต่างชาติ",
    "issued": "Issued IDs / ออกรหัส",
    "issued_female": "Issued IDs - Female",
    "issued_male": "Issued IDs - Male",
    "issued_total": "Issued IDs / จำนวนนักศึกษาที่ออกรหัส",
    "last_count": "Latest Observed Count",
    "level": "Level / ระดับการศึกษา",
    "male_students": "Male Students / นักศึกษาชาย",
    "median_growth": "Median Growth Rate",
    "median_waive": "Median Waive Rate",
    "nationality_id": "Nationality Code",
    "nationality_name": "Nationality / สัญชาติ",
    "net_transfer": "Net Transfer / ย้ายเข้าสุทธิ",
    "new_remaining_total": "New Remaining Students After Scenario / นักศึกษาใหม่คงเหลือหลังจำลอง",
    "odds_ratio": "Odds Ratio",
    "over_current_students": "Current Students in Program-Risk Table",
    "over_program_rate": "Over-Program Rate / อัตราเรียนเกินหลักสูตร",
    "over_program_students": "Over-Program Students / นักศึกษาเรียนเกินหลักสูตร",
    "p_value": "p-value",
    "param_admityear": "Admission-Year Parameter",
    "priority_score": "Priority Score / คะแนนความสำคัญ",
    "program_code": "Program Code / รหัสหลักสูตร",
    "program_name": "Program / หลักสูตร",
    "quadrant": "Growth-Leakage Quadrant / กลุ่มเติบโต-รั่วไหล",
    "rate_ratio": "Rate Ratio",
    "recommended_action": "Recommended Action / แนวทางแนะนำ",
    "regular_program_students": "Regular Program Students",
    "remained": "Remained / คงเหลือ",
    "remaining": "Remaining / คงเหลือ",
    "remaining_female": "Remaining - Female",
    "remaining_male": "Remaining - Male",
    "remaining_total": "Remaining Students / นักศึกษาคงเหลือ",
    "risk_flag": "Unusually High Risk Flag / ธงความเสี่ยงสูงผิดปกติ",
    "risk_score": "Risk Score / คะแนนความเสี่ยง",
    "risk_zscore": "Risk z-score / ค่ามาตรฐานความเสี่ยง",
    "rows": "Rows / จำนวนแถว",
    "scenario": "Scenario / สถานการณ์จำลอง",
    "semester": "Semester / ภาคเรียน",
    "special_program_students": "Special Program Students",
    "student_count": "Students / จำนวนนักศึกษา",
    "students": "Students / จำนวนนักศึกษา",
    "term": "Model Term / ตัวแปรในโมเดล",
    "transfer_in": "Transfer In / ย้ายเข้า",
    "transfer_out": "Transfer Out / ย้ายออก",
    "transfer_out_rate": "Transfer-Out Share / สัดส่วนย้ายออก",
    "waive_rate": "Waive Rate / อัตราสละสิทธิ์",
    "waived": "Waived / สละสิทธิ์",
    "waived_female": "Waived - Female",
    "waived_male": "Waived - Male",
    "waived_total": "Waived Students / นักศึกษาสละสิทธิ์",
    "yield_rate": "Yield Rate / อัตราคงเหลือ",
}

COUNT_COLUMNS = {
    "additional_students",
    "current_students",
    "expected_remained",
    "expected_waived",
    "faculties",
    "female_students",
    "files",
    "first_count",
    "graduate_count",
    "international_program_students",
    "issued",
    "issued_female",
    "issued_male",
    "issued_total",
    "last_count",
    "male_students",
    "new_remaining_total",
    "over_current_students",
    "over_program_students",
    "regular_program_students",
    "remained",
    "remaining",
    "remaining_female",
    "remaining_male",
    "remaining_total",
    "rows",
    "special_program_students",
    "student_count",
    "students",
    "transfer_in",
    "transfer_out",
    "waived",
    "waived_female",
    "waived_male",
    "waived_total",
}

PERCENT_COLUMNS = {
    "cagr",
    "graduation_output_ratio",
    "growth_rate",
    "international_program_share",
    "low_intl_rank",
    "median_growth",
    "median_waive",
    "over_program_rate",
    "transfer_out_rate",
    "waive_rate",
    "yield_rate",
}


def page_header(title: str, subtitle: str | None = None) -> None:
    st.title(title)
    if subtitle:
        st.caption(subtitle)


def data_missing_warning(required: dict[str, pd.DataFrame]) -> None:
    missing = [name for name, df in required.items() if df.empty]
    load_errors = [f"{name}: {df.attrs.get('load_error')}" for name, df in required.items() if df.attrs.get("load_error")]
    if missing:
        st.warning(
            "Missing or empty processed tables: "
            + ", ".join(missing)
            + ". To regenerate them, run `python -m src.scrape --years-back 5 --delay 1.2` and then `python -m src.clean` from the project root."
        )
    if load_errors:
        with st.expander("Data loading warnings / คำเตือนการโหลดข้อมูล"):
            for error in load_errors:
                st.write(f"- {error}")


def faculty_multiselect(df: pd.DataFrame, label: str = "Faculty / คณะ") -> list[str]:
    if df.empty or "faculty_name" not in df.columns:
        return []
    faculties = sorted(df["faculty_name"].dropna().astype(str).unique())
    return st.sidebar.multiselect(label, faculties)


def year_filter(df: pd.DataFrame, column: str = "academic_year") -> list[int]:
    if df.empty or column not in df.columns:
        return []
    years = sorted(pd.to_numeric(df[column], errors="coerce").dropna().astype(int).unique(), reverse=True)
    return st.sidebar.multiselect("Academic year / ปีการศึกษา", years, default=years[: min(3, len(years))])


def metric_card(label: str, value: float | int | None, kind: str = "number") -> None:
    if kind == "pct":
        st.metric(label, fmt_pct(value))
    else:
        st.metric(label, fmt_number(value))


def metric_grid(cards: list[dict[str, object]]) -> None:
    items = []
    for card in cards:
        label = str(card.get("label", ""))
        kind = str(card.get("kind", "number"))
        value = card.get("value")
        display_value = fmt_pct(value) if kind == "pct" else fmt_number(value)  # type: ignore[arg-type]
        caption = str(card.get("caption", ""))
        caption_html = f"<div class='cmu-kpi-caption'>{escape(caption)}</div>" if caption else ""
        items.append(
            "<div class='cmu-kpi-card'>"
            f"<div class='cmu-kpi-label'>{escape(label)}</div>"
            f"<div class='cmu-kpi-value'>{escape(display_value)}</div>"
            f"{caption_html}"
            "</div>"
        )
    st.markdown("<div class='cmu-kpi-grid'>" + "".join(items) + "</div>", unsafe_allow_html=True)


def label_for(column: str) -> str:
    if column in LABELS:
        return LABELS[column]
    return column.replace("_", " ").strip().title()


def explain(text: str) -> None:
    st.markdown(f"<div class='cmu-section-note'>{escape(text)}</div>", unsafe_allow_html=True)


def _as_number(value: object) -> float | None:
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_cell(column: str, value: object) -> object:
    if pd.isna(value):
        return ""
    if column == "risk_flag":
        return "Yes" if str(value).lower() in {"true", "1"} else "No"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    number = _as_number(value)
    if number is None:
        return value
    if column in {"admit_year", "academic_year", "graduation_year", "param_admityear", "semester", "cluster", "dof"}:
        return f"{number:.0f}"
    if column == "p_value":
        return f"{number:.2e}" if abs(number) < 0.001 else f"{number:.3f}"
    if column in {"coef", "odds_ratio", "rate_ratio", "risk_score", "risk_zscore", "priority_score", "international_opportunity_score", "dispersion"}:
        return f"{number:.3f}"
    if column in PERCENT_COLUMNS:
        return f"{number:.3%}"
    if column in COUNT_COLUMNS:
        return f"{number:,.0f}"
    if float(number).is_integer():
        return f"{number:,.0f}"
    return f"{number:,.3f}"


def format_dataframe_for_display(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    label_overrides: dict[str, str] | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    work = df[[c for c in (columns or list(df.columns)) if c in df.columns]].copy()
    formatted = pd.DataFrame(index=work.index)
    for col in work.columns:
        formatted[col] = work[col].map(lambda value, c=col: _format_cell(c, value))
    labels = {col: (label_overrides or {}).get(col, label_for(col)) for col in formatted.columns}
    return formatted.rename(columns=labels)


def display_dataframe(
    df: pd.DataFrame,
    *,
    columns: list[str] | None = None,
    label_overrides: dict[str, str] | None = None,
    height: int | str | None = None,
) -> None:
    if df.empty:
        st.info("No rows available for the current filters.")
        return
    kwargs = {"width": "stretch", "hide_index": True, "height": height or "auto"}
    st.dataframe(format_dataframe_for_display(df, columns=columns, label_overrides=label_overrides), **kwargs)


def note(text: str) -> None:
    st.markdown(f"<div class='cmu-note'>{text}</div>", unsafe_allow_html=True)
