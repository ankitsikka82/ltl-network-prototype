"""
Freight AI prototype - sample data generator + linehaul optimizer + cost-to-serve.
5-terminal cluster, one operating day. Deterministic (seeded).
Scenarios: base / light / heavy volume.

All figures ILLUSTRATIVE for prototype purposes, not carrier operating data.
"""
import csv, json, math, os, random
from collections import defaultdict

ROOT = os.path.expanduser("~/workspace/freight-prototype/data")

# ----------------------------- configuration -----------------------------
DATE = "2026-09-28"  # Monday operating day

TERMINALS = [
    ("SGF", "Springfield MO", "breakbulk"),
    ("STL", "St. Louis MO", "eol"),
    ("MKC", "Kansas City", "eol"),
    ("MEM", "Memphis TN", "eol"),
    ("TUL", "Tulsa OK", "eol"),
]
HUB = "SGF"

# scheduled linehaul lanes: (a, b, miles, cost_per_mile_usd)
# cost/mile varies by domicile driver pay + local demographics (illustrative)
LANES = [
    ("SGF", "STL", 215, 1.90),
    ("SGF", "MKC", 180, 1.85),
    ("SGF", "MEM", 285, 1.95),
    ("SGF", "TUL", 180, 1.80),
    ("STL", "MEM", 285, 2.10),
    ("MKC", "STL", 250, 2.00),
]
# road miles for non-scheduled pairs (used only to price a deviation direct)
DIRECT_MILES = {
    ("MKC", "MEM"): 350, ("MKC", "TUL"): 250,
    ("TUL", "STL"): 350, ("TUL", "MEM"): 380,
}
DIRECT_CPM = 1.95

# trailer (28' pup, illustrative)
CUBE_CAP = 1750.0   # usable cubic feet
W_CAP = 20000.0     # lbs

# doubles: ONE driver pulls TWO pups out and brings TWO pups back, full or empty.
# The driver turn is the cost unit: a turn costs the same whether the pups are
# full or empty. Cube utilization is therefore the dominant cost lever.
PUPS_PER_TURN = 2
TURN_CUBE_CAP = CUBE_CAP * PUPS_PER_TURN
TURN_W_CAP = W_CAP * PUPS_PER_TURN

# unit costs (illustrative)
DOCK_HANDLE_COST = 14.0   # $ per dock touch per shipment
PUD_END_COST = 40.0       # $ per pickup end / delivery end
HANDLES_DIRECT = 2        # origin load + dest unload
HANDLES_HUB = 4           # origin load + hub unload + hub reload + dest unload

PRODUCTS = ["P", "E"]  # P = Priority (fast), E = Economy (~1 day slower)

# shippers: id, name, home terminal, commodity, density lb/cuft, avg wt, wt sd
SHIPPERS = [
    ("S01", "AutoParts Co",      "SGF", "auto parts",        22,  900, 350),
    ("S02", "Ozark Furniture",   "SGF", "furniture",          7,  700, 300),
    ("S03", "Paper Mill Supply", "STL", "paper",              18, 1200, 450),
    ("S04", "Gateway Electronics","STL","electronics",        10,  500, 220),
    ("S05", "KC Food Dist",      "MKC", "canned food",        30, 1500, 500),
    ("S06", "Midwest Apparel",   "MKC", "apparel",             8,  600, 260),
    ("S07", "Memphis Machinery", "MEM", "machinery",          25, 1800, 600),
    ("S08", "Delta Plastics",    "MEM", "plastics",            9,  800, 320),
    ("S09", "Tulsa Beverage",    "TUL", "beverages",          28, 1600, 550),
    ("S10", "Plains Pharma",     "TUL", "pharma",              12,  400, 180),
    ("S11", "Ozark Building",    "SGF", "building materials", 20, 1400, 500),
    ("S12", "Crossroads Retail", "MKC", "retail mixed",       11,  750, 300),
]
SHIPPER_WT = [14, 8, 10, 9, 11, 8, 7, 7, 9, 6, 6, 5]  # relative shipment volume

DEST_WT = {  # destination preference given origin
    "SGF": {"STL": 22, "MKC": 20, "MEM": 18, "TUL": 14},
    "STL": {"SGF": 20, "MKC": 18, "MEM": 22, "TUL": 12},
    "MKC": {"SGF": 20, "STL": 20, "MEM": 14, "TUL": 16},
    "MEM": {"SGF": 18, "STL": 22, "MKC": 12, "TUL": 14},
    "TUL": {"SGF": 16, "STL": 12, "MKC": 16, "MEM": 18},
}

SCENARIOS = {"base": 1.00, "light": 0.65, "heavy": 1.30}
BASE_SHIPMENTS = 1050


def wpick(rng, weights):
    items = list(weights.keys()) if isinstance(weights, dict) else list(range(len(weights)))
    w = list(weights.values()) if isinstance(weights, dict) else list(weights)
    return rng.choices(items, weights=w, k=1)[0]


def lane_key(a, b):
    if (a, b) in LANE_MAP:
        return (a, b)
    if (b, a) in LANE_MAP:
        return (b, a)
    return tuple(sorted((a, b)))  # non-scheduled deviation lane


