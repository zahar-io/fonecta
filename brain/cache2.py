import pickle,time
import model as M, features_x as FX
for s in (2026,2025):
    t=time.time(); b,X,meta=M.build(s)
    Xe=FX.extra(b,meta); del X
    pickle.dump(Xe,open(f'/tmp/fonecta_brain/Xe{s}.pkl','wb')); print(s,Xe.shape,time.time()-t,flush=True)
    print(Xe.describe().T[['count','mean']])
