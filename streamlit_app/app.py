"""
Freight LTL Network Prototype — Streamlit app.
Run:  pip install -r requirements.txt
      streamlit run app.py
Reads sample data from ../data/<scenario>/. All figures ILLUSTRATIVE, not carrier data.
"""
import json
import os

import pandas as pd
import streamlit as st

st.set_page_config(page_title="LTL Network Prototype", layout="wide",
                   page_icon=":truck:")

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
SCENARIOS = ["base", "light", "heavy"]


@st.cache_data
def load_scenario(scenario):
    d = {}
    base = os.path.join(DATA, scenario)
    for name in ["terminals", "lanes", "design_routes", "shippers", "shipments",
                 "forecast_lane", "linehaul_actuals", "deviations",
                 "cost_to_serve", "lane_scoreboard", "tower_events", "tower_actions"]:
        p = os.path.join(base, name + ".csv")
        d[name] = pd.read_csv(p) if os.path.exists(p) else pd.DataFrame()
    with open(os.path.join(base, "kpis.json")) as f:
        d["kpis"] = json.load(f)
    return d


@st.cache_data
def load_all_kpis():
    with open(os.path.join(DATA, "kpis_all.json")) as f:
        return json.load(f)


st.sidebar.title(":truck: LTL Prototype")
scenario = st.sidebar.radio("Volume scenario", SCENARIOS,
                            format_func=lambda s: {"base": "Base day",
                                                   "light": "Light day (-35%)",
                                                   "heavy": "Heavy day (+30%)"}[s])
d = load_scenario(scenario)
k = d["kpis"]
st.sidebar.caption("All figures are illustrative sample data, not carrier operating data.")

st.title("LTL Network Planning Prototype")
st.caption(f"Operating day {k['date']} · 5-terminal cluster (SGF breakbulk hub; STL, MKC, MEM, TUL) · "
           f"scenario: {scenario}")

tabs = st.tabs(["Nightly KPIs", "Network", "Load plan", "Deviations",
                "Control tower", "Cost to serve", "Lane scoreboard",
                "Forecast vs actual", "Methodology", "Ask the network", "Data downloads"])

# ------------------------------ Nightly KPIs ------------------------------
with tabs[0]:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Revenue", f"${k['revenue_usd']:,.0f}")
    c2.metric("Cost to serve", f"${k['cost_to_serve_usd']:,.0f}")
    c3.metric("Margin", f"${k['margin_usd']:,.0f}", f"{k['margin_pct']}%")
    c4.metric("Avg cube utilization", f"{k['avg_cube_util_pct']}%")
    c5.metric("Empty pup slots", f"{k['empty_pup_pct']}%")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Driver turns", k["turns_dispatched"])
    c2.metric("Pups dispatched", k["loads_dispatched"])
    c3.metric("Handles / shipment", k["handles_per_shipment"])
    c4.metric("Deviations", k["deviations"], f"+${k['deviation_savings_usd']:,.0f}")
    c5.metric("Tower actions", k["tower_actions"], f"${k['tower_net_usd']:,.0f} net")
    st.caption("One driver turn = two pups out, two pups back, full or empty. "
               "A turn costs the same either way, so cube utilization is the cost lever; "
               "empty pup slots (not empty miles) are where imbalance shows up.")

    st.subheader("Cost breakdown")
    cost_df = pd.DataFrame({
        "bucket": ["P&D", "Dock handles", "Linehaul"],
        "usd": [k["pud_cost_usd"], k["dock_cost_usd"], k["linehaul_cost_usd"]],
    }).set_index("bucket")
    st.bar_chart(cost_df)

    st.subheader("Scenario comparison")
    allk = load_all_kpis()
    comp = pd.DataFrame(allk).T[["shipments", "revenue_usd", "margin_pct",
                                 "avg_cube_util_pct", "empty_pup_pct",
                                 "handles_per_shipment", "cost_per_shipment_usd",
                                 "deviation_savings_usd", "tower_net_usd"]]
    st.dataframe(comp, use_container_width=True)
    st.caption("Light day: utilization falls, cost/shipment rises, plan consolidates. "
               "Heavy day: directs cut handles to 2.12 and lift utilization to 85%.")

