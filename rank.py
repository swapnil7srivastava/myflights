"""Offline combiner: reads cached Fli results in results/raw/v2 and writes date_matrix.csv + shortlist.csv.
Usage: .venv/bin/python rank.py
Prices are INR party totals for 2 adults (Fli adults=2). Nothing here is booking-verified."""
import csv, datetime as dt, glob, json, os, collections

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
V2 = os.path.join(R, 'raw', 'v2')
CAP, EXC = 960, 1075          # 16h00, 17h55
D = dt.date.fromisoformat


def seglabel(l):
    return ' > '.join(f"{g[0]} {g[1]} {g[2][:3] if len(g[2]) < 4 else g[2][:12]}-{g[3][:12]} {g[4][5:16]}->{g[5][5:16]}" for g in l['segs'])


def tier(d):
    return 'OK' if d <= CAP else ('EXC' if d <= EXC else None)


cands = {}
# 1) multi-city (single Google price for both legs). Direction label from airports.
for f in glob.glob(os.path.join(V2, 'MC*-*.json')):
    base = os.path.basename(f)
    if not __import__('re').match(r'(MC\d*V?-BLR|MCREV)', base):
        continue
    d = json.load(open(f))
    for x in d['res']:
        if not x['total'] or len(x['legs']) < 2:
            continue
        o, r = x['legs'][:2]
        to, tr = tier(o['dur']), tier(r['dur'])
        if not to or not tr:
            continue
        out_arr = D(o['segs'][-1][5][:10]); ret_dep = D(r['segs'][0][4][:10]); out_dep = D(o['segs'][0][4][:10])
        nights = (ret_dep - out_arr).days
        key = (tuple(g[1] for g in o['segs']), tuple(g[1] for g in r['segs']), out_dep, ret_dep, o['segs'][0][2][:3] + o['segs'][-1][3][:3] + r['segs'][0][2][:3])
        row = dict(total=x['total'], out_dep=out_dep, ret_dep=ret_dep, nights=nights, o=o, r=r,
                   tier='EXC' if 'EXC' in (to, tr) else 'OK', ticketing='MULTI_CITY_SINGLE_PRICE', ts=d['ts'])
        if key not in cands or cands[key]['total'] > x['total']:
            cands[key] = row

rows = sorted(cands.values(), key=lambda t: t['total'])
valid = [t for t in rows if 9 <= t['nights'] <= 15]

# date matrix: best OK and best EXC per pair
mat = collections.defaultdict(dict)
for t in valid:
    k = (t['out_dep'], t['ret_dep'])
    cur = mat[k].get(t['tier'])
    if cur is None or t['total'] < cur['total']:
        mat[k][t['tier']] = t
with open(os.path.join(R, 'date_matrix.csv'), 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['out_dep', 'ret_dep', 'japan_nights', 'best_total_2adults_inr_<=16h', 'itinerary_<=16h', 'best_total_exception_16h-17h55', 'itinerary_exception', 'status'])
    for k in sorted(mat):
        ok, ex = mat[k].get('OK'), mat[k].get('EXC')
        n = (ok or ex)['nights']
        w.writerow([k[0], k[1], n, int(ok['total']) if ok else '', (seglabel(ok['o']) + ' || ' + seglabel(ok['r'])) if ok else '',
                    int(ex['total']) if ex else '', (seglabel(ex['o']) + ' || ' + seglabel(ex['r'])) if ex else '',
                    'ABOVE_160K' if (ok and ok['total'] > 160000) else ('PROVISIONAL' if ok else 'EXCEPTION_ONLY')])

with open(os.path.join(R, 'shortlist.csv'), 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['rank', 'total_2adults_inr', 'per_person_inr', 'out_dep', 'ret_dep', 'japan_nights', 'out_itinerary', 'out_elapsed_h', 'out_layover_min', 'ret_itinerary', 'ret_elapsed_h', 'ret_layover_min', 'duration_tier', 'ticketing', 'checked_bags', 'status', 'timestamp'])
    seen = set(); i = 0
    for t in valid:
        k = (tuple(g[1] for g in t['o']['segs']), tuple(g[1] for g in t['r']['segs']), t['out_dep'], t['ret_dep'])
        if k in seen:
            continue
        seen.add(k); i += 1
        if i > 60:
            break
        w.writerow([i, int(t['total']), t['total'] / 2, t['out_dep'], t['ret_dep'], t['nights'], seglabel(t['o']), round(t['o']['dur'] / 60, 2), [b for a, b in t['o']['lay']],
                    seglabel(t['r']), round(t['r']['dur'] / 60, 2), [b for a, b in t['r']['lay']], 'DURATION EXCEPTION' if t['tier'] == 'EXC' else '<=16h',
                    t['ticketing'] + ' (bookability not verified)', 'UNVERIFIED', 'PROVISIONAL', t['ts']])
print('candidates', len(cands), 'valid(9-15 nights)', len(valid), 'date pairs', len(mat))
for t in valid[:10]:
    print(int(t['total']), t['out_dep'], t['ret_dep'], t['nights'], t['tier'], seglabel(t['o'])[:60], '||', seglabel(t['r'])[:60])
