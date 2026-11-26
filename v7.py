"""V7 (2026-11-10): analysis of results/raw/v6 -> dated result CSVs (2027_11_10_*). Offline. Reuses the v5 bloom/leave model (bloom dates are a USER-SUPPLIED average, NOT a forecast)."""
import csv, glob, json, os, datetime as dt, collections
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results'); T = dt.datetime.fromisoformat; D = dt.date
P = '2027_11_10_'
CONF = {D(2027, 1, 26): 'Republic Day (national)', D(2027, 3, 26): 'Good Friday (date fixed; Karnataka status per 3rd-party calendars)'}
PROV = {D(2027, 4, 7): 'Ugadi (7 or 8 Apr, sources disagree)', D(2027, 4, 8): 'Ugadi (7 or 8 Apr, sources disagree)', D(2027, 4, 14): 'Ambedkar Jayanti', D(2027, 3, 10): 'Eid-ul-Fitr (moon-dependent)', D(2027, 10, 29): 'Diwali (provisional)', D(2027, 11, 1): 'Kannada Rajyotsava (employer-dependent)'}
def bloom(c, day, sh):
    fb = (D(2027, 3, 31) if c == 'Tokyo' else D(2027, 4, 4)) + dt.timedelta(sh); k = (day - fb).days
    return 1.0 if -3 <= k <= 5 else 0.5 if (-8 <= k < -3 or 5 < k <= 10) else 0.0
def sakura(arr, nights, first):
    # first city gets first half of nights; Kansai = Osaka/Kyoto/Nara (same bloom proxy). Score 0-5 = mean bloom over trip days.
    k = max(round(nights / 2), 1); out = {}
    for tag, sh in (('early', -7), ('normal', 0), ('late', 7)):
        v = [bloom(('Tokyo' if i < k else 'Kansai') if first == 'Tokyo' else ('Kansai' if i < k else 'Tokyo'), arr + dt.timedelta(i), sh) for i in range(nights + 1)]
        out[tag] = round(5 * sum(v) / len(v), 1)
    return out
def leave(dep, home):
    wk, d = [], dep.date()
    while d <= home.date():
        if d.weekday() < 5 and not (d == dep.date() and dep.hour >= 20): wk.append(d)
        d += dt.timedelta(1)
    c = [d for d in wk if d in CONF]; p = [d for d in wk if d in PROV]
    return len(wk), len(wk) - len(c), len(wk) - len(c) - len(p), '; '.join(f"{d:%d %b} {CONF[d]}" for d in c) or 'none', '; '.join(f"{d:%d %b} {PROV[d]}" for d in p) or 'none'
def group(d):
    if D(2027, 1, 18) <= d <= D(2027, 2, 5): return 'B_ANNIVERSARY_JAN'
    if D(2027, 3, 1) <= d <= D(2027, 3, 14): return 'C_BIRTHDAY_MAR'
    if D(2027, 3, 22) <= d <= D(2027, 3, 31): return 'A_SAKURA'
    if D(2027, 4, 12) <= d <= D(2027, 4, 28): return 'D_POST_SAKURA_APR'
    if D(2027, 5, 6) <= d <= D(2027, 5, 31): return 'D_MAY'
    if d.month in (10, 11): return 'E_AUTUMN'
    return 'OTHER'
