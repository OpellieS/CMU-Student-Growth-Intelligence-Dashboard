from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.metrics import faculty_match_key, faculty_metrics, load_data
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
        {"label": "Median Transfer-Out Rate / มัธยฐานอัตราย้ายออก", "value": metrics["transfer_out_rate"].median(skipna=True), "kind": "pct"},
        {"label": "Median Graduation Output Ratio / มัธยฐานผลผลิตบัณฑิต", "value": metrics["graduation_output_ratio"].median(skipna=True), "kind": "pct"},
        {"label": "Risk-Flag Faculties / คณะที่มีธงความเสี่ยง", "value": int(metrics["risk_flag"].sum())},
    ]
)

with st.expander("About these metrics / คำอธิบายตัวชี้วัด"):
    st.markdown(
        """
        - **Over-Program Rate / อัตราเรียนเกินหลักสูตร**: share of students whose study duration exceeds the normal program length.
        - **Transfer-Out Rate / อัตราการย้ายออก**: transfer-out students divided by current students. This is faculty/program movement, not dropout.
        - **Graduation Output Ratio / อัตราผลผลิตบัณฑิต**: latest graduates divided by current students. It is a rough output indicator, not a cohort completion rate.
        - **Risk z-score / ค่ามาตรฐานความเสี่ยง**: flags unusually high combined risk compared with other faculties.
        - If transfer data is missing for a selection, the risk score excludes transfer rate instead of treating it as zero.
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
    st.subheader("Transfer-Out Rate by Faculty / อัตราการย้ายออกตามคณะ")
    explain("Transfer-out rate compares transfer-out students with current students. This is student movement between faculties/programs, not dropout.")
    transfer_ready = "transfer_out_rate" in metrics.columns and metrics["transfer_out_rate"].notna().any()
    if transfer_ready:
        top = metrics.dropna(subset=["transfer_out_rate"]).sort_values("transfer_out_rate", ascending=False).head(20)
        fig = px.bar(
            top,
            x="transfer_out_rate",
            y="faculty_name",
            orientation="h",
            color="transfer_out_rate",
            color_continuous_scale=["#F5F1FA", "#4B1D80"],
            labels={
                "transfer_out_rate": "Transfer-Out Rate",
                "transfer_in": "Transfer In",
                "transfer_out": "Transfer Out",
                "current_students": "Current Students",
                "faculty_name": "Faculty",
                "net_transfer": "Net Transfer",
            },
            hover_data={
                "transfer_out_rate": ":.3%",
                "transfer_out": ":,.0f",
                "transfer_in": ":,.0f",
                "net_transfer": ":,.0f",
                "current_students": ":,.0f",
            },
        )
        fig.update_xaxes(tickformat=".1%")
        fig.update_layout(title="Faculties with Highest Transfer-Out Rate", height=480, yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, width="stretch")
    else:
        st.warning(
            "Transfer-out data is not available for the selected year, semester, or faculty. "
            "Please adjust the filters or check whether `data/processed/transfer_students.csv` is included."
        )
        with st.expander("Transfer-data diagnostics / รายละเอียดข้อมูลการย้ายคณะ"):
            transfer = data["transfer"]
            st.write("Selected faculties:", selected or "All")
            st.write("Transfer dataframe shape:", transfer.shape)
            st.write("Available columns:", list(transfer.columns))
            st.write("Expected columns:", ["faculty_name", "transfer_in", "transfer_out"])
            if not transfer.empty and "source_file" in transfer.columns:
                st.write("Source files:", sorted(transfer["source_file"].dropna().astype(str).unique()))

st.subheader("Risk Ranking / อันดับความเสี่ยง")
risk_cols = [
    "faculty_name",
    "current_students",
    "waive_rate",
    "over_program_rate",
    "transfer_out_rate",
    "transfer_out",
    "transfer_in",
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

st.subheader("Program-Level Student Transfer / การย้ายคณะรายหลักสูตร")
explain("Use this table to see whether transfer movement is concentrated in specific programs. Positive net transfer means more students moved in than out.")
transfer = data["transfer"].copy()
if transfer.empty:
    st.info("No program-level transfer data is available.")
else:
    if selected:
        selected_keys = {faculty_match_key(name) for name in selected}
        transfer = transfer.loc[transfer["faculty_name"].map(faculty_match_key).isin(selected_keys)]
    transfer_cols = [c for c in ["faculty_name", "program_name", "transfer_in", "transfer_out", "net_transfer"] if c in transfer.columns]
    if transfer.empty:
        st.info("Transfer data is available, but no rows match the selected faculty filter.")
    else:
        display_dataframe(transfer[transfer_cols].sort_values("transfer_out", ascending=False).head(50), height=420)
