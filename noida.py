"""Noida family stopover + Holi + Japan: offline combiner over cached Fli one-way results (2 adults).
Usage: .venv/bin/python noida.py   -> results/noida_domestic_flights.csv, delhi_osaka_nonstop.csv, noida_japan_all_options.csv
Every combination is SEPARATE TICKETS. Baggage, home transfers and checkout totals are UNKNOWN (never zero)."""
import csv, datetime as dt, glob, json, os, itertools, sys
ROOT = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(ROOT, 'results'); V2 = os.path.join(R, 'raw', 'v2')
T = dt.datetime.fromisoformat; D = dt.date
HOLI_DAYS = (D(2027, 3, 22), D(2027, 3, 23))
EXC = 1075

def load(pat):
    out = {}
    for f in glob.glob(os.path.join(V2, pat)):
        d = json.load(open(f)); q = d['q']; out[(q[0], q[1], q[2])] = (d, os.path.basename(f))
    return out

def info(x):
    s = x['segs']
    return dict(price=x['price'], dur=x['dur'], stops=x['stops'], dep=T(s[0][4]), arr=T(s[-1][5]), fl=' + '.join(g[0][:10] + ' ' + g[1] for g in s),
                path='>'.join([s[0][2][:3]] + [g[3][:3] for g in s]), lay='; '.join(f"{a[:3]}:{b}m" for a, b in x['lay']) or 'NONE', airlines=sorted({g[0] for g in s}), nums=[g[1] for g in s])

def wk_weekday(d): return d.weekday() < 5

def write(path, rows, cols):
    old = list(csv.DictReader(open(path, newline=''))) if os.path.exists(path) else []
    seen = {tuple(o[c] for c in cols) for o in old}; out = list(old)
    for r in rows:
        t = {c: str(r.get(c, 'UNKNOWN')) for c in cols}
        if tuple(t[c] for c in cols) not in seen: out.append(t); seen.add(tuple(t[c] for c in cols))
    tmp = path + '.tmp'
    with open(tmp, 'w', newline='') as fh: w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(out)
    os.replace(tmp, path); return len(out)

# ---------- domestic
dom = load('BLR-*-a2-b1.json'); dom_rows = []; best_dom = {}; best_any = {}
for (o, dst, dte), (d, fn) in sorted(dom.items()):
    if dst not in ('DEL', 'HDO', 'DXN') or not '2027-03-18' <= dte <= '2027-03-22': continue
    if not d['res']: continue
    for x in d['res']:
        i = info(x)
        if not i['price']: continue
        dom_rows.append(dict(source='fli_google_flights_oneway_adults2', timestamp=d['ts'], query=f'{o}>{dst} {dte} 2 adults economy', date=dte, origin=o, airport=dst, airline='/'.join(i['airlines']), flight_numbers=i['fl'],
            departure=i['dep'].strftime('%a %d %b %H:%M'), arrival=i['arr'].strftime('%a %d %b %H:%M'), stops=i['stops'], duration_min=i['dur'], connection=i['lay'], price_for_2_inr=int(i['price']),
            checked_baggage='UNVERIFIED', extra_bag_cost='UNKNOWN', home_airport_transfer_cost='UNKNOWN', noida_home_transfer_cost='UNKNOWN', verification_status='SINGLE_OBSERVATION_NOT_CHECKOUT', booking_url='UNKNOWN', evidence_file=os.path.relpath(os.path.join(V2, fn), ROOT)))
        k = (dst, dte)
        eve = dte in ('2027-03-18', '2027-03-19')       # weekday: prefer after-office departures
        if i['dur'] <= 600 and (k not in best_any or best_any[k]['price'] > i['price']): best_any[k] = i
        if i['dur'] <= 600 and (not eve or i['dep'].hour >= 17) and (k not in best_dom or best_dom[k]['price'] > i['price']): best_dom[k] = i
DCOLS = ['source', 'timestamp', 'query', 'date', 'origin', 'airport', 'airline', 'flight_numbers', 'departure', 'arrival', 'stops', 'duration_min', 'connection', 'price_for_2_inr', 'checked_baggage', 'extra_bag_cost',
         'home_airport_transfer_cost', 'noida_home_transfer_cost', 'verification_status', 'booking_url', 'evidence_file']