LANE_MAP = {}
for a, b, mi, cpm in LANES:
    LANE_MAP[(a, b)] = {"miles": mi, "cpm": cpm}
    LANE_MAP[(b, a)] = {"miles": mi, "cpm": cpm}
    LANE_MAP[tuple(sorted((a, b)))] = {"miles": mi, "cpm": cpm}  # normalized key
SCHEDULED = set(tuple(sorted((a, b))) for a, b, _, _ in LANES)


def direct_miles(a, b):
    if (a, b) in LANE_MAP:
        return LANE_MAP[(a, b)]["miles"]
    return DIRECT_MILES.get((a, b)) or DIRECT_MILES.get((b, a))


def standard_path(o, d):
    """Structured network: every OD x product has one standard path we try to follow."""
    if tuple(sorted((o, d))) in SCHEDULED:
        return [lane_key(o, d)]
    return [lane_key(o, HUB), lane_key(HUB, d)]


def path_miles(path):
    return sum(direct_miles(*leg) for leg in path)


def gen_shipments(rng, n):
    ships = []
    for i in range(n):
        si = wpick(rng, SHIPPER_WT)
        sid, name, home, comm, dens, avg_w, sd_w = SHIPPERS[si]
        o = home
        d = wpick(rng, DEST_WT[o])
        prod = "P" if rng.random() < 0.60 else "E"
        weight = max(80.0, rng.gauss(avg_w, sd_w))
        pieces = max(1, int(weight / rng.uniform(120, 260)))
        true_cube = weight / dens
        inferred_cube = true_cube * (1 + rng.gauss(0, 0.10))  # planner's estimate at pickup
        dimmed_cube = true_cube                              # dock dimensioner, known too late
        mi = direct_miles(o, d)
        rate_cwt = 16 + 0.025 * mi + (5 if prod == "P" else 0) + rng.gauss(0, 2)
        revenue = weight / 100.0 * max(8.0, rate_cwt)
        ships.append({
            "shipment_id": f"SH{i+1:05d}", "date": DATE, "customer_id": sid,
            "customer": name, "origin": o, "dest": d, "product": prod,
            "weight_lbs": round(weight, 1), "pieces": pieces,
            "density_lb_cuft": dens,
            "inferred_cube_cuft": round(max(5.0, inferred_cube), 1),
            "dimmed_cube_cuft": round(true_cube, 1),
            "revenue_usd": round(revenue, 2),
        })
    return ships

# ----------------------------- optimizer -----------------------------
def render_path(o, d, path):
    cur = o
    nodes = [o]
    for lg in path:
        srt = tuple(sorted(lg))
        nxt = srt[1] if cur == srt[0] else srt[0]
        nodes.append(nxt)
        cur = nxt
    return ">".join(nodes)
# Planner works with INFERRED cube (known at pickup time, before dock dimming).
# Objective: minimize total cost = linehaul + dock handles.
# Deviation from standard path allowed when it lowers total cost (density vs handles).

def service_ok(path, product):
    mi = path_miles(path)
    if product == "P":
        return len(path) <= 2 and mi <= 600
    return len(path) <= 2 and mi <= 1000