SEAS = {'A_SAKURA': None, 'B_ANNIVERSARY_JAN': 3.5, 'C_BIRTHDAY_MAR': 2.0, 'D_POST_SAKURA_APR': 2.5, 'D_MAY': 3.0, 'E_AUTUMN': 4.0}  # 0-5 judgement (cold/low crowds, onsen+Fuji clear skies Jan; no sakura Mar 4-17)
AIRQ = {'JL': 5, 'NH': 5, 'SQ': 5, 'CX': 4.5, 'TG': 4, 'MH': 3.5, 'VN': 3, 'AI': 3, 'GK': 2, 'TR': 2, 'VJ': 1.5}
rows = []
for f in sorted(glob.glob(os.path.join(R, 'raw', 'v6', 'MC6-*.json'))):
    j = json.load(open(f))
    if j.get('err') and not j['res']: continue
    for x in j['res']:
        if not x.get('total') or len(x['legs']) < 2: continue
        o, r = x['legs']; so, sr = o['segs'], r['segs']
        dep, arr, rdp, home = T(so[0][4]), T(so[-1][5]), T(sr[0][4]), T(sr[-1][5])
        a_ap, d_ap = so[-1][3][:3], sr[0][2][:3]
        dirn = 'OSAKA_FIRST' if (a_ap == 'KIX' and d_ap in ('HND', 'NRT')) else 'TOKYO_FIRST' if (a_ap in ('HND', 'NRT') and d_ap == 'KIX') else None
        if not dirn: continue
        chg = [] 
        for s_ in (so, sr):
            chg += [f"{s_[i][3][:3]}>{s_[i + 1][2][:3]}" for i in range(len(s_) - 1) if s_[i][3][:3] != s_[i + 1][2][:3]]
        tokyo_ap = a_ap if dirn == 'TOKYO_FIRST' else d_ap
        nights = (rdp.date() - arr.date()).days; cd = (home.date() - dep.date()).days + 1
        maxh = max(o['dur'], r['dur']) / 60
        if maxh > 17.9 or len(so) > 3 or len(sr) > 3: continue
        la, lb, lc, hc, hp = leave(dep, home)
        g = group(dep.date())
        sk = sakura(arr.date(), nights, 'Tokyo' if dirn == 'TOKYO_FIRST' else 'Kansai') if g == 'A_SAKURA' else {}
        airl = sorted({s[0][:2] for s in so + sr}); lays = [m for _, m in o['lay'] + r['lay']]
        # ---- transparent 0-100 quality score ----
        seas = (sum(sk.values()) / 3 if sk else SEAS.get(g, 2)) / 5 * 20          # 20  (sakura = mean of early/normal/late)
        price = max(0, min(1, (200000 - x['total']) / 60000)) * 15                  # 15  (<=1.40L full, >=2.00L zero)
        dur = (10 if maxh <= 12 else 8 if maxh <= 14 else 6 if maxh <= 16 else 2)    # 10
        conn = 10 if not lays else (10 if all(90 <= m <= 240 for m in lays) else 7 if all(75 <= m <= 360 for m in lays) else 4 if all(60 <= m <= 480 for m in lays) else 1)  # 10
        conn = min(conn, 10) - (3 if len(so) + len(sr) > 4 else 0)
        apc = 0 if chg else 5                                                        # 5
        bag = 2                                                                      # 5 (UNKNOWN for every fare -> flat 2, never 5)
        nts = 10 if 9 <= nights <= 11 else 6 if nights in (8, 12) else 2             # 10
        lev = max(0, min(10, 10 - (lb / max(nights, 1) - 0.4) * 10))                 # 10 (fewer weekdays per night better)
        oj = 5                                                                       # 5 (all rows are open-jaw)
        aq = sum(AIRQ.get(a, 3) for a in airl) / len(airl); comfort = aq / 5 * 6 + (2 if all(6 <= T(s[4]).hour <= 23 for s in so[:1] + sr[:1]) else 0) + (2 if len(so) + len(sr) <= 3 else 0)  # 10
        score = round(seas + price + dur + conn + apc + bag + nts + lev + oj + comfort, 1)
        rows.append(dict(observed=j['ts'], source='fli_google_flights_multicity_adults2_v6', evidence=os.path.relpath(f, R), group=g, direction=dirn,
            india_dep=dep.strftime('%a %Y-%m-%d %H:%M'), japan_arr=arr.strftime('%a %Y-%m-%d %H:%M'), japan_dep=rdp.strftime('%a %Y-%m-%d %H:%M'), india_arr=home.strftime('%a %Y-%m-%d %H:%M'),
            airlines='/'.join(airl), out_flights=' '.join(s[0][:2] + s[1] for s in so), ret_flights=' '.join(s[0][:2] + s[1] for s in sr),
            out_path='>'.join([so[0][2][:3]] + [s[3][:3] for s in so]), ret_path='>'.join([sr[0][2][:3]] + [s[3][:3] for s in sr]),
            layovers_out='; '.join(f"{a[:3]}:{m}m" for a, m in o['lay']) or 'NONE', layovers_ret='; '.join(f"{a[:3]}:{m}m" for a, m in r['lay']) or 'NONE',
            airport_change_in_connection='; '.join(chg) or 'NO', tokyo_airport=tokyo_ap, out_hours=round(o['dur'] / 60, 2), ret_hours=round(r['dur'] / 60, 2), duration_flag='OK<=16h' if maxh <= 16 else 'OVER16h-FLAG',
            japan_nights=nights, calendar_days=cd, leave_raw_weekdays=la, leave_after_confirmed_hol=lb, leave_after_confirmed_and_provisional_hol=lc, confirmed_holidays=hc, provisional_holidays=hp,
            price_for_2_inr=int(x['total']), price_per_adult_inr=int(x['total'] / 2), taxes_included='UNKNOWN (Google total normally all-in; not confirmed)', checked_baggage='UNKNOWN (bags/kg not confirmed)', cabin='ECONOMY',
            ticket_structure='single Google multi-city itinerary; protection/self-transfer UNVERIFIED', fare_rules='not visible', verification_level='LEVEL 1 (API search result; no fare page opened)',
            sakura_early=sk.get('early', 'NA'), sakura_normal=sk.get('normal', 'NA'), sakura_late=sk.get('late', 'NA'), quality_score=score))
