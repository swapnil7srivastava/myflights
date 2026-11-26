# Flight Scout — Personal CLI Flight Finder

Your sole purpose in this folder is to execute practical, on-demand searches for real flight offers, following `flight_config.yaml`. Keep it simple: no website, database, deployment, monitoring job, broad framework, or architecture project.

## Providers

- Use the existing project-scoped `octotrip-flights` MCP, specified in `.mcp.json`, as the first live source. Tools support one-way or ordinary round-trip search, two adults, Y/C cabin classes and INR currency. This is a hosted, no-key third-party service with affiliate booking links; its open repository is not proof of a fully self-hostable backend.
- If necessary, install the open-source MIT-licensed `punitarani/fli` Python CLI/MCP in a local `.venv` and use it as a second independent live source. Confirm installation from current repository documentation, then smoke-test. Its multi-city search currently raises `SearchUnsupportedError`; never claim a genuine multi-city price from it. Do not bypass anti-bot protections.
- If a source fails, show exactly what failed. Never fabricate live fares, timestamps, screenshots, discounts, baggage allowances or booking links. Do not use paid APIs or create paid accounts.
- Since new MCP configurations may need a Claude Code restart, verify `/mcp` connection first. If disconnected, explain the one-time restart needed, or use an existing accessible source to search immediately; do not claim successful searches without real evidence.

## Trip interpretation

- Read the YAML config every search. Search outbound BLR -> KIX and return HND -> BLR first; include NRT fallback, and cost-check BOM/DEL only if meaningfully cheaper AFTER positioning from/to BLR and inconvenience costs.
- Outbound search dates are 2027-03-22 through 2027-03-28 inclusive; return dates are 2027-04-02 through 2027-04-08 inclusive. Target dates are March 25 and April 5. Prefer roughly 10–12 nights but do not silently eliminate other valid date pairs.
- This is **open-jaw**: KIX inbound to Japan and HND/NRT outbound from Japan. Search each international one-way leg and form provisional combinations. Those sums are **separate-ticket estimates**, NOT verified multi-city/together-ticket prices. Where possible, compare an actual bookable multi-city fare from a source that really supports it, or provide a clearly labelled Google Flights multi-city verification link and ask the user to check the combined fare there. Never invent a multi-city fare.
- Analyze economy both ways, economy outbound/business return, and business both ways where live data allows. Start economy scanning, then check premium cabins on the best shortlisted date pairs to control search calls.
- All amounts in INR. Clearly state whether source price is **per passenger or total for 2 adults**; do not assume a price basis. Compare all-in fares with baggage, fees, repositioning, transfers and hotels when available; missing items must be marked unknown/unpriced, not zero. Do not claim checkout verification unless actually performed.
- Prefer <=1 stop and convenient layovers. Separate domestic positioning tickets must be transparent, warned as self-transfer, with substantial connection buffers; prefer an overnight buffer when possible. Do not call them protected connections.

## Execution strategy

1. Verify tools via a live smoke-test: BLR->KIX 2027-03-25, 2 adults, economy, INR; then HND->BLR 2027-04-05.
2. If live calls succeed, sweep 7 departure dates and 7 return dates independently instead of blindly making 49+ full date-pair searches. Start with center dates, neighboring dates and weekends/weekday contrasts. Respect OctoTrip's published 1-request/second limit; do not flood services. Use up to 16 initial calls; extend only if there is a convincing route to better fares and provider allows it.
3. For each leg retain 2–4 worthwhile offers per date when available. Combine only compatible date pairs; rank by total price, travel time, flight times, number of stops, risk, fees, and baggage. Show results of incomplete searches as incomplete.
4. Compare NRT and alternate India gateways after baseline, especially when there are demonstrable savings. Search repositioning fares separately and show inclusive price versus BLR baseline; don't pretend a disconnected international ticket is the full trip cost.
5. Re-query finalist combinations so fare timestamps are fresh; OctoTrip reports booking links/results as valid for approximately 15 minutes, so timestamp all outputs.
6. Write a human-readable `results/latest.md` table with cheapest / fastest / best overall / best premium value, plus route segments, airlines, dates, local times, stops, duration, baggage, source, fare basis, prices, live verification timestamp, and original links. Save structured raw output only if truly useful. Include queries that failed and unsearched combinations.
7. Reply in the CLI with the exact top options, links, an explicit confidence assessment grounded in completed search coverage, and a one-sentence next action. Never create bookings or make payments.

Keep files minimal. The actual goal is **useful live flight results right now**, not a code project.

## Fli notes (learned 31 Oct 2026)
- Fli 0.9.0: the CLI has no passengers flag; use the Python API with `PassengerInfo(adults=2)`. `adults=2` returns a party-total price.
- `fli multi` and the API support multi-city; multi-city fares can be far cheaper than summed one-ways (JAL BLR->NRT->KIX + NRT->BLR).
- The Fli bag filter does not change prices; airline filters can return unpriced results. Baggage must be verified manually.
- Itineraries with no price must not be silently dropped when summarising.
