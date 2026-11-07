"""T403 v2.1 production run: 3-model calibrated ensemble (the one reported):
  g1cal  = v2 state model (calibrated) + v2 candidate model
  g1calc = same state model + larger candidate model
  v3cal  = v3 (fold-safe label statistics, calibrated)
Trained on every dev business; thresholds from the 2025 back-test OOF sweep (THR_CLOSED, THR_OPEN).
Writes predictions_2026.csv + outputs/predictions_2026_explained.csv."""
import os,sys,json,csv,pickle,numpy as np,pandas as pd,collections,time
import harness as H, model as M, v2, v3, te as TEm
from sklearn.ensemble import HistGradientBoostingClassifier as HC, HistGradientBoostingRegressor as HR
thr={'closed':float(os.environ["THR_CLOSED"]),'open':float(os.environ["THR_OPEN"])}
B={"max_iter":300,"learning_rate":0.06,"max_leaf_nodes":31}
C={"max_iter":800,"learning_rate":0.03,"max_leaf_nodes":63,"min_samples_leaf":30}
KW=dict(categorical_features="from_dtype",random_state=0)
D6,_=pickle.load(open('/tmp/t403_D.pkl','rb'))
X,meta,L,dev=H.load(2026)
allidx=list(range(len(meta)))
y=D6['y']; gdev=np.array([meta[i]['entity_id'] for i in dev])
def cats(a,b):
    for c in M.CAT:
        a[c]=a[c].astype(str).astype("category"); b[c]=pd.Categorical(b[c].astype(str),categories=a[c].cat.categories)
P=np.zeros((len(meta),3)); byrow=collections.defaultdict(lambda:collections.defaultdict(list)); cmeta={}
# --- v2 state model, calibrated (shared by g1cal and g1calc)
Xtr=D6['X'].iloc[dev].copy(); Xa=X.copy(); cats(Xtr,Xa)
sm=HC(**B,**KW).fit(Xtr,y); Pv2=v2.calibrate(Xtr,y,gdev,sm.predict_proba(Xa))
t=time.time(); Cc,keys=v2.cand_table(X,meta,allidx); Z=v2.cand_X(Cc,X); print('cands',len(keys),round(time.time()-t),flush=True)
pos={i:j for j,i in enumerate(dev)}
cm_=y[[pos[r] for r in D6['crow']]]==2
for cpx in (B,C):
    Za,Zb=v2.align(D6['Z'][cm_].reset_index(drop=True),Z); cats(Za,Zb)
    ec=HR(**cpx,**KW).fit(Za,D6['tp'][cm_]).predict(Zb)
    for (i,h),e in zip(keys,ec): byrow[i][h].append(e)
    P+=Pv2; print('v2 model done',flush=True)
# --- v3 with label statistics from all dev businesses
rows,info=TEm.load_rows(2026,L,X,meta,dev)
te=TEm.TE(rows,info,set(gdev))
rinfo={i:v3.info_of(X,meta,i) for i in allidx}
Xtr3,Ztr3,ktr3,_=v3.fold_tables(D6,te,dev,rinfo)
Xall3,Zall3,kall3,mall3=v3.fold_tables({'X':X,'meta':meta},te,allidx,rinfo)
cats(Xtr3,Xall3)
sm3=HC(**B,**KW).fit(Xtr3,y); P+=v2.calibrate(Xtr3,y,gdev,sm3.predict_proba(Xall3))
yrow={i:y[j] for j,i in enumerate(dev)}
msk=np.array([yrow[i]==2 for i,h in ktr3])
Za,Zb=v2.align(Ztr3[msk].reset_index(drop=True),Zall3); cats(Za,Zb)
ec=HR(**B,**KW).fit(Za,v3.pts_of(D6,[ktr3[j] for j in np.where(msk)[0]])).predict(Zb)
for (i,h),e in zip(kall3,ec): byrow[i][h].append(e)
P/=3
# ens.py semantics: average each candidate over the models that produced it
br={i:[(np.mean(v),h) for h,v in d.items()] for i,d in byrow.items()}
PRI=["ly1","ly2","mall","ps1","ps2","rev_close","peer_special"]
def basis_of(m,h):
    src=[k for k,v in m['cands'].items() if v==h]
    for k in PRI:
        if k in src: return k.upper()
    return "PATTERN"
out=os.path.join(M.ROOT,"predictions_2026.csv"); expl=os.path.join(M.ROOT,"outputs","predictions_2026_explained.csv")
n=collections.Counter()
with open(out,"w",newline="",encoding="utf-8") as g, open(expl,"w",newline="",encoding="utf-8") as g2:
    w,w2=csv.writer(g),csv.writer(g2)
    w.writerow(["entity_id","date","action","hours","confidence"])
    w2.writerow(["entity_id","date","day_key","action","hours","confidence","basis","shown","p_closed","p_same","p_other","candidates_json"])
    for i,m in enumerate(meta):
        a,h,c,basis,ev=v2.decide2(P[i],m,br.get(i,[]),thr)
        if basis=="CAND": basis=basis_of(m,h)
        n[(a,basis)]+=1
        if a!="NO_ACTION": w.writerow([m["entity_id"],m["date"],a,h,round(c,3)])
        w2.writerow([m["entity_id"],m["date"],m["key"],a,h,round(c,3),basis or "",m["shown"],*[round(float(x),3) for x in P[i]],json.dumps(m["cands"],ensure_ascii=False)])
json.dump({"model":"v2.1 (T403): calibrated 3-model ensemble (h1cal, h1calc, v3hcal)","thr":thr,
           "counts":{f"{k[0]}:{k[1]}":v for k,v in n.items()}},open(os.path.join(M.HERE,"report.json"),"w"),indent=1)
print(n.most_common()); print(out)
