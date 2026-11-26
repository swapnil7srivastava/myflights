"""Holi/Noida scenario report (10 Nov 2026). Reads results/raw/holi_noida/*.json (Fli). Writes 2027_11_10_holi_noida_*.csv in results/."""
import json, glob, csv, os, datetime as dt
R=os.path.join(os.path.dirname(os.path.abspath(__file__)),'results'); H=os.path.join(R,'raw','holi_noida')
P='2027_11_10_holi_noida_'; D=dt.date; T=dt.datetime.fromisoformat
TZ_OFF={'DEL':5.5,'BLR':5.5,'DXN':5.5,'HDO':5.5,'KIX':9,'NRT':9,'HND':9,'BKK':7}
def dur_h(dep_iso, dep_ap, arr_iso, arr_ap):
    a=T(arr_iso)-dt.timedelta(hours=TZ_OFF.get(arr_ap,5.5)); d=T(dep_iso)-dt.timedelta(hours=TZ_OFF.get(dep_ap,5.5)); return round((a-d).total_seconds()/3600,2)
def ap(n): return n[:3] if n and len(n)>=3 else n
# --- positioning rows
pos=[]
for f in glob.glob(os.path.join(H,'BLR-*.json')):
    j=json.load(open(f)); name=os.path.basename(f).split('-')[1]
    for x in j.get('res',[]):
        if not x.get('total'): continue
        L=x['legs']; pos.append(dict(positioning_airport=name, arrival_day=j['day'], total_for_2_inr=int(x['total']), flight=' '.join(l[0]+l[1] for l in L), dep=L[0][4][11:16], arr=L[-1][5][11:16], stops=x['stops'], duration_min=x['dur'], observed=j['ts'], level='LEVEL 1 (Fli API)'))
pos.sort(key=lambda r:(r['arrival_day'],r['total_for_2_inr']))
pbest={}
for r in pos:
    if r['arrival_day'] not in pbest or r['total_for_2_inr']<pbest[r['arrival_day']]['total_for_2_inr']: pbest[r['arrival_day']]=r
# --- DEL multi-city rows
allr=[]
for f in glob.glob(os.path.join(H,'DEL-*.json')):
    j=json.load(open(f))
    for x in j.get('res',[]):
        if not x['total']: continue
        o=x['legs'][0]['segs']; r=x['legs'][1]['segs']
        out_d=dur_h(o[0][4],o[0][2],o[-1][5],o[-1][3]); ret_d=dur_h(r[0][4],r[0][2],r[-1][5],r[-1][3])
        allr.append(dict(direction=j['direction'], del_dep=j['dep'], japan_dep_from_jp=r[0][4][:16], japan_return_date=j['ret'], out_flights=' > '.join(s[0]+s[1] for s in o), ret_flights=' > '.join(s[0]+s[1] for s in r),
            out_route=' > '.join([o[0][2]]+[s[3] for s in o]), ret_route=' > '.join([r[0][2]]+[s[3] for s in r]), del_dep_time=o[0][4][:16], japan_arr=o[-1][5][:16], japan_dep=r[0][4][:16], home_arr=r[-1][5][:16],
            out_hours=out_d, ret_hours=ret_d, stops_out=len(o)-1, stops_ret=len(r)-1, out_layovers=' ; '.join(f"{a}:{m}m" for a,m in x['legs'][0]['lay']) or 'NONE', ret_layovers=' ; '.join(f"{a}:{m}m" for a,m in x['legs'][1]['lay']) or 'NONE',
            airlines='/'.join(sorted({s[0] for s in o+r})), total_for_2_inr=int(x['total']), observed=j['ts'], evidence=os.path.basename(f), verification='LEVEL 1 (Fli API)', baggage='UNKNOWN', taxes='UNKNOWN', self_transfer='UNVERIFIED'))
allr.sort(key=lambda r:(r['total_for_2_inr']))
# --- full-trip options: positioning on arrival day P, DEL departure on J; Noida nights = J-P
def sak(arr,nights,first):
    def bloom(c,day,sh):
        fb=(D(2027,3,31) if c=='Tokyo' else D(2027,4,4))+dt.timedelta(sh); k=(day-fb).days
        return 1.0 if -3<=k<=5 else 0.5 if (-8<=k<-3 or 5<k<=10) else 0.0
    k=max(round(nights/2),1); out={}
    for tag,sh in (('early',-7),('normal',0),('late',7)):
        v=[bloom(('Tokyo' if i<k else 'Kansai') if first=='Tokyo' else ('Kansai' if i<k else 'Tokyo'),arr+dt.timedelta(i),sh) for i in range(nights+1)]
        out[tag]=round(5*sum(v)/len(v),1)
    return out
