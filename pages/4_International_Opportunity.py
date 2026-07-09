from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.metrics import faculty_metrics, load_data
from src.ui import apply_theme, data_missing_warning, display_dataframe, explain, page_header


st.set_page_config(page_title="International Opportunity", layout="wide")
apply_theme()


@st.cache_data(show_spinner=False)
def cached_data():
    return load_data()


data = cached_data()
nationality = data["nationality"].copy()
nat_fac = data["nationality_faculty"].copy()
page_header("International Opportunity / โอกาสนักศึกษานานาชาติ", "Nationality mix, faculty concentration, and international growth opportunity.")
explain(
    "This page shows where international students currently come from and which faculties may have room to grow international recruitment."
)
data_missing_warning({"nationality": nationality})

if nationality.empty:
    st.stop()

nationality["student_count"] = pd.to_numeric(nationality["student_count"], errors="coerce").fillna(0)
nationality["is_international_bool"] = nationality["is_international"].astype(str).str.lower().isin(["true", "1"])
intl = nationality.loc[nationality["is_international_bool"]].copy()

left, right = st.columns([1.15, 0.85])
with left:
    st.subheader("Choropleth by Nationality / แผนที่สัญชาติ")
    explain("Darker countries have more current CMU students by nationality.")
    map_df = intl.loc[intl["iso_alpha3"].notna() & intl["student_count"].gt(0)]
    fig = px.choropleth(
        map_df,
        locations="iso_alpha3",
        color="student_count",
        hover_name="nationality_name",
        color_continuous_scale=["#F5F1FA", "#6E35A7", "#4B1D80"],
        labels={"student_count": "Students"},
        hover_data={"student_count": ":,.0f", "iso_alpha3": False},
    )
    fig.update_layout(title="International Students by Nationality", height=520, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, width="stretch")

with right:
    st.subheader("Top 10 International Nationalities")
    explain("Largest nationality groups can guide recruitment, partnerships, and student-support language planning.")
    top = intl.sort_values("student_count", ascending=False).head(10)
    fig = px.bar(
        top,
        x="student_count",
        y="nationality_name",
        orientation="h",
        color="student_count",
        color_continuous_scale=["#F5F1FA", "#4B1D80"],
        labels={"student_count": "Students", "nationality_name": "Nationality"},
        hover_data={"student_count": ":,.0f"},
    )
    fig.update_layout(title="Top International Nationality Groups", height=520, yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, width="stretch")

st.subheader("Nationality x Faculty Heatmap / สัญชาติ x คณะ")
explain("This heatmap shows which faculties already attract students from each major international nationality group.")
if nat_fac.empty or not {"faculty_name", "nationality_name", "student_count"}.issubset(nat_fac.columns):
    st.info("Nationality-faculty detail is missing. Run `python -m src.scrape` and `python -m src.clean` to cache nationality-specific faculty tables.")
else:
    nat_fac["student_count"] = pd.to_numeric(nat_fac["student_count"], errors="coerce").fillna(0)
    label_col = "nationality_name"
    top_labels = nat_fac.groupby(label_col)["student_count"].sum().sort_values(ascending=False).head(12).index
    top_faculties = nat_fac.groupby("faculty_name")["student_count"].sum().sort_values(ascending=False).head(18).index
    heat = nat_fac.loc[nat_fac[label_col].isin(top_labels) & nat_fac["faculty_name"].isin(top_faculties)]
    pivot = heat.pivot_table(index="faculty_name", columns=label_col, values="student_count", aggfunc="sum", fill_value=0)
    fig = px.imshow(
        pivot,
        aspect="auto",
        color_continuous_scale=["#F5F1FA", "#6E35A7", "#4B1D80"],
        labels={"x": "Nationality", "y": "Faculty", "color": "Students"},
    )
    fig.update_layout(title="Faculty Concentration by Nationality", height=560, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, width="stretch")

st.subheader("International Opportunity Score / คะแนนโอกาสนานาชาติ")
explain("The score is higher for faculties that are large, have relatively low international share, and still show growth momentum.")
fm = faculty_metrics(data)
if fm.empty:
    st.info("Faculty metrics are missing.")
else:
    work = fm.copy()
    work["current_rank"] = pd.to_numeric(work["current_students"], errors="coerce").rank(pct=True)
    work["low_intl_rank"] = (1 - pd.to_numeric(work["international_program_share"], errors="coerce").fillna(0)).rank(pct=True)
    work["growth_rank"] = pd.to_numeric(work["growth_rate"], errors="coerce").fillna(0).rank(pct=True)
    work["international_opportunity_score"] = work[["current_rank", "low_intl_rank", "growth_rank"]].mean(axis=1)
    show = work.sort_values("international_opportunity_score", ascending=False)[
        ["faculty_name", "current_students", "international_program_share", "growth_rate", "international_opportunity_score"]
    ].head(20)
    display_dataframe(show)

with st.expander("About this score / คำอธิบายคะแนน"):
    st.markdown(
        """
        - **Current-student scale** rewards faculties that can add many students if recruitment improves.
        - **Low international share** highlights faculties with room to diversify.
        - **Growth momentum** avoids pushing recruitment into areas already shrinking sharply.
        - Faculty-level score uses international-program share as a proxy when nationality-by-faculty detail is sparse.
        """
    )
