"""Finalist analysis from cached Fli multi-city results (2 adults). Usage: .venv/bin/python finalists.py
Prints exact dates/times, nights, leave, sakura heuristic, and no-airport-change comparisons. Offline only."""
import datetime as dt, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
V2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results', 'raw', 'v2')
T = dt.datetime.fromisoformat
JP_AIRPORT = lambda name: 'HND' if 'Haneda' in name else 'NRT' if 'Narita' in name else 'KIX' if 'Kansai' in name else 'BLR' if 'Bengaluru' in name else name[:12]

def load():
    out = []
    for f in glob.glob(os.path.join(V2, 'MC*.json')):
        b = os.path.basename(f)
        if not re.match(r'(MC\d*V?-BLR)', b): continue
        d = json.load(open(f))
        for x in d['res']:
            if x['total'] and len(x['legs']) >= 2: out.append((x, d['ts'], b))
    return out

def desc(x, ts=''):
    o, r = x['legs'][:2]; so, sr = o['segs'], r['segs']
    od, oa, rd, ra = T(so[0][4]), T(so[-1][5]), T(sr[0][4]), T(sr[-1][5])
    fl = lambda s: ' + '.join(f"{g[0][:2].upper()}{g[1]} {JP_AIRPORT(g[2])}-{JP_AIRPORT(g[3])} {T(g[4]):%a %d %b %H:%M}->{T(g[5]):%H:%M}" for g in s)
    change = any(JP_AIRPORT(so[i][3]) != JP_AIRPORT(so[i + 1][2]) for i in range(len(so) - 1)) or any(JP_AIRPORT(sr[i][3]) != JP_AIRPORT(sr[i + 1][2]) for i in range(len(sr) - 1))
    return dict(total=int(x['total']), out=fl(so), ret=fl(sr), out_dur=o['dur'], ret_dur=r['dur'], dep=od, arr_jp=oa, dep_jp=rd, arr_home=ra,
                nights=(rd.date() - oa.date()).days, cal_days=(ra.date() - od.date()).days + 1, airport_change=change, ts=ts,
                lay_out=[(JP_AIRPORT(a), b) for a, b in o['lay']], lay_ret=[(JP_AIRPORT(a), b) for a, b in r['lay']],
                airlines=sorted({g[0][:2].upper() for g in so + sr}))

# ---- sakura heuristic (documented; NOT a forecast). Full-bloom 30-yr averages: Tokyo Apr 3, Kyoto Apr 4, Osaka Apr 5. Early scenario = 8 days earlier.
FB = {'Tokyo': dt.date(2027, 4, 3), 'Kansai': dt.date(2027, 4, 4)}
def bloom_score(city, day, shift):
    fb = FB[city] - dt.timedelta(shift)
    delta = (day - fb).days
    if -4 <= delta <= 7: return 1.0
    if -9 <= delta < -4 or 7 < delta <= 11: return 0.5
    return 0.0

def sakura(arr: dt.date, nights: int):
    """Osaka/Kyoto/Nara first (60% of nights), Tokyo last. Rating 0-5 averaged over a 30-yr-average year and an early (-8 day) year."""
    k = round(nights * 0.6); days = [arr + dt.timedelta(i) for i in range(nights + 1)]
    sc = []
    for shift in (0, 8):
        s = [bloom_score('Kansai' if i < k else 'Tokyo', d, shift) for i, d in enumerate(days)]
        sc.append(sum(s) / len(s))
    return round(5 * sum(sc) / 2, 1), round(5 * sc[0], 1), round(5 * sc[1], 1), k

if __name__ == '__main__':
    rows = [(desc(x, ts), b) for x, ts, b in load()]
    def show(title, f, n=6, key=lambda r: r[0]['total']):
        print('\n##', title); seen = set()
        for r, b in sorted([r for r in rows if f(r[0])], key=key):
            k = (r['out'], r['ret'])
            if k in seen: continue
            seen.add(k)
            print(f"{r['total']:>7} cd={r['cal_days']} n={r['nights']} {r['dep']:%d%b}->{r['arr_home']:%d%b %H:%M} chg={'HND/NRT' if r['airport_change'] else 'no'} out {r['out_dur']//60}h{r['out_dur']%60:02d} ret {r['ret_dur']//60}h{r['ret_dur']%60:02d} | {r['out']} || {r['ret']} [{r['ts'][11:16]}]")
            if len(seen) >= n: break
    show('A: JAL/Jetstar 23 Mar dep (price 148,840)', lambda r: r['dep'].date() == dt.date(2027, 3, 23) and r['total'] == 148840 and 'GK213' in r['out'].replace(' ', '') or False)
    show('B: 28/29 Mar departures <=165k', lambda r: r['dep'].date() in (dt.date(2027, 3, 28), dt.date(2027, 3, 29)) and r['total'] <= 165000, 10)
    show('No airport change, dep 26-30 Mar, <=17h55, <=200k', lambda r: dt.date(2027, 3, 26) <= r['dep'].date() <= dt.date(2027, 3, 30) and not r['airport_change'] and r['total'] <= 200000 and dt.date(2027, 4, 4) <= r['dep_jp'].date() <= dt.date(2027, 4, 9), 12)
    show('C: Cathay mid-Mar 132,238', lambda r: r['total'] == 132238, 6)
