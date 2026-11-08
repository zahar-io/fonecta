import pickle,time,sys
import model as M, extra4
for s in (2025,2026):
    t=time.time(); b,X,meta=M.build(s)
    F=extra4.build(b,meta); pickle.dump(F,open(f'/tmp/fonecta_brain/Xc{s}.pkl','wb')); print(s,F.shape,round(time.time()-t),flush=True)
    print(F.describe().T[['count','mean','max']].to_string(),flush=True)
