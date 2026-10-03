"""Residual-alignment-weighted additive kernel for one frozen TRAIN study."""
from __future__ import annotations
import numpy as np
from additive_kernel import AdditiveKernel


class AlignedAdditiveKernel(AdditiveKernel):
    """Fit one nonnegative, globally shared weight per drug-group kernel."""

    def __init__(self, z, residual, weights, owner, eta):
        if eta not in (0.0, 0.5, 1.0):
            raise ValueError("Unregistered alignment exponent")
        self.eta = float(eta)
        self.alignments = None
        self.group_energy = None
        self.group_scale = None
        self.response_gram_norm = None
        super().__init__(z, residual, weights, owner)

    @staticmethod
    def _center_square(kernel, weights):
        right = kernel @ weights
        left = weights @ kernel
        grand = float(left @ weights)
        return kernel - right[:, None] - left[None, :] + grand

    def gaussian_groups(self, query):
        result = []
        for group in self.groups:
            a, b = query[:, group], self.z[:, group]
            distance = np.maximum(
                np.sum(a * a, axis=1)[:, None]
                + np.sum(b * b, axis=1)[None, :]
                - 2 * a @ b.T,
                0.0,
            )
            result.append(np.exp(-distance / (2 * len(group))))
        return result

    def _fit_scales(self, train_groups):
        sw = np.sqrt(self.w)
        centered_residual = self.residual - self.w @ self.residual
        response_gram = (
            sw[:, None]
            * (centered_residual @ centered_residual.T / self.residual.shape[1])
            * sw[None, :]
        )
        response_norm = float(np.linalg.norm(response_gram))
        self.response_gram_norm = response_norm
        alignments, energy = [], []
        for kernel in train_groups:
            centered = self._center_square(kernel, self.w)
            weighted = sw[:, None] * centered * sw[None, :]
            denominator = float(np.linalg.norm(weighted) * response_norm)
            alignment = 0.0 if denominator <= 1e-14 else max(
                0.0, float(np.sum(weighted * response_gram) / denominator)
            )
            alignments.append(alignment)
            energy.append(float(np.trace(weighted)))
        alignments = np.asarray(alignments)
        energy = np.asarray(energy)
        widths = np.asarray([len(group) for group in self.groups], dtype=float)
        if not np.isfinite(alignments).all() or not np.isfinite(energy).all():
            raise ValueError("Nonfinite alignment statistic")
        if (energy < -1e-10).any():
            raise ValueError("Negative centered kernel energy")
        if self.eta == 0.0:
            scales = np.ones(len(self.groups))
        elif response_norm <= 1e-14:
            # Deterministic invented-fixture fallback; real fitting responses
            # are required to have nonzero energy by the frozen runner.
            scales = np.ones(len(self.groups))
        else:
            score = np.maximum(alignments, 1e-12) ** self.eta
            numerator = float(np.sum(widths * energy))
            denominator = float(np.sum(widths * energy * score))
            if (not np.isfinite(numerator) or not np.isfinite(denominator)
                    or numerator <= 1e-14 or denominator <= 1e-14):
                raise ValueError("Degenerate alignment normalization")
            scales = score * numerator / denominator
        if not np.isfinite(scales).all() or (scales < 0).any():
            raise ValueError("Invalid group scales")
        self.alignments = alignments
        self.group_energy = energy
        self.group_scale = scales

    def raw_cross(self, query):
        query = np.asarray(query, float)
        if (query.ndim != 2 or query.shape[1] != 64
                or not np.isfinite(query).all()):
            raise ValueError("Exactly 64 finite purchased coordinates required")
        groups = self.gaussian_groups(query)
        if self.group_scale is None:
            if not np.array_equal(query, self.z):
                raise ValueError("Training alignment must precede queries")
            self._fit_scales(groups)
        result = query @ self.z.T
        for group, scale, kernel in zip(self.groups, self.group_scale, groups):
            result += len(group) * scale * kernel
        return result

    def arrays(self, coefficients):
        return dict(
            super().arrays(coefficients),
            alignment_eta=np.asarray(self.eta),
            group_alignments=self.alignments,
            group_energy=self.group_energy,
            group_scale=self.group_scale,
            response_gram_norm=np.asarray(self.response_gram_norm),
        )
