"""FINAL audit (10 Nov 2026): repeat BLR multi-city fares 3x each (Fli/Google) to classify STABLE/UNSTABLE. Saves every attempt."""
import json, datetime as dt, time, os
from fli.models import Airport, FlightSearchFilters, PassengerInfo, SeatType, TripType, MaxStops, SortBy
from fli.search import SearchFlights
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v6
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'results','raw','final_stability')
C=[('TOKYO','2027-03-30','2027-04-09'),('TOKYO','2027-03-28','2027-04-08'),('OSAKA','2027-03-28','2027-04-07'),('OSAKA','2027-03-25','2027-04-05'),('TOKYO','2027-03-23','2027-04-03'),('OSAKA','2027-03-27','2027-04-06')]
tok=[Airport.HND, Airport.NRT]
for direction,dep,ret in C:
    for attempt in (1,2,3):
        s1,s2=(v6.seg([Airport.BLR],[Airport.KIX],dep),v6.seg(tok,[Airport.BLR],ret)) if direction=='OSAKA' else (v6.seg([Airport.BLR],tok,dep),v6.seg([Airport.KIX],[Airport.BLR],ret))
        f=FlightSearchFilters(trip_type=TripType.MULTI_CITY, passenger_info=PassengerInfo(adults=2), flight_segments=[s1,s2], seat_type=SeatType.ECONOMY, stops=MaxStops.ANY, sort_by=SortBy.CHEAPEST)
        err=None; res=[]
        try:
            r=SearchFlights().search(f, top_n=8, currency='INR') or []
            res=[dict(total=(t[-1].price if t[-1].price is not None else t[0].price), legs=v6.ser(t if isinstance(t,tuple) else (t,))) for t in r]
        except Exception as e: err=repr(e)[:200]
        ts=dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')
        json.dump(dict(ts=ts,direction=direction,dep=dep,ret=ret,attempt=attempt,err=err,res=res),open(os.path.join(OUT,f'{direction}-{dep}_{ret}-a{attempt}.json'),'w'))
        print(direction,dep,ret,'a'+str(attempt),ts,'ERR '+err if err else '','n',len(res),'min',min([x['total'] for x in res if x['total']],default=None),flush=True)
        time.sleep(8)
print('ALL DONE',flush=True)
