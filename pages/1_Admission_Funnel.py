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
from src.ui import apply_theme, data_missing_warning, page_header


st.set_page_config(page_title="Admission Funnel", layout="wide")
apply_theme()


@st.cache_data(show_spinner=False)
def cached_data():
    return load_data()


data = cached_data()
admission = data["admission"]
page_header("Admission Funnel", "Issued ID -> waived -> remaining, with leakage scenarios.")
data_missing_warning({"admission_funnel": admission})

if admission.empty:
    st.stop()

scope = st.sidebar.selectbox("Admission scope", sorted(admission["admission_scope"].dropna().unique()))
years = sorted(pd.to_numeric(admission["admit_year"], errors="coerce").dropna().astype(int).unique(), reverse=True)
selected_year = st.sidebar.selectbox("Admit year / รหัสนักศึกษา", years)
view = admission.loc[(admission["admission_scope"].eq(scope)) & (pd.to_numeric(admission["admit_year"], errors="coerce").eq(selected_year))].copy()
if view.empty:
    view = latest_admission(admission, scope)

issued = view["issued_total"].sum()
waived = view["waived_total"].sum()
remaining = view["remaining_total"].sum()

left, right = st.columns([0.9, 1.1])
with left:
    fig = go.Figure(
        go.Funnel(
            y=["Issued ID / ออกรหัส", "Waived / สละสิทธิ์", "Remaining / คงเหลือ"],
            x=[issued, waived, remaining],
            marker={"color": ["#4B1D80", "#BFA14A", "#6E35A7"]},
        )
    )
    fig.update_layout(height=430, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, width="stretch")

with right:
    st.subheader("Rates by Faculty / อัตราตามคณะ")
    rates = view.sort_values("waive_rate", ascending=False)
    tab1, tab2 = st.tabs(["Waive rate", "Yield rate"])
    with tab1:
        fig = px.bar(
            rates.head(20),
            x="waive_rate",
            y="faculty_name",
            orientation="h",
            labels={"waive_rate": "Waive rate", "faculty_name": "Faculty"},
            color="waive_rate",
            color_continuous_scale=["#E8DCF4", "#4B1D80"],
        )
        fig.update_layout(height=430, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width="stretch")
    with tab2:
        fig = px.bar(
            rates.sort_values("yield_rate").head(20),
            x="yield_rate",
            y="faculty_name",
            orientation="h",
            labels={"yield_rate": "Yield rate", "faculty_name": "Faculty"},
            color="yield_rate",
            color_continuous_scale=["#F3E8B8", "#4B1D80"],
        )
        fig.update_layout(height=430, yaxis={"categoryorder": "total ascending"})
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
fig = px.bar(
    gender,
    x="gender",
    y="students",
    color="stage",
    barmode="group",
    color_discrete_map={"issued": "#4B1D80", "waived": "#BFA14A", "remaining": "#6E35A7"},
)
fig.update_layout(height=360)
st.plotly_chart(fig, width="stretch")

st.subheader("Scenario Simulation / จำลองสถานการณ์")
pp = st.slider("If waive rate decreases by X percentage points", 0.0, 20.0, 5.0, 0.5)
scenario = scenario_reduce_waive(view, pp)
add_total = scenario["additional_students"].sum() if not scenario.empty else 0
st.metric("Additional students gained", f"{add_total:,.0f}")
st.dataframe(
    scenario[["faculty_name", "issued_total", "waived_total", "remaining_total", "additional_students", "new_remaining_total"]].head(25),
    width="stretch",
    hide_index=True,
)

st.subheader("Statistical Tests")
chi = chi_square_waive_by_faculty(view)
if chi["ok"]:
    st.write(f"Chi-square = {chi['chi2']:.2f}, df = {chi['dof']}, p-value = {chi['p_value']:.4g}")
    st.dataframe(chi["table"].head(20), width="stretch", hide_index=True)
else:
    st.info(chi["message"])

logit = logistic_waiver_model(admission.loc[admission["admission_scope"].eq(scope)])
if logit["ok"]:
    st.caption(logit["message"])
    st.dataframe(logit["table"].head(30), width="stretch", hide_index=True)
else:
    st.info(logit["message"])