# ------------------------------ Network ------------------------------
with tabs[1]:
    st.subheader("Terminals (nodes)")
    st.dataframe(d["terminals"], use_container_width=True, hide_index=True)
    st.subheader("Linehaul lanes (arcs) — cost/mile varies by domicile pay + demographics")
    st.dataframe(d["lanes"], use_container_width=True, hide_index=True)
    st.subheader("Design routes — the structured network: one standard path per OD x product")
    prod = st.selectbox("Product", ["P", "E"],
                        format_func=lambda p: "Priority (fast)" if p == "P" else "Economy (~1 day slower)")
    st.dataframe(d["design_routes"][d["design_routes"]["product"] == prod]
                 .drop(columns=["product"]), use_container_width=True, hide_index=True)
    st.caption("Planners try to follow the standard path; deviations are cost-driven (see Deviations tab).")
    st.subheader("Pre-approved alternate paths — the monthly design bounds daily execution")
    alt_p = os.path.join(DATA, "alternate_paths.csv")
    if os.path.exists(alt_p):
        alt = pd.read_csv(alt_p)
        st.dataframe(alt[alt["product"] == prod].drop(columns=["product"]),
                     use_container_width=True, hide_index=True)
        st.caption("Daily deviations may ONLY use a listed alternate — never a wild reroute. "
                   "The monthly network design sets the standard; the daily plan deviates within bounds.")

# ------------------------------ Load plan ------------------------------
with tabs[2]:
    st.subheader("Dispatched linehaul pups, grouped into driver turns")
    loads = d["linehaul_actuals"].copy()
    show_empty = st.checkbox("Show empty pups", value=True)
    if not show_empty:
        loads = loads[~loads["empty"]]
    min_util = st.slider("Minimum cube utilization %", 0, 100, 0)
    loads = loads[loads["cube_util_pct"] >= min_util]
    def _row(s):
        return ("background-color: #3a2b2b" if s["empty"] else
                "background-color: #2b3a2b" if s["cube_util_pct"] >= 70 else "")
    cols = ["load_id", "lane", "direction", "turn_no", "trailer_no", "cube_cuft",
            "cube_util_pct", "empty", "flows"]
    st.dataframe(loads[cols].style.apply(lambda r: [_row(r)] * len(cols), axis=1),
                 use_container_width=True, hide_index=True)
    st.caption("Each turn = one driver with two pups (turn_no groups them). The driver goes home "
               "with two pups whether full or empty, so an empty pup's marginal cost is ~$0 — "
               "the waste is density, which is why cube comes first in the optimizer.")

# ------------------------------ Deviations ------------------------------
with tabs[3]:
    st.subheader("Cost-driven deviations from standard paths")
    dev = d["deviations"]
    if dev.empty:
        st.info("No deviations — the standard network handled this day's volume as-is.")
    else:
        st.dataframe(dev, use_container_width=True, hide_index=True)
        st.metric("Total deviation savings",
                  f"${dev['saving'].sum():,.0f}")
    st.caption("Rule: deviate ONLY to minimize total cost (linehaul vs dock handles). "
               "Heavy via-hub flows go direct (cut handles); light direct flows "
               "consolidate via hub (gain density).")

