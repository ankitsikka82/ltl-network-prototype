# Data dictionary — freight LTL prototype sample data
All figures ILLUSTRATIVE for prototype purposes, not carrier operating data.
Network: hub-and-spoke — 2 breakbulk hubs (SGF Springfield MO, MEM Memphis TN) with
spokes STL/TUL (SGF) and MKC/LIT (MEM). Operating cycles: outbound 12:00–21:00
(bids 17:00, 21:00 cut), hub sort 21:00–05:00, AM 05:00–12:00 (bids 09:00, 12:00 cut).
One operating day: 2026-09-28. Scenarios: `base` (1050 shipments), `light` (65% vol),
`heavy` (130% vol). Schema is date-keyed; extend to a week by adding dates.

## Per-scenario files (`data/<scenario>/`)
| file | grain | description |
|---|---|---|
| terminals.csv | terminal | code, city, type (breakbulk/eol) |
| lanes.csv | lane | scheduled linehaul lanes: terminal_a/b, miles, cost_per_mile_usd (domicile pay + demographics) |
| design_routes.csv | OD x product | the structured network: ONE standard path per OD x product, path type (direct/via_hub), miles |
| shippers.csv | customer | home terminal, commodity, density_lb_per_cuft (basis for cube inference) |
| shipments.csv | shipment | customer, origin, dest, product (P=Priority fast, E=Economy ~1 day slower), weight, pieces, inferred_cube_cuft (planner's pickup estimate), dimmed_cube_cuft (dock actual, known too late), revenue_usd (what customer paid) |
| forecast_lane.csv | OD x product | yesterday's lane forecast (shipments, cube) vs actuals incl. dimmed cube |
| linehaul_actuals.csv | dispatched pup | load_id, lane, direction, bid_id, depart_time (scheduled bid departure), turn_no (one driver turn = 2 pups), cube/weight loaded, cube_util_pct, empty flag (empty pup riding on a running turn), flows aboard |
| bids.csv | lane x direction x bid | scheduled bid departures: cycle, depart_time, cut flag, freight cube, pups needed, drivers staffed (ceil(pups/2)) |
| bid_opportunities.csv | directed lane | structural cut-time findings: merge the early bid into the cut — pups/drivers before vs after, lane turns saved, saving_usd, Priority freight exposure, service_check (OK/REVIEW) |
| deviations.csv | OD x product | where the plan deviated from standard path: chosen path, reason, saving_usd |
| cost_to_serve.csv | shipment | revenue vs pud_cost + dock_cost + linehaul_cost (by leg, see leg_cost_detail), margin_usd, margin_pct |
| lane_scoreboard.csv | lane x direction | driver turns, cube, utilization (vs turn capacity = 2 pups), leg cost, cost_per_cube_mile_usd (leg efficiency), verdict (good miles / watch / bad miles) |
| tower_events.csv | lane x direction x checkpoint | Central's day-of triggers: 10:00/14:00/18:00 checkpoints, planned vs projected driver turns, gap, trigger (surge/shortfall) |
| tower_actions.csv | recommended action | add_turn / cancel_turn / keep_turn / reroute / adjust_dock: detail, cost_impact_usd, service_impact, network_check (network-global feasibility verdict), copilot_message (GenAI-style draft to the service center) |
| kpis.json | scenario | revenue, cost to serve, margin, linehaul/dock/pud split, avg cube utilization, empty pup %, driver turns, handles/shipment, deviations + savings, forecast MAPE, tower events/actions/net |

## Shared files (`data/`)
| file | description |
|---|---|
| alternate_paths.csv | monthly network design: standard path (rank 1) + bounded pre-approved alternates (rank 2) per OD x product; daily deviations may only use listed alternates |
| ontology.yaml | context-engineering layer: entities, relationships, constraints, business rules, metric definitions, GenAI roles, math model sketch, implementation stack |
| kpis_all.json | KPIs for base/light/heavy side by side |

## Key concepts
- **Cube inference**: shippers don't provide cube; planner estimates at pickup from shipper density. Dock dimming gives truth too late for door/trailer planning.
- **Doubles / driver turns**: one driver pulls two pups out and brings two pups back, full or empty. The turn is the cost unit: turns(direction) = sum over scheduled bid departures of ceil(pups_in_bid/2); turns(lane) = max(turns_AB, turns_BA), and turn cost is fixed whether pups are full or empty. Fill the second pup before dispatching another driver.
- **Bid departures and cut times**: drivers bid on start times; each bid that carries freight needs its own drivers. When freight is thin across a cycle's bids, merging the early bid into the cut departure can eliminate a driver shift — the cut-time optimizer tests this lane by lane, structurally (design) and day-specifically (simulator), and never recommends a move that sacrifices Priority service.
- **Domiciled round trips**: drivers return to home service centers nightly; a turn is a round trip, so cancelling a turn removes capacity in BOTH directions. Equipment balances because drivers come home.
- **Two horizons**: monthly network design sets standard paths + bounded alternates; daily execution deviates only within those bounds, purely on cost (linehaul turns vs dock handles).
- **Network-global tower**: Central's add/cancel/reroute recommendations are checked network-wide. A locally-cheap cancel that strands return-leg freight is BLOCKED; a surge is served by the cheaper of a new turn vs rerouting into spare pup slots on a pre-approved alternate.
- **Empty pup slots, not empty miles**: with domiciled doubles the waste is density — empty pup slots riding on running turns at ~$0 marginal cost.
- **Deviation rule**: follow the standard path unless deviating lowers total cost (linehaul vs dock handles). Heavy via-hub flow -> direct (cut handles); light direct flow -> via hub (gain density).
- **Cost to serve**: turn cost splits across directions by cube share, so imbalance-causing freight absorbs its empty returns. Compare against revenue for margin by shipment, lane, customer, product.
