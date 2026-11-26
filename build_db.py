"""Merge cached Fli results into results/*.csv (append-only observations, atomic writes).
Usage: .venv/bin/python build_db.py
Only real provider responses become rows. UNKNOWN is never replaced with 0."""
import csv, datetime as dt, glob, hashlib, json, os, collections, re

ROOT = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(ROOT, 'results'); RAW = os.path.join(R, 'raw'); V2 = os.path.join(RAW, 'v2')
D = dt.date.fromisoformat
CAP, EXC = 960, 1075
COLS = ['candidate_id', 'search_timestamp_ist', 'source', 'source_query_id', 'origin', 'destination', 'outbound_date', 'return_date', 'japan_direction', 'japan_nights',
        'outbound_airlines', 'return_airlines', 'outbound_flight_numbers', 'return_flight_numbers', 'outbound_stops', 'return_stops', 'outbound_duration_min', 'return_duration_min',
        'outbound_layover_details', 'return_layover_details', 'passenger_count', 'cabin', 'quoted_price_inr', 'quoted_price_basis', 'positioning_cost_inr', 'extra_japan_transport_inr',
        'checked_baggage_status', 'baggage_cost_inr', 'other_mandatory_cost_inr', 'all_in_total_inr', 'price_verification_status', 'ticket_protection_status', 'booking_url',
        'duration_exception', 'budget_status', 'qualification_status', 'rejection_reason', 'evidence_file']
JP = {'HND', 'NRT'}


def iata(name):  # airport names were stored truncated in some files; keep first 3 letters if already IATA
    return name[:3] if len(name) <= 3 else name


def budget(t):
    if t is None: return 'UNKNOWN'
    return 'UNDER_140K' if t <= 140000 else 'FALLBACK_140_150K' if t <= 150000 else 'STRETCH_150_160K' if t <= 160000 else 'OVER_160K'


def layov(L): return '; '.join(f"{a}:{b}min" for a, b in L) if L else 'NONE'


def cid(*parts): return hashlib.sha1('|'.join(map(str, parts)).encode()).hexdigest()[:12]


def row(**k):
    r = {c: 'UNKNOWN' for c in COLS}; r.update(k); return r


rows = []
# ---- multi-city files (2 adults, single Google price for both legs)
for f in sorted(glob.glob(os.path.join(V2, 'MC*.json'))):
    b = os.path.basename(f); d = json.load(open(f))
    m = re.match(r'MC(?:\d*V?|REV)-([A-Z]{3})-([A-Z+]+)-(\d{4}-\d\d-\d\d)_([A-Z+]+)-([A-Z]{3})-(\d{4}-\d\d-\d\d)', b)
    if not m: continue
    for x in d['res']:
        if len(x['legs']) < 2: continue
        o, r = x['legs'][:2]
        so, sr = o['segs'], r['segs']
        out_arr = D(so[-1][5][:10]); ret_dep = D(sr[0][4][:10]); nights = (ret_dep - out_arr).days
        a_in, a_out = so[-1][3][:3] if False else None, None
        arr_code = None
        # airports are stored as names; derive Japan direction from the query label
        direction = 'TOKYO_FIRST' if (b.startswith('MCREV') or m.group(2).startswith(('HND', 'NRT'))) else ('NAGOYA_FIRST' if m.group(2) == 'NGO' else 'OSAKA_FIRST')
        price = x['total']
        reasons = []
        if price is None: reasons.append('NO_PRICE_RETURNED')
        if not 9 <= nights <= 15: reasons.append(f'NIGHTS_{nights}_OUTSIDE_9_15')
        if nights == 15: reasons.append('15_NIGHTS_ONLY_IF_COMPELLING')
        over = max(o['dur'], r['dur'])
        if over > EXC: reasons.append('OVER_17H55')
        exc = CAP < over <= EXC
        gateway = m.group(1)
        if gateway != 'BLR': reasons.append('GATEWAY_NEEDS_POSITIONING_COST')
        rows.append(row(candidate_id=cid('MC', [g[1] for g in so], [g[1] for g in sr], so[0][4][:10], sr[0][4][:10], gateway), search_timestamp_ist=d['ts'], source='fli_google_flights_multicity',
                        source_query_id=b[:-5], origin=gateway, destination=m.group(2), outbound_date=so[0][4][:10], return_date=sr[0][4][:10], japan_direction=direction, japan_nights=nights,
                        outbound_airlines='/'.join(sorted({g[0] for g in so})), return_airlines='/'.join(sorted({g[0] for g in sr})),
                        outbound_flight_numbers=' '.join(g[0][:2].upper() + g[1] for g in so), return_flight_numbers=' '.join(g[0][:2].upper() + g[1] for g in sr),
                        outbound_stops=o['stops'], return_stops=r['stops'], outbound_duration_min=o['dur'], return_duration_min=r['dur'],
                        outbound_layover_details=layov(o['lay']), return_layover_details=layov(r['lay']), passenger_count=d.get('adults', 2), cabin='ECONOMY',
                        quoted_price_inr=price if price else 'UNKNOWN', quoted_price_basis='PARTY_TOTAL_2_ADULTS_SINGLE_MULTICITY_PRICE',
                        positioning_cost_inr=0 if gateway == 'BLR' else 'UNKNOWN', extra_japan_transport_inr='UNKNOWN', checked_baggage_status='UNVERIFIED',
                        all_in_total_inr='UNKNOWN', price_verification_status='SINGLE_OBSERVATION' , ticket_protection_status='UNVERIFIED_GOOGLE_SELF_TRANSFER_FLAG=' + str(bool(o['self'] or r['self'])),
                        booking_url='UNKNOWN', duration_exception='YES' if exc else 'NO', budget_status=budget(price), qualification_status='REJECTED' if any(z for z in reasons if not z.startswith('15_') and not z.startswith('GATEWAY')) else 'PROVISIONAL',
                        rejection_reason=';'.join(reasons) or 'NONE', evidence_file=os.path.relpath(f, ROOT)))
