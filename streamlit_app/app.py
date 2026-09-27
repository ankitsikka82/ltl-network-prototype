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
                 "cost_to_serve", "lane_scoreboard", "tower_events", "tower_actions",
                 "bids", "bid_opportunities"]:
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
st.caption(f"Operating day {k['date']} · hub-and-spoke: SGF + MEM breakbulk hubs "
           f"(spokes STL/TUL, MKC/LIT) · scenario: {scenario}")

tabs = st.tabs(["Start here", "Network", "Nightly KPIs", "Load plan", "Deviations",
                "Control tower", "Cost to serve", "Lane scoreboard",
                "Forecast vs actual", "Ontology & context", "Methodology",
                "Ask the network", "Data downloads"])

# ------------------------------ Start here ------------------------------
with tabs[0]:
    st.subheader("What this is")
    st.markdown("""
This is a **working prototype of the AI planning stack for an LTL freight network** — not a slide
deck, a running model. Every number in it is computed from sample data by the same rules a production
system would use: doubles economics, a monthly network design, cost-driven deviations, and a central
control tower that checks every move against the whole network. All figures are **illustrative sample
data**, not carrier operating data.""")
    st.subheader("Its purpose")
    st.markdown("""
It answers the three questions executives and planners actually ask about AI in freight:
1. **How does AI fit into network planning?** — as a stack of four layers, each doing the job it's good at.
2. **Where does each kind of AI earn its keep?** — ML predicts, OR decides, GenAI explains. Nothing is used where it adds no value.
3. **What would it take to run this for real?** — the data, the models, and the context layer, all visible in this app.""")
    st.subheader("The stack — four layers, four jobs")
    st.graphviz_chart("""
digraph {
  rankdir=LR;
  node [shape=box, style="rounded,filled", fillcolor=white];
  ctx [label="Context engineering\\nthe shared truth", fillcolor=gold, shape=cylinder];
  ml [label="ML\\nPREDICTS\\nforecasts · cube inference"];
  or [label="OR\\nDECIDES\\nplan · deviations · tower"];
  gen [label="GenAI\\nEXPLAINS\\nanswers · drafts · chats"];
  ctx -> ml [label="feature defs"];
  ctx -> or [label="constraints"];
  ctx -> gen [label="ground truth"];
  ml -> or [label="demand + cube"];
  or -> gen [label="decisions"];
}""", use_container_width=True)
    r1, r2, r3, r4 = st.columns(4)
    with r1:
        st.markdown("**Context engineering**\n\nThe ontology + data dictionary: entities, constraints, business rules, metric definitions. Every other layer reads the same truth, so the forecaster, the optimizer, and the explainer never disagree about what a *lane*, a *turn*, or a *good mile* is.")
    with r2:
        st.markdown("**ML — predicts**\n\nLane-level demand forecasts and pickup cube inference (shippers don't provide cube; density profiles infer it). Used *only* where prediction beats a rule — never for decisions.")
    with r3:
        st.markdown("**OR — decides**\n\nThe nightly plan, bid schedules, cut-time optimization, cost-driven deviations, and tower recommendations. Minimizes driver turns + dock handles subject to hard constraints. Math, not vibes — every move is auditable.")
    with r4:
        st.markdown("**GenAI — explains**\n\nThe copilot answers questions and drafts service-center messages, grounded *only* on optimizer outputs + the ontology. It never decides and never invents a number — if it can't check it, it says so.")
    st.subheader("Business architecture — three horizons, one network")
    b1, b2, b3 = st.columns(3)
    with b1:
        st.markdown("**Monthly — network design**\n\nNodes, arcs, one standard path per OD × product, plus a small bounded set of pre-approved alternates. This is the structure everything else must respect.")
    with b2:
        st.markdown("**Daily — execution**\n\nStart from the standard plan. Deviate *only* onto a pre-approved alternate, *only* when total network cost (turns + handles) improves. Cube first, fewest drivers, fewest touches.")
    with b3:
        st.markdown("**Intraday — control tower**\n\nCentral watches volume at 10:00 / 14:00 / 18:00, projects turns vs plan, and recommends add / cancel / reroute / dock / cut-time moves — each network-checked, because a turn is a round trip.")
    st.subheader("Tech architecture — what runs where")
    st.markdown("""
`data_build/build.py` (deterministic, seeded) generates the sample world → CSVs + `ontology.yaml` →
this Streamlit app computes KPIs, plans, deviations, and tower moves live → the **Ask the network**
tab calls *your* LLM (Anthropic or OpenAI-compatible, your key) with a prompt built only from this
scenario's data. Swap the CSVs for real feeds and the heuristic for a MIP solver, and the architecture
doesn't change.""")
    st.subheader("Guided demo — five steps, about ten minutes")
    st.markdown("""
**1. Network** — the playing field. Press ▶ and watch a Priority shipment ride TUL → SGF → MEM → MKC:
spoke to hub, hub to hub, hub to spoke. Note the two gold breakbulk hubs: that's where handles happen,
and handles cost money. Toggle the relay overlay: blue diamonds are driver-swap points on long lanes —
the trailer keeps rolling while drivers stay within hours-of-service. A relay point can be a full
center or just a meet point; the freight path and the driver path are two different things.
**2. Nightly KPIs + Load plan** — the plan the optimizer built: 29 driver turns, 76.0% cube, $158k cost
to serve. Open the load plan and see **bid departures** — drivers leave on bid times (17:00 / 21:00
outbound, 09:00 / 12:00 AM), and the cut-time opportunities show where shifting a cut to a later bid
saves a whole driver shift. Some pups run empty, because the driver comes home either way.
**3. Deviations** — seven times the plan beat the standard path, saving $7,238. Heavy via-hub flows went direct (fewer handles); light bypasses consolidated via hub (more density).
**4. Control tower** — the day goes off-plan at 10:00. Read the **move of the day**: the cancel the agent *blocked*, and why. Then open the **what-if simulator** and surge a lane yourself — watch the same network check work your scenario.
**5. Ask the network** — interrogate it. It can only answer from the data: lanes, turns, dollars, rules.
*Short on time? Do 1, 4, and 5 — that's the whole thesis in three minutes.*""")
    st.caption("Planners: the tower tab is your desk. Executives: this page plus the Ontology & context tab is the governance story.")