# ------------------------------ Control tower ------------------------------
with tabs[4]:
    st.subheader("Central control tower — day-of volume vs plan")
    st.caption("As freight hits the dock, Central compares projected turns to the plan "
               "and recommends adjustments to the service centers. "
               "Prototype uses rule-based triggers; production pairs optimization with GenAI.")
    ev = d["tower_events"]
    ac = d["tower_actions"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Events", len(ev))
    c2.metric("Recommended actions", len(ac))
    c3.metric("Net impact", f"${k['tower_net_usd']:,.0f}",
              "savings" if k["tower_net_usd"] < 0 else "cost")
    if ev.empty:
        st.info("No interventions — the day is running to plan.")
    else:
        cp = st.selectbox("Checkpoint", ["All"] + sorted(ev["checkpoint"].unique()))
        evf = ev if cp == "All" else ev[ev["checkpoint"] == cp]
        st.dataframe(evf, use_container_width=True, hide_index=True)
        st.subheader("Recommended actions + copilot drafts")
        for _, a in ac[ac["event_id"].isin(evf["event_id"])].iterrows():
            icon = {"add_turn": ":bus:", "cancel_turn": ":scissors:",
                    "adjust_dock": ":warehouse:", "reroute": ":repeat:",
                    "keep_turn": ":octagonal_sign:"}.get(a["action_type"], ":wrench:")
            blocked = str(a.get("network_check", "")).startswith("BLOCKED")
            with st.expander(f"{icon} {a['action_id']} — {a['detail']} "
                             f"({a['cost_impact_usd']:+,.0f}$)".replace("+$", "+$")):
                st.write(f"**Service impact:** {a['service_impact']}")
                st.write(f"**Cost impact:** ${a['cost_impact_usd']:,.0f}")
                if blocked:
                    st.error(f"Network check: {a['network_check']}")
                else:
                    st.success(f"Network check: {a['network_check']}")
                st.info(f"Copilot draft: {a['copilot_message']}")
    st.caption("Every recommendation is network-checked: a turn is a domiciled round trip, "
               "so a cancel must leave room in BOTH directions; a reroute must land in spare "
               "pup slots on the alternate path. Locally-cheap moves that hurt the network are blocked.")

# ------------------------------ Cost to serve ------------------------------
with tabs[5]:
    st.subheader("Cost to serve vs what the customer paid")
    cts = d["cost_to_serve"].copy()
    f1, f2 = st.columns(2)
    custs = ["All"] + sorted(cts["customer"].unique())
    sel_c = f1.selectbox("Customer", custs)
    sel_p = f2.selectbox("Product", ["All", "P", "E"])
    if sel_c != "All":
        cts = cts[cts["customer"] == sel_c]
    if sel_p != "All":
        cts = cts[cts["product"] == sel_p]
    c1, c2, c3 = st.columns(3)
    c1.metric("Shipments", len(cts))
    c2.metric("Avg margin %", f"{cts['margin_pct'].mean():.1f}%" if len(cts) else "—")
    c3.metric("Losing money", f"{(cts['margin_usd'] < 0).sum()} shipments")
    st.dataframe(cts.sort_values("margin_pct")
                 [["shipment_id", "customer", "origin", "dest", "product", "path",
                   "handles", "revenue_usd", "cost_to_serve_usd",
                   "margin_usd", "margin_pct"]],
                 use_container_width=True, hide_index=True)

    st.subheader("Worked example: why did this shipment lose money?")
    if len(cts):
        w = cts.loc[cts["margin_pct"].idxmin()]
        st.write(f"**{w['shipment_id']}** — {w['customer']}, {w['origin']} → {w['dest']} "
                 f"({w['product']}), path `{w['path']}`, {w['handles']} handles")
        legs = [x for x in str(w.get("leg_cost_detail", "")).split(";") if x]
        wdf = pd.DataFrame({
            "component": ["Revenue (what customer paid)", "P&D cost",
                          "Dock cost"] + [f"Linehaul {l.split(':')[0]}" for l in legs],
            "usd": [w["revenue_usd"], -w["pud_cost_usd"], -w["dock_cost_usd"]] +
                   [-float(l.split(":")[1].replace("$", "")) for l in legs],
        })
        st.dataframe(wdf, use_container_width=True, hide_index=True)
        st.write(f"**Margin: ${w['margin_usd']:.2f} ({w['margin_pct']}%)** — small shipment, "
                 "high fixed P&D cost, on an imbalanced leg where it absorbs empty-return cost.")

# ------------------------------ Lane scoreboard ------------------------------
with tabs[6]:
    st.subheader("Leg efficiency — good mile vs bad mile")
    sb = d["lane_scoreboard"].copy()
    verdict_icon = {"good miles": ":green_circle:", "watch": ":yellow_circle:",
                    "bad miles": ":red_circle:"}
    sb["flag"] = sb["verdict"].map(verdict_icon)
    st.dataframe(sb[["flag", "lane", "direction", "miles", "cost_per_mile_usd",
                     "turns", "cube_util_pct", "leg_cost_usd",
                     "cost_per_cube_mile_usd", "verdict"]],
                 use_container_width=True, hide_index=True)
    st.caption("Leg efficiency = allocated leg cost / (cube x miles). "
               "Good miles: >=70% cube on a needed lane. Bad miles: empty or <40%.")

# ------------------------------ Forecast vs actual ------------------------------
with tabs[7]:
    st.subheader("Lane-level forecast (made yesterday) vs actuals")
    fc = d["forecast_lane"].copy()
    fc["cube_err_pct"] = ((fc["forecast_cube_cuft"] - fc["actual_cube_cuft"])
                          / fc["actual_cube_cuft"] * 100).round(1)
    st.metric("Forecast MAPE (cube)", f"{k['forecast_mape_pct']}%")
    st.dataframe(fc.sort_values("cube_err_pct", key=abs, ascending=False),
                 use_container_width=True, hide_index=True)
    st.caption("Planners pre-plan doors and trailers on the forecast using INFERRED cube "
               "(shippers don't provide cube). Dock dimming gives truth — too late to plan on.")

# ------------------------------ Methodology ------------------------------
with tabs[8]:
    st.subheader("Two planning horizons")
    st.markdown("""
**Monthly network design** sets the structure: nodes, arcs, and one standard path per OD x product,
plus a bounded set of pre-approved alternates (`alternate_paths.csv`). Daily execution may ONLY use a
listed alternate — never a wild reroute.
**Daily execution** starts from the standard plan and deviates purely on cost: heavy via-hub flows go
direct (fewer handles), light direct flows consolidate via hub (more density).""")
    st.subheader("Doubles economics — the driver turn is the cost unit")
    st.markdown("""
One driver pulls **two pups** out and brings **two pups** back, full or empty — and the turn costs the
same either way. So the optimizer minimizes **driver turns**, not trailers: `turns = ceil(max(pups each
way) / 2)`. Cube utilization is the dominant lever because filling the second pup on a running turn is
nearly free, while dispatching another driver is the most expensive thing in the network. Imbalance shows
up as **empty pup slots** (not empty miles): the driver comes home regardless.""")
    st.subheader("The math model")
    st.markdown("""
**Decide:** path per OD-product flow (standard / pre-approved alternate) · driver turns per lane (integer) · pup assignments
**Minimize:** `sum(turns x turn_cost) + sum(handles x dock_cost)`
**Subject to:** pup cube (1750 cu ft) + weight caps · product service windows (P: ≤2 legs/600 mi; E: ≤2 legs) ·
domiciled round trips — `turns = ceil(max(pups_AB, pups_BA)/2)`, equipment balances because drivers come home ·
deviations restricted to the pre-approved alternate set · flow conservation at the breakbulk.
**Method (prototype):** transparent greedy deviation search from the standard-path start — every move auditable.
Production path: network MIP (Gurobi / OR-Tools) or a learned optimization proxy.""")
    st.subheader("Control tower — network-global, not local")
    st.markdown("""
Central watches day-of volume at checkpoints (10:00 / 14:00 / 18:00), projects turns vs plan, and
recommends add/cancel/reroute/dock actions. Every recommendation passes a **network check**:
- **Cancel:** a turn is a round trip — the cancel must leave room for projected pups in BOTH directions,
  else it is BLOCKED (a local saving that strands return-leg freight).
- **Surge:** compare adding a turn vs rerouting overflow onto a pre-approved alternate with spare pup
  slots; recommend whichever is cheaper network-wide.
This is the intelligence the tower team shouldn't have to do in their heads.""")
    st.subheader("Conversational copilot (Ask the network)")
    st.markdown("""
The **Ask the network** tab is a grounded GenAI layer: your LLM (OpenAI, Azure, or any OpenAI-compatible
endpoint — bring your own key) answers planner questions using only this scenario's data: KPIs, deviations,
tower events and their network checks, lane scoreboard, cost-to-serve, and the business rules above.
Architecture: **context engineering** (ontology + data as the prompt's ground truth) → **ML** (forecasts,
cube inference) → **OR** (the plan and tower engine) → **GenAI** (explains and converses). The key lives in
the browser session / Streamlit secrets / env var — never in the repo.""")
    st.subheader("Cube inference")
    st.markdown("""
Shippers don't provide cube. The planner infers cube at pickup from the shipper's historical
density profile (`shippers.csv`: lbs per cubic foot by commodity). As freight hits the dock it gets
dimmed — true cube — but that's too late to set up doors and trailers. The sample data carries both
so you can see the planning gap.""")
    st.subheader("Ontology / context engineering")
    st.markdown("""
`data/ontology.yaml` is the machine-readable context layer: entities (Terminal, Lane, Shipment, Turn,
Deviation, CostToServe…), relationships, hard constraints, planner business rules, metric definitions
(good vs bad mile, leg efficiency), the GenAI roles (plan explainer, deviation justifier, cost-to-serve
narrator, exception copilot, C-suite briefer — all grounded on optimizer outputs), and the
implementation stack (Python, MIP, hierarchical lane forecast, density profiles refreshed from dimming,
ML optimization proxy, LLM explainer).""")

# ------------------------------ Ask the network ------------------------------
with tabs[9]:
    st.subheader("Ask the network — conversational copilot")
    st.caption("Grounded in this scenario's data: KPIs, deviations, tower events, lane scoreboard, "
               "cost-to-serve. The model answers only from this context.")

    with st.expander("Connection (your key, your endpoint)", expanded=False):
        key_in = st.text_input("API key", type="password",
                               help="Stored only in this browser session, never in the repo. "
                                    "You can also set it via Streamlit secrets or the OPENAI_API_KEY env var.")
        if key_in:
            st.session_state["llm_key"] = key_in
        base_url = st.text_input("Base URL (OpenAI-compatible)",
                                 value=st.session_state.get("llm_base", "https://api.openai.com/v1"))
        st.session_state["llm_base"] = base_url
        model = st.text_input("Model", value=st.session_state.get("llm_model", "gpt-4o-mini"))
        st.session_state["llm_model"] = model
        st.caption("Works with OpenAI, Azure OpenAI, or any OpenAI-compatible endpoint.")

    api_key = (st.session_state.get("llm_key")
               or st.secrets.get("OPENAI_API_KEY")
               or os.environ.get("OPENAI_API_KEY"))

    def _ctx():
        L = [f"Scenario {scenario} ({k['date']}): {k['shipments']} shipments, "
             f"revenue ${k['revenue_usd']:,.0f}, cost to serve ${k['cost_to_serve_usd']:,.0f}, "
             f"margin {k['margin_pct']}%, avg cube utilization {k['avg_cube_util_pct']}%, "
             f"empty pup slots {k['empty_pup_pct']}%, {k['turns_dispatched']} driver turns, "
             f"{k['handles_per_shipment']} handles/shipment, forecast MAPE {k['forecast_mape_pct']}%."]
        L.append("Economics: one driver turn = two pups out and back, full or empty; a turn costs the same "
                 "either way, so cube utilization is the dominant cost lever. Empty pups ride on running turns "
                 "at ~$0 marginal cost; imbalance shows up as empty pup slots. Domiciled drivers return nightly, "
                 "so a turn is a round trip: cancelling a turn removes capacity in BOTH directions.")
        dev = d["deviations"]
        if not dev.empty:
            L.append("Top deviations (standard -> chosen, saving): " +
                     "; ".join(f"{r['od']} {r['product']}: {r['standard']} -> {r['chosen']} "
                               f"(${r['saving']:,.0f}, {r['reason']})"
                               for _, r in dev.sort_values("saving", ascending=False).head(5).iterrows()))
        ev = d["tower_events"]
        if not ev.empty:
            L.append("Control tower events: " +
                     "; ".join(f"{r['checkpoint']} {r['direction']}: plan {r['planned_turns']} turns, "
                               f"projected {r['projected_turns']} ({r['trigger']})"
                               for _, r in ev.iterrows()))
        ac = d["tower_actions"]
        if not ac.empty:
            L.append("Tower recommendations: " +
                     "; ".join(f"{r['action_type']} ({r['detail'][:80]}); network check: {r['network_check'][:100]}"
                               for _, r in ac.iterrows()))
        sb = d["lane_scoreboard"].sort_values("cost_per_cube_mile_usd", ascending=False).head(5)
        L.append("Most expensive legs ($/cube-mile): " +
                 "; ".join(f"{r['lane']} {r['direction']}: ${r['cost_per_cube_mile_usd']:.4f} "
                           f"(util {r['cube_util_pct']}%, {r['verdict']})" for _, r in sb.iterrows()))
        cts = d["cost_to_serve"]
        cust = (cts.groupby("customer")
                .agg(shipments=("shipment_id", "count"), margin_pct=("margin_pct", "mean"),
                     margin_usd=("margin_usd", "sum"))
                .nsmallest(5, "margin_pct").reset_index())
        L.append("Weakest customers by margin: " +
                 "; ".join(f"{r['customer']}: {r['margin_pct']:.1f}% on {r['shipments']} shipments"
                           for _, r in cust.iterrows()))
        L.append("Business rules: every OD x product has one standard path (monthly network design); "
                 "daily deviations may ONLY use pre-approved alternate paths; deviate only when total cost "
                 "(linehaul turns + dock handles) improves; Priority = fast (<=2 legs, 600 mi), "
                 "Economy = ~1 day slower; shippers don't provide cube - it is inferred at pickup from "
                 "historical density and dimmed on the dock (too late to plan on).")
        return "\n".join(L)

    SYSTEM = ("You are the network copilot for an LTL carrier's central transportation team. "
              "Answer ONLY from the scenario context provided. Be specific: cite lanes, turns, dollars, "
              "and the network check behind each recommendation. If a question cannot be answered from the "
              "context, say so plainly. All figures are illustrative sample data, never carrier operating data. "
              "Keep answers concise and planner-actionable.\n\nSCENARIO CONTEXT:\n" + _ctx())

    sugg = ["Which lanes are the most expensive per cube-mile, and why?",
            "What should Central do about today's tower events?",
            "Where is cube utilization worst, and what would fix it?",
            "Explain the biggest deviation saving in this scenario.",
            "Which customers are we losing money on?"]
    cols = st.columns(len(sugg))
    for i, q in enumerate(sugg):
        if cols[i].button("💬", key=f"sugg_{i}", help=q):
            st.session_state["pending_q"] = q

    if "chat" not in st.session_state:
        st.session_state["chat"] = []
    for m in st.session_state["chat"]:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    pending = st.session_state.pop("pending_q", None)
    prompt = st.chat_input("Ask about this scenario's network, costs, or tower actions…")
    q = pending or prompt
    if q:
        st.session_state["chat"].append({"role": "user", "content": q})
        with st.chat_message("user"):
            st.markdown(q)
        if not api_key:
            msg = ("No API key configured — open **Connection** above and paste your key "
                   "(it stays in this session only), or set `OPENAI_API_KEY` in Streamlit secrets / env.")
            with st.chat_message("assistant"):
                st.warning(msg)
            st.session_state["chat"].append({"role": "assistant", "content": msg})
        else:
            with st.chat_message("assistant"):
                with st.spinner("Thinking…"):
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=api_key,
                                        base_url=st.session_state.get("llm_base",
                                                                     "https://api.openai.com/v1"))
                        hist = [{"role": m["role"], "content": m["content"]}
                                for m in st.session_state["chat"][-10:]]
                        resp = client.chat.completions.create(
                            model=st.session_state.get("llm_model", "gpt-4o-mini"),
                            messages=[{"role": "system", "content": SYSTEM}] + hist,
                            temperature=0.2, max_tokens=800)
                        ans = resp.choices[0].message.content
                    except Exception as e:
                        ans = f"Couldn't reach the model: {e}"
                    st.markdown(ans)
            st.session_state["chat"].append({"role": "assistant", "content": ans})

# ------------------------------ Data downloads ------------------------------
with tabs[10]:
    st.subheader("Download the sample data")
    for name in ["terminals", "lanes", "design_routes", "shippers", "shipments",
                 "forecast_lane", "linehaul_actuals", "deviations",
                 "cost_to_serve", "lane_scoreboard", "tower_events", "tower_actions"]:
        p = os.path.join(DATA, scenario, name + ".csv")
        if os.path.exists(p):
            with open(p, "rb") as f:
                st.download_button(f"{name}.csv", f, file_name=f"{scenario}_{name}.csv",
                                   key=f"dl_{scenario}_{name}")
    for extra, fname in [("alternate_paths.csv", "alternate_paths.csv"),
                         ("ontology.yaml", "ontology.yaml")]:
        op = os.path.join(DATA, extra)
        if os.path.exists(op):
            with open(op, "rb") as f:
                st.download_button(fname, f, file_name=fname,
                                   key=f"dl_{fname}")