# ---- one-way files: v2 (2 adults) and v1 (1 adult)
for f in sorted(glob.glob(os.path.join(V2, '*-a[12]-b[0-2].json'))):
    b = os.path.basename(f); d = json.load(open(f)); o_, de_, dt_, ad, bg, cab = d['q']
    for x in d['res']:
        s = x['segs']; price = x['price']
        reasons = [] if price else ['NO_PRICE_RETURNED']
        exc = CAP < x['dur'] <= EXC
        if x['dur'] > EXC: reasons.append('OVER_17H55')
        rows.append(row(candidate_id=cid('OW', [g[1] for g in s], s[0][4][:10]), search_timestamp_ist=d['ts'], source='fli_google_flights_oneway', source_query_id=b[:-5], origin=o_, destination=de_,
                        outbound_date=s[0][4][:10], return_date='NA_ONE_WAY', japan_direction='NA', japan_nights='NA', outbound_airlines='/'.join(sorted({g[0] for g in s})),
                        outbound_flight_numbers=' '.join(g[1] for g in s), outbound_stops=x['stops'], outbound_duration_min=x['dur'], outbound_layover_details=layov(x['lay']),
                        passenger_count=ad, cabin=cab, quoted_price_inr=price if price else 'UNKNOWN', quoted_price_basis=f'PARTY_TOTAL_{ad}_ADULTS_ONE_WAY',
                        checked_baggage_status='UNVERIFIED', price_verification_status='SINGLE_OBSERVATION', ticket_protection_status='SEPARATE_ONE_WAY_NOT_PROTECTED' if True else '',
                        booking_url='UNKNOWN', duration_exception='YES' if exc else 'NO', budget_status='NA_ONE_WAY', qualification_status='LEG_ONLY' if not reasons else 'REJECTED',
                        rejection_reason=';'.join(reasons) or 'LEG_ONLY_NOT_A_COMPLETE_TRIP', evidence_file=os.path.relpath(f, ROOT)))
for f in sorted(glob.glob(os.path.join(RAW, '*.json'))):
    b = os.path.basename(f)
    try: d = json.load(open(f))
    except Exception: continue
    if 'flights' not in d: continue
    q = d['query']; ts = 'v1_sweep_2026-10-31_17:41-17:45_IST'
    for x in d['flights']:
        L = x['legs']; price = x.get('price')
        reasons = [] if price else ['NO_PRICE_RETURNED']
        if x['duration'] > EXC: reasons.append('OVER_17H55')
        rows.append(row(candidate_id=cid('OW', [g['flight_number'] for g in L], L[0]['departure_time'][:10]), search_timestamp_ist=ts, source='fli_cli_oneway_1adult', source_query_id=b[:-5],
                        origin=q['origin'], destination=q['destination'], outbound_date=L[0]['departure_time'][:10], return_date='NA_ONE_WAY', japan_direction='NA', japan_nights='NA',
                        outbound_airlines='/'.join(sorted({g['airline']['code'] for g in L})), outbound_flight_numbers=' '.join(g['airline']['code'] + g['flight_number'] for g in L),
                        outbound_stops=x['stops'], outbound_duration_min=x['duration'], outbound_layover_details='; '.join(f"{v['airport']['code']}:{v['duration']}min" for v in x.get('layovers', [])) or 'NONE',
                        passenger_count=1, cabin=q['cabin_class'], quoted_price_inr=price if price else 'UNKNOWN', quoted_price_basis='PER_ADULT_1_ADULT_QUERY',
                        checked_baggage_status='UNVERIFIED', price_verification_status='SINGLE_OBSERVATION', ticket_protection_status='SEPARATE_ONE_WAY_NOT_PROTECTED', booking_url='UNKNOWN',
                        duration_exception='YES' if CAP < x['duration'] <= EXC else 'NO', budget_status='NA_ONE_WAY', qualification_status='LEG_ONLY' if not reasons else 'REJECTED',
                        rejection_reason=';'.join(reasons) or 'LEG_ONLY_NOT_A_COMPLETE_TRIP', evidence_file=os.path.relpath(f, ROOT)))