def optimize(ships):
    # aggregate to flows by (o, d, product) - this is how load planning sees the day
    flows = defaultdict(lambda: {"cube": 0.0, "weight": 0.0, "n": 0, "rev": 0.0,
                                 "dimmed": 0.0})
    for s in ships:
        f = flows[(s["origin"], s["dest"], s["product"])]
        f["cube"] += s["inferred_cube_cuft"]
        f["weight"] += s["weight_lbs"]
        f["n"] += 1
        f["rev"] += s["revenue_usd"]
        f["dimmed"] += s["dimmed_cube_cuft"]

    # start on standard paths
    path_of = {k: standard_path(k[0], k[1]) for k in flows}
    deviations = []

    def lane_volumes():
        lv = defaultdict(lambda: {"cube": 0.0, "weight": 0.0})
        for (o, d, p), f in flows.items():
            cur = o
            for leg in path_of[(o, d, p)]:
                srt = tuple(sorted(leg))
                nxt = srt[1] if cur == srt[0] else srt[0]
                dirc = "AB" if cur == srt[0] else "BA"
                lv[(srt, dirc)]["cube"] += f["cube"]
                lv[(srt, dirc)]["weight"] += f["weight"]
                cur = nxt
        return lv

    def leg_endpoints_for_flow(o, d, leg, path):
        # ordered (from, to) endpoints of leg as traversed by flow o->d
        cur = o
        for lg in path:
            srt = tuple(sorted(lg))
            nxt = srt[1] if cur == srt[0] else srt[0]
            if tuple(sorted(leg)) == srt:
                return (cur, nxt)
            cur = nxt
        return (o, d)

    def avg_cost_per_cube(lv):
        # avg linehaul $ per cube on each directed lane leg, from current assignment
        cpp = {}
        for (lane, dirc), v in lv.items():
            a, b = lane
            mi = direct_miles(a, b)
            cpm = LANE_MAP[(a, b)]["cpm"] if (a, b) in LANE_MAP else DIRECT_CPM
            one_way = mi * cpm
            trailers = max(1, math.ceil(v["cube"] / CUBE_CAP))
            cpp[(lane, dirc)] = (trailers * one_way) / max(1.0, v["cube"])
        return cpp

    def hub_path(o, d):
        return [lane_key(o, HUB), lane_key(HUB, d)]

    def direct_path(o, d):
        return [lane_key(o, d)]

    # greedy deviation search: consolidate light directs, direct heavy hub flows
    for _round in range(12):
        lv = lane_volumes()
        cpp = avg_cost_per_cube(lv)
        moved = False
        for key in sorted(flows):
            o, d, p = key
            f = flows[key]
            Q, n = f["cube"], f["n"]
            cur = path_of[key]
            cur_is_direct = len(cur) == 1
            # candidate A: heavy via-hub flow -> direct (cut handles, maybe worse density)
            if not cur_is_direct and Q >= 0.60 * CUBE_CAP:
                cand = direct_path(o, d)
                if service_ok(cand, p):
                    dm = direct_miles(o, d)
                    cpm_d = LANE_MAP[tuple(sorted((o, d)))]["cpm"] \
                        if tuple(sorted((o, d))) in LANE_MAP else DIRECT_CPM
                    n_trail = math.ceil(Q / CUBE_CAP)
                    cost_direct = n_trail * dm * cpm_d + HANDLES_DIRECT * DOCK_HANDLE_COST * n
                    cost_hub = sum(
                        Q * cpp.get((tuple(sorted(leg)),
                                     "AB" if leg_endpoints_for_flow(o, d, leg, cur)[0] == tuple(sorted(leg))[0] else "BA"), 0)
                        for leg in cur) + HANDLES_HUB * DOCK_HANDLE_COST * n
                    if cost_direct < cost_hub - 50:
                        deviations.append({"od": f"{o}>{d}", "product": p,
                                           "standard": render_path(o, d, standard_path(o, d)),
                                           "chosen": f"{o}>{d} direct",
                                           "reason": f"direct saves ${cost_hub - cost_direct:,.0f} "
                                                     f"({HANDLES_HUB - HANDLES_DIRECT} fewer handles x {n} shipments)",
                                           "saving": round(cost_hub - cost_direct, 2)})
                        path_of[key] = cand
                        moved = True
            # candidate B: light direct flow -> consolidate via hub (gain density)
            if cur_is_direct and Q < 0.45 * CUBE_CAP and o != HUB and d != HUB:
                cand = hub_path(o, d)
                if service_ok(cand, p):
                    dm = direct_miles(o, d)
                    n_trail = math.ceil(Q / CUBE_CAP)
                    cost_direct = n_trail * dm * LANE_MAP[cur[0]]["cpm"] + HANDLES_DIRECT * DOCK_HANDLE_COST * n
                    cost_hub = sum(
                        Q * cpp.get((tuple(sorted(leg)),
                                     "AB" if leg_endpoints_for_flow(o, d, leg, cand)[0] == tuple(sorted(leg))[0] else "BA"), 0)
                        for leg in cand) + HANDLES_HUB * DOCK_HANDLE_COST * n
                    if cost_hub < cost_direct - 50:
                        deviations.append({"od": f"{o}>{d}", "product": p,
                                           "standard": f"{o}>{d} direct",
                                           "chosen": f"{o}>{HUB}>{d} via hub",
                                           "reason": f"consolidation saves ${cost_direct - cost_hub:,.0f} "
                                                     f"(fills hub trailers, avoids {n_trail} low-cube direct)",
                                           "saving": round(cost_direct - cost_hub, 2)})
                        path_of[key] = cand
                        moved = True
        if not moved:
            break

    # domiciled turns: every dispatched trailer runs out-and-back, driver home nightly.
    # turns on a lane = max(trailers needed each way); light direction may run empties home.
    lane_plan = {}
    lv = lane_volumes()
    lanes_seen = set(tuple(sorted(leg)) for p in path_of.values() for leg in p)
    for lane in lanes_seen:
        a, b = lane
        vo = lv.get((lane, "AB"), {"cube": 0.0, "weight": 0.0})
        vi = lv.get((lane, "BA"), {"cube": 0.0, "weight": 0.0})
        t_out = max(math.ceil(vo["cube"] / CUBE_CAP), math.ceil(vo["weight"] / W_CAP)) if vo["cube"] > 0 else 0
        t_in = max(math.ceil(vi["cube"] / CUBE_CAP), math.ceil(vi["weight"] / W_CAP)) if vi["cube"] > 0 else 0
        # driver turns with doubles: one driver takes two pups out, brings two back.
        # turn cost is fixed whether pups are full or empty -> cube first.
        turns = math.ceil(max(t_out, t_in) / PUPS_PER_TURN)
        mi = direct_miles(a, b)
        cpm = LANE_MAP[(a, b)]["cpm"] if (a, b) in LANE_MAP else DIRECT_CPM
        turn_cost = 2 * mi * cpm  # driver + tractor round trip; same full or empty
        lane_cost = turns * turn_cost
        tot_cube = vo["cube"] + vi["cube"]
        # allocate turn cost to directions by cube share; empty returns charge to the loaded side
        cost_ab = lane_cost * (vo["cube"] / tot_cube) if tot_cube > 0 else 0
        cost_ba = lane_cost * (vi["cube"] / tot_cube) if tot_cube > 0 else 0
        lane_plan[lane] = {"AB": vo, "BA": vi, "pups_out": t_out, "pups_in": t_in,
                           "turns": turns, "miles": mi, "cpm": cpm, "turn_cost": turn_cost,
                           "lane_cost": lane_cost, "cost_AB": cost_ab, "cost_BA": cost_ba}

    # build discrete loads (first-fit decreasing) per directed lane
    loads = []
    load_seq = 0
    for lane, lp in sorted(lane_plan.items()):
        for dirc, n_pups in (("AB", lp["pups_out"]), ("BA", lp["pups_in"])):
            segs = []
            for key, f in flows.items():
                o, d, p = key
                for leg in path_of[key]:
                    if tuple(sorted(leg)) == lane:
                        frm, to = leg_endpoints_for_flow(o, d, leg, path_of[key])
                        srt = tuple(sorted(leg))
                        if (frm == srt[0] and dirc == "AB") or (frm == srt[1] and dirc == "BA"):
                            segs.append({"odp": f"{o}>{d}/{p}", "cube": f["cube"],
                                         "weight": f["weight"], "n": f["n"]})
                            break
            segs.sort(key=lambda s: -s["cube"])
            trailers = [{"cube": 0.0, "weight": 0.0, "segs": []} for _ in range(n_pups)]
            for s in segs:
                placed = False
                for t in trailers:
                    if t["cube"] + s["cube"] <= CUBE_CAP and t["weight"] + s["weight"] <= W_CAP:
                        t["cube"] += s["cube"]; t["weight"] += s["weight"]
                        t["segs"].append(s["odp"]); placed = True; break
                if not placed:
                    # split across trailers (prototype fidelity: fractional trailer assignment)
                    remaining = s["cube"]
                    for t in trailers:
                        room = CUBE_CAP - t["cube"]
                        if room > 1 and remaining > 0:
                            take = min(room, remaining)
                            t["cube"] += take; remaining -= take
                            if s["odp"] not in t["segs"]:
                                t["segs"].append(s["odp"] + "*")
                    # any leftover starts an overflow trailer
                    while remaining > 1:
                        take = min(CUBE_CAP, remaining)
                        trailers.append({"cube": take, "weight": s["weight"] * take / s["cube"],
                                         "segs": [s["odp"] + "*"]})
                        remaining -= take
            for ti, t in enumerate(trailers, 1):
                load_seq += 1
                util = t["cube"] / CUBE_CAP
                loads.append({"load_id": f"L{load_seq:04d}", "lane": f"{lane[0]}-{lane[1]}",
                              "direction": f"{lane[0]}>{lane[1]}" if dirc == "AB" else f"{lane[1]}>{lane[0]}",
                              "turn_no": (ti - 1) // PUPS_PER_TURN + 1,
                              "trailer_no": ti, "cube_cuft": round(t["cube"], 1),
                              "weight_lbs": round(t["weight"], 1),
                              "cube_util_pct": round(100 * util, 1),
                              "empty": t["cube"] < 1,
                              "flows": ";".join(t["segs"])})
        # empty pups ride on running turns: the driver goes home with two pups
        # whether they are full or empty. Marginal cost ~ $0; the waste is density.
        for dirc, loaded in (("AB", lp["pups_out"]), ("BA", lp["pups_in"])):
            for _ in range(lp["turns"] * PUPS_PER_TURN - loaded):
                load_seq += 1
                loads.append({"load_id": f"L{load_seq:04d}", "lane": f"{lane[0]}-{lane[1]}",
                              "direction": f"{lane[0]}>{lane[1]}" if dirc == "AB" else f"{lane[1]}>{lane[0]}",
                              "turn_no": 0,
                              "trailer_no": 0, "cube_cuft": 0, "weight_lbs": 0,
                              "cube_util_pct": 0.0, "empty": True,
                              "flows": "EMPTY pup on running turn"})

    return flows, path_of, deviations, lane_plan, loads

