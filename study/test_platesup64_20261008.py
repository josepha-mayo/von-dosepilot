import numpy as np
from run_platesup64_20261008 import AnyOutputKernel,core
rng=np.random.default_rng(20261008)
owner=np.repeat(np.arange(24),[3]*16+[2]*8)
z=rng.normal(size=(32,64))
y=rng.normal(size=(32,24))
w=np.ones(32)/32
a=core.BandwidthAdditive(z,y,w,owner,.7)
b=AnyOutputKernel(z,y,w,owner)
q=rng.normal(size=(6,64))
assert np.allclose(a.centered_cross(q),b.centered_cross(q),atol=1e-13)
assert np.allclose(a.coefficients(1.0,.3)[0],b.coefficients(1.0,.3)[0],atol=1e-13)
v=AnyOutputKernel(z,rng.normal(size=(32,48)),w,owner)
assert v.coefficients(1.0,.3)[0].shape==(32,48)
print("PASS spectral 24/48-channel agreement and 64-well shape")
