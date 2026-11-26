"""Delhi-origin vs Bengaluru-origin comparison from cached Fli results (2 adults). Usage: .venv/bin/python delhi.py
Writes results/delhi_comparison.csv, results/delhi_date_matrix.csv and prints a summary. Offline only."""
import csv, datetime as dt, glob, json, os, re, sys, collections
ROOT = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(ROOT, 'results'); V2 = os.path.join(R, 'raw', 'v2')
sys.path.insert(0, ROOT)
import finalists as F
T = dt.datetime.fromisoformat; D = dt.date
CAP, EXC = 960, 1075
HOL = {D(2027, 3, 26): 'Good Friday', D(2027, 4, 8): 'Ugadi (7/8 disputed)'}

def leave(s, e):
    m = []; d = s.date()
    while d <= e.date():
        if d.weekday() < 5 and not (d == s.date() and s.hour >= 20): m.append(d)
        d += dt.timedelta(1)
    return m

def ap(name):
    return F.JP_AIRPORT(name) if any(k in name for k in ('Haneda', 'Narita', 'Kansai', 'Bengaluru')) else ('NGO' if 'Chubu' in name or 'Nagoya' in name else 'DEL' if 'Delhi' in name or 'Indira' in name else name[:3].upper())

# ---- positioning fares BLR->DEL (2 adults, cheapest one-way per date) from cache
pos = {}
for f in glob.glob(os.path.join(V2, 'BLR-DEL-*-a2-*.json')):
    d = json.load(open(f)); q = d['q']; ps = [x['price'] for x in d['res'] if x['price']]
    if ps: pos[q[2]] = (min(ps), d['ts'], os.path.basename(f), [x for x in d['res'] if x['price'] == min(ps)][0])

# ---- BLR baseline: cheapest Osaka-first / any BLR quote per (out dep date, ret dep date), <=17h55
blr = {}
for x, ts, b in F.load():
    r = F.desc(x, ts)
    if r['out_dur'] > EXC or r['ret_dur'] > EXC: continue
    k = (r['dep'].date().isoformat(), r['dep_jp'].date().isoformat())
    if k not in blr or blr[k]['total'] > r['total']: blr[k] = r

rows = []
for f in sorted(glob.glob(os.path.join(V2, 'MC*-DEL-*-BLR-*.json'))):
    b = os.path.basename(f)
    m = re.match(r'MC\d*V?-DEL-([A-Z+]+)-(\d{4}-\d\d-\d\d)_([A-Z+]+)-BLR-(\d{4}-\d\d-\d\d)', b)
    if not m: continue
    d = json.load(open(f))
    for x in d['res']:
        if not x['total'] or len(x['legs']) < 2: continue
        o, r = x['legs'][:2]; so, sr = o['segs'], r['segs']
        od, oa, rd, ra = T(so[0][4]), T(so[-1][5]), T(sr[0][4]), T(sr[-1][5])
        nights = (rd.date() - oa.date()).days; cd = (ra.date() - od.date()).days + 1
        miss = leave(od, ra)
        reasons = []
        if max(o['dur'], r['dur']) > EXC: reasons.append('OVER_17H55')
        exc = CAP < max(o['dur'], r['dur']) <= EXC
        if exc: reasons.append('DURATION_EXCEPTION_16H-17H55')
        if not 8 <= nights <= 12: reasons.append(f'NIGHTS_{nights}_OUTSIDE_8_12')
        arr_ap = ap(so[-1][3]); dep_ap = ap(sr[0][2])
        chg = any(ap(so[i][3]) != ap(so[i + 1][2]) for i in range(len(so) - 1)) or any(ap(sr[i][3]) != ap(sr[i + 1][2]) for i in range(len(sr) - 1))
        if chg: reasons.append('AIRPORT_CHANGE')
        direction = 'OSAKA_FIRST' if arr_ap == 'KIX' and dep_ap in ('HND', 'NRT') else 'TOKYO_FIRST' if arr_ap in ('HND', 'NRT') and dep_ap == 'KIX' else f'{arr_ap}->{dep_ap}'
        route_id = f"DEL>{arr_ap}|{dep_ap}>BLR"
        # positioning: same-day if the DEL departure is evening (>=20:00) else day before (+ hotel UNKNOWN)
        pday = od.date() if od.hour >= 20 else od.date() - dt.timedelta(1)
        pp = pos.get(pday.isoformat())
        night_before = od.hour < 20
        positioning = pp[0] if pp else 'UNKNOWN'
        allin = (x['total'] + pp[0]) if pp else 'UNKNOWN'
        bl = blr.get((od.date().isoformat(), rd.date().isoformat()))
        bl_total = bl['total'] if bl else 'UNKNOWN'
        sav = (bl_total - x['total']) if bl else 'UNKNOWN'
        net = (bl_total - allin) if (bl and pp) else 'UNKNOWN'
        if night_before: reasons.append('POSITIONING_NEEDS_NIGHT_IN_DELHI_HOTEL_UNKNOWN')
        reasons.append('BAGGAGE_UNVERIFIED')
        rows.append(dict(route_id=route_id, search_timestamp=d['ts'], outbound_date=od.date().isoformat(), return_date=rd.date().isoformat(), actual_india_arrival_date=ra.date().isoformat(),
            india_origin='DEL', japan_arrival_airport=arr_ap, japan_departure_airport=dep_ap, india_return_airport='BLR', airline='/'.join(sorted({g[0][:2].upper() for g in so + sr})),
            flight_numbers=' '.join(g[0][:2].upper() + g[1] for g in so) + ' | ' + ' '.join(g[0][:2].upper() + g[1] for g in sr),
            stop_airports=';'.join(ap(g[3]) for g in so[:-1]) + ' | ' + ';'.join(ap(g[3]) for g in sr[:-1]), duration_outbound=f"{o['dur']//60}h{o['dur']%60:02d}", duration_return=f"{r['dur']//60}h{r['dur']%60:02d}",
            japan_hotel_nights=nights, india_calendar_days=cd, leave_days=len(miss), price_for_2_inr=int(x['total']), domestic_positioning_cost=positioning, baggage_cost='UNKNOWN', additional_transport_cost='UNKNOWN',
            all_in_total=allin, blr_comparable_total=bl_total, delhi_savings=sav, net_savings_after_positioning=net, baggage_status='UNVERIFIED',
            ticketing_status='UNVERIFIED (Google multi-city itinerary; positioning would be a separate ticket)', price_verification_status='SINGLE_OBSERVATION', booking_url='UNKNOWN',
            source='fli_google_flights_multicity_adults2', evidence_file=os.path.relpath(f, ROOT), rejection_reason=';'.join(reasons), _dir=direction, _chg=chg, _exc=exc, _od=od, _oa=oa, _rd=rd, _ra=ra,
            _o=o, _r=r, _pdate=pday, _pos=pp))
