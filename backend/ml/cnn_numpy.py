"""Small 1-D convolutional network written in numpy, trained here and exported to ONNX.

Input: BANDS x FRAMES log-mel window (bands are the channels, convolution runs over time).

    Conv1D(BANDS -> C1, k) -> ReLU -> MaxPool(2)
    -> Conv1D(C1 -> C2, k) -> ReLU -> GlobalAveragePool
    -> Dense(C2 -> classes) -> Softmax

Back-propagation and the Adam optimiser are written out by hand so the network needs no
extra libraries; the exported graph uses only standard ONNX operators and runs with
onnxruntime on CPU.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


def _im2col(x: np.ndarray, k: int) -> np.ndarray:
    """(N, C, T) -> (N, T, C*k) with 'same' zero padding (columns ordered channel-major)."""
    pad = k // 2
    xp = np.pad(x, ((0, 0), (0, 0), (pad, pad)))
    n, c, t = x.shape
    idx = np.arange(t)[:, None] + np.arange(k)[None, :]  # T x k
    cols = xp[:, :, idx]  # N, C, T, k
    return cols.transpose(0, 2, 1, 3).reshape(n, t, c * k)


def _col2im(dcols: np.ndarray, shape: tuple[int, int, int], k: int) -> np.ndarray:
    n, c, t = shape
    pad = k // 2
    d = dcols.reshape(n, t, c, k).transpose(0, 2, 1, 3)  # N, C, T, k
    dxp = np.zeros((n, c, t + 2 * pad))
    for j in range(k):
        dxp[:, :, j : j + t] += d[:, :, :, j]
    return dxp[:, :, pad : pad + t]


@dataclass
class Conv1DNet:
    in_channels: int
    classes: int
    c1: int = 16
    c2: int = 24
    k: int = 5
    seed: int = 0
    params: dict[str, np.ndarray] = field(init=False)

    def __post_init__(self) -> None:
        rng = np.random.default_rng(self.seed)

        def he(*shape: int, fan_in: int) -> np.ndarray:
            return rng.normal(0, np.sqrt(2.0 / fan_in), shape)

        self.params = {
            "w1": he(self.c1, self.in_channels, self.k, fan_in=self.in_channels * self.k),
            "b1": np.zeros(self.c1),
            "w2": he(self.c2, self.c1, self.k, fan_in=self.c1 * self.k),
            "b2": np.zeros(self.c2),
            "w3": he(self.classes, self.c2, fan_in=self.c2),
            "b3": np.zeros(self.classes),
        }

    # -- forward / backward -------------------------------------------------------------
    def forward(self, x: np.ndarray, keep: bool = False):
        p, k = self.params, self.k
        cols1 = _im2col(x, k)
        z1 = (cols1 @ p["w1"].reshape(self.c1, -1).T + p["b1"]).transpose(0, 2, 1)  # N,C1,T
        a1 = np.maximum(z1, 0)
        n, c1, t = a1.shape
        t2 = t // 2
        pooled_in = a1[:, :, : t2 * 2].reshape(n, c1, t2, 2)
        arg = pooled_in.argmax(axis=3)
        m1 = pooled_in.max(axis=3)  # N,C1,T/2
        cols2 = _im2col(m1, k)
        z2 = (cols2 @ p["w2"].reshape(self.c2, -1).T + p["b2"]).transpose(0, 2, 1)  # N,C2,T/2
        a2 = np.maximum(z2, 0)
        g = a2.mean(axis=2)  # N,C2
        logits = g @ p["w3"].T + p["b3"]
        logits -= logits.max(axis=1, keepdims=True)
        probs = np.exp(logits)
        probs /= probs.sum(axis=1, keepdims=True)
        if keep:
            self._cache = (x, cols1, z1, a1, arg, m1, cols2, z2, a2, g)
        return probs

    def backward(self, probs: np.ndarray, y: np.ndarray) -> dict[str, np.ndarray]:
        x, cols1, z1, a1, arg, m1, cols2, z2, a2, g = self._cache
        p, k = self.params, self.k
        n = len(y)
        d_logits = probs.copy()
        d_logits[np.arange(n), y] -= 1
        d_logits /= n
        grads = {"w3": d_logits.T @ g, "b3": d_logits.sum(axis=0)}
        dg = d_logits @ p["w3"]  # N,C2
        t2 = a2.shape[2]
        da2 = np.repeat(dg[:, :, None], t2, axis=2) / t2
        dz2 = da2 * (z2 > 0)
        dz2_t = dz2.transpose(0, 2, 1)  # N,T2,C2
        grads["w2"] = np.einsum("ntf,ntc->fc", dz2_t, cols2).reshape(p["w2"].shape)
        grads["b2"] = dz2.sum(axis=(0, 2))
        dm1 = _col2im(dz2_t @ p["w2"].reshape(self.c2, -1), m1.shape, k)
        n_, c1, t = a1.shape
        t2p = t // 2
        dpool = np.zeros((n_, c1, t2p, 2))
        np.put_along_axis(dpool, arg[..., None], dm1[..., None], axis=3)
        da1 = np.zeros_like(a1)
        da1[:, :, : t2p * 2] = dpool.reshape(n_, c1, t2p * 2)
        dz1 = da1 * (z1 > 0)
        dz1_t = dz1.transpose(0, 2, 1)
        grads["w1"] = np.einsum("ntf,ntc->fc", dz1_t, cols1).reshape(p["w1"].shape)
        grads["b1"] = dz1.sum(axis=(0, 2))
        return grads

    def predict(self, x: np.ndarray) -> np.ndarray:
        return self.forward(x.astype(np.float64))

    # -- training -----------------------------------------------------------------------
    def fit(
        self,
        x: np.ndarray,
        y: np.ndarray,
        epochs: int = 25,
        batch: int = 64,
        lr: float = 3e-3,
        weight_decay: float = 1e-4,
        log=print,
    ) -> None:
        rng = np.random.default_rng(self.seed + 1)
        m = {key: np.zeros_like(v) for key, v in self.params.items()}
        v = {key: np.zeros_like(val) for key, val in self.params.items()}
        step = 0
        x = x.astype(np.float64)
        for epoch in range(epochs):
            order = rng.permutation(len(x))
            losses = []
            for start in range(0, len(x), batch):
                idx = order[start : start + batch]
                probs = self.forward(x[idx], keep=True)
                losses.append(-np.log(probs[np.arange(len(idx)), y[idx]] + 1e-9).mean())
                grads = self.backward(probs, y[idx])
                step += 1
                rate = lr * (0.5 * (1 + np.cos(np.pi * epoch / epochs)))  # cosine decay
                for key, grad in grads.items():
                    if key.startswith("w"):
                        grad = grad + weight_decay * self.params[key]
                    m[key] = 0.9 * m[key] + 0.1 * grad
                    v[key] = 0.999 * v[key] + 0.001 * grad**2
                    m_hat = m[key] / (1 - 0.9**step)
                    v_hat = v[key] / (1 - 0.999**step)
                    self.params[key] -= rate * m_hat / (np.sqrt(v_hat) + 1e-8)
            log(f"  epoch {epoch + 1:2d}/{epochs}  loss {np.mean(losses):.4f}")

    # -- export -------------------------------------------------------------------------
    def to_onnx(self, frames: int):
        from onnx import TensorProto, helper, numpy_helper

        p, k = self.params, self.k
        init = [
            numpy_helper.from_array(p[name].astype(np.float32), name)
            for name in ("w1", "b1", "w2", "b2", "w3", "b3")
        ]
        nodes = [
            helper.make_node(
                "Conv", ["features", "w1", "b1"], ["z1"], kernel_shape=[k], pads=[k // 2, k // 2]
            ),
            helper.make_node("Relu", ["z1"], ["a1"]),
            helper.make_node("MaxPool", ["a1"], ["m1"], kernel_shape=[2], strides=[2]),
            helper.make_node(
                "Conv", ["m1", "w2", "b2"], ["z2"], kernel_shape=[k], pads=[k // 2, k // 2]
            ),
            helper.make_node("Relu", ["z2"], ["a2"]),
            helper.make_node("GlobalAveragePool", ["a2"], ["g3"]),
            helper.make_node("Flatten", ["g3"], ["g"], axis=1),
            helper.make_node("Gemm", ["g", "w3", "b3"], ["logits"], transB=1),
            helper.make_node("Softmax", ["logits"], ["probabilities"], axis=1),
        ]
        graph = helper.make_graph(
            nodes,
            "sound_classifier",
            [
                helper.make_tensor_value_info(
                    "features", TensorProto.FLOAT, ["batch", self.in_channels, frames]
                )
            ],
            [
                helper.make_tensor_value_info(
                    "probabilities", TensorProto.FLOAT, ["batch", self.classes]
                )
            ],
            init,
        )
        model = helper.make_model(
            graph, opset_imports=[helper.make_opsetid("", 17)], producer_name="spacescan-ml"
        )
        model.ir_version = 8
        return model
