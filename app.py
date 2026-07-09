from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.metrics import compute_kpis, faculty_filter, load_data, time_trend
from src.ui import apply_theme, data_missing_warning, faculty_multiselect, metric_card, page_header


st.set_page_config(
    page_title="CMU Student Growth Intelligence Dashboard",
    page_icon="CMU",
    layout="wide",
)
apply_theme()


@st.cache_data(show_spinner=False)
def cached_data():
    return load_data()


data = cached_data()
page_header(
    "CMU Student Growth Intelligence Dashboard",
    "Official Chiang Mai University registry statistics, API-cached locally for reproducible analysis.",
)

data_missing_warning(
    {
        "current_faculty": data["current_faculty"],
        "admission_funnel": data["admission"],
        "historical_students": data["history"],
    }
)

faculties = faculty_multiselect(data["current_faculty"])
current = faculty_filter(data["current_faculty"], faculties)
history = faculty_filter(data["history"], faculties)

filtered_data = dict(data)
filtered_data["current_faculty"] = current
filtered_data["history"] = history
if faculties:
    filtered_data["admission"] = faculty_filter(data["admission"], faculties)
    filtered_data["graduates"] = faculty_filter(data["graduates"], faculties)
    filtered_data["nationality"] = data["nationality"].iloc[0:0].copy()
kpis = compute_kpis(filtered_data)

cols = st.columns(7)
with cols[0]:
    metric_card("Total current students", kpis["total_current_students"])
with cols[1]:
    metric_card("New remaining", kpis["new_student_remaining"])
with cols[2]:
    metric_card("Waive rate", kpis["waive_rate"], "pct")
with cols[3]:
    metric_card("Yield rate", kpis["yield_rate"], "pct")
with cols[4]:
    metric_card("Graduates", kpis["graduate_count"])
with cols[5]:
    metric_card("Net growth est.", kpis["estimated_net_growth"])
with cols[6]:
    metric_card("International share", kpis["international_student_share"], "pct")

st.divider()

left, right = st.columns([1.25, 1])
with left:
    st.subheader("Time Trend / แนวโน้มจำนวนนักศึกษา")
    trend = time_trend(history, current)
    if trend.empty:
        st.info("Historical trend data is not available.")
    else:
        fig = px.line(
            trend,
            x="period",
            y="student_count",
            markers=True,
            labels={"period": "Academic year / semester", "student_count": "Students"},
            color_discrete_sequence=["#4B1D80"],
        )
        fig.update_layout(height=430, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, width="stretch")

with right:
    st.subheader("Faculty Ranking / อันดับคณะ")
    if current.empty:
        st.info("Current faculty data is not available.")
    else:
        rank = current.sort_values("current_students", ascending=False).head(15)
        fig = px.bar(
            rank,
            x="current_students",
            y="faculty_name",
            orientation="h",
            labels={"current_students": "Current students", "faculty_name": "Faculty"},
            color="current_students",
            color_continuous_scale=["#D9C8EA", "#4B1D80"],
        )
        fig.update_layout(height=430, margin=dict(l=10, r=10, t=40, b=10), yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width="stretch")

st.subheader("Data Quality / คุณภาพข้อมูล")
quality = data["quality"]
if quality.empty:
    st.info("No data-quality table found yet.")
else:
    st.dataframe(quality, width="stretch", hide_index=True)

st.caption(
    "Source: statistic.reg.cmu.ac.th official JSON API. Numbers are computed from local raw cache and processed tables, not hard-coded."
)
if faculties:
    st.caption("Faculty filter active: international share uses international-program share proxy because nationality-by-faculty data is separate.")
