from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.metrics import faculty_metrics, load_data
from src.ui import apply_theme, data_missing_warning, page_header


st.set_page_config(page_title="Retention and Progress Risk", layout="wide")
apply_theme()


@st.cache_data(show_spinner=False)
def cached_data():
    return load_data()


data = cached_data()
page_header("Retention and Progress Risk", "Over-program-length, transfer, graduation output, and unusually high-risk flags.")
data_missing_warning({"over_program_students": data["over_program"], "transfer_students": data["transfer"]})

metrics = faculty_metrics(data)
if metrics.empty:
    st.stop()

faculties = sorted(metrics["faculty_name"].dropna().astype(str).unique())
selected = st.sidebar.multiselect("Faculty / คณะ", faculties)
if selected:
    metrics = metrics.loc[metrics["faculty_name"].isin(selected)]

cols = st.columns(4)
cols[0].metric("Median over-program rate", f"{metrics['over_program_rate'].median(skipna=True):.1%}")
cols[1].metric("Median transfer out", f"{metrics['transfer_out'].median(skipna=True):,.0f}")
cols[2].metric("Median grad output ratio", f"{metrics['graduation_output_ratio'].median(skipna=True):.1%}")
cols[3].metric("Risk-flag faculties", f"{int(metrics['risk_flag'].sum())}")

left, right = st.columns(2)
with left:
    st.subheader("Over-Program-Length Rate / เรียนเกินหลักสูตร")
    top = metrics.sort_values("over_program_rate", ascending=False).head(20)
    fig = px.bar(
        top,
        x="over_program_rate",
        y="faculty_name",
        orientation="h",
        color="over_program_rate",
        color_continuous_scale=["#F5F1FA", "#4B1D80"],
        labels={"over_program_rate": "Over-program-length rate", "faculty_name": "Faculty"},
    )
    fig.update_layout(height=480, yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, width="stretch")

with right:
    st.subheader("Transfer Out / ย้ายออก")
    top = metrics.sort_values("transfer_out", ascending=False).head(20)
    fig = px.bar(
        top,
        x="transfer_out",
        y="faculty_name",
        orientation="h",
        color="net_transfer",
        color_continuous_scale=["#BFA14A", "#F5F1FA", "#4B1D80"],
        labels={"transfer_out": "Transfer out", "faculty_name": "Faculty", "net_transfer": "Net transfer"},
    )
    fig.update_layout(height=480, yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, width="stretch")

st.subheader("Risk Ranking / อันดับความเสี่ยง")
risk_cols = [
    "faculty_name",
    "current_students",
    "waive_rate",
    "over_program_rate",
    "transfer_out",
    "net_transfer",
    "graduation_output_ratio",
    "growth_rate",
    "risk_score",
    "risk_zscore",
    "risk_flag",
]
st.dataframe(metrics[[c for c in risk_cols if c in metrics.columns]].sort_values("risk_score", ascending=False), width="stretch", hide_index=True)

st.subheader("Program-Level Over-Program-Length / รายหลักสูตร")
over = data["over_program"]
if over.empty:
    st.info("No program-level over-program data.")
else:
    if selected:
        over = over.loc[over["faculty_name"].isin(selected)]
    cols = [c for c in ["faculty_name", "level", "program_name", "curriculum_type", "current_students", "over_program_students", "over_program_rate"] if c in over.columns]
    st.dataframe(over[cols].sort_values("over_program_rate", ascending=False).head(50), width="stretch", hide_index=True)
