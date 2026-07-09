from __future__ import annotations

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
        }
        .stApp {
            background: #FBFAFD;
            color: var(--cmu-ink);
        }
        section[data-testid="stSidebar"] {
            background: #F3EEF8;
        }
        h1, h2, h3 {
            color: var(--cmu-purple);
            letter-spacing: 0;
        }
        div[data-testid="stMetric"] {
            background: white;
            border: 1px solid #E7DFF1;
            border-left: 5px solid var(--cmu-purple);
            border-radius: 8px;
            padding: 0.9rem 1rem;
            box-shadow: 0 1px 8px rgba(75, 29, 128, 0.06);
        }
        div[data-testid="stMetricLabel"] {
            color: var(--cmu-muted);
        }
        .cmu-note {
            border-left: 4px solid var(--cmu-gold);
            background: #FFF9E8;
            padding: 0.75rem 1rem;
            border-radius: 6px;
            color: #3D3320;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str | None = None) -> None:
    st.title(title)
    if subtitle:
        st.caption(subtitle)


def data_missing_warning(required: dict[str, pd.DataFrame]) -> None:
    missing = [name for name, df in required.items() if df.empty]
    if missing:
        st.warning(
            "Missing or empty processed tables: "
            + ", ".join(missing)
            + ". Run `python -m src.scrape` then `python -m src.clean`."
        )


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


def note(text: str) -> None:
    st.markdown(f"<div class='cmu-note'>{text}</div>", unsafe_allow_html=True)
