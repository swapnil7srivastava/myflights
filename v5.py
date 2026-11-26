"""V5: 2027 season/date/leave engine over ALL cached Fli multi-city results (BLR origin, 2 adults, INR).
Usage: .venv/bin/python v5.py  -> results/2027_all_date_combinations.csv (append-only), 2027_seasonal_shortlist.csv, 2027_sakura_comparison.csv,
2027_leave_comparison.csv, 2027_future_inventory_dates.csv, 2027_search_progress.json. Offline only.
Bloom model (NOT a forecast): user-supplied long-term full-bloom averages Tokyo 31 Mar, Kansai 4 Apr; early = -7 d, late = +7 d.
Leave: Sat/Sun off. A = weekends-only (all weekdays away). B = A minus tentative public holidays. C = confirmed employer holidays: NOT PROVIDED (= A)."""
import csv, datetime as dt, glob, hashlib, json, os, re, collections
ROOT = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(ROOT, 'results')
T = dt.datetime.fromisoformat; D = dt.date
HOL = {D(2027, 1, 26): 'Republic Day', D(2027, 3, 23): 'Holi', D(2027, 3, 26): 'Good Friday', D(2027, 4, 7): 'Ugadi (tentative; some sources say 8 Apr)', D(2027, 4, 19): 'Mahavir Jayanti', D(2027, 10, 29): 'Diwali', D(2027, 11, 1): 'Kannada Rajyotsava (employer applicability unconfirmed)'}
CAP, EXC = 960, 1075
VERIFIED = {  # exact itineraries whose fare details were read on Google's booking screen (Playwright, 2 adults) -> LEVEL 3
    ('754 213', '753', '2027-03-23', '2027-04-02'): 'LEVEL 3', ('754 229', '753', '2027-03-29', '2027-04-07'): 'LEVEL 3'}

def season_group(d):
    if D(2027, 1, 18) <= d <= D(2027, 1, 27): return 'B_ANNIVERSARY_WINTER'
    if D(2027, 2, 24) <= d <= D(2027, 3, 14): return 'C_BIRTHDAY_EARLY_SPRING'
    if D(2027, 3, 15) <= d <= D(2027, 3, 21): return 'A0_PRE_SAKURA'
    if D(2027, 3, 22) <= d <= D(2027, 3, 31): return 'A_SAKURA'
    if D(2027, 4, 1) <= d <= D(2027, 4, 12): return 'A_LATE_SAKURA'
    if D(2027, 4, 13) <= d <= D(2027, 4, 28): return 'D_APRIL_GREEN'
    if D(2027, 4, 29) <= d <= D(2027, 5, 5): return 'D_GOLDEN_WEEK'
    if D(2027, 5, 6) <= d <= D(2027, 5, 31): return 'D_MAY'
    if d.month in (10, 11): return 'E_AUTUMN'
    return 'OTHER'

def bloom(city, day, shift):
    fb = (D(2027, 3, 31) if city == 'Tokyo' else D(2027, 4, 4)) + dt.timedelta(shift)
    k = (day - fb).days
    return 1.0 if -3 <= k <= 5 else 0.5 if (-8 <= k < -3 or 5 < k <= 10) else 0.0

def sakura(arr, nights, first):
    k = max(round(nights * 0.5), 1); days = [arr + dt.timedelta(i) for i in range(nights + 1)]; out = {}
    for tag, sh in (('early', -7), ('average', 0), ('late', 7)):
        ks, ts_ = [], []
        for i, d in enumerate(days):
            c = ('Tokyo' if i < k else 'Kansai') if first == 'Tokyo' else ('Kansai' if i < k else 'Tokyo')
            (ts_ if c == 'Tokyo' else ks).append(bloom(c, d, sh))
        out[tag] = (5 * sum(ks + ts_) / len(days), 5 * (sum(ks) / len(ks) if ks else 0), 5 * (sum(ts_) / len(ts_) if ts_ else 0))
    allr = [out[t][0] for t in out]; bal = min(sum(out[t][1] for t in out) / 3, sum(out[t][2] for t in out) / 3)
    return dict(sakura_early=round(out['early'][0], 1), sakura_average=round(out['average'][0], 1), sakura_late=round(out['late'][0], 1), sakura_overall=round(sum(allr) / 3, 1), sakura_min_city_balance=round(bal, 1))