# ------------------------------ Network (start here) ------------------------------
with tabs[1]:
    st.caption("Start here: this is the network the whole app reasons about. "
               "Five terminals, SGF as the breakbulk hub, linehaul lanes between them, "
               "and one standard path per OD × product from the monthly design.")

    def _network_dot(highlight=(), show_relay=True):
        """highlight: set of 'A>B' legs to draw bold red.
        Relay: lanes over ~250 mi get a midpoint diamond - the trailer keeps rolling
        while drivers swap, so each driver stays within hours-of-service."""
        lines = ["digraph {", "  rankdir=LR;", "  node [shape=circle, style=filled, fillcolor=white];"]
        for _, t in d["terminals"].iterrows():
            if t["type"] == "breakbulk":
                lines.append(f'  {t["terminal"]} [shape=doublecircle, fillcolor=gold, '
                             f'label="{t["terminal"]}\\nbreakbulk"];')
            else:
                lines.append(f'  {t["terminal"]} [label="{t["terminal"]}\\n{t["city"].split()[0]}"];')
        for _, l in d["lanes"].iterrows():
            a, b = l["terminal_a"], l["terminal_b"]
            mi = int(l["miles"])
            relayed = show_relay and mi > 250
            if relayed:
                r = f"R_{a}_{b}"
                lines.append(f'  {r} [shape=diamond, fillcolor=lightblue, '
                             f'label="relay\\n~{mi // 2} mi"];')
            for x, y in ((a, b), (b, a)):
                hl = f"{x}>{y}" in highlight
                if relayed:
                    r = f"R_{a}_{b}"
                    col = "red" if hl else "steelblue"
                    pw = ", penwidth=3.0" if hl else ""
                    lines.append(f'  {x} -> {r} [color={col}{pw}, style=dotted];')
                    lines.append(f'  {r} -> {y} [label="{mi} mi", color={col}{pw}];')
                elif hl:
                    lines.append(f'  {x} -> {y} [label="{mi} mi", color=red, penwidth=3.0];')
                else:
                    lines.append(f'  {x} -> {y} [label="{mi} mi", color=gray70];')
        lines.append("}")
        return "\n".join(lines)

    st.subheader("Network map — nodes and linehaul arcs")
    show_relay = st.checkbox("Show relay points (lanes over ~250 mi)", value=True,
                             help="We run a relay network: on long lanes the trailer keeps rolling "
                             "while drivers swap at the midpoint, so each driver stays within "
                             "hours-of-service. Freight path and driver path are two different things.")
    st.graphviz_chart(_network_dot(show_relay=show_relay), use_container_width=True)
    st.caption("Arcs are linehaul lanes (miles shown). Gold double-circle = breakbulk hub "
               "where freight cross-docks; the rest are end-of-line centers doing local P&D. "
               "Blue diamonds = relay points: driver swap, no freight handling.")
    with st.expander("🔁 Relay network: two networks, not one"):
        st.markdown("""
**The freight network** (shipments, handles, breakbulk sorts) decides cost and service.
**The driver network** (relay legs, domiciles, hours-of-service) decides who actually drives.

A lane marked **direct** means *no freight handling* between origin and destination — but the
**driver may still relay**: on lanes over ~250 miles (≈5h each way) the trailer swaps drivers
at the midpoint because no same-day round trip fits inside 11 driving hours. Each relay-leg
turn is domiciled at its home end, so a lane-turn decomposes into one relay-leg turn per leg.

A shipment can also flow *through another center* when the driver needs to get home within
hours — that's a driver-path decision, not a freight deviation, and it costs no extra handles.""")
        rl = d["lanes"][d["lanes"]["miles"] > 250].copy()
        rl["relay_legs"] = "2 × ~" + (rl["miles"] // 2).astype(int).astype(str) + " mi"
        rl["domiciles"] = rl["terminal_a"] + " + " + rl["terminal_b"]
        st.dataframe(rl[["terminal_a", "terminal_b", "miles", "relay_legs", "domiciles"]]
                     .rename(columns={"terminal_a": "from", "terminal_b": "to"}),
                     use_container_width=True, hide_index=True)
        st.caption("Prototype costs the lane at its blended $/mi (turn = 2 × miles × $/mi). "
                   "Production prices each relay leg at its own domicile's $/mi.")

    st.subheader("Operating cycles — the rhythm of the night")
    st.markdown("""
The linehaul day runs in three cycles. Every directed lane belongs to exactly one cycle per night:

- **Outbound 12:00–21:00** — spokes dispatch to their hubs (STL→SGF, TUL→SGF, MKC→MEM, LIT→MEM),
  plus the SGF→MEM hub-to-hub move. Bid departures at **17:00** and the **21:00 cut**.
- **Hub sort 21:00–05:00** — breakbulks cross-dock. No scheduled linehaul; this is where handles happen.
- **AM 05:00–12:00** — hubs dispatch to spokes (SGF→STL, SGF→TUL, MEM→MKC, MEM→LIT),
  plus the MEM→SGF hub-to-hub return. Bid departures at **09:00** and the **12:00 cut**.

Drivers bid on start times: each bid departure that carries freight needs its own drivers —
one driver pulls two pups. Day-to-day volume decides how many drivers each bid needs; the
*cut-time optimizer* (Load plan tab) finds bids whose freight could ride a later cut with
fewer drivers.""")

    st.subheader("Watch a shipment move")
    st.caption("A Priority shipment TUL → MKC rides the standard path TUL → SGF → MEM → MKC: "
               "spoke to hub, hub to hub, hub to spoke. Press play to animate it across the map.")
    legs = ["TUL>SGF", "SGF>MEM", "MEM>MKC"]
    if st.button("▶ Play shipment flow"):
        ph = st.empty()
        ph.graphviz_chart(_network_dot(show_relay=show_relay), use_container_width=True)
        import time as _t
        for i, leg in enumerate(legs):
            _t.sleep(0.9)
            ph.graphviz_chart(_network_dot(set(legs[:i + 1]), show_relay=show_relay),
                              use_container_width=True)
        _t.sleep(0.6)
        _lm = d["lanes"].set_index(["terminal_a", "terminal_b"])["miles"]
        _mi = (int(_lm.loc[("SGF", "TUL")]) + int(_lm.loc[("SGF", "MEM")])
               + int(_lm.loc[("MEM", "MKC")]))
        st.success(f"TUL → SGF → MEM → MKC: cross-docks at two hubs, path miles ≈ {_mi}. "
                   "The SGF → MEM leg is relayed — drivers swap at the midpoint, the freight "
                   "never touches the dock.")

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

# ------------------------------ Nightly KPIs ------------------------------
with tabs[2]:
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

# ------------------------------ Load plan ------------------------------
with tabs[3]:
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
    cols = ["load_id", "lane", "direction", "bid_id", "depart_time", "turn_no", "trailer_no",
            "cube_cuft", "cube_util_pct", "empty", "flows"]
    st.dataframe(loads[cols].style.apply(lambda r: [_row(r)] * len(cols), axis=1),
                 use_container_width=True, hide_index=True)
    st.caption("Each turn = one driver with two pups (turn_no groups them within a bid). Drivers leave on "
               "bid departures — 17:00 / 21:00 cut outbound, 09:00 / 12:00 cut AM. The driver goes home "
               "with two pups whether full or empty, so an empty pup's marginal cost is ~$0 — "
               "the waste is density, which is why cube comes first in the optimizer.")

    st.subheader("Bid schedule — who leaves when")
    bids = d["bids"]
    st.dataframe(bids, use_container_width=True, hide_index=True)
    st.caption("First-leg freight becomes available across the cycle as pickups complete, so it splits "
               "across bids; transfer freight (already at the hub) rides the first bid. Each bid with "
               "freight needs its own drivers: ceil(pups / 2).")

    st.subheader("Cut-time opportunities — the optimizer's bid-level findings")
    st.markdown("""
**Idea:** when freight is thin across two bids, one later departure can do the work of two —
*shift the cut* and save a driver shift. The optimizer checks every directed lane: if merging the
early bid into the cut bid needs fewer drivers **and** the lane still staffs fewer round trips,
that's a structural opportunity (monthly-design level). The same math runs day-of in the
simulator, where a light-volume day can cancel a bid that the design keeps.""")
    opps = d["bid_opportunities"]
    if opps.empty:
        st.info("No structural cut-time opportunities in this scenario — the bid schedule is already tight.")
    else:
        def _svc(s):
            return ("background-color: #2b3a2b" if s["service_check"] == "OK"
                    else "background-color: #3a2f2b")
        ocols = ["opp_id", "direction", "cycle", "detail", "pups_early", "pups_cut",
                 "drivers_now", "drivers_merged", "turns_saved_lane", "saving_usd",
                 "priority_in_early", "service_check"]
        st.dataframe(opps[ocols].style.apply(lambda r: [_svc(r)] * len(ocols), axis=1),
                     use_container_width=True, hide_index=True)
        st.metric("Total structural cut-time savings", f"${opps['saving_usd'].sum():,.0f}",
                  f"{int(opps['turns_saved_lane'].sum())} driver shifts")
        with st.expander("Service check details"):
            for _, o in opps.iterrows():
                st.write(f"**{o['opp_id']}** ({o['service_check']}): {o['service_note']}")
    st.caption("OK = Priority freight keeps its sort/delivery slack. REVIEW = the merge pushes Priority "
               "freight later — a planner decision, with the tradeoff priced. Nothing here moves freight "
               "without the service math attached.")

# ------------------------------ Deviations ------------------------------
with tabs[4]:
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
with tabs[5]:
    st.subheader("Central control tower — day-of volume vs plan")
    st.caption("As freight hits the dock, Central compares projected turns to the plan "
               "and recommends adjustments to the service centers. "
               "Prototype uses rule-based triggers; production pairs optimization with GenAI.")

    ev = d["tower_events"]
    ac = d["tower_actions"]

    # ---- Move of the day: the most instructive recommendation ----
    st.subheader("Move of the day")
    blocked = ac[ac["network_check"].str.startswith("BLOCKED", na=False)]
    if not blocked.empty:
        m = blocked.iloc[0]
        mev = ev[ev["event_id"] == m["event_id"]].iloc[0]
        st.warning(f"**{m['action_id']} — the move we did NOT make** ({mev['checkpoint']}, {mev['direction']})")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**What the local view said:**\n\n"
                        f"Volume is short on {mev['direction']} — cancelling a turn looks like "
                        "an easy saving. Any service center manager would take it.")
        with c2:
            st.markdown("**What the network check said:**\n\n"
                        f"{m['network_check']} "
                        "A turn is a domiciled round trip: cancelling it removes capacity in *both* directions.")
        st.caption("This is the tower's real job — not saying yes to the obvious, but knowing when the "
                   "obvious is wrong for the network. Try it yourself in the simulator below.")
        if st.button("💬 Ask the copilot about this move", key="ask_hero"):
            st.session_state["pending_q"] = (
                f"At {mev['checkpoint']} there was a {mev['trigger']} on {mev['direction']} "
                f"(plan {mev['planned_turns']} turns, projected {mev['projected_turns']}). "
                f"Why was cancelling a turn BLOCKED, and what did the network check find?")
            st.info("Question queued — open the **Ask the network** tab and it will ask automatically.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Events", len(ev))
    c2.metric("Recommended actions", len(ac))
    c3.metric("Net impact", f"${k['tower_net_usd']:,.0f}",
              "savings" if k["tower_net_usd"] < 0 else "cost")

    # ---- What-if simulator ----
    st.subheader("What-if simulator — you be the tower")
    st.caption("Pick a lane direction and shock its volume. The simulator runs the *same rules* as the "
               "nightly engine, now bid-aware: each bid's freight needs ceil(pups/2) drivers · a direction "
               "staffs the sum of its bids · the lane staffs the max of its directions (domiciled round "
               "trips) · turn cost = 2 × miles × $/mi · reroutes only onto pre-approved alternates with "
               "spare pup slots · a cancel must leave room in BOTH directions · a cut-shift merges two "
               "thin bids into one departure.")
    loads = d["linehaul_actuals"]
    loaded = loads[~loads["empty"]]
    bids = d["bids"]
    opps = d["bid_opportunities"]
    pups_dir = loaded.groupby(["lane", "direction"]).size()
    pups_lane = loaded.groupby("lane").size()
    turns_dir = loads.groupby(["lane", "direction"])["turn_no"].max().fillna(0).astype(int)
    turns_lane = turns_dir.groupby("lane").max()
    # lane lookup by unordered endpoint pair -> {miles, cpm, disp (plan lane string)}
    # (lane_scoreboard carries miles + $/mi for every lane in the plan, incl. deviation directs)
    lane_lookup = {}
    for _, l in d["lane_scoreboard"].drop_duplicates("lane").iterrows():
        key = frozenset(str(l["lane"]).split("-"))
        lane_lookup[key] = {"miles": int(l["miles"]), "cpm": float(l["cost_per_mile_usd"]),
                            "disp": l["lane"]}
    def _lane_of(a, b):
        return lane_lookup[frozenset([a, b])]
    dirs = sorted(loaded["direction"].unique())
    sim_dir = st.selectbox("Lane direction", dirs, index=dirs.index("SGF>MEM") if "SGF>MEM" in dirs else 0)
    delta = st.slider("Volume change on this direction", -100, 100, 40, 5,
                      format="%d%%", help="Positive = surge, negative = shortfall. "
                      "-100% means the direction goes to zero.")
    a, b = sim_dir.split(">")
    rev = f"{b}>{a}"
    info = _lane_of(a, b)
    lane_disp, miles, cpm = info["disp"], info["miles"], info["cpm"]
    p_out = int(pups_dir.get((lane_disp, sim_dir), 0))
    p_in = int(pups_dir.get((lane_disp, rev), 0))
    # the plan's bid split for this direction (first-leg freight spreads across bids)
    bb = bids[(bids["lane"] == lane_disp) & (bids["direction"] == sim_dir)].sort_values("depart_time")
    f1 = (bb.iloc[0]["pups"] / max(1, bb["pups"].sum())) if not bb.empty else 0.6
    planned_dir = int(turns_dir.get((lane_disp, sim_dir), 0))
    planned_other = int(turns_dir.get((lane_disp, rev), 0))
    planned_lane = max(planned_dir, planned_other)
    new_out = max(0, round(p_out * (1 + delta / 100)))
    import math as _m
    def _drivers(p):
        return _m.ceil(p / 2) if p > 0 else 0
    if new_out == 0:
        d_new_dir, p1n, p2n = 0, 0, 0
    else:
        p1n = round(new_out * f1)
        p2n = new_out - p1n
        d_new_dir = _drivers(p1n) + _drivers(p2n)
    need_lane = max(d_new_dir, planned_other)
    gap = need_lane - planned_lane
    turn_cost = 2 * miles * cpm
    DOCK = 14.0
    # cut-shift: what if the shocked direction's bids merged into the cut departure?
    cut_save, cut_note, cut_svc = 0, "", ""
    if new_out > 0 and len(bb) == 2:
        merged_d = _drivers(new_out)
        if merged_d < d_new_dir and max(merged_d, planned_other) < need_lane:
            cut_save = need_lane - max(merged_d, planned_other)
            m = opps[opps["direction"] == sim_dir]
            cut_svc = m.iloc[0]["service_check"] if not m.empty else "REVIEW"
            cut_note = (f"merge the {bb.iloc[0]['depart_time']} bid into the "
                        f"{bb.iloc[1]['depart_time']} cut on {sim_dir}")
    st.write(f"**Now:** {p_out} pups {sim_dir} / {p_in} pups {rev} → {planned_lane} lane turns "
             f"({planned_dir} departures {sim_dir} + {planned_other} {rev}; turn = ${turn_cost:,.0f}). "
             f"**After {delta:+d}%:** {new_out} pups → **{need_lane} turns needed** (gap {gap:+d}).")
    if miles > 250:
        st.caption(f"🔁 Relay lane ({miles} mi > ~250 mi): each lane-turn = 2 relay-leg turns "
                   f"(~{miles // 2} mi each, drivers swap at midpoint, freight never touches the dock). "
                   f"A cancel here frees one driver at each domicile.")
    verdict, detail, impact = None, "", 0.0
    if gap > 0:
        overflow = new_out - planned_dir * 2
        # candidate ODs whose standard path uses this leg -> pre-approved alternate w/ spare slots
        dr = d["design_routes"]
        cand = dr[dr["standard_path"].str.contains(sim_dir, regex=False)]
        alt_p = os.path.join(DATA, "alternate_paths.csv")
        alt = pd.read_csv(alt_p) if os.path.exists(alt_p) else pd.DataFrame()
        best = None
        for _, r in cand.iterrows():
            a2 = alt[(alt["origin"] == r["origin"]) & (alt["dest"] == r["dest"]) &
                     (alt["product"] == r["product"]) & (alt["rank"] == 2)]
            if a2.empty:
                continue
            legs = a2.iloc[0]["path"].split(">")
            legs = [(legs[i], legs[i + 1]) for i in range(len(legs) - 1)]
            spare, ok = 0, True
            for x, y in legs:
                key = frozenset([x, y])
                if key not in lane_lookup:
                    ok = False  # alternate leg not in the plan -> cannot absorb (build.py rule)
                    break
                lk = lane_lookup[key]["disp"]
                if lk not in turns_lane.index:
                    ok = False
                    break
                spare += max(0, int(turns_lane[lk]) * 2 - int(pups_lane.get(lk, 0)))
            if ok and (best is None or spare > best[0]):
                best = (spare, f"{r['origin']}>{r['dest']}/{r['product']}",
                        ">".join(a2.iloc[0]["path"].split(">")))
        if best and best[0] >= overflow:
            # shipments per pup on this direction (for handle-cost estimate)
            sh = d["shipments"].merge(dr, on=["origin", "dest", "product"], how="left")
            nsh = int(sh[sh["standard_path"].str.contains(sim_dir, regex=False, na=False)].shape[0])
            spp = nsh / max(1, p_out)
            cost = overflow * spp * 2 * DOCK
            verdict = ("REROUTE", f"network-OK: alternate {best[2]} ({best[1]}) has {best[0]} spare pup "
                       f"slots ≥ {overflow} overflow pups — linehaul rides ~free on running turns",
                       cost,
                       f"Reroute the overflow via the pre-approved alternate. Cost ≈ ${cost:,.0f} "
                       f"in extra dock handles (2 per shipment); no new driver turn needed.")
        else:
            cost = gap * turn_cost
            why = (f"no pre-approved alternate with ≥{overflow} spare pup slots"
                   + (f" (best: {best[0]} on {best[2]})" if best else ""))
            verdict = ("ADD TURN", f"network-OK: {why}; new turn is the network-cheapest option",
                       cost,
                       f"Add {gap} driver turn(s) on {sim_dir}: +${cost:,.0f}. Protects on-time; "
                       f"covers the surge cube.")
    elif gap < 0:
        # cancel check (build.py rule): the shocked direction drops to d_new_dir departures and the
        # lane staffs need_lane domiciled round trips; those must still cover the return leg's pups
        if p_in <= need_lane * 2:
            save = -gap * turn_cost
            verdict = ("CANCEL", "network-OK: remaining round trips cover projected pups in BOTH directions",
                       -save,
                       f"Cancel {-gap} turn(s) on {lane_disp}: −${save:,.0f}. Consolidate remaining "
                       f"freight onto running turns; the return leg still rides the round trips.")
        else:
            verdict = ("KEEP", f"BLOCKED: cancelling looks like a ${-gap * turn_cost:,.0f} local saving, "
                       f"but the return direction still needs the pups — drivers are domiciled round trips",
                       0.0,
                       "Do NOT cancel. A local saving that strands return-leg freight is worse for the network.")
    else:
        verdict = ("HOLD", "network-OK: planned turns still cover the shocked volume",
                   0.0, "No action — the plan absorbs this.")
    label, netchk, impact, rec = verdict
    if label in ("REROUTE", "ADD TURN"):
        st.success(f"**Recommendation: {label}** — {rec}")
    elif label == "CANCEL":
        st.success(f"**Recommendation: {label}** — {rec}")
    elif label == "KEEP":
        st.error(f"**Recommendation: {label} THE TURN** — {rec}")
    else:
        st.info(f"**Recommendation: {label}** — {rec}")
    st.write(f"**Network check:** {netchk}")
    st.write(f"**Cost impact:** ${impact:+,.0f} · **Service:** "
             f"{'protects on-time; covers surge cube' if gap > 0 else 'no service risk at projected volume' if gap < 0 else 'none'}")
    if cut_save > 0:
        st.warning(f"**Alternative: SHIFT CUT** — {cut_note}: saves {cut_save} driver shift(s) "
                   f"(−${cut_save * turn_cost:,.0f}); service check **{cut_svc}**. "
                   "Same math as the structural cut-time opportunities, applied to today's volume "
                   "instead of the monthly design — the day-of version of the same lever.")
    if st.button("💬 Ask the copilot about this simulation", key="ask_sim"):
        st.session_state["pending_q"] = (
            f"What-if: volume on {sim_dir} changes {delta:+d}% (pups {p_out} → {new_out}, "
            f"planned lane turns {planned_lane}, needed {need_lane}). The simulator recommends {label}: {rec} "
            f"Network check: {netchk} Cost impact ${impact:+,.0f}. "
            f"Explain whether you agree and what Central should tell the service center.")
        st.info("Question queued — open the **Ask the network** tab and it will ask automatically.")

    # ---- Full event/action log ----
    st.subheader("All tower events & actions")
    if ev.empty:
        st.info("No interventions — the day is running to plan.")
    else:
        cp = st.selectbox("Checkpoint", ["All"] + sorted(ev["checkpoint"].unique()))
        evf = ev if cp == "All" else ev[ev["checkpoint"] == cp]
        st.dataframe(evf, use_container_width=True, hide_index=True)
        st.subheader("Recommended actions + copilot drafts")
        for _, act in ac[ac["event_id"].isin(evf["event_id"])].iterrows():
            icon = {"add_turn": ":bus:", "cancel_turn": ":scissors:",
                    "adjust_dock": ":warehouse:", "reroute": ":repeat:",
                    "keep_turn": ":octagonal_sign:"}.get(act["action_type"], ":wrench:")
            blk = str(act.get("network_check", "")).startswith("BLOCKED")
            with st.expander(f"{icon} {act['action_id']} — {act['detail']} "
                             f"({act['cost_impact_usd']:+,.0f}$)".replace("+$", "+$")):
                st.write(f"**Service impact:** {act['service_impact']}")
                st.write(f"**Cost impact:** ${act['cost_impact_usd']:,.0f}")
                if blk:
                    st.error(f"Network check: {act['network_check']}")
                else:
                    st.success(f"Network check: {act['network_check']}")
                st.info(f"Copilot draft: {act['copilot_message']}")
    st.caption("Every recommendation is network-checked: a turn is a domiciled round trip, "
               "so a cancel must leave room in BOTH directions; a reroute must land in spare "
               "pup slots on the alternate path. Locally-cheap moves that hurt the network are blocked.")

