"""V6 (2026-11-10): fresh Fli/Google Flights multi-city sweep, BLR origin, 2 adults, INR. Writes results/raw/v6/*.json (same schema as v2/v4). Resumable.
Usage: .venv/bin/python v6.py [group ...]   groups: sakura jan mar apr may autumn"""
import sys, os, json, time, datetime as dt, threading
from concurrent.futures import ThreadPoolExecutor
from fli.models import Airport, FlightSegment, FlightSearchFilters, PassengerInfo, SeatType, TripType, MaxStops, SortBy
from fli.search import SearchFlights
ROOT = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(ROOT, 'results', 'raw', 'v6'); os.makedirs(OUT, exist_ok=True)
def d(m, day, y=2027): return dt.date(y, m, day).isoformat()
G = {}
S = {22: [(4, 1), (4, 2), (4, 3)], 23: [(4, 2), (4, 3), (4, 4), (4, 5)], 24: [(4, 3), (4, 4), (4, 5)], 25: [(4, 4), (4, 5), (4, 6)], 26: [(4, 4), (4, 5), (4, 6), (4, 7)],
     27: [(4, 5), (4, 6), (4, 7), (4, 8)], 28: [(4, 6), (4, 7), (4, 8)], 29: [(4, 7), (4, 8), (4, 9)], 30: [(4, 7), (4, 8), (4, 9), (4, 10)], 31: [(4, 8), (4, 9), (4, 10)]}
G['sakura'] = [(d(3, a), d(*r)) for a, rs in S.items() for r in rs]
G['jan'] = [(d(1, a), d(*r)) for a, rs in {21: [(1, 30), (1, 31)], 22: [(1, 31), (2, 1)], 23: [(2, 1), (2, 2)], 24: [(2, 2), (2, 3)]}.items() for r in rs]
G['mar'] = [(d(3, a), d(3, r)) for a, rs in {4: [13, 14], 5: [13, 14, 15], 6: [14, 15, 16], 7: [15, 16, 17]}.items() for r in rs]
G['apr'] = [(d(4, a), d(4, r)) for a, r in [(12, 22), (13, 23), (14, 24), (15, 25), (12, 23), (14, 25)]]
G['may'] = [(d(5, a), d(5, r)) for a, r in [(8, 18), (9, 19), (10, 20), (11, 21), (8, 19), (10, 21)]]
G['autumn'] = [(d(10, 29), d(11, 7)), (d(10, 29), d(11, 8)), (d(10, 30), d(11, 8)), (d(10, 30), d(11, 9)), (d(10, 31), d(11, 9)), (d(10, 31), d(11, 10)),
               (d(11, 18), d(11, 28)), (d(11, 19), d(11, 29)), (d(11, 20), d(11, 30)), (d(11, 21), d(12, 1))]
lock = threading.Lock()
def seg(o, de, date): return FlightSegment(departure_airport=[[a, 0] for a in o], arrival_airport=[[a, 0] for a in de], travel_date=date)
def ser(r):
    L = []
    for x in r:
        L.append(dict(dur=x.duration, stops=x.stops, self=False, lay=[[l.airport.name, l.duration] for l in (x.layovers or [])],
                      segs=[[l.airline.name.lstrip('_'), l.flight_number, l.departure_airport.name, l.arrival_airport.name, l.departure_datetime.isoformat(), l.arrival_datetime.isoformat()] for l in x.legs]))
    return L
def run(job):
    direction, dep, ret = job
    tag = f"MC6-{direction}-{dep}_{ret}.json"; p = os.path.join(OUT, tag)
    if os.path.exists(p): return
    tok = [Airport.HND, Airport.NRT]
    s1, s2 = (seg([Airport.BLR], [Airport.KIX], dep), seg(tok, [Airport.BLR], ret)) if direction == 'OSAKA' else (seg([Airport.BLR], tok, dep), seg([Airport.KIX], [Airport.BLR], ret))
    f = FlightSearchFilters(trip_type=TripType.MULTI_CITY, passenger_info=PassengerInfo(adults=2), flight_segments=[s1, s2], seat_type=SeatType.ECONOMY, stops=MaxStops.ANY, sort_by=SortBy.CHEAPEST)
    err = None; res = []
    for attempt in range(2):
        try:
            r = SearchFlights().search(f, top_n=8, currency='INR'); res = []
            for t in (r or []):
                t = t if isinstance(t, tuple) else (t,)
                tot = t[-1].price if t[-1].price is not None else t[0].price
                res.append(dict(total=tot, legs=ser(t)))
            err = None; break
        except Exception as e: err = repr(e)[:300]; time.sleep(5)
    with lock, open(p, 'w') as fh: json.dump(dict(ts=dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST'), adults=2, dep=dep, ret=ret, direction=direction, err=err, res=res), fh)
    print(tag, 'ERR ' + err if err else f'{len(res)} itins, min={min([x["total"] or 1e9 for x in res], default=None)}', flush=True)
    time.sleep(1.0)
if __name__ == '__main__':
    gs = sys.argv[1:] or list(G)
    jobs = [(dr, a, b) for g in gs for a, b in G[g] for dr in ('OSAKA', 'TOKYO')]
    print(len(jobs), 'jobs', flush=True)
    with ThreadPoolExecutor(2) as ex: list(ex.map(run, jobs))
