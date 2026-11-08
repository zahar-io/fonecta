import os,sys,pickle
import model as M
from features import KIT
sys.path.insert(0,KIT+'/evaluation'); import evaluate as E
LP={2026:os.path.join(KIT,'labels','dev_labels_2026.csv'),2025:os.path.join(KIT,'labels','dev_labels_2025_backtest.csv')}
def load(s):
    X,meta=pickle.load(open(f'/tmp/fonecta_brain/X{s}.pkl','rb'))
    if os.environ.get('XF','1')=='1':
        import pandas as pd
        Xe=pickle.load(open(f'/tmp/fonecta_brain/Xe{s}.pkl','rb')); X=pd.concat([X.reset_index(drop=True),Xe],axis=1)
        if os.path.exists(f'/tmp/fonecta_brain/Xa{s}.pkl') and os.environ.get('XA','1')=='1':
            X=pd.concat([X,pickle.load(open(f'/tmp/fonecta_brain/Xa{s}.pkl','rb'))],axis=1)
        if os.path.exists(f'/tmp/fonecta_brain/Xb{s}.pkl') and os.environ.get('XB','1')=='1':
            F,C=pickle.load(open(f'/tmp/fonecta_brain/Xb{s}.pkl','rb')); X=pd.concat([X,F],axis=1)
            for m,c in zip(meta,C): m['cands'].update(c)
        if os.path.exists(f'/tmp/fonecta_brain/Xc{s}.pkl') and os.environ.get('XC','1')=='1':
            F=pickle.load(open(f'/tmp/fonecta_brain/Xc{s}.pkl','rb'))
            if os.environ.get('XCDROP'): F=F.drop(columns=[c for c in F.columns if any(c.startswith(p) for p in os.environ['XCDROP'].split(','))])
            X=pd.concat([X,F],axis=1)
        if os.path.exists(f'/tmp/fonecta_brain/Xd{s}.pkl') and os.environ.get('XD','0')=='1':
            X=pd.concat([X,pickle.load(open(f'/tmp/fonecta_brain/Xd{s}.pkl','rb'))],axis=1)
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