HOLI={'2027-03-21':'Holika Dahan (Sun 21 Mar; date-sourced, Karnataka status unconfirmed)','2027-03-22':'Holi/Dhulandi (Mon 22 Mar; employer-dependent)','2027-03-26':'Good Friday (Fri 26 Mar; regional per sources)','2027-04-07':'Ugadi 7/8 Apr (sources disagree)','2027-04-08':'Ugadi 7/8 Apr (sources disagree)'}
def leave(s,e):
    d=D.fromisoformat(s); end=D.fromisoformat(e); wk=[]
    while d<=end:
        if d.weekday()<5: wk.append(d.isoformat())
        d+=dt.timedelta(1)
    prov=[x for x in wk if x in HOLI]
    return len(wk), len(wk)-len(prov), '; '.join(f"{x} {HOLI[x]}" for x in prov) or 'none'
BASE_AGG, BASE_REAL = 138078, 150000
fin=[]
for r in allr:
    if r['direction'] not in ('TOKYO','OSAKA'): continue
    if r['del_dep'] not in ('2027-03-23','2027-03-24','2027-03-25','2027-03-26','2027-03-27','2027-03-28','2027-03-29','2027-03-30'): continue
    pb=pbest.get('2027-03-19') or {}
    best_p=min([pbest[k] for k in pbest], key=lambda x:x['total_for_2_inr'])
    pass
# one best per (direction, del_dep) combined with cheapest positioning that allows Noida nights >=2
seen=set(); fin=[]
for r in allr:
    k=(r['direction'], r['del_dep'])
    if k in seen: continue
    seen.add(k)
    arrp=min([pbest[d] for d in pbest if (D.fromisoformat(r['del_dep'])-D.fromisoformat(d)).days>=2], key=lambda x:x['total_for_2_inr'])
    P=arrp['arrival_day']; nights_noida=(D.fromisoformat(r['del_dep'])-D.fromisoformat(P)).days
    jp_n=(D.fromisoformat(r['japan_return_date'])-D.fromisoformat(r['japan_arr'][:10])).days
    tot=r['total_for_2_inr']+arrp['total_for_2_inr']
    lv=leave(P, r['home_arr'][:10]) ; sk=sak(D.fromisoformat(r['japan_arr'][:10]), jp_n, 'Tokyo' if r['direction']=='TOKYO' else 'Kansai')
    fin.append(dict(rank_key=tot, positioning=f"BLR>{arrp['positioning_airport']} {arrp['flight']} {arrp['dep']}->{arrp['arr']} {P}", noida_nights=nights_noida, direction=r['direction'], del_dep=r['del_dep'], japan_arr=r['japan_arr'], japan_nights=jp_n,
        international_out=r['out_flights'], route_out=r['out_route'], out_hours=r['out_hours'], international_ret=r['ret_flights'], route_ret=r['ret_route'], ret_hours=r['ret_hours'], home_arr=r['home_arr'], stops=f"{r['stops_out']}/{r['stops_ret']}", 
        duration_flag=('OK<=16h' if max(r['out_hours'],r['ret_hours'])<=16 else 'EXCEPTION_16h-18h' if max(r['out_hours'],r['ret_hours'])<=18 else 'OVER18h'), positioning_inr=arrp['total_for_2_inr'], intl_inr=r['total_for_2_inr'], total_inr=tot,
        premium_vs_138k=tot-BASE_AGG, premium_vs_150k=tot-BASE_REAL, premium_pp_vs_138k=(tot-BASE_AGG)//2, raw_weekdays=lv[0], effective_leave=lv[1], holidays=lv[2], sak_early=sk['early'], sak_normal=sk['normal'], sak_late=sk['late'], verification='LEVEL 1 (Fli API)', baggage='UNKNOWN', observed=r['observed'], evidence=r['evidence']))
fin.sort(key=lambda x:x['total_inr'])
def wr(name, rows):
    if not rows: print('empty',name); return
    fn=[]
    for r in rows:
        for k in r:
            if k!='rank_key' and k not in fn: fn.append(k)
    with open(os.path.join(R,P+name),'w',newline='') as fh: w=csv.DictWriter(fh,fieldnames=fn,restval=''); w.writeheader(); w.writerows([{k:v for k,v in r.items() if k!='rank_key'} for r in rows])
    print(name,len(rows))
wr('all_fares.csv', pos + allr)
wr('finalists.csv', fin)
wr('leave_analysis.csv', [{k:f[k] for k in ('direction','del_dep','japan_arr','japan_nights','noida_nights','home_arr','raw_weekdays','effective_leave','holidays')} for f in fin])
wr('vs_blr.csv', [{k:f[k] for k in ('direction','del_dep','japan_nights','noida_nights','positioning_inr','intl_inr','total_inr','premium_vs_138k','premium_vs_150k','premium_pp_vs_138k','sak_early','sak_normal','sak_late','duration_flag')} for f in fin])
print('finalists:'); 
for f in fin[:10]: print(f['total_inr'], f['direction'], f['del_dep'], 'noida',f['noida_nights'],'jp',f['japan_nights'],'out',f['out_hours'],'ret',f['ret_hours'],f['duration_flag'],'prem138',f['premium_vs_138k'],'prem150',f['premium_vs_150k'],'leave',f['raw_weekdays'],f['effective_leave'],'sak',f['sak_early'],f['sak_normal'],f['sak_late'], f['stops'], f['international_out'], f['positioning'])