# ------------------------------ Cost to serve ------------------------------
with tabs[6]:
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
with tabs[7]:
    st.subheader("Leg efficiency — good mile vs bad mile")
    sb = d["lane_scoreboard"].copy()
    verdict_icon = {"good miles": ":green_circle:", "watch": ":yellow_circle:",
                    "bad miles": ":red_circle:"}
    sb["flag"] = sb["verdict"].map(verdict_icon)
    st.dataframe(sb[["flag", "lane", "direction", "miles", "cost_per_mile_usd",
                     "drivers_this_dir", "turns", "cube_util_pct", "leg_cost_usd",
                     "cost_per_cube_mile_usd", "verdict"]]
                 .rename(columns={"drivers_this_dir": "drivers (this dir)",
                                   "turns": "lane turns"}),
                 use_container_width=True, hide_index=True)
    st.caption("Leg efficiency = allocated leg cost / (cube x miles). "
               "Drivers (this dir) = bid departures staffed that way; lane turns = max of both "
               "directions (domiciled round trips). Good miles: >=70% cube on a needed lane. "
               "Bad miles: empty or <40%.")

# ------------------------------ Forecast vs actual ------------------------------
with tabs[8]:
    st.subheader("Lane-level forecast (made yesterday) vs actuals")
    fc = d["forecast_lane"].copy()
    fc["cube_err_pct"] = ((fc["forecast_cube_cuft"] - fc["actual_cube_cuft"])
                          / fc["actual_cube_cuft"] * 100).round(1)
    st.metric("Forecast MAPE (cube)", f"{k['forecast_mape_pct']}%")
    st.dataframe(fc.sort_values("cube_err_pct", key=abs, ascending=False),
                 use_container_width=True, hide_index=True)
    st.caption("Planners pre-plan doors and trailers on the forecast using INFERRED cube "
               "(shippers don't provide cube). Dock dimming gives truth — too late to plan on.")