def leave(dep, home):
    miss, d = [], dep.date()
    while d <= home.date():
        if d.weekday() < 5 and not (d == dep.date() and dep.hour >= 20): miss.append(d)
        d += dt.timedelta(1)
    hol = [d for d in miss if d in HOL]
    return len(miss), len(miss) - len(hol), '; '.join(f"{d:%d %b} {HOL[d]}" for d in hol) or 'none'

obs = []  # one observation per itinerary per query file
for f in sorted(glob.glob(os.path.join(R, 'raw', 'v2', 'MC*.json')) + glob.glob(os.path.join(R, 'raw', 'v4', 'MC-BLR-*.json'))):
    b = os.path.basename(f)
    if not (re.match(r'(MC\d*V?-BLR|MCREV-BLR)', b)): continue
    try: d = json.load(open(f))
    except Exception: continue
    for x in d['res']:
        if not x.get('total') or len(x['legs']) < 2: continue
        o, r = x['legs'][:2]; so, sr = o['segs'], r['segs']
        dep, arr, rdp, home = T(so[0][4]), T(so[-1][5]), T(sr[0][4]), T(sr[-1][5])
        a_ap, d_ap = so[-1][3][:3], sr[0][2][:3]
        direction = 'OSAKA_FIRST' if (a_ap == 'KIX' and d_ap in ('HND', 'NRT')) else 'TOKYO_FIRST' if (a_ap in ('HND', 'NRT') and d_ap == 'KIX') else f'{a_ap}>{d_ap}'
        if direction not in ('OSAKA_FIRST', 'TOKYO_FIRST'): continue
        chg = any(so[i][3][:3] != so[i + 1][2][:3] for i in range(len(so) - 1)) or any(sr[i][3][:3] != sr[i + 1][2][:3] for i in range(len(sr) - 1))
        obs.append(dict(dep=dep, arr=arr, rdp=rdp, home=home, direction=direction, chg=chg, total=int(x['total']), o=o, r=r, ts=d['ts'], file=os.path.relpath(f, ROOT),
                        out_fl=' '.join(g[1] for g in so), ret_fl=' '.join(g[1] for g in sr), airlines='/'.join(sorted({g[0][:2] for g in so + sr})),
                        out_path='>'.join([so[0][2][:3]] + [g[3][:3] for g in so]), ret_path='>'.join([sr[0][2][:3]] + [g[3][:3] for g in sr]),
                        lay_out='; '.join(f"{a[:3]}:{m}m" for a, m in o['lay']) or 'NONE', lay_ret='; '.join(f"{a[:3]}:{m}m" for a, m in r['lay']) or 'NONE'))

