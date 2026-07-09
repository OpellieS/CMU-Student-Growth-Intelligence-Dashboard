from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.metrics import faculty_metrics, load_data
from src.models import cluster_faculties, count_regression
from src.ui import apply_theme, data_missing_warning, page_header


st.set_page_config(page_title="Faculty and Program Growth", layout="wide")
apply_theme()


@st.cache_data(show_spinner=False)
def cached_data():
    return load_data()


data = cached_data()
page_header("Faculty and Program Growth", "Growth, waiver leakage, program scale, and interpretable faculty clusters.")
data_missing_warning({"current_faculty": data["current_faculty"], "historical_students": data["history"]})

metrics = faculty_metrics(data)
history = data["history"]

if metrics.empty:
    st.stop()

faculties = sorted(metrics["faculty_name"].dropna().astype(str).unique())
selected = st.sidebar.multiselect("Faculty / คณะ", faculties)
if selected:
    metrics = metrics.loc[metrics["faculty_name"].isin(selected)]
    history = history.loc[history["faculty_name"].isin(selected)] if not history.empty else history

left, right = st.columns([1.15, 0.85])
with left:
    st.subheader("Faculty x Year Heatmap / คณะ x ปี")
    if history.empty:
        st.info("Historical student table is missing.")
    else:
        heat = (
            history.assign(academic_year=pd.to_numeric(history["academic_year"], errors="coerce"))
            .groupby(["faculty_name", "academic_year"], as_index=False)["student_count"]
            .sum()
        )
        top_faculties = metrics.sort_values("current_students", ascending=False)["faculty_name"].head(18)
        heat = heat.loc[heat["faculty_name"].isin(top_faculties)]
        pivot = heat.pivot(index="faculty_name", columns="academic_year", values="student_count").fillna(0)
        fig = px.imshow(
            pivot,
            aspect="auto",
            color_continuous_scale=["#F5F1FA", "#6E35A7", "#4B1D80"],
            labels={"x": "Academic year", "y": "Faculty", "color": "Students"},
        )
        fig.update_layout(height=520, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, width="stretch")

with right:
    st.subheader("Program Ranking / อันดับสาขา")
    program_source = st.radio("Level", ["Undergraduate", "Graduate"], horizontal=True)
    programs = data["undergraduate_programs"] if program_source == "Undergraduate" else data["graduate_programs"]
    if programs.empty:
        st.info("Program table is missing.")
    else:
        if selected and "faculty_name" in programs.columns:
            programs = programs.loc[programs["faculty_name"].isin(selected)]
        keep = [c for c in ["faculty_name", "program_name", "current_students", "param_admityear"] if c in programs.columns]
        st.dataframe(programs[keep].head(20), width="stretch", hide_index=True)

st.subheader("Growth-Leakage Bubble / ฟองสบู่การเติบโตและการรั่วไหล")
y_metric = st.selectbox("Y axis", ["waive_rate", "over_program_rate", "graduation_output_ratio"])
fig = px.scatter(
    metrics,
    x="growth_rate",
    y=y_metric,
    size="current_students",
    color="quadrant",
    hover_name="faculty_name",
    labels={
        "growth_rate": "Student growth rate",
        "waive_rate": "Waive rate",
        "over_program_rate": "Over-program-length rate",
        "graduation_output_ratio": "Graduation output ratio",
        "current_students": "Current students",
    },
    color_discrete_sequence=["#4B1D80", "#6E35A7", "#BFA14A", "#9472B8"],
)
fig.update_layout(height=520, margin=dict(l=10, r=10, t=40, b=10))
st.plotly_chart(fig, width="stretch")

st.subheader("Quadrant Interpretation")
quad = (
    metrics.groupby("quadrant", as_index=False)
    .agg(faculties=("faculty_name", "count"), students=("current_students", "sum"), median_waive=("waive_rate", "median"), median_growth=("growth_rate", "median"))
    .sort_values("faculties", ascending=False)
)
st.dataframe(quad, width="stretch", hide_index=True)

st.subheader("Clustering / จัดกลุ่มคณะ")
clusters = cluster_faculties(data)
if selected and not clusters.empty:
    clusters = clusters.loc[clusters["faculty_name"].isin(selected)]
cluster_cols = [c for c in ["faculty_name", "cluster_label", "current_students", "growth_rate", "waive_rate", "over_program_rate", "international_program_share"] if c in clusters.columns]
st.dataframe(clusters[cluster_cols].sort_values(["cluster_label", "current_students"], ascending=[True, False]), width="stretch", hide_index=True)

st.subheader("Count Regression / Poisson or Negative Binomial")
count_model = count_regression(data["history"])
if count_model["ok"]:
    st.caption(f"Family: {count_model['family']}; dispersion: {count_model['dispersion']:.2f}. {count_model['message']}")
    st.dataframe(count_model["table"].head(30), width="stretch", hide_index=True)
else:
    st.info(count_model["message"])