# dedupe: same direction+flights+dates -> keep cheapest
best = {}
for r in rows:
    k = (r['direction'], r['out_flights'], r['ret_flights'], r['india_dep'], r['india_arr'])
    if k not in best or r['price_for_2_inr'] < best[k]['price_for_2_inr']: best[k] = r
rows = sorted(best.values(), key=lambda r: -r['quality_score'])
def wr(name, rs):
    if not rs: print('empty', name); return
    with open(os.path.join(R, P + name), 'w', newline='') as fh: w = csv.DictWriter(fh, fieldnames=list(rs[0].keys())); w.writeheader(); w.writerows(rs)
    print(name, len(rs))
wr('all_fares.csv', rows)
sak = [r for r in rows if r['group'] == 'A_SAKURA' and 8 <= r['japan_nights'] <= 12]
wr('sakura_finalists.csv', sak[:60])
# season comparison: best score + cheapest per group/direction
sc = []
for g in sorted({r['group'] for r in rows}):
    for dn in ('OSAKA_FIRST', 'TOKYO_FIRST'):
        p = [r for r in rows if r['group'] == g and r['direction'] == dn and 8 <= r['japan_nights'] <= 12]
        if not p: continue
        c = min(p, key=lambda r: r['price_for_2_inr']); b = max(p, key=lambda r: r['quality_score'])
        sc.append(dict(group=g, direction=dn, n_itineraries=len(p), cheapest_price=c['price_for_2_inr'], cheapest_dates=c['india_dep'][:14] + '>' + c['india_arr'][4:14], cheapest_airline=c['airlines'], cheapest_out_ret_h=f"{c['out_hours']}/{c['ret_hours']}",
                       best_score=b['quality_score'], best_score_price=b['price_for_2_inr'], best_score_dates=b['india_dep'][:14] + '>' + b['india_arr'][4:14], best_airline=b['airlines'], best_flags=b['duration_flag']))
wr('season_comparison.csv', sc)
wr('leave_analysis.csv', [{k: r[k] for k in ('group', 'direction', 'india_dep', 'india_arr', 'japan_nights', 'calendar_days', 'leave_raw_weekdays', 'leave_after_confirmed_hol', 'leave_after_confirmed_and_provisional_hol', 'confirmed_holidays', 'provisional_holidays', 'price_for_2_inr', 'airlines')} for r in sorted(rows, key=lambda r: (r['leave_after_confirmed_and_provisional_hol'], r['price_for_2_inr'])) if 8 <= r['japan_nights'] <= 12][:300])
# price changes vs v5 history (same direction + flights + dates)
hist = {}
for h in csv.DictReader(open(os.path.join(R, '2027_all_date_combinations.csv'))):
    k = (h['direction'], h['outbound_flights'], h['return_flights'], h['india_departure'][:14], h['india_home_arrival'][:14])
    if k not in hist or h['observed_ist'] > hist[k]['observed_ist']: hist[k] = h
pc = []
for r in rows:
    h = hist.get((r['direction'], r['out_flights'].replace('JL', '').replace('GK', '').replace('TG', '').replace('SQ', '').replace('CX', '').replace('MH', '').replace('AI', '').replace('NH', ''), '', '', ''))
for r in rows:
    k = None
    of = ' '.join(s[2:] for s in r['out_flights'].split()); rf = ' '.join(s[2:] for s in r['ret_flights'].split())
    h = hist.get((r['direction'], of, rf, r['india_dep'][:14], r['india_arr'][:14]))
    if h: pc.append(dict(direction=r['direction'], dates=r['india_dep'][:14] + '>' + r['india_arr'][:14], flights=r['out_flights'] + ' / ' + r['ret_flights'], old_price=h['price_for_2_inr'], old_observed=h['observed_ist'], new_price=r['price_for_2_inr'], new_observed=r['observed'], change_inr=r['price_for_2_inr'] - int(h['price_for_2_inr']), change_pct=round(100 * (r['price_for_2_inr'] / int(h['price_for_2_inr']) - 1), 1)))
wr('price_changes.csv', sorted(pc, key=lambda r: r['change_inr']))
print('total rows', len(rows))
