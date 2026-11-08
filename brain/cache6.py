import pickle,time
import model as M, extra5
for s in (2025,2026):
    t=time.time(); b,X,meta=M.build(s)
    F=extra5.build(b,meta); pickle.dump(F,open(f'/tmp/fonecta_brain/Xd{s}.pkl','wb')); print(s,F.shape,round(time.time()-t),flush=True)
    print(F.describe().T[['count','mean','max']].to_string(),flush=True)