# ------------------------------ Ontology & context ------------------------------
with tabs[9]:
    st.subheader("Context engineering: the layer everything else stands on")
    st.markdown("""
**Context engineering** is the discipline of giving every AI in the stack the same, complete,
machine-readable picture of the operation — so the forecaster, the optimizer, and the explainer
all reason from one shared truth instead of three private guesses.""")
    st.subheader("What it is in this network")
    st.markdown("""
In this prototype the context layer is **`data/ontology.yaml`** plus **`data/DATA_DICTIONARY.md`**:
a formal model of the freight world. It names the **entities** (Terminal, Lane, Product,
DesignRoute, Shipment, LaneForecast, LinehaulActual, Turn, Deviation, CostToServe, TowerEvent,
TowerAction), their **relationships** (a Turn runs on a Lane; a Deviation replaces a DesignRoute;
a TowerAction responds to a TowerEvent), the **hard constraints** (pup cube/weight caps, product
service windows, domiciled round trips, deviations only on pre-approved alternates), the
**business rules** (deviate only when total cost improves; cube first; fill running turns before
adding drivers), and the **metric definitions** (good vs bad mile, leg efficiency, handles/shipment).
Nothing here is prose for humans — it is structured context machines can check against.""")
    st.subheader("How it's set up")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
**Built once, used everywhere:**
1. Operators + data scientists write the rules down (the monthly design, service windows, cost levers).
2. They are encoded as structured YAML + the data dictionary — versioned like code.
3. `data_build/build.py` enforces them when generating the plan (deviations only on listed alternates, turns as round trips).
4. The copilot receives them as ground truth in every prompt — it can quote a rule, never invent one.""")
    with c2:
        st.markdown("**The actual file — the whole context layer fits on one screen:**")
        op = os.path.join(DATA, "ontology.yaml")
        if os.path.exists(op):
            with open(op) as f:
                st.code(f.read(), language="yaml")
    st.subheader("Its role in the stack")
    st.graphviz_chart("""
