import pickle,time
import model as M, extra2
for s in (2026,2025):
    t=time.time(); b,X,meta=M.build(s)
    F,C=extra2.build(b,meta); pickle.dump((F,C),open(f'/tmp/t403_Xb{s}.pkl','wb')); print(s,F.shape,sum(len(c) for c in C),time.time()-t,flush=True)