# ---- merge with existing CSV (append-only observations)
path = os.path.join(R, 'all_flight_results.csv')
old = []
if os.path.exists(path):
    with open(path, newline='') as fh: old = list(csv.DictReader(fh))
seen = {(r['candidate_id'], r['search_timestamp_ist'], r['source_query_id'], r['quoted_price_inr']) for r in old}
new = [r for r in rows if (r['candidate_id'], r['search_timestamp_ist'], r['source_query_id'], str(r['quoted_price_inr'])) not in seen]
allrows = old + [{k: str(v) for k, v in r.items()} for r in new]

# re-query flag: same candidate seen in >=2 observations at an identical price (still NOT checkout-verified)
obs = collections.defaultdict(list)
for r in allrows: obs[r['candidate_id']].append((r['search_timestamp_ist'], r['quoted_price_inr']))
for r in allrows:
    o_ = sorted(set(obs[r['candidate_id']]))
    if r['source'] == 'fli_google_flights_multicity' and len(o_) >= 2 and len({p for _, p in o_}) == 1 and r['quoted_price_inr'] != 'UNKNOWN':
        r['price_verification_status'] = 'REQUERIED_SAME_PRICE_NOT_CHECKOUT'
    elif r['source'] == 'fli_google_flights_multicity' and len({p for _, p in o_}) > 1:
        r['price_verification_status'] = 'PRICE_CHANGED_BETWEEN_OBSERVATIONS'
# duration-exception savings test: compare exception pair vs best <=16h for same date pair
best_ok = {}
for r in allrows:
    if r['source'] == 'fli_google_flights_multicity' and r['duration_exception'] == 'NO' and r['quoted_price_inr'] != 'UNKNOWN' and r['origin'] == 'BLR':
        k = (r['outbound_date'], r['return_date']); best_ok[k] = min(best_ok.get(k, 1e12), float(r['quoted_price_inr']))
for r in allrows:
    if r['duration_exception'] == 'YES' and r['source'] == 'fli_google_flights_multicity' and r['quoted_price_inr'] != 'UNKNOWN':
        ref = best_ok.get((r['outbound_date'], r['return_date']))
        if ref is None or ref - float(r['quoted_price_inr']) < 15000:
            if 'EXCEPTION_SAVINGS_BELOW_15000' not in r['rejection_reason']:
                r['rejection_reason'] = ('' if r['rejection_reason'] == 'NONE' else r['rejection_reason'] + ';') + 'EXCEPTION_SAVINGS_BELOW_15000'
            r['qualification_status'] = 'REJECTED'

def atomic(p, rows_, cols):
    tmp = p + '.tmp'
    with open(tmp, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows_)
    os.replace(tmp, p)

atomic(path, allrows, COLS)
trips = [r for r in allrows if r['source'] == 'fli_google_flights_multicity' and r['quoted_price_inr'] != 'UNKNOWN' and r['qualification_status'] == 'PROVISIONAL' and r['origin'] == 'BLR']
trips.sort(key=lambda r: float(r['quoted_price_inr']))
qual = [r for r in trips if r['checked_baggage_status'] == 'VERIFIED' and r['price_verification_status'] == 'VERIFIED']   # none until bags + price verified
atomic(os.path.join(R, 'qualified_flights.csv'), qual, COLS)
seen_i = set(); best = []
for r in trips:
    k = (r['outbound_flight_numbers'], r['return_flight_numbers'], r['outbound_date'], r['return_date'])
    if k in seen_i: continue
    seen_i.add(k); best.append(r)
    if len(best) >= 30: break
atomic(os.path.join(R, 'best_flights.csv'), best, COLS)

qlog = os.path.join(V2, '_queries.log')
ok = fail = 0
if os.path.exists(qlog):
    for l in open(qlog):
        ok += ' OK ' in l; fail += ' FAIL ' in l
mc_files = len(glob.glob(os.path.join(V2, 'MC*.json'))); ow_files = len(glob.glob(os.path.join(V2, '*-a[12]-b[0-2].json'))); v1 = len([1 for f in glob.glob(os.path.join(RAW, '*.json'))])
prog = {'updated_ist': dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'rows_total': len(allrows), 'rows_new_this_run': len(new), 'multicity_query_files': mc_files, 'oneway_2adult_query_files': ow_files,
        'oneway_1adult_query_files_v1': v1, 'logged_ok_since_logging_started': ok, 'logged_fail': fail, 'provisional_complete_trips': len(trips), 'distinct_provisional_trips': len(seen_i) if False else len({(r['outbound_flight_numbers'], r['return_flight_numbers'], r['outbound_date'], r['return_date']) for r in trips}),
        'under_140k_provisional': sum(1 for r in trips if float(r['quoted_price_inr']) <= 140000), 'qualified_verified': len(qual), 'baggage_confirmed': 0,
        'lowest_provisional_total_inr': float(trips[0]['quoted_price_inr']) if trips else None}
tmp = os.path.join(R, 'search_progress.json.tmp'); json.dump(prog, open(tmp, 'w'), indent=1); os.replace(tmp, os.path.join(R, 'search_progress.json'))
print(json.dumps(prog, indent=1))
