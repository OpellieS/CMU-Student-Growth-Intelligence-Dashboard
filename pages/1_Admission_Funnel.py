from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.metrics import latest_admission, load_data, scenario_reduce_waive
from src.models import chi_square_waive_by_faculty, logistic_waiver_model
from src.ui import apply_theme, data_missing_warning, display_dataframe, explain, metric_grid, page_header


st.set_page_config(page_title="Admission Funnel", layout="wide")
apply_theme()


@st.cache_data(show_spinner=False)
def cached_data():
    return load_data()


data = cached_data()
admission = data["admission"]
page_header("Admission Funnel / กระบวนการรับเข้า", "Issued ID -> waived -> remaining, with leakage scenarios.")
explain(
    "This page shows how many admitted or issued-ID students remain after waivers. "
    "It helps identify faculties where accepted students leak before becoming enrolled students."
)
data_missing_warning({"admission_funnel": admission})

if admission.empty:
    st.stop()

scope_labels = {"all": "All admitted students / นักศึกษารับเข้าทั้งหมด", "first_generation": "First-generation admission / รอบแรก"}
scope = st.sidebar.selectbox(
    "Admission group / กลุ่มรับเข้า",
    sorted(admission["admission_scope"].dropna().unique()),
    format_func=lambda value: scope_labels.get(value, str(value).replace("_", " ").title()),
)
years = sorted(pd.to_numeric(admission["admit_year"], errors="coerce").dropna().astype(int).unique(), reverse=True)
selected_year = st.sidebar.selectbox("Admission year / ปีรหัสนักศึกษา", years)
view = admission.loc[(admission["admission_scope"].eq(scope)) & (pd.to_numeric(admission["admit_year"], errors="coerce").eq(selected_year))].copy()
if view.empty:
    view = latest_admission(admission, scope)

issued = view["issued_total"].sum()
waived = view["waived_total"].sum()
remaining = view["remaining_total"].sum()

left, right = st.columns([0.9, 1.1])
with left:
    explain("Funnel chart: issued IDs are admitted students with CMU IDs; waived students did not remain; remaining students are realized intake.")
    fig = go.Figure(
        go.Funnel(
            y=["Issued ID / ออกรหัส", "Waived / สละสิทธิ์", "Remaining / คงเหลือ"],
            x=[issued, waived, remaining],
            marker={"color": ["#4B1D80", "#BFA14A", "#6E35A7"]},
        )
    )
    fig.update_layout(title="Admission Funnel: Issued ID to Remaining Students", height=430, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, width="stretch")

with right:
    st.subheader("Rates by Faculty / อัตราตามคณะ")
    explain("Waive Rate is the share of issued-ID students who left before enrollment. Yield Rate is the share who remained.")
    rates = view.sort_values("waive_rate", ascending=False)
    tab1, tab2 = st.tabs(["Waive rate", "Yield rate"])
    with tab1:
        fig = px.bar(
            rates.head(20),
            x="waive_rate",
            y="faculty_name",
            orientation="h",
            labels={
                "waive_rate": "Waive rate",
                "faculty_name": "Faculty",
                "issued_total": "Issued IDs",
                "waived_total": "Waived students",
                "remaining_total": "Remaining students",
            },
            color="waive_rate",
            color_continuous_scale=["#E8DCF4", "#4B1D80"],
            hover_data={"waive_rate": ":.3%", "issued_total": ":,.0f", "waived_total": ":,.0f", "remaining_total": ":,.0f"},
        )
        fig.update_layout(title="Highest Waive Rates by Faculty", height=430, yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, width="stretch")
    with tab2:
        fig = px.bar(
            rates.sort_values("yield_rate").head(20),
            x="yield_rate",
            y="faculty_name",
            orientation="h",
            labels={
                "yield_rate": "Yield rate",
                "faculty_name": "Faculty",
                "issued_total": "Issued IDs",
                "waived_total": "Waived students",
                "remaining_total": "Remaining students",
            },
            color="yield_rate",
            color_continuous_scale=["#F3E8B8", "#4B1D80"],
            hover_data={"yield_rate": ":.3%", "issued_total": ":,.0f", "waived_total": ":,.0f", "remaining_total": ":,.0f"},
        )
        fig.update_layout(title="Lowest Yield Rates by Faculty", height=430, yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig, width="stretch")

