"""Trip-date + office-leave engine. Reads cached multi-city results (results/raw/v2/MC*-BLR*.json) -> results/best_trip_dates.csv.
Usage: .venv/bin/python trips.py
Assumptions (documented, adjustable):
- Sat/Sun are days off. Employer holiday calendars are NOT known, so confirmed_company_holidays = 0 (NOT_PROVIDED).
- Departure before 06:00 -> leaves home the previous evening after work (start_date = previous day, that day counts as worked).
  Departure 06:00-19:59 on a weekday -> that weekday is leave. Departure >=20:00 -> that day is worked.
- Arrival on a weekday = leave day (travel/recovery). Arrival on Sat/Sun = no leave.
- japan_sightseeing_days = (nights-1 full days) + 0.5 if Japan arrival <=14:00 + 0.5 if Japan departure >=15:00.
- Tentative public holidays (web search 2026-10-31, NOT employer-confirmed): 2027-03-26 Good Friday, 2027-04-08 Ugadi (sources disagree on 7/8),
  2027-04-14 Ambedkar Jayanti. Golden Week (Japan) 2027-04-29..05-05 flagged as peak crowds/prices."""
import csv, datetime as dt, glob, json, os, re, collections

ROOT = os.path.dirname(os.path.abspath(__file__)); R = os.path.join(ROOT, 'results'); V2 = os.path.join(R, 'raw', 'v2')
CAP, EXC = 960, 1075
D = dt.date.fromisoformat; T = dt.datetime.fromisoformat
HOL = {dt.date(2027, 3, 26): 'Good Friday', dt.date(2027, 4, 8): 'Ugadi (date disputed 7/8 Apr)', dt.date(2027, 4, 14): 'Ambedkar Jayanti'}


def season(d):
    m, day = d.month, d.day
    if (m, day) < (3, 1): return ('winter', 1, 'cold, off-season')
    if (m, day) <= (3, 14): return ('late winter / plum', 2, 'cold (roughly 3-12C), cherry buds not open')
    if (m, day) <= (3, 24): return ('early spring', 3, 'cool, early cherry possible in Tokyo late in window')
    if (m, day) <= (4, 8): return ('SAKURA PEAK (typical)', 5, 'mild; 30-yr full-bloom avg Tokyo ~3 Apr, Kyoto ~4 Apr, Osaka ~5 Apr; +/-1 week yearly')
    if (m, day) <= (4, 15): return ('late sakura / petal fall', 3.5, 'mild; Tokyo/Osaka often past peak; Tohoku/Hokkaido later')
    if (m, day) <= (4, 28): return ('fresh green (post-sakura)', 3, 'mild, pleasant')
    if (m, day) <= (5, 5): return ('GOLDEN WEEK', 1.5, 'mild; peak crowds and prices (29 Apr-5 May)')
    if (m, day) <= (5, 31): return ('late spring / pre-rainy', 3.5, 'warm, fresh green; rainy season usually starts June')
    if m in (10, 11): return ('autumn foliage', 5 if (m == 11 and day >= 10) or (m == 10 and day >= 25) else 3.5, 'cool; Kyoto foliage peaks late Nov (typical)')
    return ('other', 2.5, 'not assessed')


def crowd(d):
    s = season(d)[0]
    return 'very high' if s.startswith(('SAKURA', 'GOLDEN')) else 'high' if s.startswith(('autumn', 'late sakura')) else 'moderate' if s.startswith(('early', 'fresh', 'late spring')) else 'low'


def leave(start_dt, end_dt):
    """Calendar days = India departure DATE .. India arrival DATE inclusive (actual flight dates, local times).
    A pre-dawn departure still counts its own date; the evening before is a worked day (not counted).
    returns (start_date,end_date,days,weekend_days,weekdays_missed(list))"""
    start, end = start_dt.date(), end_dt.date()
    wk = 0; miss = []
    d = start
    while d <= end:
        if d.weekday() >= 5: wk += 1
        elif d == start and start_dt.hour >= 20: pass          # evening departure after a full working day
        else: miss.append(d)
        d += dt.timedelta(1)
    return start, end, (end - start).days + 1, wk, miss


def sight_days(arr_dt, dep_dt, nights):
    full = max(nights - 1, 0)
    return full + (0.5 if arr_dt.hour <= 14 else 0) + (0.5 if dep_dt.hour >= 15 else 0)


