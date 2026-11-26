"""Hourly fare watcher (Fli / Google Flights data, 2 adults, INR). Run: .venv/bin/python watch.py [hours]
Logs every observation to results/overnight_watch/observations.csv, flags anything cheaper than the baselines in BETTER_FINDS.md.
Stops on results/overnight_watch/STOP, stops a cycle early on repeated fast-empty responses (throttling). No booking, no login."""
import sys, os, time, csv, json, datetime
from fli.models import *
from fli.core import build_multi_city_segments, resolve_airport, normalize_date
from fli.search import SearchFlights
ROOT = os.path.dirname(os.path.abspath(__file__)); W = os.path.join(ROOT, 'results', 'overnight_watch'); os.makedirs(W, exist_ok=True)
OBS = os.path.join(W, 'observations.csv'); BEST = os.path.join(W, 'BETTER_FINDS.md'); STATE = os.path.join(W, 'state.json')
BASE = {  # historical provisional baselines (INR, 2 adults)
 'A_BLR_23Mar_to_2Apr': 148840, 'A_BLR_23Mar_to_1Apr': 148840, 'A_BLR_23Mar_to_3Apr': 174642,
 'B_BLR_29Mar_to_7Apr': 149068, 'B_BLR_29Mar_to_6Apr': 149068, 'B_BLR_29Mar_to_8Apr': 149068,
 'C_DEL_TokyoFirst_23Mar_to_2Apr': 150950, 'C_DEL_KIX_23Mar_to_2Apr': 167210, 'C_DEL_KIX_25Mar_to_5Apr': 167232,
 'AI360_DEL_KIX_23Mar': 96226, 'AI360_DEL_KIX_25Mar': 96226, 'DOM_BLR_DEL_21Mar': 18664, 'DOM_BLR_DEL_20Mar': 18664, 'DOM_BLR_DXN_21Mar': 18142}
def ts(): return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
def mc(origin, out_to, ret_from, o, r):
    segs, tt = build_multi_city_segments(legs=[(resolve_airport(origin), resolve_airport(out_to[0]), normalize_date(o)), (resolve_airport(ret_from[0]), resolve_airport('BLR'), normalize_date(r))], time_restrictions=None)
    segs[0].arrival_airport = [[resolve_airport(a), 0] for a in out_to]; segs[1].departure_airport = [[resolve_airport(a), 0] for a in ret_from]
    return FlightSearchFilters(trip_type=tt, passenger_info=PassengerInfo(adults=2), flight_segments=segs, stops=MaxStops.ANY, seat_type=SeatType.ECONOMY, max_duration=1075, sort_by=SortBy.CHEAPEST)
def ow(o, d, dt, maxdur=1075):
    segs = [FlightSegment(departure_airport=[[resolve_airport(o), 0]], arrival_airport=[[resolve_airport(d), 0]], travel_date=normalize_date(dt))]
    return FlightSearchFilters(trip_type=TripType.ONE_WAY, passenger_info=PassengerInfo(adults=2), flight_segments=segs, stops=MaxStops.ANY, seat_type=SeatType.ECONOMY, max_duration=maxdur, sort_by=SortBy.CHEAPEST)
