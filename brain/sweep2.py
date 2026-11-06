import os,sys,pickle,numpy as np
import model as M
from features import KIT
sys.path.insert(0,KIT+'/evaluation'); import evaluate as E
from sklearn.model_selection import GroupKFold
def get(season):
    c=f'/tmp/fonecta_X{season}_{os.environ.get("OWN_OFFSET","1")}.pkl'
    if os.path.exists(c): return pickle.load(open(c,'rb'))
    b,X,meta=M.build(season); pickle.dump((X,meta),open(c,'wb')); return X,meta
X6,m6=get(2026); X5,m5=get(2025)
L6,L5=M.labels(2026),M.labels(2025)
import pandas as pd
d6=[i for i,m in enumerate(m6) if (m['entity_id'],m['date']) in L6]
d5=[i for i,m in enumerate(m5) if (m['entity_id'],m['date']) in L5]
y6=np.array([M.y_state(L6[(m6[i]['entity_id'],m6[i]['date'])],m6[i]['shown']) for i in d6])
y5=np.array([M.y_state(L5[(m5[i]['entity_id'],m5[i]['date'])],m5[i]['shown']) for i in d5])
use5=os.environ.get("USE2025","1")=="1"
ents=sorted(set(m6[i]['entity_id'] for i in d6)); rng=np.random.RandomState(0); fold={e:k%5 for k,e in enumerate(rng.permutation(ents))}
oof=np.zeros((len(d6),3)); cs={}
for k in range(5):
    tr6=[j for j,i in enumerate(d6) if fold[m6[i]['entity_id']]!=k]; te6=[j for j,i in enumerate(d6) if fold[m6[i]['entity_id']]==k]
    Xtr=X6.iloc[[d6[j] for j in tr6]]; ytr=y6[tr6]
    if use5:
        tr5=[j for j,i in enumerate(d5) if fold.get(m5[i]['entity_id'],-1)!=k]
        Xtr=pd.concat([Xtr,X5.iloc[[d5[j] for j in tr5]]]); ytr=np.concatenate([ytr,y5[tr5]])
        for c in M.CAT: Xtr[c]=Xtr[c].astype(str).astype('category')
    Xte=X6.iloc[[d6[j] for j in te6]].copy()
    for c in M.CAT: Xte[c]=pd.Categorical(Xte[c].astype(str),categories=Xtr[c].cat.categories)
    m=M.fit(Xtr,ytr); oof[te6]=m.predict_proba(Xte)
    c=M.cand_stats([d6[j] for j in tr6],m6,L6)
    for j in te6: cs[j]=c
lp=os.path.join(KIT,'labels','dev_labels_2026.csv')
for tc in [0.2,0.3,0.4,0.5]:
  for to in [0.1,0.2,0.3]:
    preds={}
    for j,i in enumerate(d6):
        a,h,c,_=M.decide(oof[j],m6[i],cs[j],{'closed':tc,'open':to})
        if a!='NO_ACTION': preds[(m6[i]['entity_id'],m6[i]['date'])]=(a,E.norm(h),c)
    r=E.score(preds,lp); print(tc,to,r['score_0_100'],r['precision_exact'],r['recall_exact'],r['harmful_suggestions'],r['breakdown'].get('spam_wrong_hours'))
