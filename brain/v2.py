"""v2: state model (P closed/same/other) + candidate model (expected points of each hours candidate when the truth
is open and differs from shown). Decision = max expected scorer points. Everything OOF by business."""
import os,sys,pickle,numpy as np,pandas as pd,collections
import model as M
from features import KIT, span, hm
sys.path.insert(0,KIT+'/evaluation'); import evaluate as E
from sklearn.model_selection import GroupKFold
from sklearn.ensemble import HistGradientBoostingClassifier as HC, HistGradientBoostingRegressor as HR
SRC=["sun","sat","ly_mode","rev_close","mall","ly1","ly2","ps1","ps2","peer_special","reg_open_peer_close"]
def fmt(m):
    m%=1440; return f"{m//60:02d}:{m%60:02d}"
def mk(o,c):
    if c<=o+30 or c>o+1440 or o<0: return None
    return f"{fmt(o)}-{fmt(c)}"
def gen(m):
    """candidate hours -> set of source tags"""
    shown=m['shown']; out=collections.defaultdict(set)
    for k,v in m['cands'].items():
        if v not in ('closed',shown): out[v].add(k)
    s=span(shown)
    if not s: return out
    so,sc=s
    anchors={}
    for k,v in m['cands'].items():
        sp=span(v) if v!='closed' else None
        if sp: anchors[k]=sp
    for d in (-240,-180,-120,-60,60,120):
        h=mk(so,sc+d); h and out[h].add(f"g_c{d}")
    for d in (60,120,-60):
        h=mk(so+d,sc); h and out[h].add(f"g_o{d}")
    h=mk(so+60,sc-60); h and out[h].add("g_o60c-60")
    h=mk(so+120,sc-120); h and out[h].add("g_o120c-120")
    for ab in range(12*60,19*60,60):
        if ab<sc%1440 if sc<1440 else True:
            h=mk(so,ab); h and out[h].add("g_abs")
    for k,(ao,ac) in anchors.items():
        h=mk(so,ac); h and out[h].add("so_"+k)
        h=mk(ao,sc); h and out[h].add(k+"_sc")
    out.pop(shown,None)
    return out
TAGS=None
def cand_table(X,meta,idx):
    rows=[];keys=[]
    for i in idx:
        m=meta[i]; s=span(m['shown']); so,sc=s if s else (np.nan,np.nan)
        anchors={k:span(v) for k,v in m['cands'].items() if v!='closed' and span(v)}
        for h,tags in gen(m).items():
            o,c=span(h)
            f={"row":i,"dopen":o-so,"dclose":c-sc,"o":o,"c":c,"dur":c-o,"ntag":len(tags),"nsrc":len([t for t in tags if t in SRC])}
            for t in SRC: f["s_"+t]=int(t in tags)
            for t in tags:
                if not t in SRC: f["t_"+t]=1
            for k,(ao,ac) in anchors.items():
                f["do_"+k]=o-ao; f["dc_"+k]=c-ac
            rows.append(f); keys.append((i,h))
    C=pd.DataFrame(rows)
    return C,keys
def cand_X(C,X):
    R=X.iloc[C["row"].values].reset_index(drop=True)
    Z=pd.concat([C.drop(columns=["row"]).reset_index(drop=True),R],axis=1)
    return Z
def pts(h,t):
    if h==t: return 1.0
    if (h=='closed')!=(t=='closed'): return -1.0
    return 0.6 if E.near(h,t) else 0.2

def ystate(L,meta,i): return M.y_state(L[(meta[i]['entity_id'],meta[i]['date'])],meta[i]['shown'])
import json as _j
SP=dict(**_j.loads(os.environ.get("SPX",'{"max_iter":300,"learning_rate":0.06,"max_leaf_nodes":31}')),categorical_features="from_dtype",random_state=0)
CP=dict(**_j.loads(os.environ.get("CPX",'{"max_iter":300,"learning_rate":0.06,"max_leaf_nodes":31}')),categorical_features="from_dtype",random_state=0)
def prep(s):
    X,meta,L,dev=__import__('harness').load(s)
    C,keys=cand_table(X,meta,dev)
    Z=cand_X(C,X)
    y=np.array([ystate(L,meta,i) for i in dev])
    tp=np.array([pts(h,E.norm(L[(meta[i]['entity_id'],meta[i]['date'])]['truth_hours'])) for (i,h) in keys])
    return dict(X=X,meta=meta,L=L,dev=dev,C=C,keys=keys,Z=Z,y=y,tp=tp,crow=C["row"].values)
def align(Za,Zb):
    cols=sorted(set(Za.columns)|set(Zb.columns),key=str)
    out=[]
    for Z in (Za,Zb):
        Z=Z.reindex(columns=cols)
        for c in cols:
            if c.startswith("t_") or c.startswith("s_"): Z[c]=Z[c].fillna(0)
        out.append(Z)
    return out