# ----------------------------- cost to serve -----------------------------
# cost_to_serve(shipment) = P&D + dock handles + linehaul by leg.
# Linehaul leg cost varies by lane (domiciled driver pay, demographics, miles).
# Turn cost is allocated to directions by cube share, so empty domicile returns
# (bad miles) charge back to the direction that created the imbalance.

def cost_to_serve(ships, flows, path_of, lane_plan):
    # per directed leg: $ per cube for freight moving that direction
    cpp = {}
    for lane, lp in lane_plan.items():
        for dirc, key in (("AB", "cost_AB"), ("BA", "cost_BA")):
            v = lp[dirc]
            cpp[(lane, dirc)] = (lp[key] / v["cube"]) if v["cube"] > 0 else 0.0
    rows = []
    for s in ships:
        o, d, p = s["origin"], s["dest"], s["product"]
        path = path_of[(o, d, p)]
        handles = HANDLES_DIRECT if len(path) == 1 else HANDLES_HUB
        dock = handles * DOCK_HANDLE_COST
        pud = 2 * PUD_END_COST
        lh = 0.0
        leg_costs = []
        cur = o
        for leg in path:
            srt = tuple(sorted(leg))
            nxt = srt[1] if cur == srt[0] else srt[0]
            dirc = "AB" if cur == srt[0] else "BA"
            c = s["inferred_cube_cuft"] * cpp.get((srt, dirc), 0)
            leg_costs.append(f"{cur}>{nxt}:${c:.2f}")
            lh += c
            cur = nxt
        cts = pud + dock + lh
        margin = s["revenue_usd"] - cts
        rows.append({
            "shipment_id": s["shipment_id"], "date": s["date"], "customer": s["customer"],
            "origin": o, "dest": d, "product": p,
            "weight_lbs": s["weight_lbs"], "inferred_cube_cuft": s["inferred_cube_cuft"],
            "path": ">".join([o] + [nxt for _, nxt in
                             [leg_endpoints_for_flow(o, d, lg, path) for lg in path]]),
            "handles": handles,
            "revenue_usd": s["revenue_usd"],
            "pud_cost_usd": round(pud, 2), "dock_cost_usd": round(dock, 2),
            "linehaul_cost_usd": round(lh, 2),
            "cost_to_serve_usd": round(cts, 2),
            "margin_usd": round(margin, 2),
            "margin_pct": round(100 * margin / s["revenue_usd"], 1) if s["revenue_usd"] else 0,
            "leg_cost_detail": ";".join(leg_costs),
        })
    return rows


