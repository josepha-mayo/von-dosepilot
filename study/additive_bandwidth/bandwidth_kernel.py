"""Global-bandwidth variant of DosePilot's additive drug-group kernel."""
from __future__ import annotations
import numpy as np
from additive_kernel import AdditiveKernel

class BandwidthAdditive(AdditiveKernel):
    def __init__(self, z, residual, weights, owner, factor=.7):
        self.bandwidth_factor = float(factor)
        if self.bandwidth_factor <= 0 or not np.isfinite(self.bandwidth_factor):
            raise ValueError("Positive finite bandwidth factor required")
        super().__init__(z, residual, weights, owner)

    def raw_cross(self, z):
        z = np.asarray(z, float)
        if z.ndim != 2 or z.shape[1] != 64 or not np.isfinite(z).all():
            raise ValueError("64 finite query coordinates required")
        result = z @ self.z.T
        scale = self.bandwidth_factor * self.bandwidth_factor
        for group in self.groups:
            a, b = z[:, group], self.z[:, group]
            dist = np.maximum(
                (a * a).sum(1)[:, None] + (b * b).sum(1)[None, :] - 2 * a @ b.T,
                0.0,
            )
            result += len(group) * np.exp(-dist / (2 * len(group) * scale))
        return result

    def arrays(self, coefficients):
        return dict(
            super().arrays(coefficients),
            bandwidth_factor=np.asarray(self.bandwidth_factor),
        )
