import numpy as np
import pandas as pd
import logging
from typing import Optional, Tuple

logger = logging.getLogger("TitanMLLabeling")


class DynamicTripleBarrier:
    def __init__(self, tp_mult=2.5, sl_mult=1.0, max_holding=16, min_tp_pct=0.005,
                 sideways_threshold=None, exclude_sideways=True):
        self.tp_mult = tp_mult
        self.sl_mult = sl_mult
        self.max_holding = max_holding
        self.min_tp_pct = min_tp_pct
        self.sideways_threshold = sideways_threshold
        self.exclude_sideways = exclude_sideways

    def label(self, close: pd.Series, atr: pd.Series, volatility: pd.Series) -> pd.Series:
        n = len(close)
        labels = pd.Series(0, index=close.index, dtype=int)

        for i in range(n - self.max_holding):
            price = close.iloc[i]
            cur_atr = atr.iloc[i] if not pd.isna(atr.iloc[i]) else price * 0.02
            cur_vol = volatility.iloc[i] if not pd.isna(volatility.iloc[i]) else 0.02

            vol_factor = np.clip(cur_vol / 0.02, 0.5, 3.0)
            tp = max(cur_atr * self.tp_mult * vol_factor, price * self.min_tp_pct)
            sl = max(cur_atr * self.sl_mult * vol_factor, price * self.min_tp_pct * 0.5)

            tp_price = price + tp
            sl_price = price - sl

            if self.sideways_threshold is not None:
                sw_thresh = self.sideways_threshold
            else:
                sw_thresh = max(cur_atr * 0.3 / (price + 1e-10), 0.008)

            label = 0
            for j in range(1, self.max_holding + 1):
                if i + j >= n:
                    break
                h = close.iloc[i + j]
                if h >= tp_price:
                    label = 1
                    break
                elif h <= sl_price:
                    label = -1
                    break

            if label == 0:
                final_price = close.iloc[min(i + self.max_holding, n - 1)]
                ret = (final_price - price) / (price + 1e-10)
                if ret > sw_thresh:
                    label = 1
                elif ret < -sw_thresh:
                    label = -1

            labels.iloc[i] = label

        return labels


class MetaLabeler:
    def __init__(self, primary_model=None, threshold=0.5):
        self.primary_model = primary_model
        self.threshold = threshold
        self.meta_model = None
        self.is_fitted = False

    def fit(self, X: np.ndarray, y_primary: np.ndarray, y_true: np.ndarray,
            primary_proba: Optional[np.ndarray] = None):
        from sklearn.ensemble import RandomForestClassifier

        correct = (y_primary == y_true).astype(int)

        meta_features = self._build_meta_features(X, y_primary, primary_proba)

        self.meta_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=4,
            min_samples_leaf=20,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )
        self.meta_model.fit(meta_features, correct)
        self.is_fitted = True

        accuracy = np.mean(self.meta_model.predict(meta_features) == correct)
        logger.info(f"Meta-labeler训练完成 - 准确率: {accuracy:.3f}")

    def predict_trade(self, X: np.ndarray, y_primary: np.ndarray,
                      primary_proba: Optional[np.ndarray] = None) -> Tuple[np.ndarray, np.ndarray]:
        if not self.is_fitted or self.meta_model is None:
            return np.ones(len(X), dtype=bool), np.ones(len(X))

        meta_features = self._build_meta_features(X, y_primary, primary_proba)
        meta_proba = self.meta_model.predict_proba(meta_features)

        if meta_proba.shape[1] > 1:
            trade_confidence = meta_proba[:, 1]
        else:
            trade_confidence = meta_proba[:, 0]

        should_trade = trade_confidence >= self.threshold

        return should_trade, trade_confidence

    def _build_meta_features(self, X, y_primary, primary_proba=None):
        n = len(X)
        meta = np.zeros((n, X.shape[1] + 3))
        meta[:, :X.shape[1]] = X
        meta[:, X.shape[1]] = y_primary

        if primary_proba is not None and len(primary_proba.shape) > 1:
            meta[:, X.shape[1] + 1] = np.max(primary_proba, axis=1)
            entropy = -np.sum(primary_proba * np.log(primary_proba + 1e-10), axis=1)
            meta[:, X.shape[1] + 2] = entropy
        else:
            meta[:, X.shape[1] + 1] = 0.5
            meta[:, X.shape[1] + 2] = np.log(3)

        return meta


class SampleWeighter:
    @staticmethod
    def compute_uniqueness_weights(labels: pd.Series, returns: pd.Series,
                                   holding_period: int = 12) -> np.ndarray:
        n = len(labels)
        weights = np.ones(n)

        for i in range(n):
            end = min(i + holding_period, n)
            overlapping = 0
            for j in range(max(0, i - holding_period), min(i + holding_period, n)):
                if j != i and labels.iloc[j] == labels.iloc[i]:
                    overlapping += 1
            uniqueness = 1.0 / (1 + overlapping)
            weights[i] = uniqueness

        abs_ret = np.abs(returns.values[:n])
        abs_ret_norm = abs_ret / (abs_ret.mean() + 1e-10)
        weights *= np.clip(abs_ret_norm, 0.1, 5.0)

        weights /= (weights.sum() / n)

        return weights

    @staticmethod
    def compute_time_decay_weights(n: int, decay_factor: float = 0.99) -> np.ndarray:
        weights = np.array([decay_factor ** (n - 1 - i) for i in range(n)])
        weights /= (weights.sum() / n)
        return weights

    @staticmethod
    def combine_weights(*weight_arrays) -> np.ndarray:
        combined = np.ones(len(weight_arrays[0]))
        for w in weight_arrays:
            combined *= w
        combined /= (combined.sum() / len(combined))
        return combined
