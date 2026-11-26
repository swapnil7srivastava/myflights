"""FINAL booking-day audit (10 Nov 2026). Builds FINAL CSVs from results/2027_11_10_all_fares.csv (BLR multi-city, Fli Level 1) + results/raw/final_stability (3x repeats). Offline."""
import csv, json, glob, os, collections
R='results'; P='2027_11_10_FINAL_'
rows=list(csv.DictReader(open(os.path.join(R,'2027_11_10_all_fares.csv'))))
def d(s): return s.split()[1]  # 'Sat 2027-03-27 23:10' -> date
def ret(s): return s.split()[1]
want=[r for r in rows if d(r['india_dep']) in {f'2027-03-{x}' for x in range(25,31)} and ret(r['india_arr']) in {f'2027-04-{x:02d}' for x in range(4,11)} and 8<=int(r['japan_nights'])<=12]
stab={}
for f in glob.glob(os.path.join(R,'raw','final_stability','*-a*.json')):
    j=json.load(open(f)); k=(j['direction'],j['dep'],j['ret'])
    best=min([x['total'] for x in j['res'] if x['total']],default=None)
    stab.setdefault(k,[]).append(best)
def classify(k):
    a=stab.get(k)
    if not a: return 'NOT RE-TESTED'
    hits=sum(1 for x in a if x is not None); prices={x for x in a if x is not None}
    if hits==len(a) and len(prices)==1: return 'STABLE (%d/%d same price)'%(hits,len(a))
    if hits>=2: return 'SEMI-STABLE (%d/%d found)'%(hits,len(a))
    return 'UNSTABLE/PHANTOM-RISK (%d/%d found)'%(hits,len(a))
# ---- ALL FARES (required windows)
for r in want:
    k=(r['direction'],d(r['india_dep']),ret(r['india_arr']))
    r['stability']=classify(k)
    r['baggage']='UNKNOWN'; r['verification']='LEVEL 1'
cols=list(want[0].keys()) if want else []
with open(os.path.join(R,P+'ALL_FARES.csv'),'w',newline='') as fh:
    w=csv.DictWriter(fh,fieldnames=cols); w.writeheader(); w.writerows(sorted(want,key=lambda r:int(r['price_for_2_inr'])))
# ---- FARE STABILITY (the 6 repeats)
fs=[]
for k,a in sorted(stab.items()):
    fs.append(dict(direction=k[0],india_dep=k[1],india_return=k[2],attempts=len(a),prices_found=' | '.join(str(int(x)) if x else 'NO RESULT' for x in a),classification=classify(k)))
with open(os.path.join(R,P+'FARE_STABILITY.csv'),'w',newline='') as fh:
    w=csv.DictWriter(fh,fieldnames=list(fs[0].keys())); w.writeheader(); w.writerows(fs)
# ---- LEAVE + SAKURA MATRIX (per combo, best fare)
best={}
for r in want:
    k=(r['direction'],d(r['india_dep']),ret(r['india_arr']))
    if k not in best or int(r['price_for_2_inr'])<int(best[k]['price_for_2_inr']): best[k]=r
mat=[]
for k,r in sorted(best.items(), key=lambda kv:(kv[0][1],kv[0][2],kv[0][0])):
    mat.append(dict(direction=k[0],india_dep=r['india_dep'],india_return=r['india_arr'],japan_nights=r['japan_nights'],calendar_days=r['calendar_days'],raw_weekdays=r['leave_raw_weekdays'],after_confirmed=r['leave_after_confirmed_hol'],after_provisional=r['leave_after_confirmed_and_provisional_hol'],
        good_friday_26mar=('YES (provisional, Fri 26 Mar in trip)' if d(r['india_dep'])<='2027-03-26' else 'NO'), best_fare_inr=r['price_for_2_inr'], airlines=r['airlines'], out_hours=r['out_hours'], ret_hours=r['ret_hours'], duration_flag=r['duration_flag'],
        sakura_early=r['sakura_early'], sakura_normal=r['sakura_normal'], sakura_late=r['sakura_late'], stability=classify(k)))
with open(os.path.join(R,P+'LEAVE_MATRIX.csv'),'w',newline='') as fh:
    w=csv.DictWriter(fh,fieldnames=list(mat[0].keys())); w.writeheader(); w.writerows(mat)
with open(os.path.join(R,P+'SAKURA_MATRIX.csv'),'w',newline='') as fh:
    w=csv.DictWriter(fh,fieldnames=['direction','india_dep','india_return','japan_nights','sakura_early','sakura_normal','sakura_late','duration_flag','best_fare_inr','stability']); w.writeheader()
    w.writerows([{k:m[k] for k in w.fieldnames} for m in mat])
print('want rows',len(want),'combos',len(best),'stability',len(stab))
for m in mat:
    if m['duration_flag']=='OK<=16h' and int(m['best_fare_inr'])<=175000 or m['stability'].startswith('STABLE'):
        print(m['direction'],m['india_dep'],'->',m['india_return'],'n',m['japan_nights'],'raw',m['raw_weekdays'],'prov',m['after_provisional'],'fare',m['best_fare_inr'],m['airlines'],m['out_hours'],m['ret_hours'],m['duration_flag'],'E/N/L',m['sakura_early'],m['sakura_normal'],m['sakura_late'],'|',m['stability'])
