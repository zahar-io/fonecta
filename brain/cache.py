import pickle,time
import model as M
for s in (2026,2025):
    t=time.time(); b,X,meta=M.build(s)
    pickle.dump((X,meta),open(f'/tmp/fonecta_brain/X{s}.pkl','wb')); print(s,X.shape,time.time()-t,flush=True)