nd = write(os.path.join(R, 'noida_domestic_flights.csv'), dom_rows, DCOLS)

# ---------- AI360 / DEL->KIX
dk = load('DEL-KIX-*-a2-b1.json'); ai_rows = []; out_opt = {}
for (o, dst, dte), (d, fn) in sorted(dk.items()):
    items = [info(x) for x in d['res']]
    priced = sorted([i for i in items if i['price'] and i['dur'] <= EXC], key=lambda i: i['price'])
    ai = [i for i in items if '360' in i['nums'] and any(a in ('AI', 'Air India') for a in i['airlines'])]
    if priced: out_opt.setdefault(dte, {})['cheapest'] = priced[0]
    for i in ai:
        out_opt.setdefault(dte, {})['ai360'] = i if (i['price'] or 'ai360' not in out_opt.get(dte, {})) else out_opt[dte]['ai360']
    for tag, i in [('AI360', j) for j in ai] + [('best_alternative', priced[0])] if priced else [('AI360', j) for j in ai]:
        ai_rows.append(dict(source='fli_google_flights_oneway_adults2', timestamp=d['ts'], query=f'DEL>KIX {dte} 2 adults economy', date=dte, weekday=D.fromisoformat(dte).strftime('%A'), tag=tag, airline='/'.join(i['airlines']),
            flight_numbers=i['fl'], path=i['path'], departure=i['dep'].strftime('%a %d %b %H:%M'), arrival_local=i['arr'].strftime('%a %d %b %H:%M'), elapsed_hours=round(i['dur'] / 60, 2), connection=i['lay'],
            fare_for_2_inr=int(i['price']) if i['price'] else 'UNPRICED_BY_SOURCE', checked_baggage='UNVERIFIED', evidence_status='SINGLE_OBSERVATION_NOT_CHECKOUT; AI inventory per Google; Air India official site not queried', booking_url='UNKNOWN', evidence_file=os.path.relpath(os.path.join(V2, fn), ROOT)))
ACOLS = ['source', 'timestamp', 'query', 'date', 'weekday', 'tag', 'airline', 'flight_numbers', 'path', 'departure', 'arrival_local', 'elapsed_hours', 'connection', 'fare_for_2_inr', 'checked_baggage', 'evidence_status', 'booking_url', 'evidence_file']
na = write(os.path.join(R, 'delhi_osaka_nonstop.csv'), ai_rows, ACOLS)

# ---------- returns (HND/NRT -> BLR, <=16h, cheapest priced; plus fastest nonstop priced)
ret = {}
for ap in ('HND', 'NRT'):
    for (o, dst, dte), (d, fn) in load(f'{ap}-BLR-2027-04-*-a2-b1.json').items():
        for x in d['res']:
            i = info(x)
            if not i['price'] or i['dur'] > 960: continue
            i['ap'] = ap; i['ts'] = d['ts']
            cur = ret.setdefault(dte, {})
            if 'cheap' not in cur or i['price'] < cur['cheap']['price'] or (i['price'] == cur['cheap']['price'] and i['dur'] < cur['cheap']['dur']): cur['cheap'] = i
            if i['stops'] == 0 and ('nonstop' not in cur or i['price'] < cur['nonstop']['price']): cur['nonstop'] = i

# ---------- combos
def leave_s1(start_dt, end_dt):
    n = 0; d = start_dt.date()
    while d <= end_dt.date():
        if wk_weekday(d) and not (d == start_dt.date() and start_dt.hour >= 20): n += 1
        d += dt.timedelta(1)
    return n

rows = []
for k in best_any:
    best_dom.setdefault(k, dict(best_any[k], fallback_daytime=True))
