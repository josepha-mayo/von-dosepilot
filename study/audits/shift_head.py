"""One explicit affine-response constraint on the unchanged R13 paid inputs.

At strength 1, each own-drug head has raw coefficients summing to one.
Consequently shifting all that head's paid values by delta shifts its output
by delta. This is an algebraic property, not validated laboratory transport.
"""
from __future__ import annotations
import numpy as np
from coverage_methods import CoveragePredictor, TARGETS
from sparse_methods import LAMBDAS

STRENGTHS = (0., .5, 1.)

class ShiftConstrainedPredictor(CoveragePredictor):
    def __init__(self, context, plan, lam, strength):
        if strength not in STRENGTHS:
            raise ValueError('Unregistered constraint strength')
        super().__init__(context, plan, lam)
        self.strength = float(strength)
        if strength == 0:
            return
        for target in range(TARGETS):
            cols = np.flatnonzero(self.feature_mask[target])
            h = context.cxx[np.ix_(cols, cols)] + lam*np.eye(len(cols))
            a = 1. / self.scale_x[cols]
            direction = np.linalg.solve(h, a)
            denominator = float(a @ direction)
            if not np.isfinite(denominator) or denominator <= 0:
                raise ValueError('Invalid constrained quadratic system')
            unconstrained = self.beta[cols, target].copy()
            correction = direction*(1. - a @ unconstrained)/denominator
            self.beta[cols, target] = unconstrained + strength*correction
        if not np.isfinite(self.beta).all():
            raise ValueError('Nonfinite constrained coefficients')

    def arrays(self):
        return {**super().arrays(), 'constraint_strength':np.asarray(self.strength)}