def leg_endpoints_for_flow(o, d, leg, path):
    cur = o
    for lg in path:
        srt = tuple(sorted(lg))
        nxt = srt[1] if cur == srt[0] else srt[0]
        if tuple(sorted(leg)) == srt:
            return (cur, nxt)
        cur = nxt
    return (o, d)


def compute_kpis(ships, cts_rows, lane_plan, loads, deviations):
    tot_rev = sum(s["revenue_usd"] for s in ships)
    tot_cts = sum(r["cost_to_serve_usd"] for r in cts_rows)
    tot_lh = sum(r["linehaul_cost_usd"] for r in cts_rows)
    tot_dock = sum(r["dock_cost_usd"] for r in cts_rows)
    tot_pud = sum(r["pud_cost_usd"] for r in cts_rows)
    loaded = [l for l in loads if not l["empty"]]
    avg_util = (sum(l["cube_cuft"] for l in loaded) /
                max(1, len(loaded) * CUBE_CAP)) * 100
    empty_pups = sum(1 for l in loads if l["empty"])
    # with domiciled doubles the waste is empty PUP slots on running turns,
    # not empty miles: the driver comes home with two pups, full or empty.
    empty_pup_pct = 100 * empty_pups / max(1, len(loads))
    turns_dispatched = sum(lp["turns"] for lp in lane_plan.values())
    handles = sum(r["handles"] for r in cts_rows)
    # forecast accuracy (MAPE on cube) computed by caller; placeholder here
    return {
        "date": DATE, "shipments": len(ships),
        "revenue_usd": round(tot_rev, 2),
        "cost_to_serve_usd": round(tot_cts, 2),
        "margin_usd": round(tot_rev - tot_cts, 2),
        "margin_pct": round(100 * (tot_rev - tot_cts) / tot_rev, 1) if tot_rev else 0,
        "linehaul_cost_usd": round(tot_lh, 2),
        "dock_cost_usd": round(tot_dock, 2),
        "pud_cost_usd": round(tot_pud, 2),
        "avg_cube_util_pct": round(avg_util, 1),
        "turns_dispatched": turns_dispatched,
        "loads_dispatched": len(loads),
        "empty_pup_pct": round(empty_pup_pct, 1),
        "empty_pups": empty_pups,
        "handles_per_shipment": round(handles / max(1, len(ships)), 2),
        "deviations": len(deviations),
        "deviation_savings_usd": round(sum(d["saving"] for d in deviations), 2),
        "cost_per_shipment_usd": round(tot_cts / max(1, len(ships)), 2),
    }


