import pickle,time
import model as M, an_llr
for s in (2026,2025):
    t=time.time(); b,X,meta=M.build(s)
    A=an_llr.build(b,meta); pickle.dump(A,open(f'/tmp/fonecta_brain/Xa{s}.pkl','wb')); print(s,A.shape,time.time()-t,flush=True)
    if s==2025: break
