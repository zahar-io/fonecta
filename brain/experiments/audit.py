import pickle,collections,numpy as np,sys,os
os.environ['FLAGQ']='-1'
sys.argv=['x','f3,f3c,f3s,f3x']
import ens, v2
D=ens.D6;P=ens.P6;b=ens.b6;thr={'closed':0.3,'open':0.1}
loss=collections.Counter();cnt=collections.Counter()
for j,i in enumerate(D['dev']):
    m=D['meta'][i];lab=D['L'][(m['entity_id'],m['date'])]
    a,h,c,bs,ev=v2.decide2(P[j],m,b.get(i,[]),thr)
    t=lab['truth_hours'];exp=lab['expected_action']
    ly=m['key']
    if exp=='SUGGEST':
        if a=='SUGGEST': p=v2.pts(v2.E.norm(h),t)
        elif a=='FLAG': p=.05
        else: p=0
        lost=1-p; cat=('chg',lab['mismatch_type'][:12],a if a!='SUGGEST' else ('ok' if p==1 else ('wrongstate' if p<0 else 'offhrs')),ly)
    elif exp=='FLAG': lost=1-(1 if a=='FLAG' else (0.3 if h=='closed' else (0 if a=='NO_ACTION' else -1))); cat=('perm',a)
    else:
        if a=='SUGGEST': lost=(1 if (v2.E.norm(h)=='closed')!=(lab['displayed_hours_at_snapshot']=='closed') else (0.1 if v2.E.norm(h)==lab['displayed_hours_at_snapshot'] else 0.5)); cat=('noact','sug_'+('closed' if h=='closed' else 'open'),ly)
        else: lost=0; cat=('noact','ok')
    loss[cat]+=lost; cnt[cat]+=1
tot=sum(loss.values())
for k,v in loss.most_common(20): print(f"{v:7.1f} pts ({100*v/5398:.1f} score) n={cnt[k]} {k}")