def oof(D,extra=None):
    """returns per dev-row probs and dict row->list[(h,E)] ; extra = other season dict used as extra train rows"""
    dev=D['dev']; y=D['y']; g=np.array([D['meta'][i]['entity_id'] for i in dev])
    P=np.zeros((len(dev),3)); EC=np.zeros(len(D['keys']))
    pos={i:j for j,i in enumerate(dev)}
    crow_j=np.array([pos[i] for i in D['crow']])
    for tr,te in GroupKFold(5).split(dev,y,g):
        trE=set(g[tr]); teE=set(g[te])
        Xtr=D['X'].iloc[[dev[j] for j in tr]]; ytr=y[tr]
        ctr=np.isin(crow_j,tr)&(y[crow_j]==2); Ztr=D['Z'][ctr]; ttr=D['tp'][ctr]
        if extra is not None:
            ge=np.array([extra['meta'][i]['entity_id'] for i in extra['dev']])
            ok=np.array([e in trE for e in ge])
            Xtr=pd.concat([Xtr,extra['X'].iloc[[extra['dev'][j] for j in np.where(ok)[0]]]])
            ytr=np.concatenate([ytr,extra['y'][ok]])
            pe={i:j for j,i in enumerate(extra['dev'])}
            cj=np.array([pe[i] for i in extra['crow']])
            ce=ok[cj]&(extra['y'][cj]==2)
            Za,Zb=align(Ztr,extra['Z'][ce]); Ztr=pd.concat([Za,Zb]); ttr=np.concatenate([ttr,extra['tp'][ce]])
        for c in M.CAT: Xtr[c]=Xtr[c].astype(str).astype("category")
        Xte=D['X'].iloc[[dev[j] for j in te]].copy()
        for c in M.CAT: Xte[c]=pd.Categorical(Xte[c].astype(str),categories=Xtr[c].cat.categories)
        sm=HC(**SP).fit(Xtr,ytr); P[te]=sm.predict_proba(Xte)
        if os.environ.get('CAL')=='1':
            P[te]=calibrate(Xtr,ytr,g_tr_all(D,tr,extra,trE),P[te])
        cte=np.isin(crow_j,te)
        Za,Zb=align(Ztr,D['Z'][cte])
        for c in M.CAT:
            Za[c]=Za[c].astype(str).astype("category"); Zb[c]=pd.Categorical(Zb[c].astype(str),categories=Za[c].cat.categories)
        cm=HR(**CP).fit(Za,ttr); EC[cte]=cm.predict(Zb)
    byrow=collections.defaultdict(list)
    for (i,h),e in zip(D['keys'],EC): byrow[i].append((e,h))
    return P,byrow
def g_tr_all(D,tr,extra,trE):
    g=[D['meta'][D['dev'][j]]['entity_id'] for j in tr]
    if extra is not None:
        g+= [extra['meta'][i]['entity_id'] for i in extra['dev'] if extra['meta'][i]['entity_id'] in trE]
    return np.array(g)
def calfeat(P): return np.log(np.clip(P,1e-4,1))
def calibrate(Xtr,ytr,gtr,Pte):
    """Inner 3-fold by business on the training fold only -> multinomial logistic calibration of the probabilities."""
    from sklearn.linear_model import LogisticRegression
    inner=np.zeros((len(ytr),3))
    for a,b in GroupKFold(3).split(Xtr,ytr,gtr):
        m=HC(**SP).fit(Xtr.iloc[a],ytr[a]); inner[b]=m.predict_proba(Xtr.iloc[b])
    lr=LogisticRegression(C=1.0,max_iter=1000).fit(calfeat(inner),ytr)
    return lr.predict_proba(calfeat(Pte))
def decide2(p,m,cands,thr):
    if m['flag']: return "FLAG","",0.9,"CLOSED_SIGNALS",9
    shown=m['shown']; best=("NO_ACTION","",float(p[1]),None,-9)
    if shown!='closed':
        ev=p[0]-p[1]-p[2]
        if ev>thr['closed']: best=("SUGGEST","closed",float(p[0]),"STATE_MODEL",ev)
    if cands:
        e,h=max(cands)
        ev=p[2]*e-0.5*p[1]-p[0]
        if ev>thr['open'] and ev>best[4]: best=("SUGGEST",h,float(p[2]*e),"CAND",ev)
    return best
def evaluate(D,P,byrow,thr,season):
    preds={}
    for j,i in enumerate(D['dev']):
        m=D['meta'][i]; a,h,c,_,_=decide2(P[j],m,byrow.get(i,[]),thr)
        if a!='NO_ACTION': preds[(m['entity_id'],m['date'])]=(a,E.norm(h),c)
    return E.score(preds,__import__('harness').LP[season])
def sweep(D,P,byrow,season):
    res=[]
    for tc in (0,0.1,0.2,0.3,0.4):
        for to in (-0.1,0,0.05,0.1,0.2,0.3):
            r=evaluate(D,P,byrow,{'closed':tc,'open':to},season); res.append((r['score_0_100'],tc,to,r['harmful_suggestions'],r['recall_exact']))
    return sorted(res,reverse=True)
if __name__=="__main__":
    import time;t=time.time()
    if os.environ.get('REPREP')=='1':
        D6=prep(2026); D5=prep(2025); pickle.dump((D6,D5),open('/tmp/t403_D.pkl','wb'))
    else: D6,D5=pickle.load(open('/tmp/t403_D.pkl','rb'))
    for name,ex6,ex5 in [(("own season",None,None),("+other season",D5,D6))[int(os.environ.get("EXTRA","0"))]]:
        P6,b6=oof(D6,ex6); P5,b5=oof(D5,ex5)
        s6=sweep(D6,P6,b6,2026); s5=sweep(D5,P5,b5,2025)
        # honest: thr picked on other season
        best5=s5[0]; best6=s6[0]
        r6=evaluate(D6,P6,b6,{'closed':best5[1],'open':best5[2]},2026)
        r5=evaluate(D5,P5,b5,{'closed':best6[1],'open':best6[2]},2025)
        print(name,'2026 OOF (thr from 2025):',r6['score_0_100'],r6['precision_exact'],r6['recall_exact'],r6['harmful_suggestions'],'| 2025 OOF (thr from 2026):',r5['score_0_100'],'| best-in-sample 26/25:',best6[:3],best5[:3],flush=True)
        print('  ',r6['breakdown'])
        pickle.dump((P6,b6,P5,b5),open(f'/tmp/t403_oof_{os.environ.get("TAG",name[0])}.pkl','wb'))
