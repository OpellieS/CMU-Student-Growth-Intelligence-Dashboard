from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.metrics import compute_kpis, faculty_filter, load_data, time_trend
from src.ui import apply_theme, data_missing_warning, display_dataframe, explain, faculty_multiselect, metric_grid, page_header


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
explain(
    "Overview shows CMU's current student base, latest admission retention, graduation output, and estimated net growth. "
    "Use the faculty filter to focus the entire page on selected faculties."
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

metric_grid(
    [
        {"label": "Total Current Students / นักศึกษาปัจจุบัน", "value": kpis["total_current_students"], "caption": "Active students in latest current-student table."},
        {"label": "New Remaining / นักศึกษาใหม่คงเหลือ", "value": kpis["new_student_remaining"], "caption": "Issued-ID students who remain after waivers."},
        {"label": "Waive Rate / อัตราสละสิทธิ์", "value": kpis["waive_rate"], "kind": "pct", "caption": "Share of issued-ID students who waived."},
        {"label": "Yield Rate / อัตราคงเหลือ", "value": kpis["yield_rate"], "kind": "pct", "caption": "Share of issued-ID students who remain."},
        {"label": "Graduates / ผู้สำเร็จการศึกษา", "value": kpis["graduate_count"], "caption": "Latest completed graduation count."},
        {"label": "Net Growth Estimate / ประมาณการเติบโตสุทธิ", "value": kpis["estimated_net_growth"], "caption": "New remaining minus graduates."},
        {"label": "International Share / สัดส่วนนานาชาติ", "value": kpis["international_student_share"], "kind": "pct", "caption": "Nationality share, or program proxy when filtered."},
    ]
)

with st.expander("About these metrics / คำอธิบายตัวชี้วัด"):
    st.markdown(
        """
        - **Waive Rate / อัตราสละสิทธิ์**: proportion of admitted or issued-ID students who did not remain enrolled.
        - **Yield Rate / อัตราคงเหลือ**: proportion of admitted or issued-ID students who remained as new students.
        - **Net Growth Estimate / ประมาณการเติบโตสุทธิ**: latest remaining new students minus latest observed graduates. This is an accounting estimate, not a causal forecast.
        - **International Share / สัดส่วนนานาชาติ**: nationality-based when available; faculty-filtered views use international-program share as a proxy.
        """
    )

st.divider()

left, right = st.columns([1.25, 1])
with left:
    st.subheader("Time Trend / แนวโน้มจำนวนนักศึกษา")
    explain("This line shows how total enrolled students change by academic year and semester.")
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
            hover_data={"student_count": ":,.0f", "period": True},
        )
        fig.update_layout(title="Total Students Over Time", height=430, margin=dict(l=10, r=10, t=50, b=10), hovermode="x unified")
        st.plotly_chart(fig, width="stretch")

with right:
    st.subheader("Faculty Ranking / อันดับคณะ")
    explain("This bar chart ranks faculties by current student count.")
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
            hover_data={"current_students": ":,.0f", "faculty_name": True},
        )
        fig.update_layout(title="Largest Faculties by Current Students", height=430, margin=dict(l=10, r=10, t=50, b=10), yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width="stretch")

st.subheader("Data Quality / คุณภาพข้อมูล")
quality = data["quality"]
if quality.empty:
    st.info("No data-quality table found yet.")
else:
    display_dataframe(quality)

st.caption(
    "Source: statistic.reg.cmu.ac.th official JSON API. Numbers are computed from local raw cache and processed tables, not hard-coded."
)
if faculties:
    st.caption("Faculty filter active: international share uses international-program share proxy because nationality-by-faculty data is separate.")