def write_csv(path, rows, fields=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fields = fields or list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def run_scenario(name, scale, seed):
    rng = random.Random(seed)
    out = os.path.join(ROOT, name)
    ships = gen_shipments(rng, int(BASE_SHIPMENTS * scale))
    flows, path_of, deviations, lane_plan, loads = optimize(ships)
    cts_rows = cost_to_serve(ships, flows, path_of, lane_plan)

    # forecast: lane-level, made yesterday; planner plans doors/trailers on this
    fc_rows = []
    ape = []
    for (o, d, p), f in sorted(flows.items()):
        fc_cube = f["cube"] * (1 + rng.gauss(0, 0.15))
        fc_n = max(1, round(f["n"] * (1 + rng.gauss(0, 0.12))))
        ape.append(abs(fc_cube - f["cube"]) / max(1, f["cube"]))
        fc_rows.append({"date": DATE, "origin": o, "dest": d, "product": p,
                        "forecast_shipments": fc_n,
                        "forecast_cube_cuft": round(max(10, fc_cube), 1),
                        "actual_shipments": f["n"],
                        "actual_cube_cuft": round(f["cube"], 1),
                        "actual_dimmed_cube_cuft": round(f["dimmed"], 1)})

    kpis = compute_kpis(ships, cts_rows, lane_plan, loads, deviations)
    kpis["forecast_mape_pct"] = round(100 * sum(ape) / max(1, len(ape)), 1)
    kpis["scenario"] = name

    write_csv(f"{out}/terminals.csv",
              [{"terminal": t, "city": c, "type": ty} for t, c, ty in TERMINALS])
    write_csv(f"{out}/lanes.csv",
              [{"terminal_a": a, "terminal_b": b, "miles": mi,
                "cost_per_mile_usd": cpm} for a, b, mi, cpm in LANES])
    write_csv(f"{out}/design_routes.csv",
              [{"origin": o, "dest": d, "product": p,
                "standard_path": ">".join([o] + [nxt for _, nxt in
                    [leg_endpoints_for_flow(o, d, lg, standard_path(o, d)) for lg in standard_path(o, d)]]),
                "path_type": "direct" if len(standard_path(o, d)) == 1 else "via_hub",
                "path_miles": path_miles(standard_path(o, d))}
               for o in [t[0] for t in TERMINALS] for d in [t[0] for t in TERMINALS]
               if o != d for p in PRODUCTS])
    write_csv(f"{out}/shippers.csv",
              [{"customer_id": s[0], "customer": s[1], "home_terminal": s[2],
                "commodity": s[3], "density_lb_per_cuft": s[4]} for s in SHIPPERS])
    write_csv(f"{out}/shipments.csv", ships)
    write_csv(f"{out}/forecast_lane.csv", fc_rows)
    write_csv(f"{out}/linehaul_actuals.csv", loads)
    write_csv(f"{out}/deviations.csv", deviations,
              fields=["od", "product", "standard", "chosen", "reason", "saving"] if deviations
              else ["od", "product", "standard", "chosen", "reason", "saving"])
    write_csv(f"{out}/cost_to_serve.csv", cts_rows)
    # lane scoreboard: leg efficiency, good vs bad miles
    board = []
    for lane, lp in sorted(lane_plan.items()):
        for dirc, lab in (("AB", f"{lane[0]}>{lane[1]}"), ("BA", f"{lane[1]}>{lane[0]}")):
            v = lp[dirc]
            loaded_units = v["cube"] / CUBE_CAP
            trailers_used = lp["turns"]
            util = v["cube"] / max(1, trailers_used * TURN_CUBE_CAP) * 100
            cost = lp["cost_AB"] if dirc == "AB" else lp["cost_BA"]
            board.append({
                "lane": f"{lane[0]}-{lane[1]}", "direction": lab,
                "miles": lp["miles"], "cost_per_mile_usd": lp["cpm"],
                "turns": trailers_used,
                "cube_cuft": round(v["cube"], 1),
                "cube_util_pct": round(util, 1),
                "leg_cost_usd": round(cost, 2),
                "cost_per_cube_mile_usd": round(cost / max(1, v["cube"] * lp["miles"]), 4),
                "verdict": "good miles" if util >= 70 else ("watch" if util >= 40 else "bad miles"),
            })
    write_csv(f"{out}/lane_scoreboard.csv", board)
    # control tower: day-of volume vs plan
    events, actions = build_tower(rng, fc_rows, flows, path_of, lane_plan)
    ev_fields = ["event_id", "checkpoint", "lane", "direction", "planned_turns",
                 "projected_turns", "gap_turns", "trigger"]
    ac_fields = ["action_id", "event_id", "action_type", "detail",
                 "cost_impact_usd", "service_impact", "network_check", "copilot_message"]
    write_csv(f"{out}/tower_events.csv", events, fields=ev_fields)
    write_csv(f"{out}/tower_actions.csv", actions, fields=ac_fields)
    kpis["tower_events"] = len(events)
    kpis["tower_actions"] = len(actions)
    kpis["tower_net_usd"] = round(sum(a["cost_impact_usd"] for a in actions), 2)
    with open(f"{out}/kpis.json", "w") as f:
        json.dump(kpis, f, indent=2)
    print(f"[{name}] shipments={len(ships)} loads={len(loads)} "
          f"margin={kpis['margin_pct']}% util={kpis['avg_cube_util_pct']}% "
          f"empty_pup={kpis['empty_pup_pct']}% dev={len(deviations)} "
          f"dev_save=${kpis['deviation_savings_usd']:,.0f} "
          f"tower_events={len(events)} tower_net=${kpis['tower_net_usd']:,.0f}")
    return kpis


# ----------------------------- control tower -----------------------------
# Central watches day-of volume hit the dock at checkpoints and recommends
# adjustments to service centers. Every recommendation is evaluated
# NETWORK-WIDE, not locally: a turn is a domiciled round trip, so cancelling a
# turn on A>B also removes return capacity B>A; rerouting shifts load onto other
# lanes, which must have spare pup slots. A locally-cheap move that breaks the
# network is blocked. Prototype: transparent rules; production: network MIP.

CHECKPOINTS = [("10:00", 0.35), ("14:00", 0.65), ("18:00", 0.90)]


def alternate_for(o, d, p):
    """Bounded pre-approved alternate for an OD x product (None if none exists)."""
    std = standard_path(o, d)
    if len(std) == 1 and o != HUB and d != HUB:
        alt = [lane_key(o, HUB), lane_key(HUB, d)]
        return alt if service_ok(alt, p) else None
    if len(std) == 2:
        alt = [lane_key(o, d)]
        return alt if service_ok(alt, p) else None
    return None


def _legs_with_dir(o, path):
    cur = o
    out = []
    for leg in path:
        srt = tuple(sorted(leg))
        nxt = srt[1] if cur == srt[0] else srt[0]
        out.append((srt, "AB" if cur == srt[0] else "BA"))
        cur = nxt
    return out


def find_reroute(lane, dirc, overflow_pups, cp, proj, planned_turns, planned_pups,
                 lane_n, flows, path_of):
    """Cheapest network-feasible reroute of overflow pups onto a pre-approved
    alternate path with spare pup slots at this checkpoint. None if infeasible."""
    cands = []
    for (o, d, p), f in flows.items():
        if (lane, dirc) in _legs_with_dir(o, path_of[(o, d, p)]):
            cands.append(((o, d, p), f))
    if not cands:
        return None
    cands.sort(key=lambda x: -x[1]["cube"])
    (o, d, p), f = cands[0]
    alt = alternate_for(o, d, p)
    if not alt:
        return None
    alt_legs = _legs_with_dir(o, alt)
    spare = 0
    for key in alt_legs:
        if key not in planned_turns:
            return None  # alternate lane not in the plan -> cannot absorb
        _, ppk, _ = proj[(cp,) + key]
        spare += max(0, planned_turns[key] * PUPS_PER_TURN - ppk)
    if spare < overflow_pups:
        return None
    spp = lane_n[(lane, dirc)] / max(1, planned_pups[(lane, dirc)])
    # one extra intermediate stop = 2 extra handles per rerouted shipment;
    # linehaul is ~free because it fills spare pup slots on running turns
    cost = overflow_pups * spp * 2 * DOCK_HANDLE_COST
    return {"cost": cost, "via": ">".join([o] + [k[0][1] if k[1] == "AB" else k[0][0]
                                             for k in alt_legs]),
            "spare": spare, "od": f"{o}>{d}/{p}"}


def build_tower(rng, fc_rows, flows, path_of, lane_plan):
    # planned cube / pups / turns per lane-direction from FORECAST (central's plan)
    planned_cube = defaultdict(float)
    lane_n = defaultdict(int)
    for r in fc_rows:
        o, d, p = r["origin"], r["dest"], r["product"]
        for key in _legs_with_dir(o, path_of[(o, d, p)]):
            planned_cube[key] += r["forecast_cube_cuft"]
    for (o, d, p), f in flows.items():
        for key in _legs_with_dir(o, path_of[(o, d, p)]):
            lane_n[key] += f["n"]
    planned_pups = {k: math.ceil(v / CUBE_CAP) for k, v in planned_cube.items()}
    planned_turns = {k: math.ceil(pp / PUPS_PER_TURN) for k, pp in planned_pups.items()}
    # actual (dimmed) cube; central sees it only as volume hits the dock
    actual_cube = defaultdict(float)
    for (o, d, p), f in flows.items():
        for key in _legs_with_dir(o, path_of[(o, d, p)]):
            actual_cube[key] += f["dimmed"]

    # pass 1: run-rate projections per checkpoint (cube, pups, turns)
    proj = {}
    for cp, share in CHECKPOINTS:
        for key, pc in planned_cube.items():
            ac = actual_cube.get(key, 0.0)
            observed = ac * share * (1 + rng.gauss(0, 0.08))
            pcu = observed / share
            pp = math.ceil(pcu / CUBE_CAP)
            proj[(cp,) + key] = (pcu, pp, math.ceil(pp / PUPS_PER_TURN))

    # pass 2: events + network-checked actions
    events, actions = [], []
    eid = aid = 0
    for cp, share in CHECKPOINTS:
        for (lane, dirc) in sorted(planned_cube):
            pcu, pp, pt = proj[(cp, lane, dirc)]
            plan_t = planned_turns[(lane, dirc)]
            gap = pt - plan_t
            if abs(gap) < 1:
                continue
            eid += 1
            a, b = lane
            direction = f"{a}>{b}" if dirc == "AB" else f"{b}>{a}"
            orig = direction.split(">")[0]
            lp = lane_plan.get(lane)
            tc = lp["turn_cost"] if lp else 2 * direct_miles(a, b) * DIRECT_CPM
            trig = "volume surge" if gap > 0 else "volume shortfall"
            events.append({"event_id": f"E{eid:03d}", "checkpoint": cp,
                           "lane": f"{a}-{b}", "direction": direction,
                           "planned_turns": plan_t, "projected_turns": pt,
                           "gap_turns": gap, "trigger": trig})
            if gap > 0:
                overflow_pups = pp - plan_t * PUPS_PER_TURN
                add_cost = gap * tc
                rr = find_reroute(lane, dirc, overflow_pups, cp, proj,
                                  planned_turns, planned_pups, lane_n, flows, path_of)
                aid += 1
                if rr and rr["cost"] < add_cost:
                    actions.append({
                        "action_id": f"A{aid:03d}", "event_id": f"E{eid:03d}",
                        "action_type": "reroute",
                        "detail": (f"Reroute ~{overflow_pups} pups of {rr['od']} via {rr['via']} "
                                   f"instead of adding a turn on {direction}"),
                        "cost_impact_usd": round(rr["cost"], 2),
                        "service_impact": "on-time protected; +2 handles per rerouted shipment",
                        "network_check": (f"network-OK: alternate has {rr['spare']} spare pup slots; "
                                          f"cheaper than +${add_cost:,.0f} for a new turn"),
                        "copilot_message": (
                            f"Central -> {orig} service center ({cp}): {direction} projecting {pt} turns "
                            f"vs {plan_t} planned. Network check: adding a turn costs ${add_cost:,.0f}, but "
                            f"rerouting the overflow via {rr['via']} fills spare pup slots for "
                            f"~${rr['cost']:,.0f}. Recommend the reroute; it is better for the network, "
                            f"not just this lane.")})
                else:
                    why = ("no pre-approved alternate with spare pup slots"
                           if not rr else f"reroute ~${rr['cost']:,.0f} >= new turn")
                    actions.append({
                        "action_id": f"A{aid:03d}", "event_id": f"E{eid:03d}",
                        "action_type": "add_turn",
                        "detail": f"Add {gap} driver turn(s) on {direction} ({gap * PUPS_PER_TURN} pups)",
                        "cost_impact_usd": round(add_cost, 2),
                        "service_impact": "protects on-time; covers surge cube",
                        "network_check": f"network-OK: {why}; new turn is the network-cheapest option",
                        "copilot_message": (
                            f"Central -> {orig} service center ({cp}): {direction} projecting {pt} turns "
                            f"vs {plan_t} planned. Network check done ({why}). Recommend adding "
                            f"{gap} turn(s) (+${add_cost:,.0f}).")})
                aid += 1
                actions.append({
                    "action_id": f"A{aid:03d}", "event_id": f"E{eid:03d}",
                    "action_type": "adjust_dock",
                    "detail": f"Hold {gap * PUPS_PER_TURN} pup doors + crew at {orig} for the added turn(s)",
                    "cost_impact_usd": 0,
                    "service_impact": "avoids dock bottleneck on extra turns",
                    "network_check": "network-OK: dock capacity follows the turn decision",
                    "copilot_message": (
                        f"Central -> {orig} dock ({cp}): keep {gap * PUPS_PER_TURN} doors open for the added "
                        f"{direction} turn(s); confirm crew coverage before cut time.")})
            else:
                # cancelling a turn removes 2 pup slots in BOTH directions (round trip)
                other = "BA" if dirc == "AB" else "AB"
                _, pp_here, _ = proj[(cp, lane, dirc)]
                _, pp_other, _ = proj.get((cp, lane, other), (0, 0, 0))
                slots_after = (plan_t + gap) * PUPS_PER_TURN
                aid += 1
                if pp_here <= slots_after and pp_other <= slots_after:
                    actions.append({
                        "action_id": f"A{aid:03d}", "event_id": f"E{eid:03d}",
                        "action_type": "cancel_turn",
                        "detail": f"Cancel {-gap} driver turn(s) on {direction}; consolidate remaining cube",
                        "cost_impact_usd": round(gap * tc, 2),
                        "service_impact": "no service risk at projected volume",
                        "network_check": ("network-OK: remaining turns cover projected pups in BOTH "
                                          "directions (turn is a round trip)"),
                        "copilot_message": (
                            f"Central -> {orig} service center ({cp}): {direction} projecting {pt} turns "
                            f"vs {plan_t} planned. Network check: the return leg still has room after the "
                            f"cancel. Recommend cancelling {-gap} turn(s) (-${-gap * tc:,.0f}); consolidate "
                            f"remaining freight onto running turns; release the dock crew.")})
                else:
                    actions.append({
                        "action_id": f"A{aid:03d}", "event_id": f"E{eid:03d}",
                        "action_type": "keep_turn",
                        "detail": (f"DO NOT cancel on {direction}: the return leg needs the capacity"),
                        "cost_impact_usd": 0,
                        "service_impact": "avoids stranding freight at the far end",
                        "network_check": ("BLOCKED: cancelling looks like a local saving but strands "
                                          f"{max(pp_other - slots_after, 0)} pups of return-leg freight - "
                                          "worse for the network"),
                        "copilot_message": (
                            f"Central -> {orig} service center ({cp}): cancelling a turn on {direction} "
                            f"saves ${-gap * tc:,.0f} locally, but the turn is a round trip and the return "
                            f"leg still needs the pups. Network check BLOCKS the cancel; keep the turn.")})
    return events, actions


def write_alternate_paths():
    """Monthly network design: standard path + BOUNDED pre-approved alternates.
    Daily execution may only use listed alternates - never a wild reroute."""
    terms = [t[0] for t in TERMINALS]
    rows = []
    for o in terms:
        for d in terms:
            if o == d:
                continue
            for p in PRODUCTS:
                std = standard_path(o, d)
                rows.append({"origin": o, "dest": d, "product": p, "rank": 1,
                             "path": render_path(o, d, std),
                             "path_type": "direct" if len(std) == 1 else "via_hub",
                             "note": "standard path - monthly design"})
                alt = alternate_for(o, d, p)
                if alt:
                    rows.append({"origin": o, "dest": d, "product": p, "rank": 2,
                                 "path": render_path(o, d, alt),
                                 "path_type": "direct" if len(alt) == 1 else "via_hub",
                                 "note": ("pre-approved alternate: cut handles when heavy"
                                          if len(alt) == 1 else
                                          "pre-approved alternate: consolidate to gain density")})
    write_csv(os.path.join(ROOT, "alternate_paths.csv"), rows)



if __name__ == "__main__":
    allk = {}
    for i, (name, scale) in enumerate(SCENARIOS.items()):
        allk[name] = run_scenario(name, scale, 20260926 + i)
    write_alternate_paths()  # monthly network design: standard + bounded alternates
    with open(os.path.join(ROOT, "kpis_all.json"), "w") as f:
        json.dump(allk, f, indent=2)
    print("done ->", ROOT)