digraph {
  rankdir=LR;
  node [shape=box, style=filled, fillcolor=white];
  ctx [label="Context\\n(ontology + data)", fillcolor=gold, shape=cylinder];
  ml [label="ML\\n(forecast, cube inference)"];
  or [label="OR\\n(plan, deviations, tower)"];
  gen [label="GenAI\\n(explains, drafts, chats)"];
  ctx -> ml [label="feature defs"];
  ctx -> or [label="constraints"];
  ctx -> gen [label="ground truth"];
  ml -> or [label="demand + cube"];
  or -> gen [label="decisions"];
}""", use_container_width=True)
    st.markdown("""
- **ML** reads the context for feature definitions (what a Lane is, what a Product promises) so forecasts and cube inference speak the planner's language.
- **OR** reads it as constraints — the optimizer cannot propose what the ontology forbids (no wild reroutes, no one-way turns).
- **GenAI** reads it as ground truth — the copilot answers only from this context, citing lanes, dollars, and rules. If it can't be checked against the ontology, the model says so instead of guessing.""")
    st.subheader("Why it matters")
    p1, p2 = st.columns(2)
    with p1:
        st.markdown("""
**For planners**
- Tribal knowledge becomes explicit: the same rules apply on every shift, at every service center.
- The tower's recommendations arrive pre-checked against the rules — no mental math to verify a cancel won't strand the return leg.
- When a rule changes (new service window, new alternate), you edit one file, not retrain anyone's instincts.""")
    with p2:
        st.markdown("""
**For executives**
- **Auditability:** every dollar the copilot quotes traces to a CSV row and an ontology rule — nothing is a black box.
- **Governance:** the LLM is fenced by design. It cannot invent a lane, a cost, or a policy because the context it sees is closed.
- **Leverage:** the context layer is the durable asset. Models get swapped; the ontology compounds.""")

