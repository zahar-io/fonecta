"""T403 production run of the v2 brain: train on every dev business (2026, optionally + the 2025 back-test season),
predict all 2026 targets, write predictions_2026.csv (scorer format) + outputs/predictions_2026_explained.csv (app).
Thresholds come from the 2025 back-test OOF sweep (never from 2026 labels in-sample).
    THR_CLOSED=.. THR_OPEN=.. EXTRA=0|1 CONFIGS='[[spx,cpx],...]' python brain/final.py"""
import os,sys,json,csv,pickle,numpy as np,pandas as pd,collections,time
import harness as H, model as M, v2
from sklearn.ensemble import HistGradientBoostingClassifier as HC, HistGradientBoostingRegressor as HR
ROOT=M.ROOT
B={"max_iter":300,"learning_rate":0.06,"max_leaf_nodes":31}
CONFIGS=json.loads(os.environ.get("CONFIGS",json.dumps([[B,B]])))
thr={'closed':float(os.environ["THR_CLOSED"]),'open':float(os.environ["THR_OPEN"])}
D6,D5=pickle.load(open('/tmp/t403_D.pkl','rb'))
def trainset(extra):
    Xs=[D6['X'].iloc[D6['dev']]]; ys=[D6['y']]
    p6={i:j for j,i in enumerate(D6['dev'])}
    cm=D6['y'][[p6[r] for r in D6['crow']]]==2
    Zs=[D6['Z'][cm]]; ts=[D6['tp'][cm]]
    if extra:
        Xs.append(D5['X'].iloc[D5['dev']]); ys.append(D5['y'])
        p5={i:j for j,i in enumerate(D5['dev'])}
        c5=D5['y'][[p5[r] for r in D5['crow']]]==2
        Zs.append(D5['Z'][c5]); ts.append(D5['tp'][c5])
    Xtr=pd.concat(Xs); ytr=np.concatenate(ys); Ztr=Zs[0]
    for z in Zs[1:]:
        a,b=v2.align(Ztr,z); Ztr=pd.concat([a,b])
    for c in M.CAT: Xtr[c]=Xtr[c].astype(str).astype("category")
    return Xtr,ytr,Ztr,np.concatenate(ts)
# all 2026 targets
X,meta,L,dev=H.load(2026)
t=time.time(); C,keys=v2.cand_table(X,meta,range(len(meta))); Z=v2.cand_X(C,X); print('cands',len(keys),time.time()-t,flush=True)
P=np.zeros((len(meta),3)); EC=np.zeros(len(keys))
for cfg in CONFIGS:
    spx,cpx=cfg[0],cfg[1]; extra=len(cfg)>2 and cfg[2]
    Xtr,ytr,Ztr,ttr=trainset(extra)
    Xa=X.copy()
    for c in M.CAT: Xa[c]=pd.Categorical(Xa[c].astype(str),categories=Xtr[c].cat.categories)
    Za,Zb=v2.align(Ztr,Z)
    for c in M.CAT:
        Za[c]=Za[c].astype(str).astype("category"); Zb[c]=pd.Categorical(Zb[c].astype(str),categories=Za[c].cat.categories)
    sm=HC(**spx,categorical_features="from_dtype",random_state=0).fit(Xtr,ytr); P+=sm.predict_proba(Xa)/len(CONFIGS)
    cm=HR(**cpx,categorical_features="from_dtype",random_state=0).fit(Za,ttr); EC+=cm.predict(Zb)/len(CONFIGS)
    print('fitted',cfg,flush=True)
byrow=collections.defaultdict(list); tags={}
gen_cache={}
for (i,h),e in zip(keys,EC): byrow[i].append((e,h))
PRI=["ly1","ly2","mall","ps1","ps2","rev_close","peer_special"]
def basis_of(m,h):
    src=[k for k,v in m['cands'].items() if v==h]
    for k in PRI:
        if k in src: return k.upper()
    return "PATTERN"
out=os.path.join(ROOT,"predictions_2026.csv"); expl=os.path.join(ROOT,"outputs","predictions_2026_explained.csv")
n=collections.Counter()
with open(out,"w",newline="",encoding="utf-8") as g, open(expl,"w",newline="",encoding="utf-8") as g2:
    w,w2=csv.writer(g),csv.writer(g2)
    w.writerow(["entity_id","date","action","hours","confidence"])
    w2.writerow(["entity_id","date","day_key","action","hours","confidence","basis","shown","p_closed","p_same","p_other","candidates_json"])
    for i,m in enumerate(meta):
        a,h,c,basis,ev=v2.decide2(P[i],m,byrow.get(i,[]),thr)
        if basis=="CAND": basis=basis_of(m,h)
        n[(a,basis)]+=1
        if a!="NO_ACTION": w.writerow([m["entity_id"],m["date"],a,h,round(c,3)])
        w2.writerow([m["entity_id"],m["date"],m["key"],a,h,round(c,3),basis or "",m["shown"],*[round(float(x),3) for x in P[i]],json.dumps(m["cands"],ensure_ascii=False)])
json.dump({"model":"v2 (T403): state classifier + candidate expected-points regressor","thr":thr,"configs":CONFIGS,
           "counts":{f"{k[0]}:{k[1]}":v for k,v in n.items()}},open(os.path.join(M.HERE,"report.json"),"w"),indent=1)
print(n.most_common()); print(out)
