import os,sys,pickle,numpy as np
import model as M
from features import KIT
sys.path.insert(0,KIT+'/evaluation'); import evaluate as E
from sklearn.model_selection import GroupKFold
X,meta=pickle.load(open('/tmp/fonecta_X2026_1.pkl','rb'))
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
for tc in [0.3,0.5,0.7,0.9]:
  for to in [0.2,0.4,0.6]:
    preds={}
    for j,i in enumerate(dev):
        a,h,c,_=M.decide(oof[j],meta[i],cs[j],{'closed':tc,'open':to})
        if a!='NO_ACTION': preds[(meta[i]['entity_id'],meta[i]['date'])]=(a,E.norm(h),c)
    r=E.score(preds,lp); print(tc,to,r['score_0_100'],r['precision_exact'],r['recall_exact'],r['harmful_suggestions'],r['search_views_protected_pct'])
