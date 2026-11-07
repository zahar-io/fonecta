import pickle,sys,os,numpy as np,collections
import v2
D6,D5=pickle.load(open('/tmp/fonecta_brain/D.pkl','rb'))
tags=sys.argv[1].split(',')
FLAGQ=float(os.environ.get('FLAGQ','-1'))
def load(tags):
    Ps6=[];Ps5=[];B6=collections.defaultdict(lambda:collections.defaultdict(list));B5=collections.defaultdict(lambda:collections.defaultdict(list))
    for t in tags:
        P6,b6,P5,b5=pickle.load(open(f'/tmp/fonecta_brain/oof_{t}.pkl','rb')); Ps6.append(P6);Ps5.append(P5)
        for B,b in ((B6,b6),(B5,b5)):
            for i,l in b.items():
                for e,h in l: B[i][h].append(e)
    f=lambda B:{i:[(np.mean(v),h) for h,v in d.items()] for i,d in B.items()}
    return np.mean(Ps6,0),f(B6),np.mean(Ps5,0),f(B5)
P6,b6,P5,b5=load(tags)
_dec=v2.decide2
def dec(p,m,c,thr):
    r=_dec(p,m,c,thr)
    if r[0]=='NO_ACTION' and FLAGQ>0 and (p[0] if m['shown']=='closed' else p[1])<FLAGQ: return ("FLAG","",0.5,"UNSURE",0)
    return r
v2.decide2=dec
s6=v2.sweep(D6,P6,b6,2026); s5=v2.sweep(D5,P5,b5,2025)
r6=v2.evaluate(D6,P6,b6,{'closed':s5[0][1],'open':s5[0][2]},2026)
r5=v2.evaluate(D5,P5,b5,{'closed':s6[0][1],'open':s6[0][2]},2025)
print(tags,'FLAGQ',FLAGQ,'2026:',r6['score_0_100'],r6['precision_exact'],r6['recall_exact'],r6['harmful_suggestions'],'2025:',r5['score_0_100'],'thr26<-25',s5[0][1:3],'insample',s6[0][0],s5[0][0])
if os.environ.get('WRITE'):
    import csv
    for D,P,b,s,t in ((D6,P6,b6,2026,{'closed':s5[0][1],'open':s5[0][2]}),(D5,P5,b5,2025,{'closed':s6[0][1],'open':s6[0][2]})):
        p=os.path.join(v2.M.ROOT,'outputs',f'cv_dev_{s}.csv' if s==2026 else 'cv_backtest_2025.csv')
        with open(p,'w',newline='',encoding='utf-8') as g:
            w=csv.writer(g); w.writerow(['entity_id','date','action','hours','confidence'])
            for j,i in enumerate(D['dev']):
                m=D['meta'][i]; a,h,c,_,_=v2.decide2(P[j],m,b.get(i,[]),t)
                if a!='NO_ACTION': w.writerow([m['entity_id'],m['date'],a,h,round(c,3)])
        print('wrote',p,t)
