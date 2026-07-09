from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.insights import generate_insights, priority_faculties, scenario_summary
from src.metrics import compute_kpis, load_data
from src.ui import apply_theme, data_missing_warning, page_header


st.set_page_config(page_title="Recommendation", layout="wide")
apply_theme()


@st.cache_data(show_spinner=False)
def cached_data():
    return load_data()


data = cached_data()
page_header("Recommendation", "Automatically generated insights and estimated student gains.")
data_missing_warning({"current_faculty": data["current_faculty"], "admission_funnel": data["admission"]})

waive_pp = st.sidebar.slider("Waive-rate reduction scenario (percentage points)", 0.0, 20.0, 5.0, 0.5)
intl_pp = st.sidebar.slider("International-share increase scenario (percentage points)", 0.0, 10.0, 1.0, 0.5)

st.subheader("Executive Answer")
for insight in generate_insights(data, waive_pp, intl_pp):
    st.markdown(f"- {insight}")

st.subheader("Priority Faculties / Programs")
priorities = priority_faculties(data, top_n=15)
if priorities.empty:
    st.info("Priority table cannot be computed yet.")
else:
    st.dataframe(priorities, width="stretch", hide_index=True)

st.subheader("Scenario Estimates")
scenarios = scenario_summary(data, waive_pp_values=[1, 3, 5, 10, waive_pp], intl_pp_values=[1, 2, 5, intl_pp]).drop_duplicates("scenario")
fig = px.bar(
    scenarios,
    x="additional_students",
    y="scenario",
    orientation="h",
    color="additional_students",
    color_continuous_scale=["#F5F1FA", "#4B1D80"],
    labels={"additional_students": "Expected additional students", "scenario": "Scenario"},
)
fig.update_layout(height=430, yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig, width="stretch")
st.dataframe(scenarios, width="stretch", hide_index=True)

st.subheader("Recommended Actions")
st.markdown(
    """
    1. Increase quota where growth is already high and waive rate is low.
    2. Reduce waive rate in faculties with high issued IDs but poor remaining yield.
    3. Improve onboarding where waivers are concentrated early.
    4. Improve student advising where over-program-length rates are high.
    5. Target international recruitment where current international share is low but scale and demand are already strong.
    """
)

kpis = compute_kpis(data)
st.caption(
    "Net-growth estimate = latest remaining admitted students minus latest graduate count. "
    f"Current computed estimate: {kpis.get('estimated_net_growth', float('nan')):,.0f}."
)
