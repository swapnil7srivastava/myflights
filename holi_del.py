"""Holi/Noida scenario (10 Nov 2026): DEL-origin 2-leg multi-city Japan + return to BLR. Writes results/raw/holi_noida/DEL-*.json. Not the BLR sweep."""
import sys, os, json, time, datetime as dt, threading
from concurrent.futures import ThreadPoolExecutor
from fli.models import Airport, FlightSegment, FlightSearchFilters, PassengerInfo, SeatType, TripType, MaxStops, SortBy
from fli.search import SearchFlights
ROOT=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(ROOT,'results','raw','holi_noida'); os.makedirs(OUT,exist_ok=True)
def seg(o,d,date): return FlightSegment(departure_airport=[[a,0] for a in o], arrival_airport=[[a,0] for a in d], travel_date=date)
def ser(x): return dict(total=x[-1].price if x[-1].price is not None else x[0].price, legs=[dict(dur=l.duration if hasattr(l,'duration') else None, segs=[[s.airline.name.lstrip('_'), s.flight_number, s.departure_airport.name, s.arrival_airport.name, s.departure_datetime.isoformat(), s.arrival_datetime.isoformat()] for s in l.legs], lay=[[a.airport.name,a.duration] for a in (l.layovers or [])]) for l in x])
jobs=[]
for J in range(23,31):
    for k in (9,10,11):
        R=dt.date(2027,3,J)+dt.timedelta(k+1)  # return date = Japan departure
        jobs.append(('OSAKA', f'2027-03-{J}', R.isoformat()))
        jobs.append(('TOKYO', f'2027-03-{J}', R.isoformat()))
def run(job):
    direction, dep, ret = job; p=os.path.join(OUT, f'DEL-{direction}-{dep}_{ret}.json')
    if os.path.exists(p): return
    tok=[Airport.HND, Airport.NRT]
    s1,s2 = (seg([Airport.DEL],[Airport.KIX],dep), seg(tok,[Airport.BLR],ret)) if direction=='OSAKA' else (seg([Airport.DEL],tok,dep), seg([Airport.KIX],[Airport.BLR],ret))
    f=FlightSearchFilters(trip_type=TripType.MULTI_CITY, passenger_info=PassengerInfo(adults=2), flight_segments=[s1,s2], seat_type=SeatType.ECONOMY, stops=MaxStops.ANY, sort_by=SortBy.CHEAPEST)
    err=None; res=[]
    try:
        r=SearchFlights().search(f, top_n=8, currency='INR') or []
        res=[ser(t if isinstance(t,tuple) else (t,)) for t in r]
    except Exception as e: err=repr(e)[:300]
    ts=dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
    json.dump(dict(ts=ts,direction=direction,dep=dep,ret=ret,err=err,res=res),open(p,'w'))
    print(direction,dep,ret,ts,'ERR '+err if err else '', 'n',len(res),'min',min([x['total'] for x in res if x['total']],default=None), flush=True)
    time.sleep(1.0)
if __name__=='__main__':
    print(len(jobs),'jobs',flush=True)
    with ThreadPoolExecutor(2) as ex: list(ex.map(run,jobs))
    print('ALL DONE',flush=True)
