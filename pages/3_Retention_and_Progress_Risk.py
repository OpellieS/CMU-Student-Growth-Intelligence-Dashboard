from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.metrics import faculty_metrics, load_data
from src.ui import apply_theme, data_missing_warning, display_dataframe, explain, metric_grid, page_header


st.set_page_config(page_title="Retention and Progress Risk", layout="wide")
apply_theme()


@st.cache_data(show_spinner=False)
def cached_data():
    return load_data()


data = cached_data()
page_header("Retention and Progress Risk / ความเสี่ยงด้านการคงอยู่และความก้าวหน้า", "Over-program-length, transfer, graduation output, and unusually high-risk flags.")
explain(
    "This section highlights faculties where students may have delayed progress, such as studying beyond the normal program duration, transferring out, or showing weak graduation output."
)
data_missing_warning({"over_program_students": data["over_program"], "transfer_students": data["transfer"]})

metrics = faculty_metrics(data)
if metrics.empty:
    st.stop()

faculties = sorted(metrics["faculty_name"].dropna().astype(str).unique())
selected = st.sidebar.multiselect("Faculty / คณะ", faculties)
if selected:
    metrics = metrics.loc[metrics["faculty_name"].isin(selected)]

metric_grid(
    [
        {"label": "Median Over-Program Rate / มัธยฐานเรียนเกินหลักสูตร", "value": metrics["over_program_rate"].median(skipna=True), "kind": "pct"},
        {"label": "Median Transfer Out / มัธยฐานย้ายออก", "value": metrics["transfer_out"].median(skipna=True)},
        {"label": "Median Graduation Output Ratio / มัธยฐานผลผลิตบัณฑิต", "value": metrics["graduation_output_ratio"].median(skipna=True), "kind": "pct"},
        {"label": "Risk-Flag Faculties / คณะที่มีธงความเสี่ยง", "value": int(metrics["risk_flag"].sum())},
    ]
)

with st.expander("About these metrics / คำอธิบายตัวชี้วัด"):
    st.markdown(
        """
        - **Over-Program Rate / อัตราเรียนเกินหลักสูตร**: share of students whose study duration exceeds the normal program length.
        - **Transfer Out / ย้ายออก**: students leaving a faculty/program through transfer.
        - **Graduation Output Ratio / อัตราผลผลิตบัณฑิต**: latest graduates divided by current students. It is a rough output indicator, not a cohort completion rate.
        - **Risk z-score / ค่ามาตรฐานความเสี่ยง**: flags unusually high combined risk compared with other faculties.
        """
    )

left, right = st.columns(2)
with left:
    st.subheader("Over-Program-Length Rate / เรียนเกินหลักสูตร")
    explain("Higher values suggest more students are delayed beyond normal program duration.")
    top = metrics.sort_values("over_program_rate", ascending=False).head(20)
    fig = px.bar(
        top,
        x="over_program_rate",
        y="faculty_name",
        orientation="h",
        color="over_program_rate",
        color_continuous_scale=["#F5F1FA", "#4B1D80"],
        labels={
            "over_program_rate": "Over-program-length rate",
            "faculty_name": "Faculty",
            "current_students": "Current students",
            "over_program_students": "Over-program students",
        },
        hover_data={"over_program_rate": ":.3%", "current_students": ":,.0f", "over_program_students": ":,.0f"},
    )
    fig.update_layout(title="Faculties with Highest Over-Program Rate", height=480, yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, width="stretch")

with right:
    st.subheader("Transfer Out / ย้ายออก")
    explain("Transfer-out counts show where students leave a faculty or program through transfer.")
    top = metrics.sort_values("transfer_out", ascending=False).head(20)
    fig = px.bar(
        top,
        x="transfer_out",
        y="faculty_name",
        orientation="h",
        color="net_transfer",
        color_continuous_scale=["#BFA14A", "#F5F1FA", "#4B1D80"],
        labels={"transfer_out": "Transfer out", "transfer_in": "Transfer in", "faculty_name": "Faculty", "net_transfer": "Net transfer"},
        hover_data={"transfer_out": ":,.0f", "transfer_in": ":,.0f", "net_transfer": ":,.0f"},
    )
    fig.update_layout(title="Faculties with Highest Transfer Out", height=480, yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=50, b=10))
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
display_dataframe(metrics[[c for c in risk_cols if c in metrics.columns]].sort_values("risk_score", ascending=False))

st.subheader("Program-Level Over-Program-Length / รายหลักสูตร")
explain("This table helps identify specific programs where advising or curriculum-pathway support may be needed.")
over = data["over_program"]
if over.empty:
    st.info("No program-level over-program data.")
else:
    if selected:
        over = over.loc[over["faculty_name"].isin(selected)]
    cols = [c for c in ["faculty_name", "level", "program_name", "curriculum_type", "current_students", "over_program_students", "over_program_rate"] if c in over.columns]
    display_dataframe(over[cols].sort_values("over_program_rate", ascending=False).head(50), height=520)
