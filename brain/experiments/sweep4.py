import os,sys,pickle,numpy as np
import model as M
from features import KIT
sys.path.insert(0,KIT+'/evaluation'); import evaluate as E
from sklearn.model_selection import GroupKFold
from sklearn.ensemble import HistGradientBoostingClassifier as H
X,meta=pickle.load(open('/tmp/fonecta_X2026_0.pkl','rb'))
L=M.labels(2026)
dev=[i for i,m in enumerate(meta) if (m['entity_id'],m['date']) in L]
y=np.array([M.y_state(L[(meta[i]['entity_id'],meta[i]['date'])],meta[i]['shown']) for i in dev])
g=[meta[i]['entity_id'] for i in dev]
lp=os.path.join(KIT,'labels','dev_labels_2026.csv')
for name,kw in [("base",dict(max_iter=300,learning_rate=0.06,max_leaf_nodes=31)),
                ("slow",dict(max_iter=700,learning_rate=0.03,max_leaf_nodes=31,l2_regularization=1.0)),
                ("small",dict(max_iter=500,learning_rate=0.05,max_leaf_nodes=15,min_samples_leaf=40)),
                ("big",dict(max_iter=400,learning_rate=0.05,max_leaf_nodes=63,min_samples_leaf=20))]:
    oof=np.zeros((len(dev),3)); cs={}
    for tr,te in GroupKFold(5).split(dev,y,g):
        m=H(categorical_features="from_dtype",random_state=0,**kw).fit(X.iloc[[dev[i] for i in tr]],y[tr]); oof[te]=m.predict_proba(X.iloc[[dev[i] for i in te]])
        c=M.cand_stats([dev[i] for i in tr],meta,L)
        for i in te: cs[i]=c
    best=None
    for tc in [0.1,0.2,0.3]:
      for to in [0.2,0.3,0.4]:
        preds={}
        for j,i in enumerate(dev):
            a,h,c,_=M.decide(oof[j],meta[i],cs[j],{'closed':tc,'open':to})
            if a!='NO_ACTION': preds[(meta[i]['entity_id'],meta[i]['date'])]=(a,E.norm(h),c)
        r=E.score(preds,lp)
        if not best or r['score_0_100']>best[0]: best=(r['score_0_100'],tc,to,r['harmful_suggestions'],r['recall_exact'])
    print(name,best,flush=True)