# ------------------------------ Methodology ------------------------------
with tabs[10]:
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
same either way. Drivers leave on **scheduled bid departures** (outbound: 17:00 and the 21:00 cut;
AM: 09:00 and the 12:00 cut), and each bid that carries freight needs its own drivers:
`drivers(bid) = ceil(pups_in_bid / 2)`. A direction staffs the sum of its bids; the lane staffs the
max of its directions, because drivers are domiciled round trips.
So the optimizer minimizes **driver turns**, not trailers — and the scarcest turn is often the one
with a single pup in it. Cube utilization is the dominant lever because filling the second pup on a
running turn is nearly free, while dispatching another driver is the most expensive thing in the network.
Imbalance shows up as **empty pup slots** (not empty miles): the driver comes home regardless.""")
    st.subheader("Operating cycles and cut-time optimization")
    st.markdown("""
The night runs in three cycles: **outbound 12:00–21:00** (spokes dispatch to hubs), **hub sort 21:00–05:00**
(breakbulks cross-dock, no scheduled linehaul), **AM 05:00–12:00** (hubs dispatch to spokes). When freight
is thin across a cycle's two bids, one departure can do the work of two: merge the early bid into the
**cut** and save a driver shift. The optimizer tests every directed lane for this and recommends
**SHIFT CUT** only if the lane's round-trip staffing actually declines **and** Priority freight keeps its
service slack (otherwise flagged REVIEW, tradeoff priced, planner decides). The same lever runs
structurally (monthly design, Load plan tab) and day-specifically (today's volume, what-if simulator).""")
    st.subheader("The math model")
    st.markdown("""
**Decide:** path per OD-product flow (standard / pre-approved alternate) · bid staffing
(drivers per scheduled departure) · driver turns per lane (integer) · pup assignments
**Minimize:** `sum(turns x turn_cost) + sum(handles x dock_cost)`
**Subject to:** pup cube (1750 cu ft) + weight caps · product service windows (P: ≤2 legs/600 mi; E: ≤2 legs) ·
domiciled round trips — `turns(direction) = sum over bids of ceil(pups_bid/2)`,
`turns(lane) = max(turns_AB, turns_BA)`, equipment balances because drivers come home ·
cut-time shifts never sacrifice product/service feasibility ·
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
    st.subheader("Relay network — freight path vs driver path")
    st.markdown("""
We run a **relay network**: two networks overlaid on the same lanes.

- **Freight network** — shipments, dock handles, breakbulk sorts. Decides cost and service.
  A lane marked *direct* means no freight handling between origin and destination.
- **Driver network** — relay legs, domiciled drivers, hours-of-service. Decides who actually drives.
  On lanes over ~250 miles the trailer swaps drivers at a midpoint relay point — the freight never
  touches the dock — because a 350-mile lane is ~6.5h one way and no same-day round trip fits inside
  11 driving hours. Each driver does a short out-and-back and sleeps at home.

So a shipment can flow *through another center* even on a "direct" freight path when the driver
needs to get home within hours. That is a driver-path decision, not a freight deviation, and it
costs no extra handles. One lane-turn decomposes into one relay-leg turn per leg, each domiciled
at its home end — a cancel on a relayed lane frees one driver at *each* domicile.

**Costing note:** the prototype prices a lane at its blended $/mi (turn = 2 × miles × $/mi), which
is exact when domicile rates match. Production prices each relay leg at its own domicile's $/mi —
domicile pay and demographics differ, and that's a real (if second-order) cost lever.""")
    st.subheader("Conversational copilot (Ask the network)")
    st.markdown("""
The **Ask the network** tab is a grounded GenAI layer: your LLM (Anthropic Claude natively,
or OpenAI / Azure / any OpenAI-compatible endpoint — bring your own key) answers planner questions
using only this scenario's data: KPIs, deviations,
tower events and their network checks, lane scoreboard, cost-to-serve, and the business rules above.
Architecture: **context engineering** (ontology + data as the prompt's ground truth) → **ML** (forecasts,
cube inference) → **OR** (the plan and tower engine) → **GenAI** (explains and converses). The key lives in
the browser session / Streamlit secrets / env var — never in the repo. See the **Ontology & context** tab
for the full story on the context layer.""")
    st.subheader("Cube inference")
    st.markdown("""
Shippers don't provide cube. The planner infers cube at pickup from the shipper's historical
density profile (`shippers.csv`: lbs per cubic foot by commodity). As freight hits the dock it gets
dimmed — true cube — but that's too late to set up doors and trailers. The sample data carries both
so you can see the planning gap.""")
    st.subheader("Ontology / context engineering")
    st.markdown("""
`data/ontology.yaml` is the machine-readable context layer: entities (Terminal, Lane, Shipment, Turn,
OperatingCycle, Bid, CutTime, ServiceSlack, BidConsolidationOpportunity, Deviation, CostToServe…),
relationships, hard constraints (including: a cut-time shift may never sacrifice service feasibility),
planner business rules (including the cut-shift rule and bid consolidation), metric definitions
(good vs bad mile, leg efficiency), the GenAI roles (plan explainer, deviation justifier, cost-to-serve
narrator, cut-time advisor, exception copilot, C-suite briefer — all grounded on optimizer outputs), and the
implementation stack (Python, MIP, hierarchical lane forecast, density profiles refreshed from dimming,
ML optimization proxy, LLM explainer).""")

# ------------------------------ Ask the network ------------------------------
with tabs[11]:
    st.subheader("Ask the network — conversational copilot")
    st.caption("Grounded in this scenario's data: KPIs, deviations, tower events, lane scoreboard, "
               "cost-to-serve. The model answers only from this context.")

    st.info("**What is this page?** The copilot below needs a large language model to talk to. "
            "This panel tells the app *which* model to use and holds *your* API key. Nothing is sent "
            "anywhere except the provider you choose, and the model only ever sees this scenario's "
            "data (the summary built below) — never your key, never anything else. "
            "Pick it up and use it: paste a key once per session, or save it in Streamlit secrets "
            "so it's always there.", icon="🔌")

    with st.expander("Connection (your key, your endpoint)", expanded=False):
        provider = st.selectbox("Provider",
                                ["Anthropic", "OpenAI-compatible"],
                                help="Anthropic = the native Anthropic API (claude-...). "
                                     "OpenAI-compatible = OpenAI, Azure OpenAI, or any compatible endpoint.")
        st.session_state["llm_provider"] = provider
        key_in = st.text_input("API key", type="password",
                               help="Stored only in this browser session, never in the repo. "
                                    "You can also set it via Streamlit secrets (ANTHROPIC_API_KEY or "
                                    "OPENAI_API_KEY) or the matching env var.")
        if key_in:
            st.session_state["llm_key"] = key_in
        if provider == "OpenAI-compatible":
            base_url = st.text_input("Base URL (OpenAI-compatible)",
                                     value=st.session_state.get("llm_base", "https://api.openai.com/v1"))
            st.session_state["llm_base"] = base_url
            model = st.text_input("Model", value=st.session_state.get("llm_model", "gpt-4o-mini"))
            st.session_state["llm_model"] = model
            st.caption("Works with OpenAI, Azure OpenAI, or any OpenAI-compatible endpoint.")
        else:
            model = st.text_input("Model", value=st.session_state.get("llm_model_a",
                                                                     "claude-sonnet-4-20250514"),
                                 help="Any Claude model your key can access.")
            st.session_state["llm_model_a"] = model
            st.caption("Uses the native Anthropic API. Set ANTHROPIC_API_KEY in Streamlit secrets "
                       "(⋮ → Settings → Secrets) to keep it across sessions.")

    provider = st.session_state.get("llm_provider", "Anthropic")
    if provider == "Anthropic":
        api_key = (st.session_state.get("llm_key")
                   or st.secrets.get("ANTHROPIC_API_KEY")
                   or os.environ.get("ANTHROPIC_API_KEY"))
    else:
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
        opps = d["bid_opportunities"]
        if not opps.empty:
            L.append("Cut-time opportunities (merge an early bid into the cut departure): " +
                     "; ".join(f"{r['opp_id']} {r['direction']}: {r['detail']} saves "
                               f"{int(r['turns_saved_lane'])} turn(s) ${r['saving_usd']:,.0f}, "
                               f"service check {r['service_check']}"
                               for _, r in opps.iterrows()))
        L.append("Operating cycles: outbound 12:00-21:00 (bids 17:00, 21:00 cut), hub sort 21:00-05:00, "
                 "AM 05:00-12:00 (bids 09:00, 12:00 cut). turns(direction) = sum over bids of "
                 "ceil(pups_in_bid/2); turns(lane) = max over directions (domiciled round trips).")
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
                   "(it stays in this session only), or set `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` "
                   "in Streamlit secrets / env.")
            with st.chat_message("assistant"):
                st.warning(msg)
            st.session_state["chat"].append({"role": "assistant", "content": msg})
        else:
            with st.chat_message("assistant"):
                with st.spinner("Thinking…"):
                    try:
                        hist = [{"role": m["role"], "content": m["content"]}
                                for m in st.session_state["chat"][-10:]]
                        if provider == "Anthropic":
                            from anthropic import Anthropic
                            client = Anthropic(api_key=api_key)
                            resp = client.messages.create(
                                model=st.session_state.get("llm_model_a",
                                                           "claude-sonnet-4-20250514"),
                                max_tokens=800, temperature=0.2,
                                system=SYSTEM, messages=hist)
                            ans = resp.content[0].text
                        else:
                            from openai import OpenAI
                            client = OpenAI(api_key=api_key,
                                            base_url=st.session_state.get("llm_base",
                                                                         "https://api.openai.com/v1"))
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
with tabs[12]:
    st.subheader("Download the sample data")
    for name in ["terminals", "lanes", "design_routes", "shippers", "shipments",
                 "forecast_lane", "linehaul_actuals", "deviations",
                 "cost_to_serve", "lane_scoreboard", "tower_events", "tower_actions",
                 "bids", "bid_opportunities"]:
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