def cid(v): return hashlib.sha1(f"{v['direction']}|{v['out_fl']}|{v['ret_fl']}|{v['dep']:%Y-%m-%d}|{v['rdp']:%Y-%m-%d}".encode()).hexdigest()[:12]
rows = []
for v in obs:
    if max(v['o']['dur'], v['r']['dur']) > EXC: continue
    nights = (v['rdp'].date() - v['arr'].date()).days; cd = (v['home'].date() - v['dep'].date()).days + 1
    la, lb, lh = leave(v['dep'], v['home'])
    first = 'Kansai' if v['direction'] == 'OSAKA_FIRST' else 'Tokyo'
    sk = sakura(v['arr'].date(), nights, 'Tokyo' if first == 'Tokyo' else 'Kansai') if season_group(v['dep'].date()).startswith(('A', 'D_APRIL')) else {}
    dur_flag = 'OK<=16h' if max(v['o']['dur'], v['r']['dur']) <= CAP else 'EXCEPTION_16h-17h55'
    key = (v['out_fl'], v['ret_fl'], v['dep'].strftime('%Y-%m-%d'), v['rdp'].strftime('%Y-%m-%d'))
    lvl = VERIFIED.get(key, 'LEVEL 2' if v['ts'] >= '2026-10-31 17:00' else 'LEVEL 1')
    rows.append(dict(candidate_id=cid(v), observed_ist=v['ts'], source='fli_google_flights_multicity_adults2', evidence_file=v['file'], group=season_group(v['dep'].date()), direction=v['direction'],
        india_departure=v['dep'].strftime('%a %Y-%m-%d %H:%M'), japan_arrival=v['arr'].strftime('%a %Y-%m-%d %H:%M'), japan_departure=v['rdp'].strftime('%a %Y-%m-%d %H:%M'), india_home_arrival=v['home'].strftime('%a %Y-%m-%d %H:%M'),
        japan_hotel_nights=nights, india_calendar_days=cd, leave_A_weekends_only=la, leave_B_public_holidays=lb, leave_C_employer_confirmed='NOT PROVIDED', holidays_in_window=lh,
        airlines=v['airlines'], outbound_flights=v['out_fl'], return_flights=v['ret_fl'], outbound_path=v['out_path'], return_path=v['ret_path'], layovers_out=v['lay_out'], layovers_return=v['lay_ret'],
        out_hours=round(v['o']['dur'] / 60, 2), return_hours=round(v['r']['dur'] / 60, 2), duration_flag=dur_flag, airport_change='YES' if v['chg'] else 'NO', price_for_2_inr=v['total'],
        checked_baggage='LEVEL 3 only: see final_live_prices.csv' if lvl == 'LEVEL 3' else 'UNVERIFIED', ticketing='UNVERIFIED', verification_level=lvl,
        qualification='PROVISIONAL', rejection_reason='NONE' if 8 <= nights <= 13 and cd <= 14 else f'nights={nights}/calendar_days={cd} outside preferred range', **{k: sk.get(k, 'NA') for k in ('sakura_early', 'sakura_average', 'sakura_late', 'sakura_overall', 'sakura_min_city_balance')}))

COLS = list(rows[0].keys())
path = os.path.join(R, '2027_all_date_combinations.csv'); old = list(csv.DictReader(open(path, newline=''))) if os.path.exists(path) else []
seen = {(o['candidate_id'], o['observed_ist'], o['price_for_2_inr']) for o in old}; out = list(old); new = 0
for r in rows:
    k = (r['candidate_id'], r['observed_ist'], str(r['price_for_2_inr']))
    if k not in seen: out.append({c: str(r[c]) for c in COLS}); seen.add(k); new += 1
tmp = path + '.tmp'
with open(tmp, 'w', newline='') as fh: w = csv.DictWriter(fh, fieldnames=COLS); w.writeheader(); w.writerows(out)
os.replace(tmp, path)

def wr(name, rs):
    if not rs: return 0
    p = os.path.join(R, name); tmp = p + '.tmp'
    with open(tmp, 'w', newline='') as fh: w = csv.DictWriter(fh, fieldnames=list(rs[0].keys())); w.writeheader(); w.writerows(rs)
    os.replace(tmp, p); return len(rs)

def best_latest(rs):  # latest observation per candidate
    d = {}
    for r in rs:
        if r['candidate_id'] not in d or r['observed_ist'] > d[r['candidate_id']]['observed_ist']: d[r['candidate_id']] = r
    return list(d.values())