rows = {}
for f in glob.glob(os.path.join(V2, 'MC*.json')):
    b = os.path.basename(f)
    if not re.match(r'(MC\d*V?-BLR|MCREV)', b): continue
    d = json.load(open(f))
    for x in d['res']:
        if not x['total'] or len(x['legs']) < 2: continue
        o, r = x['legs'][:2]
        if max(o['dur'], r['dur']) > EXC: continue
        so, sr = o['segs'], r['segs']
        o_dep, o_arr, r_dep, r_arr = T(so[0][4]), T(so[-1][5]), T(sr[0][4]), T(sr[-1][5])
        start, end, days, wk, miss = leave(o_dep, r_arr)
        nights = (r_dep.date() - o_arr.date()).days
        tent = [m for m in miss if m in HOL]
        leave_min = len(miss) - len(tent)
        key = (tuple(g[1] for g in so), tuple(g[1] for g in sr), o_dep.date(), r_dep.date())
        s = season(o_arr.date())
        row = dict(start_date=start, end_date=end, calendar_days=days, japan_nights=nights, japan_sightseeing_days=sight_days(o_arr, r_dep, nights), season=s[0], seasonal_rating=s[1], weather_assessment=s[2],
                   weekend_days=wk, confirmed_company_holidays='0 (employer calendars NOT PROVIDED)', tentative_public_holidays='; '.join(f"{m} {HOL[m]}" for m in tent) or 'none',
                   leave_days_person1=leave_min, leave_days_person2=leave_min, leave_days_weekends_only=len(miss), total_flight_cost_2adults_inr=int(x['total']),
                   baggage_status='UNVERIFIED', flight_duration_out=f"{o['dur']//60}h{o['dur']%60:02d}", flight_duration_back=f"{r['dur']//60}h{r['dur']%60:02d}",
                   cash_vs_miles_verdict='use cash; save MR for Taj (no verified award)', qualification_status='PROVISIONAL' + (' DURATION_EXCEPTION' if max(o['dur'], r['dur']) > CAP else ''),
                   source_timestamp=d['ts'], _route=f"{'/'.join(sorted({g[0][:2].upper() for g in so}))} {' '.join(g[1] for g in so)} | {' '.join(g[1] for g in sr)}",
                   _dir='TOKYO_FIRST' if b.startswith('MCREV') else 'OSAKA_FIRST', _out=f"{o_dep:%a %d %b %H:%M}->{o_arr:%H:%M}", _ret=f"{r_dep:%a %d %b %H:%M}->{r_arr:%a %d %b %H:%M}",
                   _crowd=crowd(o_arr.date()), _month=o_arr.date().strftime('%Y-%m'))
        if key not in rows or rows[key]['total_flight_cost_2adults_inr'] > row['total_flight_cost_2adults_inr']: rows[key] = row

cands = [r for r in rows.values() if 9 <= r['calendar_days'] <= 12]


def bucket(p): return 0 if p <= 140000 else 1 if p <= 150000 else 2 if p <= 160000 else 3


def rank_key(r):
    cd = r['calendar_days']; pen = 0 if cd in (10, 11) else 1   # 9 / 12 are 'exceptional' options
    return (pen, bucket(r['total_flight_cost_2adults_inr']), -r['seasonal_rating'], r['leave_days_person1'], r['total_flight_cost_2adults_inr'], -r['japan_sightseeing_days'])


cands.sort(key=rank_key)
COLS = ['start_date', 'end_date', 'calendar_days', 'japan_nights', 'japan_sightseeing_days', 'season', 'seasonal_rating', 'weather_assessment', 'weekend_days', 'confirmed_company_holidays',
        'tentative_public_holidays', 'leave_days_person1', 'leave_days_person2', 'leave_days_weekends_only', 'total_flight_cost_2adults_inr', 'baggage_status', 'flight_duration_out',
        'flight_duration_back', 'cash_vs_miles_verdict', 'qualification_status', 'source_timestamp']
path = os.path.join(R, 'best_trip_dates.csv')
old = []
if os.path.exists(path): old = list(csv.DictReader(open(path, newline='')))
for o in old:
    o.setdefault('calc_version', '')
    if not o['calc_version']: o['calc_version'] = 'V3.2_SUPERSEDED_overcounted_pre-dawn_departures'
seen = {tuple(o[c] for c in COLS) for o in old if o['calc_version'] == 'V3.3'}
out = list(old)
for r in cands:
    t = {c: str(r[c]) for c in COLS}; t['calc_version'] = 'V3.3'
    if tuple(t[c] for c in COLS) not in seen: out.append(t); seen.add(tuple(t[c] for c in COLS))
tmp = path + '.tmp'
with open(tmp, 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=COLS + ['calc_version']); w.writeheader(); w.writerows(out)
os.replace(tmp, path)
json.dump([{k: (str(v) if not isinstance(v, (int, float)) else v) for k, v in r.items()} for r in cands], open('/tmp/fs/trips_cands.json', 'w'))
print('candidates 9-12 calendar days:', len(cands), 'csv rows', len(out))