st.subheader("Gender Breakdown / เพศ")
gender = pd.DataFrame(
    {
        "gender": ["Male / ชาย", "Female / หญิง"],
        "issued": [view["issued_male"].sum(), view["issued_female"].sum()],
        "waived": [view["waived_male"].sum(), view["waived_female"].sum()],
        "remaining": [view["remaining_male"].sum(), view["remaining_female"].sum()],
    }
).melt(id_vars="gender", var_name="stage", value_name="students")
stage_labels = {"issued": "Issued IDs / ออกรหัส", "waived": "Waived / สละสิทธิ์", "remaining": "Remaining / คงเหลือ"}
gender["stage_label"] = gender["stage"].map(stage_labels)
fig = px.bar(
    gender,
    x="gender",
    y="students",
    color="stage_label",
    barmode="group",
    labels={"gender": "Gender", "students": "Students", "stage_label": "Admission stage"},
    color_discrete_map={"Issued IDs / ออกรหัส": "#4B1D80", "Waived / สละสิทธิ์": "#BFA14A", "Remaining / คงเหลือ": "#6E35A7"},
    hover_data={"students": ":,.0f"},
)
fig.update_layout(title="Issued, Waived, and Remaining Students by Gender", height=360, margin=dict(l=10, r=10, t=50, b=10))
st.plotly_chart(fig, width="stretch")

st.subheader("Scenario Simulation / จำลองสถานการณ์")
explain("This estimates how many additional students CMU could gain if the waive rate decreases by the selected percentage points.")
pp = st.slider("Waive-rate decrease in percentage points / ลดอัตราสละสิทธิ์ (จุดเปอร์เซ็นต์)", 0.0, 20.0, 5.0, 0.5)
scenario = scenario_reduce_waive(view, pp)
add_total = scenario["additional_students"].sum() if not scenario.empty else 0
metric_grid([{"label": "Estimated Additional Students / จำนวนนักศึกษาที่คาดว่าจะเพิ่ม", "value": add_total, "caption": "Assumes each prevented waiver becomes one remaining student."}])
display_dataframe(
    scenario[["faculty_name", "issued_total", "waived_total", "remaining_total", "additional_students", "new_remaining_total"]].head(25),
)

st.subheader("Statistical Tests / การทดสอบทางสถิติ")
with st.expander("About these tests / คำอธิบายการทดสอบ"):
    st.markdown(
        """
        - **Chi-square test** checks whether waive rates differ by faculty more than expected by random variation.
        - **Logistic regression** estimates waiver odds using aggregated faculty and gender counts. It is useful for ranking patterns, not proving causality.
        - Small p-values suggest the pattern is unlikely to be random, but they do not explain why students waived.
        """
    )
chi = chi_square_waive_by_faculty(view)
if chi["ok"]:
    st.write(f"Chi-square = {chi['chi2']:.3f}, degrees of freedom = {chi['dof']}, p-value = {chi['p_value']:.3e}")
    if chi["p_value"] < 0.05:
        st.success("Interpretation: waive rates differ significantly across faculties. CMU should inspect faculty-specific causes, not only university-wide averages.")
    else:
        st.info("Interpretation: this sample does not show statistically clear waive-rate differences across faculties.")
    display_dataframe(chi["table"].head(20))
else:
    st.info(chi["message"])

logit = logistic_waiver_model(admission.loc[admission["admission_scope"].eq(scope)])
if logit["ok"]:
    st.caption(logit["message"])
    display_dataframe(logit["table"].head(30))
    st.info("Interpretation: odds ratios above 1 mean higher waiver odds than the reference group; below 1 mean lower waiver odds. Use this as a signal for follow-up, not as proof of causality.")
else:
    st.info(logit["message"])
