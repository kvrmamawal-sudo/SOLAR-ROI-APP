"""
Siklab Solar — PV ROI Explorer
Streamlit app: loads pre-computed artifacts from the Colab notebook
(hourly_reference_profile.parquet, tariff_model.pkl, export_rate_model.pkl,
macro_constants.json, capex_rates.json) and runs a live ROI/payback simulation
as the user adjusts sliders and toggles. No retraining happens at runtime.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# --------------------------------------------------------------------------
# Page config + design tokens
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Siklab Solar | PV ROI Explorer",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

AMBER = "#FFB627"        # primary — solar
EMBER = "#E85D04"        # secondary — accent / CTA
FLARE = "#FF7A00"        # gradient midpoint
CHARCOAL = "#1C1B1F"     # dark text / dark panels
WARM_WHITE = "#FFF4E0"   # page base
SIGNAL_BLUE = "#0F6E8C"  # cool counterpoint for cash-flow line (pre-payback)
SIGNAL_GREEN = "#2D6A4F" # positive / post-payback

CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700;800&family=Inter:wght@400;500;600&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', sans-serif;
}}
h1, h2, h3, .hero-title {{
    font-family: 'Sora', sans-serif;
}}

.stApp {{
    background: {WARM_WHITE};
}}

.hero-banner {{
    background: linear-gradient(120deg, {AMBER} 0%, {FLARE} 55%, {EMBER} 100%);
    border-radius: 18px;
    padding: 2.2rem 2.4rem;
    margin-bottom: 1.6rem;
    box-shadow: 0 8px 24px rgba(232, 93, 4, 0.18);
}}
.hero-title {{
    color: {CHARCOAL};
    font-size: 2.1rem;
    font-weight: 800;
    margin: 0 0 0.3rem 0;
}}
.hero-subtitle {{
    color: {CHARCOAL};
    opacity: 0.85;
    font-size: 1.02rem;
    margin: 0;
}}

.metric-card {{
    background: white;
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    border: 1px solid rgba(28,27,31,0.06);
    box-shadow: 0 2px 10px rgba(28,27,31,0.05);
}}
.metric-label {{
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: {CHARCOAL};
    opacity: 0.6;
    font-weight: 600;
}}
.metric-value {{
    font-family: 'Sora', sans-serif;
    font-size: 1.7rem;
    font-weight: 700;
    color: {CHARCOAL};
}}
.section-label {{
    display: inline-block;
    background: {CHARCOAL};
    color: {AMBER};
    font-family: 'Sora', sans-serif;
    font-weight: 600;
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 0.25rem 0.7rem;
    border-radius: 999px;
    margin-bottom: 0.6rem;
}}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# --------------------------------------------------------------------------
# Artifact loading (cached — no retraining at runtime)
# --------------------------------------------------------------------------
ARTIFACT_DIR = Path(__file__).parent / "artifacts"

CAPEX_RATES_FALLBACK = {
    "panel_bos_php_per_kw": 15000,
    "installation_php_per_kw": 5000,
    "grid_tied_inverter_php_per_kw": 4000,
    "hybrid_inverter_php_per_kw": 7000,
    "battery_php_per_kwh": 6500,
    "net_metering_fee_php": 50000,
}


@st.cache_data(show_spinner=False)
def load_reference_profile():
    return pd.read_parquet(ARTIFACT_DIR / "hourly_reference_profile.parquet")


@st.cache_data(show_spinner=False)
def load_macro_constants():
    with open(ARTIFACT_DIR / "macro_constants.json") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def load_capex_rates():
    try:
        with open(ARTIFACT_DIR / "capex_rates.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return CAPEX_RATES_FALLBACK


ref_profile = load_reference_profile()
macro_constants = load_macro_constants()
capex_rates = load_capex_rates()

PERSONA_COLUMNS = {
    "Work-from-home (daytime-heavy)": "load_wfh_daytime_kwh",
    "Night-heavy (evenings/appliances)": "load_night_heavy_kwh",
    "Commercial (business hours)": "load_commercial_kwh",
}

# --------------------------------------------------------------------------
# Hero
# --------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero-banner">
        <p class="hero-title">☀️ Siklab Solar — PV ROI Explorer</p>
        <p class="hero-subtitle">
            See how your system size, usage habits, and Philippine energy
            market conditions shape your rooftop solar payback — updated live
            as you adjust the controls below.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Input form (single page, live-updating — no submit button)
# --------------------------------------------------------------------------
st.markdown('<span class="section-label">1 · Your system</span>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
with c1:
    system_kwp = st.slider("System size (kWp)", 1.0, 20.0, 5.0, 0.5)
with c2:
    battery_kwh = st.slider("Battery storage (kWh)", 0.0, 20.0, 0.0, 0.5,
                             help="Set to 0 for a grid-tied system with no storage.")
with c3:
    use_hybrid_inverter = st.toggle("Hybrid inverter (required for battery)", value=battery_kwh > 0)

c4, c5 = st.columns(2)
with c4:
    apply_net_metering_fee = st.toggle("Include ₱50,000 net-metering application fee", value=True)
with c5:
    n_years = st.slider("Projection horizon (years)", 5, 25, 10)

st.markdown('<span class="section-label">2 · Your usage behavior</span>', unsafe_allow_html=True)
persona_label = st.selectbox("Which best describes your household/business load pattern?",
                              list(PERSONA_COLUMNS.keys()))
load_col = PERSONA_COLUMNS[persona_label]

st.markdown('<span class="section-label">3 · Macro stress test (optional)</span>', unsafe_allow_html=True)
c6, c7 = st.columns(2)
with c6:
    shock_pct = st.slider("One-time fuel/tariff shock (%)", -30, 60, 0, 5,
                           help="Simulates a Brent crude / coal price shock passed through to retail tariffs.")
with c7:
    shock_year = st.slider("Shock occurs in year", 1, n_years, min(3, n_years), disabled=(shock_pct == 0))

# --------------------------------------------------------------------------
# Core simulation (mirrors the Colab notebook engine)
# --------------------------------------------------------------------------
def simulate_energy_balance(df, system_kwp, load_col, battery_kwh,
                             battery_round_trip_eff=0.90, battery_min_soc_pct=0.10):
    pv = (df["pv_yield_per_kwp"] * system_kwp).to_numpy()
    ld = df[load_col].to_numpy()
    n = len(df)

    self_consumed = np.zeros(n)
    export = np.zeros(n)
    imp = np.zeros(n)
    min_soc = battery_kwh * battery_min_soc_pct
    soc_prev = min_soc

    for i in range(n):
        direct_use = min(pv[i], ld[i])
        surplus = pv[i] - direct_use
        remaining_demand = ld[i] - direct_use

        room = max(battery_kwh - soc_prev, 0)
        charge_amt = min(surplus, room)
        soc_now = soc_prev + charge_amt * battery_round_trip_eff
        surplus_after_batt = surplus - charge_amt

        available = max(soc_now - min_soc, 0)
        discharge_amt = min(remaining_demand, available)
        soc_now -= discharge_amt

        self_consumed[i] = direct_use + discharge_amt
        export[i] = surplus_after_batt
        imp[i] = remaining_demand - discharge_amt
        soc_prev = soc_now

    return self_consumed.sum(), export.sum()


def calculate_capex(system_kwp, battery_kwh, use_hybrid_inverter, apply_net_metering_fee, rates):
    inverter_rate = rates["hybrid_inverter_php_per_kw"] if use_hybrid_inverter else rates["grid_tied_inverter_php_per_kw"]
    capex = (
        system_kwp * rates["panel_bos_php_per_kw"]
        + system_kwp * rates["installation_php_per_kw"]
        + system_kwp * inverter_rate
        + battery_kwh * rates["battery_php_per_kwh"]
    )
    if apply_net_metering_fee:
        capex += rates["net_metering_fee_php"]
    return capex


def project_annual_tariffs(base_retail, base_export, n_years, cagr, shock_year, shock_pct):
    retail_path, export_path = [], []
    r, e = base_retail, base_export
    for yr in range(1, n_years + 1):
        if shock_year == yr and shock_pct != 0:
            r *= (1 + shock_pct / 100)
            e *= (1 + shock_pct / 100)
        else:
            r *= (1 + cagr)
            e *= (1 + cagr)
        retail_path.append(r)
        export_path.append(e)
    return retail_path, export_path


def run_roi_simulation(annual_self_consumed, annual_export, capex, base_retail, base_export,
                        n_years, cagr, discount_rate=0.06, panel_degradation_pct=0.005,
                        shock_year=None, shock_pct=0.0):
    retail_path, export_path = project_annual_tariffs(base_retail, base_export, n_years, cagr,
                                                        shock_year, shock_pct)
    rows = []
    cumulative = -capex
    payback_year = None

    for yr in range(1, n_years + 1):
        deg = (1 - panel_degradation_pct) ** (yr - 1)
        sc = annual_self_consumed * deg
        exp = annual_export * deg
        bill_savings = sc * retail_path[yr - 1]
        export_credit = exp * export_path[yr - 1]
        cashflow = bill_savings + export_credit
        cumulative += cashflow
        if payback_year is None and cumulative >= 0:
            payback_year = yr
        rows.append({
            "Year": yr,
            "Retail rate (₱/kWh)": round(retail_path[yr - 1], 3),
            "Export rate (₱/kWh)": round(export_path[yr - 1], 3),
            "Bill savings (₱)": round(bill_savings, 0),
            "Export credit (₱)": round(export_credit, 0),
            "Annual cash flow (₱)": round(cashflow, 0),
            "Cumulative savings (₱)": round(cumulative, 0),
        })

    yearly_df = pd.DataFrame(rows)
    discounted = sum(r["Annual cash flow (₱)"] / ((1 + discount_rate) ** r["Year"]) for r in rows)
    npv = -capex + discounted
    roi_pct = (yearly_df["Cumulative savings (₱)"].iloc[-1] / capex) * 100

    summary = {
        "capex": capex,
        "payback_year": payback_year,
        "npv": npv,
        "roi_pct": roi_pct,
        "final_cumulative": yearly_df["Cumulative savings (₱)"].iloc[-1],
    }
    return summary, yearly_df


annual_self_consumed, annual_export = simulate_energy_balance(
    ref_profile, system_kwp, load_col, battery_kwh
)
capex = calculate_capex(system_kwp, battery_kwh, use_hybrid_inverter, apply_net_metering_fee, capex_rates)
summary, yearly_df = run_roi_simulation(
    annual_self_consumed, annual_export, capex,
    macro_constants["base_retail_rate_php_kwh"], macro_constants["base_export_rate_php_kwh"],
    n_years, macro_constants["retail_rate_cagr"],
    shock_year=shock_year if shock_pct != 0 else None, shock_pct=shock_pct,
)

# --------------------------------------------------------------------------
# Results — metric cards
# --------------------------------------------------------------------------
st.markdown('<span class="section-label">Results</span>', unsafe_allow_html=True)
m1, m2, m3, m4 = st.columns(4)
payback_display = f"{summary['payback_year']} yrs" if summary["payback_year"] else f"> {n_years} yrs"
for col, label, value in zip(
    [m1, m2, m3, m4],
    ["System CapEx", "Payback period", f"ROI over {n_years} yrs", "Net present value"],
    [f"₱{capex:,.0f}", payback_display, f"{summary['roi_pct']:,.0f}%", f"₱{summary['npv']:,.0f}"],
):
    col.markdown(
        f'<div class="metric-card"><div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div></div>',
        unsafe_allow_html=True,
    )

st.write("")

# --------------------------------------------------------------------------
# Chart — 10-year (or N-year) cumulative cash flow / payback
# --------------------------------------------------------------------------
fig = go.Figure()
colors = [SIGNAL_BLUE if v < 0 else SIGNAL_GREEN for v in yearly_df["Cumulative savings (₱)"]]
fig.add_trace(go.Scatter(
    x=yearly_df["Year"], y=yearly_df["Cumulative savings (₱)"],
    mode="lines+markers", line=dict(color=EMBER, width=3),
    marker=dict(size=8, color=colors), fill="tozeroy",
    fillcolor="rgba(255,182,39,0.18)", name="Cumulative savings",
))
fig.add_hline(y=0, line_dash="dash", line_color=CHARCOAL, opacity=0.4)
if summary["payback_year"]:
    fig.add_vline(x=summary["payback_year"], line_dash="dot", line_color=SIGNAL_GREEN,
                  annotation_text="Payback", annotation_position="top")
fig.update_layout(
    title=f"Cumulative savings vs. CapEx over {n_years} years",
    xaxis_title="Year", yaxis_title="Cumulative savings (₱)",
    plot_bgcolor="white", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color=CHARCOAL),
    margin=dict(t=60, b=40, l=10, r=10), height=420,
)
st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------------------------------
# Full report — expandable sections
# --------------------------------------------------------------------------
st.markdown('<span class="section-label">Full report</span>', unsafe_allow_html=True)

with st.expander("📋 Plain-language summary", expanded=True):
    if summary["payback_year"]:
        payback_sentence = (
            f"Based on your inputs, this **{system_kwp:.1f} kWp** system "
            f"({'with' if battery_kwh > 0 else 'without'} battery storage) is projected to "
            f"pay for itself in **{summary['payback_year']} years**, after an upfront cost of "
            f"**₱{capex:,.0f}**. Over {n_years} years, it's projected to generate "
            f"**₱{summary['final_cumulative']:,.0f}** in net savings — an ROI of "
            f"**{summary['roi_pct']:,.0f}%** on the initial investment."
        )
    else:
        payback_sentence = (
            f"Based on your inputs, this system does **not** fully pay back its "
            f"₱{capex:,.0f} cost within the {n_years}-year horizon you selected. "
            f"Try increasing the horizon, reducing battery size, or reviewing your usage pattern."
        )
    st.markdown(payback_sentence)
    st.caption(
        "Self-consumed energy avoids the full retail rate; exported surplus is credited at the "
        "lower blended generation rate — so usage patterns that shift more consumption into "
        "daylight hours typically shorten payback."
    )

with st.expander("📈 Year-by-year breakdown"):
    st.dataframe(yearly_df, use_container_width=True, hide_index=True)

with st.expander("🧮 How this was calculated"):
    st.markdown(
        f"""
        - **Energy balance**: hourly PV generation (scaled from a synthetic 5 kWp reference
          profile) is matched hour-by-hour against your selected load pattern, with any battery
          charged from surplus PV and discharged to cover unmet demand before falling back to
          grid export/import.
        - **CapEx**: panels/BOS ₱15,000/kW + installation ₱5,000/kW +
          {'hybrid' if use_hybrid_inverter else 'grid-tied'} inverter
          ₱{capex_rates['hybrid_inverter_php_per_kw' if use_hybrid_inverter else 'grid_tied_inverter_php_per_kw']:,}/kW
          + battery ₱6,500/kWh{' + ₱50,000 net-metering fee' if apply_net_metering_fee else ''}.
        - **Tariff escalation**: retail and export rates grow at a **{macro_constants['retail_rate_cagr']:.2%}**
          annual rate, derived from the historical 2015–2030 macro dataset, with your optional
          one-time shock applied in the selected year.
        - **Panel degradation**: 0.5%/year applied to generation.
        - **NPV** uses a 6% discount rate on projected annual cash flows.
        """
    )

with st.expander("⚠️ Assumptions & disclaimers"):
    st.markdown(
        """
        This tool uses **synthetic** meteorological, load, and macroeconomic datasets for
        educational and illustrative purposes. It is not a substitute for a formal site
        assessment or a quotation from a licensed installer, and actual generation, tariffs,
        and costs will vary. Figures are in Philippine pesos (₱) and pre-tax.
        """
    )

st.write("")
d1, d2 = st.columns(2)
with d1:
    st.download_button(
        "⬇️ Download year-by-year CSV",
        data=yearly_df.to_csv(index=False).encode("utf-8"),
        file_name="siklab_solar_roi_breakdown.csv",
        mime="text/csv",
        use_container_width=True,
    )
with d2:
    report_txt = (
        f"Siklab Solar — PV ROI Report\n"
        f"{'=' * 32}\n"
        f"System size: {system_kwp} kWp | Battery: {battery_kwh} kWh | "
        f"Inverter: {'Hybrid' if use_hybrid_inverter else 'Grid-tied'}\n"
        f"Usage pattern: {persona_label}\n"
        f"Horizon: {n_years} years | Shock: {shock_pct}% in year {shock_year if shock_pct else '-'}\n\n"
        f"CapEx: PHP {capex:,.0f}\n"
        f"Payback period: {payback_display}\n"
        f"ROI over {n_years} years: {summary['roi_pct']:.1f}%\n"
        f"NPV (6% discount): PHP {summary['npv']:,.0f}\n"
    )
    st.download_button(
        "⬇️ Download summary report (TXT)",
        data=report_txt.encode("utf-8"),
        file_name="siklab_solar_roi_summary.txt",
        mime="text/plain",
        use_container_width=True,
    )

st.markdown(
    f"<p style='opacity:0.55; font-size:0.82rem; margin-top:1.2rem;'>"
    f"Siklab Solar ROI Explorer · educational tool built on synthetic data · "
    f"not a formal quotation.</p>",
    unsafe_allow_html=True,
)