for (dst, ddate), dm in sorted(best_dom.items()):
    for adate, ao in sorted(out_opt.items()):
      for otag, o in (('AI360', ao.get('ai360')), ('cheapest_alt', ao.get('cheapest'))):
        if not o or not o['price']: continue
        if otag == 'cheapest_alt' and ao.get('ai360') is not None and o is ao.get('ai360'): continue
        ad = D.fromisoformat(adate); dom_arr = dm['arr'].date()
        if ad < dom_arr: continue
        intl_dep = o['dep']; kix_arr = o['arr']
        for rdate, ro in sorted(ret.items()):
            r = ro['cheap']; rd = D.fromisoformat(rdate)
            if not (kix_arr.date() < rd): continue
            nights = (rd - kix_arr.date()).days
            if not 8 <= nights <= 12: continue
            home = r['arr']; fam_n = (ad - dom_arr).days
            fam_days = max(fam_n - 1, 0) + (0.5 if dm['arr'].hour <= 14 else 0) + 0.5
            holi = 'both Holi days with parents' if (dom_arr <= HOLI_DAYS[0] and ad > HOLI_DAYS[1]) else ('Holika Dahan + Holi until ~17:20 departure to airport' if (dom_arr <= HOLI_DAYS[0] and ad == HOLI_DAYS[1]) else 'Holi not with parents')
            s1 = leave_s1(dm['dep'], home)
            # scenario 2: remote from Noida on weekdays; leave only for travel day (if before 17:00) and Japan stage (from KIX arrival date to home arrival date)
            s2 = (1 if (wk_weekday(dm['dep'].date()) and dm['dep'].hour < 12) else 0.5 if (wk_weekday(dm['dep'].date()) and dm['dep'].hour < 17) else 0)
            d = kix_arr.date()
            while d <= home.date():
                if wk_weekday(d): s2 += 1
                d += dt.timedelta(1)
            s3 = s1 - (0.5 if wk_weekday(dm['dep'].date()) and dm['dep'].hour >= 15 and not dm['dep'].hour >= 20 else 0) - (0.5 if wk_weekday(intl_dep.date()) else 0)
            total = int(dm['price'] + o['price'] + r['price'])
            leave_home_by = (intl_dep - dt.timedelta(hours=3, minutes=30 + 60 + 60)).strftime('%H:%M')
            rows.append(dict(source='composed_from_cached_fli_oneways_adults2', timestamp_domestic=dm.get('ts', ''), bl_to=dst, domestic_date=ddate, domestic_flight=dm['fl'] + (' [DAYTIME fallback: no after-17:00 option found]' if dm.get('fallback_daytime') and ddate in ('2027-03-18','2027-03-19') and dm['dep'].hour < 17 else ''), domestic_dep=dm['dep'].strftime('%a %d %b %H:%M'), domestic_arr=dm['arr'].strftime('%a %d %b %H:%M'),
                domestic_price_2=int(dm['price']), noida_nights=fam_n, family_days=fam_days, holi=holi, intl_date=adate, intl_flight=o['fl'], intl_path=o['path'], intl_dep=intl_dep.strftime('%a %d %b %H:%M'), japan_arr=kix_arr.strftime('%a %d %b %H:%M'),
                intl_elapsed_h=round(o['dur'] / 60, 2), intl_price_2=int(o['price']), intl_is_ai360='YES' if otag == 'AI360' else 'NO (cheapest alternative)', leave_home_by_for_intl=leave_home_by + ' (assumes 3h30 reporting + 1h road + 1h Holi/traffic buffer; unverified)',
                return_date=rdate, return_airport=r['ap'], return_flight=r['fl'], return_dep=r['dep'].strftime('%a %d %b %H:%M'), home_arrival=home.strftime('%a %d %b %H:%M'), return_elapsed_h=round(r['dur'] / 60, 2), return_stops=r['stops'], return_price_2=int(r['price']),
                japan_hotel_nights=nights, calendar_days_away_from_blr=(home.date() - dm['dep'].date()).days + 1, leave_s1_office=s1, leave_s2_remote=s2, leave_s3_half_days=s3,
                baggage_cost='UNKNOWN', home_transfers_cost='UNKNOWN', total_flights_lower_bound_inr=total, ticketing='THREE SEPARATE TICKETS (domestic, outbound, return); no protection',
                qualification='PROVISIONAL', booking_url='UNKNOWN'))
OCOLS = list(rows[0].keys()) if rows else ['none']
no = write(os.path.join(R, 'noida_japan_all_options.csv'), rows, OCOLS) if rows else 0
json.dump([{k: str(v) for k, v in r.items()} for r in rows], open('/tmp/fs/noida_rows.json', 'w'))
print('domestic rows', nd, 'ai360/outbound rows', na, 'combo rows', len(rows), 'csv', no, '| outbound dates', sorted(out_opt), '| return dates', sorted(ret), '| domestic keys', sorted(best_dom))
