"""
Green-Tech Inventory Assistant — Streamlit App
All data is read from and written to a SQLite database.
Run:  python -m streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import logging
import sys
import os

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(__file__))

from src.data_loader import (
    load_items, load_usage_logs, load_suppliers, load_impact_rules,
    add_item, update_item, add_usage_log, get_item_with_supplier,
    get_full_stock_overview, save_simulator_run, ensure_db,
)
from src.reorder_engine import analyze_all_items, analyze_item
from src.sustainability import compute_sustainability_summary
from src.insights import generate_insights
from src.simulator import run_simulation
from src.ai_explainer import generate_ai_explanation, draft_supplier_email
from src.fallback_explainer import generate_fallback_explanation, generate_fallback_insight_summary
from src.validation import validate_item
from src.utils import risk_emoji, decision_emoji, fmt_days

@st.cache_data(show_spinner=False, ttl=3600)
def cached_generate_ai_explanation(analysis_dict, insights_list=None):
    return generate_ai_explanation(analysis_dict, insights_list)

@st.cache_data(show_spinner=False, ttl=3600)
def cached_draft_supplier_email(analysis_dict):
    return draft_supplier_email(analysis_dict)

from src.validation import validate_item
from src.utils import risk_emoji, decision_emoji, fmt_days

# ──────────────────── Bootstrap DB ────────────────────
ensure_db()

# ──────────────────── Logging ────────────────────
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(name)s — %(message)s")
logger = logging.getLogger("app")

# ──────────────────── Page Config ────────────────────
st.set_page_config(
    page_title="Green-Tech Inventory Assistant",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────── Custom CSS ────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .stTabs [data-baseweb="tab-list"] { gap: 4px; }
    .stTabs [data-baseweb="tab"] { padding: 6px 12px; font-size: 14px; }
    div[data-testid="stExpander"] details summary p { font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ──────────────────── Load Data from DB ────────────────────

@st.cache_data(ttl=5)
def _load():
    items = load_items()
    usage = load_usage_logs()
    suppliers = load_suppliers()
    rules = load_impact_rules()
    return items, usage, suppliers, rules


def reload():
    _load.clear()


items_df, usage_df, suppliers_df, rules = _load()

# ──────────────────── Sidebar ────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/color/96/plant-under-rain.png", width=60)
    st.title("🌿 Green-Tech")
    st.caption("Inventory Decision Assistant")
    st.divider()

    # AI / Fallback Toggle
    st.subheader("🤖 Explanation Mode")
    simulate_ai_off = st.toggle("Simulate AI unavailable", value=False, key="ai_toggle",
                                 help="Turn on to see rule-based fallback explanations instead of AI.")
    if simulate_ai_off:
        st.info("📋 **Fallback mode active** — Rule-based explanations.")
    else:
        st.success("✨ **AI mode active** — AI explanations attempted.")

    st.divider()
    st.caption("📂 Data source: **SQLite database**")
    st.caption(f"Last refreshed: {datetime.now().strftime('%H:%M:%S')}")
    if st.button("🔄 Refresh Data"):
        reload()
        st.rerun()

# ──────────────────── Analysis ────────────────────
analysis_results = analyze_all_items(items_df, usage_df, suppliers_df)

# Enrich with supplier_id for sustainability
for r in analysis_results:
    row = items_df[items_df["item_id"] == r["item_id"]]
    if not row.empty:
        r["supplier_id"] = row.iloc[0]["supplier_id"]

sustainability = compute_sustainability_summary(analysis_results, suppliers_df)
insights = generate_insights(items_df, usage_df, analysis_results)

# ──────────────────── Main Tabs ────────────────────
tab_dash, tab_stock, tab_manage, tab_sim = st.tabs(
    ["📊 Dashboard", "📋 Full Stock Overview", "📦 Manage Items", "🧪 Simulator"]
)

# ═══════════════════════════════════════════════════════════
#                       DASHBOARD TAB
# ═══════════════════════════════════════════════════════════
with tab_dash:
    st.header("Inventory Dashboard")

    # ---- Top metric cards ----
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Items", sustainability["total_items"])
    with c2:
        st.metric("⚠️ Reorder Needed", sum(1 for r in analysis_results if r["reorder_decision"] == "reorder_now"))
    with c3:
        st.metric("🔴 Waste Risk", sustainability["items_at_waste_risk"])
    with c4:
        st.metric("♻️ Waste Avoidance", f"{sustainability['waste_reduction_pct']}%")

    # ---- Search & Filter ----
    st.subheader("Search & Filter")
    fc1, fc2 = st.columns([2, 3])
    with fc1:
        search_query = st.text_input("🔍 Search by item name", "", key="search")
    with fc2:
        filter_opts = st.multiselect(
            "Filter",
            ["Low Stock (Reorder Now)", "Expiring Soon (≤5 days)", "High Waste Risk"],
            key="filters",
        )

    # Apply filters
    filtered = analysis_results.copy()
    if search_query:
        filtered = [r for r in filtered if search_query.lower() in r["item_name"].lower()]
    if "Low Stock (Reorder Now)" in filter_opts:
        filtered = [r for r in filtered if r["reorder_decision"] == "reorder_now"]
    if "Expiring Soon (≤5 days)" in filter_opts:
        filtered = [r for r in filtered if r["days_until_expiry"] is not None and r["days_until_expiry"] <= 5]
    if "High Waste Risk" in filter_opts:
        filtered = [r for r in filtered if r["waste_risk"] == "high"]

    # ---- Reorder Recommendation List ----
    st.subheader("Reorder Recommendations")
    if not filtered:
        st.info("No items match the current filters.")
    else:
        for r in filtered:
            with st.expander(f"{decision_emoji(r['reorder_decision'])}  **{r['item_name']}** — {r['current_stock']} {r['unit']} on hand"):
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("Stock", f"{r['current_stock']} {r['unit']}")
                mc2.metric("Avg Usage/day", f"{r['avg_daily_usage']} {r['unit']}")
                mc3.metric("Days Remaining", fmt_days(r['days_remaining']))
                mc4.metric("Expiry", f"{r['days_until_expiry']}d" if r['days_until_expiry'] else "—")

                mc5, mc6 = st.columns(2)
                mc5.metric("Waste Risk", f"{risk_emoji(r['waste_risk'])} {r['waste_risk'].title()}")
                mc6.metric("Suggested Qty", f"{r['suggested_reorder_qty']} {r['unit']}" if r['suggested_reorder_qty'] > 0 else "—")

                # Explanation
                st.markdown("---")
                if simulate_ai_off:
                    st.markdown("**📋 Rule-Based Explanation (Fallback)**")
                    explanation = generate_fallback_explanation(r, usage_df)
                    st.write(explanation)
                else:
                    ai_text, used_ai = cached_generate_ai_explanation(r, insights)
                    if used_ai:
                        st.markdown("**✨ AI-Generated Explanation**")
                        st.write(ai_text)
                    else:
                        st.markdown("**📋 Rule-Based Explanation (Fallback)**")
                        explanation = generate_fallback_explanation(r, usage_df)
                        st.write(explanation)

                # Email Drafter 
                if r['reorder_decision'] == "reorder_now" and not simulate_ai_off:
                    st.markdown("---")
                    with st.expander("✉️ Draft Reorder Email to Supplier based on data"):
                        with st.spinner("Drafting professional email using AI..."):
                            email_draft = cached_draft_supplier_email(r)
                            st.text_area(
                                "Review & Copy:", 
                                value=email_draft, 
                                height=200, 
                                key=f"txt_{r['item_id']}"
                            )

    # ---- Sustainability Summary ----
    st.subheader("♻️ Sustainability Impact")
    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Items OK (before expiry)", sustainability["items_avoided_expiry"])
    sc2.metric("High Waste Risk", sustainability["items_at_waste_risk"])
    sc3.metric("Local Suppliers", sustainability["local_supplier_count"])
    sc4.metric("Eco Packaging", sustainability["good_packaging_count"])

    # ---- Pattern Insights ----
    st.subheader("📈 Consumption Insights (Top Patterns)")
    if not insights:
        st.info("Not enough data for pattern insights.")
    else:
        if simulate_ai_off:
            st.markdown("**📋 Rule-Based Insight Summary**")
            st.markdown(generate_fallback_insight_summary(insights))
        else:
            from src.ai_explainer import generate_ai_insight_summary
            ai_text, used_ai = generate_ai_insight_summary(insights, sustainability)
            if used_ai:
                st.markdown("**✨ AI Insight Summary**")
                st.write(ai_text)
            else:
                st.markdown("**📋 Rule-Based Insight Summary**")
                st.markdown(generate_fallback_insight_summary(insights))


# ──────────────────── Helper functions ────────────────────

def _short_insight(analysis: dict) -> str:
    """One-line insight for the stock overview table."""
    d = analysis.get("reorder_decision", "")
    dr = analysis.get("days_remaining")
    lt = analysis.get("lead_time", 0)
    w = analysis.get("waste_risk", "low")
    if d == "reorder_now":
        return f"Stock covers ~{dr:.0f}d, lead time {lt}d" if dr else "Low stock"
    if w == "high":
        return "Overstock — usage won't clear before expiry"
    if d == "reorder_later":
        return "Approaching reorder threshold"
    return "Stock sufficient"


# ═══════════════════════════════════════════════════════════
#                   FULL STOCK OVERVIEW TAB
# ═══════════════════════════════════════════════════════════
with tab_stock:
    st.header("📋 Full Stock Overview")
    st.caption("Complete inventory table with reorder status, waste risk, and supplier details — "
               "all fetched from the database.")

    # Fetch from DB via join
    overview_df = get_full_stock_overview()

    if overview_df.empty:
        st.info("No items in the database yet. Add items in the **Manage Items** tab.")
    else:
        # Build analysis lookup for enrichment
        analysis_map = {r["item_id"]: r for r in analysis_results}

        # ---- Filters ----
        fs1, fs2 = st.columns([2, 3])
        with fs1:
            stock_search = st.text_input("🔍 Search by item name", "", key="stock_search")
        with fs2:
            stock_filters = st.multiselect(
                "Filter",
                ["Reorder Now", "Low Stock", "Expiring Soon (≤5 days)", "High Waste Risk"],
                key="stock_filters",
            )

        # Enrich overview with analysis data
        enriched = []
        for _, row in overview_df.iterrows():
            a = analysis_map.get(row["item_id"], {})
            enriched.append({
                "Item": row["item_name"],
                "Category": row["category"],
                "Stock": f"{row['quantity_on_hand']} {row['unit']}",
                "stock_num": row["quantity_on_hand"],
                "Unit": row["unit"],
                "Expiry": row["expiry_date"].strftime("%Y-%m-%d") if isinstance(row["expiry_date"], (date, datetime)) else str(row["expiry_date"]),
                "Threshold": row["reorder_threshold"],
                "Supplier": row["supplier_name"],
                "Lead Time": f"{row['avg_lead_days']}d",
                "Reorder Status": decision_emoji(a.get("reorder_decision", "do_not_reorder")),
                "reorder_raw": a.get("reorder_decision", "do_not_reorder"),
                "Suggested Qty": f"{a.get('suggested_reorder_qty', 0):.0f}" if a.get("suggested_reorder_qty", 0) > 0 else "—",
                "Waste Risk": f"{risk_emoji(a.get('waste_risk', 'low'))} {a.get('waste_risk', 'low').title()}",
                "waste_raw": a.get("waste_risk", "low"),
                "days_exp": a.get("days_until_expiry", 999),
                "Insight": _short_insight(a),
            })

        edf = pd.DataFrame(enriched)

        # Apply search
        if stock_search:
            edf = edf[edf["Item"].str.lower().str.contains(stock_search.lower())]

        # Apply filters
        if "Reorder Now" in stock_filters:
            edf = edf[edf["reorder_raw"] == "reorder_now"]
        if "Low Stock" in stock_filters:
            edf = edf[edf["stock_num"] <= edf["Threshold"]]
        if "Expiring Soon (≤5 days)" in stock_filters:
            edf = edf[edf["days_exp"] <= 5]
        if "High Waste Risk" in stock_filters:
            edf = edf[edf["waste_raw"] == "high"]

        # Display table (drop helper columns)
        display_cols = ["Item", "Category", "Stock", "Expiry", "Threshold",
                        "Supplier", "Lead Time", "Reorder Status", "Suggested Qty",
                        "Waste Risk", "Insight"]
        st.dataframe(
            edf[display_cols],
            use_container_width=True,
            hide_index=True,
            height=min(400, 60 + len(edf) * 40),
        )

        st.caption(f"Showing {len(edf)} of {len(overview_df)} items from the database.")



# ═══════════════════════════════════════════════════════════
#                     MANAGE ITEMS TAB
# ═══════════════════════════════════════════════════════════
with tab_manage:
    st.header("Manage Inventory Items")

    mtab_add, mtab_update, mtab_log = st.tabs(["➕ Add Item", "✏️ Update Item", "📝 Log Usage"])

    supplier_ids = suppliers_df["supplier_id"].tolist() if not suppliers_df.empty else []
    supplier_names = suppliers_df["supplier_name"].tolist() if not suppliers_df.empty else []
    supplier_display = [f"{sid} — {sn}" for sid, sn in zip(supplier_ids, supplier_names)]

    # ---- Add Item ----
    with mtab_add:
        st.subheader("Add New Item")
        with st.form("add_item_form", clear_on_submit=True):
            ac1, ac2 = st.columns(2)
            name = ac1.text_input("Item Name *")
            category = ac2.selectbox("Category *", ["Beverages", "Dairy", "Produce", "Supplies", "Office", "Other"])
            ac3, ac4 = st.columns(2)
            qty = ac3.number_input("Quantity on Hand *", min_value=0.0, step=1.0)
            unit = ac4.selectbox("Unit *", ["units", "kg", "packs", "liters", "reams"])
            ac5, ac6 = st.columns(2)
            expiry = ac5.date_input("Expiry Date *", value=date.today() + timedelta(days=30))
            supplier_sel = ac6.selectbox("Supplier *", supplier_display) if supplier_display else ac6.text_input("Supplier ID *")
            reorder_thresh = st.number_input("Reorder Threshold", min_value=0, value=10, step=1)

            submitted = st.form_submit_button("Add Item", type="primary")
            if submitted:
                sup_id = supplier_sel.split(" — ")[0] if isinstance(supplier_sel, str) and " — " in supplier_sel else supplier_sel
                item_data = {
                    "item_name": name,
                    "category": category,
                    "quantity_on_hand": qty,
                    "unit": unit,
                    "expiry_date": expiry.strftime("%Y-%m-%d"),
                    "supplier_id": sup_id,
                    "reorder_threshold": reorder_thresh,
                }
                ok, errs = validate_item(item_data)
                if ok:
                    new_id = add_item(item_data)
                    st.success(f"✅ Item added with ID **{new_id}** — saved to database.")
                    reload()
                    st.rerun()
                else:
                    for e in errs:
                        st.error(e)

    # ---- Update Item ----
    with mtab_update:
        st.subheader("Update Existing Item")
        item_options = [f"{r['item_id']} — {r['item_name']}" for _, r in items_df.iterrows()] if not items_df.empty else []
        if item_options:
            sel = st.selectbox("Select item to update", item_options, key="update_sel")
            sel_id = sel.split(" — ")[0]
            item_row = items_df[items_df["item_id"] == sel_id].iloc[0]

            with st.form("update_item_form"):
                uc1, uc2 = st.columns(2)
                new_qty = uc1.number_input("Quantity on Hand", min_value=0.0, value=float(item_row["quantity_on_hand"]), step=1.0)
                exp_val = item_row["expiry_date"]
                if isinstance(exp_val, pd.Timestamp):
                    exp_val = exp_val.date()
                new_expiry = uc2.date_input("Expiry Date", value=exp_val)
                uc3, uc4 = st.columns(2)
                sup_idx = supplier_ids.index(item_row["supplier_id"]) if item_row["supplier_id"] in supplier_ids else 0
                new_supplier = uc3.selectbox("Supplier", supplier_display, index=sup_idx)
                new_thresh = uc4.number_input("Reorder Threshold", min_value=0, value=int(item_row["reorder_threshold"]), step=1)
                upd_submitted = st.form_submit_button("Update Item", type="primary")
                if upd_submitted:
                    updates = {
                        "quantity_on_hand": new_qty,
                        "expiry_date": new_expiry.strftime("%Y-%m-%d"),
                        "supplier_id": new_supplier.split(" — ")[0],
                        "reorder_threshold": new_thresh,
                    }
                    try:
                        update_item(sel_id, updates)
                        st.success(f"✅ {sel_id} updated in database.")
                        reload()
                        st.rerun()
                    except Exception as ex:
                        st.error(str(ex))
        else:
            st.info("No items in inventory yet.")

    # ---- Log Usage ----
    with mtab_log:
        st.subheader("Log Item Usage")
        item_options_log = [f"{r['item_id']} — {r['item_name']}" for _, r in items_df.iterrows()] if not items_df.empty else []
        if item_options_log:
            with st.form("usage_form", clear_on_submit=True):
                lu1, lu2, lu3 = st.columns(3)
                log_item = lu1.selectbox("Item", item_options_log, key="log_item")
                log_qty = lu2.number_input("Quantity Used", min_value=0.0, step=1.0)
                log_date = lu3.date_input("Date", value=date.today())
                log_sub = st.form_submit_button("Log Usage", type="primary")
                if log_sub:
                    log_id = log_item.split(" — ")[0]
                    if log_qty <= 0:
                        st.error("Quantity used must be greater than 0.")
                    else:
                        add_usage_log(log_id, log_date.strftime("%Y-%m-%d"), log_qty)
                        cur_item = items_df[items_df["item_id"] == log_id].iloc[0]
                        new_stock = max(0, float(cur_item["quantity_on_hand"]) - log_qty)
                        update_item(log_id, {"quantity_on_hand": new_stock})
                        st.success(f"✅ Logged {log_qty} usage for {log_id}. Stock updated to {new_stock}. Saved to database.")
                        reload()
                        st.rerun()


# ═══════════════════════════════════════════════════════════
#                      SIMULATOR TAB
# ═══════════════════════════════════════════════════════════
with tab_sim:
    st.header("🧪 What-If Purchase Simulator")
    st.caption("Simulate a purchase scenario for a single item. All data fetched from the database.")

    item_options_sim = [f"{r['item_id']} — {r['item_name']}" for _, r in items_df.iterrows()] if not items_df.empty else []
    if not item_options_sim:
        st.info("Add items first to use the simulator.")
    else:
        sim_sel = st.selectbox("Select item to simulate", item_options_sim, key="sim_item")
        sim_id = sim_sel.split(" — ")[0]

        sim_item = get_item_with_supplier(sim_id)
        if not sim_item:
            st.error("Item not found in database.")
        else:
            default_lead = int(sim_item.get("avg_lead_days", 3))

            with st.container():
                exp_display = sim_item['expiry_date']
                if isinstance(exp_display, pd.Timestamp):
                    exp_display = exp_display.date()
                st.markdown(f"**Current stock:** {sim_item['quantity_on_hand']} {sim_item['unit']}  |  "
                            f"**Expiry:** {exp_display}  |  "
                            f"**Lead time:** {default_lead} days")

            st.divider()

            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                sim_order_qty = st.number_input("Order Quantity", min_value=0.0, step=1.0, value=0.0, key="sim_qty")
            with sc2:
                sim_lead_time = st.number_input("Supplier Lead Time (days)", min_value=1, max_value=14, value=default_lead, key="sim_lead")
            with sc3:
                sim_spike = st.slider("Demand Spike %", 0, 50, 0, step=5, key="sim_spike")

            smaller_batch = st.checkbox("Enable smaller-batch mode (halves order qty)", key="sim_batch")

            if st.button("▶️ Run Simulation", type="primary", key="run_sim"):
                with st.spinner("Running simulation..."):
                    result = run_simulation(
                        item=sim_item,
                        usage_logs=usage_df,
                        lead_time_override=sim_lead_time,
                        order_quantity=sim_order_qty,
                        demand_spike_pct=sim_spike,
                        smaller_batch=smaller_batch,
                    )

                # Save to DB
                try:
                    save_simulator_run(
                        item_id=sim_id,
                        order_qty=sim_order_qty,
                        lead_override=sim_lead_time,
                        spike_pct=sim_spike,
                        end_stock=result["ending_stock"],
                        stockout=result["stockout_risk"],
                        waste=result["waste_risk"],
                    )
                except Exception:
                    pass  # non-critical

                # ---- Results ----
                st.subheader("Simulation Results")

                rc1, rc2, rc3, rc4 = st.columns(4)
                rc1.metric("Ending Stock", f"{result['ending_stock']} {sim_item['unit']}")
                rc2.metric("Stockout Risk", "⚠️ Yes" if result["stockout_risk"] else "✅ No")
                rc3.metric("Waste Risk", f"{risk_emoji(result['waste_risk'])} {result['waste_risk'].title()}")

                sus_d = result["sustainability_delta"]
                rc4.metric("Waste Risk Change", sus_d["waste_risk_change"])

                # ---- Stock Projection Chart ----
                st.subheader("Stock Projection (7-day)")
                proj = result["daily_projection"]
                dates = [p["date"] for p in proj]
                stocks = [p["stock"] for p in proj]
                labels = [p["label"] for p in proj]

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=dates, y=stocks,
                    mode="lines+markers",
                    name="Projected Stock",
                    line=dict(color="#2e7d32", width=3),
                    marker=dict(size=8),
                    text=labels,
                    hovertemplate="Day: %{x}<br>Stock: %{y}<br>%{text}<extra></extra>",
                ))
                fig.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Stockout level")
                for p in proj:
                    if "arrived" in p.get("label", ""):
                        fig.add_vline(x=p["date"], line_dash="dot", line_color="blue")
                        fig.add_annotation(
                            x=p["date"], y=0.95, yref="paper",
                            text=p["label"], showarrow=False, xanchor="left"
                        )
                fig.update_layout(
                    xaxis_title="Date", yaxis_title=f"Stock ({sim_item['unit']})",
                    height=350, margin=dict(l=40, r=20, t=30, b=40), template="plotly_white",
                )
                st.plotly_chart(fig, use_container_width=True)

                # ---- Explanation ----
                st.subheader("Scenario Explanation")
                scenario_analysis = result["scenario_analysis"]
                if simulate_ai_off:
                    st.markdown("**📋 Rule-Based Explanation (Fallback)**")
                    st.write(generate_fallback_explanation(scenario_analysis, usage_df))
                else:
                    ai_text, used_ai = cached_generate_ai_explanation(scenario_analysis, insights)
                    if used_ai:
                        st.markdown("**✨ AI-Generated Explanation**")
                        st.write(ai_text)
                    else:
                        st.markdown("**📋 Rule-Based Explanation (Fallback)**")
                        st.write(generate_fallback_explanation(scenario_analysis, usage_df))

                # ---- Sustainability Delta ----
                st.subheader("Sustainability Impact Delta")
                delta_col1, delta_col2, delta_col3 = st.columns(3)
                delta_col1.metric("Waste Risk", sus_d["waste_risk_change"])
                delta_col2.metric("Stock Change", f"{sus_d['stock_delta']:+.1f} {sim_item['unit']}" if sus_d["stock_delta"] else "—")
                delta_col3.metric("Days Remaining Δ", f"{sus_d['days_remaining_delta']:+.1f}" if sus_d["days_remaining_delta"] else "—")