JOBS = [('A_BLR_23Mar_to_2Apr', mc('BLR', ['KIX'], ['HND', 'NRT'], '2027-03-23', '2027-04-02'), 6), ('A_BLR_23Mar_to_1Apr', mc('BLR', ['KIX'], ['HND', 'NRT'], '2027-03-23', '2027-04-01'), 6),
 ('B_BLR_29Mar_to_7Apr', mc('BLR', ['KIX'], ['HND', 'NRT'], '2027-03-29', '2027-04-07'), 6), ('B_BLR_29Mar_to_6Apr', mc('BLR', ['KIX'], ['HND', 'NRT'], '2027-03-29', '2027-04-06'), 4),
 ('C_DEL_TokyoFirst_23Mar_to_2Apr', mc('DEL', ['HND', 'NRT'], ['KIX'], '2027-03-23', '2027-04-02'), 6), ('C_DEL_KIX_23Mar_to_2Apr', mc('DEL', ['KIX'], ['HND', 'NRT'], '2027-03-23', '2027-04-02'), 6),
 ('C_DEL_KIX_25Mar_to_5Apr', mc('DEL', ['KIX'], ['HND', 'NRT'], '2027-03-25', '2027-04-05'), 6), ('AI360_DEL_KIX_23Mar', ow('DEL', 'KIX', '2027-03-23'), 1), ('AI360_DEL_KIX_25Mar', ow('DEL', 'KIX', '2027-03-25'), 1),
 ('DOM_BLR_DEL_21Mar', ow('BLR', 'DEL', '2027-03-21', 600), 1), ('DOM_BLR_DEL_20Mar', ow('BLR', 'DEL', '2027-03-20', 600), 1), ('DOM_BLR_DXN_21Mar', ow('BLR', 'DXN', '2027-03-21', 600), 1)]
def describe(it):
    it = it if isinstance(it, tuple) else (it,)
    return it[-1].price, ' || '.join(' + '.join(f"{g.airline.name}{g.flight_number} {g.departure_airport.name}-{g.arrival_airport.name} {g.departure_datetime:%d%b %H:%M}" for g in x.legs) + f" [{x.duration//60}h{x.duration%60:02d}]" for x in it)
def log(rows):
    new = not os.path.exists(OBS)
    with open(OBS, 'a', newline='') as fh:
        w = csv.writer(fh)
        if new: w.writerow(['timestamp_ist', 'scenario', 'rank_in_result', 'price_for_2_inr', 'baseline_inr', 'delta_vs_baseline', 'itinerary'])
        w.writerows(rows)
def main(hours):
    st = json.load(open(STATE)) if os.path.exists(STATE) else {'best': {}}
    for cycle in range(hours):
        if os.path.exists(os.path.join(W, 'STOP')): break
        t0 = time.time(); fast = 0; found = []
        for name, f, top in JOBS:
            q0 = time.time()
            try: r = SearchFlights().search(f, top_n=top, currency='INR') or []
            except Exception as e: open(os.path.join(W, 'errors.log'), 'a').write(f'{ts()} {name} {repr(e)[:100]}\n'); continue
            if not r and time.time() - q0 < 6:
                fast += 1
                if fast >= 2: open(os.path.join(W, 'errors.log'), 'a').write(f'{ts()} THROTTLED - cycle cut short\n'); break
                continue
            fast = 0; rows = []
            priced = sorted([(describe(x), x) for x in r if (x[-1] if isinstance(x, tuple) else x).price], key=lambda t: t[0][0])
            for rank, ((p, d), _) in enumerate(priced[:5], 1): rows.append([ts(), name, rank, int(p), BASE[name], int(p) - BASE[name], d])
            log(rows)
            if priced:
                p, d = priced[0][0]
                if p < BASE[name] and (name not in st['best'] or p < st['best'][name]['price']):
                    st['best'][name] = {'price': p, 'ts': ts(), 'itinerary': d}; found.append((name, p, d))
            time.sleep(4)
        if found:
            with open(BEST, 'a') as fh:
                for name, p, d in found: fh.write(f"- **{ts()}** {name}: ₹{int(p):,} (baseline ₹{BASE[name]:,}, −₹{BASE[name]-int(p):,}) — {d}\n")
        json.dump(st, open(STATE, 'w'), indent=1)
        open(os.path.join(W, 'last_run.txt'), 'w').write(f'cycle {cycle+1}/{hours} finished {ts()}; better finds this cycle: {len(found)}\n')
        if cycle < hours - 1: time.sleep(max(60, 3600 - (time.time() - t0)))
if __name__ == '__main__': main(int(sys.argv[1]) if len(sys.argv) > 1 else 12)
