"""
Module 3b: MLP with Dropout Risk Classifiers (Cost & Delay).
Pure NumPy multi-layer perceptron with ReLU hidden layers, inverted-dropout
regularization during training, sigmoid output with binary cross-entropy, and
Adam optimization. Trained and evaluated alongside the XGBoost classifiers for
direct comparison in GroupKFold cross-validation on project_id.
"""

import numpy as np


class MLPDropoutClassifier:
    """
    Two-hidden-layer MLP with inverted dropout for binary classification.

    StandardScale input features are learned internally (fit), so raw feature
    DataFrames can be passed directly to fit / predict_proba.
    """

    def __init__(
        self,
        hidden_sizes=(64, 32),
        dropout_rate=0.3,
        learning_rate=0.01,
        epochs=60,
        batch_size=64,
        random_state=42,
    ):
        self.hidden_sizes = tuple(hidden_sizes)
        self.dropout_rate = dropout_rate
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.random_state = random_state

        self.scaler_mean_ = None
        self.scaler_scale_ = None
        self.weights_ = []
        self.biases_ = []
        self.trained = False

    def _init_params(self, n_features: int) -> None:
        rng = np.random.RandomState(self.random_state)
        sizes = [n_features] + list(self.hidden_sizes) + [1]
        self.weights_ = []
        self.biases_ = []
        for i in range(len(sizes) - 1):
            fan_in = sizes[i]
            fan_out = sizes[i + 1]
            # He initialization scaled for dropout
            limit = np.sqrt(6.0 / (fan_in + fan_out))
            self.weights_.append(
                rng.uniform(-limit, limit, size=(fan_in, fan_out)).astype(np.float64)
            )
            self.biases_.append(np.zeros((1, fan_out), dtype=np.float64))

    def _loss(self, y_true: np.ndarray, y_pred: np.ndarray) -> float:
        eps = 1e-12
        return float(-np.mean(y_true * np.log(y_pred + eps) + (1 - y_true) * np.log(1 - y_pred + eps)))

    def fit(self, X, y) -> "MLPDropoutClassifier":
        """Standardize, normalize classes, and train via mini-batch Adam with dropout."""
        X = np.asarray(X, dtype=np.float64)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        y = np.asarray(y, dtype=np.float64).reshape(-1, 1)

        self.scaler_mean_ = X.mean(axis=0)
        self.scaler_scale_ = X.std(axis=0) + 1e-8
        Xs = (X - self.scaler_mean_) / self.scaler_scale_

        # Rebalance class priors via 0/1 encoding ratio
        frac_pos = max(float(y.mean()), 1e-4)
        self.pos_weight_ = 1.0 / frac_pos
        self.neg_weight_ = 1.0 / (1.0 - frac_pos)

        self._init_params(Xs.shape[1])
        rng = np.random.RandomState(self.random_state)
        keep = 1.0 - self.dropout_rate

        # Adam state
        m_w = [np.zeros_like(w) for w in self.weights_]
        v_w = [np.zeros_like(w) for w in self.weights_]
        m_b = [np.zeros_like(b) for b in self.biases_]
        v_b = [np.zeros_like(b) for b in self.biases_]
        beta1, beta2, eps = 0.9, 0.999, 1e-8

        n = Xs.shape[0]
        step = 0

        for epoch in range(self.epochs):
            perm = rng.permutation(n)
            for start in range(0, n, self.batch_size):
                batch = perm[start : start + self.batch_size]
                Xb = Xs[batch]
                yb = y[batch]

                # --- Forward pass with inverted dropout on hidden layers ---
                a_prev = Xb
                caches = {}
                for l in range(len(self.weights_) - 1):
                    z = a_prev @ self.weights_[l] + self.biases_[l]
                    a = np.maximum(0.0, z)  # ReLU
                    mask = (rng.rand(*a.shape) < keep).astype(np.float64) / keep
                    caches[l] = (a_prev, z, mask)
                    a_prev = a * mask
                # Final layer: linear
                z_out = a_prev @ self.weights_[-1] + self.biases_[-1]
                probs = 1.0 / (1.0 + np.exp(-np.clip(z_out, -30.0, 30.0)))

                # --- Loss scaling for class imbalance ---
                weights = np.where(yb == 1, self.pos_weight_, self.neg_weight_)
                loss = float(
                    -np.mean(weights * (yb * np.log(probs + 1e-12) + (1 - yb) * np.log(1 - probs + 1e-12)))
                )

                # --- Backprop ---
                dout = (probs - yb) * weights / len(batch)
                grads_w = [None] * len(self.weights_)
                grads_b = [None] * len(self.biases_)

                # Final layer (no activation): a_prev is the dropout-scaled last hidden activation
                hid = a_prev
                grads_w[-1] = hid.T @ dout
                grads_b[-1] = dout.sum(axis=0, keepdims=True)

                # Hidden layers (ReLU with dropout mask applied)
                da_prev = dout @ self.weights_[-1].T
                for l in range(len(caches) - 1, -1, -1):
                    a0, z, mask = caches[l]
                    dz = da_prev * (z > 0).astype(np.float64) * mask
                    grads_w[l] = a0.T @ dz
                    grads_b[l] = dz.sum(axis=0, keepdims=True)
                    da_prev = dz @ self.weights_[l].T

                # --- Adam update ---
                step += 1
                t = step
                for l in range(len(self.weights_)):
                    m_w[l] = beta1 * m_w[l] + (1 - beta1) * grads_w[l]
                    v_w[l] = beta2 * v_w[l] + (1 - beta2) * (grads_w[l] ** 2)
                    mhat = m_w[l] / (1 - beta1 ** t)
                    vhat = v_w[l] / (1 - beta2 ** t)
                    self.weights_[l] -= self.learning_rate * mhat / (np.sqrt(vhat) + eps)

                    m_b[l] = beta1 * m_b[l] + (1 - beta1) * grads_b[l]
                    v_b[l] = beta2 * v_b[l] + (1 - beta2) * (grads_b[l] ** 2)
                    mhatb = m_b[l] / (1 - beta1 ** t)
                    vhatb = v_b[l] / (1 - beta2 ** t)
                    self.biases_[l] -= self.learning_rate * mhatb / (np.sqrt(vhatb) + eps)

            if epoch % 10 == 0 or epoch == self.epochs - 1:
                print(f"    [MLP] epoch {epoch + 1}/{self.epochs} loss={loss:.4f}")

        self.trained = True
        return self

    def predict_logits(self, X) -> np.ndarray:
        if not self.trained:
            raise RuntimeError("MLPDropoutClassifier must be fit before prediction.")
        X = np.asarray(X, dtype=np.float64)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        Xs = (X - self.scaler_mean_) / self.scaler_scale_
        a_prev = Xs
        for l in range(len(self.weights_) - 1):
            z = a_prev @ self.weights_[l] + self.biases_[l]
            a_prev = np.maximum(0.0, z)
        z_out = a_prev @ self.weights_[-1] + self.biases_[-1]
        return np.clip(z_out, -30.0, 30.0).ravel()

    def predict_proba(self, X) -> np.ndarray:
        logits = self.predict_logits(X)
        return 1.0 / (1.0 + np.exp(-logits))

    def predict(self, X, threshold: float = 0.5) -> np.ndarray:
        return (self.predict_proba(X) >= threshold).astype(int)

    def get_params(self, deep: bool = True) -> dict:
        return {
            "hidden_sizes": self.hidden_sizes,
            "dropout_rate": self.dropout_rate,
            "learning_rate": self.learning_rate,
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "random_state": self.random_state,
        }

    def set_params(self, **params) -> "MLPDropoutClassifier":
        for key, value in params.items():
            if not hasattr(self, key):
                raise ValueError(f"Invalid parameter {key!r}.")
            setattr(self, key, value)
        return self