COLS = ['route_id', 'search_timestamp', 'outbound_date', 'return_date', 'actual_india_arrival_date', 'india_origin', 'japan_arrival_airport', 'japan_departure_airport', 'india_return_airport', 'airline',
        'flight_numbers', 'stop_airports', 'duration_outbound', 'duration_return', 'japan_hotel_nights', 'india_calendar_days', 'leave_days', 'price_for_2_inr', 'domestic_positioning_cost',
        'baggage_cost', 'additional_transport_cost', 'all_in_total', 'blr_comparable_total', 'delhi_savings', 'net_savings_after_positioning', 'baggage_status', 'ticketing_status',
        'price_verification_status', 'booking_url', 'source', 'evidence_file', 'rejection_reason']
# dedupe exact observation, append-only
path = os.path.join(R, 'delhi_comparison.csv'); old = list(csv.DictReader(open(path, newline=''))) if os.path.exists(path) else []
seen = {tuple(o[c] for c in COLS) for o in old}; out = list(old)
for r in rows:
    t = {c: str(r[c]) for c in COLS}
    if tuple(t[c] for c in COLS) not in seen: out.append(t); seen.add(tuple(t[c] for c in COLS))
tmp = path + '.tmp'
with open(tmp, 'w', newline='') as fh: w = csv.DictWriter(fh, fieldnames=COLS); w.writeheader(); w.writerows(out)
os.replace(tmp, path)
# date matrix
mat = collections.defaultdict(dict)
for r in rows:
    if 'OVER_17H55' in r['rejection_reason'] or not 8 <= r['japan_hotel_nights'] <= 12: continue
    k = (r['outbound_date'], r['return_date'], r['_dir']); tier = 'EXC' if r['_exc'] else 'OK'
    if tier not in mat[k] or mat[k][tier]['price_for_2_inr'] > r['price_for_2_inr']: mat[k][tier] = r
path2 = os.path.join(R, 'delhi_date_matrix.csv'); tmp = path2 + '.tmp'
with open(tmp, 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['outbound_date', 'return_date', 'japan_direction', 'japan_nights', 'del_best_16h', 'del_best_exception', 'del_flights_16h', 'positioning_cost', 'del_all_in_16h', 'blr_comparable', 'del_savings_no_positioning', 'net_savings_with_positioning', 'airport_change'])
    for k in sorted(mat):
        ok = mat[k].get('OK') or mat[k].get('EXC'); e = mat[k].get('EXC')
        w.writerow([k[0], k[1], k[2], ok['japan_hotel_nights'], mat[k]['OK']['price_for_2_inr'] if 'OK' in mat[k] else '', e['price_for_2_inr'] if e else '', ok['flight_numbers'], ok['domestic_positioning_cost'], ok['all_in_total'], ok['blr_comparable_total'], ok['delhi_savings'], ok['net_savings_after_positioning'], ok['_chg']])
os.replace(tmp, path2)
json.dump([{k: (str(v) if not isinstance(v, (int, float, bool, str)) else v) for k, v in r.items() if not k.startswith('_o') and k not in ('_r', '_pos')} for r in rows], open('/tmp/fs/delhi_rows.json', 'w'))
print('rows', len(rows), 'csv', len(out), 'positioning dates cached', sorted(pos))