cur = best_latest([{c: str(r[c]) for c in COLS} for r in rows])
valid = [r for r in cur if 8 <= int(r['japan_hotel_nights']) <= 12 and int(r['india_calendar_days']) <= 14]
def price(r): return int(r['price_for_2_inr'])
sak = [r for r in valid if r['group'] in ('A_SAKURA', 'A_LATE_SAKURA', 'A0_PRE_SAKURA') and r['sakura_overall'] != 'NA']
sak.sort(key=lambda r: (price(r) > 160000, -float(r['sakura_overall']), price(r)))
sk_cols = ['candidate_id', 'direction', 'india_departure', 'india_home_arrival', 'japan_hotel_nights', 'india_calendar_days', 'airlines', 'outbound_flights', 'return_flights', 'airport_change', 'out_hours', 'return_hours', 'price_for_2_inr',
           'sakura_early', 'sakura_average', 'sakura_late', 'sakura_overall', 'sakura_min_city_balance', 'leave_A_weekends_only', 'leave_B_public_holidays', 'verification_level']
n1 = wr('2027_sakura_comparison.csv', [{c: r[c] for c in sk_cols} for r in sak[:120]])
lv_cols = ['candidate_id', 'group', 'direction', 'india_departure', 'india_home_arrival', 'japan_hotel_nights', 'india_calendar_days', 'leave_A_weekends_only', 'leave_B_public_holidays', 'leave_C_employer_confirmed', 'holidays_in_window', 'price_for_2_inr', 'verification_level']
lv = sorted(valid, key=lambda r: (int(r['leave_B_public_holidays']), price(r)))
n2 = wr('2027_leave_comparison.csv', [{c: r[c] for c in lv_cols} for r in lv[:200]])
# shortlist: best per group (<=16h, valid nights)
sl = []
for g in sorted({r['group'] for r in valid}):
    pool = sorted([r for r in valid if r['group'] == g and r['duration_flag'] == 'OK<=16h'], key=price)[:3]
    for r in pool: sl.append({'group': g, **{c: r[c] for c in ('direction', 'india_departure', 'india_home_arrival', 'japan_hotel_nights', 'india_calendar_days', 'airlines', 'outbound_flights', 'return_flights', 'airport_change', 'out_hours', 'return_hours', 'price_for_2_inr', 'leave_A_weekends_only', 'leave_B_public_holidays', 'verification_level', 'observed_ist')}})
n3 = wr('2027_seasonal_shortlist.csv', sl)
# future inventory checklist (user-supplied booking windows; NOT verified by me)
today = D(2026, 11, 1); fut = []
for o, r, label in [('2027-10-29', '2027-11-07', 'Oct29-Nov7 (Diwali/Rajyotsava, early autumn)'), ('2027-10-30', '2027-11-08', 'Oct30-Nov8'), ('2027-11-19', '2027-11-28', 'Nov19-28 (late-Nov foliage)'), ('2027-11-20', '2027-11-29', 'Nov20-29'), ('2027-11-21', '2027-11-30', 'Nov21-30')]:
    last = D.fromisoformat(r); home = last + dt.timedelta(1)
    for al, days in (('JAL (user-supplied rule: 360 days)', 360), ('ANA (user-supplied rule: 355 days)', 355)):
        rel = last - dt.timedelta(days)
        fut.append({'window': label, 'outbound': o, 'return_departure_japan': r, 'airline_rule': al, 'last_flight_date': last.isoformat(), 'expected_release_date': rel.isoformat(),
                    'status_on_2026-11-01': 'RELEASED' if rel <= today else 'NOT YET RELEASED', 'days_until_release': max((rel - today).days, 0), 'price': 'NOT AVAILABLE - do not infer', 'note': 'rule not verified by me; Fli probes of 23 Oct->30 Oct and 13 Nov->20 Nov 2027 returned zero itineraries on 31 Oct 2026 (consistent with not released)'})
n4 = wr('2027_future_inventory_dates.csv', fut)
print('observations', len(obs), 'rows kept', len(rows), 'new appended', new, 'csv rows', len(out), '| sakura', n1, 'leave', n2, 'shortlist', n3, 'future', n4, '| valid current candidates', len(valid))
json.dump([{k: v for k, v in r.items()} for r in cur], open('/tmp/fs/v5_cur.json', 'w'))
