"""Two fixed, positive-semidefinite extensions to DosePilot's additive kernel.

This is original research code, not a claim of a new general kernel theorem.
Every training-dependent centering vector is fitted on the supplied rows only.
"""
from __future__ import annotations
import numpy as np
from additive_kernel import AdditiveKernel


class StructuredKernel(AdditiveKernel):
    """Keep the 64-value linear component and change only nonlinear features."""
    def __init__(self, z, residual, weights, owner, kind):
        if kind not in ('pair_mix', 'mean_shape'):
            raise ValueError('Unregistered kernel family')
        self.kind = kind
        self.group_means = None
        self.group_grands = None
        self.pair_scale = None
        super().__init__(z, residual, weights, owner)

    def gaussian_groups(self, z):
        kernels = []
        for group in self.groups:
            a, b = z[:, group], self.z[:, group]
            dist = np.maximum(np.sum(a*a, 1)[:, None] +
                              np.sum(b*b, 1)[None, :] - 2*a@b.T, 0.)
            kernels.append(np.exp(-dist/(2*len(group))))
        return kernels

    def pair_components(self, z):
        """Sums/products of centered group kernels, weighted by group width."""
        raw = self.gaussian_groups(z)
        if self.group_means is None:
            if not np.array_equal(z, self.z):
                raise ValueError('Training centering must precede queries')
            self.group_means = [self.w@k for k in raw]
            self.group_grands = [float(m@self.w) for m in self.group_means]
        total = np.zeros((len(z), len(self.z)))
        squared = np.zeros_like(total)
        for group, k, m, g in zip(self.groups, raw, self.group_means, self.group_grands):
            centered = k - (k@self.w)[:, None] - m[None, :] + g
            component = len(group)*centered
            total += component
            squared += component*component
        pairs = (total*total - squared)/2
        return total, pairs

    def raw_cross(self, z):
        z = np.asarray(z, float)
        if z.ndim != 2 or z.shape[1] != 64 or not np.isfinite(z).all():
            raise ValueError('Exactly 64 finite purchased coordinates required')
        linear = z@self.z.T
        if self.kind == 'pair_mix':
            main, pairs = self.pair_components(z)
            if self.pair_scale is None:
                main_energy = float(self.w@np.diag(main))
                pair_energy = float(self.w@np.diag(pairs))
                if main_energy < -1e-10 or pair_energy < -1e-10:
                    raise ValueError('Negative kernel energy')
                # A zero pair space adds no information, not fabricated noise.
                self.pair_scale = main_energy/pair_energy if pair_energy > 1e-14 else 0.
            return linear + .5*main + .5*self.pair_scale*pairs
        result = linear.copy()
        for group in self.groups:
            a, b = z[:, group], self.z[:, group]
            am, bm = a.mean(1), b.mean(1)
            mean_distance = (am[:, None]-bm[None, :])**2
            ac, bc = a-am[:, None], b-bm[:, None]
            contrast_distance = np.maximum(np.sum(ac*ac, 1)[:, None] +
                                           np.sum(bc*bc, 1)[None, :] - 2*ac@bc.T, 0.)
            result += len(group)/2*(np.exp(-mean_distance/2) +
                       np.exp(-contrast_distance/(2*(len(group)-1))))
        return result

    def arrays(self, coefficients):
        arrays = dict(super().arrays(coefficients), structured_kind=np.asarray(self.kind))
        if self.kind == 'pair_mix':
            arrays.update(group_means=np.stack(self.group_means),
                          group_grands=np.asarray(self.group_grands), pair_scale=self.pair_scale)
        return arrays
