import os,sys,pickle,numpy as np,collections
import model as M
from features import KIT
sys.path.insert(0,KIT+'/evaluation'); import evaluate as E
from sklearn.model_selection import GroupKFold
LP={2026:os.path.join(KIT,'labels','dev_labels_2026.csv'),2025:os.path.join(KIT,'labels','dev_labels_2025_backtest.csv')}
def load(s):
    X,meta=pickle.load(open(f'/tmp/t403_X{s}.pkl','rb'))
    if os.environ.get('XF','1')=='1':
        import pandas as pd
        Xe=pickle.load(open(f'/tmp/t403_Xe{s}.pkl','rb')); X=pd.concat([X.reset_index(drop=True),Xe],axis=1)
        if os.path.exists(f'/tmp/t403_Xa{s}.pkl') and os.environ.get('XA','1')=='1':
            X=pd.concat([X,pickle.load(open(f'/tmp/t403_Xa{s}.pkl','rb'))],axis=1)
        if os.path.exists(f'/tmp/t403_Xb{s}.pkl') and os.environ.get('XB','1')=='1':
            F,C=pickle.load(open(f'/tmp/t403_Xb{s}.pkl','rb')); X=pd.concat([X,F],axis=1)
            for m,c in zip(meta,C): m['cands'].update(c)
        add_rev_cands(X,meta)
    L=M.labels(s)
    dev=[i for i,m in enumerate(meta) if (m['entity_id'],m['date']) in L]
    return X,meta,L,dev
def add_rev_cands(X,meta):
    from features import span
    if 'rv_early_min' not in X: return
    for v,m in zip(X['rv_early_min'].values,meta):
        if v==v and m['shown']!='closed':
            s=span(m['shown'])
            if s and s[0]<v:
                m['cands']['rev_close']=f"{s[0]//60%24:02d}:{s[0]%60:02d}-{int(v)//60%24:02d}:00"
def score(preds,s): 
    r=E.score(preds,LP[s]); return r
def oof_run(s,fitf=M.fit,decide=M.decide,thr={'closed':0.2,'open':0.3}):
    X,meta,L,dev=load(s)
    y=np.array([M.y_state(L[(meta[i]['entity_id'],meta[i]['date'])],meta[i]['shown']) for i in dev])
    g=[meta[i]['entity_id'] for i in dev]
    oof=np.zeros((len(dev),3)); cs={}
    for tr,te in GroupKFold(5).split(dev,y,g):
        m=fitf(X.iloc[[dev[i] for i in tr]],y[tr]); oof[te]=m.predict_proba(X.iloc[[dev[i] for i in te]])
        c=M.cand_stats([dev[i] for i in tr],meta,L)
        for i in te: cs[i]=c
    preds={}
    for j,i in enumerate(dev):
        a,h,c,_=decide(oof[j],meta[i],cs[j],thr)
        if a!='NO_ACTION': preds[(meta[i]['entity_id'],meta[i]['date'])]=(a,E.norm(h),c)
    return score(preds,s),oof,cs
if __name__=='__main__':
    for s in (2026,2025):
        r,_,_=oof_run(s); print(s,r['score_0_100'],r['precision_exact'],r['recall_exact'],r['harmful_suggestions'],r['breakdown'])
