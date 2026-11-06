import os,sys,pickle,numpy as np
os.environ.setdefault("LOKY_MAX_CPU_COUNT","8")
import model as M
from features import KIT
sys.path.insert(0,KIT+'/evaluation'); import evaluate as E
from sklearn.model_selection import GroupKFold
cache='/tmp/fonecta_X2026.pkl'
if os.path.exists(cache): X,meta=pickle.load(open(cache,'rb'))
else:
    b,X,meta=M.build(2026); pickle.dump((X,meta),open(cache,'wb'))
L=M.labels(2026)
dev=[i for i,m in enumerate(meta) if (m['entity_id'],m['date']) in L]
y=np.array([M.y_state(L[(meta[i]['entity_id'],meta[i]['date'])],meta[i]['shown']) for i in dev])
g=[meta[i]['entity_id'] for i in dev]
oof=np.zeros((len(dev),3)); cs={}
for tr,te in GroupKFold(5).split(dev,y,g):
    m=M.fit(X.iloc[[dev[i] for i in tr]],y[tr]); oof[te]=m.predict_proba(X.iloc[[dev[i] for i in te]])
    c=M.cand_stats([dev[i] for i in tr],meta,L)
    for i in te: cs[i]=c
lp=os.path.join(KIT,'labels','dev_labels_2026.csv')
for tc in [0.0,0.1,0.2,0.3,0.4]:
  for to in [0.0,0.1,0.2,0.3]:
    thr={'closed':tc,'open':to}; preds={}
    for j,i in enumerate(dev):
        a,h,c,_=M.decide(oof[j],meta[i],cs[j],thr)
        if a!='NO_ACTION': preds[(meta[i]['entity_id'],meta[i]['date'])]=(a,E.norm(h),c)
    r=E.score(preds,lp); print(tc,to,r['score_0_100'],r['precision_exact'],r['recall_exact'],r['harmful_suggestions'])
