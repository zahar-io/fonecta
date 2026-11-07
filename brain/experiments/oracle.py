import pickle,numpy as np,v2
D6,D5=pickle.load(open('/tmp/t403_D.pkl','rb'))
P6,b6,P5,b5=pickle.load(open('/tmp/t403_oof_base.pkl','rb'))
Y=np.eye(3)[D6['y']]
for name,P in (("oracle state",Y),("model",P6)):
    r=v2.evaluate(D6,P,b6,{'closed':0.1,'open':0.1},2026); print(name,r['score_0_100'],r['breakdown'])
# oracle cand only: best candidate by true pts, with model state
import collections
tp={k:t for k,t in zip(D6['keys'],D6['tp'])}
bo={i:[(tp[(i,h)],h) for e,h in l] for i,l in b6.items()}
r=v2.evaluate(D6,P6,bo,{'closed':0.1,'open':0.1},2026); print('oracle cand',r['score_0_100'],r['breakdown'])
