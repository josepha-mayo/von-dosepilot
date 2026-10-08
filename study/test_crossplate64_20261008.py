import sys
import numpy as np
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_crossplate64_20261008 import duplicate_plan,plan_validation,paid
r=np.random.default_rng(123)
cat=SimpleNamespace(native_ids=np.array(["q"+str(i) for i in range(72)]),native_target_indices=np.repeat(np.arange(24),3),target_ids=np.array(["t"+str(i) for i in range(24)]),concentrations=np.tile([1,10,100],24))
sel=[];own=[];plate=[]
for t in range(24):
 q=list(range(3*t,3*t+(3 if t<16 else 2)))
 sel+=q;own+=[t]*len(q)
 plate+=([t%2,1-t%2,t%2] if t<16 else [0,1])
full=dict(selected_native_indices=sel,coordinate_target_indices=own,orientation_A_plate_indices=plate,orientation_B_plate_indices=[1-z for z in plate])
x=r.normal(size=(40,72,2));y=r.normal(size=(40,24));p=np.array(["p"+str(i//2) for i in range(40)])
for k in (0,4,8):
 plan=duplicate_plan(full,x,y,p,cat,k)
 assert plan_validation(plan,cat,k)
 a=paid(x,plan,"A");b=paid(x,plan,"B")
 assert a.shape==b.shape==(40,64)
 print("PASS",k,len(set(plan["selected_native_indices"])),flush=True)
