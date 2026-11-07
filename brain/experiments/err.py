import os,sys,pickle,numpy as np,collections
import model as M
X,meta=pickle.load(open('/tmp/fonecta_X2026.pkl','rb'))
L=M.labels(2026)
c=collections.Counter(); c2=collections.Counter()
for i,m in enumerate(meta):
    lab=L.get((m['entity_id'],m['date']))
    if not lab or lab['expected_action']!='SUGGEST': continue
    t=lab['truth_hours']
    if t=='closed': c['closed_truth']+=1; continue
    has=[k for k,v in m['cands'].items() if v==t]
    c['open_other' if t!=m['shown'] else 'open_same?']+=1
    c2[tuple(sorted(has)) if has else 'NONE']+=1
    if not has and c['ex']<15:
        c['ex']+=1; print(m['entity_id'],m['date'],m['key'],'shown',m['shown'],'truth',t,m['cands'])
print(c); print(c2.most_common(20))
