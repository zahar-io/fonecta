"""v3 = v2 + fold-safe label statistics (te.py) for the state model and as hours candidates/features."""
import os,pickle,json,numpy as np,pandas as pd,time
import model as M, v2, te as TEm
from sklearn.model_selection import GroupKFold
from sklearn.ensemble import HistGradientBoostingClassifier as HC, HistGradientBoostingRegressor as HR
SP=dict(**json.loads(os.environ.get("SPX",'{"max_iter":300,"learning_rate":0.06,"max_leaf_nodes":31}')),categorical_features="from_dtype",random_state=0)
CP=dict(**json.loads(os.environ.get("CPX",'{"max_iter":300,"learning_rate":0.06,"max_leaf_nodes":31}')),categorical_features="from_dtype",random_state=0)
def info_of(X,meta,i): x=X.iloc[i]; return meta[i]['entity_id'][:2],str(x['seg']),str(x['tier'])
def fold_tables(D,te,idx,rows_info):
    X,meta=D['X'],D['meta']
    S=[];metas={}
    for i in idx:
        m=meta[i]; cc,seg,tier=rows_info[i]
        S.append(te.state_feats(m['entity_id'],cc,seg,tier,m['key']))
        m2=dict(m); m2['cands']={**m['cands'],**te.top_cands(m['entity_id'],cc,seg,tier,m['key'],m['shown'])}; metas[i]=m2
    S=pd.DataFrame(S,index=idx)
    mm=[None]*len(meta)
    for i,m2 in metas.items(): mm[i]=m2
    C,keys=v2.cand_table(X,mm,idx)
    tf=[te.cand_feats(meta[i]['entity_id'],*rows_info[i],meta[i]['key'],h,meta[i]['shown']) for i,h in keys]
    Z=pd.concat([v2.cand_X(C,X),pd.DataFrame(tf)],axis=1)
    Zs=S.loc[C['row'].values].reset_index(drop=True)
    Z=pd.concat([Z,Zs],axis=1)
    Xs=pd.concat([X.iloc[idx].reset_index(drop=True),S.reset_index(drop=True)],axis=1)
    return Xs,Z,keys,metas
def pts_of(D,keys):
    return np.array([v2.pts(h,v2.E.norm(D['L'][(D['meta'][i]['entity_id'],D['meta'][i]['date'])]['truth_hours'])) for i,h in keys])
def oof(D,season):
    dev=D['dev']; y=D['y']; g=np.array([D['meta'][i]['entity_id'] for i in dev])
    rows,info=TEm.load_rows(season,D['L'],D['X'],D['meta'],dev)
    rinfo={i:info_of(D['X'],D['meta'],i) for i in dev}
    yrow={i:y[j] for j,i in enumerate(dev)}
    P=np.zeros((len(dev),3)); byrow={}; metas_all={}
    for k,(tr,te_) in enumerate(GroupKFold(5).split(dev,y,g)):
        t=time.time()
        te=TEm.TE(rows,info,set(g[tr]))
        tri=[dev[j] for j in tr]; tei=[dev[j] for j in te_]
        Xtr,Ztr,ktr,_=fold_tables(D,te,tri,rinfo); Xte,Zte,kte,mte=fold_tables(D,te,tei,rinfo)
        metas_all.update(mte)
        for c in M.CAT:
            Xtr[c]=Xtr[c].astype(str).astype("category"); Xte[c]=pd.Categorical(Xte[c].astype(str),categories=Xtr[c].cat.categories)
        sm=HC(**SP).fit(Xtr,y[tr]); P[te_]=sm.predict_proba(Xte)
        if os.environ.get('CAL')=='1': P[te_]=v2.calibrate(Xtr,y[tr],g[tr],P[te_])
        msk=np.array([yrow[i]==2 for i,h in ktr])
        Za,Zb=v2.align(Ztr[msk].reset_index(drop=True),Zte)
        for c in M.CAT:
            Za[c]=Za[c].astype(str).astype("category"); Zb[c]=pd.Categorical(Zb[c].astype(str),categories=Za[c].cat.categories)
        cm=HR(**CP).fit(Za,pts_of(D,[ktr[j] for j in np.where(msk)[0]])); ec=cm.predict(Zb)
        for (i,h),e in zip(kte,ec): byrow.setdefault(i,[]).append((e,h))
        print(' fold',k,round(time.time()-t),flush=True)
    return P,byrow
if __name__=="__main__":
    D6,D5=pickle.load(open(os.environ.get('DPKL','/tmp/fonecta_brain/D.pkl'),'rb'))
    P6,b6=oof(D6,2026); P5,b5=oof(D5,2025)
    s6=v2.sweep(D6,P6,b6,2026); s5=v2.sweep(D5,P5,b5,2025)
    r6=v2.evaluate(D6,P6,b6,{'closed':s5[0][1],'open':s5[0][2]},2026)
    r5=v2.evaluate(D5,P5,b5,{'closed':s6[0][1],'open':s6[0][2]},2025)
    print('v3 2026 OOF (thr from 2025):',r6['score_0_100'],r6['precision_exact'],r6['recall_exact'],r6['harmful_suggestions'],'| 2025 OOF:',r5['score_0_100'],'| in-sample best',s6[0][:3],s5[0][:3],flush=True)
    print(r6['breakdown'])
    pickle.dump((P6,b6,P5,b5),open(f"/tmp/fonecta_brain/oof_{os.environ.get('TAG','v3')}.pkl",'wb'))
